"""TuningDispatcher: detect -> plan -> (user confirms) -> apply.

Enforces the AGENTS.md iteration discipline:
  - One correction pass per iteration (top-ranked actionable finding).
  - Universal safety gates run before any mutation.
  - Abort without writing if any gate fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Tuple

from dynoai.diagnostics.detector import DetectionContext, Detector
from dynoai.diagnostics.finding import Finding
from dynoai.tools.tool import PatchResult, Tool, ToolPlan


@dataclass(frozen=True)
class DispatchDecision:
    """Output of one dispatcher.step() call."""

    findings: Tuple[Finding, ...]
    plan: Optional[ToolPlan]
    skipped: Tuple[Tuple[Finding, str], ...] = ()


class TuningDispatcher:
    def __init__(
        self,
        detectors: Iterable[Detector],
        tools: Mapping[str, Tool],
    ) -> None:
        self._detectors: list[Detector] = list(detectors)
        self._tools: dict[str, Tool] = dict(tools)

    @property
    def tools(self) -> Mapping[str, Tool]:
        return dict(self._tools)

    def step(self, ctx: DetectionContext) -> DispatchDecision:
        """Run detectors, rank findings, plan the top-1 actionable one.

        No PVV mutation. Cheap. Safe to call repeatedly for previews.
        """
        all_findings: list[Finding] = []
        for detector in self._detectors:
            all_findings.extend(detector.detect(ctx))

        skipped: list[tuple[Finding, str]] = []
        actionable: list[Finding] = []
        for finding in all_findings:
            if finding.suggested_tool is None:
                skipped.append((finding, "no_suggested_tool"))
                continue
            tool = self._tools.get(finding.suggested_tool)
            if tool is None:
                skipped.append((finding, f"unknown_tool:{finding.suggested_tool}"))
                continue
            if finding.kind not in tool.manifest().fix_kinds:
                skipped.append(
                    (finding, f"kind_mismatch:{finding.kind}!={tool.manifest().fix_kinds}")
                )
                continue
            actionable.append(finding)

        actionable.sort(key=lambda f: f.rank_score(), reverse=True)

        if not actionable:
            return DispatchDecision(
                findings=tuple(all_findings),
                plan=None,
                skipped=tuple(skipped),
            )

        top = actionable[0]
        tool = self._tools[top.suggested_tool]  # type: ignore[index]
        plan = tool.plan(top, ctx)

        return DispatchDecision(
            findings=tuple(all_findings),
            plan=plan,
            skipped=tuple(skipped),
        )

    def apply(self, plan: ToolPlan, ctx: DetectionContext) -> PatchResult:
        """Run gates and write the patch. Aborts without writing on any gate failure."""
        tool = self._tools.get(plan.tool)
        if tool is None:
            raise KeyError(f"Tool not registered: {plan.tool!r}")
        return tool.apply(plan, ctx)
