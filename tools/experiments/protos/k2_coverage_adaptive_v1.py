"""
K2: Coverage-Adaptive Clamp Kernel

This kernel adjusts clamping limits based on cell coverage density.
Cells with low coverage (sparse data) get more permissive clamps to allow
exploration of correction ranges, while high-coverage cells get tighter
clamps for safety and stability.

Algorithm:
1. Use correction magnitude as coverage proxy (larger corrections = higher confidence)
2. Apply coverage-adaptive clamping (low confidence = permissive, high confidence = tight)
3. Use standard adaptive smoothing
4. Apply coverage-weighted smoothing as fallback

Key innovation: Confidence-aware safety limits that balance exploration vs safety.
"""

def kernel_smooth(grid, passes=2, low_confidence_threshold=1.0, high_confidence_threshold=3.0):
    """
    Coverage-adaptive clamp kernel smoothing for VE corrections.

    Uses correction magnitude as a proxy for confidence/coverage:
    - Small corrections (< 1.0%): Low confidence, permissive clamps (±15%)
    - Large corrections (> 3.0%): High confidence, tight clamps (±7%)
    - Medium corrections: Linear interpolation

    Args:
        grid: Input correction grid (9x5)
        passes: Number of smoothing passes (default: 2)
        low_confidence_threshold: Magnitude below which cells get permissive clamps (default: 1.0)
        high_confidence_threshold: Magnitude above which cells get tight clamps (default: 3.0)

    Returns:
        Smoothed grid with coverage-adaptive clamping
    """
    if not grid:
        return grid

    rows, cols = len(grid), len(grid[0])

    # Stage 1: Adaptive smoothing passes with confidence-adaptive clamping
    adaptive_grid = [row[:] for row in grid]  # Deep copy

    for r in range(rows):
        for c in range(cols):
            center_val = adaptive_grid[r][c]
            if center_val is None:
                continue

            # Determine confidence-based clamp limit using correction magnitude as proxy
            abs_correction = abs(center_val)

            if abs_correction <= low_confidence_threshold:
                # Low confidence: permissive clamp (±15%) for exploration
                max_adjust_pct = 15.0
            elif abs_correction >= high_confidence_threshold:
                # High confidence: tight clamp (±7%) for safety
                max_adjust_pct = 7.0
            else:
                # Linear interpolation between thresholds
                # At low_threshold: 15%, at high_threshold: 7%
                factor = (abs_correction - low_confidence_threshold) / (high_confidence_threshold - low_confidence_threshold)
                max_adjust_pct = 15.0 - (factor * (15.0 - 7.0))

            # Apply confidence-adaptive clamping to this cell
            if abs(center_val) > max_adjust_pct:
                center_val = max_adjust_pct if center_val > 0 else -max_adjust_pct
                adaptive_grid[r][c] = center_val

            # Determine adaptive passes based on correction magnitude
            if abs_correction >= 3.0:
                # Large corrections: no smoothing passes
                adaptive_passes = 0
            elif abs_correction <= 1.0:
                # Small corrections: full smoothing passes
                adaptive_passes = passes
            else:
                # Linear taper between 1.0% and 3.0%
                taper_factor = (3.0 - abs_correction) / (3.0 - 1.0)  # 1.0 at 1%, 0.0 at 3%
                adaptive_passes = int(round(passes * taper_factor))

            # Apply adaptive smoothing passes to this cell
            if adaptive_passes > 0:
                smoothed_val = center_val
                for _ in range(adaptive_passes):
                    neighbors = [smoothed_val]  # Include center

                    # Add valid neighbors
                    if r > 0 and adaptive_grid[r-1][c] is not None:
                        neighbors.append(adaptive_grid[r-1][c])  # Up
                    if r < rows-1 and adaptive_grid[r+1][c] is not None:
                        neighbors.append(adaptive_grid[r+1][c])  # Down
                    if c > 0 and adaptive_grid[r][c-1] is not None:
                        neighbors.append(adaptive_grid[r][c-1])  # Left
                    if c < cols-1 and adaptive_grid[r][c+1] is not None:
                        neighbors.append(adaptive_grid[r][c+1])  # Right

                    smoothed_val = sum(neighbors) / len(neighbors)

                adaptive_grid[r][c] = smoothed_val

    # Stage 2: Coverage-weighted smoothing (same as original)
    final_grid = [row[:] for row in adaptive_grid]

    # Parameters for coverage-weighted smoothing
    alpha = 0.20
    center_bias = 1.25
    min_hits = 1
    dist_pow = 1

    # For each cell, compute coverage-weighted average
    for r in range(rows):
        for c in range(cols):
            center_val = final_grid[r][c]
            if center_val is None:
                continue

            # Collect neighbor values and weights
            neighbor_values = []
            neighbor_weights = []

            # Center cell (with bias)
            neighbor_values.append(center_val)
            neighbor_weights.append(center_bias)

            # Neighbor cells with distance-based weights
            neighbors = [
                (r-1, c, 1.0),  # Up
                (r+1, c, 1.0),  # Down
                (r, c-1, 1.0),  # Left
                (r, c+1, 1.0),  # Right
            ]

            for nr, nc, base_weight in neighbors:
                if 0 <= nr < rows and 0 <= nc < cols:
                    n_val = final_grid[nr][nc]
                    if n_val is not None:
                        # Distance weighting (all immediate neighbors have dist=1)
                        dist_weight = 1.0 / (1.0 ** dist_pow)
                        neighbor_values.append(n_val)
                        neighbor_weights.append(base_weight * dist_weight)

            # Apply coverage weighting if we have enough neighbors
            if len(neighbor_values) >= min_hits:
                # Weighted average with alpha blending
                weighted_sum = sum(v * w for v, w in zip(neighbor_values, neighbor_weights))
                total_weight = sum(neighbor_weights)
                smoothed_val = weighted_sum / total_weight

                # Blend with original value using alpha
                final_grid[r][c] = alpha * smoothed_val + (1 - alpha) * center_val
            # If insufficient neighbors, keep original value

    return final_grid


def k2_apply_clamp(afr_err_grid, coverage_grid, soft_band, hard_band, max_band):
    """
    Apply coverage-adaptive clamping to an AFR error grid.

    Higher coverage → tighter clamp. Lower coverage → more permissive clamp.

    Args:
        afr_err_grid: 2D list of floats (correction percentages).
        coverage_grid: 2D list of floats in [0,1] matching afr_err_grid shape.
        soft_band: Tight clamp limit (e.g., 5.0).
        hard_band: Medium clamp limit (e.g., 15.0).
        max_band: Most permissive clamp limit (e.g., 25.0).

    Returns:
        2D list of floats with per-cell clamped values.
    """
    if not afr_err_grid:
        return afr_err_grid

    rows = len(afr_err_grid)
    cols = len(afr_err_grid[0])

    # Basic shape validation (fail fast to avoid subtle bugs)
    if len(coverage_grid) != rows or any(len(row) != cols for row in coverage_grid):
        raise ValueError("coverage_grid must be provided and match afr_err_grid shape")

    def clamp_value(value, limit):
        if value is None:
            return None  # Preserve structure if None appears
        abs_val = abs(float(value))
        lim = float(limit)
        if abs_val <= lim:
            return float(value)
        return lim if value > 0 else -lim

    # Thresholds for coverage buckets (can be tuned)
    high_cov_threshold = 0.75
    mid_cov_threshold = 0.40

    result = [[None for _ in range(cols)] for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            val = afr_err_grid[r][c]
            cov = coverage_grid[r][c]

            # Sanitize coverage
            try:
                cov_f = float(cov)
            except Exception:
                cov_f = 0.0
            if cov_f < 0.0 or cov_f != cov_f:  # NaN check via self-inequality
                cov_f = 0.0
            if cov_f > 1.0:
                cov_f = 1.0

            # Select clamp band by coverage bucket
            if cov_f >= high_cov_threshold:
                band = float(soft_band)
            elif cov_f >= mid_cov_threshold:
                band = float(hard_band)
            else:
                band = float(max_band)

            result[r][c] = clamp_value(val, band)

    return result