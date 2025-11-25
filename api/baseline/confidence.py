"""
Multi-factor confidence scoring for One-Pull Baseline.

Confidence is calculated based on:
1. Cell type (measured vs interpolated vs extrapolated)
2. Distance from measured data
3. FDC stability (how linear the response is)
4. Prediction agreement (do multiple methods agree?)
5. Data density (how many measured points nearby)
"""

import numpy as np
from typing import Tuple
import logging

from .models import CellType, CellConfidence, FDCAnalysis

logger = logging.getLogger(__name__)

# Base confidence by cell type
BASE_CONFIDENCE = {
    CellType.MEASURED: 100.0,
    CellType.INTERPOLATED: 80.0,
    CellType.EXTRAPOLATED: 55.0
}

# Scoring weights
DISTANCE_PENALTY_PER_STEP = 5.0
MAX_DISTANCE_PENALTY = 25.0
STABILITY_BONUS_MAX = 15.0
AGREEMENT_BONUS_MAX = 10.0
DENSITY_BONUS_MAX = 10.0


def calculate_fdc_analysis(
    measured_grid: np.ndarray,
    count_grid: np.ndarray,
    map_bins: np.ndarray
) -> FDCAnalysis:
    """
    Analyze Fuel Delivery Characteristic stability.

    Calculates FDC (slope of AFR error vs MAP) in different regions
    and determines if it's stable enough for reliable extrapolation.
    """
    n_map = len(map_bins)
    mid_point = n_map // 2

    # Collect (MAP, avg_error) points
    all_points = []
    low_points = []
    high_points = []

    for map_idx in range(n_map):
        col = measured_grid[:, map_idx]
        valid_count = np.sum(~np.isnan(col))

        if valid_count >= 2:
            avg_error = np.nanmean(col)
            point = (map_bins[map_idx], avg_error)
            all_points.append(point)

            if map_idx < mid_point:
                low_points.append(point)
            else:
                high_points.append(point)

    def calc_slope(points):
        if len(points) < 2:
            return 0.0
        maps, errors = zip(*points)
        if len(set(maps)) < 2:
            return 0.0
        coeffs = np.polyfit(maps, errors, 1)
        return coeffs[0]

    overall_fdc = calc_slope(all_points)
    low_fdc = calc_slope(low_points) if len(low_points) >= 2 else overall_fdc
    high_fdc = calc_slope(high_points) if len(high_points) >= 2 else overall_fdc

    # Calculate stability score
    # FDC is stable if low and high regions have similar slopes
    if overall_fdc == 0:
        stability_score = 0.5  # Can't determine
    else:
        low_ratio = low_fdc / overall_fdc if overall_fdc != 0 else 1.0
        high_ratio = high_fdc / overall_fdc if overall_fdc != 0 else 1.0

        # Perfect stability = 1.0, poor stability = 0.0
        deviation = abs(low_ratio - 1.0) + abs(high_ratio - 1.0)
        stability_score = max(0.0, 1.0 - deviation / 2.0)

    is_stable = stability_score >= 0.5

    instability_warning = None
    if not is_stable:
        instability_warning = (
            f"FDC varies significantly across MAP range "
            f"(low: {low_fdc:.4f}, high: {high_fdc:.4f}). "
            f"WOT extrapolations may be less accurate."
        )

    return FDCAnalysis(
        overall_fdc=float(overall_fdc),
        low_map_fdc=float(low_fdc),
        high_map_fdc=float(high_fdc),
        stability_score=float(stability_score),
        is_stable=is_stable,
        instability_warning=instability_warning
    )


def calculate_cell_confidence(
    cell_type: CellType,
    rpm_idx: int,
    map_idx: int,
    count_grid: np.ndarray,
    fdc_analysis: FDCAnalysis,
    prediction_values: list = None  # Multiple prediction methods' values
) -> CellConfidence:
    """
    Calculate detailed confidence score for a single cell.

    Args:
        cell_type: How this cell was determined
        rpm_idx: Row index in grid
        map_idx: Column index in grid
        count_grid: Grid of measured point counts
        fdc_analysis: FDC stability analysis
        prediction_values: List of values from different prediction methods

    Returns:
        CellConfidence with detailed breakdown
    """
    n_rpm, n_map = count_grid.shape

    # 1. Base score from cell type
    base_score = BASE_CONFIDENCE[cell_type]

    # 2. Distance penalty - how far from measured data?
    if cell_type == CellType.MEASURED:
        distance_penalty = 0.0
    else:
        # Find nearest measured cell (Manhattan distance)
        min_distance = float('inf')
        for dr in range(-3, 4):
            for dm in range(-3, 4):
                nr, nm = rpm_idx + dr, map_idx + dm
                if 0 <= nr < n_rpm and 0 <= nm < n_map:
                    if count_grid[nr, nm] > 0:
                        dist = abs(dr) + abs(dm)
                        min_distance = min(min_distance, dist)

        if min_distance == float('inf'):
            min_distance = 6  # Max penalty

        distance_penalty = min(
            min_distance * DISTANCE_PENALTY_PER_STEP,
            MAX_DISTANCE_PENALTY
        )

    # 3. Stability bonus - reward stable FDC
    stability_bonus = fdc_analysis.stability_score * STABILITY_BONUS_MAX

    # 4. Agreement bonus - do multiple prediction methods agree?
    agreement_bonus = 0.0
    if prediction_values and len(prediction_values) >= 2:
        # Low standard deviation = high agreement
        std_dev = np.std(prediction_values)
        if std_dev < 0.5:
            agreement_bonus = AGREEMENT_BONUS_MAX
        elif std_dev < 1.0:
            agreement_bonus = AGREEMENT_BONUS_MAX * 0.6
        elif std_dev < 2.0:
            agreement_bonus = AGREEMENT_BONUS_MAX * 0.3

    # 5. Density bonus - many measured points nearby?
    nearby_count = 0
    for dr in range(-2, 3):
        for dm in range(-2, 3):
            nr, nm = rpm_idx + dr, map_idx + dm
            if 0 <= nr < n_rpm and 0 <= nm < n_map:
                nearby_count += count_grid[nr, nm]

    if nearby_count >= 20:
        density_bonus = DENSITY_BONUS_MAX
    elif nearby_count >= 10:
        density_bonus = DENSITY_BONUS_MAX * 0.6
    elif nearby_count >= 5:
        density_bonus = DENSITY_BONUS_MAX * 0.3
    else:
        density_bonus = 0.0

    # Calculate total (only apply bonuses to non-measured cells)
    if cell_type == CellType.MEASURED:
        total = 100.0
    else:
        total = (
            base_score
            - distance_penalty
            + stability_bonus
            + agreement_bonus
            + density_bonus
        )
        total = np.clip(total, 10.0, 99.0)  # Never 100% for predictions

    return CellConfidence(
        total=float(total),
        base_score=float(base_score),
        distance_penalty=float(distance_penalty),
        stability_bonus=float(stability_bonus),
        agreement_bonus=float(agreement_bonus),
        density_bonus=float(density_bonus)
    )
