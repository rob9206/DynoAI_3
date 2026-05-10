"""Shared VE apply safety checks used by frontend and CLI flows."""

from __future__ import annotations

import math
from typing import Any, Literal, TypedDict

EPSILON = 1e-6


class SafetyThresholds(TypedDict):
    """Safety and warning thresholds mirrored from veApplyValidation.ts."""

    block_raw_delta_pct: float
    warn_raw_delta_pct: float
    warn_systematic_bias_pct: float
    warn_localized_imbalance_pct: float
    min_hits_for_inclusion: int
    warn_coverage_pct: float


SAFETY: SafetyThresholds = {
    "block_raw_delta_pct": 25.0,
    "warn_raw_delta_pct": 10.0,
    "warn_systematic_bias_pct": 2.0,
    "warn_localized_imbalance_pct": 5.0,
    "min_hits_for_inclusion": 3,
    "warn_coverage_pct": 50.0,
}

BlockReasonType = Literal[
    "extreme_correction",
    "missing_base",
    "shape_mismatch",
    "partial_cylinder",
    "invalid_base_ve",
    "empty_grid",
]


class BlockCell(TypedDict):
    rpm: float
    map: float
    value: float


class BlockReason(TypedDict, total=False):
    type: BlockReasonType
    message: str
    cells: list[BlockCell]


DualCylinderGrid = dict[str, list[list[float]]]


def validate_correction(value: Any) -> float | None:
    """Return a valid correction value or None for invalid input."""
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    if number <= 0:
        return None
    return number


def sanitize_correction(value: Any) -> float:
    """Coerce invalid corrections to neutral multiplier 1.0."""
    valid = validate_correction(value)
    if valid is None:
        return 1.0
    return valid


def has_active_correction(
    correction: float,
    hit_count: float,
    min_hits: int = SAFETY["min_hits_for_inclusion"],
) -> bool:
    """A correction is active only with enough hits and non-unity value."""
    if hit_count < min_hits:
        return False
    sanitized = sanitize_correction(correction)
    return abs(sanitized - 1.0) > EPSILON


def _axis_value(axis: list[float], idx: int) -> float:
    if 0 <= idx < len(axis):
        return float(axis[idx])
    return float(idx)


def _shape(grid: list[list[float]]) -> tuple[int, int]:
    if not grid:
        return (0, 0)
    return (len(grid), len(grid[0]) if grid[0] else 0)


# skipcq: PY-R1000
def check_block_conditions(
    base_ve: DualCylinderGrid | None,
    corrections: DualCylinderGrid,
    hit_counts: DualCylinderGrid,
    rpm_axis: list[float],
    map_axis: list[float],
) -> list[BlockReason]:
    """Run all apply-block conditions. Empty list means apply is allowed."""
    blocks: list[BlockReason] = []

    if not base_ve:
        blocks.append(
            {
                "type": "missing_base",
                "message": "Import a base VE table (PVV or preset) before applying corrections.",
            }
        )
        return blocks

    base_front = base_ve["front"]
    if len(base_front) == 0 or len(base_front[0]) == 0:
        blocks.append(
            {
                "type": "empty_grid",
                "message": "Base VE grid is empty. Import a valid tune file.",
            }
        )
        return blocks

    expected_rows = len(base_front)
    expected_cols = len(base_front[0])
    grids = [
        ("baseVE.front", base_ve["front"]),
        ("baseVE.rear", base_ve["rear"]),
        ("corrections.front", corrections["front"]),
        ("corrections.rear", corrections["rear"]),
        ("hitCounts.front", hit_counts["front"]),
        ("hitCounts.rear", hit_counts["rear"]),
    ]
    mismatches = [
        name for name, grid in grids if _shape(grid) != (expected_rows, expected_cols)
    ]
    if mismatches:
        blocks.append(
            {
                "type": "shape_mismatch",
                "message": (
                    f"Grid dimensions must be {expected_rows}x{expected_cols}. "
                    f"Mismatched: {', '.join(mismatches)}"
                ),
            }
        )
        return blocks

    invalid_base_cells: list[dict[str, Any]] = []
    for cylinder in ("front", "rear"):
        for rpm_idx, row in enumerate(base_ve[cylinder]):
            for map_idx, value in enumerate(row):
                if not math.isfinite(value) or value <= 0:
                    invalid_base_cells.append(
                        {
                            "rpm": _axis_value(rpm_axis, rpm_idx),
                            "map": _axis_value(map_axis, map_idx),
                            "value": float(value),
                            "cylinder": cylinder,
                        }
                    )

    if invalid_base_cells:
        blocks.append(
            {
                "type": "invalid_base_ve",
                "message": (
                    f"Base VE contains {len(invalid_base_cells)} invalid cells "
                    "(zero, negative, or NaN)."
                ),
                "cells": [
                    {"rpm": c["rpm"], "map": c["map"], "value": c["value"]}
                    for c in invalid_base_cells[:10]
                ],
            }
        )

    front_active_count = 0
    rear_active_count = 0

    for rpm_idx, row in enumerate(corrections["front"]):
        for map_idx, correction in enumerate(row):
            if has_active_correction(
                correction,
                hit_counts["front"][rpm_idx][map_idx],
            ):
                front_active_count += 1

    for rpm_idx, row in enumerate(corrections["rear"]):
        for map_idx, correction in enumerate(row):
            if has_active_correction(
                correction,
                hit_counts["rear"][rpm_idx][map_idx],
            ):
                rear_active_count += 1

    has_front = front_active_count > 0
    has_rear = rear_active_count > 0
    if has_front != has_rear:
        blocks.append(
            {
                "type": "partial_cylinder",
                "message": (
                    f"Both cylinders required. Active cells: front={front_active_count}, "
                    f"rear={rear_active_count}. Ensure data collection captures both cylinders."
                ),
            }
        )

    extreme_cells: list[dict[str, Any]] = []
    for cylinder in ("front", "rear"):
        for rpm_idx, row in enumerate(corrections[cylinder]):
            for map_idx, correction in enumerate(row):
                hits = hit_counts[cylinder][rpm_idx][map_idx]
                if hits < SAFETY["min_hits_for_inclusion"]:
                    continue
                sanitized = sanitize_correction(correction)
                raw_delta_pct = abs((sanitized - 1.0) * 100.0)
                if raw_delta_pct > SAFETY["block_raw_delta_pct"]:
                    extreme_cells.append(
                        {
                            "rpm": _axis_value(rpm_axis, rpm_idx),
                            "map": _axis_value(map_axis, map_idx),
                            "value": float(raw_delta_pct),
                            "cylinder": cylinder,
                        }
                    )

    if extreme_cells:
        blocks.append(
            {
                "type": "extreme_correction",
                "message": (
                    f"{len(extreme_cells)} cells exceed ±{SAFETY['block_raw_delta_pct']:.0f}% "
                    "correction. This usually indicates wrong base tune, sensor error, "
                    "or hardware change."
                ),
                "cells": [
                    {"rpm": c["rpm"], "map": c["map"], "value": c["value"]}
                    for c in extreme_cells[:10]
                ],
            }
        )

    return blocks


def get_block_reason_description(block_type: BlockReasonType) -> str:
    """Human-readable summary for block reason type."""
    descriptions = {
        "extreme_correction": "Extreme corrections detected - check sensor data or base tune",
        "missing_base": "No base VE table loaded - import a PVV file or select a preset",
        "shape_mismatch": "Grid dimensions do not match - reload data",
        "partial_cylinder": "Missing data for one cylinder - collect more samples",
        "invalid_base_ve": "Base VE contains invalid values - check imported file",
        "empty_grid": "Empty grid - import a valid tune file",
    }
    return descriptions.get(block_type, "Unknown validation error")
