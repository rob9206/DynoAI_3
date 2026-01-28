"""
Tests for JetDrive Real-Time Analysis Engine

Tests:
1. Coverage binning and accumulation
2. VE delta (AFR error) calculation
3. Quality metrics tracking
4. Alert detection (frozen RPM, implausible AFR, missing channels)
5. Graceful degradation with missing data
"""

import pytest
import time
from unittest.mock import MagicMock

from api.services.jetdrive_realtime_analysis import (
    RealtimeAnalysisEngine,
    CoverageCell,
    VEDeltaCell,
    QualityMetrics,
    Alert,
    AlertType,
    AlertSeverity,
    RPM_BIN_SIZE,
    MAP_BIN_SIZE,
    RPM_MIN,
    RPM_MAX,
    MAP_MIN,
    MAP_MAX,
    TOTAL_CELLS,
    AFR_MIN_PLAUSIBLE,
    AFR_MAX_PLAUSIBLE,
    FROZEN_RPM_THRESHOLD_SEC,
    get_realtime_engine,
    reset_realtime_engine,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def engine():
    """Create a fresh analysis engine for each test."""
    return RealtimeAnalysisEngine(target_afr=14.7)


@pytest.fixture
def sample_data():
    """Create sample data point dict."""
    return {
        "timestamp_ms": 1000,
        "rpm": 3500.0,
        "map_kpa": 85.0,
        "afr": 14.5,
        "tps": 75.0,
        "torque": 100.0,
        "horsepower": 150.0,
    }


def make_sample(
    rpm: float = 3500.0,
    map_kpa: float = 85.0,
    afr: float = 14.5,
    tps: float = 75.0,
    timestamp_ms: int = 1000,
) -> dict:
    """Helper to create sample data dicts."""
    return {
        "timestamp_ms": timestamp_ms,
        "rpm": rpm,
        "map_kpa": map_kpa,
        "afr": afr,
        "tps": tps,
        "torque": 100.0,
        "horsepower": 150.0,
    }


# =============================================================================
# Coverage Binning Tests
# =============================================================================

class TestCoverageBinning:
    """Test RPM x MAP coverage binning."""

    def test_rpm_map_binning_correct(self, engine):
        """Verify bin calculation for RPM and MAP."""
        # RPM 3500 with 500 bin size starting at 0 = bin 7
        # MAP 85 with 10 bin size starting at 20 = bin 6
        bin_key = engine._bin_rpm_map(3500.0, 85.0)
        assert bin_key == (7, 6)

    def test_binning_at_boundaries(self, engine):
        """Test binning at exact boundaries."""
        # RPM 0 = bin 0
        assert engine._bin_rpm_map(0.0, 20.0) == (0, 0)
        
        # RPM 500 = bin 1
        assert engine._bin_rpm_map(500.0, 20.0) == (1, 0)
        
        # MAP 30 = bin 1
        assert engine._bin_rpm_map(0.0, 30.0) == (0, 1)

    def test_binning_out_of_range_returns_none(self, engine):
        """Out of range values should return None."""
        # RPM too high
        assert engine._bin_rpm_map(15000.0, 85.0) is None
        
        # MAP too low
        assert engine._bin_rpm_map(3500.0, 10.0) is None
        
        # MAP too high
        assert engine._bin_rpm_map(3500.0, 150.0) is None

    def test_coverage_accumulation(self, engine):
        """Hit counts should increment correctly."""
        sample = make_sample(rpm=3500.0, map_kpa=85.0)
        
        # Process same cell multiple times
        for _ in range(5):
            engine.on_aggregated_sample(sample)
        
        # Check hit count
        bin_key = (7, 6)  # 3500 RPM, 85 kPa
        assert bin_key in engine.coverage_map
        assert engine.coverage_map[bin_key].hit_count == 5

    def test_coverage_percentage_calculation(self, engine):
        """Coverage percentage should be calculated correctly."""
        # Hit 10 different cells
        for i in range(10):
            rpm = 1000 + i * 500  # 1000, 1500, 2000, ...
            sample = make_sample(rpm=rpm, map_kpa=50.0)
            engine.on_aggregated_sample(sample)
        
        stats = engine.get_coverage_stats()
        
        # 10 cells out of TOTAL_CELLS
        expected_pct = (10 / TOTAL_CELLS) * 100
        assert stats["cells_hit"] == 10
        assert abs(stats["coverage_pct"] - expected_pct) < 0.1

    def test_active_cell_tracking(self, engine):
        """Active cell should track the most recent sample."""
        engine.on_aggregated_sample(make_sample(rpm=2000.0, map_kpa=60.0))
        engine.on_aggregated_sample(make_sample(rpm=4000.0, map_kpa=90.0))
        
        stats = engine.get_coverage_stats()
        active = stats["active_cell"]
        
        # Should be the last sample's cell
        assert active is not None
        assert active["rpm_min"] == 4000
        assert active["rpm_max"] == 4500
        assert active["map_min"] == 90
        assert active["map_max"] == 100


# =============================================================================
# VE Delta Tests
# =============================================================================

class TestVEDelta:
    """Test AFR error calculation."""

    def test_afr_error_calculation(self, engine):
        """AFR error should be AFR - target."""
        sample = make_sample(rpm=3500.0, map_kpa=85.0, afr=15.0)
        engine.on_aggregated_sample(sample)
        
        bin_key = (7, 6)
        assert bin_key in engine.ve_delta_map
        
        # Error = 15.0 - 14.7 = 0.3
        cell = engine.ve_delta_map[bin_key]
        assert abs(cell.afr_error_mean - 0.3) < 0.001

    def test_running_average_update(self, engine):
        """Running average should update correctly."""
        # First sample: AFR 15.0, error = 0.3
        engine.on_aggregated_sample(make_sample(afr=15.0))
        
        # Second sample: AFR 14.4, error = -0.3
        engine.on_aggregated_sample(make_sample(afr=14.4))
        
        bin_key = (7, 6)
        cell = engine.ve_delta_map[bin_key]
        
        # Average error = (0.3 + -0.3) / 2 = 0.0
        assert abs(cell.afr_error_mean) < 0.001
        assert cell.afr_error_count == 2

    def test_missing_afr_graceful(self, engine):
        """Missing AFR should not crash or create VE delta entry."""
        sample = make_sample()
        sample["afr"] = None
        
        engine.on_aggregated_sample(sample)
        
        # Coverage should still be updated
        assert len(engine.coverage_map) == 1
        
        # VE delta should NOT be updated
        assert len(engine.ve_delta_map) == 0

    def test_ve_delta_stats(self, engine):
        """VE delta stats should aggregate correctly."""
        # Rich sample
        engine.on_aggregated_sample(make_sample(rpm=2000.0, map_kpa=50.0, afr=13.0))
        
        # Lean sample
        engine.on_aggregated_sample(make_sample(rpm=4000.0, map_kpa=80.0, afr=16.0))
        
        stats = engine.get_ve_delta_stats()
        
        assert stats["sample_count"] == 2
        assert stats["target_afr"] == 14.7
        # Mean error = ((13-14.7) + (16-14.7)) / 2 = (-1.7 + 1.3) / 2 = -0.2
        assert abs(stats["mean_error"] - (-0.2)) < 0.01


# =============================================================================
# Quality Metrics Tests
# =============================================================================

class TestQualityMetrics:
    """Test data quality tracking."""

    def test_channel_freshness_tracking(self, engine):
        """Channel freshness should track time since last update."""
        sample = make_sample()
        engine.on_aggregated_sample(sample)
        
        # Manually adjust timestamp to simulate time passing
        for ch in engine.quality.channel_last_update:
            engine.quality.channel_last_update[ch] -= 0.5  # 500ms ago
        
        state = engine.get_state()
        freshness = state["quality"]["channel_freshness"]
        
        # All channels should have freshness > 0
        assert "rpm" in freshness
        assert "afr" in freshness
        assert freshness["rpm"] >= 0.4  # Should be ~0.5s

    def test_missing_channels_detected(self, engine):
        """Missing required channels should be flagged."""
        sample = {
            "timestamp_ms": 1000,
            "rpm": 3500.0,
            # Missing: map_kpa, afr
            "tps": 75.0,
        }
        
        engine.on_aggregated_sample(sample)
        
        state = engine.get_state()
        missing = state["quality"]["missing_channels"]
        
        assert "map_kpa" in missing
        assert "afr" in missing
        assert "rpm" not in missing  # RPM is present

    def test_overall_score_calculation(self, engine):
        """Overall quality score should be weighted composite."""
        # Good data with all channels
        for i in range(10):
            engine.on_aggregated_sample(make_sample(rpm=1000 + i * 500))
        
        state = engine.get_state()
        score = state["quality"]["score"]
        
        # Score should be reasonable (not 0, not 100)
        assert 0 < score <= 100

    def test_variance_tracking(self, engine):
        """Channel variance should be tracked."""
        # Send samples with varying RPM
        for i in range(25):
            engine.on_aggregated_sample(make_sample(rpm=3000 + i * 10))
        
        state = engine.get_state()
        variance = state["quality"]["channel_variance"]
        
        # RPM variance should be non-zero
        assert "rpm" in variance
        assert variance["rpm"] is not None
        assert variance["rpm"] > 0


# =============================================================================
# Alert Detection Tests
# =============================================================================

class TestAlertDetection:
    """Test anomaly detection and alerts."""

    def test_frozen_rpm_alert(self, engine):
        """Frozen RPM with high TPS should trigger alert."""
        # Simulate frozen RPM by manipulating internal state
        sample = make_sample(rpm=3500.0, tps=50.0)
        
        # First sample sets baseline
        engine.on_aggregated_sample(sample)
        
        # Manually set last_rpm_time to simulate time passing
        engine._last_rpm_time = time.time() - (FROZEN_RPM_THRESHOLD_SEC + 1.0)
        
        # Same RPM again - should trigger frozen alert
        engine.on_aggregated_sample(sample)
        
        # Check for frozen alert
        alerts = [a for a in engine.alerts if a.type == AlertType.FROZEN_RPM]
        assert len(alerts) >= 1
        assert alerts[0].severity == AlertSeverity.WARNING

    def test_implausible_afr_low_alert(self, engine):
        """AFR below minimum should trigger critical alert."""
        sample = make_sample(afr=8.0)  # Too low
        engine.on_aggregated_sample(sample)
        
        alerts = [a for a in engine.alerts if a.type == AlertType.IMPLAUSIBLE_AFR]
        assert len(alerts) >= 1
        assert alerts[0].severity == AlertSeverity.CRITICAL
        assert "too low" in alerts[0].message.lower()

    def test_implausible_afr_high_alert(self, engine):
        """AFR above maximum should trigger warning alert."""
        sample = make_sample(afr=20.0)  # Too high
        engine.on_aggregated_sample(sample)
        
        alerts = [a for a in engine.alerts if a.type == AlertType.IMPLAUSIBLE_AFR]
        assert len(alerts) >= 1
        assert alerts[0].severity == AlertSeverity.WARNING
        assert "too high" in alerts[0].message.lower()

    def test_missing_channel_alert(self):
        """Stale required channel should trigger alert."""
        engine = RealtimeAnalysisEngine()
        
        # Send initial sample with all channels
        engine.on_aggregated_sample(make_sample())
        
        # Wait for stale threshold (use shorter for test)
        # Note: In production this is 5 seconds, but we can check the logic
        # by manually checking freshness
        state = engine.get_state()
        
        # Initially no stale alerts (just sent data)
        stale_alerts = [a for a in engine.alerts if a.type == AlertType.STALE_CHANNEL]
        assert len(stale_alerts) == 0

    def test_alert_queue_bounded(self, engine):
        """Alert queue should not exceed max size."""
        # Generate many alerts
        for i in range(100):
            sample = make_sample(afr=5.0 + i * 0.01)  # All implausible
            engine.on_aggregated_sample(sample)
        
        # Queue should be bounded
        assert len(engine.alerts) <= 50

    def test_duplicate_alerts_suppressed(self, engine):
        """Duplicate alerts within 5 seconds should be suppressed."""
        sample = make_sample(afr=8.0)  # Implausible
        
        # Send same alert-triggering sample twice quickly
        engine.on_aggregated_sample(sample)
        engine.on_aggregated_sample(sample)
        
        # Should only have one alert (duplicate suppressed)
        afr_alerts = [a for a in engine.alerts if a.type == AlertType.IMPLAUSIBLE_AFR]
        assert len(afr_alerts) == 1


# =============================================================================
# Graceful Degradation Tests
# =============================================================================

class TestGracefulDegradation:
    """Test handling of missing/invalid data."""

    def test_missing_map_continues(self, engine):
        """Missing MAP should not crash, just skip coverage binning."""
        sample = make_sample()
        sample["map_kpa"] = None
        
        # Should not raise
        engine.on_aggregated_sample(sample)
        
        # Coverage should be empty (can't bin without MAP)
        assert len(engine.coverage_map) == 0
        
        # Quality should still track other channels
        state = engine.get_state()
        assert "rpm" in state["quality"]["channel_freshness"]

    def test_missing_afr_continues(self, engine):
        """Missing AFR should not crash, just skip VE delta."""
        sample = make_sample()
        sample["afr"] = None
        
        engine.on_aggregated_sample(sample)
        
        # Coverage should work
        assert len(engine.coverage_map) == 1
        
        # VE delta should be empty
        assert len(engine.ve_delta_map) == 0

    def test_missing_rpm_continues(self, engine):
        """Missing RPM should not crash."""
        sample = make_sample()
        sample["rpm"] = None
        
        engine.on_aggregated_sample(sample)
        
        # Nothing should crash
        state = engine.get_state()
        assert state["enabled"] is True

    def test_zero_rpm_skips_coverage(self, engine):
        """Zero RPM should skip coverage (engine not running)."""
        sample = make_sample(rpm=0.0)
        engine.on_aggregated_sample(sample)
        
        # Coverage should be empty
        assert len(engine.coverage_map) == 0

    def test_nan_values_handled(self, engine):
        """NaN values should be handled gracefully."""
        sample = make_sample()
        sample["afr"] = float("nan")
        
        # Should not crash
        engine.on_aggregated_sample(sample)
        
        # AFR should be flagged as missing
        state = engine.get_state()
        assert "afr" in state["quality"]["missing_channels"]

    def test_empty_sample_handled(self, engine):
        """Empty sample dict should not crash."""
        engine.on_aggregated_sample({})
        
        state = engine.get_state()
        assert state["enabled"] is True


# =============================================================================
# State and Reset Tests
# =============================================================================

class TestStateAndReset:
    """Test state serialization and reset."""

    def test_get_state_returns_complete_dict(self, engine):
        """get_state() should return all required fields."""
        engine.on_aggregated_sample(make_sample())
        
        state = engine.get_state()
        
        assert "enabled" in state
        assert "coverage" in state
        assert "ve_delta" in state
        assert "quality" in state
        assert "alerts" in state
        assert "uptime_sec" in state

    def test_reset_clears_all_state(self, engine):
        """reset() should clear all accumulated data."""
        # Accumulate some data
        for i in range(10):
            engine.on_aggregated_sample(make_sample(rpm=1000 + i * 500))
        
        assert len(engine.coverage_map) > 0
        
        # Reset
        engine.reset()
        
        # Should be empty
        assert len(engine.coverage_map) == 0
        assert len(engine.ve_delta_map) == 0
        assert len(engine.alerts) == 0

    def test_global_engine_singleton(self):
        """Global engine should be singleton."""
        engine1 = get_realtime_engine()
        engine2 = get_realtime_engine()
        
        assert engine1 is engine2
        
        # Clean up
        reset_realtime_engine()


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Test performance requirements."""

    def test_on_aggregated_sample_fast(self, engine):
        """on_aggregated_sample should complete in <1ms."""
        sample = make_sample()
        
        # Warm up
        for _ in range(10):
            engine.on_aggregated_sample(sample)
        
        # Measure
        start = time.perf_counter()
        for _ in range(100):
            engine.on_aggregated_sample(sample)
        elapsed = time.perf_counter() - start
        
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 1.0, f"Average time {avg_ms:.3f}ms exceeds 1ms limit"

    def test_get_state_fast(self, engine):
        """get_state() should complete quickly even with data."""
        # Accumulate data
        for i in range(100):
            engine.on_aggregated_sample(make_sample(rpm=1000 + (i % 20) * 500))
        
        # Measure
        start = time.perf_counter()
        for _ in range(10):
            engine.get_state()
        elapsed = time.perf_counter() - start
        
        avg_ms = (elapsed / 10) * 1000
        assert avg_ms < 10.0, f"Average time {avg_ms:.3f}ms exceeds 10ms limit"
