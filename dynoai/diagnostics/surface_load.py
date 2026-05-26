"""Helpers to load Surface2D objects from serialized payload dicts.

The NextGen workflow serializes Surface2D instances to plain dicts via
`Surface2D.to_dict()` when caching to disk. This module provides the
reverse operation so the diagnostics dispatcher can run on cached
payloads without re-executing the CSV-to-surface pipeline.

Pure conversion. No new analysis logic.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from dynoai.core.surface_builder import Surface2D, SurfaceAxis, SurfaceStats


def surface_from_dict(d: Mapping[str, Any]) -> Surface2D:
    """Reconstruct a Surface2D from its `.to_dict()` representation.

    Tolerates missing optional fields (mask_info, stats sub-fields) by
    falling back to sensible defaults. Lists in `values` / `hit_count`
    are kept as-is (Surface2D stores them as nested lists, not numpy
    arrays).
    """
    rpm_axis_d = d.get("rpm_axis", {})
    map_axis_d = d.get("map_axis", {})
    stats_d = d.get("stats", {}) or {}

    return Surface2D(
        surface_id=d.get("surface_id", ""),
        title=d.get("title", ""),
        description=d.get("description", ""),
        rpm_axis=SurfaceAxis(
            name=rpm_axis_d.get("name", "rpm"),
            unit=rpm_axis_d.get("unit", "RPM"),
            bins=list(rpm_axis_d.get("bins", [])),
        ),
        map_axis=SurfaceAxis(
            name=map_axis_d.get("name", "map"),
            unit=map_axis_d.get("unit", "kPa"),
            bins=list(map_axis_d.get("bins", [])),
        ),
        values=[list(row) for row in d.get("values", [])],
        hit_count=[list(row) for row in d.get("hit_count", [])],
        stats=SurfaceStats(
            min=stats_d.get("min"),
            max=stats_d.get("max"),
            mean=stats_d.get("mean"),
            p05=stats_d.get("p05"),
            p95=stats_d.get("p95"),
            non_nan_cells=int(stats_d.get("non_nan_cells", 0)),
            total_cells=int(stats_d.get("total_cells", 0)),
            total_samples=int(stats_d.get("total_samples", 0)),
        ),
        mask_info=d.get("mask_info"),
    )


def surfaces_from_payload(payload: Mapping[str, Any]) -> Dict[str, Surface2D]:
    """Extract and reconstruct all surfaces from a NextGenAnalysisPayload dict.

    Returns a dict keyed by surface_id (e.g. "spark_front", "afr_error_front",
    "knock_front"), ready to drop into `DetectionContext.surfaces`.
    """
    surfaces_section = payload.get("surfaces", {}) or {}
    return {
        sid: surface_from_dict(sd)
        for sid, sd in surfaces_section.items()
    }
