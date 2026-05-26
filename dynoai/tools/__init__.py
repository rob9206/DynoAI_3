"""Tools package: surgical PVV patch generators driven by Findings.

Each Tool addresses one or more Finding.kind types and produces a flash-safe
PVV patch by mutating only approved table Item ids. Tools must:

  - Be deterministic: same plan -> same SHA-256 (idempotency).
  - Run all manifest gates before writing; abort without writing on failure.
  - Emit a manifest.json alongside the patch with input/output SHA,
    table stats, and the bound params used.

Tools read overrides from `vehicles/<vid>/profile.json` under
`tool_overrides.<tool_name>`. Safe defaults live in each tool's manifest.
"""

from dynoai.tools.gates import (
    FloorGate,
    Gate,
    GateContext,
    GateFailure,
    ItemIntegrityGate,
    SparkClampGate,
    VeClampGate,
)
from dynoai.tools.tool import PatchResult, Tool, ToolManifest, ToolPlan, resolve_params

__all__ = [
    "FloorGate",
    "Gate",
    "GateContext",
    "GateFailure",
    "ItemIntegrityGate",
    "PatchResult",
    "SparkClampGate",
    "Tool",
    "ToolManifest",
    "ToolPlan",
    "VeClampGate",
    "resolve_params",
]
