"""AccelTransientDetector: bidirectional flag on accel enrichment tables.

Tune-as-data detector. Reads `tbl_accel_enrichment` from the base PVV
and looks at the *hot-side* cells (T >= hot_threshold). Two independent
trigger paths:

  - **Rich spike**: hot_max > rich_max_mult (default 1.2) -> emit
    `accel_rich_spike` Finding. Engine gets too much extra fuel on
    tip-in when hot; symptom is rich-smoke / fouled plugs / hesitation
    from over-rich AFR.
  - **Lean lag**: hot_min < lean_min_mult (default 0.50) -> emit
    `accel_lean_lag` Finding. Engine doesn't get enough extra fuel on
    tip-in when hot; symptom is lean stumble / hesitation / lean spike
    on initial throttle.

Both can fire simultaneously if the hot side has split behavior (some
cells too high, some too low). Both route to `accel_enrich`, but with
different `target_hot` values bound via `tool_params` so the tool's
direction matches the finding.

Severity is symmetric: distance from threshold scaled to [0.3, 1.0].
Confidence reflects how many hot cells exceed the threshold.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List, Tuple

import numpy as np

from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.finding import Finding
from dynoai.pvv.io import parse_table


_ACCEL_RICH_KIND = "accel_rich_spike"
_ACCEL_LEAN_KIND = "accel_lean_lag"
_ACCEL_ENRICH_TOOL = "accel_enrich"


def _severity_from_distance(distance_pct: float) -> float:
    """Severity 0..1 from how far past the threshold we are (in %)."""
    d = float(max(distance_pct, 0.0))
    if d <= 10.0:
        return 0.30 + d * (0.50 - 0.30) / 10.0
    if d <= 30.0:
        return 0.50 + (d - 10.0) * (0.75 - 0.50) / 20.0
    if d <= 60.0:
        return 0.75 + (d - 30.0) * (0.95 - 0.75) / 30.0
    return 1.0


class AccelTransientDetector:
    """Flags rich-spike and lean-lag conditions in the accel enrichment table.

    Reads the base PVV directly; no surfaces required. Can emit zero, one,
    or two findings depending on which thresholds the tune crosses.
    """

    name = "accel_transient_detector"
    fix_kinds: Tuple[str, ...] = (_ACCEL_RICH_KIND, _ACCEL_LEAN_KIND)

    def __init__(
        self,
        *,
        target_item_id: str = "tbl_accel_enrichment",
        hot_threshold: float = 140.0,
        rich_max_mult: float = 1.20,
        rich_target_mult: float = 0.50,
        lean_min_mult: float = 0.50,
        lean_target_mult: float = 0.90,
    ) -> None:
        if hot_threshold <= 0.0:
            raise ValueError("hot_threshold must be > 0")
        if rich_max_mult <= 1.0:
            raise ValueError("rich_max_mult must be > 1.0 (above stoich)")
        if lean_min_mult <= 0.0 or lean_min_mult >= 1.0:
            raise ValueError("lean_min_mult must be in (0, 1)")
        self.target_item_id = target_item_id
        self.hot_threshold = float(hot_threshold)
        self.rich_max_mult = float(rich_max_mult)
        self.rich_target_mult = float(rich_target_mult)
        self.lean_min_mult = float(lean_min_mult)
        self.lean_target_mult = float(lean_target_mult)

    def detect(self, ctx: DetectionContext) -> List[Finding]:
        if ctx.base_pvv_path is None or not ctx.base_pvv_path.exists():
            return []
        root = ET.parse(ctx.base_pvv_path).getroot()
        try:
            table = parse_table(root, self.target_item_id)
        except ValueError:
            return []

        values = table.values.flatten()
        cols = table.col_axis.flatten()
        if len(values) != len(cols):
            return []
        hot_indices = np.where(cols >= (self.hot_threshold - 1e-9))[0]
        if hot_indices.size == 0:
            return []

        hot_values = values[hot_indices]
        hot_min = float(np.min(hot_values))
        hot_max = float(np.max(hot_values))
        hot_mean = float(np.mean(hot_values))
        n_hot = int(hot_indices.size)

        findings: List[Finding] = []

        # Rich-spike path.
        if hot_max > self.rich_max_mult + 1e-9:
            distance_pct = (hot_max - self.rich_max_mult) / self.rich_max_mult * 100.0
            n_above = int(np.sum(hot_values > self.rich_max_mult))
            confidence = min(1.0, 0.4 + 0.6 * (n_above / max(n_hot, 1)))
            findings.append(
                Finding(
                    kind=_ACCEL_RICH_KIND,
                    severity=_severity_from_distance(distance_pct),
                    confidence=confidence,
                    evidence={
                        "target_item_id": self.target_item_id,
                        "hot_threshold": self.hot_threshold,
                        "rich_max_mult": self.rich_max_mult,
                        "hot_max": hot_max,
                        "hot_mean": hot_mean,
                        "hot_cells_above": n_above,
                        "hot_cells_total": n_hot,
                        "distance_pct_above_threshold": distance_pct,
                    },
                    suggested_tool=_ACCEL_ENRICH_TOOL,
                    tool_params={
                        "target_item_id": self.target_item_id,
                        "hot_threshold": self.hot_threshold,
                        "target_hot": self.rich_target_mult,
                    },
                    source="accel_transient_detector",
                )
            )

        # Lean-lag path.
        if hot_min < self.lean_min_mult - 1e-9:
            distance_pct = (self.lean_min_mult - hot_min) / self.lean_min_mult * 100.0
            n_below = int(np.sum(hot_values < self.lean_min_mult))
            confidence = min(1.0, 0.4 + 0.6 * (n_below / max(n_hot, 1)))
            findings.append(
                Finding(
                    kind=_ACCEL_LEAN_KIND,
                    severity=_severity_from_distance(distance_pct),
                    confidence=confidence,
                    evidence={
                        "target_item_id": self.target_item_id,
                        "hot_threshold": self.hot_threshold,
                        "lean_min_mult": self.lean_min_mult,
                        "hot_min": hot_min,
                        "hot_mean": hot_mean,
                        "hot_cells_below": n_below,
                        "hot_cells_total": n_hot,
                        "distance_pct_below_threshold": distance_pct,
                    },
                    suggested_tool=_ACCEL_ENRICH_TOOL,
                    tool_params={
                        "target_item_id": self.target_item_id,
                        "hot_threshold": self.hot_threshold,
                        "target_hot": self.lean_target_mult,
                    },
                    source="accel_transient_detector",
                )
            )

        return findings
