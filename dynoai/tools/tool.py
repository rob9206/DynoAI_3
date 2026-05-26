"""Tool protocol + manifest, plan, and result types.

A Tool exposes three operations:

  manifest()            -> static description (name, fix_kinds, schema, gates)
  plan(finding, ctx)    -> bound ToolPlan with predicted deltas; NO writes
  apply(plan, ctx)      -> PatchResult; mutates PVV iff all gates pass

The plan/apply split lets the UI preview "this would change N cells, max
delta X" before the user commits. Tools must enforce plan/apply parity:
`predicted_cells_changed` == actual cells changed in the patch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional, Protocol, Tuple, runtime_checkable

from dynoai.diagnostics.finding import Finding
from dynoai.tools.gates import GateFailure

if TYPE_CHECKING:
    from dynoai.diagnostics.detector import DetectionContext


def resolve_params(
    defaults: Mapping[str, Any],
    profile: Mapping[str, Any],
    finding: Finding,
    tool_name: str,
) -> Dict[str, Any]:
    """Merge tool defaults <- profile overrides <- finding.tool_params.

    Every Tool's `plan()` does the same merge dance: start from defaults,
    layer in `vehicle_profile["tool_overrides"][tool_name]`, then layer in
    `finding.tool_params`. Only keys that exist in `defaults` are pulled
    from the override layers (so tool_params can't smuggle unknown keys).

    Returned dict is a fresh copy; safe to mutate.
    """
    overrides = (
        profile.get("tool_overrides", {}).get(tool_name, {}) if profile else {}
    )
    params: Dict[str, Any] = dict(defaults)
    for key in params:
        if key in overrides:
            params[key] = overrides[key]
    if finding.tool_params:
        for key in params:
            if key in finding.tool_params:
                params[key] = finding.tool_params[key]
    return params


@dataclass(frozen=True)
class ToolManifest:
    """Static manifest. Stable across plan/apply calls."""

    name: str
    description: str
    fix_kinds: Tuple[str, ...]
    inputs_schema: Mapping[str, Any]
    safety_gate_names: Tuple[str, ...]
    requires_profile_keys: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolPlan:
    """Bound, predictive plan. No side effects from constructing one."""

    tool: str
    finding: Finding
    bound_params: Mapping[str, Any]
    input_pvv_path: Path
    output_pvv_path: Path
    predicted_cells_changed: int
    predicted_max_delta: Mapping[str, float]
    risk_score: float = 0.0


@dataclass(frozen=True)
class PatchResult:
    """Result of Tool.apply()."""

    success: bool
    patch_path: Optional[Path]
    manifest_path: Optional[Path]
    sha256: Optional[str]
    cells_changed: int
    gates_passed: Tuple[str, ...] = ()
    gates_failed: Tuple[GateFailure, ...] = ()
    extra: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class Tool(Protocol):
    name: str

    def manifest(self) -> ToolManifest: ...

    def plan(self, finding: Finding, ctx: "DetectionContext") -> ToolPlan: ...

    def apply(self, plan: ToolPlan, ctx: "DetectionContext") -> PatchResult: ...
