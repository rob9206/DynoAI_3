"""Convert PVV tables into Surface2D views.

Bridges `dynoai.pvv.io.parse_table` (which returns numpy-backed TableData
plus XML cell refs) and `dynoai.core.surface_builder.Surface2D` (which is
the cached/serialized form used by the NextGen workflow and consumed by
surface-based detectors).

Why this exists:
  - PVV tables are *tune data* (the configuration), not measured surfaces.
    Every cell carries a meaningful value by construction — there are no
    "missing" cells the way there are in a pull-derived surface.
  - To plug into the existing diagnostics framework symmetrically, we
    wrap each table as a Surface2D so detectors can consume them via
    `ctx.surfaces["ve_front"]` / `["ve_rear"]` instead of needing the
    base PVV path.

The wrapped surface uses `hit_count = 1` for every cell (synthetic — the
tune itself defines every cell, so coverage is universal by definition).
The mask_info field records that this is a tune-data view, not a
measured surface, so downstream consumers can distinguish.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict

from dynoai.core.surface_builder import Surface2D, SurfaceAxis, SurfaceStats
from dynoai.pvv.io import TableData, parse_table


# Default VE table ids and axis labeling for the seanbike / standard TPS-based
# tune family. Other table families can override via load_ve_surfaces() args.
DEFAULT_VE_FRONT_ID = "tbl_ve_tps_based_front_cyl"
DEFAULT_VE_REAR_ID = "tbl_ve_tps_based_rear_cyl"
DEFAULT_RPM_UNIT = "kRPM"
DEFAULT_LOAD_UNIT = "%"
DEFAULT_LOAD_NAME = "tps"


def _stats_from_values(values_2d: list[list[float]]) -> SurfaceStats:
    flat = [v for row in values_2d for v in row]
    if not flat:
        return SurfaceStats(
            min=None, max=None, mean=None, p05=None, p95=None,
            non_nan_cells=0, total_cells=0, total_samples=0,
        )
    sorted_flat = sorted(flat)
    n = len(sorted_flat)
    p05_idx = max(0, int(0.05 * n) - 1)
    p95_idx = min(n - 1, int(0.95 * n) - 1)
    return SurfaceStats(
        min=float(sorted_flat[0]),
        max=float(sorted_flat[-1]),
        mean=float(sum(flat) / n),
        p05=float(sorted_flat[p05_idx]),
        p95=float(sorted_flat[p95_idx]),
        non_nan_cells=n,
        total_cells=n,
        total_samples=n,
    )


def ve_table_to_surface(
    table: TableData,
    *,
    surface_id: str,
    title: str,
    description: str = "tune-declared VE table (PVV view)",
    rpm_unit: str = DEFAULT_RPM_UNIT,
    load_name: str = DEFAULT_LOAD_NAME,
    load_unit: str = DEFAULT_LOAD_UNIT,
) -> Surface2D:
    """Wrap an already-parsed PVV TableData as a Surface2D.

    Useful when the caller already has TableData in hand (e.g. computed
    via `dynoai.pvv.io.parse_table`).
    """
    values: list[list[float]] = [
        [float(v) for v in row] for row in table.values.tolist()
    ]
    hit_count: list[list[int]] = [[1] * len(row) for row in values]
    return Surface2D(
        surface_id=surface_id,
        title=title,
        description=description,
        rpm_axis=SurfaceAxis(
            name="rpm",
            unit=rpm_unit,
            bins=[float(v) for v in table.row_axis.tolist()],
        ),
        map_axis=SurfaceAxis(
            name=load_name,
            unit=load_unit,
            bins=[float(v) for v in table.col_axis.tolist()],
        ),
        values=values,  # type: ignore[arg-type]
        hit_count=hit_count,
        stats=_stats_from_values(values),
        mask_info="pvv_tune_view",
    )


def ve_surface_from_pvv(
    pvv_path: Path,
    *,
    table_id: str,
    surface_id: str,
    title: str | None = None,
    description: str = "tune-declared VE table (PVV view)",
    rpm_unit: str = DEFAULT_RPM_UNIT,
    load_name: str = DEFAULT_LOAD_NAME,
    load_unit: str = DEFAULT_LOAD_UNIT,
) -> Surface2D:
    """Parse a PVV table by id and wrap it as a Surface2D.

    Raises ValueError if the table isn't in the PVV.
    """
    root = ET.parse(pvv_path).getroot()
    table = parse_table(root, table_id)
    return ve_table_to_surface(
        table,
        surface_id=surface_id,
        title=title or f"{surface_id} (from PVV)",
        description=description,
        rpm_unit=rpm_unit,
        load_name=load_name,
        load_unit=load_unit,
    )


def load_ve_surfaces(
    pvv_path: Path,
    *,
    front_id: str = DEFAULT_VE_FRONT_ID,
    rear_id: str = DEFAULT_VE_REAR_ID,
    front_key: str = "ve_front",
    rear_key: str = "ve_rear",
) -> Dict[str, Surface2D]:
    """Load both VE tables from a PVV as a dict keyed by surface_id.

    Returns an empty dict if neither table is present (e.g. older tunes
    that use different Item ids). Partial success — if only one of the
    two tables is found, the dict will contain just that one. Caller
    decides whether to require both via downstream checks.
    """
    out: Dict[str, Surface2D] = {}
    if not pvv_path.exists():
        return out
    root = ET.parse(pvv_path).getroot()

    for key, table_id, title in (
        (front_key, front_id, "Front cylinder VE (PVV view)"),
        (rear_key, rear_id, "Rear cylinder VE (PVV view)"),
    ):
        try:
            table = parse_table(root, table_id)
        except ValueError:
            continue
        out[key] = ve_table_to_surface(
            table,
            surface_id=key,
            title=title,
        )
    return out
