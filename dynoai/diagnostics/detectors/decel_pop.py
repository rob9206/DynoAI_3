"""DecelPopDetector: flag aggressively-lean decel enleanment tables.

Tune-as-data detector (same shape as IdleVeNoiseDetector). Reads
`tbl_deceleration_enleanment` from the base PVV directly. If the *hottest*
cells (T >= hot_threshold) carry a lambda multiplier below `min_safe_mult`,
the tune is configured to enlean overrun aggressively enough to cause
popping, backfire, and stalling. Fires a `decel_pop` Finding routed to
the `decel_enleanment` tool.

This is a *configuration* detector — it doesn't need pull data. The
trigger is "the tune itself looks miscalibrated for decel". If the tune
is fine but the customer still reports popping, that's a different issue
(usually exhaust-side, not fueling).

Severity mapping (min hot-side multiplier -> severity 0..1):
    >= min_safe_mult : no finding
    0.45..threshold  : 0.30 -> 0.50 (mild)
    0.35..0.45       : 0.50 -> 0.75 (moderate)
    0.20..0.35       : 0.75 -> 1.00 (severe)
    < 0.20           : 1.00 (catastrophic)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List, Tuple

import numpy as np

from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.finding import Finding
from dynoai.pvv.io import parse_table


_DECEL_POP_KIND = "decel_pop"
_DECEL_ENLEANMENT_TOOL = "decel_enleanment"


def _severity_from_min_mult(value: float, threshold: float) -> float:
    v = float(value)
    if v >= threshold:
        return 0.0
    if v >= 0.45:
        span = max(threshold - 0.45, 1e-9)
        return 0.30 + (threshold - v) * (0.50 - 0.30) / span
    if v >= 0.35:
        return 0.50 + (0.45 - v) * (0.75 - 0.50) / 0.10
    if v >= 0.20:
        return 0.75 + (0.35 - v) * (1.00 - 0.75) / 0.15
    return 1.0


class DecelPopDetector:
    """Flags aggressively-lean decel enleanment tables.

    Reads the base PVV's `tbl_deceleration_enleanment` directly; no
    surfaces required. Use this detector whenever there's a base tune to
    inspect, with or without pull data.
    """

    name = "decel_pop_detector"
    fix_kinds: Tuple[str, ...] = (_DECEL_POP_KIND,)

    def __init__(
        self,
        *,
        target_item_id: str = "tbl_deceleration_enleanment",
        hot_threshold: float = 140.0,
        min_safe_mult: float = 0.55,
    ) -> None:
        if min_safe_mult <= 0.0 or min_safe_mult > 1.0:
            raise ValueError("min_safe_mult must be in (0, 1]")
        self.target_item_id = target_item_id
        self.hot_threshold = float(hot_threshold)
        self.min_safe_mult = float(min_safe_mult)

    def detect(self, ctx: DetectionContext) -> List[Finding]:
        if ctx.base_pvv_path is None or not ctx.base_pvv_path.exists():
            return []
        root = ET.parse(ctx.base_pvv_path).getroot()
        try:
            table = parse_table(root, self.target_item_id)
        except ValueError:
            return []

        # 1-D table expected, but tolerate weirdness by collapsing.
        values = table.values.flatten()
        # Column axis carries temperature labels.
        cols = table.col_axis.flatten()
        if len(values) != len(cols):
            return []

        hot_indices = np.where(cols >= (self.hot_threshold - 1e-9))[0]
        if hot_indices.size == 0:
            return []

        hot_values = values[hot_indices]
        hot_min = float(np.min(hot_values))
        hot_mean = float(np.mean(hot_values))
        hot_max = float(np.max(hot_values))

        if hot_min >= self.min_safe_mult:
            return []

        severity = _severity_from_min_mult(hot_min, self.min_safe_mult)
        # Confidence: more hot cells below threshold = more confident in the call.
        cells_below = int(np.sum(hot_values < self.min_safe_mult))
        confidence = min(1.0, 0.4 + 0.6 * (cells_below / max(len(hot_values), 1)))

        return [
            Finding(
                kind=_DECEL_POP_KIND,
                severity=severity,
                confidence=confidence,
                evidence={
                    "target_item_id": self.target_item_id,
                    "hot_threshold": self.hot_threshold,
                    "min_safe_mult": self.min_safe_mult,
                    "hot_cells_total": int(hot_indices.size),
                    "hot_cells_below_threshold": cells_below,
                    "hot_min": hot_min,
                    "hot_mean": hot_mean,
                    "hot_max": hot_max,
                },
                suggested_tool=_DECEL_ENLEANMENT_TOOL,
                tool_params={
                    "target_item_id": self.target_item_id,
                    "hot_threshold": self.hot_threshold,
                },
                source="decel_pop_detector",
            )
        ]
