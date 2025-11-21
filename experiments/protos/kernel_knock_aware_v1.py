"""
Correction-magnitude-aware smoothing kernel for DynoAI experiments.

This kernel reduces smoothing in regions with large VE correction magnitudes,
treating them as "risky" areas that need less smoothing. Large corrections
indicate areas where the AFR error is significant, so we preserve these
important tuning signals rather than smoothing them away.
"""

from typing import List, Optional, Sequence

# Correction magnitude thresholds for adaptive behavior
LOW_CORRECTION_THRESHOLD = 1.0  # percentage - below this, normal smoothing
HIGH_CORRECTION_THRESHOLD = 3.0  # percentage - above this, minimal smoothing

# Smoothing pass adjustments based on correction magnitude
NORMAL_PASSES = 2  # default smoothing passes
LOW_CORRECTION_PASSES = 2  # normal smoothing for small corrections
HIGH_CORRECTION_PASSES = 0  # minimal smoothing for large corrections


def _local_correction_magnitude(
    correction_grid: Sequence[Sequence[Optional[float]]],
    ri: int,
    ki: int,
    radius: int = 1,
) -> float:
    """
    Compute local correction magnitude around a cell.

    Args:
        correction_grid: Grid of VE correction values (percentages)
        ri, ki: Row/column indices of center cell
        radius: Neighborhood radius to consider

    Returns:
        Average absolute correction magnitude in neighborhood (0.0 if no data)
    """
    neighbors: List[float] = []
    rows = len(correction_grid)
    cols = len(correction_grid[0]) if rows else 0

    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            nr, nc = ri + dr, ki + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                corr_val = correction_grid[nr][nc]
                if corr_val is not None:
                    neighbors.append(abs(corr_val))

    return sum(neighbors) / len(neighbors) if neighbors else 0.0


def _adaptive_passes_from_correction(correction_magnitude: float) -> int:
    """
    Determine smoothing passes based on local correction magnitude.

    Args:
        correction_magnitude: Average absolute correction in neighborhood

    Returns:
        Number of smoothing passes to apply
    """
    if correction_magnitude >= HIGH_CORRECTION_THRESHOLD:
        return HIGH_CORRECTION_PASSES  # minimal smoothing
    elif correction_magnitude <= LOW_CORRECTION_THRESHOLD:
        return LOW_CORRECTION_PASSES  # normal smoothing
    else:
        # Linear interpolation between thresholds
        ratio = (correction_magnitude - LOW_CORRECTION_THRESHOLD) / (
            HIGH_CORRECTION_THRESHOLD - LOW_CORRECTION_THRESHOLD
        )
        passes_range = HIGH_CORRECTION_PASSES - LOW_CORRECTION_PASSES
        return int(LOW_CORRECTION_PASSES + ratio * passes_range)


def kernel_smooth(
    grid: List[List[Optional[float]]], passes: int = 2
) -> List[List[Optional[float]]]:
    """
    Apply correction-magnitude-aware smoothing to VE correction grid.

    In regions with large VE corrections, reduces smoothing to preserve
    important tuning signals. In regions with small corrections, applies
    normal smoothing for noise reduction.

    Args:
        grid: Input VE correction grid (9×5)
        passes: Ignored - uses adaptive passes based on correction magnitude

    Returns:
        Smoothed grid with same dimensions
    """
    # FINGERPRINT: Prove kernel is running
    print("KERNEL_KNOCK_AWARE_V1: kernel_smooth called!")

    # DEBUG: Check correction magnitudes
    magnitudes: List[float] = []
    for ri in range(len(grid)):
        for ki in range(len(grid[0])):
            if grid[ri][ki] is not None:
                magnitudes.append(abs(grid[ri][ki]))  # type: ignore
    if magnitudes:
        print(
            f"KERNEL_KNOCK_AWARE_V1: Center cell correction magnitudes range: {min(magnitudes):.3f} to {max(magnitudes):.3f}"
        )
        print(
            f"KERNEL_KNOCK_AWARE_V1: Thresholds: LOW={LOW_CORRECTION_THRESHOLD}, HIGH={HIGH_CORRECTION_THRESHOLD}"
        )

    # Pre-compute smoothed versions for different pass counts
    smoothed_versions = {}
    for p in range(5):  # 0 to 4 passes
        smoothed_versions[p] = _standard_kernel_smooth(grid, p)

    # Build correction-aware result
    result: List[List[Optional[float]]] = [
        [None for _ in range(len(grid[0]))] for _ in range(len(grid))
    ]

    for ri in range(len(grid)):
        for ki in range(len(grid[0])):
            if grid[ri][ki] is None:
                continue  # Skip sparse cells

            # Determine appropriate smoothing level based on center cell correction magnitude
            center_correction = abs(grid[ri][ki])  # type: ignore # Already checked grid[ri][ki] is not None above
            adaptive_passes = _adaptive_passes_from_correction(center_correction)

            # Use pre-computed smoothed version
            result[ri][ki] = smoothed_versions[adaptive_passes][ri][ki]

    return result


def _standard_kernel_smooth(
    grid: List[List[Optional[float]]], passes: int
) -> List[List[Optional[float]]]:
    """
    Standard 4-neighbor kernel smoothing (same as original toolkit).

    Args:
        grid: Input grid
        passes: Number of smoothing iterations

    Returns:
        Smoothed grid
    """
    result = [row[:] for row in grid]  # Deep copy

    for _ in range(passes):
        temp: List[List[Optional[float]]] = [
            [None for _ in range(len(grid[0]))] for _ in range(len(grid))
        ]

        for ri in range(len(grid)):
            for ki in range(len(grid[0])):
                center = result[ri][ki]
                if center is None:
                    continue

                # Collect valid neighbors (4-connected)
                neighbors: List[float] = [center]  # Include center

                # Up
                if ri > 0:
                    up_val = result[ri - 1][ki]
                    if up_val is not None:
                        neighbors.append(up_val)

                # Down
                if ri < len(grid) - 1:
                    down_val = result[ri + 1][ki]
                    if down_val is not None:
                        neighbors.append(down_val)

                # Left
                if ki > 0:
                    left_val = result[ri][ki - 1]
                    if left_val is not None:
                        neighbors.append(left_val)

                # Right
                if ki < len(grid[0]) - 1:
                    right_val = result[ri][ki + 1]
                    if right_val is not None:
                        neighbors.append(right_val)

                # Average all valid neighbors
                temp[ri][ki] = sum(neighbors) / len(neighbors)

        result = temp

    return result
