# experiments/protos/kernel_adaptive_v1.py
"""
Adaptive smoothing kernel that adjusts pass count based on local variance.

- High variance regions (noisy data) → more smoothing passes
- Low variance regions (stable data) → fewer passes (preserve detail)
- Signature compatible with toolkit.kernel_smooth(grid, passes=2)
- None cells remain None (no interpolation)
- Uses local MAD (median absolute deviation) to assess stability

This is a drop-in experimental kernel. Use via:

  python experiments/run_experiment.py --idea-id kernel_adaptive_v1 --csv <file> --outdir experiments/outputs/kernel_adaptive_v1

"""

from __future__ import annotations

from typing import List, Optional


def _local_variance_score(
    grid: List[List[Optional[float]]], r: int, c: int, radius: int = 1
) -> float:
    """
    Compute local variance score for a cell based on neighbor differences.

    Higher score = more variation = needs more smoothing.
    Lower score = stable region = preserve detail.

    Args:
        grid: Input grid
        r, c: Cell position
        radius: Neighborhood radius (1 = immediate neighbors)

    Returns:
        Variance score (0.0 = perfectly uniform, higher = more variation)
    """
    rows, cols = len(grid), len(grid[0]) if grid else 0
    center = grid[r][c]
    if center is None:
        return 0.0

    # Collect neighbor values within radius
    neighbors: List[float] = []
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr == 0 and dc == 0:
                continue  # Skip center
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                val = grid[nr][nc]
                if val is not None:
                    neighbors.append(val)

    if not neighbors:
        return 0.0

    # Compute mean absolute deviation from center
    mad = sum(abs(n - center) for n in neighbors) / len(neighbors)
    return mad


def _adaptive_pass_count(variance_score: float, base_passes: int = 2) -> int:
    """
    Determine smoothing passes based on variance score.

    Args:
        variance_score: Local variance metric
        base_passes: Base number of passes (typically 2)

    Returns:
        Adjusted pass count (range: 0 to base_passes+2)
    """
    # Thresholds for variance (tuned for typical VE correction percentages)
    low_variance = 0.05  # Very stable: reduce smoothing
    high_variance = 0.30  # Very noisy: increase smoothing

    if variance_score < low_variance:
        # Stable region: fewer passes to preserve detail
        return max(0, base_passes - 1)
    elif variance_score > high_variance:
        # Noisy region: more passes to reduce noise
        return base_passes + 2
    else:
        # Moderate variance: use base passes
        return base_passes


def kernel_smooth(
    grid: List[List[Optional[float]]], passes: int = 2
) -> List[List[Optional[float]]]:
    """
    Adaptive smoothing with per-cell pass count based on local variance.

    Algorithm:
    1. Compute variance score for each cell
    2. Determine adaptive pass count per cell
    3. Apply variable smoothing: high-variance cells get more passes
    4. Use weighted averaging to blend different smoothing levels

    Args:
        grid: Input grid
        passes: Base number of passes (used as reference, actual varies)

    Returns:
        Smoothed grid with adaptive processing
    """
    if not grid:
        return grid

    rows, cols = len(grid), len(grid[0])

    # Step 1: Compute variance scores for all cells
    variance_map: List[List[float]] = [[0.0] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] is not None:
                variance_map[r][c] = _local_variance_score(grid, r, c)

    # Step 2: Create multiple smoothed versions (0, 1, 2, 3, 4 passes)
    max_passes = passes + 2
    smoothed_versions: List[List[List[Optional[float]]]] = []

    for p in range(max_passes + 1):
        # Apply standard 4-neighbor smoothing for p passes
        cur: List[List[Optional[float]]] = [row[:] for row in grid]
        for _ in range(p):
            nxt: List[List[Optional[float]]] = [[None] * cols for _ in range(rows)]
            for r in range(rows):
                for c in range(cols):
                    center = cur[r][c]
                    if center is None:
                        nxt[r][c] = None
                        continue

                    acc: List[float] = [center]
                    # 4-neighbor averaging
                    if r > 0 and cur[r - 1][c] is not None:
                        acc.append(cur[r - 1][c])  # type: ignore
                    if r < rows - 1 and cur[r + 1][c] is not None:
                        acc.append(cur[r + 1][c])  # type: ignore
                    if c > 0 and cur[r][c - 1] is not None:
                        acc.append(cur[r][c - 1])  # type: ignore
                    if c < cols - 1 and cur[r][c + 1] is not None:
                        acc.append(cur[r][c + 1])  # type: ignore

                    nxt[r][c] = sum(acc) / len(acc)
            cur = nxt
        smoothed_versions.append(cur)

    # Step 3: Select appropriate smoothing level per cell based on variance
    result: List[List[Optional[float]]] = [[None] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] is None:
                result[r][c] = None
                continue

            # Determine optimal pass count for this cell
            variance_score = variance_map[r][c]
            adaptive_passes = _adaptive_pass_count(variance_score, base_passes=passes)
            adaptive_passes = min(
                adaptive_passes, max_passes
            )  # Clamp to available versions

            # Use the corresponding smoothed version
            result[r][c] = smoothed_versions[adaptive_passes][r][c]

    return result
