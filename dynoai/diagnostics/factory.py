"""TuningDispatcher factory with the standard detector + tool set.

A workflow caller (API route, CLI, test) typically wants the full
diagnostics stack: all four detectors that emit canonical Findings, all
four tools that can address them, wired into a single TuningDispatcher.

This module is the one-call constructor for that. Keep the option to
build a custom dispatcher (subset of detectors + tools) by going through
the TuningDispatcher constructor directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from dynoai.diagnostics.detector import Detector
from dynoai.diagnostics.detectors.idle_ve_noise import IdleVeNoiseDetector
from dynoai.diagnostics.detectors.knock_hotspot import KnockHotspotDetector
from dynoai.diagnostics.detectors.spark_valley import SparkValleyDetector
from dynoai.diagnostics.detectors.wot_lean import WotLeanDetector
from dynoai.diagnostics.dispatcher import TuningDispatcher
from dynoai.tools.gp_smooth_idle_cruise_ve import GpSmoothIdleCruiseVeTool
from dynoai.tools.spark_feathered_ramp import SparkFeatheredRampTool
from dynoai.tools.spark_knock_hotspot import SparkKnockHotspotTool
from dynoai.tools.wot_ve_graft import WotVeGraftTool


def build_default_dispatcher(
    *,
    donor_pvv_path: Optional[Path] = None,
    include_wot_lean: bool = True,
) -> TuningDispatcher:
    """Construct a TuningDispatcher with all four detectors and all four tools.

    Args:
        donor_pvv_path: PVV file to use as donor for `WotLeanDetector` ->
            `wot_ve_graft` routing. If None and `include_wot_lean=True`,
            the detector still emits findings but the tool's `plan()` will
            reject them (fail-closed). Pass an actual donor PVV to enable
            end-to-end WOT graft recommendations.
        include_wot_lean: If False, `WotLeanDetector` is omitted entirely.
            Useful when no donor is available and the caller doesn't want
            the noise of "lean detected, but I can't fix it" findings.

    The returned dispatcher carries:
      - 4 detectors (spark_valley, knock_hotspot, idle_ve_noise, wot_lean*)
      - 4 tools (spark_feathered_ramp, spark_knock_hotspot,
                 gp_smooth_idle_cruise_ve, wot_ve_graft)
      - The dispatcher's standard rank-by-(severity*confidence) policy
        plus the AGENTS.md "one correction pass per iter" picker.

    *WotLeanDetector is included only when `include_wot_lean=True`.
    """
    detectors: list[Detector] = [
        SparkValleyDetector(),
        KnockHotspotDetector(),
        IdleVeNoiseDetector(),
    ]
    if include_wot_lean:
        detectors.append(WotLeanDetector(donor_pvv_path=donor_pvv_path))

    tools = {
        SparkFeatheredRampTool().name: SparkFeatheredRampTool(),
        SparkKnockHotspotTool().name: SparkKnockHotspotTool(),
        GpSmoothIdleCruiseVeTool().name: GpSmoothIdleCruiseVeTool(),
        WotVeGraftTool().name: WotVeGraftTool(),
    }

    return TuningDispatcher(detectors=detectors, tools=tools)
