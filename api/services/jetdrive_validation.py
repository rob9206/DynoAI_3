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
    """Metrics for a single channel."""

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

        # Channel metrics
        self._metrics: dict[int, ChannelMetrics] = {}
        self._metrics_lock = Lock()

        # Frame statistics
        self._frame_stats = FrameStats()
        self._frame_stats_lock = Lock()

        # Channel value ranges (can be configured)
        self._value_ranges: dict[str, tuple[float, float]] = {}

    def set_channel_range(
        self, channel_name: str, min_val: float, max_val: float
    ) -> None:
        """Set expected value range for a channel."""
        self._value_ranges[channel_name] = (min_val, max_val)
        with self._metrics_lock:
            for metrics in self._metrics.values():
                if metrics.channel_name == channel_name:
                    metrics.min_value = min_val
                    metrics.max_value = max_val

    def record_sample(self, sample: JetDriveSample) -> None:
        """Record a new sample and update metrics."""
        current_time = time.time()

        with self._metrics_lock:
            if sample.channel_id not in self._metrics:
                # Create new metrics
                metrics = ChannelMetrics(
                    channel_id=sample.channel_id,
                    channel_name=sample.channel_name,
                )

                # Apply value range if configured
                if sample.channel_name in self._value_ranges:
                    min_val, max_val = self._value_ranges[sample.channel_name]
                    metrics.min_value = min_val
                    metrics.max_value = max_val

                self._metrics[sample.channel_id] = metrics

            self._metrics[sample.channel_id].update(sample, current_time)

    def record_frame_stats(
        self,
        dropped: int = 0,
        malformed: int = 0,
        non_provider: int = 0,
        total: int = 1,
    ) -> None:
        """Record frame-level statistics."""
        with self._frame_stats_lock:
            self._frame_stats.total_frames += total
            self._frame_stats.dropped_frames += dropped
            self._frame_stats.malformed_frames += malformed
            self._frame_stats.non_provider_frames += non_provider

    def get_channel_health(self, channel_id: int) -> ChannelMetrics | None:
        """Get health metrics for a specific channel."""
        with self._metrics_lock:
            return self._metrics.get(channel_id)

    def get_all_health(self) -> dict[str, Any]:
        """Get health status for all channels."""
        current_time = time.time()

        with self._metrics_lock:
            channels = {
                str(metrics.channel_id): metrics.to_dict(current_time)
                for metrics in self._metrics.values()
            }

        with self._frame_stats_lock:
            frame_stats = {
                "total_frames": self._frame_stats.total_frames,
                "dropped_frames": self._frame_stats.dropped_frames,
                "malformed_frames": self._frame_stats.malformed_frames,
                "non_provider_frames": self._frame_stats.non_provider_frames,
                "drop_rate_percent": round(self._frame_stats.get_drop_rate(), 2),
            }

        # Calculate overall health
        healthy_count = sum(
            1 for m in self._metrics.values() if m.health == ChannelHealth.HEALTHY
        )
        total_count = len(self._metrics)

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
            "channels": channels,
            "frame_stats": frame_stats,
            "timestamp": current_time,
        }

    def get_channel_summary(self) -> dict[str, Any]:
        """Get a summary of all channels for quick status check."""
        current_time = time.time()

        with self._metrics_lock:
            summary = []
            for metrics in sorted(self._metrics.values(), key=lambda m: m.channel_name):
                age = metrics.get_age_seconds(current_time)
                summary.append(
                    {
                        "name": metrics.channel_name,
                        "id": metrics.channel_id,
                        "health": metrics.health.value,
                        "value": metrics.last_value,
                        "age_seconds": round(age, 2),
                        "rate_hz": round(metrics.samples_per_second, 2),
                    }
                )

        return {
            "channels": summary,
            "timestamp": current_time,
        }

    def reset(self) -> None:
        """Reset all metrics (useful for testing or restart)."""
        with self._metrics_lock:
            self._metrics.clear()

        with self._frame_stats_lock:
            self._frame_stats = FrameStats()


# Global validator instance
_validator: JetDriveDataValidator | None = None


def get_validator() -> JetDriveDataValidator:
    """Get or create the global validator instance."""
    global _validator
    if _validator is None:
        _validator = JetDriveDataValidator()
    return _validator
