"""SparkFeatheredRamp: monotone-preserving high-load spark pull, per-row.

Lifted from `tools/seanbike/patch_spark_feathered_ramp.py` and generalized.

  - Reads ramp / load gate / floor from ToolPlan.bound_params, with safe
    defaults that match the seanbike reference output (input SHA
    1fbaad31... -> output SHA b5a69006...).
  - Reads per-vehicle overrides from
    `vehicle_profile["tool_overrides"]["spark_feathered_ramp"]` if present.
  - Runs SparkClampGate, FloorGate, and ItemIntegrityGate before writing.
    Aborts without writing on any gate failure.

Target Item: configurable via bound_params["target_item_id"], default
`tbl_spark_advance_front_cyl` (front cylinder). Only that one Item id may
change; all other table values are preserved byte-identical via surgical
xml.etree mutation.

This tool addresses Finding.kind == "spark_valley".
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Sequence, Tuple

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
    FloorGate,
    GateContext,
    GateFailure,
    ItemIntegrityGate,
    SparkClampGate,
)
from dynoai.tools.tool import PatchResult, ToolManifest, ToolPlan, resolve_params

if TYPE_CHECKING:
    from dynoai.diagnostics.detector import DetectionContext


TOOL_NAME = "spark_feathered_ramp"
DEFAULT_TARGET_ITEM_ID = "tbl_spark_advance_front_cyl"
DEFAULT_LOAD_MIN_KPA = 70.0
DEFAULT_FLOOR_DEG = 5.0
DEFAULT_MAX_RETARD_DEG = 3.0
DEFAULT_RAMP: Tuple[Tuple[float, float], ...] = (
    (4.5, 0.0),
    (5.0, 1.0),
    (5.5, 2.0),
    (6.0, 3.0),
)

_DEFAULTS: Dict[str, Any] = {
    "target_item_id": DEFAULT_TARGET_ITEM_ID,
    "load_min_kpa": DEFAULT_LOAD_MIN_KPA,
    "floor_deg": DEFAULT_FLOOR_DEG,
    "max_retard_deg": DEFAULT_MAX_RETARD_DEG,
    "ramp": [list(kv) for kv in DEFAULT_RAMP],
}


def _normalize_ramp(ramp: Any) -> List[Tuple[float, float]]:
    return [(float(r), float(p)) for r, p in ramp]


def _pull_for_rpm(rpm_krpm: float, ramp: Sequence[Tuple[float, float]]) -> float:
    ramp_sorted = sorted(ramp, key=lambda kv: kv[0])
    if rpm_krpm < ramp_sorted[0][0]:
        return 0.0
    if rpm_krpm >= ramp_sorted[-1][0]:
        return ramp_sorted[-1][1]
    for (r_lo, p_lo), (r_hi, p_hi) in zip(ramp_sorted, ramp_sorted[1:]):
        if r_lo <= rpm_krpm <= r_hi:
            if r_hi == r_lo:
                return p_hi
            t = (rpm_krpm - r_lo) / (r_hi - r_lo)
            return p_lo + t * (p_hi - p_lo)
    return 0.0


def _compute_patch(
    table: TableData,
    *,
    load_min_kpa: float,
    floor_deg: float,
    ramp: Sequence[Tuple[float, float]],
) -> Tuple[np.ndarray, np.ndarray, list[dict]]:
    """Pure computation: returns (before, after, per_row_schedule).

    Algorithm matches the seanbike reference script byte-for-byte so the
    output SHA is preserved.
    """
    before = table.values.copy()
    after = before.copy()
    load_mask = table.col_axis >= (load_min_kpa - 1e-9)
    per_row_pull = np.array(
        [_pull_for_rpm(float(r), ramp) for r in table.row_axis]
    )
    row_schedule: list[dict] = []
    for r_idx, rpm_krpm in enumerate(table.row_axis):
        pull = float(per_row_pull[r_idx])
        if pull <= 0.0:
            continue
        for c_idx, in_load in enumerate(load_mask):
            if not in_load:
                continue
            new_val = max(floor_deg, before[r_idx, c_idx] - pull)
            after[r_idx, c_idx] = new_val
        row_schedule.append(
            {
                "rpm": int(round(float(rpm_krpm) * 1000.0)),
                "pull_deg": pull,
            }
        )
    return before, after, row_schedule


class SparkFeatheredRampTool:
    """Monotone-preserving high-load spark pull (front cylinder by default)."""

    name = TOOL_NAME

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name=self.name,
            description=(
                "Per-row feathered spark pull at high load. Replaces a hard step "
                "in the timing ramp with a linear pull schedule, preserving "
                "monotonicity into the knock-hotspot RPM band."
            ),
            fix_kinds=("spark_valley",),
            inputs_schema={
                "target_item_id": {"type": "string", "default": DEFAULT_TARGET_ITEM_ID},
                "load_min_kpa": {"type": "number", "default": DEFAULT_LOAD_MIN_KPA},
                "floor_deg": {"type": "number", "default": DEFAULT_FLOOR_DEG},
                "max_retard_deg": {"type": "number", "default": DEFAULT_MAX_RETARD_DEG},
                "ramp": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                    "default": [list(kv) for kv in DEFAULT_RAMP],
                },
            },
            safety_gate_names=("spark_clamp", "floor", "item_integrity"),
            requires_profile_keys=("tool_overrides.spark_feathered_ramp",),
        )

    def plan(self, finding: Finding, ctx: "DetectionContext") -> ToolPlan:
        params = resolve_params(_DEFAULTS, ctx.vehicle_profile, finding, TOOL_NAME)
        params["ramp"] = _normalize_ramp(params["ramp"])
        target_id = params["target_item_id"]
        root = ET.parse(ctx.base_pvv_path).getroot()
        table = parse_table(root, target_id)
        before, after, _ = _compute_patch(
            table,
            load_min_kpa=params["load_min_kpa"],
            floor_deg=params["floor_deg"],
            ramp=params["ramp"],
        )
        diff = before - after
        patched_mask = np.abs(diff) > 1e-9
        cells_changed = int(np.sum(patched_mask))
        max_delta = float(np.max(diff)) if patched_mask.any() else 0.0
        output_dir = ctx.iteration_dir / "patches"
        output_name = ctx.base_pvv_path.stem + "_sparkramp.pvv"
        return ToolPlan(
            tool=self.name,
            finding=finding,
            bound_params=params,
            input_pvv_path=ctx.base_pvv_path,
            output_pvv_path=output_dir / output_name,
            predicted_cells_changed=cells_changed,
            predicted_max_delta={"spark_deg": max_delta},
            risk_score=min(1.0, max_delta / max(params["max_retard_deg"], 1e-9)),
        )

    def apply(self, plan: ToolPlan, ctx: "DetectionContext") -> PatchResult:
        params = dict(plan.bound_params)
        target_id = params["target_item_id"]
        allowed_changed = {target_id}

        original_root = ET.parse(plan.input_pvv_path).getroot()
        tree = ET.parse(plan.input_pvv_path)
        root = tree.getroot()
        table = parse_table(root, target_id)

        before, after, row_schedule = _compute_patch(
            table,
            load_min_kpa=params["load_min_kpa"],
            floor_deg=params["floor_deg"],
            ramp=params["ramp"],
        )

        gate_ctx = GateContext(
            target_item_id=target_id,
            allowed_changed_ids=allowed_changed,
            profile=ctx.vehicle_profile,
        )
        spark_gate = SparkClampGate(max_retard_deg=float(params["max_retard_deg"]))
        floor_gate = FloorGate(min_value=float(params["floor_deg"]))
        integrity_gate = ItemIntegrityGate()

        passed: list[str] = []
        failed: list[GateFailure] = []

        for gate in (spark_gate, floor_gate):
            failure = gate.check(before, after, gate_ctx)
            if failure is None:
                passed.append(gate.name)
            else:
                failed.append(failure)

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

        diff = before - after
        patched_mask = np.abs(diff) > 1e-9
        cells_changed = int(np.sum(patched_mask))

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

        changed_indices = np.argwhere(patched_mask)
        cells = [
            {
                "rpm": int(round(float(table.row_axis[r]) * 1000.0)),
                "load_axis_value": float(table.col_axis[c]),
                "before": float(before[r, c]),
                "after": float(after[r, c]),
                "delta_deg": float(before[r, c] - after[r, c]),
            }
            for r, c in changed_indices
        ]
        max_pull = float(np.max(diff)) if cells_changed else 0.0
        mean_pull_changed = (
            float(np.mean(diff[patched_mask])) if cells_changed else 0.0
        )

        manifest_path = plan.output_pvv_path.with_suffix(".manifest.json")
        manifest = {
            "kind": "spark_feathered_ramp_patch",
            "target_item_id": target_id,
            "inputs": {
                "input_pvv": str(plan.input_pvv_path),
                "input_sha256": sha256(plan.input_pvv_path),
            },
            "patch_policy": {
                "load_axis_min": params["load_min_kpa"],
                "floor_deg": params["floor_deg"],
                "max_retard_deg": params["max_retard_deg"],
                "rpm_pull_ramp_krpm_deg": params["ramp"],
                "per_row_pull_schedule": row_schedule,
            },
            "summary": {
                "cells_modified": cells_changed,
                "max_pull_deg": max_pull,
                "mean_pull_deg_in_changed_cells": mean_pull_changed,
                "front_min_before": float(np.min(before)),
                "front_max_before": float(np.max(before)),
                "front_min_after": float(np.min(after)),
                "front_max_after": float(np.max(after)),
            },
            "cells": cells,
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
            extra={"changed_ids": changed_ids},
        )
