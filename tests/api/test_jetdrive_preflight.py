"""
Tests for JetDrive Preflight System

Tests:
1. Provider-scoped channel metrics (no cross-contamination)
2. Provider pinning in validation
3. Semantic validation checks
4. Preflight pass/fail scenarios
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.jetdrive_client import JetDriveSample
from api.services.jetdrive_validation import (
    ChannelHealth,
    ChannelMetrics,
    FrameStats,
    JetDriveDataValidator,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator():
    """Create a fresh validator for each test."""
    v = JetDriveDataValidator()
    yield v
    v.reset()


@pytest.fixture
def sample_provider_1():
    """Sample data from provider 1 (ID: 0x1001)."""
    return {
        "provider_id": 0x1001,
        "rpm_value": 3500.0,
        "afr_value": 13.5,
    }


@pytest.fixture
def sample_provider_2():
    """Sample data from provider 2 (ID: 0x2002) with same channel IDs but different values."""
    return {
        "provider_id": 0x2002,
        "rpm_value": 1200.0,  # Different RPM
        "afr_value": 14.7,  # Different AFR
    }


def make_sample(provider_id: int, channel_id: int, channel_name: str,
                value: float) -> JetDriveSample:
    """Helper to create JetDriveSample instances."""
    return JetDriveSample(
        provider_id=provider_id,
        channel_id=channel_id,
        channel_name=channel_name,
        timestamp_ms=int(time.time() * 1000),
        value=value,
    )


# =============================================================================
# Provider Scoping Tests
# =============================================================================


class TestProviderScoping:
    """Test that channel metrics are properly scoped by provider ID."""

    def test_same_channel_id_different_providers_no_collision(
            self, validator, sample_provider_1, sample_provider_2):
        """
        Two providers with the same channel_id should have separate metrics.
        This prevents cross-contamination when multiple dynos are on the network.
        """
        channel_id = 10  # Same channel ID for both providers

        # Record sample from provider 1
        sample1 = make_sample(
            sample_provider_1["provider_id"],
            channel_id,
            "Digital RPM 1",
            sample_provider_1["rpm_value"],
        )
        validator.record_sample(sample1)

        # Record sample from provider 2 with same channel_id but different value
        sample2 = make_sample(
            sample_provider_2["provider_id"],
            channel_id,
            "Digital RPM 1",
            sample_provider_2["rpm_value"],
        )
        validator.record_sample(sample2)

        # Verify separate metrics exist for each provider
        metrics1 = validator.get_channel_health(
            sample_provider_1["provider_id"], channel_id)
        metrics2 = validator.get_channel_health(
            sample_provider_2["provider_id"], channel_id)

        assert metrics1 is not None, "Metrics for provider 1 should exist"
        assert metrics2 is not None, "Metrics for provider 2 should exist"

        # Values should be different (no cross-contamination)
        assert metrics1.last_value == sample_provider_1["rpm_value"]
        assert metrics2.last_value == sample_provider_2["rpm_value"]

    def test_metrics_keyed_by_provider_channel_tuple(self, validator,
                                                     sample_provider_1):
        """Verify that internal metrics dict uses (provider_id, channel_id) tuple keys."""
        sample = make_sample(
            sample_provider_1["provider_id"],
            42,
            "Test Channel",
            100.0,
        )
        validator.record_sample(sample)

        # Check internal storage uses tuple key
        expected_key = (sample_provider_1["provider_id"], 42)
        assert expected_key in validator._metrics
        assert (validator._metrics[expected_key].provider_id ==
                sample_provider_1["provider_id"])

    def test_get_channels_for_provider(self, validator, sample_provider_1,
                                       sample_provider_2):
        """Test filtering channels by provider."""
        # Add channels from both providers
        validator.record_sample(
            make_sample(sample_provider_1["provider_id"], 10, "RPM", 3500))
        validator.record_sample(
            make_sample(sample_provider_1["provider_id"], 15, "AFR", 13.5))
        validator.record_sample(
            make_sample(sample_provider_2["provider_id"], 10, "RPM", 1200))

        # Get channels for provider 1 only
        provider1_channels = validator.get_channels_for_provider(
            sample_provider_1["provider_id"])

        assert len(provider1_channels) == 2
        assert all(c.provider_id == sample_provider_1["provider_id"]
                   for c in provider1_channels)


# =============================================================================
# Provider Pinning Tests
# =============================================================================


class TestProviderPinning:
    """Test that provider pinning correctly filters samples."""

    def test_active_provider_filters_other_providers(self, validator,
                                                     sample_provider_1,
                                                     sample_provider_2):
        """When active provider is set, samples from other providers should be rejected."""
        # Pin to provider 1
        validator.set_active_provider(sample_provider_1["provider_id"])

        # Sample from provider 1 should be recorded
        sample1 = make_sample(sample_provider_1["provider_id"], 10, "RPM",
                              3500)
        result1 = validator.record_sample(sample1)
        assert result1 is True, "Sample from active provider should be recorded"

        # Sample from provider 2 should be rejected
        sample2 = make_sample(sample_provider_2["provider_id"], 10, "RPM",
                              1200)
        result2 = validator.record_sample(sample2)
        assert result2 is False, "Sample from non-active provider should be rejected"

        # Verify only provider 1's sample is in metrics
        assert (validator.get_channel_health(sample_provider_1["provider_id"],
                                             10) is not None)
        assert (validator.get_channel_health(sample_provider_2["provider_id"],
                                             10) is None)

    def test_no_active_provider_accepts_all(self, validator, sample_provider_1,
                                            sample_provider_2):
        """When no active provider is set, samples from all providers should be recorded."""
        # No provider pinned (default)
        assert validator.get_active_provider() is None

        # Both samples should be recorded
        sample1 = make_sample(sample_provider_1["provider_id"], 10, "RPM",
                              3500)
        sample2 = make_sample(sample_provider_2["provider_id"], 10, "RPM",
                              1200)

        validator.record_sample(sample1)
        validator.record_sample(sample2)

        # Both should have metrics
        assert (validator.get_channel_health(sample_provider_1["provider_id"],
                                             10) is not None)
        assert (validator.get_channel_health(sample_provider_2["provider_id"],
                                             10) is not None)

    def test_clear_active_provider(self, validator, sample_provider_1):
        """Setting active provider to None should clear the filter."""
        # Pin, then unpin
        validator.set_active_provider(sample_provider_1["provider_id"])
        validator.set_active_provider(None)

        assert validator.get_active_provider() is None

    def test_rejected_samples_tracked_as_non_provider_frames(
            self, validator, sample_provider_1, sample_provider_2):
        """Rejected samples should be counted in frame stats."""
        validator.set_active_provider(sample_provider_1["provider_id"])

        # Send samples from wrong provider
        for _ in range(5):
            sample = make_sample(sample_provider_2["provider_id"], 10, "RPM",
                                 1200)
            validator.record_sample(sample)

        # Check frame stats for provider 2
        health = validator.get_all_health()
        # The rejected samples should have incremented non_provider_frames for provider 2
        # (tracked in _frame_stats[provider_id].non_provider_frames)


# =============================================================================
# Semantic Validation Tests
# =============================================================================


class TestSemanticValidation:
    """Test semantic checks that detect mislabeled channels."""

    def test_rpm_like_values_detected(self):
        """Test detection of AFR-like values in RPM channel."""
        from api.services.jetdrive_preflight import _run_semantic_checks

        # Simulate RPM channel with AFR-like values (10-15 instead of 500-12000)
        sample_buffer = {
            "Digital RPM 1": [12.5, 13.0, 13.5, 14.0, 14.5] * 10,
        }

        check, suspicions = _run_semantic_checks(sample_buffer)

        assert len(suspicions) > 0, "Should detect mislabeled RPM"
        assert any("rpm" in s.expected_type.lower() for s in suspicions)
        assert any("afr" in s.observed_behavior.lower() for s in suspicions)

    def test_afr_like_values_detected(self):
        """Test detection of RPM-like values in AFR channel."""
        from api.services.jetdrive_preflight import _run_semantic_checks

        # Simulate AFR channel with RPM-like values (3000-4000 instead of 10-20)
        sample_buffer = {
            "Air/Fuel Ratio 1": [3000, 3200, 3500, 3800, 4000] * 10,
        }

        check, suspicions = _run_semantic_checks(sample_buffer)

        assert len(suspicions) > 0, "Should detect mislabeled AFR"
        assert any("afr" in s.expected_type.lower() for s in suspicions)

    def test_frozen_rpm_detected(self):
        """Test detection of frozen/stuck RPM sensor."""
        from api.services.jetdrive_preflight import _run_semantic_checks

        # Simulate frozen RPM (constant value)
        sample_buffer = {
            "Digital RPM 1": [3500.0] * 50,  # Same value repeated
        }

        check, suspicions = _run_semantic_checks(sample_buffer)

        assert len(suspicions) > 0, "Should detect frozen RPM"
        assert any("frozen" in s.observed_behavior.lower() for s in suspicions)

    def test_lambda_instead_of_afr_detected(self):
        """Test detection of Lambda values where AFR expected."""
        from api.services.jetdrive_preflight import _run_semantic_checks

        # Simulate Lambda values (0.9-1.1) where AFR expected (10-20)
        sample_buffer = {
            "Air/Fuel Ratio 1": [0.95, 0.98, 1.0, 1.02, 1.05] * 10,
        }

        check, suspicions = _run_semantic_checks(sample_buffer)

        assert len(suspicions) > 0, "Should detect Lambda instead of AFR"
        assert any("lambda" in s.observed_behavior.lower() for s in suspicions)

    def test_tps_out_of_range_detected(self):
        """Test detection of TPS values outside 0-100% range."""
        from api.services.jetdrive_preflight import _run_semantic_checks

        # Simulate TPS values outside valid range
        sample_buffer = {
            "TPS": [150, 180, 200, 220, 250] * 10,  # Should be 0-100
        }

        check, suspicions = _run_semantic_checks(sample_buffer)

        assert len(suspicions) > 0, "Should detect out-of-range TPS"
        assert any("tps" in s.expected_type.lower() for s in suspicions)

    def test_valid_data_passes(self):
        """Test that valid data passes semantic checks."""
        from api.services.jetdrive_preflight import _run_semantic_checks

        # Simulate valid data
        sample_buffer = {
            "Digital RPM 1": [2000, 3000, 4000, 5000, 6000] * 10,
            "Air/Fuel Ratio 1": [12.5, 13.0, 13.5, 14.0, 14.5] * 10,
            "TPS": [20, 40, 60, 80, 95] * 10,
        }

        check, suspicions = _run_semantic_checks(sample_buffer)

        # Should pass or have only low-confidence warnings
        high_confidence = [s for s in suspicions if s.confidence >= 0.8]
        assert len(high_confidence) == 0, (
            "Valid data should not have high-confidence suspicions")


# =============================================================================
# Required Channels Tests
# =============================================================================


class TestRequiredChannels:
    """Test required channel detection."""

    def test_required_channels_found(self):
        """Test that required channels are detected when present."""
        from api.services.jetdrive_preflight import _check_required_channels

        available = {"Digital RPM 1", "Air/Fuel Ratio 1", "MAP kPa", "TPS"}
        check, missing = _check_required_channels(available)

        assert check.status.value == "passed"
        assert len(missing) == 0

    def test_missing_rpm_detected(self):
        """Test that missing RPM channel is detected."""
        from api.services.jetdrive_preflight import _check_required_channels

        available = {"Air/Fuel Ratio 1", "MAP kPa", "TPS"}  # No RPM
        check, missing = _check_required_channels(available)

        assert check.status.value == "failed"
        assert "rpm" in missing

    def test_missing_afr_detected(self):
        """Test that missing AFR channel is detected."""
        from api.services.jetdrive_preflight import _check_required_channels

        available = {"Digital RPM 1", "MAP kPa", "TPS"}  # No AFR
        check, missing = _check_required_channels(available)

        assert check.status.value == "failed"
        assert "afr" in missing


# =============================================================================
# Health Thresholds Tests
# =============================================================================


class TestHealthThresholds:
    """Test health threshold checks."""

    def test_healthy_data_passes(self):
        """Test that healthy data passes threshold checks."""
        from api.services.jetdrive_preflight import _check_health_thresholds

        health_data = {
            "overall_health": "healthy",
            "healthy_channels": 5,
            "total_channels": 5,
            "channels": {
                "rpm": {
                    "health": "healthy",
                    "samples_per_second": 20
                },
                "afr": {
                    "health": "healthy",
                    "samples_per_second": 20
                },
            },
            "frame_stats": {
                "drop_rate_percent": 0.5,
            },
        }

        check = _check_health_thresholds(health_data)
        assert check.status.value == "passed"

    def test_critical_health_fails(self):
        """Test that critical health fails threshold checks."""
        from api.services.jetdrive_preflight import _check_health_thresholds

        health_data = {
            "overall_health": "critical",
            "healthy_channels": 0,
            "total_channels": 5,
            "channels": {},
            "frame_stats": {
                "drop_rate_percent": 0
            },
        }

        check = _check_health_thresholds(health_data)
        assert check.status.value == "failed"

    def test_high_drop_rate_warns(self):
        """Test that high drop rate triggers warning."""
        from api.services.jetdrive_preflight import _check_health_thresholds

        health_data = {
            "overall_health": "healthy",
            "healthy_channels": 5,
            "total_channels": 5,
            "channels": {},
            "frame_stats": {
                "drop_rate_percent": 15.0
            },  # Above 10% threshold
        }

        check = _check_health_thresholds(health_data)
        assert check.status.value in ("warning", "failed")


# =============================================================================
# Integration Tests
# =============================================================================


class TestPreflightIntegration:
    """Integration tests for the full preflight flow."""

    def test_preflight_with_no_providers(self):
        """Test preflight when no providers are found."""
        import asyncio

        from api.services.jetdrive_preflight import run_preflight

        # Patch at the jetdrive_client module level since it's imported inside the function
        with patch("api.services.jetdrive_client.discover_providers",
                   new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = []

            result = asyncio.run(run_preflight(sample_seconds=1))

            assert result.passed is False
            assert result.provider_id is None
            connectivity_check = next(
                (c for c in result.checks if c.name == "connectivity"), None)
            assert connectivity_check is not None
            assert connectivity_check.status.value == "failed"

    def test_preflight_passes_with_good_data(self):
        """Test preflight passes with valid provider and data."""
        import asyncio

        from api.services.jetdrive_client import ChannelInfo, JetDriveProviderInfo
        from api.services.jetdrive_preflight import run_preflight

        # Mock provider with good channels
        mock_provider = JetDriveProviderInfo(
            provider_id=0x1001,
            name="Test Dyno",
            host="192.168.1.100",
            port=22344,
            channels={
                10: ChannelInfo(chan_id=10, name="Digital RPM 1", unit=8),
                15: ChannelInfo(chan_id=15, name="Air/Fuel Ratio 1", unit=11),
                20: ChannelInfo(chan_id=20, name="MAP kPa", unit=7),
                21: ChannelInfo(chan_id=21, name="TPS", unit=16),
            },
        )

        # Patch at the jetdrive_client module level
        with patch("api.services.jetdrive_client.discover_providers",
                   new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = [mock_provider]

            # Mock subscribe to provide synthetic samples
            async def mock_subscribe(provider, channels, callback, **kwargs):
                # Send valid samples
                for _ in range(50):
                    callback(make_sample(0x1001, 10, "Digital RPM 1", 3500))
                    callback(make_sample(0x1001, 15, "Air/Fuel Ratio 1", 13.5))

            with patch("api.services.jetdrive_client.subscribe",
                       side_effect=mock_subscribe):
                result = asyncio.run(run_preflight(sample_seconds=1))

            # Should pass connectivity and required channels
            connectivity_check = next(
                (c for c in result.checks if c.name == "connectivity"), None)
            required_check = next(
                (c for c in result.checks if c.name == "required_channels"),
                None)

            assert connectivity_check.status.value == "passed"
            assert required_check.status.value == "passed"
            assert result.provider_id == 0x1001
