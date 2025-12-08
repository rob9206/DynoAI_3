"""
DynoAI Auto-Tune Workflow Engine

Orchestrates the complete auto-tuning workflow:
1. Import dyno logs from Power Core
2. Analyze AFR error by RPM/MAP zone
3. Generate VE correction recommendations
4. Export corrections to Power Core format

This workflow uses the existing VE operations but coordinates
the end-to-end process for Power Core integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from api.services.powercore_integration import (
    PowerVisionLog,
    TuneFile,
    TuneTable,
    generate_pvv_xml,
    generate_tunelab_script,
    parse_powervision_log,
    parse_pvv_tune,
    powervision_log_to_dynoai_format,
)


@dataclass
class AFRAnalysisResult:
    """Results from AFR error analysis."""

    mean_error_pct: float  # Overall mean AFR error
    zones_rich: int  # Zones running rich (AFR < target)
    zones_lean: int  # Zones running lean (AFR > target)
    zones_ok: int  # Zones within tolerance
    max_lean_pct: float  # Maximum lean error
    max_rich_pct: float  # Maximum rich error
    error_by_zone: pd.DataFrame  # Error matrix by RPM/MAP
    hit_count_by_zone: pd.DataFrame  # Sample count by zone


@dataclass
class VECorrectionResult:
    """Results from VE correction calculation."""

    correction_table: np.ndarray  # Correction multipliers (e.g., 0.95 to 1.05)
    rpm_axis: list[float]
    map_axis: list[float]
    zones_adjusted: int
    max_correction_pct: float
    min_correction_pct: float
    clipped_zones: int  # Zones where correction was clipped to limits


@dataclass
class AutoTuneSession:
    """A complete auto-tune session."""

    id: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    log_file: Optional[str] = None
    tune_file: Optional[str] = None

    # Parsed data
    pv_log: Optional[PowerVisionLog] = None
    dynoai_data: Optional[pd.DataFrame] = None
    base_tune: Optional[TuneFile] = None

    # Analysis results
    afr_analysis: Optional[AFRAnalysisResult] = None
    ve_corrections: Optional[VECorrectionResult] = None

    # Output files
    output_tunelab_script: Optional[str] = None
    output_pvv_file: Optional[str] = None

    status: str = "initialized"
    errors: list[str] = field(default_factory=list)


class AutoTuneWorkflow:
    """
    Orchestrates the auto-tune workflow for Power Core integration.

    Usage:
        workflow = AutoTuneWorkflow()
        session = workflow.create_session()
        workflow.import_log(session, "path/to/log.csv")
        workflow.analyze_afr(session)
        workflow.calculate_corrections(session)
        workflow.export_corrections(session, "path/to/output")
    """

    # Default axis values for VE tables
    DEFAULT_RPM_AXIS = [
        1000,
        1500,
        2000,
        2500,
        3000,
        3500,
        4000,
        4500,
        5000,
        5500,
        6000,
    ]
    DEFAULT_MAP_AXIS = [20, 30, 40, 50, 60, 70, 80, 90, 100]

    # Safety limits
    MAX_CORRECTION_PCT = 7.0  # Maximum ±7% correction
    MIN_HITS_PER_ZONE = 10  # Minimum samples needed per zone
    AFR_ERROR_TOLERANCE = 2.0  # % error considered "OK"

    def __init__(
        self,
        rpm_axis: Optional[list[float]] = None,
        map_axis: Optional[list[float]] = None,
        max_correction_pct: float = 7.0,
    ) -> None:
        self.rpm_axis = rpm_axis or self.DEFAULT_RPM_AXIS
        self.map_axis = map_axis or self.DEFAULT_MAP_AXIS
        self.max_correction_pct = max_correction_pct
        self.sessions: dict[str, AutoTuneSession] = {}

    def create_session(self) -> AutoTuneSession:
        """Create a new auto-tune session."""
        session_id = f"autotune_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        session = AutoTuneSession(id=session_id)
        self.sessions[session_id] = session
        return session

    def import_log(self, session: AutoTuneSession, log_path: str) -> bool:
        """
        Import a Power Vision log file.

        Returns True if successful, False otherwise.
        """
        try:
            session.log_file = log_path
            session.pv_log = parse_powervision_log(log_path)
            session.dynoai_data = powervision_log_to_dynoai_format(session.pv_log)
            session.status = "log_imported"
            return True
        except Exception as e:
            session.errors.append(f"Log import failed: {e}")
            session.status = "error"
            return False

    def import_tune(self, session: AutoTuneSession, tune_path: str) -> bool:
        """
        Import a PVV tune file as the base tune.

        Returns True if successful, False otherwise.
        """
        try:
            session.tune_file = tune_path
            session.base_tune = parse_pvv_tune(tune_path)
            return True
        except Exception as e:
            session.errors.append(f"Tune import failed: {e}")
            return False

    def analyze_afr(self, session: AutoTuneSession) -> Optional[AFRAnalysisResult]:
        """
        Analyze AFR error across RPM/MAP zones.

        Requires log to be imported first.
        """
        if session.dynoai_data is None:
            session.errors.append("No log data - import log first")
            return None

        df = session.dynoai_data

        # Check for required columns
        required_cols = ["Engine RPM", "MAP kPa"]
        afr_cols = [c for c in df.columns if "AFR" in c]

        if not all(c in df.columns for c in required_cols):
            session.errors.append(f"Missing required columns: {required_cols}")
            return None

        if not afr_cols:
            session.errors.append("No AFR columns found in data")
            return None

        # Use first AFR column pair (measured vs target)
        afr_meas_col = next(
            (c for c in afr_cols if "Meas" in c), afr_cols[0] if afr_cols else None
        )
        afr_target_col = next((c for c in afr_cols if "Target" in c), None)

        if afr_meas_col is None:
            session.errors.append("No AFR measurement column found")
            return None

        # If no target, assume stoich (14.7)
        if afr_target_col and afr_target_col in df.columns:
            target_afr = df[afr_target_col]
        else:
            target_afr = pd.Series([14.7] * len(df))

        meas_afr = df[afr_meas_col]

        # Calculate error: (measured - target) / target * 100
        # Positive = lean, Negative = rich
        afr_error_pct = (meas_afr - target_afr) / target_afr * 100

        # Bin data by RPM/MAP
        rpm_bins = pd.cut(
            df["Engine RPM"], bins=[0] + self.rpm_axis + [99999], labels=False
        )
        map_bins = pd.cut(df["MAP kPa"], bins=[0] + self.map_axis + [999], labels=False)

        # Create error matrix
        error_matrix = np.full((len(self.rpm_axis), len(self.map_axis)), np.nan)
        hit_matrix = np.zeros((len(self.rpm_axis), len(self.map_axis)))

        for rpm_idx in range(len(self.rpm_axis)):
            for map_idx in range(len(self.map_axis)):
                mask = (rpm_bins == rpm_idx + 1) & (map_bins == map_idx + 1)
                zone_errors = afr_error_pct[mask]

                if len(zone_errors) >= self.MIN_HITS_PER_ZONE:
                    # Use median to reduce outlier impact
                    error_matrix[rpm_idx, map_idx] = zone_errors.median()
                    hit_matrix[rpm_idx, map_idx] = len(zone_errors)

        # Create DataFrames with labeled axes
        error_df = pd.DataFrame(
            error_matrix,
            index=pd.Index(self.rpm_axis, name="RPM"),
            columns=pd.Index(self.map_axis, name="MAP"),
        )
        hit_df = pd.DataFrame(
            hit_matrix,
            index=pd.Index(self.rpm_axis, name="RPM"),
            columns=pd.Index(self.map_axis, name="MAP"),
        )

        # Count zones by status
        valid_errors = error_matrix[~np.isnan(error_matrix)]
        zones_lean = int(np.sum(valid_errors > self.AFR_ERROR_TOLERANCE))
        zones_rich = int(np.sum(valid_errors < -self.AFR_ERROR_TOLERANCE))
        zones_ok = int(np.sum(np.abs(valid_errors) <= self.AFR_ERROR_TOLERANCE))

        result = AFRAnalysisResult(
            mean_error_pct=float(np.nanmean(error_matrix)),
            zones_rich=zones_rich,
            zones_lean=zones_lean,
            zones_ok=zones_ok,
            max_lean_pct=float(np.nanmax(error_matrix)) if valid_errors.size else 0.0,
            max_rich_pct=float(np.nanmin(error_matrix)) if valid_errors.size else 0.0,
            error_by_zone=error_df,
            hit_count_by_zone=hit_df,
        )

        session.afr_analysis = result
        session.status = "afr_analyzed"
        return result

    def calculate_corrections(
        self, session: AutoTuneSession
    ) -> Optional[VECorrectionResult]:
        """
        Calculate VE corrections based on AFR analysis.

        Requires AFR analysis to be complete.
        """
        if session.afr_analysis is None:
            session.errors.append("No AFR analysis - run analyze_afr first")
            return None

        error_matrix = session.afr_analysis.error_by_zone.values
        hit_matrix = session.afr_analysis.hit_count_by_zone.values

        # Calculate correction multipliers
        # If running lean (positive error), reduce VE to reduce fuel
        # If running rich (negative error), increase VE to increase fuel
        # Wait... that's backwards. VE affects fuel:
        # - Higher VE = more fuel
        # - If lean (need more fuel), increase VE
        # - If rich (need less fuel), decrease VE
        # So correction = 1 + (error_pct / 100)
        # Actually: If measured AFR is higher than target (lean),
        # we need MORE fuel, so INCREASE VE.
        # correction = 1 + (measured - target) / target
        # But error is already (meas - target) / target * 100
        # So correction = 1 + error_pct / 100

        correction_matrix = np.ones_like(error_matrix)

        # Apply corrections where we have valid data
        valid_mask = ~np.isnan(error_matrix) & (hit_matrix >= self.MIN_HITS_PER_ZONE)

        # Correction factor: if lean (+ error), add fuel (increase VE)
        # Convert AFR error to VE correction
        raw_corrections = 1 + error_matrix / 100

        # Apply safety clamps
        min_mult = 1 - self.max_correction_pct / 100
        max_mult = 1 + self.max_correction_pct / 100

        clamped_corrections = np.clip(raw_corrections, min_mult, max_mult)
        clipped_count = int(
            np.sum(valid_mask & (raw_corrections != clamped_corrections))
        )

        # Only apply where valid
        correction_matrix[valid_mask] = clamped_corrections[valid_mask]

        # For zones without enough data, use 1.0 (no change)
        correction_matrix[~valid_mask] = 1.0

        result = VECorrectionResult(
            correction_table=correction_matrix,
            rpm_axis=self.rpm_axis,
            map_axis=self.map_axis,
            zones_adjusted=int(np.sum(valid_mask)),
            max_correction_pct=float((np.nanmax(correction_matrix) - 1) * 100),
            min_correction_pct=float((np.nanmin(correction_matrix) - 1) * 100),
            clipped_zones=clipped_count,
        )

        session.ve_corrections = result
        session.status = "corrections_calculated"
        return result

    def export_tunelab_script(
        self,
        session: AutoTuneSession,
        output_dir: str,
        correction_table: str = "Volumetric Efficiency",
    ) -> Optional[str]:
        """
        Export a TuneLab script to apply corrections in Power Core.

        Returns path to generated script.
        """
        if session.ve_corrections is None:
            session.errors.append("No corrections - run calculate_corrections first")
            return None

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        script_path = output_path / f"dynoai_correction_{session.id}.py"
        script = generate_tunelab_script(
            correction_table=correction_table,
            afr_channel="Air/Fuel Ratio 1",
            smoothing=500.0,
            min_afr=10.0,
            max_afr=19.0,
        )

        with open(script_path, "w") as f:
            f.write(script)

        session.output_tunelab_script = str(script_path)
        return str(script_path)

    def export_pvv_corrections(
        self,
        session: AutoTuneSession,
        output_dir: str,
        table_name: str = "VE Correction",
    ) -> Optional[str]:
        """
        Export VE corrections as a PVV file.

        Returns path to generated PVV file.
        """
        if session.ve_corrections is None:
            session.errors.append("No corrections - run calculate_corrections first")
            return None

        corr = session.ve_corrections

        # Create a TuneFile with the correction table
        tune = TuneFile()
        tune.tables[table_name] = TuneTable(
            name=table_name,
            units="%",
            row_axis=[float(r) for r in corr.rpm_axis],
            row_units="RPM",
            col_axis=[float(m) for m in corr.map_axis],
            col_units="MAP (KPa)",
            values=corr.correction_table * 100,  # Convert to percentage
        )

        # Add metadata as scalars
        tune.scalars["Max Correction %"] = corr.max_correction_pct
        tune.scalars["Min Correction %"] = corr.min_correction_pct
        tune.scalars["Zones Adjusted"] = float(corr.zones_adjusted)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        pvv_path = output_path / f"dynoai_ve_correction_{session.id}.pvv"

        pvv_xml = generate_pvv_xml(tune)
        with open(pvv_path, "w", encoding="utf-8") as f:
            f.write(pvv_xml)

        session.output_pvv_file = str(pvv_path)
        session.status = "exported"
        return str(pvv_path)

    def run_full_workflow(
        self,
        log_path: str,
        output_dir: str,
        tune_path: Optional[str] = None,
    ) -> AutoTuneSession:
        """
        Run the complete auto-tune workflow.

        1. Create session
        2. Import log
        3. Optionally import base tune
        4. Analyze AFR
        5. Calculate corrections
        6. Export results

        Returns the completed session.
        """
        session = self.create_session()

        # Import log
        if not self.import_log(session, log_path):
            return session

        # Optionally import base tune
        if tune_path:
            self.import_tune(session, tune_path)

        # Analyze AFR
        if self.analyze_afr(session) is None:
            return session

        # Calculate corrections
        if self.calculate_corrections(session) is None:
            return session

        # Export both formats
        self.export_tunelab_script(session, output_dir)
        self.export_pvv_corrections(session, output_dir)

        return session

    def get_session_summary(self, session: AutoTuneSession) -> dict:
        """Get a summary of the session for display."""
        summary: dict = {
            "id": session.id,
            "status": session.status,
            "created_at": session.created_at,
            "log_file": session.log_file,
            "tune_file": session.tune_file,
            "errors": session.errors,
        }

        if session.pv_log:
            summary["log_signals"] = len(session.pv_log.signals)
            summary["log_rows"] = len(session.pv_log.data)

        if session.afr_analysis:
            afr = session.afr_analysis
            summary["afr_analysis"] = {
                "mean_error_pct": round(afr.mean_error_pct, 2),
                "zones_lean": afr.zones_lean,
                "zones_rich": afr.zones_rich,
                "zones_ok": afr.zones_ok,
                "max_lean_pct": round(afr.max_lean_pct, 2),
                "max_rich_pct": round(afr.max_rich_pct, 2),
            }

        if session.ve_corrections:
            corr = session.ve_corrections
            summary["ve_corrections"] = {
                "zones_adjusted": corr.zones_adjusted,
                "max_correction_pct": round(corr.max_correction_pct, 2),
                "min_correction_pct": round(corr.min_correction_pct, 2),
                "clipped_zones": corr.clipped_zones,
            }

        if session.output_tunelab_script:
            summary["output_tunelab_script"] = session.output_tunelab_script

        if session.output_pvv_file:
            summary["output_pvv_file"] = session.output_pvv_file

        return summary


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AFRAnalysisResult",
    "AutoTuneSession",
    "AutoTuneWorkflow",
    "VECorrectionResult",
]
