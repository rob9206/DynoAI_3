"""SparkValleyDetector: adapter over dynoai/core/spark_valley.detect_valleys_multi_cylinder.

Consumes ctx.surfaces["spark_front"] / ["spark_rear"] / ["spark_global"] and
emits canonical Findings. The underlying detection algorithm in
dynoai/core/spark_valley.py is unchanged; this module only translates its
SparkValleyFinding outputs into the dispatcher's Finding shape.

Severity mapping (depth_deg -> severity 0..1):
    <  2 deg : suppressed (already below the core detector's min_depth_deg)
    2-4 deg  : 0.30 - 0.50
    4-6 deg  : 0.50 - 0.75
    6-10 deg : 0.75 - 1.00
    >10 deg  : 1.00 (saturated)

confidence is passed through verbatim from the core detector.

Tool routing:
  cylinder == "front" -> suggested_tool = "spark_feathered_ramp"
  cylinder == "rear"  -> suggested_tool = None (no rear tool yet)
  cylinder == "global"-> suggested_tool = "spark_feathered_ramp" (front by default)
"""

from __future__ import annotations

from typing import List, Tuple

from dynoai.core.spark_valley import (
    SparkValleyFinding,
    detect_valleys_multi_cylinder,
)
from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.finding import Finding


_SPARK_VALLEY_KIND = "spark_valley"
_SPARK_FEATHERED_RAMP_TOOL = "spark_feathered_ramp"


def _severity_from_depth(depth_deg: float) -> float:
    """Piecewise-linear mapping of valley depth to severity 0..1."""
    d = float(depth_deg)
    if d <= 2.0:
        return 0.3
    if d <= 4.0:
        return 0.3 + (d - 2.0) * (0.5 - 0.3) / 2.0
    if d <= 6.0:
        return 0.5 + (d - 4.0) * (0.75 - 0.5) / 2.0
    if d <= 10.0:
        return 0.75 + (d - 6.0) * (1.0 - 0.75) / 4.0
    return 1.0


def _suggested_tool_for_cylinder(cylinder: str) -> str | None:
    if cylinder == "front":
        return _SPARK_FEATHERED_RAMP_TOOL
    if cylinder == "global":
        # The front tool covers the global case by default; rear-specific
        # tool not yet lifted from seanbike/.
        return _SPARK_FEATHERED_RAMP_TOOL
    return None


def _convert(svf: SparkValleyFinding) -> Finding:
    return Finding(
        kind=_SPARK_VALLEY_KIND,
        severity=_severity_from_depth(svf.depth_deg),
        confidence=float(svf.confidence),
        evidence={
            "cylinder": svf.cylinder,
            "rpm_center": float(svf.rpm_center),
            "rpm_band": [float(svf.rpm_band[0]), float(svf.rpm_band[1])],
            "depth_deg": float(svf.depth_deg),
            "valley_min_deg": float(svf.valley_min_deg),
            "pre_valley_deg": float(svf.pre_valley_deg),
            "post_valley_deg": float(svf.post_valley_deg),
            "map_band_used": float(svf.map_band_used),
            "detector_evidence": list(svf.evidence),
        },
        suggested_tool=_suggested_tool_for_cylinder(svf.cylinder),
        tool_params={},
        source="spark_valley_detector",
    )


class SparkValleyDetector:
    """Detects knock-limited spark valleys at high MAP via dynoai/core."""

    name = "spark_valley_detector"
    fix_kinds: Tuple[str, ...] = (_SPARK_VALLEY_KIND,)

    def __init__(self, *, high_map_min_kpa: float = 80.0) -> None:
        self.high_map_min_kpa = float(high_map_min_kpa)

    def detect(self, ctx: DetectionContext) -> List[Finding]:
        if not ctx.surfaces:
            return []
        # detect_valleys_multi_cylinder accepts the same {name -> Surface2D}
        # dict shape we pass through DetectionContext.surfaces.
        svfs = detect_valleys_multi_cylinder(
            dict(ctx.surfaces),
            high_map_min_kpa=self.high_map_min_kpa,
        )
        return [_convert(svf) for svf in svfs]
