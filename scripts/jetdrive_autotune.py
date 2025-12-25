#!/usr/bin/env python3
# pyright: reportGeneralTypeIssues=false
# pyright: reportMissingTypeStubs=false
"""
DynoAI JetDrive Auto-Tune Pipeline

Complete automation from dyno capture to tuning corrections:
1. Capture/simulate JetDrive data
2. Analyze AFR by 2D RPM × MAP grid
3. Calculate VE corrections using DynoAI math
4. Generate paste-ready tables
5. Export to Power Vision PVV XML format

Usage:
    # With simulated data:
    python scripts/jetdrive_autotune.py --simulate --run-id my_test_run

    # With real JetDrive (when dyno connected):
    python scripts/jetdrive_autotune.py --provider "Power Core" --run-id my_run

    # Analyze existing CSV:
    python scripts/jetdrive_autotune.py --csv path/to/run.csv --run-id my_run
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

# Import DynoAI VE math module for versioned calculations
from dynoai.core.ve_math import (
    MathVersion,
    calculate_ve_correction,
    correction_to_percentage,
)
from dynoai.core.io_contracts import safe_path

# =============================================================================
# Standard DynoAI Grid Configuration (matches dynoai/constants.py)
# =============================================================================

# Standard RPM bins (11 bins: 1500-6500 by 500)
RPM_BINS: list[int] = [1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]

# Standard MAP/kPa bins (5 bins: 35-95)
KPA_BINS: list[int] = [35, 50, 65, 80, 95]


def sanitize_run_id(run_id: str) -> str:
    """
    Sanitize run_id to prevent path traversal attacks.
    Only allow alphanumeric, underscore, and hyphen characters.
    """
    if not run_id:
        raise ValueError("run_id cannot be empty")
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", run_id)
    sanitized = sanitized.lstrip(".-")
    if not sanitized:
        raise ValueError("Invalid run_id after sanitization")
    return sanitized


@dataclass
class TuneConfig:
    """Tuning parameters configuration."""

    # Standard AFR targets by load (MAP)
    # Higher MAP = more load = richer mixture needed
    afr_target_by_load: dict[str, float] = field(
        default_factory=lambda: {
            "Vacuum": 14.7,  # Light load / cruise (35-50 kPa)
            "Part": 13.5,  # Part throttle (50-65 kPa)
            "Mid": 13.0,  # Mid load (65-80 kPa)
            "WOT": 12.5,  # Wide open throttle (80-95 kPa)
        }
    )

    # Correction limits
    max_ve_correction_pct: float = 10.0  # Max ±10% VE change
    min_hits_per_cell: int = 3  # Minimum samples to trust cell

    # VE correction factor (7% per AFR point - DynoAI v1.0.0 standard)
    # DEPRECATED: Use math_version instead. Kept for backwards compatibility.
    ve_per_afr_point: float = 7.0

    # Math version for VE calculations
    # V1_0_0: Linear 7% per AFR point (legacy)
    # V2_0_0: Ratio model AFR_measured/AFR_target (default, physically accurate)
    math_version: MathVersion = MathVersion.V2_0_0

    # RPM bins for grid
    rpm_bins: list[int] = field(default_factory=lambda: RPM_BINS.copy())

    # MAP bins for grid
    map_bins: list[int] = field(default_factory=lambda: KPA_BINS.copy())


# =============================================================================
# JetDrive Simulation (for testing without hardware)
# =============================================================================


def generate_simulated_dyno_run(duration_s: float = 10.0) -> pd.DataFrame:
    """Generate realistic simulated dyno run data with MAP variation."""
    rows = []
    ts = 0
    step_ms = 100

    # Phase 1: Idle warmup (2 seconds) - low MAP
    for _ in range(20):
        rpm = 1000 + random.uniform(-50, 50)
        map_kpa = 35 + random.uniform(-3, 3)  # Vacuum at idle
        torque = 15 + random.uniform(-2, 2)
        hp = (torque * rpm) / 5252
        afr = 14.7 + random.uniform(-0.3, 0.3)
        rows.append(
            {
                "timestamp_ms": ts,
                "RPM": rpm,
                "MAP_kPa": map_kpa,
                "Torque": torque,
                "Horsepower": hp,
                "AFR": afr,
            }
        )
        ts += step_ms

    # Phase 2: Part throttle cruise (sweep RPM at part load)
    for rpm in range(1500, 4000, 250):
        map_kpa = 50 + random.uniform(-5, 5)  # Part throttle
        torque = 60 + (rpm - 1500) * 0.02 + random.uniform(-5, 5)
        hp = (torque * rpm) / 5252
        afr = 14.0 + random.uniform(-0.4, 0.4)  # Slightly off target
        rows.append(
            {
                "timestamp_ms": ts,
                "RPM": float(rpm),
                "MAP_kPa": map_kpa,
                "Torque": torque,
                "Horsepower": hp,
                "AFR": afr,
            }
        )
        ts += step_ms

    # Phase 3: Mid-load sweep
    for rpm in range(2500, 5000, 250):
        map_kpa = 65 + random.uniform(-5, 5)  # Mid load
        torque = 90 + (rpm - 2500) * 0.03 + random.uniform(-5, 5)
        hp = (torque * rpm) / 5252
        afr = 13.2 + random.uniform(-0.3, 0.3)  # Rich by ~0.3
        rows.append(
            {
                "timestamp_ms": ts,
                "RPM": float(rpm),
                "MAP_kPa": map_kpa,
                "Torque": torque,
                "Horsepower": hp,
                "AFR": afr,
            }
        )
        ts += step_ms

    # Phase 4: High load sweep
    for rpm in range(3000, 5500, 250):
        map_kpa = 80 + random.uniform(-5, 5)  # High load
        torque = 120 + (rpm - 3000) * 0.02 + random.uniform(-5, 5)
        hp = (torque * rpm) / 5252
        afr = 12.8 + random.uniform(-0.3, 0.3)  # Slightly rich
        rows.append(
            {
                "timestamp_ms": ts,
                "RPM": float(rpm),
                "MAP_kPa": map_kpa,
                "Torque": torque,
                "Horsepower": hp,
                "AFR": afr,
            }
        )
        ts += step_ms

    # Phase 5: WOT pull (full power)
    for rpm in range(3500, 6500, 100):
        map_kpa = 95 + random.uniform(-3, 3)  # WOT
        base_torque = 145 - abs(rpm - 4800) * 0.015
        torque = base_torque + random.uniform(-3, 3)
        hp = (torque * rpm) / 5252
        afr = 12.5 + random.uniform(-0.25, 0.25)  # On target
        rows.append(
            {
                "timestamp_ms": ts,
                "RPM": float(rpm),
                "MAP_kPa": map_kpa,
                "Torque": torque,
                "Horsepower": hp,
                "AFR": afr,
            }
        )
        ts += step_ms

    # Phase 6: Decel (coast down)
    for rpm in [5500, 4500, 3500, 2500, 1500, 1200, 1100, 1000, 950]:
        map_kpa = 30 + random.uniform(-3, 3)  # Deep vacuum on decel
        torque = 10 + random.uniform(-3, 3)
        hp = (torque * rpm) / 5252
        afr = 14.5 + random.uniform(-0.3, 0.3)
        rows.append(
            {
                "timestamp_ms": ts,
                "RPM": float(rpm),
                "MAP_kPa": map_kpa,
                "Torque": torque,
                "Horsepower": hp,
                "AFR": afr,
            }
        )
        ts += step_ms

    return pd.DataFrame(rows)


# =============================================================================
# Analysis Engine (2D RPM × MAP Grid)
# =============================================================================


@dataclass
class CellAnalysis:
    """Analysis results for a single RPM × MAP cell."""

    rpm_bin: int
    map_bin: int
    sample_count: int
    mean_afr: float
    target_afr: float
    afr_error: float  # AFR points difference
    ve_delta_pct: float  # VE correction percentage
    status: str  # "LEAN", "RICH", "OK", "NO_DATA"


@dataclass
class GridAnalysis:
    """2D grid analysis results."""

    # Grid dimensions
    rpm_bins: list[int]
    map_bins: list[int]

    # 2D matrices [rpm_idx][map_idx]
    hit_count: np.ndarray  # Sample count per cell
    mean_afr: np.ndarray  # Mean AFR per cell
    target_afr: np.ndarray  # Target AFR per cell
    afr_error: np.ndarray  # AFR error (meas - target)
    ve_correction: np.ndarray  # VE multiplier (1.0 = no change)

    # Cell-by-cell analysis
    cells: list[CellAnalysis]


@dataclass
class AnalysisResult:
    """Complete analysis results."""

    run_id: str
    timestamp: str
    source_file: str
    total_samples: int
    duration_ms: int

    # Peak values
    peak_hp: float
    peak_hp_rpm: float
    peak_tq: float
    peak_tq_rpm: float

    # 2D Grid analysis
    grid: GridAnalysis

    # Overall assessment
    overall_status: str
    lean_cells: int
    rich_cells: int
    ok_cells: int
    no_data_cells: int


def _build_power_curve(
    df: Any,
    rpm_col: str = "RPM",
    hp_col: str = "Horsepower",
    tq_col: str = "Torque",
    rpm_bin_size: int = 100,
) -> list[dict[str, float]]:
    """
    Build a compact power curve for UI overlay charts.

    We bin by RPM (default: 100 RPM) and take max HP/TQ in each bin.
    This keeps payload small and avoids over-plotting noisy raw samples.
    """
    try:
        if df is None or df.empty:
            return []
        if (
            rpm_col not in df.columns
            or hp_col not in df.columns
            or tq_col not in df.columns
        ):
            return []

        work = df[[rpm_col, hp_col, tq_col]].copy()
        work[rpm_col] = pd.to_numeric(work[rpm_col], errors="coerce")
        work[hp_col] = pd.to_numeric(work[hp_col], errors="coerce")
        work[tq_col] = pd.to_numeric(work[tq_col], errors="coerce")
        work = work.dropna(subset=[rpm_col, hp_col, tq_col])
        work = work[(work[rpm_col] > 0) & (work[rpm_col] < 20000)]

        if work.empty:
            return []

        # Round to nearest RPM bin
        work["_rpm_bin"] = (work[rpm_col] / float(rpm_bin_size)).round() * rpm_bin_size

        grouped = (
            work.groupby("_rpm_bin", as_index=False)
            .agg({hp_col: "max", tq_col: "max"})
            .sort_values(by="_rpm_bin")
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
        # Non-fatal: charting is optional
        return []


def nearest_bin(val: float, bins: list[int]) -> int:
    """Find nearest bin value."""
    return min(bins, key=lambda b: abs(b - val))


# Default AFR targets by MAP (kPa) - matches autotune_workflow.py
DEFAULT_AFR_TARGETS: dict[int, float] = {
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


def get_target_afr_for_map(
    map_kpa: float, afr_targets: dict[int, float] | None = None
) -> float:
    """Get target AFR based on MAP (load).

    Args:
        map_kpa: Manifold absolute pressure in kPa
        afr_targets: Optional dict mapping MAP values to target AFR.
                     If None, uses DEFAULT_AFR_TARGETS.

    Returns:
        Target AFR for the given MAP value (uses nearest bin)
    """
    targets = afr_targets or DEFAULT_AFR_TARGETS
    map_keys = sorted(targets.keys())

    if not map_keys:
        return 14.0  # Fallback

    # Find nearest MAP bin
    closest = min(map_keys, key=lambda k: abs(k - map_kpa))
    return targets[closest]


def analyze_dyno_data(
    df: Any,
    config: TuneConfig | None = None,
    afr_targets: dict[int, float] | None = None,
) -> AnalysisResult:
    """Run full 2D grid analysis on dyno data.

    Args:
        df: DataFrame with RPM, AFR, MAP_kPa columns
        config: Tuning configuration (optional)
        afr_targets: Custom AFR targets by MAP kPa (optional).
                     Keys are MAP values (int), values are target AFR.
                     Example: {20: 14.7, 30: 14.7, 100: 12.2}
    """
    config = config or TuneConfig()

    rpm_bins = config.rpm_bins
    map_bins = config.map_bins
    n_rpm = len(rpm_bins)
    n_map = len(map_bins)

    # Initialize 2D matrices
    hit_count = np.zeros((n_rpm, n_map), dtype=int)
    afr_sum = np.zeros((n_rpm, n_map))
    target_afr = np.zeros((n_rpm, n_map))

    # Set target AFR for each cell based on MAP (using custom targets if provided)
    for j, map_val in enumerate(map_bins):
        target = get_target_afr_for_map(map_val, afr_targets)
        for i in range(n_rpm):
            target_afr[i, j] = target

    # Check if MAP data exists
    has_map = "MAP_kPa" in df.columns and not df["MAP_kPa"].isna().all()

    # Bin each sample into the grid
    for _, row in df.iterrows():
        rpm = row["RPM"]
        afr = row["AFR"]

        if pd.isna(rpm) or pd.isna(afr):
            continue

        # Find nearest RPM bin
        rpm_bin = nearest_bin(rpm, rpm_bins)
        rpm_idx = rpm_bins.index(rpm_bin)

        # Find nearest MAP bin (default to 65 kPa if no MAP data)
        if has_map and not pd.isna(row.get("MAP_kPa")):
            map_kpa = row["MAP_kPa"]
        else:
            # Estimate MAP from RPM if not available
            if rpm < 2000:
                map_kpa = 35
            elif rpm < 3500:
                map_kpa = 50
            elif rpm < 5000:
                map_kpa = 65
            else:
                map_kpa = 80

        map_bin = nearest_bin(map_kpa, map_bins)
        map_idx = map_bins.index(map_bin)

        hit_count[rpm_idx, map_idx] += 1
        afr_sum[rpm_idx, map_idx] += afr

    # Calculate mean AFR per cell
    mean_afr = np.zeros((n_rpm, n_map))
    mean_afr[:] = np.nan
    valid_mask = hit_count >= config.min_hits_per_cell
    mean_afr[valid_mask] = afr_sum[valid_mask] / hit_count[valid_mask]

    # Calculate AFR error (for diagnostics)
    afr_error = mean_afr - target_afr  # positive = lean, negative = rich

    # Calculate VE corrections using versioned math
    # v2.0.0 (default): Ratio model - VE_correction = AFR_measured / AFR_target
    # v1.0.0 (legacy): Linear model - VE_correction = 1 + (AFR_error * 7%)
    ve_correction = np.ones((n_rpm, n_map))
    ve_delta_pct = np.zeros((n_rpm, n_map))

    for i in range(n_rpm):
        for j in range(n_map):
            if valid_mask[i, j]:
                measured = mean_afr[i, j]
                target = target_afr[i, j]

                # Use the versioned VE math module
                correction = calculate_ve_correction(
                    measured,
                    target,
                    version=config.math_version,
                    clamp=False,  # We clamp below with our own limits
                )
                ve_correction[i, j] = correction
                ve_delta_pct[i, j] = correction_to_percentage(correction)

    # Clamp corrections
    min_mult = 1 - config.max_ve_correction_pct / 100
    max_mult = 1 + config.max_ve_correction_pct / 100
    ve_correction = np.clip(ve_correction, min_mult, max_mult)

    # Set invalid cells to 1.0 (no correction)
    ve_correction[~valid_mask] = 1.0

    # Build cell analysis list
    cells = []
    lean_cells = 0
    rich_cells = 0
    ok_cells = 0
    no_data_cells = 0

    for i, rpm in enumerate(rpm_bins):
        for j, map_val in enumerate(map_bins):
            if hit_count[i, j] < config.min_hits_per_cell:
                status = "NO_DATA"
                no_data_cells += 1
                cell_afr_error = 0.0
                cell_ve_delta = 0.0
                cell_mean_afr = 0.0
            else:
                cell_afr_error = afr_error[i, j]
                cell_ve_delta = ve_delta_pct[i, j]
                cell_mean_afr = mean_afr[i, j]

                if cell_afr_error > 0.3:
                    status = "LEAN"
                    lean_cells += 1
                elif cell_afr_error < -0.3:
                    status = "RICH"
                    rich_cells += 1
                else:
                    status = "OK"
                    ok_cells += 1

            cells.append(
                CellAnalysis(
                    rpm_bin=rpm,
                    map_bin=map_val,
                    sample_count=int(hit_count[i, j]),
                    mean_afr=(
                        float(cell_mean_afr) if not np.isnan(cell_mean_afr) else 0.0
                    ),
                    target_afr=float(target_afr[i, j]),
                    afr_error=(
                        float(cell_afr_error) if not np.isnan(cell_afr_error) else 0.0
                    ),
                    ve_delta_pct=(
                        float(cell_ve_delta) if not np.isnan(cell_ve_delta) else 0.0
                    ),
                    status=status,
                )
            )

    # Overall status
    if lean_cells > rich_cells:
        overall_status = "LEAN"
    elif rich_cells > lean_cells:
        overall_status = "RICH"
    else:
        overall_status = "BALANCED"

    # Peak values
    peak_hp_idx = df["Horsepower"].idxmax()
    peak_tq_idx = df["Torque"].idxmax()

    grid = GridAnalysis(
        rpm_bins=rpm_bins,
        map_bins=map_bins,
        hit_count=hit_count,
        mean_afr=mean_afr,
        target_afr=target_afr,
        afr_error=afr_error,
        ve_correction=ve_correction,
        cells=cells,
    )

    return AnalysisResult(
        run_id="",
        timestamp=datetime.now(timezone.utc).isoformat(),
        source_file="",
        total_samples=len(df),
        duration_ms=(
            int(df["timestamp_ms"].max() - df["timestamp_ms"].min())
            if "timestamp_ms" in df.columns
            else 0
        ),
        peak_hp=df.loc[peak_hp_idx, "Horsepower"],
        peak_hp_rpm=df.loc[peak_hp_idx, "RPM"],
        peak_tq=df.loc[peak_tq_idx, "Torque"],
        peak_tq_rpm=df.loc[peak_tq_idx, "RPM"],
        grid=grid,
        overall_status=overall_status,
        lean_cells=lean_cells,
        rich_cells=rich_cells,
        ok_cells=ok_cells,
        no_data_cells=no_data_cells,
    )


# =============================================================================
# Output Generation (2D Grid + PVV XML)
# =============================================================================


def generate_pvv_xml(result: AnalysisResult) -> str:
    """Generate Power Vision PVV XML file with VE corrections."""
    root = ET.Element("PVV")

    grid = result.grid

    # VE Correction Table (Front Cylinder)
    item = ET.SubElement(root, "Item", name="VE Correction (DynoAI)", units="%")

    # Columns are MAP bins
    cols = ET.SubElement(item, "Columns", units="MAP (KPa)")
    for map_val in grid.map_bins:
        ET.SubElement(cols, "Col", label=str(map_val))

    # Rows are RPM bins
    rows = ET.SubElement(item, "Rows", units="RPM")
    for i, rpm in enumerate(grid.rpm_bins):
        row = ET.SubElement(rows, "Row", label=str(rpm))
        for j in range(len(grid.map_bins)):
            # Convert multiplier to percentage change
            mult = grid.ve_correction[i, j]
            pct_change = (mult - 1) * 100
            ET.SubElement(row, "Cell", value=f"{pct_change:.2f}")

    # AFR Error Table (for reference)
    item2 = ET.SubElement(
        root, "Item", name="AFR Error (Measured - Target)", units="AFR"
    )
    cols2 = ET.SubElement(item2, "Columns", units="MAP (KPa)")
    for map_val in grid.map_bins:
        ET.SubElement(cols2, "Col", label=str(map_val))

    rows2 = ET.SubElement(item2, "Rows", units="RPM")
    for i, rpm in enumerate(grid.rpm_bins):
        row = ET.SubElement(rows2, "Row", label=str(rpm))
        for j in range(len(grid.map_bins)):
            err = grid.afr_error[i, j]
            val = f"{err:.2f}" if not np.isnan(err) else "0.00"
            ET.SubElement(row, "Cell", value=val)

    # Hit Count Table (for reference)
    item3 = ET.SubElement(root, "Item", name="Sample Count (DynoAI)", units="count")
    cols3 = ET.SubElement(item3, "Columns", units="MAP (KPa)")
    for map_val in grid.map_bins:
        ET.SubElement(cols3, "Col", label=str(map_val))

    rows3 = ET.SubElement(item3, "Rows", units="RPM")
    for i, rpm in enumerate(grid.rpm_bins):
        row = ET.SubElement(rows3, "Row", label=str(rpm))
        for j in range(len(grid.map_bins)):
            ET.SubElement(row, "Cell", value=str(grid.hit_count[i, j]))

    # Pretty print
    ET.indent(root, space="\t")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(
        root, encoding="unicode"
    )


def generate_outputs(
    df: pd.DataFrame,
    result: AnalysisResult,
    output_dir: Path,
) -> dict[str, Path]:
    """Generate all output files including PVV XML."""
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}

    grid = result.grid

    # 1. Raw data CSV
    csv_path = output_dir / "run.csv"
    df.to_csv(csv_path, index=False)
    outputs["raw_csv"] = csv_path

    # 2. VE corrections 2D grid CSV
    ve_csv_path = output_dir / "VE_Corrections_2D.csv"
    with open(ve_csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        # Header row with MAP bins
        header = ["RPM\\MAP"] + [str(m) for m in grid.map_bins]
        writer.writerow(header)
        # Data rows
        for i, rpm in enumerate(grid.rpm_bins):
            row = [str(rpm)]
            for j in range(len(grid.map_bins)):
                mult = grid.ve_correction[i, j]
                row.append(f"{mult:.4f}")
            writer.writerow(row)
    outputs["ve_corrections_2d"] = ve_csv_path

    # 3. AFR Error 2D grid CSV
    afr_csv_path = output_dir / "AFR_Error_2D.csv"
    with open(afr_csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["RPM\\MAP"] + [str(m) for m in grid.map_bins]
        writer.writerow(header)
        for i, rpm in enumerate(grid.rpm_bins):
            row = [str(rpm)]
            for j in range(len(grid.map_bins)):
                err = grid.afr_error[i, j]
                row.append(f"{err:.2f}" if not np.isnan(err) else "N/A")
            writer.writerow(row)
    outputs["afr_error_2d"] = afr_csv_path

    # 4. Hit count 2D grid CSV
    hits_csv_path = output_dir / "Hit_Count_2D.csv"
    with open(hits_csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["RPM\\MAP"] + [str(m) for m in grid.map_bins]
        writer.writerow(header)
        for i, rpm in enumerate(grid.rpm_bins):
            row = [str(rpm)]
            for j in range(len(grid.map_bins)):
                row.append(str(grid.hit_count[i, j]))
            writer.writerow(row)
    outputs["hit_count_2d"] = hits_csv_path

    # 5. Power Vision PVV XML (main output!)
    pvv_path = output_dir / "VE_Correction.pvv"
    pvv_xml = generate_pvv_xml(result)
    with open(pvv_path, "w", encoding="utf-8") as f:
        f.write(pvv_xml)
    outputs["pvv_file"] = pvv_path

    # 6. Paste-ready VE delta table
    paste_path = output_dir / "VE_Delta_PasteReady.txt"
    with open(paste_path, "w") as f:
        f.write("# DynoAI VE Correction Table (2D Grid)\n")
        f.write(f"# Generated: {result.timestamp}\n")
        f.write(f"# Peak HP: {result.peak_hp:.1f} @ {result.peak_hp_rpm:.0f} RPM\n")
        f.write(f"# Peak TQ: {result.peak_tq:.1f} @ {result.peak_tq_rpm:.0f} RPM\n")
        f.write("#" + "=" * 60 + "\n\n")

        # Header
        f.write(f"{'RPM':>6s}")
        for m in grid.map_bins:
            f.write(f" | {m:>5d}kPa")
        f.write("\n")
        f.write("-" * (7 + 10 * len(grid.map_bins)) + "\n")

        # Data rows
        for i, rpm in enumerate(grid.rpm_bins):
            f.write(f"{rpm:>6d}")
            for j in range(len(grid.map_bins)):
                mult = grid.ve_correction[i, j]
                delta = (mult - 1) * 100
                f.write(f" | {delta:+5.1f}%  ")
            f.write("\n")
    outputs["paste_ready"] = paste_path

    # 7. TuneLab script with 2D grid
    tunelab_path = output_dir / "TuneLab_VE_Correction.py"
    with open(tunelab_path, "w") as f:
        f.write('"""\n')
        f.write("DynoAI Auto-Generated TuneLab VE Correction Script\n")
        f.write(f"Generated: {result.timestamp}\n")
        f.write(f"Peak HP: {result.peak_hp:.1f} @ {result.peak_hp_rpm:.0f} RPM\n")
        f.write(f"Peak TQ: {result.peak_tq:.1f} @ {result.peak_tq_rpm:.0f} RPM\n")
        f.write('"""\n\n')
        f.write(f"RPM_BINS = {grid.rpm_bins}\n")
        f.write(f"MAP_BINS = {grid.map_bins}\n\n")
        f.write("# VE correction multipliers [RPM_idx][MAP_idx]\n")
        f.write("VE_CORRECTIONS = [\n")
        for i, rpm in enumerate(grid.rpm_bins):
            row_vals = [
                f"{grid.ve_correction[i, j]:.4f}" for j in range(len(grid.map_bins))
            ]
            f.write(f"    [{', '.join(row_vals)}],  # {rpm} RPM\n")
        f.write("]\n")
    outputs["tunelab_script"] = tunelab_path

    # 8. Analysis manifest (JSON)
    manifest_path = output_dir / "manifest.json"
    manifest = {
        "run_id": result.run_id,
        "timestamp": result.timestamp,
        "source_file": result.source_file,
        "analysis": {
            "total_samples": result.total_samples,
            "duration_ms": result.duration_ms,
            "peak_hp": result.peak_hp,
            "peak_hp_rpm": result.peak_hp_rpm,
            "peak_tq": result.peak_tq,
            "peak_tq_rpm": result.peak_tq_rpm,
            "power_curve": _build_power_curve(df),
            "overall_status": result.overall_status,
            "lean_cells": result.lean_cells,
            "rich_cells": result.rich_cells,
            "ok_cells": result.ok_cells,
            "no_data_cells": result.no_data_cells,
        },
        "grid": {
            "rpm_bins": grid.rpm_bins,
            "map_bins": grid.map_bins,
            "ve_correction": grid.ve_correction.tolist(),
            "hit_count": grid.hit_count.tolist(),
        },
        "outputs": {k: str(v) for k, v in outputs.items()},
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    outputs["manifest"] = manifest_path

    # 9. Diagnostics report
    report_path = output_dir / "Diagnostics_Report.txt"
    with open(report_path, "w") as f:
        f.write("=" * 70 + "\n")
        f.write("DYNOAI AUTO-TUNE ANALYSIS REPORT (2D RPM × MAP Grid)\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Run ID: {result.run_id}\n")
        f.write(f"Generated: {result.timestamp}\n")
        f.write(f"Samples: {result.total_samples}\n")
        f.write(f"Duration: {result.duration_ms / 1000:.1f} seconds\n\n")

        f.write("PEAK PERFORMANCE\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Peak HP: {result.peak_hp:.1f} @ {result.peak_hp_rpm:.0f} RPM\n")
        f.write(
            f"  Peak TQ: {result.peak_tq:.1f} ft-lb @ {result.peak_tq_rpm:.0f} RPM\n\n"
        )

        f.write("GRID ANALYSIS SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Grid Size: {len(grid.rpm_bins)} RPM × {len(grid.map_bins)} MAP\n")
        f.write(f"  Total Cells: {len(grid.rpm_bins) * len(grid.map_bins)}\n")
        f.write(f"  Lean Cells:    {result.lean_cells}\n")
        f.write(f"  Rich Cells:    {result.rich_cells}\n")
        f.write(f"  OK Cells:      {result.ok_cells}\n")
        f.write(f"  No Data Cells: {result.no_data_cells}\n\n")

        f.write("VE CORRECTION GRID (% change)\n")
        f.write("-" * 70 + "\n")
        f.write(f"{'RPM':>6s}")
        for m in grid.map_bins:
            f.write(f" | {m:>5d}kPa")
        f.write("\n")
        f.write("-" * 70 + "\n")
        for i, rpm in enumerate(grid.rpm_bins):
            f.write(f"{rpm:>6d}")
            for j in range(len(grid.map_bins)):
                mult = grid.ve_correction[i, j]
                delta = (mult - 1) * 100
                if grid.hit_count[i, j] == 0:
                    f.write(" |   ---  ")
                else:
                    f.write(f" | {delta:+5.1f}%  ")
            f.write("\n")
        f.write("\n")

        f.write("HIT COUNT GRID (samples per cell)\n")
        f.write("-" * 70 + "\n")
        f.write(f"{'RPM':>6s}")
        for m in grid.map_bins:
            f.write(f" | {m:>5d}kPa")
        f.write("\n")
        f.write("-" * 70 + "\n")
        for i, rpm in enumerate(grid.rpm_bins):
            f.write(f"{rpm:>6d}")
            for j in range(len(grid.map_bins)):
                hits = grid.hit_count[i, j]
                f.write(f" | {hits:>5d}   ")
            f.write("\n")
        f.write("\n")

        f.write("OVERALL ASSESSMENT\n")
        f.write("-" * 40 + "\n")
        f.write(f"  Status: {result.overall_status}\n")
        if result.overall_status == "LEAN":
            f.write("  >> Overall tune is LEAN - increase fuel/VE\n")
        elif result.overall_status == "RICH":
            f.write("  >> Overall tune is RICH - decrease fuel/VE\n")
        else:
            f.write("  >> Tune appears balanced - minor adjustments only\n")

        f.write("\nGENERATED FILES\n")
        f.write("-" * 40 + "\n")
        f.write("  VE_Correction.pvv        <- Power Vision XML (import directly!)\n")
        f.write("  VE_Corrections_2D.csv    <- Spreadsheet-ready grid\n")
        f.write("  VE_Delta_PasteReady.txt  <- Copy/paste table\n")
        f.write("  TuneLab_VE_Correction.py <- Power Core script\n")

        f.write("\nNEXT STEPS\n")
        f.write("-" * 40 + "\n")
        f.write("  1. Import VE_Correction.pvv into Power Vision\n")
        f.write("  2. Review corrections in Power Core\n")
        f.write("  3. Re-run dyno pull to verify\n")
        f.write("  4. Iterate until all cells show OK status\n")
        f.write("\n" + "=" * 70 + "\n")

    outputs["report"] = report_path

    return outputs


# =============================================================================
# Main Pipeline
# =============================================================================


def print_banner():
    print(
        """
+==============================================================+
|                    DYNOAI AUTO-TUNE                          |
|          JetDrive -> Analysis -> Tuning Corrections          |
+==============================================================+
"""
    )


def print_results(result: AnalysisResult, outputs: dict[str, Path]):
    """Print 2D grid analysis results to console."""
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE (2D RPM × MAP Grid)")
    print("=" * 70)

    print("\nPeak Performance:")
    print(f"  HP: {result.peak_hp:.1f} @ {result.peak_hp_rpm:.0f} RPM")
    print(f"  TQ: {result.peak_tq:.1f} ft-lb @ {result.peak_tq_rpm:.0f} RPM")

    grid = result.grid

    print("\nVE Correction Grid (% change):")
    print("-" * 70)
    # Header
    header = f"{'RPM':>6s}"
    for m in grid.map_bins:
        header += f" | {m:>5d}kPa"
    print(header)
    print("-" * 70)

    # Data rows (show subset if large)
    show_rpms = grid.rpm_bins if len(grid.rpm_bins) <= 6 else grid.rpm_bins[::2]
    for i, rpm in enumerate(grid.rpm_bins):
        if rpm not in show_rpms:
            continue
        row = f"{rpm:>6d}"
        for j in range(len(grid.map_bins)):
            mult = grid.ve_correction[i, j]
            delta = (mult - 1) * 100
            hits = grid.hit_count[i, j]
            if hits == 0:
                row += " |   ---  "
            else:
                row += f" | {delta:+5.1f}%  "
        print(row)

    if len(grid.rpm_bins) > 6:
        print(f"  ... ({len(grid.rpm_bins)} RPM bins total, showing every other)")

    print("\nGrid Summary:")
    print(f"  Total Cells: {len(grid.rpm_bins) * len(grid.map_bins)}")
    print(
        "  Lean: "
        f"{result.lean_cells}  Rich: {result.rich_cells}  OK: {result.ok_cells}  No Data: {result.no_data_cells}"
    )
    print(f"  Overall: {result.overall_status}")

    print("\nGenerated Files:")
    key_files = ["pvv_file", "ve_corrections_2d", "paste_ready", "report"]
    for name in key_files:
        if name in outputs:
            print(f"  * {name:20s} -> {outputs[name]}")
    print(f"  ... and {len(outputs) - len(key_files)} more files")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="DynoAI JetDrive Auto-Tune Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simulate a dyno run and analyze:
  python scripts/jetdrive_autotune.py --simulate --run-id test_run

  # Analyze existing CSV file:
  python scripts/jetdrive_autotune.py --csv runs/my_run/run.csv --run-id my_run
        """,
    )

    parser.add_argument("--run-id", required=True, help="Unique run identifier")
    parser.add_argument("--csv", help="Path to existing CSV file to analyze")
    parser.add_argument(
        "--simulate", action="store_true", help="Generate simulated dyno data"
    )
    parser.add_argument(
        "--output-dir", help="Output directory (default: runs/<run-id>)"
    )
    parser.add_argument(
        "--afr-targets",
        help='AFR targets as JSON dict, e.g. \'{"20":14.7,"100":12.2}\'',
    )
    parser.add_argument(
        "--math-version",
        choices=["1.0.0", "2.0.0"],
        default="2.0.0",
        help="VE calculation math version: 1.0.0 (legacy 7%% per AFR), 2.0.0 (ratio model, default)",
    )
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress output")

    args = parser.parse_args()

    try:
        safe_run_id = sanitize_run_id(args.run_id)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    # Parse math version
    math_version = (
        MathVersion.V2_0_0 if args.math_version == "2.0.0" else MathVersion.V1_0_0
    )

    # Parse AFR targets if provided
    afr_targets: dict[int, float] | None = None
    if args.afr_targets:
        try:
            raw_targets = json.loads(args.afr_targets)
            # Convert string keys to int (JSON keys are always strings)
            afr_targets = {int(k): float(v) for k, v in raw_targets.items()}
            if not args.quiet:
                print(f"Using custom AFR targets: {afr_targets}")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Invalid AFR targets JSON, using defaults: {e}")
            afr_targets = None

    if not args.quiet:
        print_banner()

    # Determine output directory
    try:
        # NOTE: we always derive output under runs/<run-id> to keep paths constrained.
        # If you need custom output locations, copy the run folder after generation.
        output_dir = safe_path(str(Path("runs") / safe_run_id))
    except ValueError as e:
        print(f"Error: Invalid output directory: {e}")
        return 1

    # Get data
    if args.csv:
        if not args.quiet:
            print(f"Loading data from: {args.csv}")
        df = pd.read_csv(args.csv)
        source_file = args.csv
    elif args.simulate:
        if not args.quiet:
            print("Generating simulated dyno run...")
        df = generate_simulated_dyno_run()
        source_file = "simulated"
    else:
        print("Error: Must specify --csv or --simulate")
        return 1

    if not args.quiet:
        print(f"Loaded {len(df)} samples")

    # Run analysis
    if not args.quiet:
        print(f"Running analysis (math version {math_version})...")

    # Create config with selected math version
    config = TuneConfig(math_version=math_version)
    result = analyze_dyno_data(df, config=config, afr_targets=afr_targets)
    result.run_id = safe_run_id
    result.source_file = source_file

    # Generate outputs
    if not args.quiet:
        print(f"Generating outputs to: {output_dir}")

    outputs = generate_outputs(df, result, output_dir)

    # Print results
    if not args.quiet:
        print_results(result, outputs)

    return 0


if __name__ == "__main__":
    sys.exit(main())
