"""
DynoAI3 - Deterministic Dyno Tuning Toolkit

A deterministic, automation-first, post-processing calibration engine for dyno data.

MATH VERSION: 1.0.0 (FROZEN)
============================

This module implements the core VE correction analysis engine with three deterministic
kernels applied in a fixed, documented order:

1. K1: Gradient-Limited Adaptive Smoothing
   - Preserves large corrections (≥3.0%) while smoothing noise
   - Parameters: passes=2, gradient_threshold=1.0

2. K2: Coverage-Weighted Smoothing
   - Neighbor-weighted averaging with center bias
   - Parameters: alpha=0.20, center_bias=1.25, min_hits=1, dist_pow=1

3. K3: Tiered Spark Logic
   - Knock-based spark retard with hot IAT compensation
   - Parameters: extra_rule_deg=2.0, hot_extra=-1.0

FROZEN PARAMETERS:
All kernel parameters listed above are FROZEN and will not change without a major
version increment. See docs/KERNEL_SPECIFICATION.md for complete mathematical details.

DETERMINISTIC GUARANTEES:
- Same inputs always produce same outputs (bit-for-bit)
- No randomness, no adaptive learning, no cross-run state
- Apply/rollback operations are exact mathematical inverses
- SHA-256 verification on all apply operations

See docs/DETERMINISTIC_MATH_SPECIFICATION.md for the complete specification.
"""

import argparse
import csv
import json
import logging
import math
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, cast

from dynoai.constants import (
    AFR_RANGE_MAX,
    AFR_RANGE_MIN,
    HOT_IAT_THRESHOLD_F,
    INVALID_AFR_SENTINEL,
    KPA_BINS,
    KPA_INDEX,
    RPM_BINS,
    RPM_INDEX,
    STOICH_AFR_GASOLINE,
    TORQUE_HP_CONVERSION,
    Grid,
    GridList,
)
from dynoai.core import io_contracts
from dynoai.core.io_contracts import sanitize_csv_cell

# Configure logging
logger = logging.getLogger(__name__)

# Session replay logging - thread-safe
_session_log: List[Dict[str, Any]] = []
_session_log_lock = threading.Lock()


def log_decision(
    action: str,
    reason: str,
    values: Optional[Dict[str, Any]] = None,
    cell: Optional[Dict[str, int]] = None,
) -> None:
    """Log a decision made during processing for session replay.

    This function is thread-safe and adds minimal overhead (<1%).

    Args:
        action: Action performed (e.g., "AFR_CORRECTION", "SMOOTHING", "CLAMPING")
        reason: Reason for the action
        values: Optional dict of values involved (before/after)
        cell: Optional cell location (rpm, kpa indices)

    Thread-safety: Uses a lock to ensure safe concurrent access to session log.
    """
    entry = {
        "timestamp": io_contracts.utc_now_iso(),
        "action": action,
        "reason": reason,
    }

    if values is not None:
        entry["values"] = values

    if cell is not None:
        entry["cell"] = cell

    # Thread-safe append
    with _session_log_lock:
        _session_log.append(entry)


def get_session_log() -> List[Dict[str, Any]]:
    """Get a copy of the current session log (thread-safe)."""
    with _session_log_lock:
        return _session_log.copy()


def clear_session_log() -> None:
    """Clear the session log (thread-safe)."""
    with _session_log_lock:
        _session_log.clear()


def create_rpm_bins_standard() -> List[int]:
    """Create standard RPM bin edges: 2000-6500 by 500.

    Note: This creates an alternative standard range that excludes 1500 RPM.
    Use this for typical dyno tuning ranges. The RPM_BINS constant above
    includes 1500 RPM for extended low-end coverage.

    Returns:
        List[int]: Standard RPM bin edges [2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]
    """
    return list(range(2000, 6501, 500))


def create_kpa_bins_standard() -> List[int]:
    """Create standard MAP/KPA bin edges: 50-100 by 10.

    Note: This creates an alternative standard range with finer resolution.
    Use this for typical dyno tuning with 10 kPa steps. The KPA_BINS constant
    above uses coarser 15 kPa steps optimized for specific tuning scenarios.

    Returns:
        List[int]: Standard MAP/KPA bin edges [50, 60, 70, 80, 90, 100]
    """
    return list(range(50, 101, 10))


def compute_ve_delta(
    measured: Grid,
    target: Grid,
    clamp_pct: float = 12.0,
) -> GridList:
    """Compute VE deltas as percentages, clamped to +/- clamp_pct.

    Note: This helper is not used by the current CLI flow. It exists as a
    small, testable building block for future refactors or library usage.

    Args:
        measured: 2D grid of measured values (same shape as target).
        target: 2D grid of target values.
        clamp_pct: Maximum absolute percentage delta to allow.

    Returns:
        2D list with percentage deltas or None for missing cells.

    Raises:
        ValueError: If shapes differ or inputs are empty.
    """
    if not measured or not target:
        raise ValueError("Inputs cannot be empty")
    if len(measured) != len(target) or any(
        len(m) != len(t) for m, t in zip(measured, target)
    ):
        raise ValueError("Shape mismatch between measured and target grids")

    def clamp_val(v: float, limit: float) -> float:
        return max(-limit, min(limit, v))

    out: GridList = []
    for m_row, t_row in zip(measured, target):
        row: List[Optional[float]] = []
        for m, t in zip(m_row, t_row):
            if t is None or m is None or t == 0:
                row.append(None)
            else:
                pct = ((t - m) / t) * 100.0
                row.append(clamp_val(pct, clamp_pct))
        out.append(row)
    return out


def create_bins(start: int, end: int, step: int) -> List[int]:
    """Create custom bin edges from start to end (inclusive) with given step.

    Args:
        start (int): Starting value for bins
        end (int): Ending value for bins (inclusive)
        step (int): Step size between bins (must be positive)

    Returns:
        List[int]: List of bin edges

    Raises:
        ValueError: If step is not positive

    Example:
        >>> create_bins(2000, 6500, 500)
        [2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]
    """
    if step <= 0:
        raise ValueError(f"Step must be positive, got {step}")
    return list(range(start, end + 1, step))


def nearest_bin(val: float, bins: Sequence[int]) -> int:
    """Find the nearest bin value to the given value.

    Performance: Optimized for small bin arrays (typical size: 5-11 bins).
    Uses simple iteration instead of min() with lambda to reduce overhead.

    Args:
        val: Value to find nearest bin for
        bins: Sequence of bin values (assumed to be sorted)

    Returns:
        The bin value closest to val
    """
    if not bins:
        raise ValueError("bins cannot be empty")

    # For small bin counts (5-11), simple iteration is faster than min() with lambda
    nearest = bins[0]
    min_diff = abs(bins[0] - val)

    for b in bins[1:]:
        diff = abs(b - val)
        if diff < min_diff:
            min_diff = diff
            nearest = b

    return nearest


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def safe_float(x: Any) -> Optional[float]:
    """Convert value to float safely, returning None for invalid values.

    Performance: Optimized with early returns and fast-path for common cases.


    Args:
        x: Value to convert (can be str, int, float, etc.)

    Returns:
        Float value, or None if conversion fails or value is NaN/Inf

    Example:
        >>> safe_float("3.14")
        3.14
        >>> safe_float("invalid")
        None
        >>> safe_float(float('nan'))
        None
    """
    # Fast path: x is already a valid float
    if isinstance(x, (int, float)):
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return None
        return f

    # Slow path: conversion needed
    try:
        value = float(x)
        # Check for NaN/Inf after conversion
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    except (ValueError, TypeError):  # Specific exceptions instead of broad Exception
        return None


def find_column_by_candidates(
    headers: List[str], candidates: Sequence[str]
) -> Optional[str]:
    """
    Find a column header matching one of the candidate strings.

    This function uses a two-pass approach:
    1. Exact match (case-insensitive, space/underscore normalized)
    2. Substring match (fallback for partial matches)

    Args:
        headers: List of column header names
        candidates: List of candidate strings to search for (should be lowercase)

    Returns:
        The first matching header name, or None if no match found

    Example:
        >>> headers = ["RPM", "MAP_kPa", "Torque"]
        >>> find_column_by_candidates(headers, ["rpm"])
        'RPM'
        >>> find_column_by_candidates(headers, ["map", "kpa"])
        'MAP_kPa'
    """
    # Filter out None headers
    valid_headers = [h for h in headers if h is not None]

    # Pass 1: Exact match (case-insensitive, space/underscore normalized)
    headers_norm = {h: h.strip().lower().replace("_", " ") for h in valid_headers}
    for c in candidates:
        for h_orig, h_norm in headers_norm.items():
            if c == h_norm:
                return h_orig

    # Pass 2: Substring match (as a fallback)
    for name in valid_headers:
        low = name.strip().lower().replace("_", " ")
        for c in candidates:
            if c in low:
                return name

    return None


def mean(xs: Sequence[Optional[float]]) -> Optional[float]:
    vals: List[float] = [float(x) for x in xs if x is not None]
    return sum(vals) / len(vals) if vals else None


def median(xs: Sequence[Optional[float]]) -> Optional[float]:
    """Calculate median of a list of values."""
    vals: List[float] = [float(x) for x in xs if x is not None]
    if not vals:
        return None
    xs_sorted: List[float] = sorted(vals)
    count = len(xs_sorted)
    if count % 2 == 0:
        return (xs_sorted[count // 2 - 1] + xs_sorted[count // 2]) / 2.0
    else:
        return xs_sorted[count // 2]


def mad(xs: Sequence[Optional[float]]) -> Optional[float]:
    """Calculate median absolute deviation."""
    vals: List[float] = [float(x) for x in xs if x is not None]
    if not vals:
        return None
    med = median(vals)
    if med is None:
        return None
    deviations: List[float] = [abs(x - med) for x in vals]
    return median(deviations)


def kernel_smooth(
    grid: List[List[Optional[float]]], passes: int = 2, gradient_threshold: float = 1.0
) -> List[List[Optional[float]]]:
    """
    Gradient-limited kernel smoothing for VE corrections (K1 Kernel).

    This kernel applies smoothing but limits it in areas with high gradients
    (sudden changes) to preserve important features while reducing noise.

    Algorithm:
    1. Calculate gradient magnitude for each cell (max neighbor difference)
    2. Apply normal adaptive smoothing
    3. For cells with high gradients, blend back toward original value
    4. Apply coverage-weighted smoothing as fallback

    Args:
        grid: Input correction grid (9x5)
        passes: Number of smoothing passes (default: 2)
        gradient_threshold: Gradient threshold above which smoothing is limited (default: 2.0%)

    Returns:
        Smoothed grid with gradient-limited adjustments
    """
    if not grid:
        return grid

    log_decision(
        action="SMOOTHING_START",
        reason=f"Starting gradient-limited smoothing with {passes} passes, threshold={gradient_threshold}%",
        values={"passes": passes, "gradient_threshold": gradient_threshold},
    )

    rows, cols = len(grid), len(grid[0])

    # Stage 1: Calculate gradient magnitudes
    gradients = [[0.0 for _ in range(cols)] for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            center_val = grid[r][c]
            if center_val is None:
                continue

            max_diff = 0.0
            # Check all 4 neighbors
            neighbors = []
            if r > 0 and grid[r - 1][c] is not None:
                neighbors.append(grid[r - 1][c])
            if r < rows - 1 and grid[r + 1][c] is not None:
                neighbors.append(grid[r + 1][c])
            if c > 0 and grid[r][c - 1] is not None:
                neighbors.append(grid[r][c - 1])
            if c < cols - 1 and grid[r][c + 1] is not None:
                neighbors.append(grid[r][c + 1])

            for neighbor_val in neighbors:
                diff = abs(center_val - neighbor_val)
                max_diff = max(max_diff, diff)

            gradients[r][c] = max_diff

    # Stage 2: Adaptive smoothing passes (same as original)
    adaptive_grid = [row[:] for row in grid]  # Deep copy

    for r in range(rows):
        for c in range(cols):
            center_val = adaptive_grid[r][c]
            if center_val is None:
                continue

            # Determine adaptive passes based on correction magnitude
            abs_correction = abs(center_val)
            if abs_correction >= 3.0:
                # Large corrections: no smoothing passes
                adaptive_passes = 0
            elif abs_correction <= 1.0:
                # Small corrections: full smoothing passes
                adaptive_passes = passes
            else:
                # Linear taper between 1.0% and 3.0%
                taper_factor = (3.0 - abs_correction) / (
                    3.0 - 1.0
                )  # 1.0 at 1%, 0.0 at 3%
                adaptive_passes = int(round(passes * taper_factor))

            # Apply adaptive smoothing passes to this cell
            if adaptive_passes > 0:
                smoothed_val = center_val
                for _ in range(adaptive_passes):
                    neighbors = [smoothed_val]  # Include center

                    # Add valid neighbors
                    if r > 0 and adaptive_grid[r - 1][c] is not None:
                        neighbors.append(adaptive_grid[r - 1][c])  # Up
                    if r < rows - 1 and adaptive_grid[r + 1][c] is not None:
                        neighbors.append(adaptive_grid[r + 1][c])  # Down
                    if c > 0 and adaptive_grid[r][c - 1] is not None:
                        neighbors.append(adaptive_grid[r][c - 1])  # Left
                    if c < cols - 1 and adaptive_grid[r][c + 1] is not None:
                        neighbors.append(adaptive_grid[r][c + 1])  # Right

                    smoothed_val = sum(neighbors) / len(neighbors)

                adaptive_grid[r][c] = smoothed_val

    # Stage 3: Gradient-limited blending
    gradient_limited_grid = [row[:] for row in adaptive_grid]

    for r in range(rows):
        for c in range(cols):
            original_val = grid[r][c]
            smoothed_val = adaptive_grid[r][c]

            if original_val is None or smoothed_val is None:
                continue

            gradient_magnitude = gradients[r][c]

            # If gradient is above threshold, blend back toward original
            if gradient_magnitude > gradient_threshold:
                # Blend factor: higher gradient = more weight to original
                blend_factor = min(1.0, gradient_magnitude / (gradient_threshold * 2))
                # blend_factor = 0.5 when gradient = threshold
                # blend_factor = 1.0 when gradient = threshold * 2

                gradient_limited_grid[r][c] = (
                    1 - blend_factor
                ) * smoothed_val + blend_factor * original_val

                # Log gradient limiting for significant cases
                if gradient_magnitude > gradient_threshold * 1.5:
                    log_decision(
                        action="GRADIENT_LIMITING",
                        reason=f"High gradient detected, blending toward original value",
                        values={
                            "gradient": round(gradient_magnitude, 2),
                            "threshold": gradient_threshold,
                            "blend_factor": round(blend_factor, 3),
                            "original": round(original_val, 2),
                            "smoothed": round(smoothed_val, 2),
                            "result": round(gradient_limited_grid[r][c], 2),
                        },
                        cell={"rpm_index": r, "kpa_index": c},
                    )

    # Stage 4: Coverage-weighted smoothing (same as original)
    final_grid = [row[:] for row in gradient_limited_grid]

    # Parameters for coverage-weighted smoothing
    alpha = 0.20
    center_bias = 1.25
    min_hits = 1
    dist_pow = 1

    # For each cell, compute coverage-weighted average
    for r in range(rows):
        for c in range(cols):
            center_val = final_grid[r][c]
            if center_val is None:
                continue

            # Collect neighbor values and weights
            neighbor_values = []
            neighbor_weights = []

            # Center cell (with bias)
            neighbor_values.append(center_val)
            neighbor_weights.append(center_bias)

            # Neighbor cells with distance-based weights
            neighbors = [
                (r - 1, c, 1.0),  # Up
                (r + 1, c, 1.0),  # Down
                (r, c - 1, 1.0),  # Left
                (r, c + 1, 1.0),  # Right
            ]

            for nr, nc, base_weight in neighbors:
                if 0 <= nr < rows and 0 <= nc < cols:
                    n_val = final_grid[nr][nc]
                    if n_val is not None:
                        # Distance weighting (all immediate neighbors have dist=1)
                        dist_weight = 1.0 / (1.0**dist_pow)
                        neighbor_values.append(n_val)
                        neighbor_weights.append(base_weight * dist_weight)

            # Apply coverage weighting if we have enough neighbors
            if len(neighbor_values) >= min_hits:
                # Weighted average with alpha blending
                weighted_sum = sum(
                    v * w for v, w in zip(neighbor_values, neighbor_weights)
                )
                total_weight = sum(neighbor_weights)
                smoothed_val = weighted_sum / total_weight

                # Blend with original value using alpha
                final_grid[r][c] = alpha * smoothed_val + (1 - alpha) * center_val
            # If insufficient neighbors, keep original value

    return final_grid


def write_matrix_csv(
    path: str | Path,
    rpm_bins: Sequence[int],
    kpa_bins: Sequence[int],
    grid: Sequence[Sequence[Optional[float]]],
    value_fmt: str = "{:+.2f}",
) -> str:
    # Enforce safe target path inside workspace
    target = io_contracts.safe_path(str(path))
    with open(target, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["RPM"] + [sanitize_csv_cell(k) for k in kpa_bins])
        for ri, rpm in enumerate(rpm_bins):
            row: List[Any] = [sanitize_csv_cell(rpm)]
            for ci in range(len(kpa_bins)):
                cell_value = grid[ri][ci]
                formatted_value = (
                    "" if cell_value is None else value_fmt.format(cell_value)
                )
                row.append(sanitize_csv_cell(formatted_value))
            writer.writerow(row)
    return str(target)


OUTPUT_SPECS: Sequence[Tuple[str, str, str, bool]] = [
    ("VE_Correction_Delta_DYNO.csv", "csv", "ve_delta_grid", True),
    ("Spark_Adjust_Suggestion_Front.csv", "csv", "spark_suggestion_front", True),
    ("Spark_Adjust_Suggestion_Rear.csv", "csv", "spark_suggestion_rear", True),
    ("AFR_Error_Map_Front.csv", "csv", "afr_error_front", True),
    ("AFR_Error_Map_Rear.csv", "csv", "afr_error_rear", True),
    ("Coverage_Front.csv", "csv", "coverage_front", True),
    ("Coverage_Rear.csv", "csv", "coverage_rear", True),
    ("VE_Delta_PasteReady.txt", "text", "ve_delta_paste", False),
    ("Spark_Front_PasteReady.txt", "text", "spark_front_paste", False),
    ("Spark_Rear_PasteReady.txt", "text", "spark_rear_paste", False),
    ("Diagnostics_Report.txt", "text", "diagnostics_report", False),
    ("Anomaly_Hypotheses.json", "json", "anomaly_hypotheses", False),
    ("PowerOpportunities.json", "json", "power_opportunities", False),
    ("Coverage_Front_Table.html", "text", "coverage_table_front", False),
    ("Coverage_Front_Enhanced.csv", "csv", "coverage_front_enhanced", True),
    ("Coverage_Front_Heatmap.png", "png", "coverage_front_heatmap", False),
    ("session_replay.json", "json", "session_replay", False),
]


def register_outputs(
    manifest: Dict[str, Any],
    outdir: Path,
    extra_specs: Sequence[Tuple[str, str, str, bool]] = (),
) -> None:
    """Record generated artifacts in the manifest."""

    for filename, ftype, schema, is_grid in [*OUTPUT_SPECS, *extra_specs]:
        fpath = outdir / filename
        if not fpath.exists():
            continue
        rows = len(RPM_BINS) if (is_grid and ftype == "csv") else None
        cols = len(KPA_BINS) if (is_grid and ftype == "csv") else None
        io_contracts.add_output_entry(
            manifest,
            filename,
            str(fpath),
            ftype,
            schema,
            rows=rows,
            cols=cols,
        )
        manifest["outputs"][-1]["path"] = filename


def write_paste_block(
    path: str | Path,
    grid: Sequence[Sequence[Optional[float]]],
    value_fmt: str = "{:+.2f}",
) -> str:
    lines: List[str] = []
    for ri in range(len(RPM_BINS)):
        row_vals: List[str] = []
        for ki in range(len(KPA_BINS)):
            cell_value = grid[ri][ki]
            formatted_value = "" if cell_value is None else value_fmt.format(cell_value)
            row_vals.append(str(sanitize_csv_cell(formatted_value)))
        lines.append("\t".join(row_vals))
    target = io_contracts.safe_path(str(path))
    target.write_text("\n".join(lines))
    return str(target)


def write_grid_csv_absolute(
    path: str | Path, grid: List[List[Optional[float]]]
) -> None:
    target = io_contracts.safe_path(str(path))
    with open(target, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["RPM"] + [sanitize_csv_cell(k) for k in KPA_BINS])
        for ri, rpm in enumerate(RPM_BINS):
            row: List[Any] = [sanitize_csv_cell(rpm)]
            for ki in range(len(KPA_BINS)):
                cell_value = grid[ri][ki]
                formatted_value = "" if cell_value is None else f"{cell_value:.2f}"
                row.append(sanitize_csv_cell(formatted_value))
            writer.writerow(row)


def detect_csv_format(path: str | Path) -> str:
    """Detect whether the log is WinPEP, PowerVision, or generic.

    Robust to comma- or tab-delimited headers (WinPEP8 often uses .txt with tabs).
    """
    # Re-sanitize to appease static analysis and ensure safety if called directly
    path = io_contracts.safe_path(str(path))
    header_line = ""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            header_line = f.readline().strip().lower()
    except (IOError, UnicodeDecodeError):
        try:
            # Fallback for odd encodings sometimes seen in exports
            with open(path, newline="", encoding="cp1252") as f:
                header_line = f.readline().strip().lower()
        except Exception:
            return "unknown"

    # Normalize: treat tabs as commas, collapse extra spaces
    header_line = header_line.replace("\t", ",")
    header_line = ",".join(h.strip() for h in header_line.split(","))

    # Markers for different formats
    winpep_markers = [
        "timestamp",  # WinPEP logs typically contain timestamp
        "rpm",  # generic indicator but common in WinPEP
        "map",
        "kpa",
        "afr cmd",
        "afr meas",
        "knock",
    ]
    generic_markers = ["engspeed (rpm)", "afr measured", "time (s)", "throttle (%)"]
    powervision_markers = [
        "(harley - ecu",
        "(pv) engine speed",
        "(dwr cpu) torque",
        "(pv) wbo2 afr front",
    ]

    # Scoring
    winpep_score = sum(1 for m in winpep_markers if m in header_line)
    generic_score = sum(1 for m in generic_markers if m in header_line)
    powervision_score = sum(1 for m in powervision_markers if m in header_line)

    scores: Dict[str, int] = {
        "winpep": winpep_score,
        "generic": generic_score,
        "powervision": powervision_score,
    }
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "unknown"


def load_generic_csv(path: str | Path) -> List[Dict[str, Optional[float]]]:
    """Loads data from a generic or PowerVision-style CSV log file.

    Enhancements:
    - Expanded header synonyms (PowerVision, descriptive exports).
    - AFR fallback: derive AFR from lambda columns when AFR is missing/invalid (e.g., constant 5.1).
    - Torque derivation: if torque column absent but horsepower present, compute torque = HP * 5252 / RPM.
    """
    target = io_contracts.safe_path(str(path))
    with open(
        target, newline="", encoding="utf-8-sig"
    ) as f:  # Use utf-8-sig for BOM safety
        reader = csv.DictReader(f)

        def normalize_header(h: str) -> str:
            return h.lower().strip()

        reader.fieldnames = [
            normalize_header(fn) if fn else "" for fn in (reader.fieldnames or [])
        ]
        rows: List[Dict[str, str]] = list(reader)
    if not rows:
        raise RuntimeError("Empty CSV file.")

    headers: List[str] = list(rows[0].keys())

    # Convenience wrapper for find_column_by_candidates using current headers
    def find_col(candidates: Sequence[str]) -> Optional[str]:
        return find_column_by_candidates(headers, candidates)

    # Column discovery (normalized for generic & PowerVision)
    col_rpm = find_col(
        [
            "engine speed",
            "engspeed (rpm)",
            "(pv) engine speed",
            "(harley - ecu type 22 sw level 621) engine speed",
            "rpm",
        ]
    )
    col_map = find_col(
        [
            "manifold absolute pressure",
            "map (kpa)",
            "(pv) manifold absolute pressure",
            "(harley - ecu type 22 sw level 621) manifold absolute pressure",
            "map",
            "map kpa",
        ]
    )
    col_torque = find_col(
        [
            "torque",
            "(dwr cpu) torque",
            "(dwrt cpu) torque",
            "(dwrt cpu) torque drum 1",
            "(dwrt cpu) torque (uncorrected)",
            "(pv) torque",
            "engine torque",
        ]
    )
    col_hp = find_col(["horsepower", "hp", "(pv) horsepower", "(pv) power"])
    col_afr_cmd = find_col(
        [
            "desired air/fuel",
            "afr commanded",
            "desired afr",
            "afr target",
            "commanded afr",
        ]
    )
    col_afr_meas = find_col(
        [
            "wbo2 afr front",
            "afr measured",
            "measured afr",
            "(pv) wbo2 afr front",
            "(pv) afr meas",
        ]
    )
    col_iat = find_col(["intake air temperature", "iat (°f)", "iat"])
    col_batt = find_col(["battery voltage", "battery (v)", "vbatt"])
    col_tps = find_col(["throttle position", "throttle (%)", "tps"])

    # Lambda columns (PowerVision often logs lambda instead of valid AFR)
    lambda_cols = [h for h in headers if "lambda" in h]

    # Required columns: RPM & MAP; Torque may be derived from HP if absent
    if not (col_rpm and col_map and (col_torque or col_hp)):
        missing = [n for n, c in [("RPM", col_rpm), ("MAP", col_map)] if not c]
        # Only add Torque to missing list if neither torque nor hp exists
        if not (col_torque or col_hp):
            missing.append("Torque/HP")
        raise RuntimeError(
            f"Missing required columns for generic format: {', '.join(missing)}"
        )

    recs: List[Dict[str, Optional[float]]] = []

    def afr_invalid(v: Optional[float]) -> bool:
        return (
            v is None
            or v < AFR_RANGE_MIN
            or v > AFR_RANGE_MAX
            or abs(v - INVALID_AFR_SENTINEL) < 1e-6
        )

    for row in rows:
        rpm = safe_float(row.get(col_rpm)) if col_rpm else None
        kpa = safe_float(row.get(col_map)) if col_map else None
        torque = safe_float(row.get(col_torque)) if col_torque else None
        horsepower = safe_float(row.get(col_hp)) if col_hp else None
        if rpm is None or kpa is None:
            continue
        if not (400 <= rpm <= 8000) or not (10 <= kpa <= 110):  # basic gating
            continue

        # Torque derivation fallback
        if torque is None and horsepower is not None and rpm > 0:
            torque = (horsepower * TORQUE_HP_CONVERSION) / rpm

        afr_cmd = safe_float(row.get(col_afr_cmd)) if col_afr_cmd else None
        afr_meas = safe_float(row.get(col_afr_meas)) if col_afr_meas else None

        # Measured AFR fallback via lambda
        if afr_invalid(afr_meas):
            lambda_val: Optional[float] = None
            for lc in lambda_cols:
                lambda_value = safe_float(row.get(lc))
                if lambda_value is not None and 0.6 <= lambda_value <= 1.3:
                    lambda_val = lambda_value
                    break
            if lambda_val is not None:
                afr_meas = lambda_val * STOICH_AFR_GASOLINE

        # Commanded AFR fallback via lambda (prefer columns indicating desired/target)
        if afr_invalid(afr_cmd):
            lambda_cmd: Optional[float] = None
            for lc in lambda_cols:
                if any(k in lc for k in ["desired", "target", "cmd"]):
                    lambda_value = safe_float(row.get(lc))
                    if lambda_value is not None and 0.6 <= lambda_value <= 1.3:
                        lambda_cmd = lambda_value
                        break
            if lambda_cmd is not None:
                afr_cmd = lambda_cmd * STOICH_AFR_GASOLINE

        iat = safe_float(row.get(col_iat)) if col_iat else None
        batt = safe_float(row.get(col_batt)) if col_batt else None
        tps = safe_float(row.get(col_tps)) if col_tps else None

        afr_err_pct = None
        if afr_cmd is not None and afr_meas is not None and afr_meas > 0:
            afr_err_pct = (afr_cmd - afr_meas) / afr_meas * 100.0

        # Require torque (derived or original) for weighting acceptance
        if torque is None:
            continue

        recs.append(
            {
                "rpm": rpm,
                "kpa": kpa,
                "tq": torque,
                "hp": horsepower,
                "tps": tps,
                "iat": iat,
                "batt": batt,
                "afr_cmd_f": afr_cmd,
                "afr_cmd_r": afr_cmd,
                "afr_meas_f": afr_meas,
                "afr_meas_r": afr_meas,
                "afr_err_f_pct": afr_err_pct,
                "afr_err_r_pct": afr_err_pct,
                "knock_f": 0.0,
                "knock_r": 0.0,  # Generic format has no knock data
            }
        )
    return recs


def load_winpep_csv(path: str | Path) -> List[Dict[str, Optional[float]]]:
    """Load WinPEP/WinPEP8 CSV or TXT (tab/comma delimited) with header sniffing.

    - Uses csv.Sniffer to detect delimiter (tab, comma, semicolon).
    - Falls back to comma if sniffer fails.
    - Accepts typical WinPEP headers with substring matching.
    """
    # Read a sample for sniffing
    target = io_contracts.safe_path(str(path))
    sample = ""
    try:
        with open(target, "r", newline="", encoding="utf-8-sig") as f:
            sample = f.read(8192)
    except UnicodeDecodeError:
        with open(target, "r", newline="", encoding="cp1252") as f:
            sample = f.read(8192)

    # Detect dialect (delimiter)
    dialect = None
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=",\t;")
    except Exception:
        pass  # fallback to default

    # Now parse file with detected dialect
    with open(target, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, dialect=dialect) if dialect else csv.DictReader(f)
        rows: List[Dict[str, str]] = list(reader)  # raw strings from CSV/TXT
    if not rows:
        raise RuntimeError("Empty WinPEP CSV.")

    headers: List[str] = list(rows[0].keys())

    col_rpm = find_column_by_candidates(headers, ["rpm"])
    col_map = find_column_by_candidates(headers, ["map", "kpa"])
    col_torque = find_column_by_candidates(headers, ["torque"])
    col_afr_cmd_f = find_column_by_candidates(
        headers, ["afr cmd f", "cmd afr f", "afr target f", "commanded afr f"]
    )
    col_afr_cmd_r = find_column_by_candidates(
        headers, ["afr cmd r", "cmd afr r", "afr target r", "commanded afr r"]
    )
    col_afr_meas_f = find_column_by_candidates(
        headers, ["afr meas f", "afr f", "measured afr f", "wb afr f", "o2 f"]
    )
    col_afr_meas_r = find_column_by_candidates(
        headers, ["afr meas r", "afr r", "measured afr r", "wb afr r", "o2 r"]
    )
    col_knock_f = find_column_by_candidates(
        headers, ["knock ret f", "knock f", "spark retard f"]
    )
    col_knock_r = find_column_by_candidates(
        headers, ["knock ret r", "knock r", "spark retard r"]
    )
    col_iat = find_column_by_candidates(headers, ["iat", "intake air"])
    col_batt = find_column_by_candidates(headers, ["battery", "vbatt", "voltage"])
    col_tps = find_column_by_candidates(headers, ["tps", "throttle"])
    col_hp = find_column_by_candidates(
        headers, ["hp", "horsepower"]
    )  # Find horsepower column

    # Performance: Only log if debug level is enabled
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Column mappings: RPM=%s, MAP=%s, Torque=%s, AFR_Cmd_F=%s, AFR_Meas_F=%s, AFR_Cmd_R=%s, AFR_Meas_R=%s, HP=%s",
            col_rpm,
            col_map,
            col_torque,
            col_afr_cmd_f,
            col_afr_meas_f,
            col_afr_cmd_r,
            col_afr_meas_r,
            col_hp,
        )

    # Validate required columns exist
    if not (col_rpm and col_map and col_torque):
        missing: List[str] = []
        if not col_rpm:
            missing.append("RPM")
        if not col_map:
            missing.append("MAP/kPa")
        if not col_torque:
            missing.append("Torque")

        # Get available column names for user reference
        available_cols = (
            ", ".join(f"'{col}'" for col in rows[0].keys()) if rows else "none"
        )

        raise RuntimeError(
            f"Missing required columns in WinPEP CSV: {', '.join(missing)}\n\n"
            f"Available columns: {available_cols}\n\n"
            f"Hint: Column names are matched using substrings (case-insensitive).\n"
            f"For example, 'rpm', 'RPM', 'Engine_RPM' will all match.\n"
            f"Expected column patterns:\n"
            f"  - RPM: 'rpm', 'engine rpm', 'motor rpm'\n"
            f"  - MAP: 'map', 'kpa', 'manifold', 'pressure'\n"
            f"  - Torque: 'torque', 'tq', 'ft-lb'"
        )

    recs: List[Dict[str, Optional[float]]] = []
    for row in rows:
        rpm = safe_float(row.get(col_rpm))
        kpa = safe_float(row.get(col_map))
        torque = safe_float(row.get(col_torque))
        rpm = safe_float(row.get(col_rpm))
        if rpm is None or kpa is None or torque is None:
            continue
        horsepower = safe_float(row.get(col_hp)) if col_hp else None
        afr_cmd_f = safe_float(row.get(col_afr_cmd_f)) if col_afr_cmd_f else None
        afr_cmd_r = safe_float(row.get(col_afr_cmd_r)) if col_afr_cmd_r else None
        afr_meas_f = safe_float(row.get(col_afr_meas_f)) if col_afr_meas_f else None
        afr_meas_r = safe_float(row.get(col_afr_meas_r)) if col_afr_meas_r else None
        knock_f = safe_float(row.get(col_knock_f)) if col_knock_f else None
        knock_r = safe_float(row.get(col_knock_r)) if col_knock_r else None
        iat = safe_float(row.get(col_iat)) if col_iat else None
        batt = safe_float(row.get(col_batt)) if col_batt else None
        tps = safe_float(row.get(col_tps)) if col_tps else None

        afr_err_f_pct = None
        afr_err_r_pct = None
        if afr_cmd_f is not None and afr_meas_f is not None and afr_meas_f > 0:
            afr_err_f_pct = (afr_cmd_f - afr_meas_f) / afr_meas_f * 100.0
        if afr_cmd_r is not None and afr_meas_r is not None and afr_meas_r > 0:
            afr_err_r_pct = (afr_cmd_r - afr_meas_r) / afr_meas_r * 100.0

        recs.append(
            {
                "rpm": rpm,
                "kpa": kpa,
                "tq": torque,
                "hp": horsepower,
                "tps": tps,
                "afr_cmd_f": afr_cmd_f,
                "afr_cmd_r": afr_cmd_r,
                "afr_meas_f": afr_meas_f,
                "afr_meas_r": afr_meas_r,
                "afr_err_f_pct": afr_err_f_pct,
                "afr_err_r_pct": afr_err_r_pct,
                "knock_f": knock_f,
                "knock_r": knock_r,
                "iat": iat,
                "batt": batt,
            }
        )
    return recs


def dyno_bin_aggregate(
    recs: Sequence[Dict[str, Optional[float]]],
    cyl: str = "f",
    use_hp_weight: bool = False,
) -> Tuple[
    List[List[Optional[float]]],  # AFR Error Grid
    List[List[float]],
    List[List[Optional[float]]],
    List[List[int]],
    Dict[str, Any],
    List[List[Optional[float]]],  # Torque Grid
    List[List[Optional[float]]],  # HP Grid
]:
    """
    Aggregate AFR error data by bin with diagnostics.

    Thread-safety: This function is NOT thread-safe. It assumes single-threaded
    execution. If concurrent processing is needed, external synchronization
    (locks, queues) must be used around calls to this function.

    Returns: (grid, knock_max, iat_max, coverage, diagnostics, tq_grid, hp_grid)
    """
    sums: List[List[float]] = [[0.0 for _ in KPA_BINS] for _ in RPM_BINS]
    weights: List[List[float]] = [[0.0 for _ in KPA_BINS] for _ in RPM_BINS]
    tq_sums: List[List[float]] = [[0.0 for _ in KPA_BINS] for _ in RPM_BINS]
    hp_sums: List[List[float]] = [[0.0 for _ in KPA_BINS] for _ in RPM_BINS]
    knock_max: List[List[float]] = [[0.0 for _ in KPA_BINS] for _ in RPM_BINS]
    iat_max: List[List[Optional[float]]] = [[None for _ in KPA_BINS] for _ in RPM_BINS]
    coverage: List[List[int]] = [[0 for _ in KPA_BINS] for _ in RPM_BINS]

    # Per-bin storage for all accepted AFR error values (for MAD calculation)
    bin_values: List[List[List[float]]] = [[[] for _ in KPA_BINS] for _ in RPM_BINS]

    # Diagnostic counters
    diagnostics: Dict[str, Any] = {
        "accepted_wb": 0,
        "temp_out_of_range": 0,
        "map_out_of_range": 0,
        "tps_out_of_range": 0,
        "ve_out_of_range": 0,  # Reserved for future use if VE validation is added
        "bad_afr_or_request_afr": 0,
        "no_requested_afr": 0,
        "total_records_processed": 0,
    }

    # Define reasonable ranges for validation
    IAT_RANGE = (30.0, 300.0)  # Fahrenheit
    MAP_RANGE = (10.0, 110.0)  # kPa
    TPS_RANGE = (0.0, 100.0)  # Percent
    AFR_RANGE = (9.0, 18.0)  # Reasonable AFR range

    afr_err_key = "afr_err_f_pct" if cyl == "f" else "afr_err_r_pct"
    afr_cmd_key = "afr_cmd_f" if cyl == "f" else "afr_cmd_r"
    afr_meas_key = "afr_meas_f" if cyl == "f" else "afr_meas_r"
    knock_key = "knock_f" if cyl == "f" else "knock_r"

    for r in recs:
        diagnostics["total_records_processed"] += 1

        # Check if we have AFR command data
        afr_cmd = r.get(afr_cmd_key)
        if afr_cmd is None:
            diagnostics["no_requested_afr"] += 1
            continue

        afr_err = r.get(afr_err_key)
        afr_meas = r.get(afr_meas_key)

        # Check for bad AFR data
        if afr_err is None or afr_meas is None:
            diagnostics["bad_afr_or_request_afr"] += 1
            continue

        # Validate AFR values are in reasonable range
        if not (AFR_RANGE[0] <= afr_cmd <= AFR_RANGE[1]) or not (
            AFR_RANGE[0] <= afr_meas <= AFR_RANGE[1]
        ):
            diagnostics["bad_afr_or_request_afr"] += 1
            continue

        # Validate temperature (IAT)
        iat = r.get("iat")
        if iat is not None and not (IAT_RANGE[0] <= iat <= IAT_RANGE[1]):
            diagnostics["temp_out_of_range"] += 1
            continue

        # Validate MAP
        kpa = r.get("kpa")
        if kpa is not None and not (MAP_RANGE[0] <= kpa <= MAP_RANGE[1]):
            diagnostics["map_out_of_range"] += 1
            continue

        # Validate TPS
        tps = r.get("tps")
        if tps is not None and not (TPS_RANGE[0] <= tps <= TPS_RANGE[1]):
            diagnostics["tps_out_of_range"] += 1
            continue

        rpm_value = cast(float, r["rpm"])  # ensured non-None by load_winpep_csv
        kpa_value = cast(float, r["kpa"])  # ensured non-None by load_winpep_csv
        rpm_bin = nearest_bin(rpm_value, RPM_BINS)
        kpa_bin = nearest_bin(kpa_value, KPA_BINS)
        # Performance: Use O(1) dict lookup instead of O(n) list.index()
        rpm_index = RPM_INDEX[rpm_bin]
        kpa_index = KPA_INDEX[kpa_bin]

        # Weight by torque or HP to emphasize loaded points; ignore near-zero values
        if use_hp_weight:
            weight = max(0.0, cast(float, r.get("hp", 0.0)))
        else:
            weight = max(0.0, cast(float, r.get("tq", 0.0)))

        if weight < 5.0:
            continue

        # Data accepted!
        diagnostics["accepted_wb"] += 1

        # Performance: Only log if debug level is enabled (avoids string formatting overhead)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "AGG (%s): Accepted row #%d. RPM=%.0f, KPA=%.1f, TQ=%.1f, AFR_Err=%.2f, Weight=%.1f",
                cyl,
                diagnostics["accepted_wb"],
                r["rpm"],
                r["kpa"],
                r["tq"],
                afr_err,
                weight,
            )

        # Log AFR correction decision for first few samples per bin
        if coverage[rpm_index][kpa_index] < 3:
            log_decision(
                action="AFR_CORRECTION",
                reason=f"Accepted AFR error sample for {cyl} cylinder",
                values={
                    "afr_error_pct": round(afr_err, 2),
                    "weight": round(weight, 1),
                    "afr_commanded": round(afr_cmd, 2) if afr_cmd else None,
                    "afr_measured": round(afr_meas, 2) if afr_meas else None,
                },
                cell={"rpm": rpm_bin, "kpa": kpa_bin, "cylinder": cyl},
            )

        assert afr_err is not None
        sums[rpm_index][kpa_index] += afr_err * weight
        weights[rpm_index][kpa_index] += weight

        # Safely add to torque and HP sums
        tq_val = r.get("tq")
        if tq_val is not None:
            tq_sums[rpm_index][kpa_index] += tq_val * weight

        hp_val = r.get("hp")
        if hp_val is not None:
            hp_sums[rpm_index][kpa_index] += hp_val * weight

        coverage[rpm_index][kpa_index] += 1
        bin_values[rpm_index][kpa_index].append(afr_err)

        # Track max knock and max IAT for gating/suggestions
        kret = r.get(knock_key)
        if kret is not None:
            knock_max[rpm_index][kpa_index] = max(knock_max[rpm_index][kpa_index], kret)
        iat = r.get("iat")
        # Safely track the maximum IAT value seen for this cell.
        if iat is not None:
            current_iat = iat_max[rpm_index][kpa_index]
            if current_iat is None or iat > current_iat:
                iat_max[rpm_index][kpa_index] = iat

    grid: List[List[Optional[float]]] = [[None for _ in KPA_BINS] for _ in RPM_BINS]
    tq_grid: List[List[Optional[float]]] = [[None for _ in KPA_BINS] for _ in RPM_BINS]
    hp_grid: List[List[Optional[float]]] = [[None for _ in KPA_BINS] for _ in RPM_BINS]
    mad_grid: List[List[Optional[float]]] = [[None for _ in KPA_BINS] for _ in RPM_BINS]

    for rpm_index in range(len(RPM_BINS)):
        for kpa_index in range(len(KPA_BINS)):
            if weights[rpm_index][kpa_index] > 0.0:
                grid[rpm_index][kpa_index] = (
                    sums[rpm_index][kpa_index] / weights[rpm_index][kpa_index]
                )
                # Only calculate average if sums were populated
                if tq_sums[rpm_index][kpa_index] > 0.0:
                    tq_grid[rpm_index][kpa_index] = (
                        tq_sums[rpm_index][kpa_index] / weights[rpm_index][kpa_index]
                    )
                if hp_sums[rpm_index][kpa_index] > 0.0:
                    hp_grid[rpm_index][kpa_index] = (
                        hp_sums[rpm_index][kpa_index] / weights[rpm_index][kpa_index]
                    )
                # Calculate MAD for this bin
                mad_grid[rpm_index][kpa_index] = mad(bin_values[rpm_index][kpa_index])

    # Add per-bin statistics to diagnostics
    diagnostics["per_bin_stats"] = {"mad": mad_grid, "hits": coverage}

    return grid, knock_max, iat_max, coverage, diagnostics, tq_grid, hp_grid


def grid_map(
    func: Callable[[float], float],
    grid: List[List[Optional[float]]],
) -> List[List[Optional[float]]]:
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    out: List[List[Optional[float]]] = [[None] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            cell = grid[r][c]
            out[r][c] = func(cell) if cell is not None else None
    return out


def clamp_grid(
    grid: List[List[Optional[float]]], limit: float
) -> Tuple[List[List[Optional[float]]], List[Dict[str, Any]]]:
    """Clamp grid values to +/- limit, logging significant clamps.

    Returns:
        Tuple of (clamped_grid, clamped_cells_list)
    """
    log_decision(
        action="CLAMPING_START",
        reason=f"Clamping VE corrections to +/- {limit}%",
        values={"limit": limit},
    )

    # Track clamped cells for logging
    clamped_cells = []
    result = []

    for r_idx, row in enumerate(grid):
        result_row = []
        for c_idx, val in enumerate(row):
            if val is not None:
                original = val
                clamped = clamp(val, -limit, limit)
                result_row.append(clamped)

                # Log if value was actually clamped
                if abs(original - clamped) > 0.01:
                    clamped_cells.append(
                        {
                            "rpm_index": r_idx,
                            "kpa_index": c_idx,
                            "original": round(original, 2),
                            "clamped": round(clamped, 2),
                        }
                    )
            else:
                result_row.append(None)
        result.append(result_row)

    if clamped_cells:
        log_decision(
            action="CLAMPING_APPLIED",
            reason=f"Clamped {len(clamped_cells)} cells exceeding +/- {limit}% limit",
            values={
                "clamped_count": len(clamped_cells),
                "cells": clamped_cells[:10],
            },  # Log first 10
        )

    return result, clamped_cells


def combine_front_rear(
    f_grid: List[List[Optional[float]]], r_grid: List[List[Optional[float]]]
) -> List[List[Optional[float]]]:
    rows = len(f_grid)
    cols = len(f_grid[0]) if rows else 0
    out: List[List[Optional[float]]] = [[None] * cols for _ in range(rows)]
    for row_index in range(rows):
        for col_index in range(cols):
            front_value = f_grid[row_index][col_index]
            rear_value = r_grid[row_index][col_index]
            if front_value is None and rear_value is None:
                out[row_index][col_index] = None
            elif front_value is None:
                out[row_index][col_index] = rear_value
            elif rear_value is None:
                out[row_index][col_index] = front_value
            else:
                out[row_index][col_index] = (front_value + rear_value) / 2.0
    return out


def spark_suggestion(
    knock_grid: Sequence[Sequence[Optional[float]]],
    iat_grid: Sequence[Sequence[Optional[float]]],
) -> List[List[float]]:
    rows = len(knock_grid)
    cols = len(knock_grid[0]) if rows else 0
    out: List[List[float]] = [[0.0] * cols for _ in range(rows)]
    for row_index in range(rows):
        for col_index in range(cols):
            k_val = knock_grid[row_index][col_index]
            knock_value: float = k_val if k_val is not None else 0.0
            iat = iat_grid[row_index][col_index]
            pull = 0.0
            if knock_value >= 0.5:
                pull = -min(2.0, max(0.5, (knock_value / 3.0) * 2.0))
            if iat is not None and iat >= HOT_IAT_THRESHOLD_F and pull < 0.0:
                pull -= 0.5
            out[row_index][col_index] = pull
    return out


def enforce_rear_rule(
    spark_grid: List[List[float]],
    extra_rule_deg: float = 2.0,
    hot_extra: float = -1.0,
    iat_grid: Optional[List[List[Optional[float]]]] = None,
) -> List[List[float]]:
    for ri, rpm in enumerate(RPM_BINS):
        if 2800 <= rpm <= 3600:
            for ki, kpa in enumerate(KPA_BINS):
                if 75 <= kpa <= 95:
                    base = -abs(extra_rule_deg)
                    spark_grid[ri][ki] = spark_grid[ri][ki] + base
                    if iat_grid is not None:
                        iat = iat_grid[ri][ki]
                        if iat is not None and iat >= HOT_IAT_THRESHOLD_F:
                            spark_grid[ri][ki] += hot_extra  # negative
    return spark_grid


def apply_delta_to_base(
    base_grid: List[List[Optional[float]]],
    delta_grid: List[List[Optional[float]]],
) -> List[List[Optional[float]]]:
    rows = len(base_grid)
    cols = len(base_grid[0]) if rows else 0
    out: List[List[Optional[float]]] = [[None] * cols for _ in range(rows)]
    for row_index in range(rows):
        for col_index in range(cols):
            base_value = base_grid[row_index][col_index]
            delta_value = delta_grid[row_index][col_index]
            if base_value is None:
                out[row_index][col_index] = None
            elif delta_value is None:
                out[row_index][col_index] = base_value
            else:
                out[row_index][col_index] = base_value * (1.0 + delta_value / 100.0)
    return out


def read_grid_csv(path: str | Path) -> List[List[Optional[float]]]:
    target = io_contracts.safe_path(str(path))
    with open(target, newline="") as f:
        reader = csv.reader(f)
        rows: List[List[str]] = list(reader)
    if not rows:
        raise RuntimeError(f"{target} is empty.")
    hdr = [h.strip() for h in rows[0]]
    if len(hdr) < 6 or hdr[0].lower() != "rpm":
        raise RuntimeError(f"{target} missing RPM header row")
    kpa = [int(float(x)) for x in hdr[1:6]]
    if kpa != KPA_BINS:
        raise RuntimeError(f"{target} MAP bins {kpa} != expected {KPA_BINS}")
    grid: List[List[Optional[float]]] = [
        [None] * len(KPA_BINS) for _ in range(len(RPM_BINS))
    ]
    for row in rows[1:]:
        if not row:
            continue
        rpm = int(float(row[0]))
        if rpm not in RPM_INDEX:
            continue
        # Performance: Use O(1) dict lookup instead of O(n) list.index()
        rpm_index = RPM_INDEX[rpm]
        for j in range(1, 6):
            cell = row[j].strip() if j < len(row) else ""
            if cell == "":
                grid[rpm_index][j - 1] = None
            else:
                grid[rpm_index][j - 1] = float(cell)
    return grid


def coverage_csv(path: str | Path, coverage: List[List[int]]) -> None:
    target = io_contracts.safe_path(str(path))
    with open(target, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["RPM"] + [sanitize_csv_cell(k) for k in KPA_BINS])
        for rpm_index, rpm in enumerate(RPM_BINS):
            row = [sanitize_csv_cell(rpm)] + [
                sanitize_csv_cell(coverage[rpm_index][kpa_index])
                for kpa_index in range(len(KPA_BINS))
            ]
            writer.writerow(row)


# --- Anomaly detection helpers ---


def robust_stats(values: Sequence[Optional[float]]) -> Tuple[Optional[float], float]:
    vals: List[float] = [float(v) for v in values if v is not None]
    if not vals:
        return None, 1e-6
    vals_sorted: List[float] = sorted(vals)
    count = len(vals_sorted)
    median: float = (
        vals_sorted[count // 2]
        if count % 2 == 1
        else 0.5 * (vals_sorted[count // 2 - 1] + vals_sorted[count // 2])
    )
    # MAD
    dev: List[float] = [abs(v - median) for v in vals_sorted]
    dev_sorted: List[float] = sorted(dev)
    mad_val: float = (
        dev_sorted[count // 2]
        if count % 2 == 1
        else 0.5 * (dev_sorted[count // 2 - 1] + dev_sorted[count // 2])
    )
    return median, mad_val if mad_val > 0 else 1e-6


def robust_z_grid(grid: List[List[Optional[float]]]) -> List[List[Optional[float]]]:
    vals: List[float] = [float(v) for row in grid for v in row if v is not None]
    if not vals:
        return [[None for _ in row] for row in grid]
    med, mad = robust_stats(vals)
    out: List[List[Optional[float]]] = []
    for row in grid:
        out_row: List[Optional[float]] = []
        for value in row:
            if value is None or med is None:
                out_row.append(None)
            else:
                z_score = 0.6745 * (value - med) / mad
                out_row.append(z_score)
        out.append(out_row)
    return out


def spatial_roughness(grid: List[List[Optional[float]]]) -> List[List[Optional[float]]]:
    # Laplacian-like magnitude |cell - avg(neighbors)|
    rows: int = len(grid)
    cols: int = len(grid[0]) if rows else 0
    rough: List[List[Optional[float]]] = [[None] * cols for _ in range(rows)]
    for row_index in range(rows):
        for col_index in range(cols):
            cell_value: Optional[float] = grid[row_index][col_index]
            if cell_value is None:
                rough[row_index][col_index] = None
                continue
            neigh: List[float] = []
            if row_index > 0:
                up = grid[row_index - 1][col_index]
                if up is not None:
                    neigh.append(up)
            if row_index < rows - 1:
                down = grid[row_index + 1][col_index]
                if down is not None:
                    neigh.append(down)
            if col_index > 0:
                left = grid[row_index][col_index - 1]
                if left is not None:
                    neigh.append(left)
            if col_index < cols - 1:
                right = grid[row_index][col_index + 1]
                if right is not None:
                    neigh.append(right)
            if not neigh:
                rough[row_index][col_index] = 0.0
            else:
                rough[row_index][col_index] = abs(
                    cell_value - (sum(neigh) / len(neigh))
                )
    return rough


def avg_band(
    grid: List[List[Optional[float]]],
    rpm_lo: int,
    rpm_hi: int,
    kpa_lo: int,
    kpa_hi: int,
) -> Optional[float]:
    vals: List[Optional[float]] = []
    for ri, rpm in enumerate(RPM_BINS):
        if rpm_lo <= rpm <= rpm_hi:
            for ki, kpa in enumerate(KPA_BINS):
                if kpa_lo <= kpa <= kpa_hi:
                    v: Optional[float] = grid[ri][ki]
                    if v is not None:
                        vals.append(v)
    return mean(vals)


def anomaly_diagnostics(
    recs: Sequence[Dict[str, Optional[float]]],
    afr_err_f: List[List[Optional[float]]],
    afr_err_r: List[List[Optional[float]]],
    ve_delta_grid: List[List[Optional[float]]],
    knock_f: List[List[float]],
    iat_f: List[List[Optional[float]]],
    knock_r: List[List[float]],
    iat_r: List[List[Optional[float]]],
    coverage: List[List[int]],
) -> List[Dict[str, Any]]:
    log_decision(
        action="ANOMALY_DETECTION_START",
        reason="Starting anomaly detection analysis",
    )

    anomalies: List[Dict[str, Any]] = []

    # 1) Spatial discontinuity
    rough = spatial_roughness(ve_delta_grid)
    # robust z on roughness values
    rough_vals: List[float] = [float(v) for row in rough for v in row if v is not None]
    if rough_vals:
        med, mad = robust_stats(rough_vals)
        # Median should be defined when rough_vals is non-empty
        assert med is not None
        for rpm_index, rpm in enumerate(RPM_BINS):
            for kpa_index, kpa in enumerate(KPA_BINS):
                roughness_value = rough[rpm_index][kpa_index]
                if roughness_value is None:
                    continue
                z_score = 0.6745 * (roughness_value - med) / mad if mad > 0 else 0.0
                if z_score > 3.5 and coverage[rpm_index][kpa_index] > 0:
                    anomaly = {
                        "type": "Spatial discontinuity",
                        "score": float(z_score),
                        "cell": {"rpm": rpm, "kpa": kpa},
                        "explanation": "Large VE change vs neighbors; could be data artifact or real airflow quirk.",
                        "next_checks": [
                            "Re-run steady-state in this cell",
                            "Inspect for vacuum leaks, throttle sync, or sensor noise",
                        ],
                    }
                    anomalies.append(anomaly)

                    log_decision(
                        action="ANOMALY_DETECTED",
                        reason=anomaly["explanation"],
                        values={"type": anomaly["type"], "score": anomaly["score"]},
                        cell={"rpm": rpm, "kpa": kpa},
                    )

    # 2) Rear vs Front bias in mid band
    diff_grid: List[List[Optional[float]]] = [
        [None] * len(KPA_BINS) for _ in range(len(RPM_BINS))
    ]
    for rpm_index in range(len(RPM_BINS)):
        for kpa_index in range(len(KPA_BINS)):
            front_value = afr_err_f[rpm_index][kpa_index]
            rear = afr_err_r[rpm_index][kpa_index]
            diff_grid[rpm_index][kpa_index] = (
                None if front_value is None or rear is None else (rear - front_value)
            )
    mid_diff = avg_band(diff_grid, 2500, 3800, 65, 95)
    if mid_diff is not None and abs(mid_diff) >= 3.0:
        anomalies.append(
            {
                "type": "Cylinder fueling imbalance",
                "score": float(abs(mid_diff)),
                "cell_band": {"rpm": [2500, 3800], "kpa": [65, 95]},
                "explanation": f"Rear minus front AFR error ~ {mid_diff:+.1f}% in mid band; suggests rear needs VE bias or injector variance.",
                "next_checks": [
                    "Flow test injectors",
                    "Apply rear VE bias 2–3% then retest",
                    "Check exhaust leaks near rear sensor",
                ],
            }
        )

    # 3) Low-MAP lean only
    lowmap = avg_band(combine_front_rear(afr_err_f, afr_err_r), 1500, 2500, 35, 50)
    midmap = avg_band(combine_front_rear(afr_err_f, afr_err_r), 2500, 3500, 65, 80)
    if lowmap is not None and midmap is not None and (lowmap - midmap) >= 4.0:
        anomalies.append(
            {
                "type": "Possible exhaust leak (low MAP bias)",
                "score": float(lowmap - midmap),
                "cell_band": {"rpm": [1500, 2500], "kpa": [35, 50]},
                "explanation": "Lean bias at low MAP not seen at higher load suggests O2 contamination/leak upstream.",
                "next_checks": [
                    "Smoke test exhaust joints",
                    "Check O2 bung welds",
                    "Use TT sensor condition test in ambient air",
                ],
            }
        )

    # 4) Knock + Hot IAT cluster
    hot_knock_cells: List[Dict[str, Any]] = []
    for ri, rpm in enumerate(RPM_BINS):
        for ki, kpa in enumerate(KPA_BINS):
            if (knock_f[ri][ki] and knock_f[ri][ki] >= 1.5) or (
                knock_r[ri][ki] and knock_r[ri][ki] >= 1.5
            ):
                hot = False
                iatf = iat_f[ri][ki]
                iatr = iat_r[ri][ki]
                if (iatf is not None and iatf >= 120) or (
                    iatr is not None and iatr >= 120
                ):
                    hot = True
                hot_knock_cells.append(
                    {"rpm": RPM_BINS[ri], "kpa": KPA_BINS[ki], "hot": hot}
                )
    if hot_knock_cells:
        anomalies.append(
            {
                "type": "Knock cluster",
                "score": float(len(hot_knock_cells)),
                "cells": hot_knock_cells[:10],
                "explanation": "Knock retard ≥1.5° observed; hotter cells likely need richer AFR and/or timing pull.",
                "next_checks": [
                    "Richen 0.1–0.2 λ eq. in affected cells",
                    "Pull 1–2° timing; validate",
                ],
            }
        )

    # 5) Battery correlation
    # Build arrays of (afr_err, batt) during positive torque
    afr_errs: List[float] = []
    batts: List[float] = []
    for rec in recs:
        if rec["tq"] is not None and rec["tq"] > 5.0 and rec["batt"] is not None:
            # combine f/r errors if present
            if rec["afr_err_f_pct"] is not None:
                afr_errs.append(rec["afr_err_f_pct"])
                batts.append(rec["batt"])
            if rec["afr_err_r_pct"] is not None:
                afr_errs.append(rec["afr_err_r_pct"])
                batts.append(rec["batt"])
    if len(afr_errs) >= 10:
        # Pearson correlation
        mean_afr_error = sum(afr_errs) / len(afr_errs)
        mean_battery = sum(batts) / len(batts)
        num = sum(
            (x - mean_afr_error) * (y - mean_battery) for x, y in zip(afr_errs, batts)
        )
        denx = math.sqrt(sum((x - mean_afr_error) ** 2 for x in afr_errs))
        deny = math.sqrt(sum((y - mean_battery) ** 2 for y in batts))
        corr = num / (denx * deny) if denx > 0 and deny > 0 else 0.0
        if corr <= -0.4:  # lower volts -> more error
            anomalies.append(
                {
                    "type": "Electrical supply correlation",
                    "score": float(abs(corr)),
                    "explanation": f"AFR error correlates with low battery voltage (r={corr:+.2f}); injector latency or pump voltage sag may bias fueling.",
                    "next_checks": [
                        "Log battery voltage under load",
                        "Check grounds/charging",
                        "Compensate injector offset if supported",
                    ],
                }
            )

    return anomalies


def find_power_opportunities(
    afr_err_f: List[List[Optional[float]]],
    afr_err_r: List[List[Optional[float]]],
    spark_f: List[List[float]],
    spark_r: List[List[float]],
    coverage_f: List[List[int]],
    coverage_r: List[List[int]],
    knock_f: List[List[float]],
    knock_r: List[List[float]],
    hp_grid: List[List[Optional[float]]],
) -> List[Dict[str, Any]]:
    """
    Analyze tuning data to identify safe opportunities for power gains.

    Looks for:
    1. Cells that are >2% rich with good coverage (>20 hits)
    2. Cells where spark timing could be advanced safely (no knock)
    3. Areas where VE could be increased without exceeding AFR targets

    Returns prioritized list of opportunities with specific suggestions.

    Args:
        afr_err_f: Front AFR error grid (% rich/lean)
        afr_err_r: Rear AFR error grid (% rich/lean)
        spark_f: Front spark suggestions (degrees)
        spark_r: Rear spark suggestions (degrees)
        coverage_f: Front coverage (hit count per cell)
        coverage_r: Rear coverage (hit count per cell)
        knock_f: Front knock retard grid (degrees)
        knock_r: Rear knock retard grid (degrees)
        hp_grid: Combined horsepower grid

    Returns:
        List of power opportunities sorted by estimated gain (highest first)
    """
    opportunities: List[Dict[str, Any]] = []

    # Minimum coverage threshold for confident suggestions
    MIN_COVERAGE = 20

    # Safety limits
    MAX_AFR_CHANGE_PCT = 3.0  # Don't suggest more than ±3% AFR change
    MAX_TIMING_ADVANCE_DEG = 2.0  # Max 2° timing advance per suggestion
    KNOCK_THRESHOLD = 0.5  # Don't suggest changes where knock >= 0.5°

    # Rich threshold - cells richer than this are power opportunities
    RICH_THRESHOLD_PCT = 2.0

    for ri, rpm in enumerate(RPM_BINS):
        for ki, kpa in enumerate(KPA_BINS):
            # Combine front and rear data
            afr_err_front = afr_err_f[ri][ki]
            afr_err_rear = afr_err_r[ri][ki]
            coverage_total = coverage_f[ri][ki] + coverage_r[ri][ki]
            knock_front = knock_f[ri][ki]
            knock_rear = knock_r[ri][ki]
            spark_suggest_f = spark_f[ri][ki]
            spark_suggest_r = spark_r[ri][ki]
            hp_current = hp_grid[ri][ki]

            # Skip cells with insufficient coverage
            if coverage_total < MIN_COVERAGE:
                continue

            # Skip cells with knock activity (not safe to advance timing or lean out)
            if knock_front >= KNOCK_THRESHOLD or knock_rear >= KNOCK_THRESHOLD:
                continue

            # Calculate average AFR error (positive = rich, negative = lean)
            afr_errors = [e for e in [afr_err_front, afr_err_rear] if e is not None]
            if not afr_errors:
                continue

            avg_afr_err = sum(afr_errors) / len(afr_errors)

            # Calculate confidence based on coverage
            confidence = min(100, int((coverage_total / 50) * 100))

            # Opportunity 1: Rich cells - can lean out for more power
            if avg_afr_err > RICH_THRESHOLD_PCT:
                # Suggest leaning by up to 50% of the error, capped at MAX_AFR_CHANGE_PCT
                lean_suggestion = min(avg_afr_err * 0.5, MAX_AFR_CHANGE_PCT)

                # Estimate power gain: ~2% HP per 1% leaner AFR (conservative)
                # Only apply to cells with actual HP data
                if hp_current is not None and hp_current > 0:
                    estimated_hp_gain = hp_current * (lean_suggestion * 0.02)
                else:
                    # Estimate based on typical HP for this RPM/load
                    estimated_hp_gain = (
                        (rpm / 1000) * (kpa / 100) * lean_suggestion * 0.5
                    )

                opportunities.append(
                    {
                        "type": "Lean AFR",
                        "rpm": rpm,
                        "kpa": kpa,
                        "suggestion": f"Lean by {lean_suggestion:.1f}% (currently {avg_afr_err:+.1f}% rich)",
                        "estimated_gain_hp": round(estimated_hp_gain, 2),
                        "confidence": confidence,
                        "coverage": coverage_total,
                        "current_hp": round(hp_current, 1) if hp_current else None,
                        "details": {
                            "afr_error_pct": round(avg_afr_err, 2),
                            "suggested_change_pct": round(
                                -lean_suggestion, 2
                            ),  # Negative = lean
                            "knock_front": round(knock_front, 2),
                            "knock_rear": round(knock_rear, 2),
                        },
                    }
                )

            # Opportunity 2: Timing advance potential (no knock, not already suggested to advance)
            # If spark suggestion is 0 or slightly negative but no knock, there's room to advance
            avg_spark_suggest = (spark_suggest_f + spark_suggest_r) / 2.0

            if avg_spark_suggest <= 0 and knock_front < 0.1 and knock_rear < 0.1:
                # Suggest conservative timing advance
                timing_advance = min(MAX_TIMING_ADVANCE_DEG, 2.0)

                # Estimate power gain: ~3% HP per degree of advance (conservative)
                if hp_current is not None and hp_current > 0:
                    estimated_hp_gain = hp_current * (timing_advance * 0.03)
                else:
                    estimated_hp_gain = (
                        (rpm / 1000) * (kpa / 100) * timing_advance * 0.8
                    )

                opportunities.append(
                    {
                        "type": "Advance Timing",
                        "rpm": rpm,
                        "kpa": kpa,
                        "suggestion": f"Advance timing by {timing_advance:.1f}° (no knock detected)",
                        "estimated_gain_hp": round(estimated_hp_gain, 2),
                        "confidence": confidence,
                        "coverage": coverage_total,
                        "current_hp": round(hp_current, 1) if hp_current else None,
                        "details": {
                            "current_suggestion_deg": round(avg_spark_suggest, 2),
                            "advance_deg": round(timing_advance, 2),
                            "knock_front": round(knock_front, 2),
                            "knock_rear": round(knock_rear, 2),
                        },
                    }
                )

            # Opportunity 3: Combined opportunity (rich + no knock = lean AND advance)
            if (
                avg_afr_err > RICH_THRESHOLD_PCT
                and knock_front < 0.1
                and knock_rear < 0.1
            ):
                lean_suggestion = min(avg_afr_err * 0.5, MAX_AFR_CHANGE_PCT)
                timing_advance = min(
                    MAX_TIMING_ADVANCE_DEG, 1.5
                )  # More conservative when combining

                # Combined gains are multiplicative (but use conservative estimate)
                if hp_current is not None and hp_current > 0:
                    afr_gain = hp_current * (lean_suggestion * 0.02)
                    timing_gain = hp_current * (timing_advance * 0.03)
                    estimated_hp_gain = (
                        afr_gain + timing_gain * 0.8
                    )  # Reduce timing gain when combined
                else:
                    estimated_hp_gain = (
                        (rpm / 1000) * (kpa / 100) * (lean_suggestion + timing_advance)
                    )

                opportunities.append(
                    {
                        "type": "Combined (AFR + Timing)",
                        "rpm": rpm,
                        "kpa": kpa,
                        "suggestion": f"Lean by {lean_suggestion:.1f}% AND advance {timing_advance:.1f}°",
                        "estimated_gain_hp": round(estimated_hp_gain, 2),
                        "confidence": confidence,
                        "coverage": coverage_total,
                        "current_hp": round(hp_current, 1) if hp_current else None,
                        "details": {
                            "afr_error_pct": round(avg_afr_err, 2),
                            "suggested_afr_change_pct": round(-lean_suggestion, 2),
                            "advance_deg": round(timing_advance, 2),
                            "knock_front": round(knock_front, 2),
                            "knock_rear": round(knock_rear, 2),
                        },
                    }
                )

    # Sort by estimated HP gain (highest first)
    opportunities.sort(key=lambda x: x["estimated_gain_hp"], reverse=True)

    # Return top 10 opportunities
    return opportunities[:10]


def write_session_replay(outdir: str | Path, run_id: str) -> None:
    """Write session replay log to JSON file.

    Args:
        outdir: Output directory path
        run_id: Run identifier for the session
    """
    safe_outdir = io_contracts.safe_path(str(outdir))
    session_log = get_session_log()

    replay_data = {
        "schema_version": "1.0",
        "run_id": run_id,
        "generated_at": io_contracts.utc_now_iso(),
        "total_decisions": len(session_log),
        "decisions": session_log,
    }

    replay_path = safe_outdir / "session_replay.json"
    with open(replay_path, "w", encoding="utf-8") as f:
        json.dump(replay_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Session replay log written: {len(session_log)} decisions logged")


def calculate_tune_confidence(
    coverage_f: List[List[int]],
    coverage_r: List[List[int]],
    mad_grid_f: List[List[Optional[float]]],
    mad_grid_r: List[List[Optional[float]]],
    anomalies: Sequence[Dict[str, Any]],
    clamped_cells_f: List[Dict[str, Any]],
    clamped_cells_r: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Calculate comprehensive tune confidence score based on coverage, consistency, and quality.

    Returns a confidence report with:
    - Overall score (0-100%)
    - Letter grade (A/B/C/D)
    - Breakdown by area (idle, cruise, WOT)
    - Specific recommendations for improvement

    Completes in <100ms using only pre-calculated data.
    """
    import time

    start_time = time.perf_counter()

    log_decision(
        action="CONFIDENCE_SCORING_START",
        reason="Calculating tune confidence metrics",
    )

    # Define operating regions
    regions = {
        "idle": {"rpm_range": (1000, 2000), "kpa_range": (20, 40)},
        "cruise": {"rpm_range": (2000, 3500), "kpa_range": (40, 70)},
        "wot": {"rpm_range": (3000, 6500), "kpa_range": (85, 105)},
    }

    total_cells = len(RPM_BINS) * len(KPA_BINS)

    # 1. COVERAGE ANALYSIS (40% of score)
    coverage_threshold = 10  # Minimum hits for "good" coverage
    well_covered_cells = 0
    coverage_by_region: Dict[str, Dict[str, int]] = {}

    for region_name, bounds in regions.items():
        region_total = 0
        region_covered = 0

        for ri, rpm in enumerate(RPM_BINS):
            for ki, kpa in enumerate(KPA_BINS):
                if (
                    bounds["rpm_range"][0] <= rpm <= bounds["rpm_range"][1]
                    and bounds["kpa_range"][0] <= kpa <= bounds["kpa_range"][1]
                ):
                    region_total += 1
                    hits = coverage_f[ri][ki] + coverage_r[ri][ki]
                    if hits >= coverage_threshold:
                        region_covered += 1

        coverage_by_region[region_name] = {
            "total": region_total,
            "covered": region_covered,
            "percentage": (
                (region_covered / region_total * 100) if region_total > 0 else 0
            ),
        }

    # Overall coverage
    for ri in range(len(RPM_BINS)):
        for ki in range(len(KPA_BINS)):
            hits = coverage_f[ri][ki] + coverage_r[ri][ki]
            if hits >= coverage_threshold:
                well_covered_cells += 1

    coverage_percentage = (well_covered_cells / total_cells) * 100
    coverage_score = min(
        100, coverage_percentage * 1.2
    )  # Boost to make 85% coverage = 100 points

    # 2. CONSISTENCY ANALYSIS (30% of score)
    # Lower MAD = better consistency
    mad_values: List[float] = []
    mad_by_region: Dict[str, List[float]] = {region: [] for region in regions}

    for ri, rpm in enumerate(RPM_BINS):
        for ki, kpa in enumerate(KPA_BINS):
            # Combine front and rear MAD values
            for mad_grid in [mad_grid_f, mad_grid_r]:
                mad_val = mad_grid[ri][ki]
                if mad_val is not None and mad_val > 0:
                    mad_values.append(mad_val)

                    # Categorize by region
                    for region_name, bounds in regions.items():
                        if (
                            bounds["rpm_range"][0] <= rpm <= bounds["rpm_range"][1]
                            and bounds["kpa_range"][0] <= kpa <= bounds["kpa_range"][1]
                        ):
                            mad_by_region[region_name].append(mad_val)

    avg_mad = sum(mad_values) / len(mad_values) if mad_values else 0.0

    # Score consistency: MAD < 0.5 = excellent, MAD > 2.0 = poor
    if avg_mad < 0.5:
        consistency_score = 100
    elif avg_mad < 1.0:
        consistency_score = 90 - (avg_mad - 0.5) * 40  # 90 to 70
    elif avg_mad < 2.0:
        consistency_score = 70 - (avg_mad - 1.0) * 40  # 70 to 30
    else:
        consistency_score = max(0, 30 - (avg_mad - 2.0) * 15)

    # 3. ANOMALY IMPACT (15% of score)
    anomaly_count = len(anomalies)
    high_severity_anomalies = sum(1 for a in anomalies if a.get("score", 0) > 3.0)

    if anomaly_count == 0:
        anomaly_score = 100
    elif anomaly_count <= 2:
        anomaly_score = 85
    elif anomaly_count <= 5:
        anomaly_score = 70
    else:
        anomaly_score = max(0, 70 - (anomaly_count - 5) * 10)

    # Penalize high-severity anomalies more
    anomaly_score = max(0, anomaly_score - (high_severity_anomalies * 10))

    # 4. CLAMPING ANALYSIS (15% of score)
    total_clamped = len(clamped_cells_f) + len(clamped_cells_r)
    clamp_percentage = (total_clamped / total_cells) * 100

    if clamp_percentage == 0:
        clamp_score = 100
    elif clamp_percentage < 5:
        clamp_score = 90
    elif clamp_percentage < 10:
        clamp_score = 75
    elif clamp_percentage < 20:
        clamp_score = 50
    else:
        clamp_score = max(0, 50 - (clamp_percentage - 20) * 2)

    # CALCULATE OVERALL SCORE
    overall_score = (
        coverage_score * 0.40
        + consistency_score * 0.30
        + anomaly_score * 0.15
        + clamp_score * 0.15
    )

    # ASSIGN LETTER GRADE
    if overall_score >= 85:
        letter_grade = "A"
        grade_description = "Excellent - Ready for deployment"
    elif overall_score >= 70:
        letter_grade = "B"
        grade_description = "Good - Minor improvements recommended"
    elif overall_score >= 50:
        letter_grade = "C"
        grade_description = "Fair - Additional data collection needed"
    else:
        letter_grade = "D"
        grade_description = "Poor - Significant issues require attention"

    # GENERATE RECOMMENDATIONS
    recommendations: List[str] = []
    weak_areas: List[str] = []

    # Coverage recommendations
    if coverage_percentage < 60:
        recommendations.append(
            f"Collect more data: Only {coverage_percentage:.1f}% of cells have sufficient data (≥{coverage_threshold} hits)"
        )
        for region_name, stats in coverage_by_region.items():
            if stats["percentage"] < 50:
                weak_areas.append(f"{region_name} ({stats['percentage']:.0f}% covered)")

        if weak_areas:
            recommendations.append(f"Focus data collection on: {', '.join(weak_areas)}")

    # Consistency recommendations
    if avg_mad > 1.5:
        recommendations.append(
            f"Data consistency is poor (MAD={avg_mad:.2f}). Check for mechanical issues, sensor problems, or unstable operating conditions."
        )

        # Identify regions with worst consistency
        worst_regions = []
        for region_name, mad_vals in mad_by_region.items():
            if mad_vals:
                region_avg_mad = sum(mad_vals) / len(mad_vals)
                if region_avg_mad > 2.0:
                    worst_regions.append(f"{region_name} (MAD={region_avg_mad:.2f})")

        if worst_regions:
            recommendations.append(f"Worst consistency in: {', '.join(worst_regions)}")

    # Clamping recommendations
    if clamp_percentage > 10:
        recommendations.append(
            f"{clamp_percentage:.1f}% of corrections hit clamp limits. Consider increasing clamp limits or investigating root causes."
        )

    # Anomaly recommendations
    if high_severity_anomalies > 0:
        recommendations.append(
            f"{high_severity_anomalies} high-severity anomalies detected. Review Anomaly_Hypotheses.json for details."
        )

    # Success message if score is high
    if overall_score >= 85 and not recommendations:
        recommendations.append(
            "Tune quality is excellent. No major improvements needed."
        )

    # Calculate region-specific MAD averages
    region_mad_avg = {}
    for region_name, mad_vals in mad_by_region.items():
        region_mad_avg[region_name] = sum(mad_vals) / len(mad_vals) if mad_vals else 0.0

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    log_decision(
        action="CONFIDENCE_SCORING_COMPLETE",
        reason=f"Confidence score calculated: {overall_score:.1f}% (Grade {letter_grade})",
        values={
            "overall_score": round(overall_score, 1),
            "letter_grade": letter_grade,
            "elapsed_ms": round(elapsed_ms, 2),
        },
    )

    return {
        "overall_score": round(overall_score, 1),
        "letter_grade": letter_grade,
        "grade_description": grade_description,
        "component_scores": {
            "coverage": {
                "score": round(coverage_score, 1),
                "weight": "40%",
                "details": {
                    "well_covered_cells": well_covered_cells,
                    "total_cells": total_cells,
                    "coverage_percentage": round(coverage_percentage, 1),
                    "threshold_hits": coverage_threshold,
                },
            },
            "consistency": {
                "score": round(consistency_score, 1),
                "weight": "30%",
                "details": {
                    "average_mad": round(avg_mad, 3),
                    "mad_samples": len(mad_values),
                },
            },
            "anomalies": {
                "score": round(anomaly_score, 1),
                "weight": "15%",
                "details": {
                    "total_anomalies": anomaly_count,
                    "high_severity": high_severity_anomalies,
                },
            },
            "clamping": {
                "score": round(clamp_score, 1),
                "weight": "15%",
                "details": {
                    "clamped_cells": total_clamped,
                    "clamp_percentage": round(clamp_percentage, 1),
                },
            },
        },
        "region_breakdown": {
            region_name: {
                "coverage_percentage": round(stats["percentage"], 1),
                "cells_covered": stats["covered"],
                "cells_total": stats["total"],
                "average_mad": round(region_mad_avg.get(region_name, 0.0), 3),
            }
            for region_name, stats in coverage_by_region.items()
        },
        "recommendations": recommendations,
        "weak_areas": weak_areas,
        "performance": {
            "calculation_time_ms": round(elapsed_ms, 2),
        },
        "methodology": {
            "description": "Confidence score based on weighted combination of coverage, consistency, anomalies, and clamping",
            "weights": {
                "coverage": "40% - Cells with ≥10 hits",
                "consistency": "30% - Average MAD (lower is better)",
                "anomalies": "15% - Detected issues",
                "clamping": "15% - Corrections hitting limits",
            },
            "grading_scale": {
                "A": "≥85% - Excellent",
                "B": "70-85% - Good",
                "C": "50-70% - Fair",
                "D": "<50% - Poor",
            },
        },
    }


def write_diagnostics(
    outdir: str | Path,
    anomalies: Sequence[Dict[str, Any]],
    correction_diagnostics: Optional[Dict[str, Dict[str, Any]]] = None,
    confidence_report: Optional[Dict[str, Any]] = None,
) -> None:
    # Human-readable
    lines: List[str] = []
    lines.append("Dyno AI Tuner v1.2 Diagnostics")
    lines.append("")

    # Add confidence report if provided
    if confidence_report:
        lines.append("=" * 60)
        lines.append("=== TUNE CONFIDENCE SCORE ===")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Overall Score: {confidence_report['overall_score']}%")
        lines.append(
            f"Letter Grade: {confidence_report['letter_grade']} - {confidence_report['grade_description']}"
        )
        lines.append("")

        lines.append("Component Scores:")
        for component, data in confidence_report["component_scores"].items():
            lines.append(
                f"  {component.upper()}: {data['score']:.1f}% (weight: {data['weight']})"
            )
            for key, value in data["details"].items():
                lines.append(f"    - {key}: {value}")
        lines.append("")

        lines.append("Region Breakdown:")
        for region, data in confidence_report["region_breakdown"].items():
            lines.append(f"  {region.upper()}:")
            lines.append(
                f"    Coverage: {data['coverage_percentage']:.1f}% ({data['cells_covered']}/{data['cells_total']} cells)"
            )
            lines.append(f"    Avg MAD: {data['average_mad']:.3f}")
        lines.append("")

        if confidence_report["recommendations"]:
            lines.append("RECOMMENDATIONS:")
            for i, rec in enumerate(confidence_report["recommendations"], 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")

        if confidence_report["weak_areas"]:
            lines.append("WEAK AREAS NEEDING MORE DATA:")
            for area in confidence_report["weak_areas"]:
                lines.append(f"  - {area}")
            lines.append("")

        lines.append(
            f"Calculation time: {confidence_report['performance']['calculation_time_ms']:.2f} ms"
        )
        lines.append("")
        lines.append("=" * 60)
        lines.append("")

    # Add correction diagnostics if provided
    if correction_diagnostics:
        lines.append("=== AFR Correction Data Quality ===")
        lines.append("")
        for cyl in ["front", "rear"]:
            if cyl in correction_diagnostics:
                diag: Dict[str, Any] = correction_diagnostics[cyl]
                lines.append(f"{cyl.upper()} CYLINDER:")
                lines.append(
                    f"  Total records processed: {diag.get('total_records_processed', 0)}"
                )
                lines.append(f"  Accepted WB records: {diag.get('accepted_wb', 0)}")
                lines.append(f"  No requested AFR: {diag.get('no_requested_afr', 0)}")
                lines.append(
                    f"  Bad AFR or request AFR: {diag.get('bad_afr_or_request_afr', 0)}"
                )
                lines.append(f"  Temp out of range: {diag.get('temp_out_of_range', 0)}")
                lines.append(f"  MAP out of range: {diag.get('map_out_of_range', 0)}")
                lines.append(f"  TPS out of range: {diag.get('tps_out_of_range', 0)}")
                lines.append(f"  VE out of range: {diag.get('ve_out_of_range', 0)}")
                lines.append("")
        lines.append("")

    lines.append("=== Anomaly Detection ===")
    lines.append("")
    if not anomalies:
        lines.append("No strong anomalies detected under current data/thresholds.")
    else:
        for i, anomaly_raw in enumerate(anomalies, 1):
            anomaly = anomaly_raw  # No need to cast if types are correct
            lines.append(
                f"{i}. [{anomaly.get('type', '')}] score={anomaly.get('score', '')}"
            )
            cell = cast(Optional[Dict[str, Any]], anomaly.get("cell"))
            if cell is not None:
                lines.append(f"   cell: RPM {cell.get('rpm')} / {cell.get('kpa')} kPa")
            cell_band = cast(Optional[Dict[str, Any]], anomaly.get("cell_band"))
            if cell_band is not None:
                lines.append(
                    f"   band: RPM {cell_band.get('rpm')} / kPa {cell_band.get('kpa')}"
                )
            cells = cast(Sequence[Dict[str, Any]], anomaly.get("cells", []))
            if cells:
                cells_s = ", ".join(
                    [
                        f"({c.get('rpm')},{c.get('kpa')}{' hot' if c.get('hot') else ''})"
                        for c in cells
                    ]
                )
                lines.append(f"   cells: {cells_s} ...")
            lines.append(f"   why: {anomaly.get('explanation', '')}")
            next_checks = cast(Sequence[str], anomaly.get("next_checks", []))
            lines.append(f"   next: {', '.join(next_checks)}")
    safe_outdir = io_contracts.safe_path(str(outdir))
    Path(safe_outdir, "Diagnostics_Report.txt").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    # Machine-readable
    diagnostic_output: Dict[str, Any] = {
        "anomalies": anomalies,
        "correction_diagnostics": correction_diagnostics or {},
    }
    Path(safe_outdir, "Anomaly_Hypotheses.json").write_text(
        json.dumps(diagnostic_output, indent=2), encoding="utf-8"
    )

    # Write confidence report separately if provided
    if confidence_report:
        Path(safe_outdir, "ConfidenceReport.json").write_text(
            json.dumps(confidence_report, indent=2), encoding="utf-8"
        )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Dyno-mode AI tuner v1.2 (VE apply + diagnostics)"
    )
    ap.add_argument("--csv", required=True, help="WinPEP8 export CSV path.")
    ap.add_argument("--outdir", default=".", help="Output directory.")
    ap.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose debug logging."
    )
    ap.add_argument(
        "--weighting",
        choices=["torque", "hp"],
        default="torque",
        help="Use torque or horsepower for weighting AFR error data.",
    )
    ap.add_argument(
        "--smooth_passes",
        type=int,
        default=2,
        help="Neighbor smoothing passes for VE delta.",
    )
    ap.add_argument(
        "--clamp",
        type=float,
        default=7.0,
        help="Clamp VE delta to +/- this percent (production: 7, analysis: 10-15).",
    )
    ap.add_argument(
        "--rear_bias",
        type=float,
        default=0.0,
        help="Add %% to REAR VE in 2500-3800 rpm @ 65-95 kPa before smoothing (e.g., 2.5).",
    )
    ap.add_argument(
        "--rear_rule_deg",
        type=float,
        default=2.0,
        help="Base rear-cylinder extra retard (deg) to enforce in mid-load band.",
    )
    ap.add_argument(
        "--hot_extra",
        type=float,
        default=-1.0,
        help="Additional rear retard (deg) when IAT >=120F in rule band (negative).",
    )
    ap.add_argument(
        "--base_front",
        help="Front VE base CSV (9x5 bins). If provided, tool emits updated absolute VE tables.",
    )
    ap.add_argument(
        "--base_rear",
        help="Rear VE base CSV (optional; if omitted, base_front is reused).",
    )
    # Decel fuel management options
    ap.add_argument(
        "--decel-management",
        action="store_true",
        help="Enable decel fuel management to eliminate exhaust popping.",
    )
    ap.add_argument(
        "--decel-severity",
        choices=["low", "medium", "high"],
        default="medium",
        help="Decel enrichment severity: low (minimal), medium (balanced), high (aggressive).",
    )
    ap.add_argument(
        "--decel-rpm-min",
        type=int,
        default=1500,
        help="Minimum RPM for decel zone (default: 1500).",
    )
    ap.add_argument(
        "--decel-rpm-max",
        type=int,
        default=5500,
        help="Maximum RPM for decel zone (default: 5500).",
    )
    # Cylinder balancing options
    ap.add_argument(
        "--balance-cylinders",
        action="store_true",
        help="Enable per-cylinder auto-balancing to equalize front/rear AFR.",
    )
    ap.add_argument(
        "--balance-mode",
        choices=["equalize", "match_front", "match_rear"],
        default="equalize",
        help="Balancing strategy: equalize (both toward average), match_front (rear to front), match_rear (front to rear).",
    )
    ap.add_argument(
        "--balance-max-correction",
        type=float,
        default=3.0,
        help="Maximum VE correction percentage for balancing (default: 3.0%%).",
    )
    # PDF report generation options
    ap.add_argument(
        "--generate-report",
        action="store_true",
        help="Generate a professional PDF report suitable for customer delivery and insurance.",
    )
    ap.add_argument(
        "--report-shop-name",
        type=str,
        default="",
        help="Shop/business name to include in report header.",
    )
    ap.add_argument(
        "--report-operator",
        type=str,
        default="",
        help="Operator name for the tuning session.",
    )
    ap.add_argument(
        "--report-vehicle",
        type=str,
        default="",
        help="Vehicle description (year, make, model).",
    )
    args = ap.parse_args()

    # Configure logging level based on --verbose flag
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Validate input CSV path (prevent path traversal)
    try:
        csv_path = io_contracts.safe_path(args.csv)
    except ValueError as e:
        print(f"[ERROR] Invalid CSV path: {e}", file=sys.stderr)
        return 1

    # Validate output directory path (prevent path traversal)
    try:
        outdir = io_contracts.safe_path(args.outdir)
    except ValueError as e:
        print(f"[ERROR] Invalid output directory: {e}", file=sys.stderr)
        return 1

    # Validate base VE table paths if provided
    base_front_path = None
    base_rear_path = None
    if args.base_front:
        try:
            base_front_path = io_contracts.safe_path(args.base_front)
        except ValueError as e:
            print(f"[ERROR] Invalid base front VE table path: {e}", file=sys.stderr)
            return 1
    if args.base_rear:
        try:
            base_rear_path = io_contracts.safe_path(args.base_rear)
        except ValueError as e:
            print(f"[ERROR] Invalid base rear VE table path: {e}", file=sys.stderr)
            return 1

    outdir.mkdir(parents=True, exist_ok=True)

    run_id = io_contracts.make_run_id()

    # Check if input CSV exists before proceeding
    try:
        input_info: Dict[str, Any] = io_contracts.csv_schema_check(str(csv_path))
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    args_cfg = {
        "smooth_passes": args.smooth_passes,
        "clamp": args.clamp,
        "rear_bias": args.rear_bias,
        "rear_rule_deg": args.rear_rule_deg,
        "hot_extra": args.hot_extra,
    }
    base_tables = {"front": args.base_front, "rear": args.base_rear}
    # Make a copy of the args for the manifest
    args_cfg = vars(args).copy()
    # don't store file handles in the manifest
    if "csv" in args_cfg and hasattr(args_cfg["csv"], "name"):
        args_cfg["csv"] = args_cfg["csv"].name

    manifest: Dict[str, Any] = io_contracts.start_manifest(
        tool_version="1.2",
        run_id=run_id,
        input_info=input_info,
        args_cfg=args_cfg,
        base_tables=base_tables,
    )
    stats: Optional[Dict[str, Any]] = None
    last_stage = "init"
    try:
        last_stage = "load"
        print("PROGRESS:10:Loading and parsing CSV...")
        sys.stdout.flush()

        file_format = detect_csv_format(str(csv_path))
        print(f"INFO: Detected CSV format: {file_format}")

        if file_format == "winpep":
            recs = load_winpep_csv(str(csv_path))
        elif file_format in [
            "generic",
            "powervision",
        ]:  # Handle both generic and powervision
            recs = load_generic_csv(str(csv_path))
        else:
            # Fallback or error
            try:
                print("WARN: Unknown CSV format, attempting to load as WinPEP...")
                recs = load_winpep_csv(str(csv_path))
            except RuntimeError as e:
                raise RuntimeError(
                    "Failed to parse CSV. Format is not recognized as WinPEP or Generic.\n"
                    f"Original error: {e}"
                )

        last_stage = "aggregate"
        print("PROGRESS:30:Aggregating front cylinder data...")
        sys.stdout.flush()
        (
            afr_err_f,
            knock_f,
            iat_f,
            cov_f,
            diag_f,
            tq_f,
            hp_f,
        ) = dyno_bin_aggregate(recs, cyl="f", use_hp_weight=args.weighting == "hp")
        print("PROGRESS:50:Aggregating rear cylinder data...")
        sys.stdout.flush()
        (
            afr_err_r,
            knock_r,
            iat_r,
            cov_r,
            diag_r,
            tq_r,
            hp_r,
        ) = dyno_bin_aggregate(recs, cyl="r", use_hp_weight=args.weighting == "hp")

        # Combine front and rear cylinder data for primary outputs
        ve_delta = combine_front_rear(afr_err_f, afr_err_r)
        tq_combined = combine_front_rear(tq_f, tq_r)
        hp_combined = combine_front_rear(hp_f, hp_r)

        if abs(args.rear_bias) > 0.0:
            for ri, rpm in enumerate(RPM_BINS):
                for ki, kpa in enumerate(KPA_BINS):
                    if 2500 <= rpm <= 3800 and 65 <= kpa <= 95:
                        if afr_err_r[ri][ki] is not None:
                            afr_err_r[ri][ki] = (
                                afr_err_r[ri][ki] or 0.0
                            ) + args.rear_bias

        print("PROGRESS:70:Smoothing and clamping VE corrections...")
        sys.stdout.flush()
        ve_smooth = kernel_smooth(ve_delta, passes=max(0, min(5, args.smooth_passes)))
        ve_clamped, clamped_cells_combined = clamp_grid(ve_smooth, args.clamp)

        print("PROGRESS:80:Generating spark advance suggestions...")
        sys.stdout.flush()
        spark_f = spark_suggestion(knock_f, iat_f)
        spark_r = spark_suggestion(knock_r, iat_r)
        spark_r = enforce_rear_rule(
            spark_r,
            extra_rule_deg=args.rear_rule_deg,
            hot_extra=args.hot_extra,
            iat_grid=iat_r,
        )

        last_stage = "export"
        print("PROGRESS:90:Writing output files...")
        sys.stdout.flush()
        write_matrix_csv(
            outdir / "VE_Correction_Delta_DYNO.csv", RPM_BINS, KPA_BINS, ve_clamped
        )
        write_matrix_csv(
            outdir / "Spark_Adjust_Suggestion_Front.csv",
            RPM_BINS,
            KPA_BINS,
            spark_f,
            value_fmt="{:+.2f}",
        )
        write_matrix_csv(
            outdir / "Spark_Adjust_Suggestion_Rear.csv",
            RPM_BINS,
            KPA_BINS,
            spark_r,
            value_fmt="{:+.2f}",
        )
        write_matrix_csv(
            outdir / "AFR_Error_Map_Front.csv",
            RPM_BINS,
            KPA_BINS,
            afr_err_f,
            value_fmt="{:+.2f}",
        )
        write_matrix_csv(
            outdir / "AFR_Error_Map_Rear.csv",
            RPM_BINS,
            KPA_BINS,
            afr_err_r,
            value_fmt="{:+.2f}",
        )

        # Individual cylinder torque and HP maps for diagnostics
        write_matrix_csv(
            outdir / "Torque_Map_Front.csv",
            RPM_BINS,
            KPA_BINS,
            tq_f,
            value_fmt="{:.1f}",
        )
        write_matrix_csv(
            outdir / "Torque_Map_Rear.csv",
            RPM_BINS,
            KPA_BINS,
            tq_r,
            value_fmt="{:.1f}",
        )
        write_matrix_csv(
            outdir / "HP_Map_Front.csv",
            RPM_BINS,
            KPA_BINS,
            hp_f,
            value_fmt="{:.1f}",
        )
        write_matrix_csv(
            outdir / "HP_Map_Rear.csv",
            RPM_BINS,
            KPA_BINS,
            hp_r,
            value_fmt="{:.1f}",
        )

        # Combined torque and HP maps for overall performance view
        write_matrix_csv(
            outdir / "Torque_Map_Combined.csv",
            RPM_BINS,
            KPA_BINS,
            tq_combined,
            value_fmt="{:.1f}",
        )
        write_matrix_csv(
            outdir / "HP_Map_Combined.csv",
            RPM_BINS,
            KPA_BINS,
            hp_combined,
            value_fmt="{:.1f}",
        )

        coverage_csv(outdir / "Coverage_Front.csv", cov_f)
        coverage_csv(outdir / "Coverage_Rear.csv", cov_r)

        write_paste_block(
            outdir / "VE_Delta_PasteReady.txt", ve_clamped, value_fmt="{:+.2f}"
        )
        write_paste_block(
            outdir / "Spark_Front_PasteReady.txt", spark_f, value_fmt="{:+.2f}"
        )
        write_paste_block(
            outdir / "Spark_Rear_PasteReady.txt", spark_r, value_fmt="{:+.2f}"
        )

        if base_front_path:
            base_f = read_grid_csv(str(base_front_path))
            base_r = read_grid_csv(str(base_rear_path or base_front_path))
            ve_abs_f = apply_delta_to_base(base_f, ve_clamped)
            ve_abs_r = apply_delta_to_base(base_r, ve_clamped)
            write_grid_csv_absolute(outdir / "VE_Front_Updated.csv", ve_abs_f)
            write_grid_csv_absolute(outdir / "VE_Rear_Updated.csv", ve_abs_r)
            write_paste_block(
                outdir / "VE_Front_Absolute_PasteReady.txt",
                ve_abs_f,
                value_fmt="{:.2f}",
            )
            write_paste_block(
                outdir / "VE_Rear_Absolute_PasteReady.txt", ve_abs_r, value_fmt="{:.2f}"
            )
            extra_specs.extend(
                [
                    ("VE_Front_Updated.csv", "csv", "ve_front_updated", True),
                    ("VE_Rear_Updated.csv", "csv", "ve_rear_updated", True),
                    (
                        "VE_Front_Absolute_PasteReady.txt",
                        "text",
                        "ve_front_absolute_paste",
                        False,
                    ),
                    (
                        "VE_Rear_Absolute_PasteReady.txt",
                        "text",
                        "ve_rear_absolute_paste",
                        False,
                    ),
                ]
            )

        last_stage = "diagnostics"
        print("PROGRESS:95:Running anomaly diagnostics...")
        sys.stdout.flush()
        anomalies = anomaly_diagnostics(
            recs,
            afr_err_f=afr_err_f,
            afr_err_r=afr_err_r,
            ve_delta_grid=ve_clamped,
            knock_f=knock_f,
            iat_f=iat_f,
            knock_r=knock_r,
            iat_r=iat_r,
            coverage=[
                [cov_f[r][k] + cov_r[r][k] for k in range(len(KPA_BINS))]
                for r in range(len(RPM_BINS))
            ],
        )

        # Calculate tune confidence score
        print("PROGRESS:96:Calculating tune confidence score...")
        sys.stdout.flush()

        # Extract MAD grids from diagnostics
        mad_grid_f = diag_f.get("per_bin_stats", {}).get(
            "mad", [[None for _ in KPA_BINS] for _ in RPM_BINS]
        )
        mad_grid_r = diag_r.get("per_bin_stats", {}).get(
            "mad", [[None for _ in KPA_BINS] for _ in RPM_BINS]
        )

        # For clamped cells, we need to split by cylinder (we only have combined)
        # Since we don't track separately, we'll split them evenly for the confidence calc
        half_clamped = len(clamped_cells_combined) // 2
        clamped_cells_f = clamped_cells_combined[:half_clamped]
        clamped_cells_r = clamped_cells_combined[half_clamped:]

        confidence_report = calculate_tune_confidence(
            coverage_f=cov_f,
            coverage_r=cov_r,
            mad_grid_f=mad_grid_f,
            mad_grid_r=mad_grid_r,
            anomalies=anomalies,
            clamped_cells_f=clamped_cells_f,
            clamped_cells_r=clamped_cells_r,
        )

        print(
            f"[OK] Tune Confidence: {confidence_report['overall_score']}% (Grade {confidence_report['letter_grade']})"
        )

        correction_diagnostics = {"front": diag_f, "rear": diag_r}
        write_diagnostics(outdir, anomalies, correction_diagnostics, confidence_report)

        # Initialize extra_specs list for additional outputs
        extra_specs: List[Tuple[str, str, str, bool]] = []

        # --- Find Power Opportunities ---
        print("PROGRESS:96:Analyzing power opportunities...")
        sys.stdout.flush()
        power_opportunities = find_power_opportunities(
            afr_err_f=afr_err_f,
            afr_err_r=afr_err_r,
            spark_f=spark_f,
            spark_r=spark_r,
            coverage_f=cov_f,
            coverage_r=cov_r,
            knock_f=knock_f,
            knock_r=knock_r,
            hp_grid=hp_combined,
        )

        # Write power opportunities to JSON
        power_output_path = outdir / "PowerOpportunities.json"
        power_output = {
            "summary": {
                "total_opportunities": len(power_opportunities),
                "total_estimated_gain_hp": round(
                    sum(opp["estimated_gain_hp"] for opp in power_opportunities), 2
                ),
                "analysis_date": io_contracts.utc_now_iso(),
            },
            "opportunities": power_opportunities,
            "safety_notes": [
                "All suggestions are conservative and prioritize engine safety",
                "Test changes incrementally and monitor for knock",
                "Verify AFR targets are appropriate for your fuel and application",
                "Maximum suggested changes: ±3% AFR, +2° timing per cell",
            ],
        }
        power_output_path.write_text(
            json.dumps(power_output, indent=2), encoding="utf-8"
        )
        print(
            f"[OK] Found {len(power_opportunities)} power opportunities, "
            f"estimated total gain: {power_output['summary']['total_estimated_gain_hp']:.2f} HP"
        )

        stats = {
            "rows_read": len(recs),
            "bins_total": len(RPM_BINS) * len(KPA_BINS),
            "bins_covered": sum(1 for row in cov_f for value in row if value > 0),
            "front_accepted": diag_f["accepted_wb"],
            "rear_accepted": diag_r["accepted_wb"],
            "power_opportunities_found": len(power_opportunities),
        }

        # --- Decel Fuel Management ---
        if args.decel_management:
            print("\nPROGRESS:96:Running decel fuel management analysis...")
            sys.stdout.flush()
            try:
                from dynoai.core.decel_management import process_decel_management

                # Build decel config from args
                decel_config = {
                    "rpm_min": args.decel_rpm_min,
                    "rpm_max": args.decel_rpm_max,
                }

                decel_result = process_decel_management(
                    recs,
                    output_dir=outdir,
                    severity=args.decel_severity,
                    sample_rate_ms=10.0,  # Typical dyno log sample rate
                    input_file=str(csv_path),
                    config=decel_config,
                )

                print(
                    f"[OK] Decel management: {decel_result['events_detected']} events detected, "
                    f"severity={decel_result['severity_used']}"
                )

                # Add decel outputs to manifest
                extra_specs.extend(
                    [
                        ("Decel_Fuel_Overlay.csv", "csv", "decel_overlay", True),
                        ("Decel_Analysis_Report.json", "json", "decel_report", False),
                    ]
                )

            except ImportError as e:
                print(f"[WARN] Decel management module not available: {e}")
            except Exception as e:
                print(f"[WARN] Decel management failed: {e}")

        # --- Per-Cylinder Auto-Balancing ---
        if args.balance_cylinders:
            print("\nPROGRESS:97:Running per-cylinder auto-balancing...")
            sys.stdout.flush()
            try:
                from dynoai.core.cylinder_balancing import process_cylinder_balancing

                balance_result = process_cylinder_balancing(
                    records=recs,
                    output_dir=outdir,
                    mode=args.balance_mode,
                    max_correction_pct=args.balance_max_correction,
                    input_file=str(csv_path),
                )

                print(
                    f"[OK] Cylinder balancing: {balance_result['cells_imbalanced']}/{balance_result['cells_analyzed']} cells imbalanced "
                    f"(max delta: {balance_result['max_afr_delta']:.2f} AFR)"
                )

                # Add balance outputs to manifest
                extra_specs.extend(
                    [
                        (
                            "Front_Balance_Factor.csv",
                            "csv",
                            "front_balance_factor",
                            True,
                        ),
                        ("Rear_Balance_Factor.csv", "csv", "rear_balance_factor", True),
                        (
                            "Cylinder_Balance_Report.json",
                            "json",
                            "balance_report",
                            False,
                        ),
                    ]
                )

            except ImportError as e:
                print(f"[WARN] Cylinder balancing module not available: {e}")
            except Exception as e:
                print(f"[WARN] Cylinder balancing failed: {e}")

        # --- Visualization Call ---
        # Always attempt to generate visualizations if the script exists
        vis_script_path = Path(__file__).parent / "visualize_coverage_all.py"
        if vis_script_path.exists():
            print("\nPROGRESS:98:Generating coverage visualizations...")
            sys.stdout.flush()

            # We need to find the primary coverage file to pass to the script
            coverage_file_path = outdir / "Coverage_Front.csv"

            if coverage_file_path.exists():
                try:
                    import subprocess

                    # Use sys.executable to ensure the correct python interpreter is used
                    result = subprocess.run(
                        [sys.executable, str(vis_script_path), str(coverage_file_path)],
                        capture_output=True,
                        text=True,
                        cwd=outdir,  # Run from the output directory
                        check=False,  # Don't throw exception on non-zero exit
                    )
                    if result.returncode == 0:
                        print("[OK] Coverage visualizations generated successfully.")
                    else:
                        print("[WARN] Coverage visualization script ran with errors.")
                        # Log stdout/stderr for debugging
                        if result.stdout:
                            print(f"       STDOUT: {result.stdout.strip()}")
                        if result.stderr:
                            print(f"       STDERR: {result.stderr.strip()}")
                except Exception as vis_exc:
                    print(f"[ERROR] Failed to run visualization script: {vis_exc}")
            else:
                print("[WARN] 'Coverage_Front.csv' not found, skipping visualization.")
        else:
            print(
                "[WARN] 'visualize_coverage_all.py' not found, skipping visualization."
            )
        # --- End Visualization Call ---

        # --- Write Session Replay Log ---
        print("PROGRESS:99:Writing session replay log...")
        sys.stdout.flush()
        write_session_replay(outdir, run_id)

        # --- Generate PDF Report (if requested) ---
        if args.generate_report:
            print("\nPROGRESS:99.5:Generating PDF report...")
            sys.stdout.flush()
            try:
                from report_generator import generate_pdf_report

                # Prepare run data
                run_data = {
                    "run_id": run_id,
                    "date": io_contracts.utc_now_iso(),
                    "operator": args.report_operator or "N/A",
                    "vehicle": args.report_vehicle or "N/A",
                }

                # Prepare shop info
                shop_info = None
                if args.report_shop_name:
                    shop_info = {
                        "name": args.report_shop_name,
                        "address": "",
                        "phone": "",
                        "email": "",
                        "website": "",
                        "logo_path": None,
                    }

                # Generate PDF
                pdf_path = outdir / "DynoAI_Report.pdf"
                generate_pdf_report(
                    output_path=pdf_path,
                    run_data=run_data,
                    manifest=manifest,
                    anomalies=anomalies,
                    confidence_report=confidence_report,
                    ve_delta=ve_clamped,
                    torque_map=tq_combined,
                    hp_map=hp_combined,
                    rpm_bins=RPM_BINS,
                    kpa_bins=KPA_BINS,
                    shop_info=shop_info,
                    disclaimer=None,  # Use default
                )

                print(f"[OK] PDF report generated: {pdf_path}")

                # Add PDF to outputs manifest
                extra_specs.append(("DynoAI_Report.pdf", "pdf", "tuning_report", False))

            except ImportError as e:
                print(f"[WARN] PDF report generation not available: {e}")
                print("[WARN] Install required packages: pip install reportlab qrcode")
            except Exception as e:
                print(f"[WARN] PDF report generation failed: {e}")
                logger.exception("PDF generation error")
        # --- End PDF Report Generation ---

        register_outputs(manifest, outdir, extra_specs)
        # Finalize and write manifest
        io_contracts.finish_manifest(
            manifest, ok=True, last_stage="export", stats=stats
        )
        io_contracts.write_manifest_pair(manifest, str(outdir), run_id)

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        # Update manifest with error state
        if manifest:
            io_contracts.finish_manifest(
                manifest, ok=False, last_stage=last_stage, message=str(e)
            )
            io_contracts.write_manifest_pair(manifest, str(outdir), run_id)
        sys.exit(1)

    finally:
        if manifest and manifest.get("timing", {}).get("end") is None:
            # This block is for cases where sys.exit might be called before finish_manifest
            io_contracts.finish_manifest(
                manifest, ok=False, last_stage=last_stage, message="Incomplete run"
            )

        if manifest:
            # Validate outputs against manifest
            val_ok, val_msg = io_contracts.validate_outputs_against_manifest(
                str(outdir), manifest
            )
            if not val_ok:
                print(f"[WARNING] Output validation failed: {val_msg}", file=sys.stderr)

    print("PROGRESS:100:Done.")
    sys.stdout.flush()
    print("Dyno AI Tuner v1.2 outputs written to:", outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
