"""
K1: Gradient-Limit Smoothing Kernel

This kernel applies smoothing but limits it in areas with high gradients
(sudden changes) to preserve important features while reducing noise.

Algorithm:
1. Calculate gradient magnitude for each cell (max neighbor difference)
2. Apply normal adaptive smoothing
3. For cells with high gradients, blend back toward original value
4. Apply coverage-weighted smoothing as fallback

Key innovation: Gradient-aware smoothing that preserves edges/features
while still reducing noise in smooth areas.
"""


def kernel_smooth(grid, passes=2, gradient_threshold=1.0):
    """
    Gradient-limited kernel smoothing for VE corrections.

    Args:
        grid: Input correction grid (9x5)
        passes: Number of smoothing passes (default: 2)
        gradient_threshold: Gradient threshold above which smoothing is limited (default: 2.0%)

    Returns:
        Smoothed grid with gradient-limited adjustments
    """
    if not grid:
        return grid

    rows, cols = len(grid), len(grid[0])

    # Stage 1: Calculate gradient magnitudes
    gradients = [[0.0 for _ in range(cols)] for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            center_val = grid[r][c]
            if center_val is None:
                continue

            max_diff = 0.0
            # Check all 4 neighbors
            neighbors = []
            if r > 0 and grid[r - 1][c] is not None:
                neighbors.append(grid[r - 1][c])
            if r < rows - 1 and grid[r + 1][c] is not None:
                neighbors.append(grid[r + 1][c])
            if c > 0 and grid[r][c - 1] is not None:
                neighbors.append(grid[r][c - 1])
            if c < cols - 1 and grid[r][c + 1] is not None:
                neighbors.append(grid[r][c + 1])

            for neighbor_val in neighbors:
                diff = abs(center_val - neighbor_val)
                max_diff = max(max_diff, diff)

            gradients[r][c] = max_diff

    # Stage 2: Adaptive smoothing passes (same as original)
    adaptive_grid = [row[:] for row in grid]  # Deep copy

    for r in range(rows):
        for c in range(cols):
            center_val = adaptive_grid[r][c]
            if center_val is None:
                continue

            # Determine adaptive passes based on correction magnitude
            abs_correction = abs(center_val)
            if abs_correction >= 3.0:
                # Large corrections: no smoothing passes
                adaptive_passes = 0
            elif abs_correction <= 1.0:
                # Small corrections: full smoothing passes
                adaptive_passes = passes
            else:
                # Linear taper between 1.0% and 3.0%
                taper_factor = (3.0 - abs_correction) / (
                    3.0 - 1.0
                )  # 1.0 at 1%, 0.0 at 3%
                adaptive_passes = int(round(passes * taper_factor))

            # Apply adaptive smoothing passes to this cell
            if adaptive_passes > 0:
                smoothed_val = center_val
                for _ in range(adaptive_passes):
                    neighbors = [smoothed_val]  # Include center

                    # Add valid neighbors
                    if r > 0 and adaptive_grid[r - 1][c] is not None:
                        neighbors.append(adaptive_grid[r - 1][c])  # Up
                    if r < rows - 1 and adaptive_grid[r + 1][c] is not None:
                        neighbors.append(adaptive_grid[r + 1][c])  # Down
                    if c > 0 and adaptive_grid[r][c - 1] is not None:
                        neighbors.append(adaptive_grid[r][c - 1])  # Left
                    if c < cols - 1 and adaptive_grid[r][c + 1] is not None:
                        neighbors.append(adaptive_grid[r][c + 1])  # Right

                    smoothed_val = sum(neighbors) / len(neighbors)

                adaptive_grid[r][c] = smoothed_val

    # Stage 3: Gradient-limited blending
    gradient_limited_grid = [row[:] for row in adaptive_grid]

    for r in range(rows):
        for c in range(cols):
            original_val = grid[r][c]
            smoothed_val = adaptive_grid[r][c]

            if original_val is None or smoothed_val is None:
                continue

            gradient_magnitude = gradients[r][c]

            # If gradient is above threshold, blend back toward original
            if gradient_magnitude > gradient_threshold:
                # Blend factor: higher gradient = more weight to original
                blend_factor = min(1.0, gradient_magnitude / (gradient_threshold * 2))
                # blend_factor = 0.5 when gradient = threshold
                # blend_factor = 1.0 when gradient = threshold * 2

                gradient_limited_grid[r][c] = (
                    1 - blend_factor
                ) * smoothed_val + blend_factor * original_val

    # Stage 4: Coverage-weighted smoothing (same as original)
    final_grid = [row[:] for row in gradient_limited_grid]

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
                (r - 1, c, 1.0),  # Up
                (r + 1, c, 1.0),  # Down
                (r, c - 1, 1.0),  # Left
                (r, c + 1, 1.0),  # Right
            ]

            for nr, nc, base_weight in neighbors:
                if 0 <= nr < rows and 0 <= nc < cols:
                    n_val = final_grid[nr][nc]
                    if n_val is not None:
                        # Distance weighting (all immediate neighbors have dist=1)
                        dist_weight = 1.0 / (1.0**dist_pow)
                        neighbor_values.append(n_val)
                        neighbor_weights.append(base_weight * dist_weight)

            # Apply coverage weighting if we have enough neighbors
            if len(neighbor_values) >= min_hits:
                # Weighted average with alpha blending
                weighted_sum = sum(
                    v * w for v, w in zip(neighbor_values, neighbor_weights)
                )
                total_weight = sum(neighbor_weights)
                smoothed_val = weighted_sum / total_weight

                # Blend with original value using alpha
                final_grid[r][c] = alpha * smoothed_val + (1 - alpha) * center_val
            # If insufficient neighbors, keep original value

    return final_grid
