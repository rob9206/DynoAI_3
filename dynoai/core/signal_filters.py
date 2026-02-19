"""
DynoAI Signal Filters Module - TuneLab-Inspired Data Filtering

This module provides signal processing filters inspired by Dynojet Power Core's
TuneLab filtering system. These filters are designed for automotive sensor data,
particularly AFR (Air/Fuel Ratio) signals from wideband O2 sensors.

Filters included:
- LowpassFilter: RC-style IIR lowpass filter for noise reduction
- MinMaxFilter: Simple range clamping
- TimeAwareMinMaxFilter: Range clamping with time-based neighbor exclusion
- StatisticalOutlierFilter: 2-sigma statistical rejection
- CompositeFilter: Chain multiple filters together

Usage:
    from dynoai.core.signal_filters import (
        LowpassFilter, TimeAwareMinMaxFilter, StatisticalOutlierFilter,
        CompositeFilter, FilteredSample
    )
    
    # Create a composite filter chain (TuneLab-style)
    afr_filter = CompositeFilter([
        LowpassFilter(rc_ms=500.0),
        TimeAwareMinMaxFilter(min_val=10.0, max_val=19.0, exclude_ms=50),
        StatisticalOutlierFilter(sigma_threshold=2.0),
    ])
    
    # Filter samples
    filtered = afr_filter.filter(samples)

References:
    - Dynojet Power Core tlfilters.py
    - docs/TUNELAB_INTEGRATION.md
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple, Union
import logging

__all__ = [
    "FilteredSample",
    "SignalFilter",
    "LowpassFilter",
    "MinMaxFilter",
    "TimeAwareMinMaxFilter",
    "StatisticalOutlierFilter",
    "CompositeFilter",
    "filter_afr_samples",
]

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class FilteredSample:
    """
    A single data sample with timestamp and value.
    
    Attributes:
        time_ms: Timestamp in milliseconds
        value: Sample value (e.g., AFR reading)
        is_valid: Whether the sample passed all filters
        original_value: Original value before any filtering
    """
    time_ms: float
    value: float
    is_valid: bool = True
    original_value: Optional[float] = None
    
    def __post_init__(self):
        if self.original_value is None:
            self.original_value = self.value
    
    def invalidate(self) -> None:
        """Mark this sample as invalid (sets value to NaN)."""
        self.is_valid = False
        self.value = float('nan')
    
    @property
    def is_nan(self) -> bool:
        """Check if value is NaN."""
        return math.isnan(self.value) if self.value == self.value else True


@dataclass
class FilterStatistics:
    """Statistics from a filtering operation."""
    total_samples: int = 0
    valid_samples: int = 0
    rejected_samples: int = 0
    rejection_reasons: dict = field(default_factory=dict)
    
    @property
    def rejection_rate(self) -> float:
        """Percentage of samples rejected."""
        if self.total_samples == 0:
            return 0.0
        return (self.rejected_samples / self.total_samples) * 100.0


# =============================================================================
# Base Filter Class
# =============================================================================


class SignalFilter(ABC):
    """
    Abstract base class for signal filters.
    
    All filters operate on lists of FilteredSample objects in-place,
    modifying the is_valid flag and value as needed.
    """
    
    @abstractmethod
    def filter(self, samples: List[FilteredSample]) -> List[FilteredSample]:
        """
        Apply filter to samples.
        
        Args:
            samples: List of FilteredSample objects (modified in-place)
            
        Returns:
            The same list of samples (for chaining)
        """
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset any internal filter state."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable filter name."""
        pass


# =============================================================================
# Lowpass Filter (TuneLab-style RC filter)
# =============================================================================


class LowpassFilter(SignalFilter):
    """
    RC-style IIR lowpass filter for noise reduction.
    
    This is equivalent to TuneLab's LowpassFilter. The RC time constant
    controls the cutoff frequency: higher RC = more smoothing.
    
    Transfer function: y[i] = α×x[i] + (1-α)×y[i-1]
    Where: α = dt / (RC + dt)
    
    Args:
        rc_ms: RC time constant in milliseconds (default: 200)
            - 100-200: Light smoothing, preserves transients
            - 300-500: Medium smoothing, good for AFR
            - 500-1000: Heavy smoothing, may blur transients
    
    Example:
        >>> filter = LowpassFilter(rc_ms=500.0)
        >>> filtered = filter.filter(samples)
    """
    
    def __init__(self, rc_ms: float = 200.0):
        if rc_ms <= 0:
            raise ValueError("RC time constant must be positive")
        self.rc_ms = rc_ms
        self._last_valid_idx: int = -1
        self._stats = FilterStatistics()
    
    @property
    def name(self) -> str:
        return f"LowpassFilter(RC={self.rc_ms}ms)"
    
    def reset(self) -> None:
        self._last_valid_idx = -1
        self._stats = FilterStatistics()
    
    def filter(self, samples: List[FilteredSample]) -> List[FilteredSample]:
        """
        Apply lowpass filter to samples.
        
        Samples with is_valid=False are skipped but the filter state
        continues from the last valid sample.
        """
        self.reset()
        
        if len(samples) < 2:
            return samples
        
        self._stats.total_samples = len(samples)
        
        for i in range(1, len(samples)):
            if not samples[i].is_valid:
                continue
            
            # Find last valid sample for time delta
            if self._last_valid_idx < 0:
                self._last_valid_idx = i
                self._stats.valid_samples += 1
                continue
            
            prev_sample = samples[self._last_valid_idx]
            
            # Calculate time delta and alpha
            dt_ms = samples[i].time_ms - prev_sample.time_ms
            if dt_ms <= 0:
                dt_ms = 1.0  # Prevent division issues
            
            alpha = dt_ms / (self.rc_ms + dt_ms)
            
            # Apply IIR filter: y[i] = α×x[i] + (1-α)×y[i-1]
            samples[i].value = (
                alpha * samples[i].value + 
                (1.0 - alpha) * prev_sample.value
            )
            
            self._last_valid_idx = i
            self._stats.valid_samples += 1
        
        return samples
    
    @property
    def statistics(self) -> FilterStatistics:
        return self._stats


# =============================================================================
# Min/Max Filter
# =============================================================================


class MinMaxFilter(SignalFilter):
    """
    Simple range clamping filter.
    
    Samples outside [min_val, max_val] are marked invalid (NaN).
    Equivalent to TuneLab's BasicMinMaxZFilter.
    
    Args:
        min_val: Minimum valid value (default: 10.0 for AFR)
        max_val: Maximum valid value (default: 19.0 for AFR)
    
    Example:
        >>> filter = MinMaxFilter(min_val=10.0, max_val=18.0)
        >>> filtered = filter.filter(samples)
    """
    
    def __init__(self, min_val: float = 10.0, max_val: float = 19.0):
        if min_val >= max_val:
            raise ValueError("min_val must be less than max_val")
        self.min_val = min_val
        self.max_val = max_val
        self._stats = FilterStatistics()
    
    @property
    def name(self) -> str:
        return f"MinMaxFilter([{self.min_val}, {self.max_val}])"
    
    def reset(self) -> None:
        self._stats = FilterStatistics()
    
    def filter(self, samples: List[FilteredSample]) -> List[FilteredSample]:
        """Apply range filter, invalidating out-of-range samples."""
        self.reset()
        self._stats.total_samples = len(samples)
        
        for sample in samples:
            if not sample.is_valid:
                continue
            
            if sample.value < self.min_val or sample.value > self.max_val:
                sample.invalidate()
                self._stats.rejected_samples += 1
                reason = "below_min" if sample.value < self.min_val else "above_max"
                self._stats.rejection_reasons[reason] = (
                    self._stats.rejection_reasons.get(reason, 0) + 1
                )
            else:
                self._stats.valid_samples += 1
        
        return samples
    
    @property
    def statistics(self) -> FilterStatistics:
        return self._stats


# =============================================================================
# Time-Aware Min/Max Filter (TuneLab TimeMinMaxZFilter)
# =============================================================================


class TimeAwareMinMaxFilter(SignalFilter):
    """
    Range filter with time-based neighbor exclusion.
    
    When a sample is outside [min_val, max_val], this filter also
    invalidates samples within ±exclude_ms of the outlier. This prevents
    transient spikes from corrupting nearby valid data.
    
    Equivalent to TuneLab's TimeMinMaxZFilter.
    
    Args:
        min_val: Minimum valid value
        max_val: Maximum valid value
        exclude_leading_ms: Time before outlier to exclude (default: 50ms)
        exclude_trailing_ms: Time after outlier to exclude (default: 50ms)
    
    Example:
        >>> filter = TimeAwareMinMaxFilter(
        ...     min_val=10.0, max_val=19.0,
        ...     exclude_leading_ms=50, exclude_trailing_ms=50
        ... )
    """
    
    def __init__(
        self,
        min_val: float = 10.0,
        max_val: float = 19.0,
        exclude_leading_ms: float = 50.0,
        exclude_trailing_ms: float = 50.0,
    ):
        if min_val >= max_val:
            raise ValueError("min_val must be less than max_val")
        self.min_val = min_val
        self.max_val = max_val
        self.exclude_leading_ms = exclude_leading_ms
        self.exclude_trailing_ms = exclude_trailing_ms
        self._stats = FilterStatistics()
    
    @property
    def name(self) -> str:
        return (
            f"TimeAwareMinMaxFilter([{self.min_val}, {self.max_val}], "
            f"±{self.exclude_leading_ms}/{self.exclude_trailing_ms}ms)"
        )
    
    def reset(self) -> None:
        self._stats = FilterStatistics()
    
    def filter(self, samples: List[FilteredSample]) -> List[FilteredSample]:
        """Apply range filter with time-based neighbor exclusion."""
        self.reset()
        self._stats.total_samples = len(samples)
        
        if not samples:
            return samples
        
        # First pass: identify outliers and their exclusion ranges
        exclusion_ranges: List[Tuple[float, float]] = []
        
        in_outlier = False
        outlier_start_time = 0.0
        
        for i, sample in enumerate(samples):
            if not sample.is_valid:
                continue
            
            is_out_of_bounds = (
                sample.value < self.min_val or 
                sample.value > self.max_val
            )
            
            if is_out_of_bounds:
                if not in_outlier:
                    # Start of outlier region
                    in_outlier = True
                    outlier_start_time = sample.time_ms - self.exclude_leading_ms
                
                sample.invalidate()
                self._stats.rejected_samples += 1
                self._stats.rejection_reasons["out_of_range"] = (
                    self._stats.rejection_reasons.get("out_of_range", 0) + 1
                )
            else:
                if in_outlier:
                    # End of outlier region
                    in_outlier = False
                    outlier_end_time = sample.time_ms + self.exclude_trailing_ms
                    exclusion_ranges.append((outlier_start_time, outlier_end_time))
        
        # Handle case where we end while still in outlier
        if in_outlier and samples:
            outlier_end_time = samples[-1].time_ms + self.exclude_trailing_ms
            exclusion_ranges.append((outlier_start_time, outlier_end_time))
        
        # Second pass: invalidate samples in exclusion ranges
        for sample in samples:
            if not sample.is_valid:
                continue
            
            for start_time, end_time in exclusion_ranges:
                if start_time <= sample.time_ms <= end_time:
                    sample.invalidate()
                    self._stats.rejected_samples += 1
                    self._stats.rejection_reasons["neighbor_exclusion"] = (
                        self._stats.rejection_reasons.get("neighbor_exclusion", 0) + 1
                    )
                    break
            else:
                self._stats.valid_samples += 1
        
        return samples
    
    @property
    def statistics(self) -> FilterStatistics:
        return self._stats


# =============================================================================
# Statistical Outlier Filter (TuneLab AdvancedAfrFilter)
# =============================================================================


class StatisticalOutlierFilter(SignalFilter):
    """
    Statistical outlier rejection using Welford's algorithm.
    
    Samples beyond sigma_threshold standard deviations from the running
    mean are rejected, along with nearby samples (±reject_neighbors).
    
    Equivalent to TuneLab's AdvancedAfrFilter, developed by Wayne Radochonski.
    
    The filter only activates when standard deviation exceeds min_std_threshold,
    preventing rejection in stable data (no big spikes to filter).
    
    Args:
        sigma_threshold: Number of standard deviations for rejection (default: 2.0)
        min_std_threshold: Minimum std dev to activate filter (default: 0.5)
        reject_leading_samples: Samples to reject before outlier (default: 5)
        reject_trailing_samples: Samples to reject after outlier (default: 5)
    
    Example:
        >>> filter = StatisticalOutlierFilter(sigma_threshold=2.0)
    """
    
    def __init__(
        self,
        sigma_threshold: float = 2.0,
        min_std_threshold: float = 0.5,
        reject_leading_samples: int = 5,
        reject_trailing_samples: int = 5,
    ):
        self.sigma_threshold = sigma_threshold
        self.min_std_threshold = min_std_threshold
        self.reject_leading_samples = reject_leading_samples
        self.reject_trailing_samples = reject_trailing_samples
        
        # Welford's algorithm state
        self._n = 0
        self._mean = 0.0
        self._m2 = 0.0
        self._stats = FilterStatistics()
    
    @property
    def name(self) -> str:
        return f"StatisticalOutlierFilter({self.sigma_threshold}σ)"
    
    def reset(self) -> None:
        self._n = 0
        self._mean = 0.0
        self._m2 = 0.0
        self._stats = FilterStatistics()
    
    def _add_sample(self, x: float) -> None:
        """Add sample to running statistics (Welford's algorithm)."""
        self._n += 1
        delta = x - self._mean
        self._mean += delta / self._n
        delta2 = x - self._mean
        self._m2 += delta * delta2
    
    @property
    def variance(self) -> float:
        """Current variance estimate."""
        if self._n < 2:
            return 0.0
        return self._m2 / (self._n - 1)
    
    @property
    def std_dev(self) -> float:
        """Current standard deviation estimate."""
        return math.sqrt(self.variance)
    
    def _is_outlier(self, x: float) -> bool:
        """Check if value is an outlier based on current statistics."""
        std = self.std_dev
        
        # Only filter if std dev is significant (data has real spikes)
        if std < self.min_std_threshold:
            return False
        
        return abs(x - self._mean) > (self.sigma_threshold * std)
    
    def filter(self, samples: List[FilteredSample]) -> List[FilteredSample]:
        """
        Apply statistical outlier filter.
        
        Two-pass algorithm:
        1. Calculate running statistics from all valid samples
        2. Reject outliers and their neighbors
        """
        self.reset()
        self._stats.total_samples = len(samples)
        
        if len(samples) < 3:
            return samples
        
        # First pass: calculate statistics
        for sample in samples:
            if sample.is_valid and not sample.is_nan:
                self._add_sample(sample.value)
        
        # Second pass: identify outliers and rejection ranges
        reject_indices: set = set()
        
        for i, sample in enumerate(samples):
            if not sample.is_valid:
                continue
            
            if self._is_outlier(sample.value):
                # Mark this sample and neighbors for rejection
                start_idx = max(0, i - self.reject_leading_samples)
                end_idx = min(len(samples) - 1, i + self.reject_trailing_samples)
                
                for j in range(start_idx, end_idx + 1):
                    reject_indices.add(j)
        
        # Apply rejections
        for i, sample in enumerate(samples):
            if not sample.is_valid:
                continue
            
            if i in reject_indices:
                sample.invalidate()
                self._stats.rejected_samples += 1
                self._stats.rejection_reasons["statistical_outlier"] = (
                    self._stats.rejection_reasons.get("statistical_outlier", 0) + 1
                )
            else:
                self._stats.valid_samples += 1
        
        logger.debug(
            f"StatisticalOutlierFilter: mean={self._mean:.2f}, std={self.std_dev:.2f}, "
            f"rejected={self._stats.rejected_samples}/{self._stats.total_samples}"
        )
        
        return samples
    
    @property
    def statistics(self) -> FilterStatistics:
        return self._stats


# =============================================================================
# Composite Filter (Filter Chain)
# =============================================================================


class CompositeFilter(SignalFilter):
    """
    Chain multiple filters together.
    
    Filters are applied in order. Each filter sees the output of the
    previous filter. Statistics are collected from all filters.
    
    Example:
        >>> # TuneLab-style AFR filter chain
        >>> afr_filter = CompositeFilter([
        ...     LowpassFilter(rc_ms=500.0),
        ...     TimeAwareMinMaxFilter(min_val=10.0, max_val=19.0),
        ...     StatisticalOutlierFilter(sigma_threshold=2.0),
        ... ])
        >>> filtered = afr_filter.filter(samples)
    """
    
    def __init__(self, filters: List[SignalFilter]):
        if not filters:
            raise ValueError("At least one filter required")
        self.filters = filters
        self._combined_stats = FilterStatistics()
    
    @property
    def name(self) -> str:
        names = [f.name for f in self.filters]
        return f"CompositeFilter([{', '.join(names)}])"
    
    def reset(self) -> None:
        for f in self.filters:
            f.reset()
        self._combined_stats = FilterStatistics()
    
    def filter(self, samples: List[FilteredSample]) -> List[FilteredSample]:
        """Apply all filters in sequence."""
        self.reset()
        
        for f in self.filters:
            samples = f.filter(samples)
        
        # Combine statistics
        self._combined_stats.total_samples = len(samples)
        self._combined_stats.valid_samples = sum(1 for s in samples if s.is_valid)
        self._combined_stats.rejected_samples = (
            self._combined_stats.total_samples - self._combined_stats.valid_samples
        )
        
        # Merge rejection reasons from all filters
        for f in self.filters:
            for reason, count in f.statistics.rejection_reasons.items():
                self._combined_stats.rejection_reasons[reason] = (
                    self._combined_stats.rejection_reasons.get(reason, 0) + count
                )
        
        return samples
    
    @property
    def statistics(self) -> FilterStatistics:
        return self._combined_stats


# =============================================================================
# Convenience Functions
# =============================================================================


def samples_from_arrays(
    times_ms: Sequence[float],
    values: Sequence[float],
) -> List[FilteredSample]:
    """
    Create FilteredSample list from parallel arrays.
    
    Args:
        times_ms: Timestamps in milliseconds
        values: Sample values
        
    Returns:
        List of FilteredSample objects
    """
    if len(times_ms) != len(values):
        raise ValueError("times_ms and values must have same length")
    
    return [
        FilteredSample(time_ms=t, value=v)
        for t, v in zip(times_ms, values)
    ]


def samples_to_arrays(
    samples: List[FilteredSample],
    include_invalid: bool = False,
) -> Tuple[List[float], List[float]]:
    """
    Convert FilteredSample list to parallel arrays.
    
    Args:
        samples: List of FilteredSample objects
        include_invalid: If False, skip invalid samples
        
    Returns:
        Tuple of (times_ms, values)
    """
    times = []
    values = []
    
    for s in samples:
        if include_invalid or s.is_valid:
            times.append(s.time_ms)
            values.append(s.value)
    
    return times, values


def filter_afr_samples(
    times_ms: Sequence[float],
    afr_values: Sequence[float],
    lowpass_rc_ms: float = 500.0,
    min_afr: float = 10.0,
    max_afr: float = 19.0,
    exclude_ms: float = 50.0,
    sigma_threshold: float = 2.0,
    enable_lowpass: bool = True,
    enable_range_filter: bool = True,
    enable_statistical: bool = True,
) -> Tuple[List[float], List[float], FilterStatistics]:
    """
    Convenience function to filter AFR data with TuneLab-style filtering.
    
    This applies the full filter chain:
    1. Lowpass smoothing (optional)
    2. Time-aware range filter (optional)
    3. Statistical outlier rejection (optional)
    
    Args:
        times_ms: Timestamps in milliseconds
        afr_values: AFR readings
        lowpass_rc_ms: RC time constant for lowpass filter
        min_afr: Minimum valid AFR
        max_afr: Maximum valid AFR
        exclude_ms: Time to exclude around range violations
        sigma_threshold: Standard deviations for outlier rejection
        enable_lowpass: Enable lowpass filter
        enable_range_filter: Enable range filter
        enable_statistical: Enable statistical filter
        
    Returns:
        Tuple of (filtered_times, filtered_values, statistics)
        
    Example:
        >>> times, values, stats = filter_afr_samples(
        ...     times_ms=[0, 10, 20, 30],
        ...     afr_values=[13.0, 13.1, 25.0, 13.2],  # 25.0 is outlier
        ... )
        >>> print(f"Rejected {stats.rejection_rate:.1f}% of samples")
    """
    # Build filter chain
    filters: List[SignalFilter] = []
    
    if enable_lowpass:
        filters.append(LowpassFilter(rc_ms=lowpass_rc_ms))
    
    if enable_range_filter:
        filters.append(TimeAwareMinMaxFilter(
            min_val=min_afr,
            max_val=max_afr,
            exclude_leading_ms=exclude_ms,
            exclude_trailing_ms=exclude_ms,
        ))
    
    if enable_statistical:
        filters.append(StatisticalOutlierFilter(sigma_threshold=sigma_threshold))
    
    if not filters:
        # No filters enabled, return as-is
        return list(times_ms), list(afr_values), FilterStatistics()
    
    # Create composite filter and apply
    composite = CompositeFilter(filters)
    samples = samples_from_arrays(times_ms, afr_values)
    filtered_samples = composite.filter(samples)
    
    # Extract valid samples
    filtered_times, filtered_values = samples_to_arrays(
        filtered_samples, include_invalid=False
    )
    
    return filtered_times, filtered_values, composite.statistics


# =============================================================================
# TuneLab Compatibility Functions
# =============================================================================


def create_tunelab_filter_chain(
    smoothing: float = 500.0,
    min_afr: float = 10.0,
    max_afr: float = 19.0,
) -> CompositeFilter:
    """
    Create a filter chain matching TuneLab/EasyLab defaults.
    
    This replicates the filtering behavior of:
    - tlfilters.LowpassFilter(rc=500)
    - tlfilters.TimeMinMaxZFilter(min=10, max=19)
    
    Args:
        smoothing: RC time constant (TuneLab default: 500)
        min_afr: Minimum AFR (TuneLab default: 10)
        max_afr: Maximum AFR (TuneLab default: 19)
        
    Returns:
        CompositeFilter configured for TuneLab compatibility
    """
    return CompositeFilter([
        LowpassFilter(rc_ms=smoothing),
        TimeAwareMinMaxFilter(
            min_val=min_afr,
            max_val=max_afr,
            exclude_leading_ms=50.0,
            exclude_trailing_ms=50.0,
        ),
    ])
