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
from dynoai.diagnostics.detectors.accel_transient import AccelTransientDetector
from dynoai.diagnostics.detectors.decel_pop import DecelPopDetector
from dynoai.diagnostics.detectors.idle_ve_noise import IdleVeNoiseDetector
from dynoai.diagnostics.detectors.injector_mismatch import InjectorMismatchDetector
from dynoai.diagnostics.detectors.knock_hotspot import KnockHotspotDetector
from dynoai.diagnostics.detectors.spark_valley import SparkValleyDetector
from dynoai.diagnostics.detectors.wot_lean import WotLeanDetector
from dynoai.diagnostics.dispatcher import TuningDispatcher
from dynoai.tools.accel_enrich import AccelEnrichTool
from dynoai.tools.decel_enleanment import DecelEnleanmentTool
from dynoai.tools.gp_smooth_idle_cruise_ve import GpSmoothIdleCruiseVeTool
from dynoai.tools.idle_ve_scale import IdleVeScaleTool
from dynoai.tools.injector_scalar_rebase import InjectorScalarRebaseTool
from dynoai.tools.spark_feathered_ramp import SparkFeatheredRampTool
from dynoai.tools.spark_knock_hotspot import SparkKnockHotspotTool
from dynoai.tools.wot_ve_graft import WotVeGraftTool


def build_default_dispatcher(
    *,
    donor_pvv_path: Optional[Path] = None,
    include_wot_lean: bool = True,
) -> TuningDispatcher:
    """Construct a TuningDispatcher with the full detector + tool set.

    Args:
        donor_pvv_path: PVV file to use as donor for `WotLeanDetector` ->
            `wot_ve_graft` routing. If None and `include_wot_lean=True`,
            the detector still emits findings but the tool's `plan()` will
            reject them (fail-closed). Pass an actual donor PVV to enable
            end-to-end WOT graft recommendations.
        include_wot_lean: If False, `WotLeanDetector` is omitted entirely.
            Useful when no donor is available and the caller doesn't want
            the noise of "lean detected, but I can't fix it" findings.

    Detectors registered (7 total when include_wot_lean=True):
      - SparkValleyDetector       -> spark_feathered_ramp
      - KnockHotspotDetector      -> spark_knock_hotspot
      - IdleVeNoiseDetector       -> gp_smooth_idle_cruise_ve
      - WotLeanDetector*          -> wot_ve_graft
      - DecelPopDetector          -> decel_enleanment
      - AccelTransientDetector    -> accel_enrich (rich + lean paths)
      - InjectorMismatchDetector  -> injector_scalar_rebase

    Tools registered (7 total):
      - spark_feathered_ramp, spark_knock_hotspot,
        gp_smooth_idle_cruise_ve, wot_ve_graft,
        decel_enleanment, accel_enrich, injector_scalar_rebase

    The dispatcher's rank-by-(severity*confidence) policy + the AGENTS.md
    "one correction pass per iter" picker means a single step() call
    returns the single most actionable finding plus its bound ToolPlan.

    *WotLeanDetector is included only when `include_wot_lean=True`.
    """
    detectors: list[Detector] = [
        SparkValleyDetector(),
        KnockHotspotDetector(),
        IdleVeNoiseDetector(),
        DecelPopDetector(),
        AccelTransientDetector(),
        InjectorMismatchDetector(),
    ]
    if include_wot_lean:
        detectors.append(WotLeanDetector(donor_pvv_path=donor_pvv_path))

    tools = {
        SparkFeatheredRampTool().name: SparkFeatheredRampTool(),
        SparkKnockHotspotTool().name: SparkKnockHotspotTool(),
        GpSmoothIdleCruiseVeTool().name: GpSmoothIdleCruiseVeTool(),
        WotVeGraftTool().name: WotVeGraftTool(),
        DecelEnleanmentTool().name: DecelEnleanmentTool(),
        AccelEnrichTool().name: AccelEnrichTool(),
        InjectorScalarRebaseTool().name: InjectorScalarRebaseTool(),
        IdleVeScaleTool().name: IdleVeScaleTool(),
    }

    return TuningDispatcher(detectors=detectors, tools=tools)
