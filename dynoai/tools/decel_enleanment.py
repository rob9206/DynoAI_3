"""DecelEnleanment: soften hot-side decel enleanment to eliminate overrun popping.

Lifted from `tools/seanbike/patch_decel_enleanment.py` and generalized.

  - Target table: `tbl_deceleration_enleanment` (default; overridable). This
    is a 1-D table indexed by temperature: one row, N columns where each
    column label is a temperature value and each cell is a lambda
    multiplier (lower = more aggressive enleanment = leaner overrun).
  - Hot mask: cells whose temperature column label >= hot_threshold get
    softened toward target_hot. Cold cells are byte-identical to base.
  - Per-cell algorithm:
        delta = target_hot - current
        delta = clip(delta, -per_cell_max_delta, +per_cell_max_delta)
        new   = clip(current + delta, abs_floor, abs_ceil)
  - Per-cell `MaxDeltaGate` and a hard `[abs_floor, abs_ceil]` range gate
    catch any algorithm regression that would emit a value outside the
    declared policy.

First lifted tool that targets a 1-D table (1 row x N cols) and a
non-VE/spark table family. Validates that `dynoai.pvv.io.parse_table`
works as-is on 1-D tables.

Addresses Finding.kind == "decel_pop".
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Tuple

import numpy as np

from dynoai.diagnostics.finding import Finding
from dynoai.pvv.io import (
    TableData,
    mutate_table_cells,
    parse_table,
    sha256,
    verify_integrity_or_cleanup,
    write_xml_tree,
)
from dynoai.tools.gates import (
    GateContext,
    GateFailure,
    ItemIntegrityGate,
)
from dynoai.tools.tool import PatchResult, ToolManifest, ToolPlan, resolve_params

if TYPE_CHECKING:
    from dynoai.diagnostics.detector import DetectionContext


TOOL_NAME = "decel_enleanment"
DEFAULT_TARGET_ITEM_ID = "tbl_deceleration_enleanment"
DEFAULT_HOT_THRESHOLD = 140.0     # temperature axis value
DEFAULT_TARGET_HOT = 0.60         # lambda multiplier target for hot cells
DEFAULT_PER_CELL_MAX_DELTA = 0.40 # algorithm clip
DEFAULT_ABS_FLOOR = 0.30          # never disable enleanment entirely on the low side
DEFAULT_ABS_CEIL = 0.90           # never disable enleanment entirely on the high side
DEFAULT_GATE_DELTA = 0.45         # 5% buffer over policy clip, catches algorithm bugs

_DEFAULTS: Dict[str, Any] = {
    "target_item_id": DEFAULT_TARGET_ITEM_ID,
    "hot_threshold": DEFAULT_HOT_THRESHOLD,
    "target_hot": DEFAULT_TARGET_HOT,
    "per_cell_max_delta": DEFAULT_PER_CELL_MAX_DELTA,
    "abs_floor": DEFAULT_ABS_FLOOR,
    "abs_ceil": DEFAULT_ABS_CEIL,
    "gate_max_delta": DEFAULT_GATE_DELTA,
}


def _compute_patch(
    table: TableData,
    *,
    hot_threshold: float,
    target_hot: float,
    per_cell_max_delta: float,
    abs_floor: float,
    abs_ceil: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pure computation: returns (before, after, touched_mask).

    `touched_mask` is the boolean mask of cells that were eligible for
    modification (hot side). Cells outside the mask are byte-identical in
    `after`. Whether a touched cell actually moved depends on whether
    `before` already equals `target_hot`.
    """
    if table.values.shape[0] != 1:
        raise RuntimeError(
            f"{TOOL_NAME}: expected a 1-row table; got shape {table.values.shape}"
        )
    before = table.values.copy()
    after = before.copy()
    # Column-wise mask on the temperature axis.
    hot_mask = table.col_axis >= (hot_threshold - 1e-9)
    touched_mask = np.zeros_like(before, dtype=bool)
    touched_mask[0, :] = hot_mask
    for c_idx, is_hot in enumerate(hot_mask):
        if not is_hot:
            continue
        current = float(before[0, c_idx])
        delta = target_hot - current
        if delta > per_cell_max_delta:
            delta = per_cell_max_delta
        elif delta < -per_cell_max_delta:
            delta = -per_cell_max_delta
        new_val = current + delta
        new_val = max(abs_floor, min(abs_ceil, new_val))
        after[0, c_idx] = new_val
    return before, after, touched_mask


def _check_max_delta(
    before: np.ndarray,
    after: np.ndarray,
    max_delta: float,
) -> GateFailure | None:
    """Defensive gate: |after - before| <= max_delta for every cell."""
    delta = np.abs(after - before)
    if delta.size == 0:
        return None
    worst = float(np.max(delta))
    if worst > max_delta + 1e-9:
        return GateFailure(
            gate="max_delta",
            reason=(
                f"max per-cell |delta| {worst:.4f} exceeds policy clamp "
                f"{max_delta:.4f}"
            ),
            details={"worst_delta": worst, "clamp": max_delta},
        )
    return None


def _check_range(
    before: np.ndarray,
    after: np.ndarray,
    *,
    abs_floor: float,
    abs_ceil: float,
) -> GateFailure | None:
    """Verify touched cells are in [abs_floor, abs_ceil]."""
    diff_mask = np.abs(after - before) > 1e-9
    if not diff_mask.any():
        return None
    touched = after[diff_mask]
    worst_low = float(np.min(touched))
    worst_high = float(np.max(touched))
    if worst_low < abs_floor - 1e-9:
        return GateFailure(
            gate="range",
            reason=(
                f"touched min {worst_low:.4f} below abs_floor {abs_floor:.4f}"
            ),
            details={"worst_low": worst_low, "abs_floor": abs_floor},
        )
    if worst_high > abs_ceil + 1e-9:
        return GateFailure(
            gate="range",
            reason=(
                f"touched max {worst_high:.4f} above abs_ceil {abs_ceil:.4f}"
            ),
            details={"worst_high": worst_high, "abs_ceil": abs_ceil},
        )
    return None


class DecelEnleanmentTool:
    """Soften decel enleanment on the hot side to eliminate overrun popping."""

    name = TOOL_NAME

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name=self.name,
            description=(
                "Raise hot-side decel enleanment lambda multipliers toward "
                "target_hot to soften aggressive enleanment that causes "
                "overrun popping and stalling. Cold cells preserved."
            ),
            fix_kinds=("decel_pop",),
            inputs_schema={
                "target_item_id": {"type": "string", "default": DEFAULT_TARGET_ITEM_ID},
                "hot_threshold": {"type": "number", "default": DEFAULT_HOT_THRESHOLD},
                "target_hot": {"type": "number", "default": DEFAULT_TARGET_HOT},
                "per_cell_max_delta": {
                    "type": "number", "default": DEFAULT_PER_CELL_MAX_DELTA,
                },
                "abs_floor": {"type": "number", "default": DEFAULT_ABS_FLOOR},
                "abs_ceil": {"type": "number", "default": DEFAULT_ABS_CEIL},
                "gate_max_delta": {
                    "type": "number", "default": DEFAULT_GATE_DELTA,
                },
            },
            safety_gate_names=("max_delta", "range", "item_integrity"),
            requires_profile_keys=("tool_overrides.decel_enleanment",),
        )

    def plan(self, finding: Finding, ctx: "DetectionContext") -> ToolPlan:
        params = resolve_params(_DEFAULTS, ctx.vehicle_profile, finding, TOOL_NAME)
        root = ET.parse(ctx.base_pvv_path).getroot()
        table = parse_table(root, params["target_item_id"])
        before, after, _ = _compute_patch(
            table,
            hot_threshold=float(params["hot_threshold"]),
            target_hot=float(params["target_hot"]),
            per_cell_max_delta=float(params["per_cell_max_delta"]),
            abs_floor=float(params["abs_floor"]),
            abs_ceil=float(params["abs_ceil"]),
        )
        diff = after - before
        changed_mask = np.abs(diff) > 1e-9
        cells_changed = int(np.sum(changed_mask))
        max_delta = float(np.max(np.abs(diff))) if changed_mask.any() else 0.0
        output_dir = ctx.iteration_dir / "patches"
        output_name = ctx.base_pvv_path.stem + "_decelsoft.pvv"
        return ToolPlan(
            tool=self.name,
            finding=finding,
            bound_params=params,
            input_pvv_path=ctx.base_pvv_path,
            output_pvv_path=output_dir / output_name,
            predicted_cells_changed=cells_changed,
            predicted_max_delta={"lambda_mult": max_delta},
            risk_score=min(
                1.0,
                max_delta / max(float(params["gate_max_delta"]), 1e-9),
            ),
        )

    def apply(self, plan: ToolPlan, ctx: "DetectionContext") -> PatchResult:
        params = dict(plan.bound_params)
        target_id = params["target_item_id"]
        allowed_changed = {target_id}

        original_root = ET.parse(plan.input_pvv_path).getroot()
        tree = ET.parse(plan.input_pvv_path)
        root = tree.getroot()
        table = parse_table(root, target_id)

        before, after, touched_mask = _compute_patch(
            table,
            hot_threshold=float(params["hot_threshold"]),
            target_hot=float(params["target_hot"]),
            per_cell_max_delta=float(params["per_cell_max_delta"]),
            abs_floor=float(params["abs_floor"]),
            abs_ceil=float(params["abs_ceil"]),
        )

        integrity_gate = ItemIntegrityGate()
        passed: list[str] = []
        failed: list[GateFailure] = []

        delta_failure = _check_max_delta(
            before, after, float(params["gate_max_delta"])
        )
        if delta_failure is None:
            passed.append("max_delta")
        else:
            failed.append(delta_failure)

        range_failure = _check_range(
            before,
            after,
            abs_floor=float(params["abs_floor"]),
            abs_ceil=float(params["abs_ceil"]),
        )
        if range_failure is None:
            passed.append("range")
        else:
            failed.append(range_failure)

        if failed:
            return PatchResult(
                success=False,
                patch_path=None,
                manifest_path=None,
                sha256=None,
                cells_changed=0,
                gates_passed=tuple(passed),
                gates_failed=tuple(failed),
                extra={"reason": "pre_write_gate_failure"},
            )

        diff = after - before
        changed_mask = np.abs(diff) > 1e-9
        cells_changed = int(np.sum(changed_mask))
        if cells_changed != plan.predicted_cells_changed:
            failed.append(
                GateFailure(
                    gate="plan_parity",
                    reason=(
                        f"actual cells_changed={cells_changed} != predicted "
                        f"{plan.predicted_cells_changed}"
                    ),
                )
            )
            return PatchResult(
                success=False,
                patch_path=None,
                manifest_path=None,
                sha256=None,
                cells_changed=0,
                gates_passed=tuple(passed),
                gates_failed=tuple(failed),
                extra={"reason": "plan_parity_violation"},
            )

        mutate_table_cells(table, after)
        plan.output_pvv_path.parent.mkdir(parents=True, exist_ok=True)
        write_xml_tree(tree, plan.output_pvv_path)

        integrity_failure, in_cells, out_cells, changed_ids = verify_integrity_or_cleanup(
            plan.output_pvv_path,
            original_root,
            allowed_changed,
            integrity_gate=integrity_gate,
        )
        if integrity_failure is not None:
            failed.append(integrity_failure)
            return PatchResult(
                success=False,
                patch_path=None,
                manifest_path=None,
                sha256=None,
                cells_changed=0,
                gates_passed=tuple(passed),
                gates_failed=tuple(failed),
                extra={"reason": "integrity_violation"},
            )

        passed.append(integrity_gate.name)
        output_sha = sha256(plan.output_pvv_path)

        cell_records: list[dict] = []
        for c_idx in range(table.values.shape[1]):
            if not touched_mask[0, c_idx]:
                continue
            cell_records.append({
                "temp_axis": float(table.col_axis[c_idx]),
                "before": float(before[0, c_idx]),
                "after": float(after[0, c_idx]),
                "delta": float(after[0, c_idx] - before[0, c_idx]),
            })

        manifest_path = plan.output_pvv_path.with_suffix(".manifest.json")
        manifest = {
            "kind": "decel_enleanment_patch",
            "target_item_id": target_id,
            "inputs": {
                "input_pvv": str(plan.input_pvv_path),
                "input_sha256": sha256(plan.input_pvv_path),
            },
            "patch_policy": {
                "hot_threshold": params["hot_threshold"],
                "target_hot": params["target_hot"],
                "per_cell_max_delta": params["per_cell_max_delta"],
                "abs_floor": params["abs_floor"],
                "abs_ceil": params["abs_ceil"],
                "gate_max_delta": params["gate_max_delta"],
            },
            "summary": {
                "cells_touched": int(np.sum(touched_mask)),
                "cells_changed": cells_changed,
                "max_delta": float(np.max(np.abs(diff))) if cells_changed else 0.0,
                "before_min": float(np.min(before)),
                "before_max": float(np.max(before)),
                "after_min": float(np.min(after)),
                "after_max": float(np.max(after)),
            },
            "cells": cell_records,
            "output": {
                "pvv": str(plan.output_pvv_path),
                "sha256": output_sha,
                "changed_ids": changed_ids,
            },
            "finding": {
                "kind": plan.finding.kind,
                "severity": plan.finding.severity,
                "confidence": plan.finding.confidence,
                "source": plan.finding.source,
            },
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return PatchResult(
            success=True,
            patch_path=plan.output_pvv_path,
            manifest_path=manifest_path,
            sha256=output_sha,
            cells_changed=cells_changed,
            gates_passed=tuple(passed),
            gates_failed=(),
            extra={
                "changed_ids": changed_ids,
                "cells_touched": int(np.sum(touched_mask)),
                "max_delta": float(np.max(np.abs(diff))) if cells_changed else 0.0,
            },
        )
