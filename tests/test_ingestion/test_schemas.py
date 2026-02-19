"""
Tests for data validation schemas.

Tests:
- DataSample validation
- JetDrive schemas
- Innovate schemas
- DynoDataPoint validation
- Value range validation
- Error handling
"""

import math
import sys
from pathlib import Path

import pytest

from api.services.ingestion.schemas import (
    SENSOR_RANGES,
    DataSample,
    DynoDataPointSchema,
    DynoRunSchema,
    InnovateSampleSchema,
    JetDriveChannelSchema,
    JetDriveProviderSchema,
    JetDriveSampleSchema,
    ValidationError,
    ValidationResult,
    ValueRange,
    batch_validate,
    get_range_for_channel,
    sanitize_value,
)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestDataSample:
    """Tests for DataSample base class."""

    @staticmethod
    def test_create_sample():
        """Test creating a basic sample."""
        sample = DataSample(
            timestamp_ms=1000,
            source="test",
            channel="rpm",
            value=3500.0,
            unit="RPM",
        )
        assert sample.timestamp_ms == 1000
        assert sample.value == 3500.0
        assert sample.quality == "good"

    @staticmethod
    def test_validate_valid_sample():
        """Test validation of a valid sample."""
        sample = DataSample(
            timestamp_ms=1000,
            source="test",
            channel="rpm",
            value=3500.0,
        )
        result = sample.validate()
        assert result.is_valid
        assert len(result.errors) == 0

    @staticmethod
    def test_validate_negative_timestamp():
        """Test validation rejects negative timestamp."""
        sample = DataSample(
            timestamp_ms=-100,
            source="test",
            channel="rpm",
            value=3500.0,
        )
        result = sample.validate()
        assert not result.is_valid
        assert any("timestamp" in e.field for e in result.errors)

    @staticmethod
    def test_validate_nan_value():
        """Test validation rejects NaN value."""
        sample = DataSample(
            timestamp_ms=1000,
            source="test",
            channel="rpm",
            value=float("nan"),
        )
        result = sample.validate()
        assert not result.is_valid
        assert any("NaN" in e.message for e in result.errors)

    @staticmethod
    def test_validate_inf_value():
        """Test validation rejects infinite value."""
        sample = DataSample(
            timestamp_ms=1000,
            source="test",
            channel="rpm",
            value=float("inf"),
        )
        result = sample.validate()
        assert not result.is_valid
        assert any("infinite" in e.message for e in result.errors)

    @staticmethod
    def test_validate_out_of_range_rpm():
        """Test validation detects out-of-range RPM."""
        sample = DataSample(
            timestamp_ms=1000,
            source="test",
            channel="rpm",
            value=50000.0,  # Way too high
        )
        result = sample.validate()
        assert not result.is_valid

    @staticmethod
    def test_from_raw_coercion():
        """Test creating sample from raw values with coercion."""
        # String to float
        sample = DataSample.from_raw(
            timestamp_ms=1000,
            source="test",
            channel="rpm",
            raw_value="3500.5",
        )
        assert sample.value == 3500.5
        assert sample.quality == "good"

    @staticmethod
    def test_from_raw_handles_nan_string():
        """Test handling of 'nan' string."""
        sample = DataSample.from_raw(
            timestamp_ms=1000,
            source="test",
            channel="rpm",
            raw_value="nan",
        )
        assert math.isnan(sample.value)
        assert sample.quality == "bad"

    @staticmethod
    def test_from_raw_handles_none():
        """Test handling of None value."""
        sample = DataSample.from_raw(
            timestamp_ms=1000,
            source="test",
            channel="rpm",
            raw_value=None,
        )
        assert math.isnan(sample.value)
        assert sample.quality == "bad"

    @staticmethod
    def test_to_dict():
        """Test conversion to dictionary."""
        sample = DataSample(
            timestamp_ms=1000,
            source="test",
            channel="rpm",
            value=3500.0,
            unit="RPM",
        )
        d = sample.to_dict()
        assert d["timestamp_ms"] == 1000
        assert d["value"] == 3500.0
        assert d["unit"] == "RPM"


class TestValueRange:
    """Tests for ValueRange validation."""

    @staticmethod
    def test_valid_range():
        """Test value within range."""
        range_def = ValueRange(min_value=0, max_value=100)
        is_valid, warning = range_def.validate(50.0)
        assert is_valid
        assert warning is None

    @staticmethod
    def test_below_minimum():
        """Test value below minimum."""
        range_def = ValueRange(min_value=0, max_value=100)
        is_valid, warning = range_def.validate(-10.0)
        assert not is_valid

    @staticmethod
    def test_above_maximum():
        """Test value above maximum."""
        range_def = ValueRange(min_value=0, max_value=100)
        is_valid, warning = range_def.validate(150.0)
        assert not is_valid

    @staticmethod
    def test_warning_thresholds():
        """Test warning thresholds."""
        range_def = ValueRange(min_value=0, max_value=100, warn_min=20, warn_max=80)

        # Valid but below warning threshold
        is_valid, warning = range_def.validate(10.0)
        assert is_valid
        assert warning is not None
        assert "below" in warning

        # Valid but above warning threshold
        is_valid, warning = range_def.validate(90.0)
        assert is_valid
        assert warning is not None
        assert "above" in warning

    @staticmethod
    def test_nan_rejected():
        """Test NaN is rejected."""
        range_def = ValueRange(min_value=0, max_value=100)
        is_valid, _ = range_def.validate(float("nan"))
        assert not is_valid


class TestSensorRanges:
    """Tests for predefined sensor ranges."""

    @staticmethod
    def test_rpm_range():
        """Test RPM range detection."""
        rpm_range = get_range_for_channel("Engine RPM")
        assert rpm_range is not None
        assert rpm_range.max_value == 20000

    @staticmethod
    def test_afr_range():
        """Test AFR range detection."""
        afr_range = get_range_for_channel("AFR")
        assert afr_range is not None
        assert afr_range.min_value == 6.0
        assert afr_range.max_value == 35.0

    @staticmethod
    def test_map_range():
        """Test MAP range detection."""
        map_range = get_range_for_channel("MAP kPa")
        assert map_range is not None
        assert map_range.max_value == 300

    @staticmethod
    def test_horsepower_range():
        """Test horsepower range detection."""
        hp_range = get_range_for_channel("Horsepower")
        assert hp_range is not None
        assert hp_range.max_value == 2000

    @staticmethod
    def test_unknown_channel():
        """Test unknown channel returns None."""
        unknown_range = get_range_for_channel("UnknownChannel123")
        assert unknown_range is None


class TestJetDriveSchemas:
    """Tests for JetDrive-specific schemas."""

    @staticmethod
    def test_channel_schema_valid():
        """Test valid channel schema."""
        channel = JetDriveChannelSchema(
            chan_id=1,
            name="Engine RPM",
            unit=8,
            vendor=1,
        )
        result = channel.validate()
        assert result.is_valid

    @staticmethod
    def test_channel_schema_invalid_id():
        """Test invalid channel ID."""
        channel = JetDriveChannelSchema(
            chan_id=70000,  # Out of range
            name="Test",
            unit=0,
        )
        result = channel.validate()
        assert not result.is_valid

    @staticmethod
    def test_channel_schema_name_too_long():
        """Test name too long."""
        channel = JetDriveChannelSchema(
            chan_id=1,
            name="A" * 50,  # Too long
            unit=0,
        )
        result = channel.validate()
        assert not result.is_valid

    @staticmethod
    def test_sample_schema_valid():
        """Test valid sample schema."""
        sample = JetDriveSampleSchema(
            timestamp_ms=1000,
            source="jetdrive",
            channel="Engine RPM",
            value=3500.0,
            provider_id=100,
            channel_id=1,
        )
        result = sample.validate()
        assert result.is_valid

    @staticmethod
    def test_provider_schema_valid():
        """Test valid provider schema."""
        provider = JetDriveProviderSchema(
            provider_id=100,
            name="Test Provider",
            host="192.168.1.100",
            port=22344,
            channels=[
                JetDriveChannelSchema(chan_id=1, name="RPM", unit=8),
            ],
        )
        result = provider.validate()
        assert result.is_valid


class TestInnovateSampleSchema:
    """Tests for Innovate AFR schemas."""

    @staticmethod
    def test_valid_afr_sample():
        """Test valid AFR sample."""
        sample = InnovateSampleSchema(
            timestamp_ms=1000,
            source="innovate",
            channel="AFR_1",
            value=14.7,
            afr=14.7,
            lambda_value=1.0,
            sensor_channel=1,
        )
        result = sample.validate()
        assert result.is_valid

    @staticmethod
    def test_afr_out_of_range():
        """Test AFR out of range."""
        sample = InnovateSampleSchema(
            timestamp_ms=1000,
            source="innovate",
            channel="AFR_1",
            value=50.0,  # Way too high
            afr=50.0,
        )
        result = sample.validate()
        assert not result.is_valid

    @staticmethod
    def test_lambda_out_of_range():
        """Test lambda out of range."""
        sample = InnovateSampleSchema(
            timestamp_ms=1000,
            source="innovate",
            channel="AFR_1",
            value=14.7,
            afr=14.7,
            lambda_value=5.0,  # Way too high
        )
        result = sample.validate()
        assert not result.is_valid


class TestDynoDataPointSchema:
    """Tests for dyno data point schema."""

    @staticmethod
    def test_valid_data_point():
        """Test valid data point."""
        point = DynoDataPointSchema(
            timestamp_ms=1000,
            rpm=3500,
            horsepower=85,
            torque=90,
            afr=13.5,
        )
        result = point.validate()
        assert result.is_valid

    @staticmethod
    def test_negative_rpm():
        """Test negative RPM validation."""
        point = DynoDataPointSchema(
            timestamp_ms=1000,
            rpm=-100,  # Invalid
        )
        result = point.validate()
        assert not result.is_valid

    @staticmethod
    def test_excessive_horsepower():
        """Test excessive HP validation."""
        point = DynoDataPointSchema(
            timestamp_ms=1000,
            rpm=3500,
            horsepower=5000,  # Way too high
        )
        result = point.validate()
        assert not result.is_valid

    @staticmethod
    def test_from_dict_mapping():
        """Test creating from dict with column mapping."""
        data = {
            "timestamp_ms": 1000,
            "Engine RPM": 3500,
            "Horsepower": 85,
            "Torque": 90,
            "AFR": 13.5,
        }
        point = DynoDataPointSchema.from_dict(data)
        assert point.rpm == 3500
        assert point.horsepower == 85
        assert point.afr == 13.5

    @staticmethod
    def test_to_dict():
        """Test conversion to dict."""
        point = DynoDataPointSchema(
            timestamp_ms=1000,
            rpm=3500,
            horsepower=85,
        )
        d = point.to_dict()
        assert d["timestamp_ms"] == 1000
        assert d["rpm"] == 3500
        assert d["horsepower"] == 85


class TestDynoRunSchema:
    """Tests for complete dyno run schema."""

    @staticmethod
    def test_valid_run():
        """Test valid run schema."""
        points = [
            DynoDataPointSchema(timestamp_ms=i * 50, rpm=2000 + i * 10, horsepower=i)
            for i in range(100)
        ]
        run = DynoRunSchema(
            run_id="test_run",
            source="test",
            timestamp=pytest.importorskip("datetime").datetime.now(),
            data_points=points,
        )
        result = run.validate()
        assert result.is_valid

    @staticmethod
    def test_empty_run_warning():
        """Test empty run produces warning."""
        run = DynoRunSchema(
            run_id="test_run",
            source="test",
            timestamp=pytest.importorskip("datetime").datetime.now(),
            data_points=[],
        )
        result = run.validate()
        assert result.is_valid  # Empty is valid but warning
        assert len(result.warnings) > 0

    @staticmethod
    def test_compute_summary():
        """Test summary computation."""
        points = [
            DynoDataPointSchema(
                timestamp_ms=i * 50, rpm=2000 + i * 10, horsepower=50 + i, torque=80 + i
            )
            for i in range(100)
        ]
        run = DynoRunSchema(
            run_id="test_run",
            source="test",
            timestamp=pytest.importorskip("datetime").datetime.now(),
            data_points=points,
        )
        run.compute_summary()

        assert run.peak_hp == 149
        assert run.peak_torque == 179
        assert run.data_point_count == 100


class TestValidationError:
    """Tests for ValidationError class."""

    @staticmethod
    def test_error_formatting():
        """Test error message formatting."""
        error = ValidationError(
            message="Value out of range",
            field="rpm",
            value=50000,
            source="jetdrive",
        )
        msg = str(error)
        assert "Value out of range" in msg
        assert "rpm" in msg
        assert "50000" in msg

    @staticmethod
    def test_error_to_dict():
        """Test error conversion to dict."""
        error = ValidationError(
            message="Test error",
            field="test_field",
            value=123,
        )
        d = error.to_dict()
        assert d["message"] == "Test error"
        assert d["field"] == "test_field"


class TestSanitizeValue:
    """Tests for value sanitization."""

    @staticmethod
    def test_sanitize_float():
        """Test float sanitization."""
        assert sanitize_value(3.14, float) == 3.14
        assert sanitize_value("3.14", float) == 3.14
        assert sanitize_value(3, float) == 3.0

    @staticmethod
    def test_sanitize_int():
        """Test int sanitization."""
        assert sanitize_value(3, int) == 3
        assert sanitize_value(3.7, int) == 3
        assert sanitize_value("5", int) == 5

    @staticmethod
    def test_sanitize_handles_nan():
        """Test NaN handling."""
        assert sanitize_value(float("nan"), float) is None
        assert sanitize_value("nan", float) is None

    @staticmethod
    def test_sanitize_handles_none():
        """Test None handling."""
        assert sanitize_value(None, float) is None
        assert sanitize_value(None, int) is None


class TestBatchValidate:
    """Tests for batch validation."""

    @staticmethod
    def test_batch_validate_all_valid():
        """Test batch validation with all valid items."""
        items = [
            DataSample(timestamp_ms=i, source="test", channel="rpm", value=3000.0)
            for i in range(10)
        ]
        result = batch_validate(items)
        assert result.is_valid
        assert len(result.errors) == 0

    @staticmethod
    def test_batch_validate_some_invalid():
        """Test batch validation with some invalid items."""
        items = [
            DataSample(timestamp_ms=1, source="test", channel="rpm", value=3000.0),
            DataSample(
                timestamp_ms=-1, source="test", channel="rpm", value=3000.0
            ),  # Invalid timestamp
            DataSample(
                timestamp_ms=2, source="test", channel="rpm", value=float("nan")
            ),  # Invalid value (NaN + range)
        ]
        result = batch_validate(items)
        assert not result.is_valid
        # Note: NaN triggers both "NaN" and "out of range" errors, so 3 total
        assert len(result.errors) >= 2

    @staticmethod
    def test_batch_validate_max_errors():
        """Test batch validation stops at max errors."""
        items = [
            DataSample(timestamp_ms=-i, source="test", channel="rpm", value=3000.0)
            for i in range(1, 200)  # All invalid
        ]
        result = batch_validate(items, max_errors=10)
        assert len(result.errors) == 10
        assert len(result.warnings) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
