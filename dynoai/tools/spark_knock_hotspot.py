"""SparkKnockHotspot: uniform spark retard over a knock-prone RPM/load zone.

Lifted from `tools/seanbike/patch_spark_knock_hotspot.py` and generalized.

  - Target table: configurable, default `tbl_spark_advance_front_cyl`.
  - Patch zone: cells where RPM >= rpm_min_krpm AND load_axis >= load_min_kpa.
  - Apply: `after = max(floor_deg, before - pull_deg)` uniformly across the zone.
  - Per-cell clamp gate: SparkClampGate with max_retard_deg.
  - Floor gate: in touched cells, post-patch value >= floor_deg.
  - Item integrity gate: only the target table id may change.

Difference vs `spark_feathered_ramp`:
  - Feathered ramp: per-row pull varies along an RPM ramp (0/1/2/3 deg).
  - Knock hotspot: uniform pull across the entire zone.

This tool addresses Finding.kind == "knock_hotspot".
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
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
    FloorGate,
    GateContext,
    GateFailure,
    ItemIntegrityGate,
    SparkClampGate,
)
from dynoai.tools.tool import PatchResult, ToolManifest, ToolPlan, resolve_params

if TYPE_CHECKING:
    from dynoai.diagnostics.detector import DetectionContext


TOOL_NAME = "spark_knock_hotspot"
DEFAULT_TARGET_ITEM_ID = "tbl_spark_advance_front_cyl"
DEFAULT_RPM_MIN_KRPM = 5.0
DEFAULT_LOAD_MIN_KPA = 70.0
DEFAULT_PULL_DEG = 3.0
DEFAULT_FLOOR_DEG = 5.0
DEFAULT_MAX_RETARD_DEG = 3.0

_DEFAULTS: Dict[str, Any] = {
    "target_item_id": DEFAULT_TARGET_ITEM_ID,
    "rpm_min_krpm": DEFAULT_RPM_MIN_KRPM,
    "load_min_kpa": DEFAULT_LOAD_MIN_KPA,
    "pull_deg": DEFAULT_PULL_DEG,
    "floor_deg": DEFAULT_FLOOR_DEG,
    "max_retard_deg": DEFAULT_MAX_RETARD_DEG,
}


def _compute_patch(
    table: TableData,
    *,
    rpm_min_krpm: float,
    load_min_kpa: float,
    pull_deg: float,
    floor_deg: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    before = table.values.copy()
    rpm_mask = table.row_axis[:, None] >= (rpm_min_krpm - 1e-9)
    load_mask = table.col_axis[None, :] >= (load_min_kpa - 1e-9)
    patch_mask = rpm_mask & load_mask
    after = before.copy()
    after[patch_mask] = np.maximum(floor_deg, after[patch_mask] - pull_deg)
    return before, after, patch_mask


class SparkKnockHotspotTool:
    """Uniform spark retard over a knock-prone RPM/load zone (front cyl by default)."""

    name = TOOL_NAME

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name=self.name,
            description=(
                "Uniform spark pull across cells where RPM >= rpm_min_krpm "
                "AND load_axis >= load_min_kpa. Single-zone hotspot guard "
                "for a known knock-prone region."
            ),
            fix_kinds=("knock_hotspot",),
            inputs_schema={
                "target_item_id": {"type": "string", "default": DEFAULT_TARGET_ITEM_ID},
                "rpm_min_krpm": {"type": "number", "default": DEFAULT_RPM_MIN_KRPM},
                "load_min_kpa": {"type": "number", "default": DEFAULT_LOAD_MIN_KPA},
                "pull_deg": {"type": "number", "default": DEFAULT_PULL_DEG},
                "floor_deg": {"type": "number", "default": DEFAULT_FLOOR_DEG},
                "max_retard_deg": {"type": "number", "default": DEFAULT_MAX_RETARD_DEG},
            },
            safety_gate_names=("spark_clamp", "floor", "item_integrity"),
            requires_profile_keys=("tool_overrides.spark_knock_hotspot",),
        )

    def plan(self, finding: Finding, ctx: "DetectionContext") -> ToolPlan:
        params = resolve_params(_DEFAULTS, ctx.vehicle_profile, finding, TOOL_NAME)
        root = ET.parse(ctx.base_pvv_path).getroot()
        table = parse_table(root, params["target_item_id"])
        before, after, patch_mask = _compute_patch(
            table,
            rpm_min_krpm=float(params["rpm_min_krpm"]),
            load_min_kpa=float(params["load_min_kpa"]),
            pull_deg=float(params["pull_deg"]),
            floor_deg=float(params["floor_deg"]),
        )
        diff = before - after
        changed_mask = np.abs(diff) > 1e-9
        cells_changed = int(np.sum(changed_mask))
        max_delta = float(np.max(diff)) if changed_mask.any() else 0.0
        output_dir = ctx.iteration_dir / "patches"
        output_name = ctx.base_pvv_path.stem + "_sparkguard.pvv"
        return ToolPlan(
            tool=self.name,
            finding=finding,
            bound_params=params,
            input_pvv_path=ctx.base_pvv_path,
            output_pvv_path=output_dir / output_name,
            predicted_cells_changed=cells_changed,
            predicted_max_delta={"spark_deg": max_delta},
            risk_score=min(1.0, max_delta / max(float(params["max_retard_deg"]), 1e-9)),
        )

    def apply(self, plan: ToolPlan, ctx: "DetectionContext") -> PatchResult:
        params = dict(plan.bound_params)
        target_id = params["target_item_id"]
        allowed_changed = {target_id}

        original_root = ET.parse(plan.input_pvv_path).getroot()
        tree = ET.parse(plan.input_pvv_path)
        root = tree.getroot()
        table = parse_table(root, target_id)

        before, after, patch_mask = _compute_patch(
            table,
            rpm_min_krpm=float(params["rpm_min_krpm"]),
            load_min_kpa=float(params["load_min_kpa"]),
            pull_deg=float(params["pull_deg"]),
            floor_deg=float(params["floor_deg"]),
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

        indices = np.argwhere(patch_mask)
        cells = [
            {
                "rpm": float(table.row_axis[r] * 1000.0),
                "load_axis_value": float(table.col_axis[c]),
                "before": float(before[r, c]),
                "after": float(after[r, c]),
                "delta_deg": float(before[r, c] - after[r, c]),
            }
            for r, c in indices
        ]
        max_pull = float(np.max(diff)) if cells_changed else 0.0
        mean_pull = (
            float(np.mean(diff[patch_mask])) if patch_mask.any() else 0.0
        )
        cells_targeted = int(np.sum(patch_mask))

        manifest_path = plan.output_pvv_path.with_suffix(".manifest.json")
        manifest = {
            "kind": "spark_hotspot_guard_patch",
            "target_item_id": target_id,
            "inputs": {
                "input_pvv": str(plan.input_pvv_path),
                "input_sha256": sha256(plan.input_pvv_path),
            },
            "patch_policy": {
                "rpm_min_krpm": params["rpm_min_krpm"],
                "load_axis_min": params["load_min_kpa"],
                "pull_deg": params["pull_deg"],
                "floor_deg": params["floor_deg"],
                "max_retard_deg": params["max_retard_deg"],
            },
            "summary": {
                "cells_targeted": cells_targeted,
                "max_pull_deg": max_pull,
                "mean_pull_deg": mean_pull,
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
            extra={
                "changed_ids": changed_ids,
                "cells_targeted": cells_targeted,
                "max_pull_deg": max_pull,
                "mean_pull_deg": mean_pull,
            },
        )
