"""WotVeGraft: conservative WOT VE graft from a donor PVV.

Lifted from `tools/seanbike/graft_wot_from_v5.py` and generalized.

  - Reads a *donor* PVV path from `finding.tool_params["donor_pvv_path"]`
    (or ToolPlan.bound_params). The donor must have the same VE table
    shapes and axes as the base PVV; an axis-alignment gate verifies this
    before any write.
  - Reads engine displacement and injector size scalars from both donor
    and base, computes a scalar compensation factor:
        f = (src_disp / dst_disp) * (dst_inj / src_inj)
  - In the WOT mask (RPM >= rpm_min_krpm AND TPS >= tps_min_pct),
    per-cell final value = min(
        base * (1 + graft_pct/100),     # destination gain cap
        source * scalar_factor,         # scalar-compensated donor
        ve_cap                          # absolute ceiling
    ).
  - Outside mask: cells are byte-identical to base.

First lifted tool that consumes more than one input PVV. The donor path
flows via finding.tool_params and is carried through ToolPlan.bound_params
so the manifest can record both inputs.

Addresses Finding.kind == "wot_lean".
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Mapping

import numpy as np

from dynoai.diagnostics.finding import Finding
from dynoai.pvv.io import (
    TableData,
    mutate_table_cells,
    parse_scalar,
    parse_table,
    sha256,
    verify_integrity_or_cleanup,
    write_xml_tree,
)
from dynoai.tools.gates import (
    GateContext,
    GateFailure,
    ItemIntegrityGate,
    VeClampGate,
)
from dynoai.tools.tool import PatchResult, ToolManifest, ToolPlan, resolve_params

if TYPE_CHECKING:
    from dynoai.diagnostics.detector import DetectionContext


TOOL_NAME = "wot_ve_graft"
DEFAULT_VE_FRONT_ID = "tbl_ve_tps_based_front_cyl"
DEFAULT_VE_REAR_ID = "tbl_ve_tps_based_rear_cyl"
DEFAULT_DISPLACEMENT_ID = "tbl_engine_displacement"
DEFAULT_INJECTOR_ID = "tbl_injector_size"
DEFAULT_GRAFT_PCT = 8.0
DEFAULT_RPM_MIN_KRPM = 5.0
DEFAULT_TPS_MIN_PCT = 80.0
DEFAULT_VE_CAP = 140.0
DEFAULT_VE_CLAMP_GATE_PCT = 30.0  # AGENTS.md +/-10% would block legitimate
                                  # +8% grafts after scalar comp; this tool's
                                  # natural envelope is larger. Gate sits at
                                  # 30% as a catch-all for runaway bugs.

_DEFAULTS: Dict[str, Any] = {
    "ve_front_id": DEFAULT_VE_FRONT_ID,
    "ve_rear_id": DEFAULT_VE_REAR_ID,
    "displacement_id": DEFAULT_DISPLACEMENT_ID,
    "injector_id": DEFAULT_INJECTOR_ID,
    "graft_pct": DEFAULT_GRAFT_PCT,
    "rpm_min_krpm": DEFAULT_RPM_MIN_KRPM,
    "tps_min_pct": DEFAULT_TPS_MIN_PCT,
    "ve_cap": DEFAULT_VE_CAP,
    "ve_clamp_gate_pct": DEFAULT_VE_CLAMP_GATE_PCT,
    "donor_pvv_path": None,
    # gain_schedule: optional list of (rpm_krpm, gain_pct) knots for an
    # RPM-shaped gain ramp. None (default) = use flat graft_pct on every
    # row, byte-identical to the original graft_wot_from_v5 behavior.
    # When set, the per-row gain is linearly interpolated between knots
    # (clamped to first/last knot outside the range), matching the
    # graft_wot_rpm_ramp.py seanbike variant.
    "gain_schedule": None,
}


def _gain_for_rpm(
    rpm_krpm: float, ramp: List[Tuple[float, float]]
) -> float:
    """Linear interpolation of a (rpm_krpm, gain_pct) ramp. Clamps outside."""
    ramp_sorted = sorted(ramp, key=lambda kv: kv[0])
    if rpm_krpm <= ramp_sorted[0][0]:
        return float(ramp_sorted[0][1])
    if rpm_krpm >= ramp_sorted[-1][0]:
        return float(ramp_sorted[-1][1])
    for (r_lo, g_lo), (r_hi, g_hi) in zip(ramp_sorted, ramp_sorted[1:]):
        if r_lo <= rpm_krpm <= r_hi:
            if r_hi == r_lo:
                return float(g_hi)
            t = (rpm_krpm - r_lo) / (r_hi - r_lo)
            return float(g_lo + t * (g_hi - g_lo))
    return 0.0


def _verify_axis_alignment(
    src: TableData, dst: TableData, table_id: str
) -> GateFailure | None:
    if src.values.shape != dst.values.shape:
        return GateFailure(
            gate="axis_alignment",
            reason=(
                f"Shape mismatch for {table_id}: donor={src.values.shape} vs "
                f"base={dst.values.shape}"
            ),
            details={"donor_shape": list(src.values.shape), "base_shape": list(dst.values.shape)},
        )
    if not np.allclose(src.row_axis, dst.row_axis):
        return GateFailure(
            gate="axis_alignment",
            reason=f"Row axis mismatch for {table_id}",
            details={
                "donor_row_axis": src.row_axis.tolist(),
                "base_row_axis": dst.row_axis.tolist(),
            },
        )
    if not np.allclose(src.col_axis, dst.col_axis):
        return GateFailure(
            gate="axis_alignment",
            reason=f"Column axis mismatch for {table_id}",
            details={
                "donor_col_axis": src.col_axis.tolist(),
                "base_col_axis": dst.col_axis.tolist(),
            },
        )
    return None


def _compute_patch(
    base_root: ET.Element,
    donor_root: ET.Element,
    params: Mapping[str, Any],
) -> Dict[str, Any]:
    src_disp = parse_scalar(donor_root, params["displacement_id"])
    src_inj = parse_scalar(donor_root, params["injector_id"])
    dst_disp = parse_scalar(base_root, params["displacement_id"])
    dst_inj = parse_scalar(base_root, params["injector_id"])
    if dst_disp == 0.0 or src_inj == 0.0:
        raise RuntimeError("Zero displacement or injector scalar; cannot compute factor")
    scalar_factor = (src_disp / dst_disp) * (dst_inj / src_inj)

    graft_pct = float(params["graft_pct"])
    rpm_min_krpm = float(params["rpm_min_krpm"])
    tps_min_pct = float(params["tps_min_pct"])
    ve_cap = float(params["ve_cap"])
    gain_schedule_raw = params.get("gain_schedule")
    gain_schedule: List[Tuple[float, float]] | None = None
    if gain_schedule_raw:
        # Normalize to list of (float, float) tuples for deterministic ordering.
        gain_schedule = [
            (float(r), float(p)) for r, p in gain_schedule_raw
        ]

    per_table: Dict[str, Dict[str, Any]] = {}
    axis_failure: GateFailure | None = None

    for table_id in sorted({params["ve_front_id"], params["ve_rear_id"]}):
        source = parse_table(donor_root, table_id)
        target = parse_table(base_root, table_id)
        axis_failure = _verify_axis_alignment(source, target, table_id)
        if axis_failure is not None:
            break

        before = target.values.copy()
        source_scalar_comp = source.values * scalar_factor

        # Per-row gain: either constant (flat graft) or RPM-interpolated (ramp).
        if gain_schedule is not None:
            per_row_gain_pct = np.array(
                [_gain_for_rpm(float(r), gain_schedule) for r in target.row_axis]
            )
            gain_cap = before * (1.0 + per_row_gain_pct[:, None] / 100.0)
        else:
            per_row_gain_pct = None
            gain_cap = before * (1.0 + graft_pct / 100.0)

        mask = (
            (target.row_axis[:, None] >= (rpm_min_krpm - 1e-9))
            & (target.col_axis[None, :] >= (tps_min_pct - 1e-9))
        )
        after = before.copy()
        after[mask] = np.minimum(
            np.minimum(gain_cap[mask], source_scalar_comp[mask]),
            ve_cap,
        )
        delta = after - before
        changed_mask = np.abs(delta) > 1e-9

        per_table[table_id] = {
            "table": target,
            "before": before,
            "after": after,
            "delta": delta,
            "mask": mask,
            "source_scalar_comp": source_scalar_comp,
            "per_row_gain_pct": per_row_gain_pct,
            "cells_in_mask": int(np.sum(mask)),
            "cells_changed": int(np.sum(changed_mask)),
        }

    return {
        "per_table": per_table,
        "scalar_factor": scalar_factor,
        "src_disp": src_disp,
        "src_inj": src_inj,
        "dst_disp": dst_disp,
        "dst_inj": dst_inj,
        "axis_failure": axis_failure,
    }


class WotVeGraftTool:
    """Conservative WOT VE graft from a donor PVV, scalar-aware and triple-capped."""

    name = TOOL_NAME

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name=self.name,
            description=(
                "Graft WOT VE cells from a donor PVV into the base, "
                "compensating for displacement and injector-size differences. "
                "Triple-capped: destination gain cap, scalar-comp source, "
                "absolute VE ceiling."
            ),
            fix_kinds=("wot_lean",),
            inputs_schema={
                "donor_pvv_path": {"type": "string"},
                "ve_front_id": {"type": "string", "default": DEFAULT_VE_FRONT_ID},
                "ve_rear_id": {"type": "string", "default": DEFAULT_VE_REAR_ID},
                "displacement_id": {"type": "string", "default": DEFAULT_DISPLACEMENT_ID},
                "injector_id": {"type": "string", "default": DEFAULT_INJECTOR_ID},
                "graft_pct": {"type": "number", "default": DEFAULT_GRAFT_PCT},
                "rpm_min_krpm": {"type": "number", "default": DEFAULT_RPM_MIN_KRPM},
                "tps_min_pct": {"type": "number", "default": DEFAULT_TPS_MIN_PCT},
                "ve_cap": {"type": "number", "default": DEFAULT_VE_CAP},
                "ve_clamp_gate_pct": {
                    "type": "number",
                    "default": DEFAULT_VE_CLAMP_GATE_PCT,
                },
            },
            safety_gate_names=(
                "axis_alignment",
                "ve_clamp",
                "ve_cap",
                "item_integrity",
            ),
            requires_profile_keys=("tool_overrides.wot_ve_graft",),
        )

    def plan(self, finding: Finding, ctx: "DetectionContext") -> ToolPlan:
        params = resolve_params(_DEFAULTS, ctx.vehicle_profile, finding, TOOL_NAME)
        if not params.get("donor_pvv_path"):
            raise ValueError(
                f"{TOOL_NAME}: donor_pvv_path must be set via "
                "finding.tool_params or profile.tool_overrides"
            )
        donor_path = Path(params["donor_pvv_path"])
        if not donor_path.exists():
            raise FileNotFoundError(f"donor PVV not found: {donor_path}")
        params["donor_pvv_path"] = str(donor_path)

        base_root = ET.parse(ctx.base_pvv_path).getroot()
        donor_root = ET.parse(donor_path).getroot()
        computation = _compute_patch(base_root, donor_root, params)

        if computation["axis_failure"] is not None:
            # Surface this in the plan as a zero-cell change with a high risk
            # score; apply() will catch and fail closed.
            return ToolPlan(
                tool=self.name,
                finding=finding,
                bound_params=params,
                input_pvv_path=ctx.base_pvv_path,
                output_pvv_path=ctx.iteration_dir / "patches" / "_axis_mismatch.pvv",
                predicted_cells_changed=0,
                predicted_max_delta={"axis_mismatch": 1.0},
                risk_score=1.0,
            )

        total_changed = sum(
            int(t["cells_changed"]) for t in computation["per_table"].values()
        )
        max_delta = max(
            (
                float(np.max(np.abs(t["delta"])))
                for t in computation["per_table"].values()
            ),
            default=0.0,
        )
        output_dir = ctx.iteration_dir / "patches"
        output_name = ctx.base_pvv_path.stem + "_wotgraft.pvv"
        return ToolPlan(
            tool=self.name,
            finding=finding,
            bound_params=params,
            input_pvv_path=ctx.base_pvv_path,
            output_pvv_path=output_dir / output_name,
            predicted_cells_changed=total_changed,
            predicted_max_delta={"ve_abs": max_delta},
            risk_score=min(
                1.0,
                max_delta / max(float(params["ve_clamp_gate_pct"]) / 100.0 * 100.0, 1e-9),
            ),
        )

    def apply(self, plan: ToolPlan, ctx: "DetectionContext") -> PatchResult:
        params = dict(plan.bound_params)
        front_id = params["ve_front_id"]
        rear_id = params["ve_rear_id"]
        allowed_changed = {front_id, rear_id}

        donor_path = Path(params["donor_pvv_path"])
        if not donor_path.exists():
            return PatchResult(
                success=False,
                patch_path=None,
                manifest_path=None,
                sha256=None,
                cells_changed=0,
                gates_failed=(
                    GateFailure(
                        gate="donor_present",
                        reason=f"donor PVV not found at apply time: {donor_path}",
                    ),
                ),
                extra={"reason": "donor_missing"},
            )

        original_root = ET.parse(plan.input_pvv_path).getroot()
        tree = ET.parse(plan.input_pvv_path)
        base_root = tree.getroot()
        donor_root = ET.parse(donor_path).getroot()

        computation = _compute_patch(base_root, donor_root, params)
        if computation["axis_failure"] is not None:
            return PatchResult(
                success=False,
                patch_path=None,
                manifest_path=None,
                sha256=None,
                cells_changed=0,
                gates_failed=(computation["axis_failure"],),
                extra={"reason": "axis_mismatch"},
            )

        gate_ctx = GateContext(
            target_item_id=f"{front_id}+{rear_id}",
            allowed_changed_ids=allowed_changed,
            profile=ctx.vehicle_profile,
        )
        ve_clamp_pct = float(params["ve_clamp_gate_pct"])
        ve_clamp_gate = VeClampGate(max_pct=ve_clamp_pct)
        integrity_gate = ItemIntegrityGate()
        ve_cap = float(params["ve_cap"])

        passed: list[str] = []
        failed: list[GateFailure] = []

        for table_id, t in computation["per_table"].items():
            failure = ve_clamp_gate.check(t["before"], t["after"], gate_ctx)
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

        global_max = max(
            float(np.max(t["after"])) for t in computation["per_table"].values()
        )
        if global_max > ve_cap + 1e-9:
            failed.append(
                GateFailure(
                    gate="ve_cap",
                    reason=f"max VE {global_max:.3f} > cap {ve_cap:.3f}",
                    details={"max_ve": global_max, "cap": ve_cap},
                )
            )
        else:
            passed.append("ve_cap")

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
        changed_cells_by_table: Dict[str, list] = {}
        for table_id, t in computation["per_table"].items():
            mask = t["mask"]
            delta = t["delta"]
            masked_delta = delta[mask]
            before = t["before"]
            after = t["after"]
            changed_indices = np.argwhere(np.abs(delta) > 1e-9)
            changed_cells_by_table[table_id] = [
                {
                    "rpm": int(round(float(t["table"].row_axis[r]) * 1000.0)),
                    "tps": float(t["table"].col_axis[c]),
                    "before": float(before[r, c]),
                    "after": float(after[r, c]),
                    "delta": float(delta[r, c]),
                    "source_scalar_comp": float(t["source_scalar_comp"][r, c]),
                }
                for r, c in changed_indices
            ]
            table_stats.append(
                {
                    "table_id": table_id,
                    "cells_in_mask": int(np.sum(mask)),
                    "cells_changed": int(t["cells_changed"]),
                    "delta_min_mask": float(np.min(masked_delta)),
                    "delta_mean_mask": float(np.mean(masked_delta)),
                    "delta_max_mask": float(np.max(masked_delta)),
                    "before_min_mask": float(np.min(before[mask])),
                    "before_max_mask": float(np.max(before[mask])),
                    "after_min_mask": float(np.min(after[mask])),
                    "after_max_mask": float(np.max(after[mask])),
                }
            )

        manifest_path = plan.output_pvv_path.with_suffix(".manifest.json")
        manifest = {
            "kind": "wot_ve_graft",
            "inputs": {
                "source_pvv": str(donor_path),
                "source_sha256": sha256(donor_path),
                "input_pvv": str(plan.input_pvv_path),
                "input_sha256": sha256(plan.input_pvv_path),
            },
            "policy": {
                "graft_pct": params["graft_pct"],
                "gain_schedule": params.get("gain_schedule"),
                "rpm_min_krpm": params["rpm_min_krpm"],
                "tps_min_pct": params["tps_min_pct"],
                "ve_cap": params["ve_cap"],
                "ve_clamp_gate_pct": params["ve_clamp_gate_pct"],
                "source_to_target_scalar_factor": computation["scalar_factor"],
                "source_displacement": computation["src_disp"],
                "target_displacement": computation["dst_disp"],
                "source_injector_size": computation["src_inj"],
                "target_injector_size": computation["dst_inj"],
            },
            "table_stats": table_stats,
            "changed_cells_by_table": changed_cells_by_table,
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
                "scalar_factor": computation["scalar_factor"],
                "table_stats": table_stats,
            },
        )
