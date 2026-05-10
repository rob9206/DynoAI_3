"""Dispatch readiness evaluator for `dynoai.session.v3` sessions."""

from __future__ import annotations

from typing import Any

from api.services.tuning_workspace import SessionStatus, TuningSession


def evaluate_dispatch_readiness(
    session: TuningSession,
    workspace_status: SessionStatus,
) -> dict[str, Any]:
    """
    Aggregate dispatch gates for a v3 session.

    Gates:
    - Workspace has required artifacts (base tune + pulls)
    - All blocking verify blockers are resolved
    - Session status has reached a template `dispatch_after` state (if configured)
    - Kernel sentinel has `halt_on_breach` explicitly enabled
    - P0 plausibility has a pass/warn outcome recorded
    """
    v3 = session.v3 or {}
    template = v3.get("template") or {}
    kernel = v3.get("kernel_sentinel") or {}
    blockers = v3.get("verify_blockers") or []
    session_blockers = v3.get("session_blockers") or []

    unresolved_verify = []
    for blocker in blockers:
        if not isinstance(blocker, dict):
            continue
        if not blocker.get("blocking", True):
            continue
        if not blocker.get("resolved", False):
            unresolved_verify.append(
                {
                    "field": blocker.get("field"),
                    "owner": blocker.get("owner"),
                }
            )

    dispatch_after = template.get("dispatch_after") or []
    status_gate_ok = True
    if isinstance(dispatch_after, list) and dispatch_after:
        status_gate_ok = session.status in dispatch_after

    halt_on_breach = bool(kernel.get("halt_on_breach"))
    p0 = _extract_p0_status(v3)
    p0_ok = p0 in {"pass", "warn", "warning"}

    ready = all(
        [
            workspace_status.ready_to_analyze,
            not unresolved_verify,
            not session_blockers,
            status_gate_ok,
            halt_on_breach,
            p0_ok,
        ]
    )

    return {
        "ready": ready,
        "session_id": session.id,
        "schema_version": session.schema_version,
        "gates": {
            "workspace_ready": workspace_status.ready_to_analyze,
            "verify_blockers_resolved": len(unresolved_verify) == 0,
            "session_blockers_clear": len(session_blockers) == 0,
            "status_gate_ok": status_gate_ok,
            "kernel_halt_on_breach": halt_on_breach,
            "p0_plausibility_ok": p0_ok,
        },
        "details": {
            "unresolved_verify_blockers": unresolved_verify,
            "session_blockers": session_blockers,
            "dispatch_after": dispatch_after,
            "current_status": session.status,
            "p0_plausibility_status": p0,
            "workspace_status": workspace_status.to_dict(),
        },
    }


def _extract_p0_status(v3: dict[str, Any]) -> str | None:
    checks = v3.get("checks")
    if isinstance(checks, dict):
        p0 = checks.get("p0_plausibility")
        if isinstance(p0, dict):
            status = p0.get("status")
            if isinstance(status, str):
                return status.lower()
    return None
