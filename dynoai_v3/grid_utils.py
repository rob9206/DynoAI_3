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
    dst_points = np.array([
        [r, m] for r in dst_rpm_arr for m in dst_map_arr
    ])

    resampled_flat = interp(dst_points)
    resampled = resampled_flat.reshape(len(dst_rpm_arr), len(dst_map_arr))

    logger.info(
        "Resampled VE table: (%d x %d) -> (%d x %d)",
        len(src_rpm_arr), len(src_map_arr),
        len(dst_rpm_arr), len(dst_map_arr),
    )

    return resampled
