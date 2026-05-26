"""Patch recommendation service: NextGen analysis -> dispatcher -> patch plan.

Bridges the existing NextGen workflow (CSV -> surfaces -> hypotheses) to
the dynoai.diagnostics dispatcher, producing flash-safe patch
recommendations without mutating the tune.

This service is read-only: it calls `dispatcher.step()` (which runs each
tool's `plan()`, a no-write preview) and returns a JSON-friendly payload.
Actually applying a patch requires a separate, explicit user action via a
dedicated apply endpoint (out of scope for this slice — patches are
safety-critical and should never auto-apply from a recommendation call).

Inputs come from two sources:
  - `run_id`: NextGen analysis output cache (surfaces, etc.)
  - `vehicle_id` / `session_id`: standard vehicles/<vid>/sessions/<sid>/
    layout for the base PVV + profile.json
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from api.services.nextgen_workflow import get_nextgen_workflow
from dynoai.diagnostics import (
    DetectionContext,
    DispatchDecision,
    Finding,
    build_default_dispatcher,
    surfaces_from_payload,
)
from dynoai.tools.tool import PatchResult, ToolPlan

logger = logging.getLogger(__name__)


VEHICLES_ROOT = Path("vehicles")


# =============================================================================
# Resolution helpers (paths from the standard layout)
# =============================================================================


def resolve_base_pvv(vehicle_id: str, session_id: str) -> Optional[Path]:
    """Return base_tune/base.pvv absolute path for the given session, or None."""
    candidate = (
        VEHICLES_ROOT
        / vehicle_id
        / "sessions"
        / session_id
        / "base_tune"
        / "base.pvv"
    ).resolve()
    return candidate if candidate.exists() else None


def resolve_profile(vehicle_id: str) -> Dict[str, Any]:
    """Load vehicles/<vid>/profile.json, or return an empty profile."""
    candidate = VEHICLES_ROOT / vehicle_id / "profile.json"
    if not candidate.exists():
        return {"id": vehicle_id, "tool_overrides": {}}
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            f"Failed to load profile for {vehicle_id}: {exc}; using empty profile"
        )
        return {"id": vehicle_id, "tool_overrides": {}}


def resolve_active_iteration_dir(vehicle_id: str, session_id: str) -> Optional[Path]:
    """Read session.json -> active_iteration_id, return that iter dir."""
    session_json = (
        VEHICLES_ROOT / vehicle_id / "sessions" / session_id / "session.json"
    )
    if not session_json.exists():
        return None
    try:
        session = json.loads(session_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Failed to read session.json: {exc}")
        return None
    iter_id = session.get("active_iteration_id")
    if not iter_id:
        return None
    candidate = (
        VEHICLES_ROOT
        / vehicle_id
        / "sessions"
        / session_id
        / "iterations"
        / iter_id
    )
    return candidate if candidate.exists() else None


# =============================================================================
# Serialization (Finding / DispatchDecision -> JSON-friendly dicts)
# =============================================================================


def _finding_to_dict(finding: Finding) -> Dict[str, Any]:
    return {
        "kind": finding.kind,
        "severity": float(finding.severity),
        "confidence": float(finding.confidence),
        "rank_score": finding.rank_score(),
        "evidence": dict(finding.evidence),
        "suggested_tool": finding.suggested_tool,
        "tool_params": dict(finding.tool_params),
        "source": finding.source,
    }


def _plan_to_dict(plan: ToolPlan) -> Dict[str, Any]:
    return {
        "tool": plan.tool,
        "bound_params": dict(plan.bound_params),
        "input_pvv_path": str(plan.input_pvv_path),
        "output_pvv_path": str(plan.output_pvv_path),
        "predicted_cells_changed": int(plan.predicted_cells_changed),
        "predicted_max_delta": dict(plan.predicted_max_delta),
        "risk_score": float(plan.risk_score),
        "finding": _finding_to_dict(plan.finding),
    }


def _decision_to_dict(decision: DispatchDecision) -> Dict[str, Any]:
    return {
        "findings": [_finding_to_dict(f) for f in decision.findings],
        "plan": _plan_to_dict(decision.plan) if decision.plan is not None else None,
        "skipped": [
            {"finding": _finding_to_dict(f), "reason": reason}
            for f, reason in decision.skipped
        ],
    }


# =============================================================================
# Public API
# =============================================================================


@dataclass(frozen=True)
class PatchRecommendationRequest:
    run_id: str
    vehicle_id: str
    session_id: str
    donor_pvv_path: Optional[Path] = None
    include_wot_lean: bool = True


@dataclass(frozen=True)
class PatchRecommendationResult:
    success: bool
    error: Optional[str] = None
    decision_dict: Optional[Dict[str, Any]] = None
    context_meta: Optional[Dict[str, Any]] = None


def recommend_patches(req: PatchRecommendationRequest) -> PatchRecommendationResult:
    """Run the diagnostics dispatcher on a cached NextGen analysis.

    Steps:
      1. Load the NextGen payload (must already exist via /generate).
      2. Resolve base PVV, vehicle profile, active iteration dir.
      3. Reconstruct Surface2D objects from the payload.
      4. Build a default dispatcher (with optional donor for wot_ve_graft).
      5. Call dispatcher.step() -- preview only, no writes.
      6. Serialize the decision to JSON-friendly dicts.

    Returns a PatchRecommendationResult either with success=True and a
    decision_dict, or with success=False and an error message.
    """
    workflow = get_nextgen_workflow()
    cached = workflow.load_cached(req.run_id)
    if cached is None:
        return PatchRecommendationResult(
            success=False,
            error=(
                f"NextGen analysis not found for run {req.run_id}. "
                f"Generate first: POST /api/nextgen/{req.run_id}/generate"
            ),
        )

    base_pvv = resolve_base_pvv(req.vehicle_id, req.session_id)
    if base_pvv is None:
        return PatchRecommendationResult(
            success=False,
            error=(
                f"Base PVV not found at "
                f"vehicles/{req.vehicle_id}/sessions/{req.session_id}/base_tune/base.pvv"
            ),
        )

    profile = resolve_profile(req.vehicle_id)
    iter_dir = resolve_active_iteration_dir(req.vehicle_id, req.session_id)
    if iter_dir is None:
        # Fall back to a synthetic iter_0 path under the session — recommendations
        # are read-only, so the path is only used for output_pvv_path planning;
        # nothing actually gets written until the apply endpoint is called.
        iter_dir = (
            VEHICLES_ROOT
            / req.vehicle_id
            / "sessions"
            / req.session_id
            / "iterations"
            / "iter_0"
        ).resolve()
    else:
        iter_dir = iter_dir.resolve()

    try:
        surfaces = surfaces_from_payload(cached)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to deserialize surfaces from cached payload")
        return PatchRecommendationResult(
            success=False,
            error=f"Failed to deserialize surfaces: {exc}",
        )

    dispatcher = build_default_dispatcher(
        donor_pvv_path=req.donor_pvv_path,
        include_wot_lean=req.include_wot_lean,
    )

    ctx = DetectionContext(
        base_pvv_path=base_pvv,
        vehicle_profile=profile,
        iteration_dir=iter_dir,
        surfaces=surfaces,
    )

    try:
        decision = dispatcher.step(ctx)
    except Exception as exc:  # noqa: BLE001
        logger.exception("dispatcher.step failed")
        return PatchRecommendationResult(
            success=False,
            error=f"dispatcher.step failed: {exc}",
        )

    context_meta = {
        "run_id": req.run_id,
        "vehicle_id": req.vehicle_id,
        "session_id": req.session_id,
        "base_pvv_path": str(base_pvv),
        "iteration_dir": str(iter_dir),
        "donor_pvv_path": str(req.donor_pvv_path) if req.donor_pvv_path else None,
        "surfaces_loaded": sorted(surfaces.keys()),
        "include_wot_lean": req.include_wot_lean,
    }
    return PatchRecommendationResult(
        success=True,
        decision_dict=_decision_to_dict(decision),
        context_meta=context_meta,
    )


# =============================================================================
# Apply path: explicit user-confirmed patch application
# =============================================================================


APPLY_CONFIRMATION_TOKEN = "apply_patch"
APPLY_LOG_FILENAME = "apply_log.jsonl"


def _patch_result_to_dict(result: PatchResult) -> Dict[str, Any]:
    return {
        "success": bool(result.success),
        "patch_path": str(result.patch_path) if result.patch_path else None,
        "manifest_path": str(result.manifest_path) if result.manifest_path else None,
        "sha256": result.sha256,
        "cells_changed": int(result.cells_changed),
        "gates_passed": list(result.gates_passed),
        "gates_failed": [
            {
                "gate": gf.gate,
                "reason": gf.reason,
                "details": dict(gf.details),
            }
            for gf in result.gates_failed
        ],
        "extra": {
            k: (str(v) if isinstance(v, Path) else v)
            for k, v in (result.extra or {}).items()
        },
    }


def _append_apply_log(
    iter_dir: Path,
    *,
    run_id: str,
    vehicle_id: str,
    session_id: str,
    plan_dict: Mapping[str, Any],
    result_dict: Mapping[str, Any],
) -> Path:
    """Append a JSON Lines audit entry for an apply attempt.

    The log lives at `<iter_dir>/apply_log.jsonl` and accumulates one entry
    per apply call (successful or not). Each entry carries enough to
    reproduce the call: timestamp, ids, the bound plan, gate outcomes,
    output SHA. Append-only by design.
    """
    iter_dir.mkdir(parents=True, exist_ok=True)
    log_path = iter_dir / APPLY_LOG_FILENAME
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "vehicle_id": vehicle_id,
        "session_id": session_id,
        "plan": dict(plan_dict),
        "result": dict(result_dict),
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, separators=(",", ":")))
        fh.write("\n")
    return log_path


@dataclass(frozen=True)
class PatchApplyRequest:
    run_id: str
    vehicle_id: str
    session_id: str
    plan_dict: Mapping[str, Any]
    confirmation: str
    donor_pvv_path: Optional[Path] = None


@dataclass(frozen=True)
class PatchApplyResult:
    success: bool
    error: Optional[str] = None
    result_dict: Optional[Dict[str, Any]] = None
    audit_log_path: Optional[Path] = None
    context_meta: Optional[Dict[str, Any]] = None


def apply_patch_request(req: PatchApplyRequest) -> PatchApplyResult:
    """Materialize and apply a ToolPlan submitted by an apply HTTP call.

    Safety contract:
      - Caller MUST include the explicit confirmation token. The endpoint
        layer validates this BEFORE calling here; we re-check defensively.
      - All patch safety lives in the tool's own gates (per-cell clamps,
        floor/ceiling, item integrity, plan/apply parity). We never
        relax or bypass those.
      - Gate failures are surfaced as success=False results, not raised.
        Callers see "patch refused" in the JSON, not a 5xx error.
      - Every attempt (success or fail) appends an entry to the
        iteration's apply_log.jsonl for audit.
    """
    if req.confirmation != APPLY_CONFIRMATION_TOKEN:
        return PatchApplyResult(
            success=False,
            error=(
                "Missing or invalid confirmation token. Set "
                f"'confirmation' = {APPLY_CONFIRMATION_TOKEN!r} in the request body."
            ),
        )

    try:
        plan = ToolPlan.from_dict(req.plan_dict)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to reconstruct ToolPlan from request: %s", exc)
        return PatchApplyResult(
            success=False,
            error=f"Invalid plan structure: {exc}",
        )

    base_pvv = resolve_base_pvv(req.vehicle_id, req.session_id)
    if base_pvv is None:
        return PatchApplyResult(
            success=False,
            error=(
                f"Base PVV not found at "
                f"vehicles/{req.vehicle_id}/sessions/{req.session_id}/base_tune/base.pvv"
            ),
        )

    profile = resolve_profile(req.vehicle_id)
    iter_dir = resolve_active_iteration_dir(req.vehicle_id, req.session_id)
    if iter_dir is None:
        iter_dir = (
            VEHICLES_ROOT
            / req.vehicle_id
            / "sessions"
            / req.session_id
            / "iterations"
            / "iter_0"
        ).resolve()
    else:
        iter_dir = iter_dir.resolve()

    # The dispatcher carries the tool registry. Including wot_lean is harmless
    # for apply — we're invoking a specific tool by id from the plan, not
    # routing via detectors.
    dispatcher = build_default_dispatcher(
        donor_pvv_path=req.donor_pvv_path,
        include_wot_lean=True,
    )
    if plan.tool not in dispatcher.tools:
        return PatchApplyResult(
            success=False,
            error=(
                f"Unknown tool {plan.tool!r}. Registered: "
                f"{sorted(dispatcher.tools.keys())}"
            ),
        )

    # No surfaces needed for apply — the tool reads what it needs (base PVV,
    # optionally donor PVV via bound_params). Pass an empty surfaces dict.
    ctx = DetectionContext(
        base_pvv_path=base_pvv,
        vehicle_profile=profile,
        iteration_dir=iter_dir,
        surfaces={},
    )

    try:
        result = dispatcher.apply(plan, ctx)
    except Exception as exc:  # noqa: BLE001
        logger.exception("dispatcher.apply raised; logging as a failed apply")
        # Even unexpected exceptions get logged for audit.
        result_dict = {
            "success": False,
            "patch_path": None,
            "manifest_path": None,
            "sha256": None,
            "cells_changed": 0,
            "gates_passed": [],
            "gates_failed": [{"gate": "exception", "reason": str(exc), "details": {}}],
            "extra": {"reason": "exception"},
        }
        log_path = _append_apply_log(
            iter_dir,
            run_id=req.run_id,
            vehicle_id=req.vehicle_id,
            session_id=req.session_id,
            plan_dict=req.plan_dict,
            result_dict=result_dict,
        )
        return PatchApplyResult(
            success=False,
            error=f"dispatcher.apply raised: {exc}",
            result_dict=result_dict,
            audit_log_path=log_path,
        )

    result_dict = _patch_result_to_dict(result)
    log_path = _append_apply_log(
        iter_dir,
        run_id=req.run_id,
        vehicle_id=req.vehicle_id,
        session_id=req.session_id,
        plan_dict=req.plan_dict,
        result_dict=result_dict,
    )

    context_meta = {
        "run_id": req.run_id,
        "vehicle_id": req.vehicle_id,
        "session_id": req.session_id,
        "base_pvv_path": str(base_pvv),
        "iteration_dir": str(iter_dir),
        "tool": plan.tool,
    }
    return PatchApplyResult(
        success=bool(result.success),
        # Gate failures aren't service-level errors; result_dict carries the details.
        error=None if result.success else "Gate failure — see result.gates_failed",
        result_dict=result_dict,
        audit_log_path=log_path,
        context_meta=context_meta,
    )
