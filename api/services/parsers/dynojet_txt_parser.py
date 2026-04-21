"""
Dynojet WinPEP `.txt` export parser.

Dynojet's "Print data to text" feature emits a tab-delimited table that
looks like one of these shapes:

    Time (s)    Speed (mph)    Power (hp)   LC1 AFR   LC2 AFR
    Time (s)    Speed (mph)    Torque       Power     LC1 AFR   LC2 AFR

The column count varies (with or without Torque; with or without headers;
with one or two widebands). We do a tolerant parse: skip comment/blank/
non-numeric lines, take the first 2-6 float columns of each row, and
classify columns by value range as a fallback if the header is missing.

Returns a pandas DataFrame with the columns we can identify, plus a
ParseReport describing what we saw. Used by the ingest sniffer and by
post-patch analysis workflows.
"""

from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

__all__ = [
    "DynojetTxtReport",
    "parse_dynojet_txt",
    "parse_dynojet_txt_path",
    "looks_like_dynojet_txt",
]

_NUMERIC_RE = re.compile(r"^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$")

HEADER_HINTS = {
    "time": "time_s",
    "seconds": "time_s",
    "speed": "mph",
    "mph": "mph",
    "power": "hp",
    "hp": "hp",
    "torque": "torque_ftlb",
    "tq": "torque_ftlb",
    "ft-lbs": "torque_ftlb",
    "ftlbs": "torque_ftlb",
    "nm": "torque_nm",
    "lc1": "lc1_afr",
    "lc2": "lc2_afr",
    "afr": "afr",
    "rpm": "rpm",
}


@dataclass
class DynojetTxtReport:
    """Summary of what we parsed out of a Dynojet TXT export."""

    column_names: list[str] = field(default_factory=list)
    row_count: int = 0
    skipped_lines: int = 0
    has_time: bool = False
    has_mph: bool = False
    has_hp: bool = False
    has_torque: bool = False
    has_afr: bool = False
    peak_hp: Optional[float] = None
    peak_hp_mph: Optional[float] = None
    peak_torque: Optional[float] = None
    mean_lc1_afr: Optional[float] = None
    mean_lc2_afr: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


def looks_like_dynojet_txt(text: str) -> bool:
    """Cheap content-sniff for Dynojet TXT shape.

    We accept anything that contains at least one line of 4+ whitespace-
    separated float columns, optionally preceded by a header line that
    mentions at least one of the Dynojet column keywords.
    """
    text_head = text[:8_000]
    lower = text_head.lower()
    has_keyword = any(
        k in lower
        for k in ("lc1", "lc2", "afr", "mph", "speed", "horsepower", "power (hp)")
    )
    numeric_rows = 0
    for line in text_head.splitlines():
        if not line.strip():
            continue
        toks = line.replace("\t", " ").split()
        if len(toks) < 4:
            continue
        if sum(1 for t in toks if _NUMERIC_RE.match(t)) >= 4:
            numeric_rows += 1
            if numeric_rows >= 3:
                break
    return has_keyword and numeric_rows >= 3


def parse_dynojet_txt_path(path: Path) -> tuple[pd.DataFrame, DynojetTxtReport]:
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_dynojet_txt(raw)


def parse_dynojet_txt(text: str) -> tuple[pd.DataFrame, DynojetTxtReport]:
    """Parse raw Dynojet TXT content.

    Returns a DataFrame and a `DynojetTxtReport`. The DataFrame will have
    columns drawn from (`time_s`, `mph`, `hp`, `torque_ftlb`, `lc1_afr`,
    `lc2_afr`) depending on what's present.
    """
    if not text:
        return pd.DataFrame(), DynojetTxtReport()

    lines = text.splitlines()
    header_cols: Optional[list[str]] = None
    raw_header_line: Optional[str] = None
    data_rows: list[list[float]] = []
    skipped = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            skipped += 1
            continue

        tab_tokens = [t.strip() for t in stripped.split("\t") if t.strip()]
        space_tokens = stripped.split()

        tab_numeric = sum(1 for t in tab_tokens if _NUMERIC_RE.match(t))
        space_numeric = sum(1 for t in space_tokens if _NUMERIC_RE.match(t))

        if tab_numeric >= 2 and tab_numeric == len(tab_tokens):
            data_row_tokens = tab_tokens
        elif space_numeric >= 2 and space_numeric == len(space_tokens):
            data_row_tokens = space_tokens
        else:
            header_candidate_tokens = (
                tab_tokens if len(tab_tokens) >= 2 else space_tokens
            )
            if _maybe_header(header_candidate_tokens):
                if header_cols is None:
                    header_cols = _map_header(header_candidate_tokens)
                raw_header_line = stripped
            else:
                skipped += 1
            continue

        try:
            row = [float(t) for t in data_row_tokens]
        except ValueError:
            skipped += 1
            continue
        data_rows.append(row)

    if not data_rows:
        return pd.DataFrame(), DynojetTxtReport(skipped_lines=skipped)

    widths = [len(r) for r in data_rows]
    try:
        mode_width = max(set(widths), key=widths.count)
    except ValueError:
        mode_width = widths[0]
    data_rows = [r for r in data_rows if len(r) == mode_width]

    rechunked = (
        _chunk_header_to_width(raw_header_line, mode_width) if raw_header_line else None
    )
    if rechunked and len(rechunked) == mode_width:
        cols = rechunked
    elif header_cols and len(header_cols) == mode_width:
        cols = header_cols
    else:
        cols = _infer_columns(mode_width, data_rows)

    df = pd.DataFrame(data_rows, columns=cols)

    report = DynojetTxtReport(
        column_names=cols,
        row_count=len(df),
        skipped_lines=skipped,
        has_time="time_s" in df.columns,
        has_mph="mph" in df.columns,
        has_hp="hp" in df.columns,
        has_torque="torque_ftlb" in df.columns,
        has_afr=any(c in df.columns for c in ("lc1_afr", "lc2_afr", "afr")),
    )

    if "hp" in df.columns:
        idx = df["hp"].idxmax()
        report.peak_hp = float(df["hp"].iloc[idx])
        if "mph" in df.columns:
            report.peak_hp_mph = float(df["mph"].iloc[idx])
    if "torque_ftlb" in df.columns:
        report.peak_torque = float(df["torque_ftlb"].max())
    if "lc1_afr" in df.columns:
        s = df["lc1_afr"]
        clean = s[(s >= 10) & (s <= 20)]
        if len(clean):
            report.mean_lc1_afr = float(clean.mean())
    if "lc2_afr" in df.columns:
        s = df["lc2_afr"]
        clean = s[(s >= 10) & (s <= 20)]
        if len(clean):
            report.mean_lc2_afr = float(clean.mean())

    return df, report


# -----------------------------------------------------------------------------
# Internals
# -----------------------------------------------------------------------------


def _chunk_header_to_width(raw_header: str, width: int) -> Optional[list[str]]:
    """Given an unstructured header line like
        "Time   mph   ft-lbs   hp   LC1 Volts Petrol AFR   LC2 Volts Petrol AFR2"
    split into `width` groups of whitespace-separated tokens by locating
    runs of 2+ spaces. Then map each group to a canonical column name.
    """
    if not raw_header or width <= 0:
        return None
    groups = re.split(r"\s{2,}", raw_header.strip())
    groups = [g.strip() for g in groups if g.strip()]
    if len(groups) < width:
        return None
    if len(groups) > width:
        groups = groups[:width]
    cols: list[str] = []
    seen: set[str] = set()
    lc_counter = 0
    for group in groups:
        g = group.lower()
        canonical: Optional[str] = None
        if "lc1" in g or ("wideband" in g and "1" in g):
            canonical = "lc1_afr"
        elif "lc2" in g or ("wideband" in g and "2" in g) or "afr2" in g:
            canonical = "lc2_afr"
        elif "afr" in g:
            lc_counter += 1
            canonical = "lc1_afr" if lc_counter == 1 else "lc2_afr"
        else:
            for hint, canonical_name in HEADER_HINTS.items():
                if hint in g:
                    canonical = canonical_name
                    break
        if canonical is None:
            canonical = f"col{len(cols)}"
        while canonical in seen:
            canonical += "_x"
        seen.add(canonical)
        cols.append(canonical)
    return cols


def _maybe_header(tokens: list[str]) -> bool:
    if len(tokens) < 2:
        return False
    lowered = [t.lower() for t in tokens]
    hits = sum(1 for t in lowered if any(key in t for key in HEADER_HINTS))
    return hits >= 1


def _map_header(tokens: list[str]) -> list[str]:
    cols: list[str] = []
    seen: set[str] = set()
    lc_counter = 0
    for tok in tokens:
        t = tok.lower().strip("()[]:")
        name: Optional[str] = None
        if "lc1" in t or ("wideband" in t and "1" in t):
            name = "lc1_afr"
        elif "lc2" in t or ("wideband" in t and "2" in t):
            name = "lc2_afr"
        elif "afr" in t:
            lc_counter += 1
            name = "lc1_afr" if lc_counter == 1 else "lc2_afr"
        else:
            for hint, canonical in HEADER_HINTS.items():
                if hint in t:
                    name = canonical
                    break
        if not name:
            name = f"col{len(cols)}"
        while name in seen:
            name += "_x"
        seen.add(name)
        cols.append(name)
    return cols


def _infer_columns(width: int, rows: list[list[float]]) -> list[str]:
    """Fall back when there's no usable header -- classify by value range."""
    df = pd.DataFrame(rows)

    col_names: list[Optional[str]] = [None] * width
    available_labels = [
        "time_s",
        "mph",
        "torque_ftlb",
        "hp",
        "lc1_afr",
        "lc2_afr",
    ]

    def take(label: str, idx: int) -> None:
        col_names[idx] = label
        if label in available_labels:
            available_labels.remove(label)

    def range_match(
        col_idx: int, lo: float, hi: float, mean_lo: float, mean_hi: float
    ) -> bool:
        s = df[col_idx]
        if not len(s):
            return False
        if not ((s >= lo) & (s <= hi)).mean() > 0.7:
            return False
        m = float(s.mean())
        return mean_lo <= m <= mean_hi

    for idx in range(width):
        if col_names[idx] is not None:
            continue
        if "time_s" in available_labels and range_match(idx, 0, 60, 0.5, 30):
            s = df[idx]
            if s.is_monotonic_increasing:
                take("time_s", idx)
                continue

    for idx in range(width):
        if col_names[idx] is not None:
            continue
        if "mph" in available_labels and range_match(idx, 10, 200, 25, 120):
            take("mph", idx)
            continue

    for idx in range(width):
        if col_names[idx] is not None:
            continue
        if "lc1_afr" in available_labels and range_match(idx, 10, 25, 11.5, 16):
            take("lc1_afr", idx)
            continue
        if "lc2_afr" in available_labels and range_match(idx, 10, 25, 11.5, 16):
            take("lc2_afr", idx)
            continue

    for idx in range(width):
        if col_names[idx] is not None:
            continue
        if "hp" in available_labels and range_match(idx, 0, 400, 10, 200):
            take("hp", idx)
            continue

    for idx in range(width):
        if col_names[idx] is not None:
            continue
        if "torque_ftlb" in available_labels and range_match(idx, 0, 500, 10, 250):
            take("torque_ftlb", idx)
            continue

    for idx in range(width):
        if col_names[idx] is None:
            col_names[idx] = f"col{idx}"

    return [c or f"col{i}" for i, c in enumerate(col_names)]
