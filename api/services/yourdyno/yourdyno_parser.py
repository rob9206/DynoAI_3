"""
YourDyno file parser + normalization utilities.

Phase 1a focuses on post-run import readiness:
- Parse generic YourDyno CSV exports
- Map flexible header names into DynoAI standard columns
- Provide minimal metadata for UI/route validation
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


def _resolve_path(path: str) -> Path:
    """Resolve file path and ensure it exists."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not p.is_file():
        raise ValueError(f"Expected file path, got directory: {path}")
    return p


@dataclass
class YourDynoRun:
    source_path: str
    raw_data: pd.DataFrame
    normalized_data: pd.DataFrame
    detected_columns: dict[str, str]


def find_yourdyno_run_files(search_dirs: Optional[list[Path]] = None) -> list[Path]:
    """
    Discover likely YourDyno run/export files in common directories.
    """
    if search_dirs is None:
        user_home = Path(os.environ.get("USERPROFILE", "")).expanduser()
        docs = user_home / "Documents"
        search_dirs = [
            docs / "YourDyno",
            docs / "DynoRuns",
            docs / "PowerRuns",
            user_home / "AppData" / "Local" / "YourDyno",
            user_home / "AppData" / "Roaming" / "YourDyno",
            Path("C:/ProgramData/YourDyno"),
        ]

    candidates: list[Path] = []
    seen: set[str] = set()
    patterns = ("*.csv", "*.txt")

    for root in search_dirs:
        if not root.exists() or not root.is_dir():
            continue
        for pattern in patterns:
            for p in root.rglob(pattern):
                key = str(p.resolve())
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(p.resolve())

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates


def parse_yourdyno_csv(csv_path: str) -> pd.DataFrame:
    """
    Parse a YourDyno CSV export with tolerant encoding + delimiter handling.
    """
    path = _resolve_path(csv_path)

    # Try common delimiters/encodings in order. Keep this resilient because
    # exports can vary by locale and app version.
    read_attempts: list[tuple[str, Optional[str]]] = [
        ("utf-8", ","),
        ("utf-8-sig", ","),
        ("cp1252", ","),
        ("latin1", ","),
        ("utf-8", ";"),
        ("utf-8-sig", ";"),
        ("cp1252", ";"),
        ("latin1", ";"),
        # Last resort: let pandas infer delimiter.
        ("utf-8", None),
    ]

    last_error: Exception | None = None
    df: pd.DataFrame | None = None
    for encoding, sep in read_attempts:
        try:
            kwargs = {"encoding": encoding}
            if sep is not None:
                kwargs["sep"] = sep
            else:
                kwargs["sep"] = None
                kwargs["engine"] = "python"
            candidate = pd.read_csv(path, **kwargs)
            if candidate.shape[1] >= 2:
                df = candidate
                break
        except Exception as exc:  # pragma: no cover - best effort parse fallback
            last_error = exc

    if df is None:
        raise ValueError(f"Failed to parse CSV {path}: {last_error}")

    # Normalize obvious blank/unnamed columns.
    drop_cols = [c for c in df.columns if str(c).strip().startswith("Unnamed:")]
    if drop_cols:
        df = df.drop(columns=drop_cols)

    return df


def parse_yourdyno_run(file_path: str) -> YourDynoRun:
    """
    Parse a YourDyno run file and return both raw and normalized DataFrames.

    For now we support CSV. Additional run formats can be layered here later.
    """
    path = _resolve_path(file_path)
    suffix = path.suffix.lower()
    if suffix not in {".csv", ".txt"}:
        raise ValueError(f"Unsupported YourDyno run format: {suffix}")

    raw_df = parse_yourdyno_csv(str(path))
    normalized, detected = yourdyno_to_dynoai_format(raw_df, return_detected=True)
    return YourDynoRun(
        source_path=str(path),
        raw_data=raw_df,
        normalized_data=normalized,
        detected_columns=detected,
    )


def yourdyno_to_dynoai_format(
    df: pd.DataFrame, *, return_detected: bool = False
) -> pd.DataFrame | tuple[pd.DataFrame, dict[str, str]]:
    """
    Map YourDyno columns into DynoAI standard columns used by the analysis pipeline.

    Core targets:
    - Time_ms / Time_s
    - Engine RPM
    - Horsepower / Torque
    - AFR Meas (or AFR Meas F / AFR Meas R)
    - MAP kPa / TPS / IAT F / Engine Temp
    """
    if df.empty:
        out = pd.DataFrame()
        return (out, {}) if return_detected else out

    out = df.copy()
    detected: dict[str, str] = {}

    # Build normalized lookup: "Engine RPM" -> "engine rpm"
    normalized_cols = {c: _norm(c) for c in out.columns}

    # Canonical mappings: target -> candidate patterns (priority order)
    targets: dict[str, list[str]] = {
        "Time_ms": ["time_ms", "time ms", "timestamp_ms", "timestamp", "time"],
        "Time_s": ["time_s", "time sec", "seconds", "elapsed", "elapsed_time"],
        "Engine RPM": ["engine rpm", "rpm", "rpm1", "digital rpm 1"],
        "Roller RPM": ["roller rpm", "wheel rpm", "drum rpm"],
        "Horsepower": ["horsepower", "engine hp", "hp", "power hp", "power"],
        "Torque": ["torque", "engine torque", "tq", "torque ftlb"],
        "AFR Meas": ["afr", "air fuel ratio", "afr meas", "wideband", "wb o2"],
        "AFR Meas F": ["afr front", "afr 1", "air fuel ratio 1", "lambda 1"],
        "AFR Meas R": ["afr rear", "afr 2", "air fuel ratio 2", "lambda 2"],
        "MAP kPa": ["map", "map kpa", "manifold pressure", "manifold abs pressure"],
        "TPS": ["tps", "throttle", "throttle position"],
        "IAT F": ["iat", "intake temp", "intake air temp"],
        "Engine Temp": ["ect", "engine temp", "coolant temp", "cyl temp"],
        "Vehicle Speed": ["speed", "mph", "wheel speed", "roller speed"],
        "Force": ["force", "load", "load cell", "tractive force"],
    }

    for target, patterns in targets.items():
        match = _find_best_match(normalized_cols, patterns)
        if match:
            detected[target] = match
            if target != match:
                out = out.rename(columns={match: target})

    # If time appears to be seconds, generate Time_ms.
    if "Time_ms" not in out.columns and "Time_s" in out.columns:
        out["Time_ms"] = pd.to_numeric(out["Time_s"], errors="coerce") * 1000.0

    # If only Time_ms exists, also provide Time_s.
    if "Time_s" not in out.columns and "Time_ms" in out.columns:
        out["Time_s"] = pd.to_numeric(out["Time_ms"], errors="coerce") / 1000.0

    # Ensure key numeric columns are numeric.
    for col in [
        "Time_ms",
        "Time_s",
        "Engine RPM",
        "Roller RPM",
        "Horsepower",
        "Torque",
        "AFR Meas",
        "AFR Meas F",
        "AFR Meas R",
        "MAP kPa",
        "TPS",
        "IAT F",
        "Engine Temp",
        "Vehicle Speed",
        "Force",
    ]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    # Create an AFR fallback if only cylinder AFRs exist.
    if "AFR Meas" not in out.columns:
        if "AFR Meas F" in out.columns and "AFR Meas R" in out.columns:
            out["AFR Meas"] = (out["AFR Meas F"] + out["AFR Meas R"]) / 2.0
        elif "AFR Meas F" in out.columns:
            out["AFR Meas"] = out["AFR Meas F"]
        elif "AFR Meas R" in out.columns:
            out["AFR Meas"] = out["AFR Meas R"]

    # Strip rows with no RPM and no timing (purely empty rows).
    core_cols = [c for c in ("Engine RPM", "Time_ms", "Time_s") if c in out.columns]
    if core_cols:
        out = out.dropna(subset=core_cols, how="all").reset_index(drop=True)

    return (out, detected) if return_detected else out


def _find_best_match(
    normalized_cols: dict[str, str], patterns: list[str]
) -> str | None:
    # Exact normalized match first
    for pattern in patterns:
        p = _norm(pattern)
        for original, normalized in normalized_cols.items():
            if normalized == p:
                return original

    # Then relaxed contains match
    for pattern in patterns:
        p = _norm(pattern)
        for original, normalized in normalized_cols.items():
            if p and (p in normalized or normalized in p):
                return original

    return None


def _norm(value: str) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[\[\](){}:/\\\-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


__all__ = [
    "YourDynoRun",
    "find_yourdyno_run_files",
    "parse_yourdyno_csv",
    "parse_yourdyno_run",
    "yourdyno_to_dynoai_format",
]
