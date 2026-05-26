"""IdleVeScale: intentionally lean out the idle/low-load VE region.

Lifted from `tools/seanbike/patch_idle_ve.py`.

Different intent from `gp_smooth_idle_cruise_ve`:
  - `gp_smooth_idle_cruise_ve` denoises noisy idle/cruise cells with a GP
    posterior mean clamped to +/-5% of original.
  - `idle_ve_scale` *intentionally reduces* idle-zone VE (default 25% cut)
    to cure rich-idle smoke and idle stability on stage-tuned bikes.
    WOT and cruise stay untouched.

Zone shape:
  - Strict idle (RPM <= idle_rpm_max AND TPS <= idle_tps_max):
        scale = idle_scale (default 0.75 = 25% VE reduction)
  - Transition (RPM in [idle_rpm_max, trans_rpm_max] AND TPS in
    [idle_tps_max, trans_tps_max]):
        scale = idle_scale + (1.0 - idle_scale) * max(rpm_frac, tps_frac)
  - WOT / cruise (RPM > trans_rpm_max OR TPS > trans_tps_max):
        scale = 1.0 (no change)

Applied identically to both front and rear VE tables (preserves cylinder
balance). Sanity range on idle_scale: [0.50, 0.95].

Addresses Finding.kind == "idle_rich".
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Tuple

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
    GateFailure,
    ItemIntegrityGate,
    VeClampGate,
)
from dynoai.tools.tool import PatchResult, ToolManifest, ToolPlan, resolve_params

if TYPE_CHECKING:
    from dynoai.diagnostics.detector import DetectionContext


TOOL_NAME = "idle_ve_scale"
DEFAULT_VE_FRONT_ID = "tbl_ve_tps_based_front_cyl"
DEFAULT_VE_REAR_ID = "tbl_ve_tps_based_rear_cyl"
DEFAULT_IDLE_SCALE = 0.75
DEFAULT_IDLE_RPM_MAX = 1.5    # kRPM
DEFAULT_IDLE_TPS_MAX = 10.0   # %
DEFAULT_TRANS_RPM_MAX = 2.0   # kRPM
DEFAULT_TRANS_TPS_MAX = 20.0  # %
DEFAULT_VE_CLAMP_GATE_PCT = 30.0  # 25% reduction is the policy; gate at 30% catches bugs

SANITY_SCALE_MIN = 0.50
SANITY_SCALE_MAX = 0.95

_DEFAULTS: Dict[str, Any] = {
    "ve_front_id": DEFAULT_VE_FRONT_ID,
    "ve_rear_id": DEFAULT_VE_REAR_ID,
    "idle_scale": DEFAULT_IDLE_SCALE,
    "idle_rpm_max": DEFAULT_IDLE_RPM_MAX,
    "idle_tps_max": DEFAULT_IDLE_TPS_MAX,
    "trans_rpm_max": DEFAULT_TRANS_RPM_MAX,
    "trans_tps_max": DEFAULT_TRANS_TPS_MAX,
    "ve_clamp_gate_pct": DEFAULT_VE_CLAMP_GATE_PCT,
}


def _cell_scale(
    rpm_k: float,
    tps: float,
    idle_scale: float,
    *,
    idle_rpm_max: float,
    idle_tps_max: float,
    trans_rpm_max: float,
    trans_tps_max: float,
) -> float:
    """Per-cell scale factor. Matches seanbike `cell_scale` byte-for-byte."""
    if rpm_k <= idle_rpm_max and tps <= idle_tps_max:
        return idle_scale
    if rpm_k > trans_rpm_max or tps > trans_tps_max:
        return 1.0
    rpm_frac = max(0.0, (rpm_k - idle_rpm_max) / max(trans_rpm_max - idle_rpm_max, 1e-9))
    tps_frac = max(0.0, (tps - idle_tps_max) / max(trans_tps_max - idle_tps_max, 1e-9))
    blend = min(1.0, max(rpm_frac, tps_frac))
    return idle_scale + (1.0 - idle_scale) * blend


def _compute_patch(
    base_root: ET.Element,
    params: Mapping[str, Any],
) -> Dict[str, Any]:
    idle_scale = float(params["idle_scale"])
    if not (SANITY_SCALE_MIN <= idle_scale <= SANITY_SCALE_MAX):
        raise ValueError(
            f"idle_scale {idle_scale} out of sanity range "
            f"[{SANITY_SCALE_MIN}, {SANITY_SCALE_MAX}]"
        )

    zone_kw = {
        "idle_rpm_max": float(params["idle_rpm_max"]),
        "idle_tps_max": float(params["idle_tps_max"]),
        "trans_rpm_max": float(params["trans_rpm_max"]),
        "trans_tps_max": float(params["trans_tps_max"]),
    }

    per_table: Dict[str, Dict[str, Any]] = {}
    for table_id in sorted({params["ve_front_id"], params["ve_rear_id"]}):
        target = parse_table(base_root, table_id)
        before = target.values.copy()
        after = before.copy()
        rows, cols = target.values.shape
        for r_idx in range(rows):
            rpm_k = float(target.row_axis[r_idx])
            for c_idx in range(cols):
                tps = float(target.col_axis[c_idx])
                scale = _cell_scale(rpm_k, tps, idle_scale, **zone_kw)
                if abs(scale - 1.0) < 1e-9:
                    continue
                after[r_idx, c_idx] = before[r_idx, c_idx] * scale
        delta = after - before
        changed_mask = np.abs(delta) > 1e-9
        per_table[table_id] = {
            "table": target,
            "before": before,
            "after": after,
            "delta": delta,
            "cells_changed": int(np.sum(changed_mask)),
        }

    return {
        "per_table": per_table,
        "idle_scale": idle_scale,
        "zone": zone_kw,
    }


class IdleVeScaleTool:
    """Intentionally reduce idle/low-load VE to cure rich-idle smoke."""

    name = TOOL_NAME

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name=self.name,
            description=(
                "Multiplicative idle-zone VE reduction with linear blend "
                "through the transition zone. Cures rich-idle smoke and "
                "idle stability on stage-tuned bikes. WOT and cruise "
                "untouched. Applied identically to front + rear tables."
            ),
            fix_kinds=("idle_rich",),
            inputs_schema={
                "ve_front_id": {"type": "string", "default": DEFAULT_VE_FRONT_ID},
                "ve_rear_id": {"type": "string", "default": DEFAULT_VE_REAR_ID},
                "idle_scale": {
                    "type": "number", "default": DEFAULT_IDLE_SCALE,
                    "description": "Idle-zone VE multiplier (0.75 = 25% reduction)",
                },
                "idle_rpm_max": {"type": "number", "default": DEFAULT_IDLE_RPM_MAX},
                "idle_tps_max": {"type": "number", "default": DEFAULT_IDLE_TPS_MAX},
                "trans_rpm_max": {"type": "number", "default": DEFAULT_TRANS_RPM_MAX},
                "trans_tps_max": {"type": "number", "default": DEFAULT_TRANS_TPS_MAX},
                "ve_clamp_gate_pct": {
                    "type": "number", "default": DEFAULT_VE_CLAMP_GATE_PCT,
                },
            },
            safety_gate_names=("ve_clamp", "item_integrity"),
            requires_profile_keys=("tool_overrides.idle_ve_scale",),
        )

    def plan(self, finding: Finding, ctx: "DetectionContext") -> ToolPlan:
        params = resolve_params(_DEFAULTS, ctx.vehicle_profile, finding, TOOL_NAME)
        base_root = ET.parse(ctx.base_pvv_path).getroot()
        computation = _compute_patch(base_root, params)

        total_changed = sum(
            int(t["cells_changed"]) for t in computation["per_table"].values()
        )
        max_abs_delta = max(
            (float(np.max(np.abs(t["delta"]))) for t in computation["per_table"].values()),
            default=0.0,
        )
        output_dir = ctx.iteration_dir / "patches"
        output_name = ctx.base_pvv_path.stem + "_idle_ve_scale.pvv"
        return ToolPlan(
            tool=self.name,
            finding=finding,
            bound_params=params,
            input_pvv_path=ctx.base_pvv_path,
            output_pvv_path=output_dir / output_name,
            predicted_cells_changed=total_changed,
            predicted_max_delta={"ve_abs": max_abs_delta},
            risk_score=min(
                1.0,
                (1.0 - float(params["idle_scale"]))
                / max(float(params["ve_clamp_gate_pct"]) / 100.0, 1e-9),
            ),
        )

    def apply(self, plan: ToolPlan, ctx: "DetectionContext") -> PatchResult:
        params = dict(plan.bound_params)
        allowed_changed = {params["ve_front_id"], params["ve_rear_id"]}

        original_root = ET.parse(plan.input_pvv_path).getroot()
        tree = ET.parse(plan.input_pvv_path)
        base_root = tree.getroot()
        computation = _compute_patch(base_root, params)

        ve_clamp_gate = VeClampGate(max_pct=float(params["ve_clamp_gate_pct"]))
        integrity_gate = ItemIntegrityGate()

        passed: list[str] = []
        failed: list[GateFailure] = []

        for table_id, t in computation["per_table"].items():
            failure = ve_clamp_gate.check(t["before"], t["after"], None)  # type: ignore[arg-type]
            if failure is not None:
                failed.append(
                    GateFailure(
                        gate=f"ve_clamp[{table_id}]",
                        reason=failure.reason,
                        details=dict(failure.details),
                    )
                )
        if not failed:
            passed.append(ve_clamp_gate.name)

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

        total_changed = sum(
            int(t["cells_changed"]) for t in computation["per_table"].values()
        )
        if total_changed != plan.predicted_cells_changed:
            failed.append(
                GateFailure(
                    gate="plan_parity",
                    reason=(
                        f"actual cells_changed={total_changed} != predicted "
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

        for t in computation["per_table"].values():
            mutate_table_cells(t["table"], t["after"])
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

        table_stats: List[dict] = []
        for table_id, t in computation["per_table"].items():
            mask_changed = np.abs(t["delta"]) > 1e-9
            table_stats.append({
                "table_id": table_id,
                "cells_changed": int(t["cells_changed"]),
                "before_min": float(np.min(t["before"])),
                "before_max": float(np.max(t["before"])),
                "after_min": float(np.min(t["after"])),
                "after_max": float(np.max(t["after"])),
                "delta_max_abs": (
                    float(np.max(np.abs(t["delta"][mask_changed])))
                    if mask_changed.any() else 0.0
                ),
            })

        manifest_path = plan.output_pvv_path.with_suffix(".manifest.json")
        manifest = {
            "kind": "idle_ve_scale_patch",
            "inputs": {
                "input_pvv": str(plan.input_pvv_path),
                "input_sha256": sha256(plan.input_pvv_path),
            },
            "policy": {
                "idle_scale": params["idle_scale"],
                "idle_rpm_max": params["idle_rpm_max"],
                "idle_tps_max": params["idle_tps_max"],
                "trans_rpm_max": params["trans_rpm_max"],
                "trans_tps_max": params["trans_tps_max"],
                "ve_clamp_gate_pct": params["ve_clamp_gate_pct"],
            },
            "summary": {
                "total_cells_changed": total_changed,
                "table_stats": table_stats,
            },
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
            cells_changed=total_changed,
            gates_passed=tuple(passed),
            gates_failed=(),
            extra={
                "changed_ids": changed_ids,
                "idle_scale": float(params["idle_scale"]),
                "table_stats": table_stats,
            },
        )
