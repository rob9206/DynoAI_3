"""WotLeanDetector: find under-VE'd WOT cells from an AFR-error surface.

Consumes ctx.surfaces["afr_error_front"] / ["afr_error_rear"] / ["afr_error_global"]
where each cell value is `measured_AFR - target_AFR` (positive = lean, the
mixture is leaner than the tuner wants). Detects contiguous high-error
zones inside the WOT region (RPM >= wot_rpm_min_krpm AND TPS >=
wot_tps_min_pct) and emits one Finding per zone.

Routes to `wot_ve_graft` and packs the detected zone bounds into
tool_params so the graft tool applies directly to the same RPM/TPS region.
The donor PVV path is a *constructor argument* on this detector — the
caller (workflow, API route, dispatcher harness) chooses which prior tune
to graft from, since "donor selection" is a policy decision the detector
itself shouldn't make.

Severity mapping (peak AFR error in lean direction -> 0..1):
    < min_lean_afr_error : not a finding
    0.05..0.30           : 0.30 -> 0.50  (mild)
    0.30..0.70           : 0.50 -> 0.75  (moderate)
    0.70..1.50           : 0.75 -> 0.95  (severe)
    >= 1.50              : 1.00          (critical / dangerous)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Mapping, Optional, Tuple

from dynoai.core.surface_builder import Surface2D
from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.finding import Finding


_WOT_LEAN_KIND = "wot_lean"
_WOT_VE_GRAFT_TOOL = "wot_ve_graft"

_SURFACE_KEYS_BY_CYLINDER: Tuple[Tuple[str, str], ...] = (
    ("afr_error_front", "front"),
    ("afr_error_rear", "rear"),
    ("afr_error_global", "global"),
)


def _severity_from_peak_lean(error: float, threshold: float) -> float:
    e = float(error)
    if e < threshold:
        return 0.0
    if e <= 0.30:
        span = max(0.30 - threshold, 1e-9)
        return 0.30 + (e - threshold) * (0.50 - 0.30) / span
    if e <= 0.70:
        return 0.50 + (e - 0.30) * (0.75 - 0.50) / 0.40
    if e <= 1.50:
        return 0.75 + (e - 0.70) * (0.95 - 0.75) / 0.80
    return 1.0


def _rpm_to_krpm(rpm_value: float) -> float:
    return float(rpm_value) / 1000.0 if rpm_value > 100.0 else float(rpm_value)


def _hotzone_bounds(
    surface: Surface2D,
    *,
    wot_rpm_min_krpm: float,
    wot_tps_min_pct: float,
    min_lean_afr_error: float,
    min_cells: int,
) -> Optional[dict]:
    """Find the bounding box around lean cells inside the WOT region.

    Cell qualifies iff:
      - It's inside the WOT region (RPM >= wot_rpm_min, TPS >= wot_tps_min)
      - Its AFR-error value >= min_lean_afr_error (lean by that much)
    """
    rpm_bins = list(surface.rpm_axis.bins)
    load_bins = list(surface.map_axis.bins)
    n_rpm = len(rpm_bins)
    n_load = len(load_bins)

    hot_indices: list[tuple[int, int]] = []
    peak_error = 0.0
    qualifying_hits = 0
    total_hits = 0

    for r in range(n_rpm):
        rpm_value = float(rpm_bins[r])
        rpm_krpm = _rpm_to_krpm(rpm_value)
        if rpm_krpm < wot_rpm_min_krpm - 1e-9:
            continue
        for k in range(n_load):
            load_value = float(load_bins[k])
            if load_value < wot_tps_min_pct - 1e-9:
                continue
            error = surface.values[r][k]
            hits = surface.hit_count[r][k]
            if error is None or hits is None:
                continue
            total_hits += int(hits)
            if float(error) >= min_lean_afr_error:
                hot_indices.append((r, k))
                qualifying_hits += int(hits)
                peak_error = max(peak_error, float(error))

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
        "cells_lean": len(hot_indices),
        "peak_lean_afr_error": peak_error,
        "qualifying_hits": qualifying_hits,
        "total_hits_in_wot": total_hits,
        "threshold": min_lean_afr_error,
    }


def _confidence_from_zone(zone: Mapping[str, Any], min_cells: int) -> float:
    cells_lean = int(zone["cells_lean"])
    hits = int(zone["qualifying_hits"])
    cell_factor = min(0.5, 0.5 * (cells_lean / max(3 * min_cells, 1)))
    hit_factor = min(0.5, 0.5 * (hits / 60.0))
    return min(1.0, cell_factor + hit_factor)


def _convert(
    zone: Mapping[str, Any],
    cylinder: str,
    min_cells: int,
    donor_pvv_path: Optional[Path],
) -> Finding:
    rpm_min_krpm = _rpm_to_krpm(float(zone["rpm_min_axis"]))
    tps_min_pct = float(zone["load_min_axis"])
    severity = _severity_from_peak_lean(
        float(zone["peak_lean_afr_error"]), float(zone["threshold"])
    )
    confidence = _confidence_from_zone(zone, min_cells)
    tool_params: dict[str, Any] = {
        "rpm_min_krpm": rpm_min_krpm,
        "tps_min_pct": tps_min_pct,
    }
    if donor_pvv_path is not None:
        tool_params["donor_pvv_path"] = str(donor_pvv_path)
    return Finding(
        kind=_WOT_LEAN_KIND,
        severity=severity,
        confidence=confidence,
        evidence={
            "cylinder": cylinder,
            "rpm_min_axis": zone["rpm_min_axis"],
            "rpm_max_axis": zone["rpm_max_axis"],
            "load_min_axis": zone["load_min_axis"],
            "load_max_axis": zone["load_max_axis"],
            "cells_lean": zone["cells_lean"],
            "peak_lean_afr_error": zone["peak_lean_afr_error"],
            "qualifying_hits": zone["qualifying_hits"],
            "total_hits_in_wot": zone["total_hits_in_wot"],
            "threshold": zone["threshold"],
        },
        suggested_tool=_WOT_VE_GRAFT_TOOL,
        tool_params=tool_params,
        source="wot_lean_detector",
    )


class WotLeanDetector:
    """Detects WOT lean zones from an AFR-error Surface2D.

    The detected zone bounds are passed via Finding.tool_params so the
    routed `wot_ve_graft` tool applies to the same RPM/TPS region. The
    *donor PVV* (which prior tune to graft from) is a constructor
    argument because donor selection is a policy decision the detector
    itself shouldn't make.
    """

    name = "wot_lean_detector"
    fix_kinds: Tuple[str, ...] = (_WOT_LEAN_KIND,)

    def __init__(
        self,
        *,
        donor_pvv_path: Optional[Path] = None,
        wot_rpm_min_krpm: float = 5.0,
        wot_tps_min_pct: float = 80.0,
        min_lean_afr_error: float = 0.10,
        min_cells: int = 3,
    ) -> None:
        if min_lean_afr_error <= 0.0:
            raise ValueError("min_lean_afr_error must be > 0")
        if min_cells < 1:
            raise ValueError("min_cells must be >= 1")
        self.donor_pvv_path = Path(donor_pvv_path) if donor_pvv_path else None
        self.wot_rpm_min_krpm = float(wot_rpm_min_krpm)
        self.wot_tps_min_pct = float(wot_tps_min_pct)
        self.min_lean_afr_error = float(min_lean_afr_error)
        self.min_cells = int(min_cells)

    def detect(self, ctx: DetectionContext) -> List[Finding]:
        if not ctx.surfaces:
            return []
        findings: List[Finding] = []
        for surface_key, cylinder in _SURFACE_KEYS_BY_CYLINDER:
            surface = ctx.surfaces.get(surface_key)
            if surface is None:
                continue
            zone = _hotzone_bounds(
                surface,
                wot_rpm_min_krpm=self.wot_rpm_min_krpm,
                wot_tps_min_pct=self.wot_tps_min_pct,
                min_lean_afr_error=self.min_lean_afr_error,
                min_cells=self.min_cells,
            )
            if zone is None:
                continue
            findings.append(
                _convert(zone, cylinder, self.min_cells, self.donor_pvv_path)
            )
        return findings
