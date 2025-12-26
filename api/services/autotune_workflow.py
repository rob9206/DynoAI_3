"""
DynoAI Auto-Tune Workflow Engine

Orchestrates the complete auto-tuning workflow:
1. Import dyno logs from multiple sources (Power Vision, JetDrive, CSV)
2. Analyze AFR error by RPM/MAP zone using 2D grid
3. Generate VE correction recommendations (7% per AFR point)
4. Export corrections to Power Core format (PVV XML, TuneLab)

This is the UNIFIED analysis engine for all DynoAI data sources.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Union

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

# Import versioned VE math module
from dynoai.core.ve_math import (
    MathVersion,
    calculate_ve_correction,
    correction_to_percentage,
)


class DataSource(str, Enum):
    """Supported data sources for auto-tune analysis."""

    POWER_VISION = "power_vision"
    JETDRIVE = "jetdrive"
    CSV = "csv"
    SIMULATION = "simulation"


@dataclass
class AFRAnalysisResult:
    """Results from AFR error analysis."""

    mean_error_pct: float  # Overall mean AFR error (VE delta %)
    mean_afr_error: float  # Overall mean AFR error (AFR points)
    zones_rich: int  # Zones running rich (AFR < target)
    zones_lean: int  # Zones running lean (AFR > target)
    zones_ok: int  # Zones within tolerance
    zones_no_data: int  # Zones without enough data
    max_lean_pct: float  # Maximum lean error
    max_rich_pct: float  # Maximum rich error
    error_by_zone: pd.DataFrame  # Error matrix by RPM/MAP (AFR points)
    ve_delta_by_zone: pd.DataFrame  # VE correction % by zone
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
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    data_source: DataSource = DataSource.CSV
    log_file: Optional[str] = None
    tune_file: Optional[str] = None

    # Parsed data
    pv_log: Optional[PowerVisionLog] = None
    dynoai_data: Optional[pd.DataFrame] = None
    base_tune: Optional[TuneFile] = None

    # Analysis results
    afr_analysis: Optional[AFRAnalysisResult] = None
    ve_corrections: Optional[VECorrectionResult] = None

    # Peak performance
    peak_hp: float = 0.0
    peak_hp_rpm: float = 0.0
    peak_tq: float = 0.0
    peak_tq_rpm: float = 0.0

    # Output files
    output_dir: Optional[str] = None
    output_tunelab_script: Optional[str] = None
    output_pvv_file: Optional[str] = None

    status: str = "initialized"
    errors: list[str] = field(default_factory=list)


class AutoTuneWorkflow:
    """
    UNIFIED Auto-Tune Workflow Engine for all DynoAI data sources.

    Supports:
    - Power Vision CSV logs
    - JetDrive multicast captures
    - Generic CSV files
    - Simulated data

    Uses the DynoAI standard "7% per AFR point" VE correction formula.

    Usage:
        workflow = AutoTuneWorkflow()
        session = workflow.create_session()

        # Option 1: Power Vision log
        workflow.import_log(session, "path/to/log.csv")

        # Option 2: JetDrive CSV
        workflow.import_jetdrive_csv(session, "path/to/jetdrive.csv")

        # Option 3: Generic DataFrame
        workflow.import_dataframe(session, df)

        # Then analyze and export
        workflow.analyze_afr(session)
        workflow.calculate_corrections(session)
        workflow.export_all(session, "path/to/output")
    """

    # Standard DynoAI grid - 11 RPM x 9 MAP = 99 cells
    DEFAULT_RPM_AXIS = [
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
        6500,
    ]
    DEFAULT_MAP_AXIS = [20, 30, 40, 50, 60, 70, 80, 90, 100]

    # DynoAI standard correction formula (v1.0.0 legacy)
    # DEPRECATED: Use math_version instead
    VE_PCT_PER_AFR_POINT = 7.0  # 7% VE change per 1 AFR point

    # Default math version for VE calculations
    # v1.0.0: Linear 7% per AFR point (legacy)
    # v2.0.0: Ratio model AFR_measured/AFR_target (default, physically accurate)
    DEFAULT_MATH_VERSION = MathVersion.V2_0_0

    # Safety limits
    MAX_CORRECTION_PCT = 10.0  # Maximum ±10% correction
    MIN_HITS_PER_ZONE = 3  # Minimum samples needed per zone
    AFR_ERROR_TOLERANCE = 0.3  # AFR points considered "OK" (±0.3)

    # AFR targets by MAP load (kPa) - richer at higher loads
    AFR_TARGETS_BY_MAP = {
        20: 14.7,  # Deep vacuum / decel
        30: 14.7,  # Idle
        40: 14.5,  # Light cruise
        50: 14.0,  # Cruise
        60: 13.5,  # Part throttle
        70: 13.0,  # Mid load
        80: 12.8,  # Heavy load
        90: 12.5,  # High load
        100: 12.2,  # WOT / boost
    }

    def __init__(
        self,
        rpm_axis: Optional[list[float]] = None,
        map_axis: Optional[list[float]] = None,
        max_correction_pct: float = 10.0,
        afr_targets: Optional[dict[int, float]] = None,
        math_version: Optional[MathVersion] = None,
    ) -> None:
        self.rpm_axis = rpm_axis or self.DEFAULT_RPM_AXIS
        self.map_axis = map_axis or self.DEFAULT_MAP_AXIS
        self.max_correction_pct = max_correction_pct
        self.math_version = math_version or self.DEFAULT_MATH_VERSION
        # Allow custom AFR targets (keyed by MAP in kPa)
        if afr_targets:
            self.afr_targets_by_map = {int(k): float(v) for k, v in afr_targets.items()}
        else:
            self.afr_targets_by_map = dict(self.AFR_TARGETS_BY_MAP)
        self.sessions: dict[str, AutoTuneSession] = {}

    def create_session(
        self, run_id: Optional[str] = None, data_source: DataSource = DataSource.CSV
    ) -> AutoTuneSession:
        """Create a new auto-tune session."""
        session_id = (
            run_id or f"autotune_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        )
        session = AutoTuneSession(id=session_id, data_source=data_source)
        self.sessions[session_id] = session
        return session

    def get_target_afr(self, map_kpa: float) -> float:
        """Get target AFR based on MAP (load).

        Uses custom afr_targets_by_map if set, otherwise falls back to defaults.
        """
        # Find nearest MAP bin from configured targets
        target_keys = list(self.afr_targets_by_map.keys())
        if not target_keys:
            return 14.0
        nearest_map = min(target_keys, key=lambda x: abs(x - map_kpa))
        return self.afr_targets_by_map.get(nearest_map, 14.0)

    def set_afr_targets(self, afr_targets: dict[int, float]) -> None:
        """Update AFR targets.

        Args:
            afr_targets: Dict mapping MAP (kPa) to target AFR.
                         Example: {20: 14.7, 100: 12.2}
        """
        self.afr_targets_by_map = {int(k): float(v) for k, v in afr_targets.items()}

    def import_log(self, session: AutoTuneSession, log_path: str) -> bool:
        """
        Import a Power Vision log file.

        Returns True if successful, False otherwise.
        """
        try:
            session.log_file = log_path
            session.data_source = DataSource.POWER_VISION
            session.pv_log = parse_powervision_log(log_path)
            session.dynoai_data = powervision_log_to_dynoai_format(session.pv_log)
            self._extract_peak_performance(session)
            session.status = "log_imported"
            return True
        except Exception as e:
            session.errors.append(f"Log import failed: {e}")
            session.status = "error"
            return False

    def import_jetdrive_csv(self, session: AutoTuneSession, csv_path: str) -> bool:
        """
        Import a JetDrive CSV capture file.

        Expected columns: timestamp_ms, RPM, Torque, Horsepower, AFR, MAP_kPa (optional)

        Returns True if successful, False otherwise.
        """
        try:
            session.log_file = csv_path
            session.data_source = DataSource.JETDRIVE
            df = pd.read_csv(csv_path)

            # Normalize column names for DynoAI format
            column_map = {
                "RPM": "Engine RPM",
                "MAP_kPa": "MAP kPa",
                "Torque": "Torque",
                "Horsepower": "Horsepower",
                "AFR": "AFR Meas",
            }
            df = df.rename(
                columns={k: v for k, v in column_map.items() if k in df.columns}
            )

            # If no MAP column, estimate from RPM
            if "MAP kPa" not in df.columns:
                df["MAP kPa"] = df["Engine RPM"].apply(self._estimate_map_from_rpm)

            session.dynoai_data = df
            self._extract_peak_performance(session)
            session.status = "log_imported"
            return True
        except Exception as e:
            session.errors.append(f"JetDrive CSV import failed: {e}")
            session.status = "error"
            return False

    def import_dataframe(
        self,
        session: AutoTuneSession,
        df: pd.DataFrame,
        source: DataSource = DataSource.CSV,
    ) -> bool:
        """
        Import a pandas DataFrame directly.

        Required columns: Engine RPM (or RPM), AFR Meas (or AFR)
        Optional columns: MAP kPa (or MAP_kPa), Horsepower, Torque

        Returns True if successful, False otherwise.
        """
        try:
            session.data_source = source

            # Normalize column names
            column_map = {
                "RPM": "Engine RPM",
                "MAP_kPa": "MAP kPa",
                "MAP": "MAP kPa",
                "AFR": "AFR Meas",
            }
            df = df.rename(
                columns={k: v for k, v in column_map.items() if k in df.columns}
            )

            # If no MAP column, estimate from RPM
            if "MAP kPa" not in df.columns and "Engine RPM" in df.columns:
                df["MAP kPa"] = df["Engine RPM"].apply(self._estimate_map_from_rpm)

            session.dynoai_data = df
            self._extract_peak_performance(session)
            session.status = "log_imported"
            return True
        except Exception as e:
            session.errors.append(f"DataFrame import failed: {e}")
            session.status = "error"
            return False

    def _estimate_map_from_rpm(self, rpm: float) -> float:
        """Estimate MAP from RPM when not available."""
        if rpm < 2000:
            return 35  # Vacuum at idle
        elif rpm < 3500:
            return 50  # Light load
        elif rpm < 5000:
            return 65  # Mid load
        else:
            return 80  # High load / WOT

    def _extract_peak_performance(self, session: AutoTuneSession) -> None:
        """Extract peak HP and torque from session data."""
        if session.dynoai_data is None:
            return

        df = session.dynoai_data

        def _find_col_case_insensitive(columns, *, prefers: list[str]) -> str | None:
            """
            Find a likely column by case-insensitive substring matching.
            `prefers` should be ordered from most-specific to least-specific.
            """
            for pref in prefers:
                pref_l = pref.lower()
                for c in columns:
                    c_s = str(c)
                    c_l = c_s.lower()
                    if pref_l in c_l:
                        return c_s
            return None

        # Look for HP column (case-insensitive; prefer explicit names)
        hp_col = _find_col_case_insensitive(
            df.columns,
            prefers=[
                "horsepower",
                "horse power",
                " hp",  # suffix form "Engine HP"
                "hp ",  # prefix form "HP Engine"
                "power",
            ],
        )
        if hp_col and hp_col in df.columns:
            peak_idx = df[hp_col].idxmax()
            session.peak_hp = float(df.loc[peak_idx, hp_col])
            rpm_col = "Engine RPM" if "Engine RPM" in df.columns else "RPM"
            if rpm_col in df.columns:
                session.peak_hp_rpm = float(df.loc[peak_idx, rpm_col])

        # Look for torque column (case-insensitive)
        tq_col = _find_col_case_insensitive(
            df.columns,
            prefers=[
                "torque",
                " tq",
                "tq ",
            ],
        )
        if tq_col and tq_col in df.columns:
            peak_idx = df[tq_col].idxmax()
            session.peak_tq = float(df.loc[peak_idx, tq_col])
            rpm_col = "Engine RPM" if "Engine RPM" in df.columns else "RPM"
            if rpm_col in df.columns:
                session.peak_tq_rpm = float(df.loc[peak_idx, rpm_col])

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
        Analyze AFR error across RPM/MAP zones using 2D grid.

        Uses the DynoAI standard formula:
        - AFR error (points) = measured AFR - target AFR
        - VE correction (%) = +AFR_error * 7%  (7% per AFR point)

        Requires log to be imported first.
        """
        if session.dynoai_data is None:
            session.errors.append("No log data - import log first")
            return None

        df = session.dynoai_data.copy()

        # Find RPM column
        rpm_col = next((c for c in df.columns if c in ["Engine RPM", "RPM"]), None)
        if rpm_col is None:
            session.errors.append("No RPM column found in data")
            return None

        # Find MAP column
        map_col = next(
            (c for c in df.columns if c in ["MAP kPa", "MAP_kPa", "MAP"]), None
        )
        if map_col is None:
            # Estimate from RPM
            df["MAP kPa"] = df[rpm_col].apply(self._estimate_map_from_rpm)
            map_col = "MAP kPa"

        # Find AFR column
        afr_cols = [c for c in df.columns if "AFR" in c]
        if not afr_cols:
            session.errors.append("No AFR columns found in data")
            return None

        afr_meas_col = next((c for c in afr_cols if "Meas" in c), afr_cols[0])

        # Convert AFR to numeric
        df[afr_meas_col] = pd.to_numeric(df[afr_meas_col], errors="coerce")
        df = df.dropna(subset=[afr_meas_col])

        # Initialize 2D matrices
        n_rpm = len(self.rpm_axis)
        n_map = len(self.map_axis)
        afr_error_matrix = np.full((n_rpm, n_map), np.nan)  # AFR points
        ve_delta_matrix = np.full((n_rpm, n_map), np.nan)  # VE %
        hit_matrix = np.zeros((n_rpm, n_map), dtype=int)
        afr_sum = np.zeros((n_rpm, n_map))

        # Helper to find nearest bin
        def nearest_bin(val: float, bins: list) -> int:
            return min(range(len(bins)), key=lambda i: abs(bins[i] - val))

        # Bin each sample into the grid
        for _, row in df.iterrows():
            rpm = row[rpm_col]
            afr = row[afr_meas_col]
            map_kpa = row[map_col]

            if pd.isna(rpm) or pd.isna(afr) or pd.isna(map_kpa):
                continue

            rpm_idx = nearest_bin(rpm, self.rpm_axis)
            map_idx = nearest_bin(map_kpa, self.map_axis)

            hit_matrix[rpm_idx, map_idx] += 1
            afr_sum[rpm_idx, map_idx] += afr

        # Calculate mean AFR and error per cell
        for i in range(n_rpm):
            for j in range(n_map):
                if hit_matrix[i, j] >= self.MIN_HITS_PER_ZONE:
                    mean_afr = afr_sum[i, j] / hit_matrix[i, j]
                    target_afr = self.get_target_afr(self.map_axis[j])

                    # AFR error in points (positive = lean, negative = rich)
                    afr_error = mean_afr - target_afr
                    afr_error_matrix[i, j] = afr_error

                    # VE correction using versioned math module
                    # v2.0.0 (default): Ratio model - VE_correction = AFR_measured / AFR_target
                    # v1.0.0 (legacy): Linear model - VE_correction = 1 + (AFR_error * 7%)
                    # Lean (+error) -> need more fuel -> INCREASE VE -> positive VE delta %
                    # Rich (-error) -> need less fuel -> DECREASE VE -> negative VE delta %
                    ve_correction = calculate_ve_correction(
                        mean_afr, target_afr, version=self.math_version, clamp=False
                    )
                    ve_delta_pct = correction_to_percentage(ve_correction)
                    ve_delta_matrix[i, j] = ve_delta_pct

        # Create DataFrames with labeled axes
        error_df = pd.DataFrame(
            afr_error_matrix,
            index=pd.Index(self.rpm_axis, name="RPM"),
            columns=pd.Index(self.map_axis, name="MAP"),
        )
        ve_delta_df = pd.DataFrame(
            ve_delta_matrix,
            index=pd.Index(self.rpm_axis, name="RPM"),
            columns=pd.Index(self.map_axis, name="MAP"),
        )
        hit_df = pd.DataFrame(
            hit_matrix,
            index=pd.Index(self.rpm_axis, name="RPM"),
            columns=pd.Index(self.map_axis, name="MAP"),
        )

        # Count zones by status (based on AFR error, not VE delta)
        valid_mask = ~np.isnan(afr_error_matrix)
        valid_errors = afr_error_matrix[valid_mask]

        zones_lean = int(np.sum(valid_errors > self.AFR_ERROR_TOLERANCE))
        zones_rich = int(np.sum(valid_errors < -self.AFR_ERROR_TOLERANCE))
        zones_ok = int(np.sum(np.abs(valid_errors) <= self.AFR_ERROR_TOLERANCE))
        zones_no_data = int(np.sum(~valid_mask))

        # Mean VE delta (percentage)
        valid_ve_deltas = ve_delta_matrix[valid_mask]
        mean_ve_delta = float(np.mean(valid_ve_deltas)) if valid_ve_deltas.size else 0.0

        result = AFRAnalysisResult(
            mean_error_pct=mean_ve_delta,
            mean_afr_error=float(np.mean(valid_errors)) if valid_errors.size else 0.0,
            zones_rich=zones_rich,
            zones_lean=zones_lean,
            zones_ok=zones_ok,
            zones_no_data=zones_no_data,
            max_lean_pct=(
                float(np.nanmax(ve_delta_matrix)) if valid_ve_deltas.size else 0.0
            ),
            max_rich_pct=(
                float(np.nanmin(ve_delta_matrix)) if valid_ve_deltas.size else 0.0
            ),
            error_by_zone=error_df,
            ve_delta_by_zone=ve_delta_df,
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

        Uses the pre-calculated VE delta from analyze_afr (which already
        applies the 7% per AFR point formula).

        Requires AFR analysis to be complete.
        """
        if session.afr_analysis is None:
            session.errors.append("No AFR analysis - run analyze_afr first")
            return None

        # VE delta is already calculated in analyze_afr using 7% per AFR point
        ve_delta_matrix = session.afr_analysis.ve_delta_by_zone.values
        hit_matrix = session.afr_analysis.hit_count_by_zone.values

        # Convert VE delta % to multiplier (e.g., +5% -> 1.05)
        correction_matrix = np.ones_like(ve_delta_matrix, dtype=float)

        # Apply corrections where we have valid data
        valid_mask = ~np.isnan(ve_delta_matrix) & (hit_matrix >= self.MIN_HITS_PER_ZONE)

        # Convert percentage to multiplier
        raw_corrections = 1 + ve_delta_matrix / 100

        # Apply safety clamps
        min_mult = 1 - self.max_correction_pct / 100
        max_mult = 1 + self.max_correction_pct / 100

        clamped_corrections = np.clip(raw_corrections, min_mult, max_mult)
        clipped_count = int(
            np.sum(
                valid_mask & (np.abs(raw_corrections - clamped_corrections) > 0.0001)
            )
        )

        # Only apply where valid
        correction_matrix[valid_mask] = clamped_corrections[valid_mask]

        # For zones without enough data, use 1.0 (no change)
        correction_matrix[~valid_mask] = 1.0

        result = VECorrectionResult(
            correction_table=correction_matrix,
            rpm_axis=list(self.rpm_axis),
            map_axis=list(self.map_axis),
            zones_adjusted=int(np.sum(valid_mask)),
            max_correction_pct=(
                float((np.nanmax(correction_matrix[valid_mask]) - 1) * 100)
                if np.any(valid_mask)
                else 0.0
            ),
            min_correction_pct=(
                float((np.nanmin(correction_matrix[valid_mask]) - 1) * 100)
                if np.any(valid_mask)
                else 0.0
            ),
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

    def export_all(
        self,
        session: AutoTuneSession,
        output_dir: str,
    ) -> dict[str, str]:
        """
        Export all outputs: PVV, TuneLab script, CSV grids, manifest.

        Returns dict of output file paths.
        """
        outputs = {}
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        session.output_dir = str(output_path)

        # 1. Export PVV XML
        pvv_path = self.export_pvv_corrections(session, output_dir)
        if pvv_path:
            outputs["pvv_file"] = pvv_path

        # 2. Export TuneLab script
        script_path = self.export_tunelab_script(session, output_dir)
        if script_path:
            outputs["tunelab_script"] = script_path

        # 3. Export VE correction grid CSV
        if session.ve_corrections:
            ve_csv_path = output_path / "VE_Corrections_2D.csv"
            corr = session.ve_corrections
            with open(ve_csv_path, "w") as f:
                f.write("RPM\\MAP," + ",".join(str(m) for m in corr.map_axis) + "\n")
                for i, rpm in enumerate(corr.rpm_axis):
                    row = [str(rpm)] + [
                        f"{corr.correction_table[i, j]:.4f}"
                        for j in range(len(corr.map_axis))
                    ]
                    f.write(",".join(row) + "\n")
            outputs["ve_corrections_csv"] = str(ve_csv_path)

        # 4. Export AFR error grid CSV
        if session.afr_analysis:
            afr_csv_path = output_path / "AFR_Error_2D.csv"
            session.afr_analysis.error_by_zone.to_csv(afr_csv_path)
            outputs["afr_error_csv"] = str(afr_csv_path)

            # Hit count CSV
            hits_csv_path = output_path / "Hit_Count_2D.csv"
            session.afr_analysis.hit_count_by_zone.to_csv(hits_csv_path)
            outputs["hit_count_csv"] = str(hits_csv_path)

        # 5. Export manifest.json
        manifest = self.get_session_summary(session)
        manifest["outputs"] = outputs
        manifest_path = output_path / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, default=str)
        outputs["manifest"] = str(manifest_path)

        session.status = "exported"
        return outputs

    def run_full_workflow(
        self,
        log_path: str,
        output_dir: str,
        tune_path: Optional[str] = None,
        data_source: DataSource = DataSource.POWER_VISION,
    ) -> AutoTuneSession:
        """
        Run the complete auto-tune workflow.

        1. Create session
        2. Import log (auto-detect or specify source)
        3. Optionally import base tune
        4. Analyze AFR
        5. Calculate corrections
        6. Export all results

        Returns the completed session.
        """
        session = self.create_session(data_source=data_source)

        # Import log based on source type
        if data_source == DataSource.JETDRIVE:
            if not self.import_jetdrive_csv(session, log_path):
                return session
        else:
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

        # Export all formats
        self.export_all(session, output_dir)

        return session

    def get_session_summary(self, session: AutoTuneSession) -> dict:
        """Get a summary of the session for display."""

        def _build_power_curve_from_df(df: "pd.DataFrame") -> list[dict[str, float]]:
            try:
                if df is None or df.empty:
                    return []

                rpm_col = next(
                    (c for c in df.columns if c in ["Engine RPM", "RPM"]), None
                )
                if rpm_col is None:
                    return []

                def _find_col_case_insensitive(
                    columns, *, prefers: list[str]
                ) -> str | None:
                    for pref in prefers:
                        pref_l = pref.lower()
                        for c in columns:
                            c_s = str(c)
                            c_l = c_s.lower()
                            if pref_l in c_l:
                                return c_s
                    return None

                hp_col = _find_col_case_insensitive(
                    df.columns,
                    prefers=[
                        "horsepower",
                        "horse power",
                        " hp",
                        "hp ",
                        "power",
                    ],
                )
                tq_col = _find_col_case_insensitive(
                    df.columns,
                    prefers=[
                        "torque",
                        " tq",
                        "tq ",
                    ],
                )
                if hp_col is None or tq_col is None:
                    return []

                work = df[[rpm_col, hp_col, tq_col]].copy()
                work[rpm_col] = pd.to_numeric(work[rpm_col], errors="coerce")
                work[hp_col] = pd.to_numeric(work[hp_col], errors="coerce")
                work[tq_col] = pd.to_numeric(work[tq_col], errors="coerce")
                work = work.dropna(subset=[rpm_col, hp_col, tq_col])
                work = work[(work[rpm_col] > 0) & (work[rpm_col] < 20000)]
                if work.empty:
                    return []

                rpm_bin_size = 100.0
                work["_rpm_bin"] = (work[rpm_col] / rpm_bin_size).round() * rpm_bin_size
                grouped = (
                    work.groupby("_rpm_bin", as_index=False)
                    .agg({hp_col: "max", tq_col: "max"})
                    .sort_values("_rpm_bin")
                )

                curve: list[dict[str, float]] = []
                for _, row in grouped.iterrows():
                    rpm = float(row["_rpm_bin"])
                    curve.append(
                        {
                            "rpm": float(int(round(rpm))),
                            "hp": round(float(row[hp_col]), 2),
                            "tq": round(float(row[tq_col]), 2),
                        }
                    )
                return curve
            except Exception:
                return []

        summary: dict = {
            "run_id": session.id,
            "status": session.status,
            "created_at": session.created_at,
            "timestamp": session.created_at,
            "data_source": (
                session.data_source.value
                if isinstance(session.data_source, DataSource)
                else session.data_source
            ),
            "log_file": session.log_file,
            "tune_file": session.tune_file,
            "errors": session.errors,
        }

        # Peak performance
        if session.peak_hp > 0 or session.peak_tq > 0:
            summary["peak_performance"] = {
                "peak_hp": round(session.peak_hp, 1),
                "peak_hp_rpm": round(session.peak_hp_rpm, 0),
                "peak_tq": round(session.peak_tq, 1),
                "peak_tq_rpm": round(session.peak_tq_rpm, 0),
            }

        if session.pv_log:
            summary["log_signals"] = len(session.pv_log.signals)
            summary["log_rows"] = len(session.pv_log.data)

        if session.dynoai_data is not None:
            summary["total_samples"] = len(session.dynoai_data)

        if session.afr_analysis:
            afr = session.afr_analysis
            # Determine overall status
            if afr.zones_lean > afr.zones_rich:
                overall_status = "LEAN"
            elif afr.zones_rich > afr.zones_lean:
                overall_status = "RICH"
            else:
                overall_status = "BALANCED"

            summary["analysis"] = {
                "overall_status": overall_status,
                "mean_ve_delta_pct": round(afr.mean_error_pct, 2),
                "mean_afr_error": round(afr.mean_afr_error, 2),
                "zones_lean": afr.zones_lean,
                "zones_rich": afr.zones_rich,
                "zones_ok": afr.zones_ok,
                "zones_no_data": afr.zones_no_data,
                "max_lean_pct": round(afr.max_lean_pct, 2),
                "max_rich_pct": round(afr.max_rich_pct, 2),
                "lean_cells": afr.zones_lean,
                "rich_cells": afr.zones_rich,
                "ok_cells": afr.zones_ok,
                "no_data_cells": afr.zones_no_data,
            }
            # Add peak performance to analysis for backward compat
            if session.peak_hp > 0:
                summary["analysis"]["peak_hp"] = round(session.peak_hp, 1)
                summary["analysis"]["peak_hp_rpm"] = round(session.peak_hp_rpm, 0)
            if session.peak_tq > 0:
                summary["analysis"]["peak_tq"] = round(session.peak_tq, 1)
                summary["analysis"]["peak_tq_rpm"] = round(session.peak_tq_rpm, 0)

        # Power curve for UI overlay charts (optional)
        if session.dynoai_data is not None:
            curve = _build_power_curve_from_df(session.dynoai_data)
            if curve:
                if "analysis" not in summary or not isinstance(
                    summary.get("analysis"), dict
                ):
                    summary["analysis"] = {}
                summary["analysis"]["power_curve"] = curve

        if session.ve_corrections:
            corr = session.ve_corrections
            summary["grid"] = {
                "rpm_bins": corr.rpm_axis,
                "map_bins": corr.map_axis,
                "ve_correction": corr.correction_table.tolist(),
            }
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

        if session.output_dir:
            summary["output_dir"] = session.output_dir

        return summary


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AFRAnalysisResult",
    "AutoTuneSession",
    "AutoTuneWorkflow",
    "DataSource",
    "VECorrectionResult",
]
