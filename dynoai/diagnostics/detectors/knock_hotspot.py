"""KnockHotspotDetector: find contiguous high-knock zones from a knock surface.

Consumes ctx.surfaces["knock_front"] (or "knock_rear" / "knock_global") where
each cell carries the knock rate (events per sample, 0..1). Emits one Finding
per detected hotspot with the zone's minimum RPM/load bounds packed into
tool_params so `spark_knock_hotspot` can apply directly.

Severity mapping (peak knock rate -> severity 0..1):
    < min_knock_rate: not a hotspot
    threshold..0.10 : 0.40 -> 0.65 (mild, occasional pings)
    0.10..0.25      : 0.65 -> 0.85 (moderate)
    0.25..0.50      : 0.85 -> 1.00 (severe)
    >= 0.50         : 1.00 saturated

Confidence reflects how many cells (and how many samples) supported the zone:
the more cells above threshold and the larger the hit count, the more
confident the detector is.

Unit conversion:
    Surface2D.rpm_axis bins are assumed to be raw RPM (e.g. 5000, 5500).
    `tool_params["rpm_min_krpm"]` is in kRPM (5.0, 5.5) to match the tool's
    schema. Detection is based on the highest-bin maximum so this works
    regardless of which axis convention upstream code uses, but we emit kRPM
    for the tool.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional, Tuple

import numpy as np

from dynoai.core.surface_builder import Surface2D
from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.finding import Finding


_KNOCK_HOTSPOT_KIND = "knock_hotspot"
_SPARK_KNOCK_HOTSPOT_TOOL = "spark_knock_hotspot"

_SURFACE_KEYS_BY_CYLINDER: Tuple[Tuple[str, str], ...] = (
    ("knock_front", "front"),
    ("knock_rear", "rear"),
    ("knock_global", "global"),
)


def _severity_from_peak_rate(rate: float, threshold: float) -> float:
    r = float(rate)
    if r < threshold:
        return 0.0
    if r <= 0.10:
        span = max(0.10 - threshold, 1e-9)
        return 0.40 + (r - threshold) * (0.65 - 0.40) / span
    if r <= 0.25:
        return 0.65 + (r - 0.10) * (0.85 - 0.65) / 0.15
    if r <= 0.50:
        return 0.85 + (r - 0.25) * (1.00 - 0.85) / 0.25
    return 1.0


def _rpm_to_krpm(rpm_value: float) -> float:
    """Raw RPM -> kRPM. If the input already looks like kRPM (<= 100), keep it."""
    return float(rpm_value) / 1000.0 if rpm_value > 100.0 else float(rpm_value)


def _hotspot_zone(
    surface: Surface2D,
    threshold: float,
    min_cells: int,
) -> Optional[dict]:
    """Find the bounding box around cells with knock_rate >= threshold.

    Returns None if fewer than `min_cells` cells qualify. Otherwise returns
    a dict with min/max RPM and load axis values plus aggregate stats.
    """
    rpm_bins = list(surface.rpm_axis.bins)
    load_bins = list(surface.map_axis.bins)
    n_rpm = len(rpm_bins)
    n_load = len(load_bins)

    hot_indices: list[tuple[int, int]] = []
    peak_rate = 0.0
    total_hits = 0
    qualifying_hits = 0

    for r in range(n_rpm):
        for k in range(n_load):
            rate = surface.values[r][k]
            hits = surface.hit_count[r][k]
            if rate is None or hits is None:
                continue
            total_hits += int(hits)
            if float(rate) >= threshold:
                hot_indices.append((r, k))
                qualifying_hits += int(hits)
                peak_rate = max(peak_rate, float(rate))

    if len(hot_indices) < min_cells:
        return None

    rmin = min(r for r, _ in hot_indices)
    rmax = max(r for r, _ in hot_indices)
    kmin = min(k for _, k in hot_indices)
    kmax = max(k for _, k in hot_indices)
    return {
        "rpm_min_axis": float(rpm_bins[rmin]),
        "rpm_max_axis": float(rpm_bins[rmax]),
        "load_min_axis": float(load_bins[kmin]),
        "load_max_axis": float(load_bins[kmax]),
        "cells_hot": len(hot_indices),
        "peak_knock_rate": peak_rate,
        "qualifying_hits": qualifying_hits,
        "total_hits": total_hits,
        "threshold": threshold,
    }


def _confidence_from_zone(zone: Mapping[str, Any], min_cells: int) -> float:
    cells_hot = int(zone["cells_hot"])
    hits = int(zone["qualifying_hits"])
    # Cell-count contribution (0..0.5): saturates at 3x min_cells.
    cell_factor = min(0.5, 0.5 * (cells_hot / max(3 * min_cells, 1)))
    # Hit-count contribution (0..0.5): saturates at 60 samples in zone.
    hit_factor = min(0.5, 0.5 * (hits / 60.0))
    return min(1.0, cell_factor + hit_factor)


def _convert(zone: Mapping[str, Any], cylinder: str, min_cells: int) -> Finding:
    rpm_min_krpm = _rpm_to_krpm(float(zone["rpm_min_axis"]))
    load_min_kpa = float(zone["load_min_axis"])
    severity = _severity_from_peak_rate(
        float(zone["peak_knock_rate"]), float(zone["threshold"])
    )
    confidence = _confidence_from_zone(zone, min_cells)
    return Finding(
        kind=_KNOCK_HOTSPOT_KIND,
        severity=severity,
        confidence=confidence,
        evidence={
            "cylinder": cylinder,
            "rpm_min_axis": zone["rpm_min_axis"],
            "rpm_max_axis": zone["rpm_max_axis"],
            "load_min_axis": zone["load_min_axis"],
            "load_max_axis": zone["load_max_axis"],
            "cells_hot": zone["cells_hot"],
            "peak_knock_rate": zone["peak_knock_rate"],
            "qualifying_hits": zone["qualifying_hits"],
            "total_hits": zone["total_hits"],
            "threshold": zone["threshold"],
        },
        suggested_tool=_SPARK_KNOCK_HOTSPOT_TOOL,
        tool_params={
            "rpm_min_krpm": rpm_min_krpm,
            "load_min_kpa": load_min_kpa,
        },
        source="knock_hotspot_detector",
    )


class KnockHotspotDetector:
    """Detects contiguous high-knock zones from a knock-rate Surface2D."""

    name = "knock_hotspot_detector"
    fix_kinds: Tuple[str, ...] = (_KNOCK_HOTSPOT_KIND,)

    def __init__(
        self,
        *,
        min_knock_rate: float = 0.05,
        min_cells: int = 3,
    ) -> None:
        if min_knock_rate <= 0.0 or min_knock_rate > 1.0:
            raise ValueError("min_knock_rate must be in (0, 1]")
        if min_cells < 1:
            raise ValueError("min_cells must be >= 1")
        self.min_knock_rate = float(min_knock_rate)
        self.min_cells = int(min_cells)

    def detect(self, ctx: DetectionContext) -> List[Finding]:
        if not ctx.surfaces:
            return []
        findings: List[Finding] = []
        for surface_key, cylinder in _SURFACE_KEYS_BY_CYLINDER:
            surface = ctx.surfaces.get(surface_key)
            if surface is None:
                continue
            zone = _hotspot_zone(surface, self.min_knock_rate, self.min_cells)
            if zone is None:
                continue
            findings.append(_convert(zone, cylinder, self.min_cells))
        return findings
