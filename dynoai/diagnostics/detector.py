"""Detector protocol + DetectionContext.

A Detector is a pure function over a DetectionContext that emits Findings.
Detectors must be deterministic: same context in -> same findings out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Mapping, Protocol, Tuple, runtime_checkable

from dynoai.diagnostics.finding import Finding


@dataclass(frozen=True)
class DetectionContext:
    """Inputs available to all detectors during one iteration step.

    `surfaces` carries pre-built Surface2D objects (spark_front, spark_rear,
    afr_error, knock, etc.) keyed by name. Building them is out of scope for
    the dispatcher; it's the caller's job (typically nextgen_workflow or the
    workspace analyzer) to populate the context.
    """

    base_pvv_path: Path
    vehicle_profile: Mapping[str, Any]
    iteration_dir: Path
    surfaces: Mapping[str, Any] = field(default_factory=dict)
    pulls_dir: Path | None = None
    prior_findings: Tuple[Finding, ...] = ()


@runtime_checkable
class Detector(Protocol):
    """Pure detector. Implementations must be deterministic and side-effect free."""

    name: str
    fix_kinds: Tuple[str, ...]

    def detect(self, ctx: DetectionContext) -> List[Finding]: ...
