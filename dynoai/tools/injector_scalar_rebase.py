"""InjectorScalarRebase: rewrite injector + displacement scalars, preserve WOT fuel.

Lifted from `tools/seanbike/patch_stock_injectors_110_preserve_wot.py`.

This is the first lifted tool that mutates *scalars* (single-cell Items)
in addition to table cells. Specifically:

  - Rewrites `tbl_injector_size` (lb/hr) from the current value to a new
    value computed from `injector_gps` (grams/second).
  - Rewrites `tbl_engine_displacement` (CID) from the current value to
    `displacement_cid`.
  - Computes a `preserve_factor` such that effective WOT fueling stays
    the same after the scalar change:
        preserve_factor = (old_disp / old_inj) * (new_inj / new_disp)
  - Applies a *zone-blended* version of preserve_factor across both VE
    tables:
      - Idle zone (RPM <= 1.5 kRPM AND TPS <= 10%): factor = 1.0
        (VE preserved; idle becomes LEANER with the new scalar, which is
        intentional — kills rich idle / black smoke).
      - Main/load zone (RPM >= 2.0 kRPM OR TPS >= 25%): factor =
        preserve_factor (full WOT preservation).
      - Transition between: linear blend on RPM and TPS.

Four target Item ids may change:
  - `tbl_injector_size`
  - `tbl_engine_displacement`
  - `tbl_ve_tps_based_front_cyl`
  - `tbl_ve_tps_based_rear_cyl`

Safety gates:
  - `max_ve_block` (default 170.0): hard fail-closed if any post-patch VE
    cell exceeds this. The seanbike script raises an exception at this
    threshold; the framework version returns PatchResult(success=False).
  - `max_ve_warn` (default 155.0): informational only, recorded in the
    manifest. Does NOT block writes.
  - `ItemIntegrityGate`: verifies only the four allowed item ids changed.

Addresses Finding.kind == "injector_calibration".
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Tuple

import numpy as np

from dynoai.diagnostics.finding import Finding
from dynoai.pvv.io import (
    TableData,
    mutate_scalar,
    mutate_table_cells,
    parse_scalar,
    parse_table,
    sha256,
    verify_integrity_or_cleanup,
    write_xml_tree,
)
from dynoai.tools.gates import (
    GateFailure,
    ItemIntegrityGate,
)
from dynoai.tools.tool import PatchResult, ToolManifest, ToolPlan, resolve_params

if TYPE_CHECKING:
    from dynoai.diagnostics.detector import DetectionContext


TOOL_NAME = "injector_scalar_rebase"
DEFAULT_VE_FRONT_ID = "tbl_ve_tps_based_front_cyl"
DEFAULT_VE_REAR_ID = "tbl_ve_tps_based_rear_cyl"
DEFAULT_INJECTOR_ID = "tbl_injector_size"
DEFAULT_DISPLACEMENT_ID = "tbl_engine_displacement"

DEFAULT_INJECTOR_GPS = 3.91          # grams/second
DEFAULT_DISPLACEMENT_CID = 110.0     # cubic inches
DEFAULT_MAX_VE_WARN = 155.0
DEFAULT_MAX_VE_BLOCK = 170.0

# Idle zone definition (factor=1.0 inside, blended on edges).
DEFAULT_IDLE_RPM_KRPM = 1.5
DEFAULT_IDLE_TPS_PCT = 10.0
# Main zone definition (factor=preserve_factor inside, blended on edges).
DEFAULT_MAIN_RPM_KRPM = 2.0
DEFAULT_MAIN_TPS_PCT = 25.0

# Stock injector range sanity check, matches seanbike script.
INJECTOR_SANITY_MIN_LB_HR = 25.0
INJECTOR_SANITY_MAX_LB_HR = 36.0
DISPLACEMENT_SANITY_MIN_CID = 95.0
DISPLACEMENT_SANITY_MAX_CID = 120.0

# Conversion constant: matches seanbike script byte-for-byte.
G_PER_SEC_TO_LB_PER_HR = 3600.0 / 453.59237


_DEFAULTS: Dict[str, Any] = {
    "ve_front_id": DEFAULT_VE_FRONT_ID,
    "ve_rear_id": DEFAULT_VE_REAR_ID,
    "injector_id": DEFAULT_INJECTOR_ID,
    "displacement_id": DEFAULT_DISPLACEMENT_ID,
    "injector_gps": DEFAULT_INJECTOR_GPS,
    "displacement_cid": DEFAULT_DISPLACEMENT_CID,
    "max_ve_warn": DEFAULT_MAX_VE_WARN,
    "max_ve_block": DEFAULT_MAX_VE_BLOCK,
    "idle_rpm_krpm": DEFAULT_IDLE_RPM_KRPM,
    "idle_tps_pct": DEFAULT_IDLE_TPS_PCT,
    "main_rpm_krpm": DEFAULT_MAIN_RPM_KRPM,
    "main_tps_pct": DEFAULT_MAIN_TPS_PCT,
}


def _blend_factor(
    rpm_k: float,
    tps: float,
    preserve_factor: float,
    *,
    idle_rpm: float,
    idle_tps: float,
    main_rpm: float,
    main_tps: float,
) -> float:
    """Piecewise blend: idle stays 1.0, main gets preserve_factor, linear edge.

    Matches the seanbike script's `blend_factor` byte-for-byte.
    """
    if rpm_k <= idle_rpm and tps <= idle_tps:
        return 1.0
    if rpm_k >= main_rpm or tps >= main_tps:
        return preserve_factor
    rpm_blend = max(0.0, min(1.0, (rpm_k - idle_rpm) / max(main_rpm - idle_rpm, 1e-9)))
    tps_blend = max(0.0, min(1.0, (tps - idle_tps) / max(main_tps - idle_tps, 1e-9)))
    blend = max(rpm_blend, tps_blend)
    return 1.0 + (preserve_factor - 1.0) * blend


def _compute_patch(
    base_root: ET.Element,
    params: Mapping[str, Any],
) -> Dict[str, Any]:
    old_injector = parse_scalar(base_root, params["injector_id"])
    old_displacement = parse_scalar(base_root, params["displacement_id"])
    new_injector_gps = float(params["injector_gps"])
    new_injector_lb_hr = new_injector_gps * G_PER_SEC_TO_LB_PER_HR
    new_displacement = float(params["displacement_cid"])

    if not (INJECTOR_SANITY_MIN_LB_HR <= new_injector_lb_hr <= INJECTOR_SANITY_MAX_LB_HR):
        raise ValueError(
            f"converted injector {new_injector_lb_hr:.3f} lb/hr outside "
            f"sanity range [{INJECTOR_SANITY_MIN_LB_HR}, {INJECTOR_SANITY_MAX_LB_HR}]"
        )
    if not (DISPLACEMENT_SANITY_MIN_CID <= new_displacement <= DISPLACEMENT_SANITY_MAX_CID):
        raise ValueError(
            f"displacement {new_displacement:.3f} CID outside sanity range "
            f"[{DISPLACEMENT_SANITY_MIN_CID}, {DISPLACEMENT_SANITY_MAX_CID}]"
        )

    if old_injector <= 0 or new_displacement <= 0:
        raise ValueError("non-positive injector or displacement; cannot rebase")

    preserve_factor = (
        (old_displacement / old_injector)
        * (new_injector_lb_hr / new_displacement)
    )

    idle_rpm = float(params["idle_rpm_krpm"])
    idle_tps = float(params["idle_tps_pct"])
    main_rpm = float(params["main_rpm_krpm"])
    main_tps = float(params["main_tps_pct"])

    per_table: Dict[str, Dict[str, Any]] = {}
    for table_id in sorted({params["ve_front_id"], params["ve_rear_id"]}):
        target = parse_table(base_root, table_id)
        before = target.values.copy()
        after = before.copy()
        for r_idx, rpm_k in enumerate(target.row_axis):
            for c_idx, tps in enumerate(target.col_axis):
                factor = _blend_factor(
                    float(rpm_k),
                    float(tps),
                    preserve_factor,
                    idle_rpm=idle_rpm,
                    idle_tps=idle_tps,
                    main_rpm=main_rpm,
                    main_tps=main_tps,
                )
                after[r_idx, c_idx] = before[r_idx, c_idx] * factor
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
        "old_injector_lb_hr": old_injector,
        "old_displacement_cid": old_displacement,
        "new_injector_lb_hr": new_injector_lb_hr,
        "new_displacement_cid": new_displacement,
        "preserve_factor": preserve_factor,
    }


class InjectorScalarRebaseTool:
    """Rewrite injector + displacement scalars, preserving WOT effective fueling."""

    name = TOOL_NAME

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name=self.name,
            description=(
                "Rewrite tbl_injector_size + tbl_engine_displacement scalars "
                "to match real hardware. Compensates VE tables via a zone-"
                "blended preserve_factor so effective WOT fueling is "
                "preserved while idle gets leaner with the corrected "
                "scalars (intentional — kills rich idle and black smoke)."
            ),
            fix_kinds=("injector_calibration",),
            inputs_schema={
                "ve_front_id": {"type": "string", "default": DEFAULT_VE_FRONT_ID},
                "ve_rear_id": {"type": "string", "default": DEFAULT_VE_REAR_ID},
                "injector_id": {"type": "string", "default": DEFAULT_INJECTOR_ID},
                "displacement_id": {"type": "string", "default": DEFAULT_DISPLACEMENT_ID},
                "injector_gps": {
                    "type": "number", "default": DEFAULT_INJECTOR_GPS,
                    "description": "Target injector flow in grams/sec",
                },
                "displacement_cid": {
                    "type": "number", "default": DEFAULT_DISPLACEMENT_CID,
                    "description": "Target engine displacement in cubic inches",
                },
                "max_ve_warn": {"type": "number", "default": DEFAULT_MAX_VE_WARN},
                "max_ve_block": {"type": "number", "default": DEFAULT_MAX_VE_BLOCK},
                "idle_rpm_krpm": {"type": "number", "default": DEFAULT_IDLE_RPM_KRPM},
                "idle_tps_pct": {"type": "number", "default": DEFAULT_IDLE_TPS_PCT},
                "main_rpm_krpm": {"type": "number", "default": DEFAULT_MAIN_RPM_KRPM},
                "main_tps_pct": {"type": "number", "default": DEFAULT_MAIN_TPS_PCT},
            },
            safety_gate_names=("max_ve_block", "item_integrity"),
            requires_profile_keys=("tool_overrides.injector_scalar_rebase",),
        )

    def plan(self, finding: Finding, ctx: "DetectionContext") -> ToolPlan:
        params = resolve_params(_DEFAULTS, ctx.vehicle_profile, finding, TOOL_NAME)
        base_root = ET.parse(ctx.base_pvv_path).getroot()
        computation = _compute_patch(base_root, params)

        total_changed = sum(
            int(t["cells_changed"]) for t in computation["per_table"].values()
        )
        max_delta = max(
            (float(np.max(np.abs(t["delta"]))) for t in computation["per_table"].values()),
            default=0.0,
        )
        max_after = max(
            (float(np.max(t["after"])) for t in computation["per_table"].values()),
            default=0.0,
        )
        output_dir = ctx.iteration_dir / "patches"
        output_name = ctx.base_pvv_path.stem + "_injector_rebase.pvv"
        return ToolPlan(
            tool=self.name,
            finding=finding,
            bound_params=params,
            input_pvv_path=ctx.base_pvv_path,
            output_pvv_path=output_dir / output_name,
            predicted_cells_changed=total_changed,
            predicted_max_delta={
                "ve_abs": max_delta,
                "ve_max_after": max_after,
                "preserve_factor": float(computation["preserve_factor"]),
            },
            risk_score=min(
                1.0,
                max_after / max(float(params["max_ve_block"]), 1e-9),
            ),
        )

    def apply(self, plan: ToolPlan, ctx: "DetectionContext") -> PatchResult:
        params = dict(plan.bound_params)
        allowed_changed = {
            params["ve_front_id"],
            params["ve_rear_id"],
            params["injector_id"],
            params["displacement_id"],
        }

        original_root = ET.parse(plan.input_pvv_path).getroot()
        tree = ET.parse(plan.input_pvv_path)
        base_root = tree.getroot()
        computation = _compute_patch(base_root, params)

        max_after = float(
            max(np.max(t["after"]) for t in computation["per_table"].values())
        )
        max_ve_block = float(params["max_ve_block"])
        max_ve_warn = float(params["max_ve_warn"])

        passed: list[str] = []
        failed: list[GateFailure] = []

        if max_after > max_ve_block + 1e-9:
            failed.append(
                GateFailure(
                    gate="max_ve_block",
                    reason=(
                        f"max post-patch VE {max_after:.3f} exceeds hard block "
                        f"{max_ve_block:.3f}"
                    ),
                    details={"max_after": max_after, "block": max_ve_block},
                )
            )
        else:
            passed.append("max_ve_block")

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

        # Mutate scalars + tables in the tree.
        mutate_scalar(base_root, params["injector_id"], computation["new_injector_lb_hr"])
        mutate_scalar(base_root, params["displacement_id"], computation["new_displacement_cid"])
        for t in computation["per_table"].values():
            mutate_table_cells(t["table"], t["after"])

        plan.output_pvv_path.parent.mkdir(parents=True, exist_ok=True)
        write_xml_tree(tree, plan.output_pvv_path)

        integrity_gate = ItemIntegrityGate()
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

        # Build per-table stats for the manifest.
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

        # Surface the warn level in the manifest (not a hard fail).
        warnings: List[str] = []
        if max_after > max_ve_warn + 1e-9:
            warnings.append(
                f"max VE {max_after:.3f} exceeds warn threshold {max_ve_warn:.3f}"
            )

        manifest_path = plan.output_pvv_path.with_suffix(".manifest.json")
        manifest = {
            "kind": "injector_scalar_rebase_patch",
            "inputs": {
                "input_pvv": str(plan.input_pvv_path),
                "input_sha256": sha256(plan.input_pvv_path),
            },
            "scalars": {
                "old_injector_lb_hr": computation["old_injector_lb_hr"],
                "old_displacement_cid": computation["old_displacement_cid"],
                "new_injector_lb_hr": computation["new_injector_lb_hr"],
                "new_displacement_cid": computation["new_displacement_cid"],
                "new_injector_gps": float(params["injector_gps"]),
                "preserve_factor": float(computation["preserve_factor"]),
            },
            "blend_zones": {
                "idle_rpm_krpm": float(params["idle_rpm_krpm"]),
                "idle_tps_pct": float(params["idle_tps_pct"]),
                "main_rpm_krpm": float(params["main_rpm_krpm"]),
                "main_tps_pct": float(params["main_tps_pct"]),
            },
            "safety_thresholds": {
                "max_ve_warn": max_ve_warn,
                "max_ve_block": max_ve_block,
            },
            "summary": {
                "total_cells_changed": total_changed,
                "max_post_patch_ve": max_after,
                "table_stats": table_stats,
            },
            "warnings": warnings,
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
                "preserve_factor": float(computation["preserve_factor"]),
                "max_post_patch_ve": max_after,
                "warnings": warnings,
            },
        )
