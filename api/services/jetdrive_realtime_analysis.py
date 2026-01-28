"""
JetDrive Real-Time Analysis Engine

Provides live analysis during capture without impacting 20Hz UI update rate:
- Coverage map with cell hit counts (RPM x MAP grid)
- VE delta calculation (AFR error by cell)
- Quality metrics (freshness, variance, missing channels)
- Alert detection (frozen RPM, implausible values, missing channels)

All updates are O(1) to maintain performance.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Binning configuration
RPM_BIN_SIZE = 500  # 500 RPM increments
MAP_BIN_SIZE = 10   # 10 kPa increments
RPM_MIN = 0
RPM_MAX = 10000     # 20 bins
MAP_MIN = 20        # kPa
MAP_MAX = 120       # kPa (10 bins)

# Total possible cells for coverage calculation
TOTAL_RPM_BINS = (RPM_MAX - RPM_MIN) // RPM_BIN_SIZE  # 20
TOTAL_MAP_BINS = (MAP_MAX - MAP_MIN) // MAP_BIN_SIZE  # 10
TOTAL_CELLS = TOTAL_RPM_BINS * TOTAL_MAP_BINS  # 200

# Alert thresholds
FROZEN_RPM_THRESHOLD_SEC = 2.0  # RPM unchanged for this long = frozen
FROZEN_TPS_THRESHOLD = 20.0     # Only alert if TPS > this (engine running)
AFR_MIN_PLAUSIBLE = 10.0
AFR_MAX_PLAUSIBLE = 18.0
CHANNEL_STALE_THRESHOLD_SEC = 5.0  # Channel not updated for this long = stale

# Quality weights
QUALITY_WEIGHT_FRESHNESS = 0.4
QUALITY_WEIGHT_COVERAGE = 0.3
QUALITY_WEIGHT_MISSING = 0.3

# Required channels for full analysis
REQUIRED_CHANNELS = ["rpm", "afr", "map_kpa"]
RECOMMENDED_CHANNELS = ["tps", "torque", "horsepower"]

# Alert queue size
MAX_ALERTS = 50


# =============================================================================
# Enums
# =============================================================================

class AlertType(str, Enum):
    """Types of real-time alerts."""
    FROZEN_RPM = "frozen_rpm"
    IMPLAUSIBLE_AFR = "implausible_afr"
    MISSING_CHANNEL = "missing_channel"
    STALE_CHANNEL = "stale_channel"
    OUT_OF_RANGE = "out_of_range"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CoverageCell:
    """A single cell in the RPM x MAP coverage grid."""
    rpm_bin: int  # Bin index (0-based)
    map_bin: int  # Bin index (0-based)
    hit_count: int = 0
    last_hit_time: float = 0.0
    
    @property
    def rpm_min(self) -> int:
        return RPM_MIN + self.rpm_bin * RPM_BIN_SIZE
    
    @property
    def rpm_max(self) -> int:
        return self.rpm_min + RPM_BIN_SIZE
    
    @property
    def map_min(self) -> int:
        return MAP_MIN + self.map_bin * MAP_BIN_SIZE
    
    @property
    def map_max(self) -> int:
        return self.map_min + MAP_BIN_SIZE
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "rpm_min": self.rpm_min,
            "rpm_max": self.rpm_max,
            "map_min": self.map_min,
            "map_max": self.map_max,
            "hit_count": self.hit_count,
        }


@dataclass
class VEDeltaCell:
    """AFR error tracking for a single cell."""
    rpm_bin: int
    map_bin: int
    afr_error_sum: float = 0.0
    afr_error_count: int = 0
    
    @property
    def afr_error_mean(self) -> float:
        if self.afr_error_count == 0:
            return 0.0
        return self.afr_error_sum / self.afr_error_count
    
    @property
    def rpm_min(self) -> int:
        return RPM_MIN + self.rpm_bin * RPM_BIN_SIZE
    
    @property
    def rpm_max(self) -> int:
        return self.rpm_min + RPM_BIN_SIZE
    
    @property
    def map_min(self) -> int:
        return MAP_MIN + self.map_bin * MAP_BIN_SIZE
    
    @property
    def map_max(self) -> int:
        return self.map_min + MAP_BIN_SIZE
    
    def update(self, afr_error: float) -> None:
        """Update running average with new error value. O(1)."""
        self.afr_error_sum += afr_error
        self.afr_error_count += 1
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "rpm_min": self.rpm_min,
            "rpm_max": self.rpm_max,
            "map_min": self.map_min,
            "map_max": self.map_max,
            "afr_error_mean": round(self.afr_error_mean, 3),
            "sample_count": self.afr_error_count,
        }


@dataclass
class QualityMetrics:
    """Data quality tracking."""
    channel_last_update: dict[str, float] = field(default_factory=dict)
    channel_values: dict[str, list[float]] = field(default_factory=dict)  # Recent values for variance
    missing_channels: list[str] = field(default_factory=list)
    overall_score: float = 100.0
    
    # Variance tracking window
    VARIANCE_WINDOW = 20  # Keep last 20 samples for variance calculation
    
    def update_channel(self, channel: str, value: float, timestamp: float) -> None:
        """Update channel freshness and variance tracking. O(1) amortized."""
        self.channel_last_update[channel] = timestamp
        
        # Track recent values for variance
        if channel not in self.channel_values:
            self.channel_values[channel] = []
        
        values = self.channel_values[channel]
        values.append(value)
        
        # Keep bounded
        if len(values) > self.VARIANCE_WINDOW:
            values.pop(0)
    
    def get_freshness(self, current_time: float) -> dict[str, float]:
        """Get seconds since last update for each channel."""
        return {
            ch: current_time - ts
            for ch, ts in self.channel_last_update.items()
        }
    
    def get_variance(self, channel: str) -> float | None:
        """Get variance of recent values for a channel."""
        values = self.channel_values.get(channel, [])
        if len(values) < 2:
            return None
        
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return variance
    
    def compute_score(self, current_time: float, coverage_pct: float) -> float:
        """Compute overall quality score (0-100)."""
        # Freshness score: penalize stale channels
        freshness = self.get_freshness(current_time)
        if freshness:
            avg_freshness = sum(freshness.values()) / len(freshness)
            # Score decreases as freshness increases (stale = bad)
            freshness_score = max(0, 100 - avg_freshness * 20)  # 5 sec = 0 score
        else:
            freshness_score = 0
        
        # Missing channels penalty
        missing_penalty = len(self.missing_channels) * 20  # -20 per missing required channel
        missing_score = max(0, 100 - missing_penalty)
        
        # Coverage contributes to score
        coverage_score = coverage_pct
        
        # Weighted average
        self.overall_score = (
            QUALITY_WEIGHT_FRESHNESS * freshness_score +
            QUALITY_WEIGHT_COVERAGE * coverage_score +
            QUALITY_WEIGHT_MISSING * missing_score
        )
        
        return self.overall_score
    
    def to_dict(self, current_time: float) -> dict[str, Any]:
        freshness = self.get_freshness(current_time)
        return {
            "score": round(self.overall_score, 1),
            "channel_freshness": {k: round(v, 2) for k, v in freshness.items()},
            "channel_variance": {
                ch: round(var, 4) if var is not None else None
                for ch in self.channel_values
                for var in [self.get_variance(ch)]
            },
            "missing_channels": self.missing_channels,
        }


@dataclass
class Alert:
    """A real-time alert."""
    type: AlertType
    severity: AlertSeverity
    channel: str
    message: str
    timestamp: float
    value: float | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "channel": self.channel,
            "message": self.message,
            "timestamp": self.timestamp,
            "value": self.value,
        }


# =============================================================================
# Main Engine
# =============================================================================

class RealtimeAnalysisEngine:
    """
    Real-time analysis engine for live JetDrive capture.
    
    All update methods are O(1) to maintain 20Hz UI responsiveness.
    """
    
    def __init__(self, target_afr: float = 14.7):
        """
        Initialize the analysis engine.
        
        Args:
            target_afr: Target AFR for VE delta calculation (default stoich)
        """
        self.target_afr = target_afr
        
        # Coverage map: (rpm_bin, map_bin) -> CoverageCell
        self.coverage_map: dict[tuple[int, int], CoverageCell] = {}
        
        # VE delta map: (rpm_bin, map_bin) -> VEDeltaCell
        self.ve_delta_map: dict[tuple[int, int], VEDeltaCell] = {}
        
        # Quality metrics
        self.quality = QualityMetrics()
        
        # Alert queue (bounded)
        self.alerts: deque[Alert] = deque(maxlen=MAX_ALERTS)
        
        # State tracking for alert detection
        self._last_rpm: float | None = None
        self._last_rpm_time: float = 0.0
        self._last_tps: float = 0.0
        self._active_cell: tuple[int, int] | None = None
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Start time for relative timestamps
        self._start_time = time.time()
    
    def on_aggregated_sample(self, data: dict[str, Any]) -> None:
        """
        Process an aggregated sample from the live capture queue.
        
        This is called once per 50ms aggregation window.
        All operations are O(1).
        
        Args:
            data: DynoDataPointSchema as dict (from to_dict())
        """
        current_time = time.time()
        
        with self._lock:
            # Extract values with graceful handling
            rpm = data.get("rpm")
            map_kpa = data.get("map_kpa")
            afr = data.get("afr")
            tps = data.get("tps")
            
            # Update quality metrics for all present channels
            self._update_quality(data, current_time)
            
            # Check for missing required channels
            self._check_missing_channels(data)
            
            # Detect alerts
            self._detect_alerts(data, current_time)
            
            # Update coverage and VE delta if we have required data
            if rpm is not None and rpm > 0:
                if map_kpa is not None:
                    # Update coverage
                    self._update_coverage(rpm, map_kpa, current_time)
                    
                    # Update VE delta if AFR available
                    if afr is not None:
                        self._update_ve_delta(rpm, map_kpa, afr)
                
                # Track RPM for frozen detection
                self._last_rpm = rpm
                self._last_rpm_time = current_time
            
            # Track TPS for frozen RPM detection context
            if tps is not None:
                self._last_tps = tps
    
    def _bin_rpm_map(self, rpm: float, map_kpa: float) -> tuple[int, int] | None:
        """
        Convert RPM and MAP to bin indices.
        
        Returns None if values are out of range.
        O(1) operation.
        """
        # Clamp to valid range
        if rpm < RPM_MIN or rpm >= RPM_MAX:
            return None
        if map_kpa < MAP_MIN or map_kpa >= MAP_MAX:
            return None
        
        rpm_bin = int((rpm - RPM_MIN) // RPM_BIN_SIZE)
        map_bin = int((map_kpa - MAP_MIN) // MAP_BIN_SIZE)
        
        return (rpm_bin, map_bin)
    
    def _update_coverage(self, rpm: float, map_kpa: float, current_time: float) -> None:
        """Update coverage map. O(1)."""
        bin_key = self._bin_rpm_map(rpm, map_kpa)
        if bin_key is None:
            return
        
        if bin_key not in self.coverage_map:
            self.coverage_map[bin_key] = CoverageCell(
                rpm_bin=bin_key[0],
                map_bin=bin_key[1],
            )
        
        cell = self.coverage_map[bin_key]
        cell.hit_count += 1
        cell.last_hit_time = current_time
        
        # Track active cell
        self._active_cell = bin_key
    
    def _update_ve_delta(self, rpm: float, map_kpa: float, afr: float) -> None:
        """Update VE delta (AFR error) map. O(1)."""
        bin_key = self._bin_rpm_map(rpm, map_kpa)
        if bin_key is None:
            return
        
        if bin_key not in self.ve_delta_map:
            self.ve_delta_map[bin_key] = VEDeltaCell(
                rpm_bin=bin_key[0],
                map_bin=bin_key[1],
            )
        
        afr_error = afr - self.target_afr
        self.ve_delta_map[bin_key].update(afr_error)
    
    def _update_quality(self, data: dict[str, Any], current_time: float) -> None:
        """Update quality metrics for all present channels. O(n) where n = channels."""
        channel_map = {
            "rpm": data.get("rpm"),
            "afr": data.get("afr"),
            "map_kpa": data.get("map_kpa"),
            "tps": data.get("tps"),
            "torque": data.get("torque"),
            "horsepower": data.get("horsepower"),
        }
        
        for channel, value in channel_map.items():
            if value is not None and not math.isnan(value):
                self.quality.update_channel(channel, value, current_time)
    
    def _check_missing_channels(self, data: dict[str, Any]) -> None:
        """Check for missing required channels. O(1)."""
        missing = []
        for ch in REQUIRED_CHANNELS:
            value = data.get(ch)
            if value is None or (isinstance(value, float) and math.isnan(value)):
                missing.append(ch)
        
        self.quality.missing_channels = missing
    
    def _detect_alerts(self, data: dict[str, Any], current_time: float) -> None:
        """Detect and emit alerts. O(1)."""
        rpm = data.get("rpm")
        afr = data.get("afr")
        tps = data.get("tps", self._last_tps)
        
        # Frozen RPM detection
        if (
            self._last_rpm is not None and
            rpm is not None and
            abs(rpm - self._last_rpm) < 1.0 and  # RPM unchanged
            tps > FROZEN_TPS_THRESHOLD and  # Engine should be running
            current_time - self._last_rpm_time > FROZEN_RPM_THRESHOLD_SEC
        ):
            self._add_alert(Alert(
                type=AlertType.FROZEN_RPM,
                severity=AlertSeverity.WARNING,
                channel="rpm",
                message=f"RPM frozen at {rpm:.0f} for {current_time - self._last_rpm_time:.1f}s with TPS={tps:.0f}%",
                timestamp=current_time,
                value=rpm,
            ))
        
        # Implausible AFR detection
        if afr is not None:
            if afr < AFR_MIN_PLAUSIBLE:
                self._add_alert(Alert(
                    type=AlertType.IMPLAUSIBLE_AFR,
                    severity=AlertSeverity.CRITICAL,
                    channel="afr",
                    message=f"AFR too low: {afr:.1f} (min plausible: {AFR_MIN_PLAUSIBLE})",
                    timestamp=current_time,
                    value=afr,
                ))
            elif afr > AFR_MAX_PLAUSIBLE:
                self._add_alert(Alert(
                    type=AlertType.IMPLAUSIBLE_AFR,
                    severity=AlertSeverity.WARNING,
                    channel="afr",
                    message=f"AFR too high: {afr:.1f} (max plausible: {AFR_MAX_PLAUSIBLE})",
                    timestamp=current_time,
                    value=afr,
                ))
        
        # Stale channel detection
        freshness = self.quality.get_freshness(current_time)
        for channel, staleness in freshness.items():
            if staleness > CHANNEL_STALE_THRESHOLD_SEC and channel in REQUIRED_CHANNELS:
                self._add_alert(Alert(
                    type=AlertType.STALE_CHANNEL,
                    severity=AlertSeverity.WARNING,
                    channel=channel,
                    message=f"Channel '{channel}' not updated for {staleness:.1f}s",
                    timestamp=current_time,
                ))
    
    def _add_alert(self, alert: Alert) -> None:
        """Add alert to queue, avoiding duplicates. O(n) where n = MAX_ALERTS."""
        # Check for recent duplicate (same type + channel within 5 seconds)
        for existing in self.alerts:
            if (
                existing.type == alert.type and
                existing.channel == alert.channel and
                alert.timestamp - existing.timestamp < 5.0
            ):
                return  # Skip duplicate
        
        self.alerts.append(alert)
    
    def get_coverage_stats(self) -> dict[str, Any]:
        """Get coverage statistics. Caller must hold lock or call from unlocked context."""
        total_hits = sum(cell.hit_count for cell in self.coverage_map.values())
        cells_hit = len(self.coverage_map)
        coverage_pct = (cells_hit / TOTAL_CELLS) * 100 if TOTAL_CELLS > 0 else 0
        
        # Get active cell info
        active_cell_info = None
        if self._active_cell and self._active_cell in self.coverage_map:
            cell = self.coverage_map[self._active_cell]
            ve_cell = self.ve_delta_map.get(self._active_cell)
            active_cell_info = {
                **cell.to_dict(),
                "afr_error_mean": ve_cell.afr_error_mean if ve_cell else None,
            }
        
        return {
            "cells": [cell.to_dict() for cell in self.coverage_map.values()],
            "total_hits": total_hits,
            "cells_hit": cells_hit,
            "total_cells": TOTAL_CELLS,
            "coverage_pct": round(coverage_pct, 1),
            "active_cell": active_cell_info,
        }
    
    def get_ve_delta_stats(self) -> dict[str, Any]:
        """Get VE delta statistics. Caller must hold lock or call from unlocked context."""
        cells = [cell.to_dict() for cell in self.ve_delta_map.values()]
        
        # Calculate overall mean error
        total_error = sum(cell.afr_error_sum for cell in self.ve_delta_map.values())
        total_count = sum(cell.afr_error_count for cell in self.ve_delta_map.values())
        mean_error = total_error / total_count if total_count > 0 else 0.0
        
        return {
            "cells": cells,
            "mean_error": round(mean_error, 3),
            "sample_count": total_count,
            "target_afr": self.target_afr,
        }
    
    def get_state(self) -> dict[str, Any]:
        """Get complete analysis state for API response."""
        current_time = time.time()
        
        with self._lock:
            coverage = self.get_coverage_stats()  # Called within lock
            ve_delta = self.get_ve_delta_stats()  # Called within lock
            
            # Compute quality score
            self.quality.compute_score(current_time, coverage["coverage_pct"])
            quality = self.quality.to_dict(current_time)
            
            alerts = [alert.to_dict() for alert in self.alerts]
            
            return {
                "enabled": True,
                "coverage": coverage,
                "ve_delta": ve_delta,
                "quality": quality,
                "alerts": alerts,
                "uptime_sec": round(current_time - self._start_time, 1),
            }
    
    def reset(self) -> None:
        """Reset all analysis state."""
        with self._lock:
            self.coverage_map.clear()
            self.ve_delta_map.clear()
            self.quality = QualityMetrics()
            self.alerts.clear()
            self._last_rpm = None
            self._last_rpm_time = 0.0
            self._last_tps = 0.0
            self._active_cell = None
            self._start_time = time.time()


# =============================================================================
# Global Instance
# =============================================================================

_realtime_engine: RealtimeAnalysisEngine | None = None
_engine_lock = threading.Lock()


def get_realtime_engine(target_afr: float = 14.7) -> RealtimeAnalysisEngine:
    """Get or create the global realtime analysis engine."""
    global _realtime_engine
    with _engine_lock:
        if _realtime_engine is None:
            _realtime_engine = RealtimeAnalysisEngine(target_afr=target_afr)
        return _realtime_engine


def reset_realtime_engine() -> None:
    """Reset the global engine."""
    global _realtime_engine
    with _engine_lock:
        if _realtime_engine is not None:
            _realtime_engine.reset()
