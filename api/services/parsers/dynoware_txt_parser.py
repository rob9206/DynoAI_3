"""
DynoWare channel-log TXT parser.

This parser handles the wide CSV exports produced by DynoWare/Power Vision
logging where each row is a sampled timestamp and each column is a channel.

Typical files look like:

    Time, (PV) Engine Speed, (PV) Battery Voltage, ...
    0.20, 0, 11.2, ...
    0.25, 0, 11.2, ...

The parser prefers `(PV) ...` channels and falls back to `(Harley ...) ...`
when PV columns are missing.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Optional

import pandas as pd

__all__ = [
    "DynowareTxtReport",
    "looks_like_dynoware_txt",
    "parse_dynoware_txt",
    "parse_dynoware_txt_path",
]

_PV_HINTS = (
    "(pv) engine speed",
    "(pv) battery voltage",
    "(pv) manifold absolute pressure",
)

_CHANNEL_SUFFIXES: dict[str, str] = {
    "rpm": "engine speed",
    "vbatt": "battery voltage",
    "map_kpa": "manifold absolute pressure",
    "ect": "engine temperature",
    "iat": "intake air temperature",
    "iac": "idle air control motor position",
    "idle_set_rpm": "idle set speed",
    "inj_pw_f": "injector time front",
    "inj_pw_r": "injector time rear",
    "spark_f": "spark advance front",
    "spark_r": "spark advance rear",
    "knock_f": "front spark knock retard",
    "knock_r": "rear spark knock retard",
    "tps": "throttle position",
    "afr_cmd": "desired air/fuel",
    "warm_up_afr": "warm-up fuel afr (ratio)",
    "accel_enr": "accel enrichment",
    "afr_meas_f": "wbo2 afr front",
    "afr_meas_r": "wbo2 afr rear",
}

_CANONICAL_ORDER = [
    "time_s",
    "rpm",
    "vbatt",
    "map_kpa",
    "ect",
    "iat",
    "iac",
    "idle_set_rpm",
    "inj_pw_f",
    "inj_pw_r",
    "spark_f",
    "spark_r",
    "knock_f",
    "knock_r",
    "tps",
    "afr_cmd",
    "warm_up_afr",
    "accel_enr",
    "afr_meas_f",
    "afr_meas_r",
]


@dataclass
class DynowareTxtReport:
    """Summary of what we parsed out of a DynoWare TXT export."""

    column_names: list[str] = field(default_factory=list)
    row_count: int = 0
    skipped_lines: int = 0
    sample_rate_hz: Optional[float] = None
    duration_s: Optional[float] = None
    has_rpm: bool = False
    has_vbatt: bool = False
    has_map: bool = False
    has_iac: bool = False
    has_inj_pw: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def looks_like_dynoware_txt(text: str) -> bool:
    """Cheap content sniff for DynoWare channel-log CSV shape."""
    if not text:
        return False

    lines = text[:16_000].splitlines()
    for line in lines[:12]:
        stripped = line.strip()
        if not stripped or "," not in stripped:
            continue

        normalized = _normalize_header_name(stripped)
        if not normalized.startswith("time,"):
            continue

        if any(hint in normalized for hint in _PV_HINTS):
            return True

    return False


def parse_dynoware_txt_path(path: Path) -> tuple[pd.DataFrame, DynowareTxtReport]:
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_dynoware_txt(raw)


def parse_dynoware_txt(text: str) -> tuple[pd.DataFrame, DynowareTxtReport]:
    """Parse raw DynoWare channel-log TXT content."""
    if not text:
        return pd.DataFrame(), DynowareTxtReport()

    lines = text.splitlines()
    header_idx = _locate_header_index(lines)
    if header_idx is None:
        skipped = sum(1 for line in lines if line.strip())
        return pd.DataFrame(), DynowareTxtReport(skipped_lines=skipped)

    reader = csv.reader(lines[header_idx:], skipinitialspace=True)
    try:
        raw_header = next(reader)
    except StopIteration:
        return pd.DataFrame(), DynowareTxtReport(skipped_lines=header_idx)

    headers = [_normalize_header_name(h) for h in raw_header]
    while headers and not headers[-1]:
        headers.pop()

    if not headers:
        return pd.DataFrame(), DynowareTxtReport(skipped_lines=header_idx + 1)

    time_index = _find_time_index(headers)
    if time_index is None:
        skipped = sum(1 for line in lines if line.strip())
        return pd.DataFrame(), DynowareTxtReport(skipped_lines=skipped)

    resolved = _resolve_channel_indices(headers)
    column_names = [
        column for column in _CANONICAL_ORDER if column == "time_s" or column in resolved
    ]

    rows: list[dict[str, float | None]] = []
    skipped_lines = header_idx

    for row in reader:
        if not row or not any(cell.strip() for cell in row):
            skipped_lines += 1
            continue

        if len(row) < len(headers):
            row = row + [""] * (len(headers) - len(row))
        elif len(row) > len(headers):
            row = row[: len(headers)]

        time_s = _to_float(row[time_index])
        if time_s is None:
            skipped_lines += 1
            continue

        record: dict[str, float | None] = {"time_s": time_s}
        for canonical, idx in resolved.items():
            record[canonical] = _to_float(row[idx]) if idx < len(row) else None
        rows.append(record)

    if not rows:
        empty = pd.DataFrame(columns=column_names)
        report = _build_report(empty, column_names, skipped_lines)
        return empty, report

    df = pd.DataFrame(rows)
    df = df.reindex(columns=column_names)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    report = _build_report(df, column_names, skipped_lines)
    return df, report


def _locate_header_index(lines: list[str]) -> Optional[int]:
    """Find the first CSV header row that looks like a DynoWare channel header."""
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or "," not in stripped:
            continue

        normalized = _normalize_header_name(stripped)
        if not normalized.startswith("time,"):
            continue

        has_pv_signal = any(hint in normalized for hint in _PV_HINTS)
        has_harley_signal = "(harley" in normalized and "engine speed" in normalized
        if has_pv_signal or has_harley_signal:
            return idx

    return None


def _resolve_channel_indices(headers: list[str]) -> dict[str, int]:
    resolved: dict[str, int] = {}
    for canonical, suffix in _CHANNEL_SUFFIXES.items():
        idx = _find_channel_index(headers, suffix)
        if idx is not None:
            resolved[canonical] = idx
    return resolved


def _find_time_index(headers: list[str]) -> Optional[int]:
    for idx, header in enumerate(headers):
        if header == "time":
            return idx
    return None


def _find_channel_index(headers: list[str], suffix: str) -> Optional[int]:
    # Prefer Power Vision namespace channels.
    for idx, header in enumerate(headers):
        if header.startswith("(pv)") and header.endswith(suffix):
            return idx

    # Fall back to Harley namespace channels.
    for idx, header in enumerate(headers):
        if header.startswith("(harley") and header.endswith(suffix):
            return idx

    # Final fallback if no namespace wrapper exists.
    for idx, header in enumerate(headers):
        if header == suffix:
            return idx

    return None


def _build_report(
    df: pd.DataFrame,
    column_names: list[str],
    skipped_lines: int,
) -> DynowareTxtReport:
    sample_rate_hz = _compute_sample_rate(df)
    duration_s = _compute_duration(df)
    return DynowareTxtReport(
        column_names=column_names,
        row_count=len(df),
        skipped_lines=skipped_lines,
        sample_rate_hz=sample_rate_hz,
        duration_s=duration_s,
        has_rpm="rpm" in df.columns,
        has_vbatt="vbatt" in df.columns,
        has_map="map_kpa" in df.columns,
        has_iac="iac" in df.columns,
        has_inj_pw=("inj_pw_f" in df.columns or "inj_pw_r" in df.columns),
    )


def _compute_sample_rate(df: pd.DataFrame) -> Optional[float]:
    if "time_s" not in df.columns or len(df) < 2:
        return None

    diffs = df["time_s"].diff().dropna()
    valid = diffs[diffs > 0]
    if valid.empty:
        return None

    step = float(median(valid.tolist()))
    if step <= 0:
        return None

    return 1.0 / step


def _compute_duration(df: pd.DataFrame) -> Optional[float]:
    if "time_s" not in df.columns or df.empty:
        return None

    first = pd.to_numeric(df["time_s"].iloc[0], errors="coerce")
    last = pd.to_numeric(df["time_s"].iloc[-1], errors="coerce")
    if pd.isna(first) or pd.isna(last):
        return None

    return float(last - first)


def _normalize_header_name(value: str) -> str:
    return " ".join(value.strip().split()).lower()


def _to_float(value: str) -> Optional[float]:
    raw = value.strip()
    if not raw:
        return None

    try:
        return float(raw)
    except ValueError:
        return None
