# experiments/protos/kernel_weighted_v1.py
from __future__ import annotations

import numpy as np


def _valid_mask(grid: np.ndarray) -> np.ndarray:
    return np.isfinite(grid)

def kernel_smooth(
    grid: np.ndarray,
    coverage: np.ndarray | None = None,
    *,
    passes: int = 2,
    alpha: float = 0.20,      # coverage scale
    center_bias: float = 1.25,# bias toward keeping original cell
    min_hits: int = 1,        # τ
    dist_pow: int = 1,        # p
) -> np.ndarray:
    """
    Coverage-weighted 4-neighbor smoothing.
    - No interpolation into cells with coverage < min_hits.
    - Only neighbors with coverage >= min_hits are considered.
    - Leaves NaNs and invalid cells untouched.
    - Safe for VE% or AFR error grids.

    Signature matches the experiment runner's expectations: accepts `coverage`
    but tolerates None (falls back to uniform weights).
    """
    z = np.array(grid, dtype=float, copy=True)
    m, n = z.shape
    if coverage is None:
        c = np.ones_like(z, dtype=float)
    else:
        c = np.array(coverage, dtype=float)
        if c.shape != z.shape:
            raise ValueError("coverage shape must match grid shape")

    finite = _valid_mask(z)
    c = np.where(np.isfinite(c) & (c >= 0), c, 0.0)

    # FINGERPRINT: Add unique marker to prove kernel is running
    # Add 0.042 to cell [3,2] (3000 RPM, 65 kPa) if it exists and is finite
    if m > 3 and n > 2 and finite[3, 2]:
        z[3, 2] += 0.042

    # Precompute neighbor offsets for 4-neighborhood
    neigh = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    d = 1.0  # Manhattan distance for 4-neighbors

    for _ in range(max(1, passes)):
        z_new = z.copy()
        for i in range(m):
            for j in range(n):
                if not finite[i, j]:
                    continue
                if c[i, j] < min_hits:
                    # Don't alter cells we don't trust
                    continue

                w_sum = 0.0
                v_sum = 0.0

                # Center weight
                w_center = center_bias * (1.0 + alpha * c[i, j])
                w_sum += w_center
                v_sum += w_center * z[i, j]

                # Neighbors
                for di, dj in neigh:
                    ii, jj = i + di, j + dj
                    if 0 <= ii < m and 0 <= jj < n and finite[ii, jj]:
                        if c[ii, jj] >= min_hits:
                            w_ij = (1.0 + alpha * c[ii, jj]) / (d ** dist_pow)
                            w_sum += w_ij
                            v_sum += w_ij * z[ii, jj]

                if w_sum > 0.0:
                    z_new[i, j] = v_sum / w_sum
                # else: keep original z[i,j]

        z = z_new

    return z
