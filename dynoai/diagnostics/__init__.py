"""Diagnostics package: detectors, findings, and the tuning dispatcher.

A Detector consumes a DetectionContext (base PVV, vehicle profile, surfaces
built from pulls) and emits Findings. A Finding carries enough info for the
TuningDispatcher to rank it, look up a Tool that can address it, and hand
the Tool the params it needs to plan a patch.

The dispatcher enforces the AGENTS.md iteration discipline: one correction
pass + one verification gate per iter, with universal safety gates run
before any PVV mutation.
"""

from dynoai.diagnostics.detector import DetectionContext, Detector
from dynoai.diagnostics.detectors.accel_transient import AccelTransientDetector
from dynoai.diagnostics.detectors.decel_pop import DecelPopDetector
from dynoai.diagnostics.detectors.idle_ve_noise import IdleVeNoiseDetector
from dynoai.diagnostics.detectors.injector_mismatch import InjectorMismatchDetector
from dynoai.diagnostics.detectors.knock_hotspot import KnockHotspotDetector
from dynoai.diagnostics.detectors.spark_valley import SparkValleyDetector
from dynoai.diagnostics.detectors.wot_lean import WotLeanDetector
from dynoai.diagnostics.dispatcher import DispatchDecision, TuningDispatcher
from dynoai.diagnostics.factory import build_default_dispatcher
from dynoai.diagnostics.finding import Finding
from dynoai.diagnostics.surface_load import surface_from_dict, surfaces_from_payload

__all__ = [
    "AccelTransientDetector",
    "DecelPopDetector",
    "DetectionContext",
    "Detector",
    "DispatchDecision",
    "Finding",
    "IdleVeNoiseDetector",
    "InjectorMismatchDetector",
    "KnockHotspotDetector",
    "SparkValleyDetector",
    "TuningDispatcher",
    "WotLeanDetector",
    "build_default_dispatcher",
    "surface_from_dict",
    "surfaces_from_payload",
]
