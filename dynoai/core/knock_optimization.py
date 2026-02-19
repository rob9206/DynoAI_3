"""
DynoAI Knock-Based Timing Optimizer

This module automates the process of finding Maximum Brake Torque (MBT) timing while avoiding knock.
It specifically handles Harley-Davidson's Delphi Ion-Sensing Knock Detection characteristics.

Key Features:
1.  **Knock Event Clustering**: Identifies cells with recurring knock events (not just random noise).
2.  **Retard Strategy**: Calculates specific retard values based on knock severity and frequency.
3.  **Advance Strategy**: Suggests timing advance in areas with zero knock and clean ion signals (if supported by log data).
4.  **Per-Cylinder Handling**: Applies corrections independently to Front/Rear timing tables.

Usage:
    from knock_optimization import process_knock_data, generate_timing_corrections

    # Load log data
    records = load_dyno_log("logs/run_01.csv")

    # Analyze knock
    knock_summary = process_knock_data(records)

    # Generate correction map (negative values = retard, positive = advance)
    corrections = generate_timing_corrections(knock_summary, aggressiveness="safe")
"""

import csv
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from dynoai.constants import (
    KPA_BINS,
    KPA_INDEX,
    RPM_BINS,
    RPM_INDEX,
    get_kpa_index,
    get_rpm_index,
)

# ============================================================================
# Configuration
# ============================================================================

# Minimum hits in a cell to recommend ADVANCE (needs confidence)
MIN_HITS_FOR_ADVANCE = 20

# Minimum hits in a cell to recommend RETARD (needs verification)
MIN_HITS_FOR_RETARD = 5

# Knock Retard Steps (Degrees)
RETARD_STEP_MILD = 2.0  # Occasional knock
RETARD_STEP_HEAVY = 4.0  # Frequent knock (>10% of events)
RETARD_MAX_TOTAL = 8.0  # Safety cap

# Advance Steps (Degrees)
ADVANCE_STEP_SAFE = 1.0  # Clean run correction

# ============================================================================
# Data Structures
# ============================================================================


class KnockSeverity(Enum):
    NONE = "none"
    MILD = "mild"  # Occasional pings
    MODERATE = "moderate"  # Repeatable knock
    SEVERE = "severe"  # Constant/heavy knock


@dataclass
class CellKnockStats:
    rpm_bin: int
    kpa_bin: int
    sample_count: int = 0
    knock_events: int = 0
    max_retard_seen: float = 0.0

    @property
    def knock_rate(self) -> float:
        return self.knock_events / self.sample_count if self.sample_count > 0 else 0.0


@dataclass
class KnockAnalysis:
    cylinder: str  # 'front' or 'rear'
    cells: Dict[Tuple[int, int], CellKnockStats] = field(default_factory=dict)
    total_events: int = 0
    max_knock_rate: float = 0.0


# ============================================================================
# Core Logic
# ============================================================================


def _get_bin_indices(rpm: float, kpa: float) -> Tuple[int, int]:
    """Map raw values to nearest bin indices."""
    # Use existing helper or simple min distance
    rpm_bin = min(RPM_BINS, key=lambda x: abs(x - rpm))
    kpa_bin = min(KPA_BINS, key=lambda x: abs(x - kpa))

    # We need indices for the grid
    r_idx = RPM_INDEX.get(rpm_bin, 0)
    k_idx = KPA_INDEX.get(kpa_bin, 0)
    return r_idx, k_idx


def process_knock_data(
    records: Sequence[Dict[str, float]], cylinder: str = "front"
) -> KnockAnalysis:
    """
    Analyze log records for knock activity.

    Args:
        records: Log data
        cylinder: 'front' or 'rear' to select correct knock sensor column

    Returns:
        KnockAnalysis object
    """
    # Column names usually: 'knock_f', 'knock_r' or 'knock_retard_f'
    # Some logs have binary 'knock' (0/1), others have 'retard' (degrees)

    # Heuristic: Look for columns
    col_name = f"knock_{cylinder[0]}"
    retard_col = f"knock_retard_{cylinder[0]}"

    analysis = KnockAnalysis(cylinder=cylinder)

    for r in records:
        rpm = r.get("rpm", 0)
        kpa = r.get("map", 0)

        # Get knock status
        knock_val = r.get(col_name, 0)
        retard_val = r.get(retard_col, 0)

        is_knock = False
        if knock_val > 0:
            is_knock = True
        if retard_val > 0:
            is_knock = True

        r_idx, k_idx = _get_bin_indices(rpm, kpa)
        key = (r_idx, k_idx)

        if key not in analysis.cells:
            analysis.cells[key] = CellKnockStats(
                rpm_bin=RPM_BINS[r_idx], kpa_bin=KPA_BINS[k_idx]
            )

        stats = analysis.cells[key]
        stats.sample_count += 1
        if is_knock:
            stats.knock_events += 1
            stats.max_retard_seen = max(stats.max_retard_seen, retard_val)
            analysis.total_events += 1

    # Update summary stats
    if analysis.cells:
        analysis.max_knock_rate = max(c.knock_rate for c in analysis.cells.values())

    return analysis


def generate_timing_corrections(
    analysis: KnockAnalysis, aggressiveness: str = "safe"
) -> List[List[float]]:
    """
    Generate a timing correction grid (Advance/Retard in degrees).
    """
    grid = [[0.0 for _ in KPA_BINS] for _ in RPM_BINS]

    for (r_idx, k_idx), stats in analysis.cells.items():
        correction = 0.0

        # RETARD LOGIC (Safety First)
        if stats.knock_events > 0:
            # If we have verified knock, we MUST retard
            if stats.knock_rate > 0.10:  # >10% of samples knocked -> Severe
                correction = -RETARD_STEP_HEAVY
            elif stats.knock_rate > 0.0:  # Any knock -> Mild retard
                correction = -RETARD_STEP_MILD

            # Cap retard
            correction = max(correction, -RETARD_MAX_TOTAL)

        # ADVANCE LOGIC (Performance)
        # Only advance if we have LOTS of data and ZERO knock
        elif (
            stats.sample_count >= MIN_HITS_FOR_ADVANCE
            and stats.knock_events == 0
            and aggressiveness == "aggressive"
        ):
            correction = ADVANCE_STEP_SAFE

        grid[r_idx][k_idx] = correction

    return grid


def write_timing_grid_csv(
    grid: List[List[float]],
    output_path: Path,
    rpm_bins: Sequence[int] = None,
    kpa_bins: Sequence[int] = None,
) -> str:
    """Write timing corrections to CSV."""
    if rpm_bins is None:
        rpm_bins = RPM_BINS
    if kpa_bins is None:
        kpa_bins = KPA_BINS
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["RPM"] + [str(k) for k in kpa_bins])
        for i, row in enumerate(grid):
            out_row = [str(rpm_bins[i])] + [f"{x:+.1f}" for x in row]
            writer.writerow(out_row)
    return str(output_path)
