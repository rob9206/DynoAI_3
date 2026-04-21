"""
DynoAI v3.0 — Grid Utilities
================================

Shared helpers for RPM/MAP grid operations:
    - ``nearest_idx``: snap a continuous value to the nearest bin index
    - ``resample_ve_table``: bilinear interpolation from one grid to another

Author: Thunderhorse Tuning / DynoAI
"""

from __future__ import annotations

import logging
from typing import List, Sequence, Union

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


def nearest_idx(value: float, bins: Sequence[float]) -> int:
    """
    Return the index of the bin closest to *value*.

    Args:
        value: Scalar value to snap.
        bins:  Sorted sequence of bin centres.

    Returns:
        Integer index into *bins*.
    """
    arr = np.asarray(bins, dtype=np.float64)
    return int(np.argmin(np.abs(arr - value)))


def resample_ve_table(
    table: NDArray[np.float64],
    src_rpm: Union[List[float], NDArray[np.float64]],
    src_map: Union[List[float], NDArray[np.float64]],
    dst_rpm: Union[List[float], NDArray[np.float64]],
    dst_map: Union[List[float], NDArray[np.float64]],
) -> NDArray[np.float64]:
    """
    Bilinearly interpolate a VE table from one grid to another.

    This is needed when a PVV import's grid doesn't match the session
    grid (different bin count or range).

    Args:
        table:   Source VE table, shape ``(len(src_rpm), len(src_map))``.
        src_rpm: RPM bins of the source table.
        src_map: MAP bins of the source table (kPa).
        dst_rpm: RPM bins of the destination grid.
        dst_map: MAP bins of the destination grid (kPa).

    Returns:
        Resampled VE table, shape ``(len(dst_rpm), len(dst_map))``.
    """
    from scipy.interpolate import RegularGridInterpolator

    src_rpm_arr = np.asarray(src_rpm, dtype=np.float64)
    src_map_arr = np.asarray(src_map, dtype=np.float64)
    dst_rpm_arr = np.asarray(dst_rpm, dtype=np.float64)
    dst_map_arr = np.asarray(dst_map, dtype=np.float64)
    table_arr = np.asarray(table, dtype=np.float64)

    if table_arr.shape != (len(src_rpm_arr), len(src_map_arr)):
        raise ValueError(
            f"table shape {table_arr.shape} doesn't match "
            f"src grid ({len(src_rpm_arr)}, {len(src_map_arr)})"
        )

    interp = RegularGridInterpolator(
        (src_rpm_arr, src_map_arr),
        table_arr,
        method="linear",
        bounds_error=False,
        fill_value=None,  # extrapolate
    )

    # Build destination grid points
    dst_points = np.array([[r, m] for r in dst_rpm_arr for m in dst_map_arr])

    resampled_flat = interp(dst_points)
    resampled = resampled_flat.reshape(len(dst_rpm_arr), len(dst_map_arr))

    # Clamp extrapolated values to source edge values
    # This prevents garbage values when target MAP bins extend outside source range
    src_rpm_min, src_rpm_max = src_rpm_arr[0], src_rpm_arr[-1]
    src_map_min, src_map_max = src_map_arr[0], src_map_arr[-1]

    for ri, dst_r in enumerate(dst_rpm_arr):
        for ci, dst_m in enumerate(dst_map_arr):
            # Clamp to source grid edges if outside source range
            clamped_r = np.clip(dst_r, src_rpm_min, src_rpm_max)
            clamped_m = np.clip(dst_m, src_map_min, src_map_max)

            # If clamping occurred, re-interpolate at the clamped coordinates
            if clamped_r != dst_r or clamped_m != dst_m:
                resampled[ri, ci] = float(interp([[clamped_r, clamped_m]])[0])

    logger.info(
        "Resampled VE table: (%d x %d) -> (%d x %d), MAP range src=[%.1f-%.1f] dst=[%.1f-%.1f]",
        len(src_rpm_arr),
        len(src_map_arr),
        len(dst_rpm_arr),
        len(dst_map_arr),
        src_map_min,
        src_map_max,
        dst_map_arr[0],
        dst_map_arr[-1],
    )

    return resampled
