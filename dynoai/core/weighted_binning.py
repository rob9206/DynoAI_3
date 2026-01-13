"""
DynoAI Weighted Binning Module - TuneLab-Inspired Cell Accumulation

This module provides distance-weighted cell accumulation for 2D table generation,
inspired by Dynojet Power Core's TuneLab `generate_sample_table()` algorithm.

The key insight is that samples closer to a cell's center should contribute
more to that cell's value than samples near the edges. TuneLab uses logarithmic
weighting based on distance from cell center.

Weighting Algorithm (TuneLab):
    1. For each sample, find the nearest cell in the 2D grid
    2. Calculate distance from sample to cell center as percentage
    3. Apply logarithmic weight: weight = -log10(distance²) / (distance + 1)⁴
    4. Accumulate weighted values: sum += value × weight
    5. Final value = sum / total_weight

This produces more accurate tables from sparse data compared to simple averaging.

Usage:
    from dynoai.core.weighted_binning import WeightedBinAccumulator

    # Create accumulator with axis definitions
    accumulator = WeightedBinAccumulator(
        x_axis=[1000, 1500, 2000, 2500, 3000],  # RPM
        y_axis=[20, 40, 60, 80, 100],           # MAP kPa
    )

    # Add samples
    for rpm, map_kpa, afr in samples:
        accumulator.add_sample(rpm, map_kpa, afr)

    # Get weighted table
    table = accumulator.get_table()
    hit_counts = accumulator.get_hit_counts()

References:
    - Dynojet Power Core tunelab.py::generate_sample_table()
    - docs/TUNELAB_INTEGRATION.md
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

__all__ = [
    "WeightedBinAccumulator",
    "BinPlacement",
    "WeightingStrategy",
    "create_rpm_axis",
    "create_map_axis",
]

logger = logging.getLogger(__name__)

# =============================================================================
# Weighting Strategies
# =============================================================================


class WeightingStrategy:
    """Base class for cell weighting strategies."""

    def calculate_weight(self, distance: float) -> float:
        """
        Calculate weight for a sample based on distance from cell center.

        Args:
            distance: Normalized distance from cell center (0.0 = center, 1.0 = edge)

        Returns:
            Weight value (higher = more influence)
        """
        raise NotImplementedError


class UniformWeighting(WeightingStrategy):
    """
    Uniform weighting - all samples in a cell count equally.

    This is what DynoAI traditionally uses.
    """

    def calculate_weight(self, distance: float) -> float:
        return 1.0


class LinearWeighting(WeightingStrategy):
    """
    Linear weighting - samples closer to center count more.

    Weight decreases linearly from 1.0 at center to 0.0 at edge.
    """

    def calculate_weight(self, distance: float) -> float:
        return max(0.0, 1.0 - distance)


class LogarithmicWeighting(WeightingStrategy):
    """
    Logarithmic weighting - TuneLab's default algorithm.

    This strongly favors samples near cell centers, providing better
    accuracy with sparse data.

    Formula: weight = -log10(distance²) / (distance + 1)⁴

    The function has these properties:
    - At distance=0: weight approaches infinity (clamped to max)
    - At distance=0.5: weight ≈ 0.6
    - At distance=1.0: weight ≈ 0.0
    """

    MIN_DISTANCE = 1e-10  # Prevent log(0)
    MAX_WEIGHT = 100.0  # Clamp very high weights

    def calculate_weight(self, distance: float) -> float:
        # Clamp minimum distance to prevent numerical issues
        distance = max(self.MIN_DISTANCE, abs(distance))

        # TuneLab formula: -log10(distance²) / (distance + 1)⁴
        weight = -math.log10(distance**2) / ((distance + 1.0) ** 4)

        # Clamp to reasonable range
        return min(self.MAX_WEIGHT, max(0.0, weight))


class GaussianWeighting(WeightingStrategy):
    """
    Gaussian weighting - smooth falloff from center.

    Args:
        sigma: Standard deviation (default: 0.5)
            Lower sigma = sharper peak at center
            Higher sigma = broader influence
    """

    def __init__(self, sigma: float = 0.5):
        self.sigma = sigma

    def calculate_weight(self, distance: float) -> float:
        # Gaussian: exp(-distance² / (2σ²))
        return math.exp(-(distance**2) / (2 * self.sigma**2))


# =============================================================================
# Bin Placement
# =============================================================================


@dataclass
class BinPlacement:
    """
    Result of placing a value on an axis.

    Attributes:
        index: Index of the nearest bin
        percent_to_next: Percentage distance toward the next bin
            - 0.0 = exactly at bin center
            - 0.5 = halfway to next bin
            - negative = toward previous bin
    """

    index: int
    percent_to_next: float

    @property
    def is_near_center(self) -> bool:
        """True if value is within 25% of cell center."""
        return abs(self.percent_to_next) < 0.25


def find_axis_placement(axis: Sequence[float], value: float) -> BinPlacement:
    """
    Find where a value falls on an axis.

    This is equivalent to TuneLab's axis_place_value() function.

    Args:
        axis: Sorted axis values (ascending or descending)
        value: Value to place

    Returns:
        BinPlacement with index and percentage to next bin

    Example:
        >>> axis = [1000, 1500, 2000, 2500]
        >>> placement = find_axis_placement(axis, 1750)
        >>> placement.index  # 1 (nearest to 1500)
        >>> placement.percent_to_next  # 0.5 (halfway to 2000)
    """
    if len(axis) == 0:
        return BinPlacement(index=-1, percent_to_next=float("nan"))

    if len(axis) == 1:
        return BinPlacement(index=0, percent_to_next=0.0)

    # Determine axis direction
    is_ascending = axis[0] < axis[-1]

    # Bound value to axis range
    if is_ascending:
        value = max(axis[0], min(axis[-1], value))
    else:
        value = min(axis[0], max(axis[-1], value))

    # Find placement
    index = -1
    percent_next = float("nan")

    if is_ascending:
        for idx in range(1, len(axis)):
            if value == axis[idx - 1]:
                return BinPlacement(index=idx - 1, percent_to_next=0.0)
            elif value < axis[idx]:
                index = idx - 1
                span = axis[idx] - axis[idx - 1]
                if span != 0:
                    percent_next = (value - axis[idx - 1]) / span
                else:
                    percent_next = 0.0
                break
            elif value == axis[idx]:
                return BinPlacement(index=idx, percent_to_next=0.0)
        else:
            # Value at or beyond last bin
            index = len(axis) - 1
            percent_next = 0.0
    else:
        # Descending axis
        for idx in range(len(axis) - 1):
            if value == axis[idx]:
                return BinPlacement(index=idx, percent_to_next=0.0)
            elif value <= axis[idx] and value > axis[idx + 1]:
                index = idx
                span = axis[idx + 1] - axis[idx]
                if span != 0:
                    percent_next = (value - axis[idx]) / span
                else:
                    percent_next = 0.0
                break
        else:
            # Value at or beyond last bin
            index = len(axis) - 1
            percent_next = 0.0

    return BinPlacement(index=index, percent_to_next=percent_next)


# =============================================================================
# Weighted Bin Accumulator
# =============================================================================


@dataclass
class CellAccumulator:
    """Accumulator for a single cell."""

    weighted_sum: float = 0.0
    weight_sum: float = 0.0
    hit_count: int = 0
    min_value: float = float("inf")
    max_value: float = float("-inf")

    def add(self, value: float, weight: float) -> None:
        """Add a weighted sample."""
        self.weighted_sum += value * weight
        self.weight_sum += weight
        self.hit_count += 1
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)

    @property
    def mean(self) -> Optional[float]:
        """Get weighted mean, or None if no samples."""
        if self.weight_sum == 0 or self.hit_count == 0:
            return None
        return self.weighted_sum / self.weight_sum

    @property
    def simple_mean(self) -> Optional[float]:
        """Get unweighted mean (for comparison)."""
        if self.hit_count == 0:
            return None
        # Would need to track unweighted sum for this
        # For now, return weighted mean
        return self.mean


class WeightedBinAccumulator:
    """
    2D weighted bin accumulator for table generation.

    This implements TuneLab's generate_sample_table() algorithm with
    configurable weighting strategies.

    Args:
        x_axis: X-axis bin values (e.g., RPM)
        y_axis: Y-axis bin values (e.g., MAP kPa)
        weighting: Weighting strategy (default: LogarithmicWeighting)
        min_hits: Minimum hits for a cell to be valid (default: 1)
        snap_threshold: Percentage threshold for snapping to nearest bin
            If sample is >snap_threshold from center, snap to closer bin
            TuneLab uses 0.5 (50%)

    Example:
        >>> acc = WeightedBinAccumulator(
        ...     x_axis=[1000, 2000, 3000, 4000, 5000],
        ...     y_axis=[20, 40, 60, 80, 100],
        ...     weighting=LogarithmicWeighting(),
        ... )
        >>>
        >>> # Add samples from dyno log
        >>> for row in dyno_data:
        ...     acc.add_sample(row['rpm'], row['map'], row['afr'])
        >>>
        >>> # Get result table
        >>> afr_table = acc.get_table()
    """

    def __init__(
        self,
        x_axis: Sequence[float],
        y_axis: Sequence[float],
        weighting: Optional[WeightingStrategy] = None,
        min_hits: int = 1,
        snap_threshold: float = 0.5,
    ):
        self.x_axis = list(x_axis)
        self.y_axis = list(y_axis)
        self.weighting = weighting or LogarithmicWeighting()
        self.min_hits = min_hits
        self.snap_threshold = snap_threshold

        # Initialize cell accumulators
        self._cells: List[List[CellAccumulator]] = [
            [CellAccumulator() for _ in range(len(y_axis))] for _ in range(len(x_axis))
        ]

        self._total_samples = 0
        self._accepted_samples = 0

    @property
    def shape(self) -> Tuple[int, int]:
        """Grid shape (x_size, y_size)."""
        return (len(self.x_axis), len(self.y_axis))

    def reset(self) -> None:
        """Clear all accumulated data."""
        self._cells = [
            [CellAccumulator() for _ in range(len(self.y_axis))]
            for _ in range(len(self.x_axis))
        ]
        self._total_samples = 0
        self._accepted_samples = 0

    def add_sample(
        self,
        x_value: float,
        y_value: float,
        z_value: float,
    ) -> bool:
        """
        Add a sample to the accumulator.

        Args:
            x_value: X-axis value (e.g., RPM)
            y_value: Y-axis value (e.g., MAP kPa)
            z_value: Value to accumulate (e.g., AFR)

        Returns:
            True if sample was accepted, False if rejected
        """
        self._total_samples += 1

        # Validate input
        if math.isnan(x_value) or math.isnan(y_value) or math.isnan(z_value):
            return False
        if math.isinf(x_value) or math.isinf(y_value) or math.isinf(z_value):
            return False

        # Find cell placement
        x_place = find_axis_placement(self.x_axis, x_value)
        y_place = find_axis_placement(self.y_axis, y_value)

        if x_place.index < 0 or y_place.index < 0:
            return False

        # Apply snap threshold (TuneLab behavior)
        x_idx = x_place.index
        y_idx = y_place.index
        percent_x = x_place.percent_to_next
        percent_y = y_place.percent_to_next

        if percent_x >= self.snap_threshold and x_idx < len(self.x_axis) - 1:
            x_idx += 1
            percent_x -= 1.0

        if percent_y >= self.snap_threshold and y_idx < len(self.y_axis) - 1:
            y_idx += 1
            percent_y -= 1.0

        # Calculate distance from cell center
        # Combined Euclidean distance of X and Y percentages
        distance = math.sqrt(percent_x**2 + percent_y**2)

        # Calculate weight
        weight = self.weighting.calculate_weight(distance)

        # Accumulate
        self._cells[x_idx][y_idx].add(z_value, weight)
        self._accepted_samples += 1

        return True

    def add_samples_batch(
        self,
        x_values: Sequence[float],
        y_values: Sequence[float],
        z_values: Sequence[float],
    ) -> int:
        """
        Add multiple samples at once.

        Args:
            x_values: X-axis values
            y_values: Y-axis values
            z_values: Z values to accumulate

        Returns:
            Number of samples accepted
        """
        if not (len(x_values) == len(y_values) == len(z_values)):
            raise ValueError("All input arrays must have same length")

        accepted = 0
        for x, y, z in zip(x_values, y_values, z_values):
            if self.add_sample(x, y, z):
                accepted += 1

        return accepted

    def get_table(self) -> List[List[Optional[float]]]:
        """
        Get the accumulated table as weighted means.

        Cells with fewer than min_hits are returned as None.

        Returns:
            2D list of values (or None for insufficient data)
        """
        result: List[List[Optional[float]]] = []

        for x_idx in range(len(self.x_axis)):
            row: List[Optional[float]] = []
            for y_idx in range(len(self.y_axis)):
                cell = self._cells[x_idx][y_idx]
                if cell.hit_count >= self.min_hits:
                    row.append(cell.mean)
                else:
                    row.append(None)
            result.append(row)

        return result

    def get_hit_counts(self) -> List[List[int]]:
        """
        Get hit counts for each cell.

        Returns:
            2D list of hit counts
        """
        return [
            [self._cells[x][y].hit_count for y in range(len(self.y_axis))]
            for x in range(len(self.x_axis))
        ]

    def get_cell_stats(
        self,
        x_idx: int,
        y_idx: int,
    ) -> Optional[dict]:
        """
        Get detailed statistics for a single cell.

        Returns:
            Dict with mean, hit_count, min, max, weight_sum
        """
        if x_idx < 0 or x_idx >= len(self.x_axis):
            return None
        if y_idx < 0 or y_idx >= len(self.y_axis):
            return None

        cell = self._cells[x_idx][y_idx]

        return {
            "mean": cell.mean,
            "hit_count": cell.hit_count,
            "min_value": cell.min_value if cell.hit_count > 0 else None,
            "max_value": cell.max_value if cell.hit_count > 0 else None,
            "weight_sum": cell.weight_sum,
            "x_bin": self.x_axis[x_idx],
            "y_bin": self.y_axis[y_idx],
        }

    @property
    def statistics(self) -> dict:
        """Get overall accumulator statistics."""
        total_hits = sum(
            self._cells[x][y].hit_count
            for x in range(len(self.x_axis))
            for y in range(len(self.y_axis))
        )

        cells_with_data = sum(
            1
            for x in range(len(self.x_axis))
            for y in range(len(self.y_axis))
            if self._cells[x][y].hit_count >= self.min_hits
        )

        total_cells = len(self.x_axis) * len(self.y_axis)

        return {
            "total_samples": self._total_samples,
            "accepted_samples": self._accepted_samples,
            "rejection_rate": (
                (self._total_samples - self._accepted_samples)
                / self._total_samples
                * 100
                if self._total_samples > 0
                else 0.0
            ),
            "total_cells": total_cells,
            "cells_with_data": cells_with_data,
            "coverage_pct": (
                cells_with_data / total_cells * 100 if total_cells > 0 else 0.0
            ),
            "avg_hits_per_cell": total_hits / total_cells if total_cells > 0 else 0.0,
            "weighting_strategy": type(self.weighting).__name__,
        }


# =============================================================================
# Convenience Functions
# =============================================================================


def create_rpm_axis(
    start: int = 1000,
    end: int = 6500,
    step: int = 500,
) -> List[float]:
    """
    Create a standard RPM axis.

    Args:
        start: Starting RPM (default: 1000)
        end: Ending RPM (default: 6500)
        step: Step size (default: 500)

    Returns:
        List of RPM values
    """
    return list(range(start, end + 1, step))


def create_map_axis(
    start: int = 20,
    end: int = 100,
    step: int = 10,
) -> List[float]:
    """
    Create a standard MAP axis in kPa.

    Args:
        start: Starting MAP (default: 20)
        end: Ending MAP (default: 100)
        step: Step size (default: 10)

    Returns:
        List of MAP values
    """
    return list(range(start, end + 1, step))


def create_ve_accumulator(
    rpm_axis: Optional[Sequence[float]] = None,
    map_axis: Optional[Sequence[float]] = None,
    use_tunelab_weighting: bool = True,
    min_hits: int = 3,
) -> WeightedBinAccumulator:
    """
    Create a VE table accumulator with common defaults.

    Args:
        rpm_axis: Custom RPM axis (default: 1000-6500 by 500)
        map_axis: Custom MAP axis (default: 20-100 by 10)
        use_tunelab_weighting: Use TuneLab logarithmic weighting
        min_hits: Minimum hits per cell

    Returns:
        Configured WeightedBinAccumulator
    """
    if rpm_axis is None:
        rpm_axis = create_rpm_axis()
    if map_axis is None:
        map_axis = create_map_axis()

    weighting = LogarithmicWeighting() if use_tunelab_weighting else UniformWeighting()

    return WeightedBinAccumulator(
        x_axis=rpm_axis,
        y_axis=map_axis,
        weighting=weighting,
        min_hits=min_hits,
    )


# =============================================================================
# TuneLab Compatibility
# =============================================================================


def generate_sample_table_tunelab_style(
    x_values: Sequence[float],
    y_values: Sequence[float],
    z_values: Sequence[float],
    x_axis: Sequence[float],
    y_axis: Sequence[float],
    min_hits: int = 1,
) -> Tuple[List[List[Optional[float]]], List[List[int]]]:
    """
    Generate a sample table using TuneLab's algorithm.

    This is a drop-in replacement for TuneLab's generate_sample_table()
    that works with raw arrays instead of Power Core channel objects.

    Args:
        x_values: X channel data (e.g., RPM)
        y_values: Y channel data (e.g., MAP)
        z_values: Z channel data (e.g., AFR)
        x_axis: X axis bins
        y_axis: Y axis bins
        min_hits: Minimum hits per cell (default: 1)

    Returns:
        Tuple of (value_table, hit_count_table)

    Example:
        >>> values, hits = generate_sample_table_tunelab_style(
        ...     x_values=df['RPM'],
        ...     y_values=df['MAP'],
        ...     z_values=df['AFR'],
        ...     x_axis=[1000, 2000, 3000, 4000, 5000],
        ...     y_axis=[20, 40, 60, 80, 100],
        ... )
    """
    acc = WeightedBinAccumulator(
        x_axis=x_axis,
        y_axis=y_axis,
        weighting=LogarithmicWeighting(),
        min_hits=min_hits,
    )

    acc.add_samples_batch(x_values, y_values, z_values)

    return acc.get_table(), acc.get_hit_counts()
