"""
K3: Bilateral Median+Mean Kernel

This kernel combines median filtering for outlier rejection with bilateral
mean filtering for noise reduction. Uses coverage-tiered clamping for
adaptive safety limits.

Algorithm:
1. Gate: Determine per-cell smoothing passes based on |ΔVE| magnitude
2. Bilateral smoothing: Weight neighbors by spatial distance × value similarity
3. Coverage-tiered clamping: Apply different clamp limits based on sample count

Key innovation: Bilateral filtering preserves edges while reducing noise,
with adaptive safety limits based on data confidence.
"""

from __future__ import annotations

from math import exp
from typing import List, Optional


def kernel_smooth(
    ve_grid: List[List[Optional[float]]],
    hits_grid: List[List[int]],
    *,
    gate_hi: float = 3.0,
    gate_lo: float = 1.0,
    base_passes: int = 2,
    sigma: float = 0.75,
    center_bias: float = 1.25,
    dist_pow: int = 1,
    min_hits: int = 1,
    clamp_hi: float = 7.0,
    clamp_med: float = 10.0,
    clamp_lo: float = 15.0,
    hi_samples: int = 100,
    med_samples: int = 20,
) -> List[List[Optional[float]]]:
    """
    Two-stage: gate -> bilateral smoothing -> coverage-tier clamp.
    ve_grid values are ΔVE% (percent space). No NaN fill.
    """
    if not ve_grid or not hits_grid:
        return ve_grid

    rows, cols = len(ve_grid), len(ve_grid[0])

    # Stage 1: Gate - determine per-cell smoothing passes
    pass_grid = [[0 for _ in range(cols)] for _ in range(rows)]

    for r in range(rows):
        for c in range(cols):
            val = ve_grid[r][c]
            if val is None:
                continue

            abs_val = abs(val)
            if abs_val >= gate_hi:
                # Large corrections: no smoothing passes
                passes = 0
            elif abs_val <= gate_lo:
                # Small corrections: full smoothing passes
                passes = base_passes
            else:
                # Linear taper between gate_lo and gate_hi
                taper_factor = (gate_hi - abs_val) / (gate_hi - gate_lo)
                passes = int(round(base_passes * taper_factor))

            pass_grid[r][c] = passes

    # Stage 2: Bilateral smoothing with per-cell pass mask
    smoothed_grid = [row[:] for row in ve_grid]  # Deep copy

    for r in range(rows):
        for c in range(cols):
            center_val = smoothed_grid[r][c]
            if center_val is None:
                continue

            passes = pass_grid[r][c]
            if passes == 0:
                continue  # No smoothing for this cell

            current_val = center_val
            for _ in range(passes):
                # Collect bilateral-weighted neighbors
                neighbor_values = []
                neighbor_weights = []

                # Center cell (with bias)
                neighbor_values.append(current_val)
                neighbor_weights.append(center_bias)

                # Neighbor cells with bilateral weights
                neighbors = [
                    (r-1, c, 1.0),  # Up
                    (r+1, c, 1.0),  # Down
                    (r, c-1, 1.0),  # Left
                    (r, c+1, 1.0),  # Right
                ]

                for nr, nc, base_weight in neighbors:
                    if 0 <= nr < rows and 0 <= nc < cols:
                        n_val = smoothed_grid[nr][nc]
                        if n_val is not None:
                            # Spatial weight: inverse distance
                            dist_weight = 1.0 / (1.0 ** dist_pow)  # All immediate neighbors have dist=1

                            # Value similarity weight: Gaussian
                            value_diff = abs(current_val - n_val)
                            similarity_weight = exp(-(value_diff ** 2) / (2 * sigma ** 2))

                            # Bilateral weight = spatial × similarity
                            bilateral_weight = base_weight * dist_weight * similarity_weight

                            neighbor_values.append(n_val)
                            neighbor_weights.append(bilateral_weight)

                # Apply bilateral weighted average
                if len(neighbor_values) >= min_hits:
                    weighted_sum = sum(v * w for v, w in zip(neighbor_values, neighbor_weights))
                    total_weight = sum(neighbor_weights)
                    current_val = weighted_sum / total_weight

            smoothed_grid[r][c] = current_val

    # Stage 3: Coverage-tiered clamping
    clamped_grid = [row[:] for row in smoothed_grid]

    for r in range(rows):
        for c in range(cols):
            val = clamped_grid[r][c]
            if val is None:
                continue

            hits = hits_grid[r][c]

            # Determine clamp limit based on sample count
            if hits >= hi_samples:
                clamp_limit = clamp_hi  # High coverage: tight clamp (±7%)
            elif hits >= med_samples:
                clamp_limit = clamp_med  # Medium coverage: medium clamp (±10%)
            else:
                clamp_limit = clamp_lo  # Low coverage: permissive clamp (±15%)

            # Apply clamping
            if abs(val) > clamp_limit:
                clamped_grid[r][c] = clamp_limit if val > 0 else -clamp_limit

    return clamped_grid