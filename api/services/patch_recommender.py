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
from dynoai.tools.tool import ToolPlan

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
