"""
Data Validation Schemas for JetDrive Data Ingestion

Provides comprehensive validation for all data sources:
- JetDrive (Dynoware RT-150)
- Innovate (DLG-1, LC-2 wideband O2)
- PowerVision (.pvlog files)
- WP8 (WinPEP8 dyno runs)
- CSV data imports

Uses Pydantic for validation with:
- Type checking
- Range validation
- Custom validators
- Automatic data coercion
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Generic, TypeVar

# Use dataclasses for validation since pydantic may not be installed
# This provides a compatible interface without external dependencies


class ValidationError(Exception):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        source: str | None = None,
    ):
        self.message = message
        self.field = field
        self.value = value
        self.source = source
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        parts = [self.message]
        if self.field:
            parts.append(f"field={self.field}")
        if self.value is not None:
            parts.append(f"value={self.value!r}")
        if self.source:
            parts.append(f"source={self.source}")
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "validation_error",
            "message": self.message,
            "field": self.field,
            "value": self.value,
            "source": self.source,
        }


class IngestionError(Exception):
    """Raised when data ingestion fails."""

    def __init__(
        self,
        message: str,
        error_type: str = "ingestion_error",
        source: str | None = None,
        recoverable: bool = True,
        context: dict[str, Any] | None = None,
    ):
        self.message = message
        self.error_type = error_type
        self.source = source
        self.recoverable = recoverable
        self.context = context or {}
        self.timestamp = datetime.now()
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        return f"[{self.error_type}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.error_type,
            "message": self.message,
            "source": self.source,
            "recoverable": self.recoverable,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ValidationResult:
    """Result of data validation."""

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized_data: dict[str, Any] | None = None

    def add_error(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
    ) -> None:
        self.errors.append(ValidationError(message, field, value))
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
            "sanitized_data": self.sanitized_data,
        }


# =============================================================================
# Value Range Definitions
# =============================================================================


@dataclass
class ValueRange:
    """Defines valid range for a sensor value."""

    min_value: float
    max_value: float
    warn_min: float | None = None
    warn_max: float | None = None
    unit: str = ""
    description: str = ""

    def validate(self, value: float) -> tuple[bool, str | None]:
        """Validate value is within range. Returns (is_valid, warning_message)."""
        if math.isnan(value) or math.isinf(value):
            return False, None

        if value < self.min_value or value > self.max_value:
            return False, None

        # Check warning thresholds
        warning = None
        if self.warn_min is not None and value < self.warn_min:
            warning = f"Value {value} below warning threshold {self.warn_min}"
        elif self.warn_max is not None and value > self.warn_max:
            warning = f"Value {value} above warning threshold {self.warn_max}"

        return True, warning


# Standard sensor ranges for motorsport data
SENSOR_RANGES: dict[str, ValueRange] = {
    # Engine parameters
    "rpm": ValueRange(0, 20000, 500, 15000, "RPM", "Engine speed"),
    "rpm_drum": ValueRange(0, 10000, 0, 8000, "RPM", "Drum/wheel speed"),
    "map_kpa": ValueRange(0, 300, 20, 250, "kPa", "Manifold absolute pressure"),
    "map_psi": ValueRange(0, 45, 3, 36, "PSI", "Manifold absolute pressure"),
    "tps": ValueRange(0, 100, None, None, "%", "Throttle position"),
    "iat_f": ValueRange(-40, 300, 32, 200, "°F", "Intake air temperature"),
    "iat_c": ValueRange(-40, 150, 0, 95, "°C", "Intake air temperature"),
    "ect_f": ValueRange(-40, 350, 100, 250, "°F", "Engine coolant temperature"),
    "ect_c": ValueRange(-40, 175, 38, 120, "°C", "Engine coolant temperature"),
    # AFR / Lambda
    "afr": ValueRange(6.0, 35.0, 10.0, 20.0, "AFR", "Air/fuel ratio"),
    "lambda": ValueRange(0.4, 2.4, 0.7, 1.4, "λ", "Lambda (relative AFR)"),
    # Power
    "horsepower": ValueRange(-50, 2000, 0, 1000, "HP", "Engine horsepower"),
    "torque_ftlb": ValueRange(-100, 2000, 0, 800, "ft-lb", "Engine torque"),
    "torque_nm": ValueRange(-135, 2700, 0, 1100, "Nm", "Engine torque"),
    # Force/acceleration
    "force_lbs": ValueRange(-500, 2000, None, None, "lbs", "Force on drum"),
    "acceleration_g": ValueRange(-5, 10, None, None, "g", "Acceleration"),
    # Electrical
    "voltage": ValueRange(0, 20, 11, 15, "V", "Battery/system voltage"),
    "knock": ValueRange(0, 100, None, 30, "", "Knock sensor"),
    # Environmental
    "barometric_inhg": ValueRange(20, 35, 28, 31, "inHg", "Barometric pressure"),
    "humidity": ValueRange(0, 100, None, None, "%", "Relative humidity"),
    "ambient_temp_f": ValueRange(-40, 150, 32, 110, "°F", "Ambient temperature"),
    # Timestamps
    "timestamp_ms": ValueRange(
        0, 3600000, None, None, "ms", "Timestamp in milliseconds"
    ),
}


def get_range_for_channel(channel_name: str) -> ValueRange | None:
    """Get the appropriate value range for a channel name."""
    name_lower = channel_name.lower()

    # Engine speed
    if "rpm" in name_lower:
        if "drum" in name_lower or "digital" in name_lower:
            return SENSOR_RANGES["rpm_drum"]
        return SENSOR_RANGES["rpm"]

    # Manifold pressure
    if "map" in name_lower:
        if "kpa" in name_lower:
            return SENSOR_RANGES["map_kpa"]
        if "psi" in name_lower:
            return SENSOR_RANGES["map_psi"]
        return SENSOR_RANGES["map_kpa"]

    # Throttle
    if "tps" in name_lower or "throttle" in name_lower:
        return SENSOR_RANGES["tps"]

    # AFR
    if "afr" in name_lower or "air/fuel" in name_lower or "fuel" in name_lower:
        return SENSOR_RANGES["afr"]

    if "lambda" in name_lower:
        return SENSOR_RANGES["lambda"]

    # Power
    if "horsepower" in name_lower or name_lower == "hp":
        return SENSOR_RANGES["horsepower"]

    if "torque" in name_lower:
        if "nm" in name_lower:
            return SENSOR_RANGES["torque_nm"]
        return SENSOR_RANGES["torque_ftlb"]

    # Temperature
    if "iat" in name_lower:
        if "c" in name_lower:
            return SENSOR_RANGES["iat_c"]
        return SENSOR_RANGES["iat_f"]

    if "ect" in name_lower or "coolant" in name_lower:
        if "c" in name_lower:
            return SENSOR_RANGES["ect_c"]
        return SENSOR_RANGES["ect_f"]

    # Force
    if "force" in name_lower:
        return SENSOR_RANGES["force_lbs"]

    # Acceleration
    if "accel" in name_lower:
        return SENSOR_RANGES["acceleration_g"]

    # Voltage
    if "volt" in name_lower or "vbatt" in name_lower:
        return SENSOR_RANGES["voltage"]

    return None


# =============================================================================
# Base Data Sample Schema
# =============================================================================


@dataclass
class DataSample:
    """Base class for all data samples."""

    timestamp_ms: int
    source: str
    channel: str
    value: float
    unit: str = ""
    quality: str = "good"  # good, suspect, bad

    # Class variable for tracking validation
    _validation_errors: ClassVar[list[str]] = []

    def validate(self) -> ValidationResult:
        """Validate this sample."""
        result = ValidationResult(is_valid=True)

        # Check timestamp
        if self.timestamp_ms < 0:
            result.add_error(
                "Timestamp cannot be negative", "timestamp_ms", self.timestamp_ms
            )

        # Check value for NaN/Inf
        if math.isnan(self.value):
            result.add_error("Value is NaN", "value", self.value)
        elif math.isinf(self.value):
            result.add_error("Value is infinite", "value", self.value)

        # Check value range for known channels
        value_range = get_range_for_channel(self.channel)
        if value_range:
            is_valid, warning = value_range.validate(self.value)
            if not is_valid:
                result.add_error(
                    f"Value out of range [{value_range.min_value}, {value_range.max_value}]",
                    "value",
                    self.value,
                )
            elif warning:
                result.add_warning(warning)

        return result

    @classmethod
    def from_raw(
        cls,
        timestamp_ms: int,
        source: str,
        channel: str,
        raw_value: Any,
        unit: str = "",
    ) -> "DataSample":
        """Create sample from raw value with coercion and sanitization."""
        # Coerce to float
        try:
            if raw_value is None:
                value = float("nan")
            elif isinstance(raw_value, str):
                # Handle common string formats
                raw_value = raw_value.strip()
                if raw_value.lower() in ("", "nan", "null", "none"):
                    value = float("nan")
                elif raw_value.lower() == "inf":
                    value = float("inf")
                elif raw_value.lower() == "-inf":
                    value = float("-inf")
                else:
                    value = float(raw_value)
            else:
                value = float(raw_value)
        except (ValueError, TypeError):
            value = float("nan")

        return cls(
            timestamp_ms=max(0, int(timestamp_ms)),
            source=source,
            channel=channel,
            value=value,
            unit=unit,
            quality="good" if not math.isnan(value) else "bad",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_ms": self.timestamp_ms,
            "source": self.source,
            "channel": self.channel,
            "value": self.value,
            "unit": self.unit,
            "quality": self.quality,
        }


# =============================================================================
# JetDrive Schemas
# =============================================================================


@dataclass
class JetDriveChannelSchema:
    """Schema for JetDrive channel definition."""

    chan_id: int
    name: str
    unit: int
    vendor: int = 0

    def validate(self) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if self.chan_id < 0 or self.chan_id > 65535:
            result.add_error("Channel ID out of range", "chan_id", self.chan_id)

        if not self.name or len(self.name) > 30:
            result.add_error("Channel name invalid", "name", self.name)

        if self.unit < 0 or self.unit > 255:
            result.add_error("Unit value out of range", "unit", self.unit)

        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "chan_id": self.chan_id,
            "name": self.name,
            "unit": self.unit,
            "vendor": self.vendor,
        }


@dataclass
class JetDriveSampleSchema(DataSample):
    """Schema for JetDrive data sample."""

    provider_id: int = 0
    channel_id: int = 0

    def validate(self) -> ValidationResult:
        result = super().validate()

        if self.provider_id < 0 or self.provider_id > 65535:
            result.add_error(
                "Provider ID out of range", "provider_id", self.provider_id
            )

        if self.channel_id < 0 or self.channel_id > 65535:
            result.add_error("Channel ID out of range", "channel_id", self.channel_id)

        return result

    @classmethod
    def from_jetdrive_sample(cls, sample: Any) -> "JetDriveSampleSchema":
        """Create from JetDriveSample dataclass."""
        return cls(
            timestamp_ms=sample.timestamp_ms,
            source="jetdrive",
            channel=sample.channel_name,
            value=sample.value,
            provider_id=sample.provider_id,
            channel_id=sample.channel_id,
        )


@dataclass
class JetDriveProviderSchema:
    """Schema for JetDrive provider information."""

    provider_id: int
    name: str
    host: str
    port: int
    channels: list[JetDriveChannelSchema] = field(default_factory=list)

    def validate(self) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if self.provider_id < 0 or self.provider_id > 65535:
            result.add_error(
                "Provider ID out of range", "provider_id", self.provider_id
            )

        if not self.name or len(self.name) > 50:
            result.add_error("Provider name invalid", "name", self.name)

        if self.port < 1 or self.port > 65535:
            result.add_error("Port out of range", "port", self.port)

        # Validate channels
        for channel in self.channels:
            ch_result = channel.validate()
            if not ch_result.is_valid:
                result.errors.extend(ch_result.errors)
                result.is_valid = False

        return result

    @classmethod
    def from_provider_info(cls, info: Any) -> "JetDriveProviderSchema":
        """Create from JetDriveProviderInfo dataclass."""
        channels = [
            JetDriveChannelSchema(
                chan_id=ch.chan_id,
                name=ch.name,
                unit=ch.unit,
                vendor=ch.vendor,
            )
            for ch in info.channels.values()
        ]
        return cls(
            provider_id=info.provider_id,
            name=info.name,
            host=info.host,
            port=info.port,
            channels=channels,
        )


# =============================================================================
# Innovate Schemas
# =============================================================================


@dataclass
class InnovateSampleSchema(DataSample):
    """Schema for Innovate AFR sample."""

    afr: float = 0.0
    lambda_value: float | None = None
    sensor_channel: int = 1
    device_type: str = ""

    def validate(self) -> ValidationResult:
        result = super().validate()

        # Validate AFR range (gasoline typically 8-25)
        afr_range = SENSOR_RANGES["afr"]
        is_valid, warning = afr_range.validate(self.afr)
        if not is_valid:
            result.add_error(
                f"AFR out of range [{afr_range.min_value}, {afr_range.max_value}]",
                "afr",
                self.afr,
            )
        elif warning:
            result.add_warning(warning)

        # Validate lambda if provided
        if self.lambda_value is not None:
            lambda_range = SENSOR_RANGES["lambda"]
            is_valid, warning = lambda_range.validate(self.lambda_value)
            if not is_valid:
                result.add_error(
                    f"Lambda out of range [{lambda_range.min_value}, {lambda_range.max_value}]",
                    "lambda_value",
                    self.lambda_value,
                )
            elif warning:
                result.add_warning(warning)

        if self.sensor_channel not in (1, 2):
            result.add_warning(f"Unexpected sensor channel: {self.sensor_channel}")

        return result

    @classmethod
    def from_innovate_sample(cls, sample: Any) -> "InnovateSampleSchema":
        """Create from InnovateSample dataclass."""
        return cls(
            timestamp_ms=int(sample.timestamp * 1000),
            source="innovate",
            channel=f"AFR_{sample.channel}",
            value=sample.afr,
            afr=sample.afr,
            lambda_value=sample.lambda_value,
            sensor_channel=sample.channel,
            device_type=sample.device_type,
        )


# =============================================================================
# Dyno Data Schemas
# =============================================================================


@dataclass
class DynoDataPointSchema:
    """Schema for a single dyno data point."""

    timestamp_ms: int
    rpm: float
    horsepower: float = 0.0
    torque: float = 0.0
    afr: float | None = None
    afr_front: float | None = None
    afr_rear: float | None = None
    map_kpa: float | None = None
    tps: float | None = None
    iat: float | None = None
    ect: float | None = None
    speed_mph: float | None = None
    force_lbs: float | None = None
    acceleration: float | None = None

    def validate(self) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        # Validate timestamp
        if self.timestamp_ms < 0:
            result.add_error(
                "Timestamp cannot be negative", "timestamp_ms", self.timestamp_ms
            )

        # Validate RPM
        rpm_range = SENSOR_RANGES["rpm"]
        is_valid, warning = rpm_range.validate(self.rpm)
        if not is_valid:
            result.add_error(
                f"RPM out of range [{rpm_range.min_value}, {rpm_range.max_value}]",
                "rpm",
                self.rpm,
            )

        # Validate HP if present
        if self.horsepower != 0:
            hp_range = SENSOR_RANGES["horsepower"]
            is_valid, warning = hp_range.validate(self.horsepower)
            if not is_valid:
                result.add_error(
                    f"Horsepower out of range [{hp_range.min_value}, {hp_range.max_value}]",
                    "horsepower",
                    self.horsepower,
                )

        # Validate torque if present
        if self.torque != 0:
            tq_range = SENSOR_RANGES["torque_ftlb"]
            is_valid, warning = tq_range.validate(self.torque)
            if not is_valid:
                result.add_error(
                    f"Torque out of range [{tq_range.min_value}, {tq_range.max_value}]",
                    "torque",
                    self.torque,
                )

        # Validate AFR if present
        if self.afr is not None:
            afr_range = SENSOR_RANGES["afr"]
            is_valid, warning = afr_range.validate(self.afr)
            if not is_valid:
                result.add_error(
                    f"AFR out of range [{afr_range.min_value}, {afr_range.max_value}]",
                    "afr",
                    self.afr,
                )

        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_ms": self.timestamp_ms,
            "rpm": self.rpm,
            "horsepower": self.horsepower,
            "torque": self.torque,
            "afr": self.afr,
            "afr_front": self.afr_front,
            "afr_rear": self.afr_rear,
            "map_kpa": self.map_kpa,
            "tps": self.tps,
            "iat": self.iat,
            "ect": self.ect,
            "speed_mph": self.speed_mph,
            "force_lbs": self.force_lbs,
            "acceleration": self.acceleration,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DynoDataPointSchema":
        """Create from dictionary with flexible column mapping."""
        # Map common column name variations
        timestamp = (
            data.get("timestamp_ms") or data.get("time_ms") or data.get("Time") or 0
        )

        # RPM variations
        rpm = (
            data.get("rpm")
            or data.get("RPM")
            or data.get("Engine RPM")
            or data.get("engine_rpm")
            or 0
        )

        # Power variations
        hp = (
            data.get("horsepower")
            or data.get("Horsepower")
            or data.get("HP")
            or data.get("hp")
            or 0
        )
        tq = (
            data.get("torque")
            or data.get("Torque")
            or data.get("TQ")
            or data.get("torque_ftlb")
            or 0
        )

        # AFR variations
        afr = data.get("afr") or data.get("AFR") or data.get("Air/Fuel Ratio 1")
        afr_front = data.get("afr_front") or data.get("AFR Meas F") or data.get("AFR_F")
        afr_rear = data.get("afr_rear") or data.get("AFR Meas R") or data.get("AFR_R")

        # MAP variations
        map_kpa = data.get("map_kpa") or data.get("MAP_kPa") or data.get("MAP kPa")

        # TPS variations
        tps = data.get("tps") or data.get("TPS") or data.get("Throttle")

        # Temperature variations
        iat = data.get("iat") or data.get("IAT") or data.get("IAT F")
        ect = data.get("ect") or data.get("ECT") or data.get("Engine Temp")

        return cls(
            timestamp_ms=int(timestamp),
            rpm=float(rpm) if rpm else 0.0,
            horsepower=float(hp) if hp else 0.0,
            torque=float(tq) if tq else 0.0,
            afr=float(afr) if afr else None,
            afr_front=float(afr_front) if afr_front else None,
            afr_rear=float(afr_rear) if afr_rear else None,
            map_kpa=float(map_kpa) if map_kpa else None,
            tps=float(tps) if tps else None,
            iat=float(iat) if iat else None,
            ect=float(ect) if ect else None,
            speed_mph=data.get("speed_mph"),
            force_lbs=data.get("force_lbs") or data.get("Force Drum 1"),
            acceleration=data.get("acceleration") or data.get("Acceleration"),
        )


@dataclass
class DynoRunSchema:
    """Schema for a complete dyno run."""

    run_id: str
    source: str
    timestamp: datetime
    data_points: list[DynoDataPointSchema] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Computed/summary fields
    peak_hp: float = 0.0
    hp_peak_rpm: float = 0.0
    peak_torque: float = 0.0
    torque_peak_rpm: float = 0.0
    duration_ms: int = 0
    data_point_count: int = 0

    def validate(self) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if not self.run_id:
            result.add_error("Run ID is required", "run_id")

        if not self.data_points:
            result.add_warning("No data points in run")

        # Validate individual data points (sample for large datasets)
        validation_sample = self.data_points[:100]  # Check first 100
        for i, point in enumerate(validation_sample):
            point_result = point.validate()
            if not point_result.is_valid:
                for error in point_result.errors:
                    error.source = f"data_points[{i}]"
                    result.errors.append(error)
                if len(result.errors) > 10:
                    result.add_warning(
                        f"Validation stopped after 10 errors. "
                        f"{len(self.data_points)} total points."
                    )
                    break

        result.is_valid = len(result.errors) == 0
        return result

    def compute_summary(self) -> None:
        """Compute summary statistics from data points."""
        if not self.data_points:
            return

        self.data_point_count = len(self.data_points)

        # Find peaks
        for point in self.data_points:
            if point.horsepower > self.peak_hp:
                self.peak_hp = point.horsepower
                self.hp_peak_rpm = point.rpm
            if point.torque > self.peak_torque:
                self.peak_torque = point.torque
                self.torque_peak_rpm = point.rpm

        # Compute duration
        if len(self.data_points) >= 2:
            self.duration_ms = (
                self.data_points[-1].timestamp_ms - self.data_points[0].timestamp_ms
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "peak_hp": self.peak_hp,
            "hp_peak_rpm": self.hp_peak_rpm,
            "peak_torque": self.peak_torque,
            "torque_peak_rpm": self.torque_peak_rpm,
            "duration_ms": self.duration_ms,
            "data_point_count": self.data_point_count,
            "metadata": self.metadata,
        }


# =============================================================================
# Utility Functions
# =============================================================================


def sanitize_value(value: Any, expected_type: type = float) -> Any:
    """Sanitize a raw value to expected type with error handling."""
    if value is None:
        return None

    try:
        if expected_type == float:
            if isinstance(value, str):
                value = value.strip()
                if value.lower() in ("", "nan", "null", "none", "-"):
                    return None
            result = float(value)
            if math.isnan(result) or math.isinf(result):
                return None
            return result

        elif expected_type == int:
            return int(float(value))

        elif expected_type == str:
            return str(value).strip()

        elif expected_type == bool:
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "on")
            return bool(value)

        return value
    except (ValueError, TypeError):
        return None


def validate_csv_row(
    row: dict[str, Any],
    required_fields: list[str],
    source: str = "csv",
) -> ValidationResult:
    """Validate a CSV row has required fields."""
    result = ValidationResult(is_valid=True)

    for field in required_fields:
        if field not in row or row[field] is None or row[field] == "":
            result.add_error(f"Missing required field: {field}", field, source=source)

    return result


def batch_validate(
    items: list[Any],
    max_errors: int = 100,
) -> ValidationResult:
    """Validate a batch of items, stopping after max_errors."""
    result = ValidationResult(is_valid=True)
    error_count = 0

    for i, item in enumerate(items):
        if hasattr(item, "validate"):
            item_result = item.validate()
            if not item_result.is_valid:
                for error in item_result.errors:
                    error.source = f"item[{i}]"
                    result.errors.append(error)
                    error_count += 1
                    if error_count >= max_errors:
                        result.add_warning(
                            f"Validation stopped after {max_errors} errors"
                        )
                        result.is_valid = False
                        return result

    result.is_valid = len(result.errors) == 0
    return result
