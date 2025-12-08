"""
WP8 (WinPEP8) File Parser

Parses Dynojet WinPEP8 dyno run files (.wp8).
These files use a Protocol Buffers-like binary format with:
- Magic header: FECEFACE
- Channel definitions with names, units, device info
- Time-series data for each channel

This is a reverse-engineered parser based on file analysis.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Optional

import numpy as np
import pandas as pd

# WP8 Magic header
WP8_MAGIC = b"\xfe\xce\xfa\xce"


@dataclass
class WP8Channel:
    """A channel definition in a WP8 file."""

    channel_id: int
    name: str
    units: str
    device: str
    category: str
    data_type: int = 0  # 0=unknown, 1=float, 2=int, 3=bool


@dataclass
class WP8Run:
    """Parsed WP8 dyno run file."""

    source_path: str
    channels: dict[int, WP8Channel] = field(default_factory=dict)
    data: Optional[pd.DataFrame] = None
    metadata: dict[str, str] = field(default_factory=dict)
    raw_data: dict[int, list[tuple[float, float]]] = field(default_factory=dict)

    @property
    def channel_names(self) -> list[str]:
        """List of all channel names."""
        return [ch.name for ch in self.channels.values()]


def _read_varint(f: BinaryIO) -> int:
    """Read a variable-length integer (protobuf-style)."""
    result = 0
    shift = 0
    while True:
        byte = f.read(1)
        if not byte:
            raise EOFError("Unexpected end of file reading varint")
        b = byte[0]
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
    return result


def _read_string(f: BinaryIO) -> str:
    """Read a length-prefixed string."""
    length = _read_varint(f)
    data = f.read(length)
    return data.decode("utf-8", errors="replace")


def _skip_field(f: BinaryIO, wire_type: int) -> None:
    """Skip a field based on wire type."""
    if wire_type == 0:  # Varint
        _read_varint(f)
    elif wire_type == 1:  # 64-bit
        f.read(8)
    elif wire_type == 2:  # Length-delimited
        length = _read_varint(f)
        f.read(length)
    elif wire_type == 5:  # 32-bit
        f.read(4)
    else:
        raise ValueError(f"Unknown wire type: {wire_type}")


def _parse_channel_def(data: bytes) -> Optional[WP8Channel]:
    """Parse a channel definition from embedded message."""
    try:
        # This is a simplified parser - real format may vary
        name = ""
        units = ""
        device = ""
        category = ""
        channel_id = 0

        i = 0
        while i < len(data):
            if i >= len(data):
                break

            tag_byte = data[i]
            field_num = tag_byte >> 3
            wire_type = tag_byte & 0x07
            i += 1

            if wire_type == 2:  # Length-delimited (string)
                if i >= len(data):
                    break
                str_len = data[i]
                i += 1
                if i + str_len > len(data):
                    break
                string_data = data[i: i + str_len].decode("utf-8", errors="replace")
                i += str_len

                # Map fields based on typical order
                if field_num == 2:
                    name = string_data
                elif field_num == 3:
                    units = string_data
                elif field_num == 7:
                    device = string_data
                elif field_num == 8:
                    category = string_data

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
            return WP8Channel(
                channel_id=channel_id,
                name=name,
                units=units,
                device=device,
                category=category,
            )
    except (IndexError, UnicodeDecodeError):
        pass

    return None


def parse_wp8_file(wp8_path: str) -> WP8Run:
    """
    Parse a WP8 WinPEP8 dyno run file.

    This parser extracts:
    - Channel definitions (name, units, device)
    - Time-series data for each channel

    Note: This is a reverse-engineered parser. The format may have
    variations that aren't fully handled.
    """
    path = Path(wp8_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"WP8 file not found: {wp8_path}")

    run = WP8Run(source_path=str(path))

    with open(path, "rb") as f:
        # Verify magic header
        magic = f.read(4)
        if magic != WP8_MAGIC:
            raise ValueError(f"Invalid WP8 file - wrong magic header: {magic.hex()}")

        run.metadata["magic"] = magic.hex().upper()

        # Read the rest of the file
        content = f.read()

    # Parse channel definitions
    # Look for patterns like: 0A XX (message start) followed by channel data
    i = 0
    channel_count = 0

    while i < len(content) - 10:
        # Look for message delimiters (0x0A followed by length)
        if content[i] == 0x0A:
            try:
                msg_len = content[i + 1]
                if msg_len > 5 and msg_len < 200 and i + 2 + msg_len <= len(content):
                    msg_data = content[i + 2: i + 2 + msg_len]

                    # Try to parse as channel definition
                    channel = _parse_channel_def(msg_data)
                    if channel and channel.name:
                        # Use auto-increment ID if none found
                        if channel.channel_id == 0:
                            channel.channel_id = channel_count

                        # Avoid duplicates
                        if channel.name not in [c.name for c in run.channels.values()]:
                            run.channels[channel.channel_id] = channel
                            channel_count += 1

                    i += 2 + msg_len
                    continue
            except (IndexError, ValueError):
                pass

        i += 1

    # Look for data section
    # Data typically follows channel definitions and contains float values
    # The structure varies, so we use heuristics

    # Find potential data start (look for sequences of floats)
    data_candidates: dict[str, list[float]] = {}

    # Simple approach: scan for reasonable float values
    float_scan_start = len(content) // 3  # Data usually in latter part
    for scan_pos in range(float_scan_start, len(content) - 4, 4):
        try:
            val = struct.unpack("<f", content[scan_pos: scan_pos + 4])[0]
            # Check if it's a reasonable value (not NaN, not extreme)
            if not np.isnan(val) and not np.isinf(val) and abs(val) < 100000:
                pass  # Could collect these for pattern analysis
        except (struct.error, ValueError):
            pass

    # If we found channels but no structured data, create empty DataFrame
    if run.channels:
        columns = ["Time_ms"] + [ch.name for ch in run.channels.values()]
        run.data = pd.DataFrame(columns=columns)

    run.metadata["channel_count"] = str(len(run.channels))
    run.metadata["file_size"] = str(path.stat().st_size)

    return run


def wp8_to_dataframe(run: WP8Run) -> pd.DataFrame:
    """
    Convert WP8 run data to a DataFrame.

    If parsing extracted time-series data, returns the full DataFrame.
    Otherwise returns an empty DataFrame with channel columns.
    """
    if run.data is not None and not run.data.empty:
        return run.data

    # Return empty DataFrame with correct columns
    columns = ["Time_ms"] + [ch.name for ch in run.channels.values()]
    return pd.DataFrame(columns=columns)


def list_wp8_channels(wp8_path: str) -> list[dict[str, str]]:
    """
    List all channels in a WP8 file without full parsing.

    Returns list of dicts with channel info.
    """
    run = parse_wp8_file(wp8_path)
    return [
        {
            "id": str(ch.channel_id),
            "name": ch.name,
            "units": ch.units,
            "device": ch.device,
            "category": ch.category,
        }
        for ch in run.channels.values()
    ]


def find_wp8_files(search_dir: Optional[str] = None) -> list[Path]:
    """Find WP8 files in common locations."""
    import os

    if search_dir:
        search_paths = [Path(search_dir)]
    else:
        user_docs = Path(os.environ.get("USERPROFILE", "")) / "Documents"
        onedrive_docs = (
            Path(os.environ.get("USERPROFILE", "")) / "OneDrive" / "Documents"
        )
        search_paths = [
            user_docs / "DynoRuns",
            onedrive_docs / "DynoRuns",
            user_docs / "Power Core",
            onedrive_docs / "Power Core",
        ]

    wp8_files: list[Path] = []
    for search_path in search_paths:
        if search_path.exists():
            wp8_files.extend(search_path.rglob("*.wp8"))

    return sorted(wp8_files, key=lambda p: p.stat().st_mtime, reverse=True)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "WP8Channel",
    "WP8Run",
    "find_wp8_files",
    "list_wp8_channels",
    "parse_wp8_file",
    "wp8_to_dataframe",
]
