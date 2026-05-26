"""IdleVeNoiseDetector: detect roughness in the idle/cruise VE region.

Consumes the tune's VE tables. Two input paths, preferred order:

  1. **`ctx.surfaces["ve_front"]` + `["ve_rear"]`** — symmetric with the
     other surface-based detectors. The NextGen workflow can populate
     these by passing `base_pvv_path` to `generate_for_run()`, which
     merges PVV VE tables into the payload's surfaces dict via
     `dynoai.pvv.surface_view.load_ve_surfaces`.
  2. **`ctx.base_pvv_path`** — direct PVV parse fallback for callers
     that don't populate surfaces (legacy, tests, ad-hoc invocations).

Both paths produce the same metric on the same input.

Metric: **max adjacent-cell delta as a percentage of the mean cell value
in the smoothing mask** (RPM <= mask_rpm_max AND TPS <= mask_tps_max).

Why this metric and not mean-delta or stddev: empirical calibration on the
seanbike fixtures shows it's the only metric with clean separation between
the noisy PC-translated input (31-33% on the front/rear tables) and the
post-smoothed output (21-23%). The GP smoother is designed to kill the
biggest jumps, so the max-delta metric is exactly what it changes most.

Severity mapping (max_delta_pct -> 0..1):
    < min_noise_pct  : not a finding
    25-35  pct       : 0.30 -> 0.50  (mild)
    35-50  pct       : 0.50 -> 0.75  (moderate)
    50-75  pct       : 0.75 -> 0.95  (severe)
    >= 75  pct       : 1.00          (critical)

Routes to `gp_smooth_idle_cruise_ve`. The detected mask bounds
(mask_rpm_max, mask_tps_max) flow through tool_params so the smoother
operates on the same region the detector flagged.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from dynoai.core.surface_builder import Surface2D
from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.finding import Finding
from dynoai.pvv.io import parse_table


_IDLE_VE_NOISE_KIND = "idle_ve_noise"
_GP_SMOOTH_TOOL = "gp_smooth_idle_cruise_ve"


def _severity_from_max_delta_pct(pct: float, threshold: float) -> float:
    p = float(pct)
    if p < threshold:
        return 0.0
    if p <= 35.0:
        span = max(35.0 - threshold, 1e-9)
        return 0.30 + (p - threshold) * (0.50 - 0.30) / span
    if p <= 50.0:
        return 0.50 + (p - 35.0) * (0.75 - 0.50) / 15.0
    if p <= 75.0:
        return 0.75 + (p - 50.0) * (0.95 - 0.75) / 25.0
    return 1.0


def _compute_roughness(
    values: np.ndarray,
    mask: np.ndarray,
) -> Dict[str, float]:
    """Compute roughness metrics over masked cells.

    Returns mean_delta_pct, max_delta_pct, std_pct, mean_val, n_pairs.
    Returns zeros and `n_pairs=0` if the mask has < 2 connected cells.
    """
    rows, cols = values.shape
    mean_val = float(np.mean(values[mask])) if np.any(mask) else 0.0
    if mean_val <= 0.0:
        return {
            "mean_delta_pct": 0.0,
            "max_delta_pct": 0.0,
            "std_pct": 0.0,
            "mean_val": 0.0,
            "n_pairs": 0,
        }
    deltas: list[float] = []
    for r in range(rows):
        for c in range(cols):
            if not mask[r, c]:
                continue
            for dr, dc in ((0, 1), (1, 0)):
                nr, nc = r + dr, c + dc
                if nr < rows and nc < cols and mask[nr, nc]:
                    deltas.append(abs(float(values[nr, nc] - values[r, c])))
    if not deltas:
        return {
            "mean_delta_pct": 0.0,
            "max_delta_pct": 0.0,
            "std_pct": 0.0,
            "mean_val": mean_val,
            "n_pairs": 0,
        }
    return {
        "mean_delta_pct": float(np.mean(deltas)) / mean_val * 100.0,
        "max_delta_pct": float(np.max(deltas)) / mean_val * 100.0,
        "std_pct": float(np.std(values[mask])) / mean_val * 100.0,
        "mean_val": mean_val,
        "n_pairs": len(deltas),
    }


def _build_mask(
    row_axis_krpm: np.ndarray,
    col_axis_tps: np.ndarray,
    mask_rpm_max_krpm: float,
    mask_tps_max: float,
) -> np.ndarray:
    rpm_ok = row_axis_krpm[:, None] <= (mask_rpm_max_krpm + 1e-9)
    tps_ok = col_axis_tps[None, :] <= (mask_tps_max + 1e-9)
    return rpm_ok & tps_ok


class IdleVeNoiseDetector:
    """Detects noisy idle/cruise VE cells by reading the base PVV directly."""

    name = "idle_ve_noise_detector"
    fix_kinds: Tuple[str, ...] = (_IDLE_VE_NOISE_KIND,)

    def __init__(
        self,
        *,
        ve_front_id: str = "tbl_ve_tps_based_front_cyl",
        ve_rear_id: str = "tbl_ve_tps_based_rear_cyl",
        mask_rpm_max_krpm: float = 4.0,
        mask_tps_max_pct: float = 40.0,
        min_max_delta_pct: float = 25.0,
        min_mask_cells: int = 6,
    ) -> None:
        if min_max_delta_pct <= 0.0:
            raise ValueError("min_max_delta_pct must be > 0")
        if min_mask_cells < 1:
            raise ValueError("min_mask_cells must be >= 1")
        self.ve_front_id = ve_front_id
        self.ve_rear_id = ve_rear_id
        self.mask_rpm_max_krpm = float(mask_rpm_max_krpm)
        self.mask_tps_max_pct = float(mask_tps_max_pct)
        self.min_max_delta_pct = float(min_max_delta_pct)
        self.min_mask_cells = int(min_mask_cells)

    def _load_from_surfaces(
        self,
        ctx: DetectionContext,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
        """Try to load front+rear VE arrays from ctx.surfaces.

        Returns (front_values, rear_values, row_axis, col_axis) or None if
        either surface is missing or has incompatible shape.
        """
        if not ctx.surfaces:
            return None
        front_s = ctx.surfaces.get("ve_front")
        rear_s = ctx.surfaces.get("ve_rear")
        if front_s is None or rear_s is None:
            return None
        if not isinstance(front_s, Surface2D) or not isinstance(rear_s, Surface2D):
            return None
        front_vals = np.asarray(front_s.values, dtype=float)
        rear_vals = np.asarray(rear_s.values, dtype=float)
        if front_vals.shape != rear_vals.shape:
            return None
        front_row = np.asarray(front_s.rpm_axis.bins, dtype=float)
        front_col = np.asarray(front_s.map_axis.bins, dtype=float)
        rear_row = np.asarray(rear_s.rpm_axis.bins, dtype=float)
        rear_col = np.asarray(rear_s.map_axis.bins, dtype=float)
        if not np.array_equal(front_row, rear_row) or not np.array_equal(front_col, rear_col):
            return None
        return front_vals, rear_vals, front_row, front_col

    def _load_from_pvv(
        self,
        ctx: DetectionContext,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
        """Fallback: parse VE tables from ctx.base_pvv_path directly."""
        if ctx.base_pvv_path is None or not ctx.base_pvv_path.exists():
            return None
        root = ET.parse(ctx.base_pvv_path).getroot()
        try:
            front = parse_table(root, self.ve_front_id)
            rear = parse_table(root, self.ve_rear_id)
        except ValueError:
            return None
        if front.values.shape != rear.values.shape:
            return None
        if not np.array_equal(front.row_axis, rear.row_axis) or not np.array_equal(
            front.col_axis, rear.col_axis
        ):
            return None
        return front.values, rear.values, front.row_axis, front.col_axis

    def detect(self, ctx: DetectionContext) -> List[Finding]:
        # Prefer surfaces (symmetry with other detectors). Fall back to
        # direct PVV parse if surfaces aren't populated.
        loaded = self._load_from_surfaces(ctx) or self._load_from_pvv(ctx)
        if loaded is None:
            return []
        front_values, rear_values, row_axis, col_axis = loaded

        mask = _build_mask(
            row_axis,
            col_axis,
            self.mask_rpm_max_krpm,
            self.mask_tps_max_pct,
        )
        n_mask = int(np.sum(mask))
        if n_mask < self.min_mask_cells:
            return []

        front_metrics = _compute_roughness(front_values, mask)
        rear_metrics = _compute_roughness(rear_values, mask)

        peak_max_delta_pct = max(
            front_metrics["max_delta_pct"], rear_metrics["max_delta_pct"]
        )
        if peak_max_delta_pct < self.min_max_delta_pct:
            return []

        severity = _severity_from_max_delta_pct(
            peak_max_delta_pct, self.min_max_delta_pct
        )

        # Confidence: cell-count factor + signal-strength factor.
        cell_factor = min(0.5, 0.5 * (n_mask / 60.0))
        # Larger gap above threshold -> more confidence in the call.
        strength_factor = min(
            0.5, 0.5 * ((peak_max_delta_pct - self.min_max_delta_pct) / 25.0)
        )
        confidence = min(1.0, cell_factor + strength_factor)

        return [
            Finding(
                kind=_IDLE_VE_NOISE_KIND,
                severity=severity,
                confidence=confidence,
                evidence={
                    "mask_rpm_max_krpm": self.mask_rpm_max_krpm,
                    "mask_tps_max_pct": self.mask_tps_max_pct,
                    "mask_cells": n_mask,
                    "front": front_metrics,
                    "rear": rear_metrics,
                    "peak_max_delta_pct": peak_max_delta_pct,
                    "threshold_pct": self.min_max_delta_pct,
                },
                suggested_tool=_GP_SMOOTH_TOOL,
                tool_params={
                    "mask_rpm_max": self.mask_rpm_max_krpm,
                    "mask_tps_max": self.mask_tps_max_pct,
                },
                source="idle_ve_noise_detector",
            )
        ]
