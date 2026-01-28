"""
JetDrive Data Quality Validation Service

Tracks and validates data quality metrics for JetDrive channels:
- Data freshness (time since last sample)
- Data rate (samples per second)
- Value validation (NaN, infinity, reasonable ranges)
- Frame drop tracking
- Channel health status
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any

from api.services.jetdrive_client import JetDriveSample

logger = logging.getLogger(__name__)


class ChannelHealth(Enum):
    """Health status for a channel."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    STALE = "stale"
    INVALID = "invalid"


@dataclass
class ChannelMetrics:
    """Metrics for a single channel, scoped by provider."""

    provider_id: int  # Provider that owns this channel
    channel_id: int
    channel_name: str

    # Sample tracking
    last_sample_time: float = 0.0
    last_value: float = 0.0
    last_timestamp_ms: int = 0

    # Rate tracking (samples per second)
    sample_times: deque = field(default_factory=lambda: deque(maxlen=100))
    samples_per_second: float = 0.0

    # Value validation
    invalid_value_count: int = 0
    total_samples: int = 0

    # Health status
    health: ChannelHealth = ChannelHealth.STALE
    health_reason: str = "No data received"

    # Expected ranges (optional, can be set per channel)
    min_value: float | None = None
    max_value: float | None = None

    @property
    def key(self) -> tuple[int, int]:
        """Return the unique key for this channel (provider_id, channel_id)."""
        return (self.provider_id, self.channel_id)

    def update(self, sample: JetDriveSample, current_time: float) -> None:
        """Update metrics with a new sample."""
        self.total_samples += 1
        self.last_sample_time = current_time
        self.last_value = sample.value
        self.last_timestamp_ms = sample.timestamp_ms

        # Track sample times for rate calculation
        self.sample_times.append(current_time)

        # Calculate samples per second (over last 10 samples or 1 second, whichever is shorter)
        if len(self.sample_times) >= 2:
            time_span = self.sample_times[-1] - self.sample_times[0]
            if time_span > 0:
                self.samples_per_second = len(self.sample_times) / time_span
            else:
                self.samples_per_second = len(self.sample_times)
        else:
            self.samples_per_second = 0.0

        # Validate value
        if not self._is_valid_value(sample.value):
            self.invalid_value_count += 1
        else:
            # Reset invalid count on valid sample (allows recovery)
            if self.invalid_value_count > 0:
                self.invalid_value_count = max(0, self.invalid_value_count - 1)

        # Update health status
        self._update_health(current_time)

    def _is_valid_value(self, value: float) -> bool:
        """Check if a value is valid (not NaN, not infinity, within range)."""
        if math.isnan(value) or math.isinf(value):
            return False

        if self.min_value is not None and value < self.min_value:
            return False

        if self.max_value is not None and value > self.max_value:
            return False

        return True

    def _update_health(self, current_time: float) -> None:
        """Update health status based on current metrics."""
        # Check for stale data (no update in last 5 seconds)
        time_since_last = current_time - self.last_sample_time
        if time_since_last > 5.0:
            self.health = ChannelHealth.STALE
            self.health_reason = f"No data for {time_since_last:.1f}s"
            return

        # Check for invalid values
        if self.invalid_value_count > 10:
            self.health = ChannelHealth.INVALID
            self.health_reason = f"{self.invalid_value_count} invalid values"
            return

        # Check for low data rate (less than 1 Hz is suspicious for dyno data)
        if self.samples_per_second < 1.0 and self.total_samples > 5:
            self.health = ChannelHealth.WARNING
            self.health_reason = f"Low rate: {self.samples_per_second:.1f} Hz"
            return

        # Check for reasonable data rate (dyno typically 10-100 Hz)
        if self.samples_per_second > 200:
            self.health = ChannelHealth.WARNING
            self.health_reason = f"Very high rate: {self.samples_per_second:.1f} Hz"
            return

        # All checks passed
        self.health = ChannelHealth.HEALTHY
        self.health_reason = "OK"

    def get_age_seconds(self, current_time: float) -> float:
        """Get age of last sample in seconds."""
        return current_time - self.last_sample_time

    def to_dict(self, current_time: float) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "provider_id": self.provider_id,
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "health": self.health.value,
            "health_reason": self.health_reason,
            "last_value": self.last_value,
            "last_timestamp_ms": self.last_timestamp_ms,
            "age_seconds": self.get_age_seconds(current_time),
            "samples_per_second": round(self.samples_per_second, 2),
            "total_samples": self.total_samples,
            "invalid_value_count": self.invalid_value_count,
            "last_sample_time": self.last_sample_time,
        }


@dataclass
class FrameStats:
    """Frame-level statistics."""

    total_frames: int = 0
    dropped_frames: int = 0
    malformed_frames: int = 0
    non_provider_frames: int = 0

    def get_drop_rate(self) -> float:
        """Get frame drop rate as percentage."""
        if self.total_frames == 0:
            return 0.0
        return (self.dropped_frames / self.total_frames) * 100.0


class JetDriveDataValidator:
    """
    Validates and tracks data quality for JetDrive channels.

    Channels are uniquely identified by (provider_id, channel_id) to prevent
    cross-contamination when multiple providers have overlapping channel IDs.
    """

    def __init__(
        self,
        stale_threshold_seconds: float = 5.0,
        min_samples_per_second: float = 1.0,
        max_samples_per_second: float = 200.0,
    ):
        """
        Initialize validator.

        Args:
            stale_threshold_seconds: Time before channel is considered stale
            min_samples_per_second: Minimum expected sample rate
            max_samples_per_second: Maximum expected sample rate
        """
        self.stale_threshold = stale_threshold_seconds
        self.min_rate = min_samples_per_second
        self.max_rate = max_samples_per_second

        # Channel metrics keyed by (provider_id, channel_id) tuple
        self._metrics: dict[tuple[int, int], ChannelMetrics] = {}
        self._metrics_lock = Lock()

        # Frame statistics (per provider)
        self._frame_stats: dict[int, FrameStats] = defaultdict(FrameStats)
        self._frame_stats_lock = Lock()

        # Channel value ranges (can be configured by channel name)
        self._value_ranges: dict[str, tuple[float, float]] = {}

        # Active provider filter (None = accept all)
        self._active_provider_id: int | None = None

    def set_active_provider(self, provider_id: int | None) -> None:
        """
        Set the active provider filter.

        When set, only samples from this provider will be recorded.
        Set to None to accept samples from all providers.
        """
        self._active_provider_id = provider_id
        logger.info(f"Active provider set to: {provider_id}")

    def get_active_provider(self) -> int | None:
        """Get the currently active provider ID."""
        return self._active_provider_id

    def set_channel_range(self, channel_name: str, min_val: float,
                          max_val: float) -> None:
        """Set expected value range for a channel (applies to all providers)."""
        self._value_ranges[channel_name] = (min_val, max_val)
        with self._metrics_lock:
            for metrics in self._metrics.values():
                if metrics.channel_name == channel_name:
                    metrics.min_value = min_val
                    metrics.max_value = max_val

    def record_sample(self, sample: JetDriveSample) -> bool:
        """
        Record a new sample and update metrics.

        Args:
            sample: The JetDrive sample to record

        Returns:
            True if sample was recorded, False if rejected (wrong provider)
        """
        # Filter by active provider if set
        if self._active_provider_id is not None:
            if sample.provider_id != self._active_provider_id:
                # Track as non-provider frame but don't record metrics
                with self._frame_stats_lock:
                    self._frame_stats[
                        sample.provider_id].non_provider_frames += 1
                return False

        current_time = time.time()
        key = (sample.provider_id, sample.channel_id)

        with self._metrics_lock:
            if key not in self._metrics:
                # Create new metrics for this (provider, channel) pair
                metrics = ChannelMetrics(
                    provider_id=sample.provider_id,
                    channel_id=sample.channel_id,
                    channel_name=sample.channel_name,
                )

                # Apply value range if configured
                if sample.channel_name in self._value_ranges:
                    min_val, max_val = self._value_ranges[sample.channel_name]
                    metrics.min_value = min_val
                    metrics.max_value = max_val

                self._metrics[key] = metrics

            self._metrics[key].update(sample, current_time)

        return True

    def record_frame_stats(
        self,
        provider_id: int,
        dropped: int = 0,
        malformed: int = 0,
        non_provider: int = 0,
        total: int = 1,
    ) -> None:
        """Record frame-level statistics for a provider."""
        with self._frame_stats_lock:
            stats = self._frame_stats[provider_id]
            stats.total_frames += total
            stats.dropped_frames += dropped
            stats.malformed_frames += malformed
            stats.non_provider_frames += non_provider

    def get_channel_health(self, provider_id: int,
                           channel_id: int) -> ChannelMetrics | None:
        """Get health metrics for a specific channel from a specific provider."""
        key = (provider_id, channel_id)
        with self._metrics_lock:
            return self._metrics.get(key)

    def get_channels_for_provider(self,
                                  provider_id: int) -> list[ChannelMetrics]:
        """Get all channel metrics for a specific provider."""
        with self._metrics_lock:
            return [
                m for m in self._metrics.values()
                if m.provider_id == provider_id
            ]

    def get_all_health(self, provider_id: int | None = None) -> dict[str, Any]:
        """
        Get health status for all channels.

        Args:
            provider_id: If specified, only return health for this provider.
                         If None, return health for all providers (or active provider if set).
        """
        current_time = time.time()

        # Determine which provider(s) to report on
        filter_provider = provider_id or self._active_provider_id

        with self._metrics_lock:
            if filter_provider is not None:
                # Filter to specific provider
                channels = {
                    f"{m.provider_id}_{m.channel_id}": m.to_dict(current_time)
                    for m in self._metrics.values()
                    if m.provider_id == filter_provider
                }
                metrics_list = [
                    m for m in self._metrics.values()
                    if m.provider_id == filter_provider
                ]
            else:
                # All providers
                channels = {
                    f"{m.provider_id}_{m.channel_id}": m.to_dict(current_time)
                    for m in self._metrics.values()
                }
                metrics_list = list(self._metrics.values())

        # Aggregate frame stats
        with self._frame_stats_lock:
            if filter_provider is not None:
                stats = self._frame_stats.get(filter_provider, FrameStats())
                frame_stats = {
                    "provider_id": filter_provider,
                    "total_frames": stats.total_frames,
                    "dropped_frames": stats.dropped_frames,
                    "malformed_frames": stats.malformed_frames,
                    "non_provider_frames": stats.non_provider_frames,
                    "drop_rate_percent": round(stats.get_drop_rate(), 2),
                }
            else:
                # Aggregate across all providers
                total = sum(s.total_frames for s in self._frame_stats.values())
                dropped = sum(s.dropped_frames
                              for s in self._frame_stats.values())
                malformed = sum(s.malformed_frames
                                for s in self._frame_stats.values())
                non_provider = sum(s.non_provider_frames
                                   for s in self._frame_stats.values())
                drop_rate = (dropped / total * 100) if total > 0 else 0.0
                frame_stats = {
                    "provider_id": None,
                    "total_frames": total,
                    "dropped_frames": dropped,
                    "malformed_frames": malformed,
                    "non_provider_frames": non_provider,
                    "drop_rate_percent": round(drop_rate, 2),
                }

        # Calculate overall health
        healthy_count = sum(1 for m in metrics_list
                            if m.health == ChannelHealth.HEALTHY)
        total_count = len(metrics_list)

        overall_health = ChannelHealth.HEALTHY
        if total_count == 0:
            overall_health = ChannelHealth.STALE
            health_reason = "No channels active"
        elif healthy_count == 0:
            overall_health = ChannelHealth.CRITICAL
            health_reason = "No healthy channels"
        elif healthy_count < total_count * 0.5:
            overall_health = ChannelHealth.WARNING
            health_reason = f"Only {healthy_count}/{total_count} channels healthy"
        else:
            health_reason = f"{healthy_count}/{total_count} channels healthy"

        return {
            "overall_health": overall_health.value,
            "health_reason": health_reason,
            "healthy_channels": healthy_count,
            "total_channels": total_count,
            "active_provider_id": self._active_provider_id,
            "channels": channels,
            "frame_stats": frame_stats,
            "timestamp": current_time,
        }

    def get_channel_summary(self,
                            provider_id: int | None = None) -> dict[str, Any]:
        """
        Get a summary of all channels for quick status check.

        Args:
            provider_id: If specified, only return summary for this provider.
                         If None, use active provider if set, else return all.
        """
        current_time = time.time()
        filter_provider = provider_id or self._active_provider_id

        with self._metrics_lock:
            summary = []
            for metrics in sorted(self._metrics.values(),
                                  key=lambda m: m.channel_name):
                if (filter_provider is not None
                        and metrics.provider_id != filter_provider):
                    continue
                age = metrics.get_age_seconds(current_time)
                summary.append({
                    "provider_id": metrics.provider_id,
                    "name": metrics.channel_name,
                    "id": metrics.channel_id,
                    "health": metrics.health.value,
                    "value": metrics.last_value,
                    "age_seconds": round(age, 2),
                    "rate_hz": round(metrics.samples_per_second, 2),
                })

        return {
            "channels": summary,
            "active_provider_id": self._active_provider_id,
            "timestamp": current_time,
        }

    def reset(self, provider_id: int | None = None) -> None:
        """
        Reset metrics.

        Args:
            provider_id: If specified, only reset metrics for this provider.
                         If None, reset all metrics.
        """
        with self._metrics_lock:
            if provider_id is not None:
                # Remove only metrics for this provider
                keys_to_remove = [
                    k for k in self._metrics.keys() if k[0] == provider_id
                ]
                for key in keys_to_remove:
                    del self._metrics[key]
            else:
                self._metrics.clear()

        with self._frame_stats_lock:
            if provider_id is not None:
                self._frame_stats[provider_id] = FrameStats()
            else:
                self._frame_stats.clear()

        # Also reset active provider if resetting all
        if provider_id is None:
            self._active_provider_id = None


# Global validator instance
_validator: JetDriveDataValidator | None = None


def get_validator() -> JetDriveDataValidator:
    """Get or create the global validator instance."""
    global _validator
    if _validator is None:
        _validator = JetDriveDataValidator()
    return _validator
