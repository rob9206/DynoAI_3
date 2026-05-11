"""
Pydantic models for `dynoai.session.v3` workspace session blueprints.

The legacy `TuningSession` dataclass in `api/services/tuning_workspace.py`
remains the storage anchor; this module validates and normalizes the richer
v3 payload stored under `TuningSession.v3`.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "dynoai.session.v3"


class VerifiedValue(BaseModel):
    model_config = ConfigDict(extra="allow")

    value: Any
    verified: Literal[True] = True
    source: str = ""
    evidence: str = ""


class InferredValue(BaseModel):
    model_config = ConfigDict(extra="allow")

    value: Any
    inferred: Literal[True] = True
    source: str = ""
    confidence: str = ""
    kill_switch: str = ""


class Customer(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    lead_status: Optional[str] = None
    intake_call_scheduled: Optional[str] = None
    intake_call_completed: Optional[str] = None
    notion_page_id: Optional[str] = None


class SessionVehicle(BaseModel):
    model_config = ConfigDict(extra="allow")

    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    common_name: Optional[str] = None
    vin: Optional[str] = None
    mileage_last_known: Optional[int] = None
    mileage_date: Optional[str] = None
    platform: Optional[str] = None
    counterbalanced: Optional[bool] = None


class CamSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    kit_pn: Optional[str] = None
    type: Optional[str] = None
    profile: Optional[str] = None


class InjectorSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    flow_rate_g_s: Optional[float] = None
    stock_flow_g_s: Optional[float] = None
    status: Optional[str] = None


class IntakeSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Optional[str] = None
    status: Optional[str] = None


class ExhaustSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    make: Optional[str] = None
    model: Optional[str] = None
    config: Optional[str] = None
    flow_class: Optional[str] = None


class EcmSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    vendor: Optional[str] = None
    part_number: Optional[str] = None
    status: Optional[str] = None


class BuildSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    displacement_ci: Optional[float] = None
    displacement_ci_options: list[float] = Field(default_factory=list)
    displacement_ci_status: Optional[str] = None
    stroker_kit_pn: Optional[str] = None
    cams: Optional[CamSpec] = None
    cam_plate: Optional[str] = None
    cam_bearings: Optional[str] = None
    pistons_cylinders: Optional[str] = None
    break_in_miles: Optional[float] = None
    break_in_status: Optional[str] = None
    injectors: Optional[InjectorSpec] = None
    intake: Optional[IntakeSpec] = None
    exhaust: Optional[ExhaustSpec] = None
    ecm: Optional[EcmSpec] = None
    current_calibration_source: Optional[str] = None
    current_calibration_status: Optional[str] = None
    afr_gauge_installed: Optional[bool] = None
    afr_gauge_status: Optional[str] = None


class EcmInterface(BaseModel):
    model_config = ConfigDict(extra="allow")

    tool: Optional[str] = None
    version_options: list[str] = Field(default_factory=list)
    version_selected: Optional[str] = None
    token_status: Optional[str] = None


class WidebandSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    primary: Optional[str] = None
    channels: Optional[int] = None
    placement: list[str] = Field(default_factory=list)
    logger: Optional[str] = None


class DynoSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: Optional[str] = None
    software: list[str] = Field(default_factory=list)


class Hardware(BaseModel):
    model_config = ConfigDict(extra="allow")

    ecm_interface: Optional[EcmInterface] = None
    wideband: Optional[WidebandSpec] = None
    dyno: Optional[DynoSpec] = None


class TemplateSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    dispatch_after: list[str] = Field(default_factory=list)
    afr_strategy: Optional[str] = None
    weighting: Optional[str] = None


class TimingInitialDeg(BaseModel):
    model_config = ConfigDict(extra="allow")

    cruise: Optional[float] = None
    wot: Optional[float] = None


class LambdaTargets(BaseModel):
    model_config = ConfigDict(extra="allow")

    # User locked this session to 0.88 as default in plan decisions.
    wot: float = 0.88
    cruise_min: Optional[float] = None
    cruise_max: Optional[float] = None
    idle: Optional[float] = None


class KernelSentinel(BaseModel):
    model_config = ConfigDict(extra="allow")

    ve_clamp_pct_per_cell: Optional[float] = None
    timing_initial_deg: Optional[TimingInitialDeg] = None
    knock_aware_retract: Optional[bool] = None
    lambda_targets: Optional[LambdaTargets] = None
    egt_redline_f: Optional[float] = None
    egt_warn_f: Optional[float] = None
    oil_temp_rollback_f: Optional[float] = None
    max_consecutive_lean_cells: Optional[int] = None
    halt_on_breach: Optional[bool] = None


class PhaseSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: Optional[str] = None
    method: Optional[str] = None
    kernel: Optional[str] = None
    pulls_budget: Optional[int] = None
    pulls_budget_min: Optional[int] = None
    pulls_budget_max: Optional[int] = None
    must_complete_first: Optional[bool] = None
    confirmation_only: Optional[bool] = None


class AdaptiveTestPlan(BaseModel):
    model_config = ConfigDict(extra="allow")

    phases: list[PhaseSpec] = Field(default_factory=list)
    rollback_on_breach: Optional[str] = None


class TargetRange(BaseModel):
    model_config = ConfigDict(extra="allow")

    min: Optional[float] = None
    max: Optional[float] = None
    stretch: Optional[float] = None


class DeltaVsCurrentState(BaseModel):
    model_config = ConfigDict(extra="allow")

    hp: Optional[str] = None
    tq_ftlb: Optional[str] = None


class Targets(BaseModel):
    model_config = ConfigDict(extra="allow")

    peak_hp: Optional[TargetRange] = None
    peak_tq_ftlb: Optional[TargetRange] = None
    powerband_priority_rpm: list[int] = Field(default_factory=list)
    delta_vs_current_state: Optional[DeltaVsCurrentState] = None
    note: Optional[str] = None


class VerifyBlocker(BaseModel):
    model_config = ConfigDict(extra="allow")

    field: str
    blocking: bool = True
    owner: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    evidence: Optional[str] = None


class RiskFlag(BaseModel):
    model_config = ConfigDict(extra="allow")

    level: str
    id: str
    description: str
    trigger: Optional[str] = None


class AgentAssignments(BaseModel):
    model_config = ConfigDict(extra="allow")

    planner: Optional[str] = None
    test_guardian: Optional[str] = None
    kernel_sentinel: Optional[str] = None
    integration_orchestrator: Optional[str] = None
    documentation_scribe: Optional[str] = None


class SessionV3(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = SCHEMA_VERSION
    session_id: str
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    shop: Optional[str] = None
    proposal_ref: Optional[str] = None
    ops_order: Optional[str] = None
    status: Optional[str] = None

    customer: Optional[Customer] = None
    vehicle: Optional[SessionVehicle] = None
    build_spec: Optional[BuildSpec] = None
    verify_blockers: list[VerifyBlocker] = Field(default_factory=list)
    hardware: Optional[Hardware] = None
    template: Optional[TemplateSpec] = None
    kernel_sentinel: Optional[KernelSentinel] = None
    adaptive_test_plan: Optional[AdaptiveTestPlan] = None
    targets: Optional[Targets] = None
    preflight_checks: list[str] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    session_blockers: list[str] = Field(default_factory=list)
    agent_assignments: Optional[AgentAssignments] = None


def validate_session_v3_payload(payload: dict[str, Any]) -> SessionV3:
    """Validate and normalize a raw v3 payload."""
    return SessionV3.model_validate(payload)


def dump_session_v3_payload(payload: SessionV3) -> dict[str, Any]:
    """Dump model to JSON-serializable dict for session.json storage."""
    return payload.model_dump(exclude_none=True)
