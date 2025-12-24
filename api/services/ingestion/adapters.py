"""
Data Source Adapters

Provides format conversion and normalization for different data sources:
- JetDrive (UDP multicast)
- Innovate (Serial AFR)
- CSV files
- WP8 files (WinPEP8)
- PowerVision logs

Each adapter converts source-specific data to a common format for processing.
"""

from __future__ import annotations

import csv
import io
import logging
import math
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Iterator, TextIO

from .schemas import (
    DataSample,
    DynoDataPointSchema,
    DynoRunSchema,
    InnovateSampleSchema,
    JetDriveChannelSchema,
    JetDriveProviderSchema,
    JetDriveSampleSchema,
    ValidationError,
    ValidationResult,
    sanitize_value,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Base Adapter
# =============================================================================


class DataAdapter(ABC):
    """Abstract base class for data source adapters."""

    source_name: str = "unknown"

    @abstractmethod
    def can_handle(self, data: Any) -> bool:
        """Check if this adapter can handle the given data."""
        pass

    @abstractmethod
    def convert(self, data: Any) -> DynoDataPointSchema | list[DynoDataPointSchema]:
        """Convert source data to common format."""
        pass

    def convert_batch(
        self, items: list[Any]
    ) -> tuple[list[DynoDataPointSchema], list[ValidationError]]:
        """
        Convert a batch of items with error collection.

        Returns:
            Tuple of (converted items, errors)
        """
        results = []
        errors = []

        for i, item in enumerate(items):
            try:
                converted = self.convert(item)
                if isinstance(converted, list):
                    results.extend(converted)
                else:
                    results.append(converted)
            except Exception as e:
                errors.append(
                    ValidationError(
                        message=str(e),
                        field=f"item[{i}]",
                        source=self.source_name,
                    )
                )

        return results, errors


# =============================================================================
# JetDrive Adapter
# =============================================================================


class JetDriveAdapter(DataAdapter):
    """Adapter for JetDrive UDP multicast data."""

    source_name = "jetdrive"

    # Channel name mappings to standard names
    CHANNEL_MAP = {
        "Engine RPM": "rpm",
        "Digital RPM 1": "rpm",
        "Digital RPM 2": "rpm_2",
        "Horsepower": "horsepower",
        "Torque": "torque",
        "Force Drum 1": "force_lbs",
        "Acceleration": "acceleration",
        "Air/Fuel Ratio 1": "afr",
        "Air/Fuel Ratio 2": "afr_rear",
        "AFR Meas F": "afr_front",
        "AFR Meas R": "afr_rear",
        "MAP kPa": "map_kpa",
        "TPS": "tps",
        "IAT F": "iat",
        "Temperature 1": "temp_1",
        "Temperature 2": "temp_2",
        "Humidity": "humidity",
        "Pressure": "barometric",
    }

    def __init__(self):
        self._channel_values: dict[str, float] = {}
        self._last_timestamp: int = 0

    def can_handle(self, data: Any) -> bool:
        """Check if data is from JetDrive."""
        if hasattr(data, "provider_id") and hasattr(data, "channel_id"):
            return True
        if isinstance(data, dict) and "channel_name" in data:
            return True
        return False

    def convert(self, data: Any) -> DynoDataPointSchema:
        """Convert JetDrive sample to standard format."""
        # Handle JetDriveSample dataclass
        if hasattr(data, "channel_name"):
            channel_name = data.channel_name
            value = data.value
            timestamp = data.timestamp_ms
        elif isinstance(data, dict):
            channel_name = data.get("channel_name", "unknown")
            value = data.get("value", 0)
            timestamp = data.get("timestamp_ms", 0)
        else:
            raise ValueError(f"Cannot convert JetDrive data: {type(data)}")

        # Update channel values
        self._channel_values[channel_name] = value
        self._last_timestamp = max(self._last_timestamp, timestamp)

        # Map to standard name
        standard_name = self.CHANNEL_MAP.get(channel_name, channel_name.lower())

        # Build data point with all collected values
        return DynoDataPointSchema(
            timestamp_ms=self._last_timestamp,
            rpm=self._channel_values.get("Engine RPM", 0)
            or self._channel_values.get("Digital RPM 1", 0),
            horsepower=self._channel_values.get("Horsepower", 0),
            torque=self._channel_values.get("Torque", 0),
            afr=self._channel_values.get("Air/Fuel Ratio 1"),
            afr_front=self._channel_values.get("AFR Meas F"),
            afr_rear=self._channel_values.get("AFR Meas R"),
            map_kpa=self._channel_values.get("MAP kPa"),
            tps=self._channel_values.get("TPS"),
            iat=self._channel_values.get("IAT F"),
            force_lbs=self._channel_values.get("Force Drum 1"),
            acceleration=self._channel_values.get("Acceleration"),
        )

    def reset(self) -> None:
        """Reset accumulated channel values."""
        self._channel_values.clear()
        self._last_timestamp = 0

    def aggregate_samples(
        self, samples: list[Any], time_window_ms: int = 50
    ) -> list[DynoDataPointSchema]:
        """
        Aggregate multiple samples into data points.

        Groups samples by time window and creates one data point per window.
        """
        if not samples:
            return []

        # Sort by timestamp
        sorted_samples = sorted(samples, key=lambda s: s.timestamp_ms)

        results = []
        window_start = sorted_samples[0].timestamp_ms
        window_values: dict[str, float] = {}

        for sample in sorted_samples:
            if sample.timestamp_ms - window_start >= time_window_ms:
                # Create data point for previous window
                if window_values:
                    results.append(
                        DynoDataPointSchema(
                            timestamp_ms=window_start,
                            rpm=window_values.get("rpm", 0),
                            horsepower=window_values.get("horsepower", 0),
                            torque=window_values.get("torque", 0),
                            afr=window_values.get("afr"),
                            afr_front=window_values.get("afr_front"),
                            afr_rear=window_values.get("afr_rear"),
                            map_kpa=window_values.get("map_kpa"),
                            tps=window_values.get("tps"),
                            iat=window_values.get("iat"),
                            force_lbs=window_values.get("force_lbs"),
                            acceleration=window_values.get("acceleration"),
                        )
                    )

                # Start new window
                window_start = sample.timestamp_ms
                window_values.clear()

            # Add to current window
            standard_name = self.CHANNEL_MAP.get(
                sample.channel_name, sample.channel_name.lower()
            )
            window_values[standard_name] = sample.value

        # Don't forget the last window
        if window_values:
            results.append(
                DynoDataPointSchema(
                    timestamp_ms=window_start,
                    rpm=window_values.get("rpm", 0),
                    horsepower=window_values.get("horsepower", 0),
                    torque=window_values.get("torque", 0),
                    afr=window_values.get("afr"),
                    afr_front=window_values.get("afr_front"),
                    afr_rear=window_values.get("afr_rear"),
                    map_kpa=window_values.get("map_kpa"),
                    tps=window_values.get("tps"),
                    iat=window_values.get("iat"),
                    force_lbs=window_values.get("force_lbs"),
                    acceleration=window_values.get("acceleration"),
                )
            )

        return results


# =============================================================================
# Innovate Adapter
# =============================================================================


class InnovateAdapter(DataAdapter):
    """Adapter for Innovate AFR data."""

    source_name = "innovate"

    def can_handle(self, data: Any) -> bool:
        """Check if data is from Innovate device."""
        if hasattr(data, "afr") and hasattr(data, "lambda_value"):
            return True
        if isinstance(data, dict) and "afr" in data:
            return True
        return False

    def convert(self, data: Any) -> DynoDataPointSchema:
        """Convert Innovate sample to standard format."""
        if hasattr(data, "afr"):
            afr = data.afr
            channel = getattr(data, "channel", 1)
            timestamp = int(getattr(data, "timestamp", 0) * 1000)
        elif isinstance(data, dict):
            afr = data.get("afr", 0)
            channel = data.get("channel", 1)
            timestamp = int(data.get("timestamp", 0) * 1000)
        else:
            raise ValueError(f"Cannot convert Innovate data: {type(data)}")

        # Create data point with AFR
        return DynoDataPointSchema(
            timestamp_ms=timestamp,
            rpm=0,  # Innovate doesn't provide RPM
            afr=afr if channel == 1 else None,
            afr_front=afr if channel == 1 else None,
            afr_rear=afr if channel == 2 else None,
        )

    def merge_with_dyno(
        self,
        afr_samples: list[Any],
        dyno_points: list[DynoDataPointSchema],
        time_tolerance_ms: int = 100,
    ) -> list[DynoDataPointSchema]:
        """
        Merge AFR samples with dyno data points.

        Matches AFR samples to nearest dyno point within tolerance.
        """
        if not afr_samples or not dyno_points:
            return dyno_points

        # Sort both by timestamp
        sorted_afr = sorted(
            afr_samples, key=lambda s: getattr(s, "timestamp", 0) * 1000
        )
        sorted_dyno = sorted(dyno_points, key=lambda p: p.timestamp_ms)

        # Match AFR to dyno points
        afr_idx = 0
        for point in sorted_dyno:
            while afr_idx < len(sorted_afr):
                afr_ts = getattr(sorted_afr[afr_idx], "timestamp", 0) * 1000

                # Skip if AFR is too early
                if afr_ts < point.timestamp_ms - time_tolerance_ms:
                    afr_idx += 1
                    continue

                # Check if within tolerance
                if abs(afr_ts - point.timestamp_ms) <= time_tolerance_ms:
                    afr_sample = sorted_afr[afr_idx]
                    channel = getattr(afr_sample, "channel", 1)
                    afr = afr_sample.afr

                    if channel == 1:
                        point.afr = afr
                        point.afr_front = afr
                    else:
                        point.afr_rear = afr

                    afr_idx += 1
                break

        return sorted_dyno


# =============================================================================
# CSV Adapter
# =============================================================================


class CSVAdapter(DataAdapter):
    """Adapter for CSV file data."""

    source_name = "csv"

    # Common column name variations
    COLUMN_ALIASES = {
        "timestamp_ms": ["timestamp_ms", "time_ms", "Time", "time", "timestamp"],
        "rpm": ["rpm", "RPM", "Engine RPM", "engine_rpm", "EngineRPM"],
        "horsepower": ["horsepower", "Horsepower", "HP", "hp", "Power"],
        "torque": ["torque", "Torque", "TQ", "tq", "torque_ftlb"],
        "afr": ["afr", "AFR", "Air/Fuel Ratio 1", "air_fuel"],
        "afr_front": ["afr_front", "AFR Meas F", "AFR_F", "afr_f"],
        "afr_rear": ["afr_rear", "AFR Meas R", "AFR_R", "afr_r"],
        "map_kpa": ["map_kpa", "MAP_kPa", "MAP kPa", "MAP", "map"],
        "tps": ["tps", "TPS", "Throttle", "throttle"],
        "iat": ["iat", "IAT", "IAT F", "intake_air_temp"],
        "ect": ["ect", "ECT", "Engine Temp", "coolant_temp"],
        "speed_mph": ["speed_mph", "Speed", "speed", "mph"],
        "force_lbs": ["force_lbs", "Force Drum 1", "force"],
        "acceleration": ["acceleration", "Acceleration", "accel", "g"],
    }

    def __init__(self):
        self._column_map: dict[str, str] = {}

    def can_handle(self, data: Any) -> bool:
        """Check if data is CSV-compatible."""
        if isinstance(data, (str, Path)):
            path = Path(data)
            return path.suffix.lower() == ".csv"
        if isinstance(data, dict) and any(
            key.lower() in ["rpm", "engine rpm", "horsepower"] for key in data.keys()
        ):
            return True
        return False

    def convert(self, data: Any) -> DynoDataPointSchema:
        """Convert CSV row to standard format."""
        if isinstance(data, dict):
            return DynoDataPointSchema.from_dict(data)
        raise ValueError(f"Cannot convert CSV data: {type(data)}")

    def _detect_columns(self, headers: list[str]) -> dict[str, str]:
        """Detect which columns map to which standard fields."""
        column_map = {}

        for standard_name, aliases in self.COLUMN_ALIASES.items():
            for header in headers:
                header_clean = header.strip()
                if header_clean in aliases or header_clean.lower() in [
                    a.lower() for a in aliases
                ]:
                    column_map[header_clean] = standard_name
                    break

        return column_map

    def parse_file(
        self,
        file_path: str | Path,
        encoding: str = "utf-8",
    ) -> DynoRunSchema:
        """
        Parse a CSV file into a DynoRunSchema.

        Args:
            file_path: Path to CSV file
            encoding: File encoding

        Returns:
            DynoRunSchema with parsed data
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        data_points = []
        errors = []

        with open(path, "r", encoding=encoding, newline="") as f:
            # Detect delimiter
            sample = f.read(4096)
            f.seek(0)

            try:
                dialect = csv.Sniffer().sniff(sample)
            except csv.Error:
                dialect = csv.excel

            reader = csv.DictReader(f, dialect=dialect)

            # Detect column mapping
            if reader.fieldnames:
                self._column_map = self._detect_columns(list(reader.fieldnames))
                logger.debug(f"Detected column mapping: {self._column_map}")

            for i, row in enumerate(reader):
                try:
                    # Map columns to standard names
                    mapped_row = {}
                    for original, standard in self._column_map.items():
                        if original in row:
                            mapped_row[standard] = row[original]

                    # Add unmapped columns
                    for key, value in row.items():
                        if key not in self._column_map:
                            mapped_row[key] = value

                    point = DynoDataPointSchema.from_dict(mapped_row)
                    data_points.append(point)
                except Exception as e:
                    errors.append(f"Row {i + 1}: {e}")
                    if len(errors) > 100:
                        logger.warning("Too many errors, stopping parse")
                        break

        # Create run schema
        run = DynoRunSchema(
            run_id=path.stem,
            source="csv",
            timestamp=datetime.fromtimestamp(path.stat().st_mtime),
            data_points=data_points,
            metadata={
                "file_path": str(path),
                "row_count": len(data_points),
                "parse_errors": len(errors),
                "column_map": self._column_map,
            },
        )

        run.compute_summary()
        return run

    def parse_string(self, csv_content: str) -> list[DynoDataPointSchema]:
        """Parse CSV content from string."""
        data_points = []

        f = io.StringIO(csv_content)
        reader = csv.DictReader(f)

        if reader.fieldnames:
            self._column_map = self._detect_columns(list(reader.fieldnames))

        for row in reader:
            mapped_row = {}
            for original, standard in self._column_map.items():
                if original in row:
                    mapped_row[standard] = row[original]

            point = DynoDataPointSchema.from_dict(mapped_row)
            data_points.append(point)

        return data_points


# =============================================================================
# WP8 Adapter
# =============================================================================


class WP8Adapter(DataAdapter):
    """Adapter for WP8 (WinPEP8) dyno run files."""

    source_name = "wp8"

    WP8_MAGIC = b"\xfe\xce\xfa\xce"

    def can_handle(self, data: Any) -> bool:
        """Check if data is a WP8 file."""
        if isinstance(data, (str, Path)):
            path = Path(data)
            if path.suffix.lower() == ".wp8":
                return True
            # Check magic bytes
            if path.exists():
                with open(path, "rb") as f:
                    magic = f.read(4)
                    return magic == self.WP8_MAGIC
        return False

    def convert(self, data: Any) -> list[DynoDataPointSchema]:
        """Convert WP8 data to standard format."""
        if isinstance(data, (str, Path)):
            return self.parse_file(data)

        raise ValueError(f"Cannot convert WP8 data: {type(data)}")

    def parse_file(self, file_path: str | Path) -> list[DynoDataPointSchema]:
        """
        Parse WP8 file with improved error handling.

        This is a simplified parser - the full WP8 format is complex.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"WP8 file not found: {file_path}")

        with open(path, "rb") as f:
            # Verify magic
            magic = f.read(4)
            if magic != self.WP8_MAGIC:
                raise ValueError(f"Invalid WP8 file - wrong magic: {magic.hex()}")

            content = f.read()

        # Parse channel definitions (simplified)
        channels = self._parse_channels(content)
        logger.debug(f"Found {len(channels)} channels in WP8 file")

        # Parse data (simplified - actual format is complex)
        data_points = self._parse_data(content, channels)

        return data_points

    def _parse_channels(self, content: bytes) -> dict[int, str]:
        """Parse channel definitions from WP8 content."""
        channels = {}
        i = 0

        while i < len(content) - 10:
            # Look for channel definition markers
            if content[i] == 0x0A:
                try:
                    msg_len = content[i + 1]
                    if 5 < msg_len < 200 and i + 2 + msg_len <= len(content):
                        msg_data = content[i + 2: i + 2 + msg_len]
                        channel_info = self._parse_channel_def(msg_data)
                        if channel_info:
                            chan_id, name = channel_info
                            channels[chan_id] = name
                        i += 2 + msg_len
                        continue
                except (IndexError, ValueError):
                    pass
            i += 1

        return channels

    def _parse_channel_def(self, data: bytes) -> tuple[int, str] | None:
        """Parse a single channel definition."""
        try:
            name = ""
            channel_id = 0
            i = 0

            while i < len(data):
                if i >= len(data):
                    break

                tag_byte = data[i]
                field_num = tag_byte >> 3
                wire_type = tag_byte & 0x07
                i += 1

                if wire_type == 2:  # String
                    if i >= len(data):
                        break
                    str_len = data[i]
                    i += 1
                    if i + str_len > len(data):
                        break
                    string_data = data[i: i + str_len].decode(
                        "utf-8", errors="replace"
                    )
                    i += str_len

                    if field_num == 2:
                        name = string_data.strip()

                elif wire_type == 0:  # Varint
                    val = 0
                    shift = 0
                    while i < len(data):
                        b = data[i]
                        i += 1
                        val |= (b & 0x7F) << shift
                        if (b & 0x80) == 0:
                            break
                        shift += 7

                    if field_num == 4:
                        channel_id = val

                elif wire_type == 5:  # 32-bit
                    i += 4
                elif wire_type == 1:  # 64-bit
                    i += 8
                else:
                    break

            if name:
                return (channel_id, name)
        except (IndexError, UnicodeDecodeError):
            pass

        return None

    def _parse_data(
        self, content: bytes, channels: dict[int, str]
    ) -> list[DynoDataPointSchema]:
        """Parse time-series data from WP8 content."""
        # This is a simplified parser - actual WP8 data format varies
        data_points = []

        # For now, return empty list as full parsing requires more format research
        # The actual implementation would need to:
        # 1. Find the data section start
        # 2. Parse the binary data format (typically packed floats)
        # 3. Map values to channels

        logger.warning(
            "WP8 data parsing not fully implemented - returning channel info only"
        )

        return data_points


# =============================================================================
# Factory Functions
# =============================================================================

_adapters: dict[str, DataAdapter] = {}


def get_adapter(source_name: str) -> DataAdapter | None:
    """Get adapter by source name."""
    return _adapters.get(source_name)


def register_adapter(source_name: str, adapter: DataAdapter) -> None:
    """Register an adapter."""
    _adapters[source_name] = adapter


def get_adapter_for_source(data: Any) -> DataAdapter | None:
    """
    Auto-detect and return appropriate adapter for data.

    Tries each registered adapter until one can handle the data.
    """
    # Initialize default adapters
    if not _adapters:
        _adapters["jetdrive"] = JetDriveAdapter()
        _adapters["innovate"] = InnovateAdapter()
        _adapters["csv"] = CSVAdapter()
        _adapters["wp8"] = WP8Adapter()

    for adapter in _adapters.values():
        if adapter.can_handle(data):
            return adapter

    return None


def convert_to_standard(
    data: Any, source_hint: str | None = None
) -> DynoDataPointSchema | list[DynoDataPointSchema] | None:
    """
    Convert data to standard format using auto-detection.

    Args:
        data: Source data
        source_hint: Optional hint about data source

    Returns:
        Converted data or None if no adapter found
    """
    if source_hint:
        adapter = get_adapter(source_hint)
        if adapter and adapter.can_handle(data):
            return adapter.convert(data)

    adapter = get_adapter_for_source(data)
    if adapter:
        return adapter.convert(data)

    return None
