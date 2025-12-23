"""
DynoAI Per-Cylinder Auto-Balancing - Automatic AFR equalization for V-twin engines.

This module detects AFR imbalances between front and rear cylinders and generates
VE correction factors to equalize them, addressing the 0.5-1.0 AFR point variation
common in V-twins due to heat soak, airflow differences, and firing order effects.

The algorithm:
1. Analyzes front vs rear AFR data from dyno logs
2. Identifies zones with significant cylinder-to-cylinder variation
3. Calculates smart correction factors to equalize AFR
4. Generates separate VE correction overlays for each cylinder
5. Applies safety limits to prevent overcorrection

Usage:
    from dynoai.core.cylinder_balancing import process_cylinder_balancing

    result = process_cylinder_balancing(
        records=log_data,
        output_dir="./output",
        target_mode="equalize",  # or "match_front", "match_rear"
        max_correction_pct=3.0
    )
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from dynoai.constants import KPA_BINS, KPA_INDEX, RPM_BINS, RPM_INDEX
from dynoai.core.io_contracts import sanitize_csv_cell
from dynoai.core.ve_math import (
    MathVersion,
    calculate_ve_correction,
    correction_to_percentage,
)

logger = logging.getLogger(__name__)

# Default math version for VE calculations
DEFAULT_MATH_VERSION = MathVersion.V2_0_0

# ============================================================================
# Configuration Constants
# ============================================================================


class BalanceMode(Enum):
    """Cylinder balancing strategy modes."""

    EQUALIZE = "equalize"  # Balance both cylinders toward average AFR
    MATCH_FRONT = "match_front"  # Adjust rear to match front AFR
    MATCH_REAR = "match_rear"  # Adjust front to match rear AFR


# Default configuration
DEFAULT_MAX_CORRECTION_PCT = 3.0  # Maximum VE adjustment per iteration
DEFAULT_MIN_SAMPLES_PER_CELL = 3  # Minimum data points to trust a cell
DEFAULT_AFR_THRESHOLD = 0.5  # Minimum AFR difference to correct (0.5 points)
DEFAULT_TARGET_AFR_TOLERANCE = 0.2  # Target AFR tolerance for "balanced"

# Safety limits
MAX_ABSOLUTE_CORRECTION = 5.0  # Never adjust VE by more than 5% in one go
MIN_AFR_FOR_ANALYSIS = 10.0  # Ignore obviously bad AFR readings
MAX_AFR_FOR_ANALYSIS = 18.0  # Ignore obviously bad AFR readings

# ============================================================================
# Data Models
# ============================================================================


@dataclass
class CylinderData:
    """AFR data for a single cylinder across the RPM/KPA grid."""

    afr_grid: List[List[float]] = field(default_factory=list)  # Average AFR per cell
    sample_counts: List[List[int]] = field(default_factory=list)  # Number of samples
    afr_cmd_grid: List[List[float]] = field(default_factory=list)  # Commanded AFR


@dataclass
class ImbalanceCell:
    """Represents a single cell with cylinder imbalance."""

    rpm_idx: int
    kpa_idx: int
    rpm: int
    kpa: int
    front_afr: float
    rear_afr: float
    delta: float  # Positive = rear running richer than front
    front_samples: int
    rear_samples: int

    def severity(self) -> str:
        """Classify imbalance severity."""
        abs_delta = abs(self.delta)
        if abs_delta >= 1.0:
            return "high"
        elif abs_delta >= 0.7:
            return "medium"
        else:
            return "low"


@dataclass
class BalanceAnalysis:
    """Complete analysis of cylinder-to-cylinder imbalance."""

    imbalanced_cells: List[ImbalanceCell] = field(default_factory=list)
    front_data: CylinderData = field(default_factory=CylinderData)
    rear_data: CylinderData = field(default_factory=CylinderData)
    max_delta: float = 0.0
    avg_delta: float = 0.0
    cells_analyzed: int = 0
    cells_imbalanced: int = 0

    def summary(self) -> Dict[str, Any]:
        """Generate summary statistics."""
        high_severity = sum(
            1 for cell in self.imbalanced_cells if cell.severity() == "high"
        )
        medium_severity = sum(
            1 for cell in self.imbalanced_cells if cell.severity() == "medium"
        )
        low_severity = sum(
            1 for cell in self.imbalanced_cells if cell.severity() == "low"
        )

        return {
            "cells_analyzed": self.cells_analyzed,
            "cells_imbalanced": self.cells_imbalanced,
            "imbalance_percentage": (
                round(100 * self.cells_imbalanced / self.cells_analyzed, 1)
                if self.cells_analyzed > 0
                else 0
            ),
            "max_afr_delta": round(self.max_delta, 2),
            "avg_afr_delta": round(self.avg_delta, 2),
            "severity_breakdown": {
                "high": high_severity,
                "medium": medium_severity,
                "low": low_severity,
            },
        }


# ============================================================================
# Core Analysis Functions
# ============================================================================


def aggregate_cylinder_afr(
    records: Sequence[Dict[str, Optional[float]]],
    afr_col: str,
    afr_cmd_col: str = "afr_cmd_f",
    min_samples: int = DEFAULT_MIN_SAMPLES_PER_CELL,
) -> CylinderData:
    """
    Aggregate AFR data for a single cylinder into RPM/KPA grid.

    Args:
        records: Log records with rpm, kpa, and AFR data
        afr_col: Column name for measured AFR (e.g., 'afr_meas_f' or 'afr_meas_r')
        afr_cmd_col: Column name for commanded AFR
        min_samples: Minimum samples required per cell

    Returns:
        CylinderData with aggregated AFR grids
    """
    # Initialize grids
    afr_sums = [[0.0 for _ in KPA_BINS] for _ in RPM_BINS]
    afr_cmd_sums = [[0.0 for _ in KPA_BINS] for _ in RPM_BINS]
    counts = [[0 for _ in KPA_BINS] for _ in RPM_BINS]

    # Aggregate data
    for rec in records:
        rpm = rec.get("rpm")
        kpa = rec.get("kpa")
        afr_meas = rec.get(afr_col)
        afr_cmd = rec.get(afr_cmd_col)

        if rpm is None or kpa is None or afr_meas is None:
            continue

        # Filter out bad AFR readings
        if afr_meas < MIN_AFR_FOR_ANALYSIS or afr_meas > MAX_AFR_FOR_ANALYSIS:
            continue

        # Find nearest bin
        rpm_bin = min(RPM_BINS, key=lambda x: abs(x - rpm))
        kpa_bin = min(KPA_BINS, key=lambda x: abs(x - kpa))

        rpm_idx = RPM_INDEX[rpm_bin]
        kpa_idx = KPA_INDEX[kpa_bin]

        afr_sums[rpm_idx][kpa_idx] += afr_meas
        if afr_cmd is not None:
            afr_cmd_sums[rpm_idx][kpa_idx] += afr_cmd
        counts[rpm_idx][kpa_idx] += 1

    # Calculate averages
    afr_grid = []
    afr_cmd_grid = []

    for r_idx in range(len(RPM_BINS)):
        afr_row = []
        afr_cmd_row = []
        for k_idx in range(len(KPA_BINS)):
            count = counts[r_idx][k_idx]
            if count >= min_samples:
                afr_row.append(afr_sums[r_idx][k_idx] / count)
                afr_cmd_row.append(
                    afr_cmd_sums[r_idx][k_idx] / count
                    if afr_cmd_sums[r_idx][k_idx] > 0
                    else 0.0
                )
            else:
                afr_row.append(0.0)  # Insufficient data
                afr_cmd_row.append(0.0)
        afr_grid.append(afr_row)
        afr_cmd_grid.append(afr_cmd_row)

    return CylinderData(
        afr_grid=afr_grid, sample_counts=counts, afr_cmd_grid=afr_cmd_grid
    )


def analyze_imbalance(
    front_data: CylinderData,
    rear_data: CylinderData,
    afr_threshold: float = DEFAULT_AFR_THRESHOLD,
) -> BalanceAnalysis:
    """
    Analyze cylinder-to-cylinder AFR imbalance.

    Args:
        front_data: Front cylinder AFR data
        rear_data: Rear cylinder AFR data
        afr_threshold: Minimum AFR delta to flag as imbalanced

    Returns:
        BalanceAnalysis with detected imbalances
    """
    imbalanced_cells = []
    total_delta = 0.0
    max_delta = 0.0
    cells_analyzed = 0

    for r_idx in range(len(RPM_BINS)):
        for k_idx in range(len(KPA_BINS)):
            front_afr = front_data.afr_grid[r_idx][k_idx]
            rear_afr = rear_data.afr_grid[r_idx][k_idx]
            front_count = front_data.sample_counts[r_idx][k_idx]
            rear_count = rear_data.sample_counts[r_idx][k_idx]

            # Skip cells with insufficient data
            if front_afr == 0.0 or rear_afr == 0.0:
                continue

            cells_analyzed += 1
            delta = rear_afr - front_afr
            abs_delta = abs(delta)

            total_delta += abs_delta
            if abs_delta > max_delta:
                max_delta = abs_delta

            # Flag if imbalance exceeds threshold
            if abs_delta >= afr_threshold:
                imbalanced_cells.append(
                    ImbalanceCell(
                        rpm_idx=r_idx,
                        kpa_idx=k_idx,
                        rpm=RPM_BINS[r_idx],
                        kpa=KPA_BINS[k_idx],
                        front_afr=front_afr,
                        rear_afr=rear_afr,
                        delta=delta,
                        front_samples=front_count,
                        rear_samples=rear_count,
                    )
                )

    return BalanceAnalysis(
        imbalanced_cells=imbalanced_cells,
        front_data=front_data,
        rear_data=rear_data,
        max_delta=max_delta,
        avg_delta=total_delta / cells_analyzed if cells_analyzed > 0 else 0.0,
        cells_analyzed=cells_analyzed,
        cells_imbalanced=len(imbalanced_cells),
    )


# ============================================================================
# Correction Calculation
# ============================================================================


def calculate_correction_factors(
    analysis: BalanceAnalysis,
    mode: BalanceMode = BalanceMode.EQUALIZE,
    max_correction_pct: float = DEFAULT_MAX_CORRECTION_PCT,
    math_version: MathVersion = DEFAULT_MATH_VERSION,
) -> Tuple[List[List[float]], List[List[float]]]:
    """
    Calculate VE correction factors to balance cylinders.

    Strategy:
    - AFR is inversely proportional to VE (more VE = richer = lower AFR)
    - To raise AFR (make leaner): reduce VE
    - To lower AFR (make richer): increase VE

    Math Versions:
        v1.0.0: Linear 7% per AFR point (legacy)
        v2.0.0: Ratio model AFR_measured/AFR_target (default, physically accurate)

    Args:
        analysis: Imbalance analysis results
        mode: Balancing strategy
        max_correction_pct: Maximum VE adjustment per cell
        math_version: VE calculation math version (default: V2_0_0)

    Returns:
        Tuple of (front_factors, rear_factors) as 2D grids
        Values are percentage adjustments (0.03 = +3%, -0.02 = -2%)
    """
    # Initialize factor grids (0 = no change)
    front_factors = [[0.0 for _ in KPA_BINS] for _ in RPM_BINS]
    rear_factors = [[0.0 for _ in KPA_BINS] for _ in RPM_BINS]

    for cell in analysis.imbalanced_cells:
        r_idx = cell.rpm_idx
        k_idx = cell.kpa_idx

        # Get commanded AFR for this cell (use front as reference)
        afr_target = analysis.front_data.afr_cmd_grid[r_idx][k_idx]
        if afr_target == 0.0:
            afr_target = 14.0  # Fallback to stoichiometric for gasoline

        if mode == BalanceMode.EQUALIZE:
            # Balance both toward the average
            avg_afr = (cell.front_afr + cell.rear_afr) / 2.0
            front_correction = _calculate_ve_correction_decimal(
                cell.front_afr, avg_afr, math_version
            )
            rear_correction = _calculate_ve_correction_decimal(
                cell.rear_afr, avg_afr, math_version
            )

        elif mode == BalanceMode.MATCH_FRONT:
            # Adjust rear to match front
            front_correction = 0.0
            rear_correction = _calculate_ve_correction_decimal(
                cell.rear_afr, cell.front_afr, math_version
            )

        elif mode == BalanceMode.MATCH_REAR:
            # Adjust front to match rear
            front_correction = _calculate_ve_correction_decimal(
                cell.front_afr, cell.rear_afr, math_version
            )
            rear_correction = 0.0

        # Apply safety clamping
        front_factors[r_idx][k_idx] = _clamp_correction(
            front_correction, max_correction_pct
        )
        rear_factors[r_idx][k_idx] = _clamp_correction(
            rear_correction, max_correction_pct
        )

    return front_factors, rear_factors


def _calculate_ve_correction_decimal(
    afr_measured: float,
    afr_target: float,
    math_version: MathVersion = DEFAULT_MATH_VERSION,
) -> float:
    """
    Calculate VE correction as a decimal percentage.

    Uses the versioned VE math module for calculation.

    Math Versions:
        v1.0.0: Linear 7% per AFR point (legacy approximation)
        v2.0.0: Ratio model AFR_measured/AFR_target (physically accurate)

    Args:
        afr_measured: Measured AFR from wideband sensor
        afr_target: Target AFR to achieve
        math_version: VE calculation version (default: V2_0_0)

    Returns:
        VE correction as decimal (0.07 = +7%, -0.07 = -7%)

    Example:
        >>> _calculate_ve_correction_decimal(14.0, 13.0, MathVersion.V2_0_0)
        0.0769...  # ~7.7% more fuel needed (lean condition)
    """
    try:
        # Get multiplier from ve_math module (e.g., 1.077 for +7.7%)
        multiplier = calculate_ve_correction(
            afr_measured, afr_target, version=math_version, clamp=False
        )
        # Convert to decimal percentage (1.077 -> 0.077)
        return multiplier - 1.0
    except Exception as e:
        logger.warning(
            "VE calculation failed for AFR %.2f/%.2f: %s, using 0.0",
            afr_measured,
            afr_target,
            e,
        )
        return 0.0


# Legacy function name for backwards compatibility
def _afr_error_to_ve_correction(afr_error: float) -> float:
    """
    DEPRECATED: Use _calculate_ve_correction_decimal() instead.

    Convert AFR error to VE correction using v1.0.0 linear model.

    This function is kept for backwards compatibility but uses the
    legacy v1.0.0 formula (7% per AFR point).

    Args:
        afr_error: Measured AFR - Target AFR (positive = lean)

    Returns:
        VE correction as decimal (0.07 = +7%)
    """
    # Legacy formula: error * 0.07
    return afr_error * 0.07


def _clamp_correction(correction: float, max_pct: float) -> float:
    """Clamp correction to safety limits."""
    # First clamp to max_correction_pct
    clamped = max(-max_pct / 100.0, min(max_pct / 100.0, correction))

    # Then clamp to absolute maximum
    clamped = max(
        -MAX_ABSOLUTE_CORRECTION / 100.0, min(MAX_ABSOLUTE_CORRECTION / 100.0, clamped)
    )

    return clamped


# ============================================================================
# Output Generation
# ============================================================================


def write_correction_csv(
    factors: List[List[float]], output_path: Path, value_fmt: str = "{:.4f}"
) -> None:
    """
    Write VE correction factors to CSV file.

    Format matches standard VE table format with RPM rows and KPA columns.
    Values are written as percentage factors (1.03 = 3% increase, 0.97 = 3% decrease).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header row: RPM, followed by KPA bins
        writer.writerow(["RPM"] + [sanitize_csv_cell(k) for k in KPA_BINS])

        # Data rows
        for ri, rpm in enumerate(RPM_BINS):
            row = [sanitize_csv_cell(rpm)]
            for ci in range(len(KPA_BINS)):
                factor_pct = factors[ri][ci]
                # Convert percentage to multiplier (0.03 → 1.03, -0.02 → 0.98)
                multiplier = 1.0 + factor_pct
                formatted_value = value_fmt.format(multiplier)
                row.append(sanitize_csv_cell(formatted_value))
            writer.writerow(row)

    logger.info(f"Wrote correction factors to {output_path}")


def generate_balance_report(
    analysis: BalanceAnalysis,
    front_factors: List[List[float]],
    rear_factors: List[List[float]],
    mode: BalanceMode,
    input_file: str = "",
) -> Dict[str, Any]:
    """Generate comprehensive balance analysis report."""

    # Calculate correction statistics
    front_corrections_applied = sum(
        1 for row in front_factors for val in row if val != 0.0
    )
    rear_corrections_applied = sum(
        1 for row in rear_factors for val in row if val != 0.0
    )

    max_front_correction = max(abs(val) for row in front_factors for val in row)
    max_rear_correction = max(abs(val) for row in rear_factors for val in row)

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_file": input_file,
        "balance_mode": mode.value,
        "analysis": analysis.summary(),
        "corrections": {
            "front_cells_corrected": front_corrections_applied,
            "rear_cells_corrected": rear_corrections_applied,
            "max_front_correction_pct": round(max_front_correction * 100, 2),
            "max_rear_correction_pct": round(max_rear_correction * 100, 2),
        },
        "imbalanced_zones": [
            {
                "rpm": cell.rpm,
                "kpa": cell.kpa,
                "front_afr": round(cell.front_afr, 2),
                "rear_afr": round(cell.rear_afr, 2),
                "delta": round(cell.delta, 2),
                "severity": cell.severity(),
            }
            for cell in analysis.imbalanced_cells[:20]  # Top 20 worst cells
        ],
    }

    return report


# ============================================================================
# High-Level Integration Function
# ============================================================================


def process_cylinder_balancing(
    records: Sequence[Dict[str, Optional[float]]],
    output_dir: str | Path,
    mode: str = "equalize",
    max_correction_pct: float = DEFAULT_MAX_CORRECTION_PCT,
    afr_threshold: float = DEFAULT_AFR_THRESHOLD,
    min_samples: int = DEFAULT_MIN_SAMPLES_PER_CELL,
    input_file: str = "",
) -> Dict[str, Any]:
    """
    Complete cylinder balancing processing pipeline.

    Args:
        records: Raw log records with AFR data for both cylinders
        output_dir: Directory for output files
        mode: Balance mode ('equalize', 'match_front', 'match_rear')
        max_correction_pct: Maximum VE correction percentage
        afr_threshold: Minimum AFR delta to trigger correction
        min_samples: Minimum samples per cell for analysis
        input_file: Name of input file for report

    Returns:
        Dict with processing results and output file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        f"Running cylinder balancing (mode={mode}, max_correction={max_correction_pct}%)"
    )

    # Parse mode
    try:
        balance_mode = BalanceMode(mode.lower())
    except ValueError:
        logger.warning(f"Unknown balance mode '{mode}', using 'equalize'")
        balance_mode = BalanceMode.EQUALIZE

    # Step 1: Aggregate AFR data for each cylinder
    logger.info("Aggregating front cylinder AFR data...")
    front_data = aggregate_cylinder_afr(records, "afr_meas_f", "afr_cmd_f", min_samples)

    logger.info("Aggregating rear cylinder AFR data...")
    rear_data = aggregate_cylinder_afr(records, "afr_meas_r", "afr_cmd_r", min_samples)

    # Step 2: Analyze imbalance
    logger.info("Analyzing cylinder-to-cylinder imbalance...")
    analysis = analyze_imbalance(front_data, rear_data, afr_threshold)

    logger.info(
        f"Found {analysis.cells_imbalanced} imbalanced cells (max delta: {analysis.max_delta:.2f} AFR)"
    )

    # Step 3: Calculate correction factors
    logger.info("Calculating correction factors...")
    front_factors, rear_factors = calculate_correction_factors(
        analysis, balance_mode, max_correction_pct
    )

    # Step 4: Write output files
    front_csv = output_dir / "Front_Balance_Factor.csv"
    rear_csv = output_dir / "Rear_Balance_Factor.csv"
    report_json = output_dir / "Cylinder_Balance_Report.json"

    write_correction_csv(front_factors, front_csv)
    write_correction_csv(rear_factors, rear_csv)

    report = generate_balance_report(
        analysis, front_factors, rear_factors, balance_mode, input_file
    )

    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Cylinder balancing complete. Files written to {output_dir}")

    return {
        "cells_analyzed": analysis.cells_analyzed,
        "cells_imbalanced": analysis.cells_imbalanced,
        "max_afr_delta": analysis.max_delta,
        "avg_afr_delta": analysis.avg_delta,
        "mode_used": balance_mode.value,
        "front_corrections_applied": sum(
            1 for row in front_factors for val in row if val != 0.0
        ),
        "rear_corrections_applied": sum(
            1 for row in rear_factors for val in row if val != 0.0
        ),
        "output_files": {
            "front_factors": str(front_csv),
            "rear_factors": str(rear_csv),
            "report": str(report_json),
        },
    }
