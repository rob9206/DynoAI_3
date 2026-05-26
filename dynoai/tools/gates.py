"""Universal safety gates for surgical patches.

Gates are pure predicates over (before, after, context). They return None on
pass, or a GateFailure on violation. Tools must run all manifest gates
before any write; ANY failure must abort without writing per AGENTS.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol, Set, runtime_checkable

import numpy as np


@dataclass(frozen=True)
class GateFailure:
    gate: str
    reason: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GateContext:
    """Context passed to Gate.check(). Carries enough state for any built-in gate."""

    target_item_id: str
    allowed_changed_ids: Set[str]
    profile: Mapping[str, Any] = field(default_factory=dict)
    extra: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class Gate(Protocol):
    name: str

    def check(
        self,
        before: np.ndarray,
        after: np.ndarray,
        ctx: GateContext,
    ) -> Optional[GateFailure]: ...


@dataclass(frozen=True)
class SparkClampGate:
    """Per-cell spark delta must be within +/- max_retard_deg.

    AGENTS.md default: 3 degrees. The gate fires symmetrically on both
    over-retard and over-advance.
    """

    max_retard_deg: float = 3.0
    name: str = "spark_clamp"

    def check(
        self,
        before: np.ndarray,
        after: np.ndarray,
        ctx: GateContext,
    ) -> Optional[GateFailure]:
        delta = np.abs(after - before)
        overshoot = float(np.max(delta)) if delta.size else 0.0
        if overshoot > self.max_retard_deg + 1e-9:
            return GateFailure(
                gate=self.name,
                reason=(
                    f"max per-cell |delta| {overshoot:.3f} deg exceeds clamp "
                    f"{self.max_retard_deg:.3f} deg"
                ),
                details={
                    "overshoot_deg": overshoot,
                    "clamp_deg": self.max_retard_deg,
                },
            )
        return None


@dataclass(frozen=True)
class VeClampGate:
    """Per-cell delta must be within +/- max_pct of the base value.

    Semantics: |after - before| <= |before| * (max_pct/100). Multiplicative
    rather than absolute, because VE cells span 25-140 and a 10% relative
    move is meaningful across that whole range.

    AGENTS.md default: 10%. The tool's own clamp may be tighter (e.g. 5%);
    this gate is the safety net for misconfiguration or algorithm bugs.
    """

    max_pct: float = 10.0
    name: str = "ve_clamp"

    def check(
        self,
        before: np.ndarray,
        after: np.ndarray,
        ctx: GateContext,
    ) -> Optional[GateFailure]:
        if before.size == 0:
            return None
        ratio_limit = self.max_pct / 100.0
        allowed = np.abs(before) * ratio_limit
        delta = np.abs(after - before)
        overshoot = delta - allowed
        worst_idx = int(np.argmax(overshoot)) if overshoot.size else 0
        worst_overshoot = float(overshoot.flat[worst_idx])
        if worst_overshoot > 1e-9:
            worst_delta = float(delta.flat[worst_idx])
            worst_before = float(before.flat[worst_idx])
            worst_pct = (
                worst_delta / abs(worst_before) * 100.0 if worst_before else float("inf")
            )
            return GateFailure(
                gate=self.name,
                reason=(
                    f"max per-cell |delta| {worst_delta:.3f} ({worst_pct:.2f}%) "
                    f"exceeds clamp {self.max_pct:.2f}%"
                ),
                details={
                    "worst_delta": worst_delta,
                    "worst_before": worst_before,
                    "worst_pct": worst_pct,
                    "clamp_pct": self.max_pct,
                },
            )
        return None


@dataclass(frozen=True)
class FloorGate:
    """In cells the tool touched, the post-patch value must be >= floor.

    Cells the tool did not modify are exempt; they may have legitimate
    pre-existing values below the floor (e.g. idle region with low spark
    advance that is outside the patch's load mask).
    """

    min_value: float
    name: str = "floor"

    def check(
        self,
        before: np.ndarray,
        after: np.ndarray,
        ctx: GateContext,
    ) -> Optional[GateFailure]:
        if after.size == 0:
            return None
        diff_mask = np.abs(after - before) > 1e-9
        if not diff_mask.any():
            return None
        touched = after[diff_mask]
        worst = float(np.min(touched))
        if worst < self.min_value - 1e-9:
            return GateFailure(
                gate=self.name,
                reason=(
                    f"min after-value in touched cells {worst:.3f} below floor "
                    f"{self.min_value:.3f}"
                ),
                details={"min_after": worst, "floor": self.min_value},
            )
        return None


@dataclass(frozen=True)
class ItemIntegrityGate:
    """Only Item ids in `allowed_changed_ids` may differ between input and output XML.

    Runs against the parsed XML roots, not the before/after table arrays.
    Use via `check_xml_roots()` from the tool after `tree.write()`, since the
    before/after numpy arrays don't carry XML structure.
    """

    name: str = "item_integrity"

    def check(
        self,
        before: np.ndarray,
        after: np.ndarray,
        ctx: GateContext,
    ) -> Optional[GateFailure]:
        # This gate is a no-op on numeric arrays; it runs at XML level
        # via check_xml_roots() instead.
        return None

    def check_xml_roots(
        self,
        in_cells: Mapping[str, list],
        out_cells: Mapping[str, list],
        allowed_changed_ids: Set[str],
    ) -> Optional[GateFailure]:
        if set(in_cells.keys()) != set(out_cells.keys()):
            missing = sorted(set(in_cells.keys()) - set(out_cells.keys()))
            added = sorted(set(out_cells.keys()) - set(in_cells.keys()))
            return GateFailure(
                gate=self.name,
                reason="Item id set changed between input and output",
                details={"missing": missing, "added": added},
            )
        changed = sorted(
            item_id for item_id in in_cells if in_cells[item_id] != out_cells[item_id]
        )
        unexpected = sorted(item_id for item_id in changed if item_id not in allowed_changed_ids)
        if unexpected:
            return GateFailure(
                gate=self.name,
                reason=(
                    "Non-approved item ids changed: " + ", ".join(unexpected)
                ),
                details={"unexpected": unexpected, "allowed": sorted(allowed_changed_ids)},
            )
        return None
