"""Finding: uniform diagnostic shape across all detectors.

A Finding is what a Detector emits. The dispatcher uses it to rank, dedupe,
and look up the Tool that can address it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class Finding:
    """A diagnostic observation plus optional remediation hook.

    `kind` is the canonical issue type (e.g. "spark_valley", "knock_hotspot",
    "wot_lean", "decel_pop", "idle_ve_noise", "cruise_ve_noise",
    "accel_lean_lag", "injector_calibration"). Tools register the kinds they
    can address; the dispatcher uses `suggested_tool` as a hint but verifies
    the tool actually claims `kind` in its manifest before invoking.
    """

    kind: str
    severity: float
    confidence: float
    evidence: Mapping[str, Any] = field(default_factory=dict)
    suggested_tool: Optional[str] = None
    tool_params: Mapping[str, Any] = field(default_factory=dict)
    source: str = ""

    def rank_score(self) -> float:
        return float(self.severity) * float(self.confidence)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Finding":
        """Reconstruct a Finding from a JSON-decoded dict.

        Counterpart to the serialization used by the patch_recommender's
        decision_dict. Tolerates the round-trip-derived `rank_score` field
        in the input (ignored — it's a derived property).
        """
        return cls(
            kind=str(d["kind"]),
            severity=float(d["severity"]),
            confidence=float(d["confidence"]),
            evidence=dict(d.get("evidence") or {}),
            suggested_tool=d.get("suggested_tool"),
            tool_params=dict(d.get("tool_params") or {}),
            source=str(d.get("source") or ""),
        )
