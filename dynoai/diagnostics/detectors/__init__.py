"""Detector implementations.

Each detector module adapts a dynoai/core analysis function to the canonical
Detector protocol + Finding shape defined in `dynoai.diagnostics`.

The adapters are intentionally thin: the analysis logic lives in dynoai/core
where it's been validated; the adapters translate dynoai/core's
issue-specific dataclasses (SparkValleyFinding, KnockHotspot, etc.) into
the uniform Finding shape the dispatcher consumes.
"""

from dynoai.diagnostics.detectors.accel_transient import AccelTransientDetector
from dynoai.diagnostics.detectors.decel_pop import DecelPopDetector
from dynoai.diagnostics.detectors.idle_ve_noise import IdleVeNoiseDetector
from dynoai.diagnostics.detectors.injector_mismatch import InjectorMismatchDetector
from dynoai.diagnostics.detectors.knock_hotspot import KnockHotspotDetector
from dynoai.diagnostics.detectors.spark_valley import SparkValleyDetector
from dynoai.diagnostics.detectors.wot_lean import WotLeanDetector

__all__ = [
    "AccelTransientDetector",
    "DecelPopDetector",
    "IdleVeNoiseDetector",
    "InjectorMismatchDetector",
    "KnockHotspotDetector",
    "SparkValleyDetector",
    "WotLeanDetector",
]
