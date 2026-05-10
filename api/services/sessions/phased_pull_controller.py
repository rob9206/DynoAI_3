"""P0..P4 phased pull controller for v3 session execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_PHASE_ORDER = ["P0", "P1", "P2", "P3", "P4"]


@dataclass
class PhaseSnapshot:
    active_phase: str
    completed_phases: list[str]
    remaining_phases: list[str]
    can_advance: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_phase": self.active_phase,
            "completed_phases": self.completed_phases,
            "remaining_phases": self.remaining_phases,
            "can_advance": self.can_advance,
        }


def derive_phase_order(v3_payload: dict[str, Any] | None) -> list[str]:
    if not v3_payload:
        return list(DEFAULT_PHASE_ORDER)

    adaptive = v3_payload.get("adaptive_test_plan")
    if not isinstance(adaptive, dict):
        return list(DEFAULT_PHASE_ORDER)
    phases = adaptive.get("phases")
    if not isinstance(phases, list):
        return list(DEFAULT_PHASE_ORDER)

    order: list[str] = []
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        phase_id = str(phase.get("id") or "").strip().upper()
        if not phase_id:
            continue
        order.append(phase_id)
    return order or list(DEFAULT_PHASE_ORDER)


def compute_phase_snapshot(v3_payload: dict[str, Any] | None) -> PhaseSnapshot:
    order = derive_phase_order(v3_payload)
    execution = (v3_payload or {}).get("execution") if v3_payload else {}
    if not isinstance(execution, dict):
        execution = {}

    completed = execution.get("completed_phases")
    if not isinstance(completed, list):
        completed = []
    completed_norm = [str(p).upper() for p in completed if str(p).strip()]

    active = execution.get("active_phase")
    active_norm = str(active).upper() if active else None
    if active_norm not in order:
        active_norm = _first_remaining(order, completed_norm) or order[-1]

    remaining = [p for p in order if p not in completed_norm]
    can_advance = bool(remaining and active_norm in remaining)
    return PhaseSnapshot(
        active_phase=active_norm,
        completed_phases=completed_norm,
        remaining_phases=remaining,
        can_advance=can_advance,
    )


def mark_phase_complete(
    v3_payload: dict[str, Any],
    phase_id: str,
) -> dict[str, Any]:
    order = derive_phase_order(v3_payload)
    phase = phase_id.strip().upper()
    if phase not in order:
        raise ValueError(f"unknown phase: {phase_id}")

    execution = v3_payload.setdefault("execution", {})
    completed = execution.setdefault("completed_phases", [])
    if phase not in completed:
        completed.append(phase)

    next_phase = _first_remaining(order, [str(p).upper() for p in completed])
    execution["active_phase"] = next_phase or phase
    return v3_payload


def _first_remaining(order: list[str], completed: list[str]) -> str | None:
    for phase in order:
        if phase not in completed:
            return phase
    return None
