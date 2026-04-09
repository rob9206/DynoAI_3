"""
MasterTune cleartext header parser.

MasterTune calibration files are encrypted, but the file header includes
cleartext metadata that can be used to build a hardware catalog.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from dynoai_v3.template_library import HardwareConfig

_HEADER_SCAN_BYTES = 1024
_MAGIC_PREFIX = "TTS Encrypted File v"
_TEXT_REGEX = re.compile(r"[ -~]{2,}")
_DISP_CI_REGEX = re.compile(r"\b(\d{2,3}(?:\.\d+)?)\s*(?:ci|cid|cubic inches?)\b", re.I)
_DISP_FROM_APP_REGEX = re.compile(r"\b(\d{2,3}(?:\.\d+)?)\s+(?:air|oil|water)\s+cooled\b", re.I)
_DISP_CC_REGEX = re.compile(r"\b(\d{3,4}(?:\.\d+)?)\s*cc\b", re.I)
_CAL_PN_REGEX = re.compile(r"^([A-Z0-9]{3,}-\d{2})", re.I)

_FOLDER_ENGINE_FAMILY = {
    "bigtwin": "twin_cam",
    "milwaukee-eight": "m8",
    "milwaukee-eight-helix": "m8_vvt",
    "xl": "sportster",
    "v-rod": "v_rod",
    "street": "street",
}


@dataclass
class ParsedGrid:
    row_bins: List[float]
    col_bins: List[float]
    values: List[List[float]]

    def shape(self) -> Tuple[int, int]:
        return (len(self.row_bins), len(self.col_bins))


@dataclass
class MasterTuneHeader:
    file_path: str
    file_name: str
    format_version: str
    cal_pn: str
    application: str
    configuration: str
    components: List[str]
    modified_date: str
    app_name: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _extract_text_chunks(raw: bytes) -> List[str]:
    decoded = raw.decode("latin-1", errors="ignore")
    chunks = [chunk.strip() for chunk in _TEXT_REGEX.findall(decoded)]
    return [chunk for chunk in chunks if chunk]


def _find_value(chunks: Iterable[str], label: str) -> str:
    label_lower = label.lower()
    for chunk in chunks:
        if not chunk.lower().startswith(label_lower):
            continue
        parts = chunk.split(":", 1)
        if len(parts) != 2:
            return ""
        return parts[1].strip()
    return ""


def _extract_components(chunks: Iterable[str]) -> List[str]:
    in_components = False
    components: List[str] = []
    for chunk in chunks:
        lowered = chunk.lower()
        if lowered.startswith("components:"):
            in_components = True
            tail = chunk.split(":", 1)[1].strip()
            if tail:
                components.append(tail.lstrip("- ").strip())
            continue

        if in_components:
            if lowered.startswith("modified date") or ":" in chunk and not chunk.startswith("--"):
                break
            if chunk.startswith("--"):
                components.append(chunk.lstrip("- ").strip())
                continue
            if chunk:
                components.append(chunk.strip())
    return [item for item in components if item]


def _infer_cal_pn(file_name: str) -> str:
    stem = Path(file_name).stem
    match = _CAL_PN_REGEX.match(stem)
    return match.group(1).upper() if match else ""


def parse_mt_header(path: Path) -> Optional[MasterTuneHeader]:
    """
    Parse cleartext metadata from an MT7/MT8/MT9 file header.
    """
    file_path = Path(path)
    if file_path.suffix.lower() not in {".mt7", ".mt8", ".mt9"}:
        return None
    if not file_path.exists():
        return None

    raw = file_path.read_bytes()[:_HEADER_SCAN_BYTES]
    chunks = _extract_text_chunks(raw)
    if not chunks:
        return None

    magic = chunks[0]
    if not magic.startswith(_MAGIC_PREFIX):
        return None

    format_version = magic.replace(_MAGIC_PREFIX, "").strip()
    file_name = _find_value(chunks, "File Name") or file_path.name

    header = MasterTuneHeader(
        file_path=str(file_path),
        file_name=file_name,
        format_version=format_version,
        cal_pn=_infer_cal_pn(file_name),
        application=_find_value(chunks, "Application"),
        configuration=_find_value(chunks, "Configuration"),
        components=_extract_components(chunks),
        modified_date=_find_value(chunks, "Modified Date"),
        app_name=_find_value(chunks, "App Name"),
    )
    return header


def _to_float(value: str, *, context: str) -> float:
    cleaned = value.strip().replace(",", "")
    if cleaned == "":
        raise ValueError(f"Missing numeric value in {context}")
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value '{value}' in {context}") from exc


def _detect_delimiter(header_line: str) -> Optional[str]:
    if "\t" in header_line:
        return "\t"
    if ";" in header_line:
        return ";"
    if "," in header_line:
        return ","
    return None


def _split_row(row: str, delimiter: Optional[str]) -> List[str]:
    if delimiter is None:
        return [part.strip() for part in row.strip().split() if part.strip()]
    return [part.strip() for part in row.split(delimiter)]


def _is_strictly_increasing(values: Sequence[float]) -> bool:
    return all(values[idx + 1] > values[idx] for idx in range(len(values) - 1))


def _nearest_index(values: Sequence[float], target: float) -> int:
    best_idx = 0
    best_distance = abs(values[0] - target)
    for idx, value in enumerate(values[1:], start=1):
        distance = abs(value - target)
        if distance < best_distance:
            best_distance = distance
            best_idx = idx
    return best_idx


def _interpolate_1d(
    src_x: Sequence[float],
    src_y: Sequence[float],
    dst_x: Sequence[float],
) -> List[float]:
    if len(src_x) != len(src_y):
        raise ValueError("Interpolation source axis/value length mismatch")
    if len(src_x) < 2:
        raise ValueError("Interpolation requires at least 2 source points")
    if not _is_strictly_increasing(src_x):
        raise ValueError("Interpolation source axis must be strictly increasing")

    out: List[float] = []
    for x in dst_x:
        if x <= src_x[0]:
            out.append(float(src_y[0]))
            continue
        if x >= src_x[-1]:
            out.append(float(src_y[-1]))
            continue

        left = 0
        for idx in range(len(src_x) - 1):
            if src_x[idx] <= x <= src_x[idx + 1]:
                left = idx
                break
        x0 = src_x[left]
        x1 = src_x[left + 1]
        y0 = src_y[left]
        y1 = src_y[left + 1]
        if x1 == x0:
            out.append(float(y0))
            continue
        ratio = (x - x0) / (x1 - x0)
        out.append(float(y0 + (y1 - y0) * ratio))
    return out


def parse_values_only_matrix(
    text: str, *, source_name: str = "matrix"
) -> Optional[List[List[float]]]:
    """Parse a values-only numeric matrix (no axis headers). Returns None on failure."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    delimiter = _detect_delimiter(lines[0])
    matrix: List[List[float]] = []
    expected_cols = 0
    for line in lines:
        parts = _split_row(line, delimiter)
        try:
            row = [float(cell.replace(",", "")) for cell in parts if cell]
        except ValueError:
            return None
        if not row:
            return None
        if expected_cols == 0:
            expected_cols = len(row)
            if expected_cols < 2:
                return None
        elif len(row) != expected_cols:
            return None
        matrix.append(row)
    return matrix


def parse_tsv_grid_text(tsv_text: str, *, source_name: str = "grid") -> ParsedGrid:
    """
    Parse tab/comma/semicolon/whitespace-separated table text copied from MasterTune.
    """
    raw_lines = [line for line in tsv_text.splitlines() if line.strip()]
    if len(raw_lines) < 2:
        raise ValueError(f"{source_name}: expected header + at least one data row")

    delimiter = _detect_delimiter(raw_lines[0])
    header = _split_row(raw_lines[0], delimiter)
    if len(header) < 2:
        raise ValueError(f"{source_name}: expected at least one column bin in header row")

    col_bins = [
        _to_float(value, context=f"{source_name} header column {idx + 1}")
        for idx, value in enumerate(header[1:])
    ]
    if not _is_strictly_increasing(col_bins):
        raise ValueError(f"{source_name}: column bins must be strictly increasing")

    row_bins: List[float] = []
    values: List[List[float]] = []
    expected_cols = len(col_bins)

    for line_idx, line in enumerate(raw_lines[1:], start=2):
        parts = _split_row(line, delimiter)
        if len(parts) < expected_cols + 1:
            raise ValueError(
                f"{source_name}: line {line_idx} has {len(parts)} columns; expected {expected_cols + 1}"
            )
        row_bin = _to_float(parts[0], context=f"{source_name} line {line_idx} row bin")
        row_values = [
            _to_float(cell, context=f"{source_name} line {line_idx} column {col_idx + 1}")
            for col_idx, cell in enumerate(parts[1: expected_cols + 1])
        ]
        row_bins.append(row_bin)
        values.append(row_values)

    if not _is_strictly_increasing(row_bins):
        raise ValueError(f"{source_name}: row bins must be strictly increasing")

    return ParsedGrid(row_bins=row_bins, col_bins=col_bins, values=values)


def parse_tsv_grid_file(path: Path) -> ParsedGrid:
    source = Path(path)
    content = source.read_text(encoding="utf-8")
    return parse_tsv_grid_text(content, source_name=str(source))


def resample_grid_to_bins(
    grid: ParsedGrid,
    *,
    target_row_bins: Sequence[float],
    target_col_bins: Sequence[float],
) -> ParsedGrid:
    """
    Resample a parsed grid onto new row/column bins using linear interpolation.
    """
    if not grid.row_bins or not grid.col_bins:
        raise ValueError("grid must include row and column bins")
    if not target_row_bins or not target_col_bins:
        raise ValueError("target bins must be non-empty")
    if not _is_strictly_increasing(grid.row_bins):
        raise ValueError("grid row bins must be strictly increasing")
    if not _is_strictly_increasing(grid.col_bins):
        raise ValueError("grid column bins must be strictly increasing")
    if not _is_strictly_increasing(target_row_bins):
        raise ValueError("target row bins must be strictly increasing")
    if not _is_strictly_increasing(target_col_bins):
        raise ValueError("target col bins must be strictly increasing")
    if len(grid.values) != len(grid.row_bins):
        raise ValueError("grid row count does not match row bins")
    if any(len(row) != len(grid.col_bins) for row in grid.values):
        raise ValueError("grid column count does not match column bins")

    # Step 1: resample each source row across target columns.
    rowwise_col_resampled: List[List[float]] = []
    for row in grid.values:
        rowwise_col_resampled.append(
            _interpolate_1d(grid.col_bins, row, target_col_bins)
        )

    # Step 2: for each target column, resample down rows to target RPM bins.
    target_values: List[List[float]] = [
        [0.0 for _ in target_col_bins] for _ in target_row_bins
    ]
    for col_idx in range(len(target_col_bins)):
        src_col_series = [row[col_idx] for row in rowwise_col_resampled]
        dst_col_series = _interpolate_1d(grid.row_bins, src_col_series, target_row_bins)
        for row_idx, value in enumerate(dst_col_series):
            target_values[row_idx][col_idx] = float(value)

    return ParsedGrid(
        row_bins=[float(v) for v in target_row_bins],
        col_bins=[float(v) for v in target_col_bins],
        values=target_values,
    )


def lambda_grid_to_afr_targets(
    lambda_grid: ParsedGrid,
    *,
    target_map_bins: Optional[Sequence[float]] = None,
    representative_rpm: float = 2500.0,
    stoich: float = 14.68,
    interpolate_map: bool = True,
) -> Dict[int, float]:
    """
    Convert a lambda table grid into AFR targets keyed by MAP bin.
    """
    if stoich <= 0:
        raise ValueError("stoich must be positive")
    if not lambda_grid.row_bins or not lambda_grid.col_bins:
        raise ValueError("lambda_grid must include row and column bins")

    expected_shape = (len(lambda_grid.row_bins), len(lambda_grid.col_bins))
    if len(lambda_grid.values) != expected_shape[0]:
        raise ValueError("lambda_grid row count does not match row bins")
    if any(len(row) != expected_shape[1] for row in lambda_grid.values):
        raise ValueError("lambda_grid column count does not match column bins")

    row_idx = _nearest_index(lambda_grid.row_bins, representative_rpm)
    lambda_profile = [float(v) for v in lambda_grid.values[row_idx]]
    output_bins = [float(v) for v in (target_map_bins or lambda_grid.col_bins)]

    if target_map_bins is not None:
        same_bins = (
            len(output_bins) == len(lambda_grid.col_bins)
            and all(abs(a - b) < 1e-6 for a, b in zip(output_bins, lambda_grid.col_bins))
        )
        if not same_bins:
            if not interpolate_map:
                raise ValueError("Lambda MAP bins do not match target MAP bins")
            lambda_profile = _interpolate_1d(lambda_grid.col_bins, lambda_profile, output_bins)

    return {
        int(round(map_bin)): round(float(lambda_value * stoich), 3)
        for map_bin, lambda_value in zip(output_bins, lambda_profile)
    }


def _parse_displacement_ci(application: str, configuration: str) -> int:
    candidates = [application, configuration]

    for source in candidates:
        match = _DISP_CI_REGEX.search(source)
        if match:
            return int(round(float(match.group(1))))

    for source in candidates:
        match = _DISP_FROM_APP_REGEX.search(source)
        if match:
            return int(round(float(match.group(1))))

    for source in candidates:
        match = _DISP_CC_REGEX.search(source)
        if match:
            cc_value = float(match.group(1))
            ci_value = cc_value / 16.387064
            return int(round(ci_value))

    return 0


def _normalize_text(value: str, fallback: str = "stock") -> str:
    clean = value.strip().lower()
    return clean if clean else fallback


def header_to_hardware_config(header: MasterTuneHeader, folder_name: str) -> HardwareConfig:
    """
    Convert parsed MasterTune metadata into a v3 HardwareConfig.
    """
    folder_key = folder_name.strip().lower()
    engine_family = _FOLDER_ENGINE_FAMILY.get(folder_key, folder_key or "unknown")

    displacement_ci = _parse_displacement_ci(header.application, header.configuration)
    components = " ".join(header.components).lower()
    config_text = f"{header.configuration} {components}".lower()

    exhaust_type = "stock"
    if "2-1" in config_text or "2 into 1" in config_text or "2-into-1" in config_text:
        exhaust_type = "2_into_1"
    elif "slip-on" in config_text or "slip on" in config_text:
        exhaust_type = "slip_on"
    elif "full exhaust" in config_text:
        exhaust_type = "full_system"

    air_cleaner = "stock"
    if "breather" in config_text or "intake" in config_text or "air cleaner" in config_text:
        air_cleaner = "high_flow"

    cam_spec = "stock"
    if "cam" in config_text:
        cam_spec = _normalize_text(header.configuration)

    return HardwareConfig(
        engine_family=engine_family,
        displacement_ci=displacement_ci,
        cam_spec=cam_spec,
        exhaust_type=exhaust_type,
        air_cleaner=air_cleaner,
        tune_platform="mastertune",
    )


__all__ = [
    "MasterTuneHeader",
    "ParsedGrid",
    "parse_mt_header",
    "parse_tsv_grid_text",
    "parse_tsv_grid_file",
    "parse_values_only_matrix",
    "resample_grid_to_bins",
    "lambda_grid_to_afr_targets",
    "header_to_hardware_config",
]
