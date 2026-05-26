"""GpSmoothIdleCruiseVe: Matern 5/2 GP smoother over noisy idle/cruise VE cells.

Lifted from `tools/seanbike/gp_smooth_safeavg140.py` and generalized.

  - Two target tables: `tbl_ve_tps_based_front_cyl` and
    `tbl_ve_tps_based_rear_cyl` (overridable via bound_params).
  - Front and rear GPs are fit independently (cylinders can legitimately
    differ in airflow character).
  - Smoothing mask: RPM <= mask_rpm_max AND TPS <= mask_tps_max. Cells
    outside the mask are byte-identical in the output.
  - Per-cell |delta| clamped to +/- clamp_pct of original cell value
    (default 5%, matching the seanbike reference).
  - Defensive `VeClampGate` (default +/-10% per AGENTS.md) guards against
    misconfiguration / algorithm regression on top of the tighter patch
    clamp.

This tool addresses Finding.kind == "idle_ve_noise" / "cruise_ve_noise".
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any, Dict, Mapping, Tuple

import numpy as np

from dynoai.core.gp_engine import MaternGP
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
    VeClampGate,
)
from dynoai.tools.tool import PatchResult, ToolManifest, ToolPlan, resolve_params

if TYPE_CHECKING:
    from dynoai.diagnostics.detector import DetectionContext


TOOL_NAME = "gp_smooth_idle_cruise_ve"
DEFAULT_VE_FRONT_ID = "tbl_ve_tps_based_front_cyl"
DEFAULT_VE_REAR_ID = "tbl_ve_tps_based_rear_cyl"

DEFAULT_MASK_RPM_MAX = 4.0       # kRPM
DEFAULT_MASK_TPS_MAX = 40.0      # %
DEFAULT_CLAMP_PCT = 5.0          # patch policy
DEFAULT_VE_CLAMP_PCT = 10.0      # AGENTS.md safety gate

DEFAULT_LENGTH_SCALE_RPM = 0.30
DEFAULT_LENGTH_SCALE_TPS = 0.30
DEFAULT_SIGNAL_VAR = 1.0
DEFAULT_NOISE_VAR = 0.15

DEFAULT_VE_FLOOR = 25.0
DEFAULT_VE_CEILING = 140.0
DEFAULT_WARN_FR_DELTA = 12.6

_DEFAULTS: Dict[str, Any] = {
    "ve_front_id": DEFAULT_VE_FRONT_ID,
    "ve_rear_id": DEFAULT_VE_REAR_ID,
    "mask_rpm_max": DEFAULT_MASK_RPM_MAX,
    "mask_tps_max": DEFAULT_MASK_TPS_MAX,
    "clamp_pct": DEFAULT_CLAMP_PCT,
    "ve_clamp_gate_pct": DEFAULT_VE_CLAMP_PCT,
    "length_scale_rpm": DEFAULT_LENGTH_SCALE_RPM,
    "length_scale_tps": DEFAULT_LENGTH_SCALE_TPS,
    "signal_var": DEFAULT_SIGNAL_VAR,
    "noise_var": DEFAULT_NOISE_VAR,
    "ve_floor": DEFAULT_VE_FLOOR,
    "ve_ceiling": DEFAULT_VE_CEILING,
    "warn_front_rear_delta": DEFAULT_WARN_FR_DELTA,
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


def _normalize_inputs(
    rpm_krpm: np.ndarray, tps: np.ndarray
) -> Tuple[np.ndarray, dict]:
    rpm_min, rpm_max = float(rpm_krpm.min()), float(rpm_krpm.max())
    tps_min, tps_max = float(tps.min()), float(tps.max())
    rpm_span = max(rpm_max - rpm_min, 1e-9)
    tps_span = max(tps_max - tps_min, 1e-9)
    return (
        np.stack(
            [
                (rpm_krpm - rpm_min) / rpm_span,
                (tps - tps_min) / tps_span,
            ],
            axis=1,
        ),
        {
            "rpm_min": rpm_min,
            "rpm_max": rpm_max,
            "tps_min": tps_min,
            "tps_max": tps_max,
        },
    )


def _gp_smooth_grid(
    rpm_axis_krpm: np.ndarray,
    tps_axis: np.ndarray,
    values: np.ndarray,
    mask: np.ndarray,
    length_scales: Tuple[float, float],
    noise_var: float,
    signal_var: float,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    rpm_grid, tps_grid = np.meshgrid(rpm_axis_krpm, tps_axis, indexing="ij")
    flat_rpm = rpm_grid.reshape(-1)
    flat_tps = tps_grid.reshape(-1)
    flat_val = values.reshape(-1)
    flat_mask = mask.reshape(-1)

    full_X, _ = _normalize_inputs(flat_rpm, flat_tps)
    X_train = full_X[flat_mask]
    y_train = flat_val[flat_mask]

    gp = MaternGP(
        length_scales=np.asarray(length_scales, dtype=np.float64),
        signal_var=signal_var,
        noise_var=noise_var,
    )
    gp.fit(X_train, y_train)
    mean_pred, std_pred = gp.predict(X_train, return_std=True)

    smoothed = values.copy()
    std_grid = np.full_like(values, np.nan, dtype=float)
    smoothed_flat = smoothed.reshape(-1)
    std_flat = std_grid.reshape(-1)
    masked_idx = np.where(flat_mask)[0]
    smoothed_flat[masked_idx] = mean_pred
    std_flat[masked_idx] = std_pred if std_pred is not None else np.nan

    return smoothed, std_grid, gp.get_hyperparameters()


def _apply_per_cell_clamp(
    original: np.ndarray,
    smoothed: np.ndarray,
    mask: np.ndarray,
    clamp_pct: float,
) -> Tuple[np.ndarray, dict]:
    cap = clamp_pct / 100.0
    lo = original * (1.0 - cap)
    hi = original * (1.0 + cap)
    proposal = np.where(mask, smoothed, original)
    clamped = np.clip(proposal, lo, hi)
    final = np.where(mask, clamped, original)
    delta = final - original
    capped_mask = mask & (
        np.isclose(final, lo, atol=1e-9) | np.isclose(final, hi, atol=1e-9)
    )
    stats = {
        "max_abs_delta": float(np.max(np.abs(delta))),
        "mean_abs_delta_in_mask": float(
            np.mean(np.abs(delta[mask])) if np.any(mask) else 0.0
        ),
        "cells_changed_in_mask": int(np.sum((np.abs(delta) > 1e-6) & mask)),
        "cells_capped_in_mask": int(np.sum(capped_mask)),
    }
    return final, stats


def _compute_patch(
    root: ET.Element, params: Mapping[str, Any]
) -> Dict[str, Any]:
    """Pure computation: parse tables, GP smooth, clamp.

    Returns a dict with per-cylinder before/after/stats and the shared mask.
    Does not touch XML cell elements (caller must do that via
    `mutate_table_cells` after gates pass).
    """
    front = parse_table(root, params["ve_front_id"])
    rear = parse_table(root, params["ve_rear_id"])
    if front.values.shape != rear.values.shape:
        raise RuntimeError("Front/rear shape mismatch")
    if not np.array_equal(front.row_axis, rear.row_axis) or not np.array_equal(
        front.col_axis, rear.col_axis
    ):
        raise RuntimeError("Front/rear axes mismatch")

    mask = _build_mask(
        front.row_axis,
        front.col_axis,
        float(params["mask_rpm_max"]),
        float(params["mask_tps_max"]),
    )
    if int(np.sum(mask)) < 6:
        raise RuntimeError(
            f"Not enough cells in mask ({int(np.sum(mask))}); GP fit needs >=6"
        )

    length_scales = (
        float(params["length_scale_rpm"]),
        float(params["length_scale_tps"]),
    )
    front_smoothed, front_std, front_hparams = _gp_smooth_grid(
        front.row_axis,
        front.col_axis,
        front.values,
        mask,
        length_scales=length_scales,
        noise_var=float(params["noise_var"]),
        signal_var=float(params["signal_var"]),
    )
    front_final, front_stats = _apply_per_cell_clamp(
        front.values, front_smoothed, mask, float(params["clamp_pct"])
    )

    rear_smoothed, rear_std, rear_hparams = _gp_smooth_grid(
        rear.row_axis,
        rear.col_axis,
        rear.values,
        mask,
        length_scales=length_scales,
        noise_var=float(params["noise_var"]),
        signal_var=float(params["signal_var"]),
    )
    rear_final, rear_stats = _apply_per_cell_clamp(
        rear.values, rear_smoothed, mask, float(params["clamp_pct"])
    )

    return {
        "front_table": front,
        "rear_table": rear,
        "front_before": front.values.copy(),
        "rear_before": rear.values.copy(),
        "front_after": front_final,
        "rear_after": rear_final,
        "front_std": front_std,
        "rear_std": rear_std,
        "front_hparams": front_hparams,
        "rear_hparams": rear_hparams,
        "front_stats": front_stats,
        "rear_stats": rear_stats,
        "mask": mask,
    }


class GpSmoothIdleCruiseVeTool:
    """Matern 5/2 GP smoother over the idle/cruise VE cells."""

    name = TOOL_NAME

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name=self.name,
            description=(
                "Deterministic GP smoother over noisy idle/cruise VE cells "
                "(RPM<=mask_rpm_max AND TPS<=mask_tps_max). Fits front and "
                "rear cylinders independently. Per-cell change clamped to "
                "+/-clamp_pct of the original VE value."
            ),
            fix_kinds=("idle_ve_noise", "cruise_ve_noise"),
            inputs_schema={
                "ve_front_id": {"type": "string", "default": DEFAULT_VE_FRONT_ID},
                "ve_rear_id": {"type": "string", "default": DEFAULT_VE_REAR_ID},
                "mask_rpm_max": {"type": "number", "default": DEFAULT_MASK_RPM_MAX},
                "mask_tps_max": {"type": "number", "default": DEFAULT_MASK_TPS_MAX},
                "clamp_pct": {"type": "number", "default": DEFAULT_CLAMP_PCT},
                "ve_clamp_gate_pct": {"type": "number", "default": DEFAULT_VE_CLAMP_PCT},
                "length_scale_rpm": {"type": "number", "default": DEFAULT_LENGTH_SCALE_RPM},
                "length_scale_tps": {"type": "number", "default": DEFAULT_LENGTH_SCALE_TPS},
                "signal_var": {"type": "number", "default": DEFAULT_SIGNAL_VAR},
                "noise_var": {"type": "number", "default": DEFAULT_NOISE_VAR},
                "ve_floor": {"type": "number", "default": DEFAULT_VE_FLOOR},
                "ve_ceiling": {"type": "number", "default": DEFAULT_VE_CEILING},
                "warn_front_rear_delta": {
                    "type": "number",
                    "default": DEFAULT_WARN_FR_DELTA,
                },
            },
            safety_gate_names=("ve_clamp", "ve_floor", "ve_ceiling", "item_integrity"),
            requires_profile_keys=("tool_overrides.gp_smooth_idle_cruise_ve",),
        )

    def plan(self, finding: Finding, ctx: "DetectionContext") -> ToolPlan:
        params = resolve_params(_DEFAULTS, ctx.vehicle_profile, finding, TOOL_NAME)
        root = ET.parse(ctx.base_pvv_path).getroot()
        result = _compute_patch(root, params)

        front_changed = result["front_stats"]["cells_changed_in_mask"]
        rear_changed = result["rear_stats"]["cells_changed_in_mask"]
        front_max = result["front_stats"]["max_abs_delta"]
        rear_max = result["rear_stats"]["max_abs_delta"]

        output_dir = ctx.iteration_dir / "patches"
        output_name = ctx.base_pvv_path.stem + "_gpsmooth.pvv"

        return ToolPlan(
            tool=self.name,
            finding=finding,
            bound_params=params,
            input_pvv_path=ctx.base_pvv_path,
            output_pvv_path=output_dir / output_name,
            predicted_cells_changed=int(front_changed + rear_changed),
            predicted_max_delta={
                "ve_front_abs": float(front_max),
                "ve_rear_abs": float(rear_max),
            },
            risk_score=min(
                1.0,
                max(front_max, rear_max)
                / max(float(params["ve_clamp_gate_pct"]), 1e-9),
            ),
        )

    def apply(self, plan: ToolPlan, ctx: "DetectionContext") -> PatchResult:
        params = dict(plan.bound_params)
        front_id = params["ve_front_id"]
        rear_id = params["ve_rear_id"]
        allowed_changed = {front_id, rear_id}

        original_root = ET.parse(plan.input_pvv_path).getroot()
        tree = ET.parse(plan.input_pvv_path)
        root = tree.getroot()
        result = _compute_patch(root, params)

        gate_ctx = GateContext(
            target_item_id=f"{front_id}+{rear_id}",
            allowed_changed_ids=allowed_changed,
            profile=ctx.vehicle_profile,
        )
        ve_clamp_pct = float(params["ve_clamp_gate_pct"])
        ve_clamp_gate = VeClampGate(max_pct=ve_clamp_pct)
        integrity_gate = ItemIntegrityGate()

        passed: list[str] = []
        failed: list[GateFailure] = []

        for table_key, base_key, after_key in (
            ("front", "front_before", "front_after"),
            ("rear", "rear_before", "rear_after"),
        ):
            failure = ve_clamp_gate.check(result[base_key], result[after_key], gate_ctx)
            if failure is not None:
                failed.append(
                    GateFailure(
                        gate=f"ve_clamp[{table_key}]",
                        reason=failure.reason,
                        details=dict(failure.details),
                    )
                )
        if not failed:
            passed.append(ve_clamp_gate.name)

        ve_floor = float(params["ve_floor"])
        ve_ceiling = float(params["ve_ceiling"])
        global_min = float(
            min(np.min(result["front_after"]), np.min(result["rear_after"]))
        )
        global_max = float(
            max(np.max(result["front_after"]), np.max(result["rear_after"]))
        )
        if global_min < ve_floor - 1e-9:
            failed.append(
                GateFailure(
                    gate="ve_floor",
                    reason=f"global min {global_min:.3f} < floor {ve_floor:.3f}",
                    details={"min": global_min, "floor": ve_floor},
                )
            )
        else:
            passed.append("ve_floor")
        if global_max > ve_ceiling + 1e-9:
            failed.append(
                GateFailure(
                    gate="ve_ceiling",
                    reason=f"global max {global_max:.3f} > ceiling {ve_ceiling:.3f}",
                    details={"max": global_max, "ceiling": ve_ceiling},
                )
            )
        else:
            passed.append("ve_ceiling")

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

        front_changed = int(result["front_stats"]["cells_changed_in_mask"])
        rear_changed = int(result["rear_stats"]["cells_changed_in_mask"])
        actual_total = front_changed + rear_changed
        if actual_total != plan.predicted_cells_changed:
            failed.append(
                GateFailure(
                    gate="plan_parity",
                    reason=(
                        f"actual cells_changed={actual_total} != predicted "
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

        mutate_table_cells(result["front_table"], result["front_after"])
        mutate_table_cells(result["rear_table"], result["rear_after"])
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

        mask = result["mask"]
        n_mask = int(np.sum(mask))
        n_total = int(mask.size)
        max_fr_delta = float(
            np.max(np.abs(result["front_after"] - result["rear_after"]))
        )

        manifest_path = plan.output_pvv_path.with_suffix(".manifest.json")
        manifest = {
            "kind": "gp_smooth_idle_cruise_ve",
            "strategy": "matern52_posterior_mean_with_per_cell_clamp",
            "wot_lock": True,
            "inputs": {
                "input_pvv": str(plan.input_pvv_path),
                "input_sha256": sha256(plan.input_pvv_path),
            },
            "mask": {
                "rpm_max_krpm": params["mask_rpm_max"],
                "tps_max_pct": params["mask_tps_max"],
                "cells_in_mask": n_mask,
                "cells_total": n_total,
            },
            "gp_hyperparameters": {
                "front": result["front_hparams"],
                "rear": result["rear_hparams"],
            },
            "clamp_pct": params["clamp_pct"],
            "ve_clamp_gate_pct": params["ve_clamp_gate_pct"],
            "front_summary": result["front_stats"],
            "rear_summary": result["rear_stats"],
            "ve_summary": {
                "global_min": global_min,
                "global_max": global_max,
                "max_front_rear_delta": max_fr_delta,
            },
            "front_std_in_mask": result["front_std"][mask].tolist(),
            "rear_std_in_mask": result["rear_std"][mask].tolist(),
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
            cells_changed=actual_total,
            gates_passed=tuple(passed),
            gates_failed=(),
            extra={
                "changed_ids": changed_ids,
                "front_cells_changed": front_changed,
                "rear_cells_changed": rear_changed,
                "front_cells_capped": result["front_stats"]["cells_capped_in_mask"],
                "rear_cells_capped": result["rear_stats"]["cells_capped_in_mask"],
                "max_front_rear_delta": max_fr_delta,
            },
        )
