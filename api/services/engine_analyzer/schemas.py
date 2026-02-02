"""
Engine Analyzer component schemas.

Uses dataclasses for compatibility (no external validation dependency).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


def _to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return {k: _to_dict(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: _to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_dict(v) for v in value]
    return value


class Serializable:
    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class HeadFlowPoint(Serializable):
    lift_inches: float
    cfm: float


@dataclass
class IntakeSpec(Serializable):
    name: str
    runner_length_in: float | None = None
    runner_dia_in: float | None = None
    throttle_body_dia_in: float | None = None
    notes: str | None = None
    raw_numbers: list[float] = field(default_factory=list)


@dataclass
class HeadSpec(Serializable):
    name: str
    intake_valve_dia: float | None = None
    exhaust_valve_dia: float | None = None
    intake_port_cc: float | None = None
    exhaust_port_cc: float | None = None
    chamber_cc: float | None = None
    intake_flow: list[HeadFlowPoint] = field(default_factory=list)
    exhaust_flow: list[HeadFlowPoint] = field(default_factory=list)
    notes: str | None = None
    raw_numbers: list[float] = field(default_factory=list)


@dataclass
class CamSpec(Serializable):
    name: str
    intake_duration_050: float | None = None
    exhaust_duration_050: float | None = None
    intake_lift: float | None = None
    exhaust_lift: float | None = None
    lobe_separation: float | None = None
    advance: float | None = None
    rocker_ratio_int: float | None = None
    rocker_ratio_exh: float | None = None
    notes: str | None = None
    raw_numbers: list[float] = field(default_factory=list)


@dataclass
class ShortBlockSpec(Serializable):
    name: str
    bore: float | None = None
    stroke: float | None = None
    rod_length: float | None = None
    cylinders: int | None = None
    compression_ratio: float | None = None
    notes: str | None = None
    raw_numbers: list[float] = field(default_factory=list)


@dataclass
class CompleteEngineSpec(Serializable):
    name: str
    short_block: ShortBlockSpec | None = None
    heads: HeadSpec | None = None
    cam: CamSpec | None = None
    intake: IntakeSpec | None = None
    component_refs: list[str] = field(default_factory=list)
    notes: str | None = None
    raw_numbers: list[float] = field(default_factory=list)
    displacement_ci: float | None = None
    displacement_cc: float | None = None
    summary: str | None = None
