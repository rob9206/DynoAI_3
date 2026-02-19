from __future__ import annotations

import re
from dataclasses import dataclass, fields
from typing import Iterable, Literal, Optional


def _coerce_optional_float(value: object) -> Optional[float]:
    """Convert stringified numbers to float; return None on empty values."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _clean_optional_str(value: object) -> Optional[str]:
    """Normalize optional string fields."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass
class DynoChartMeta:
    source: Literal["fuelmoto", "dynojet"]
    id: str
    category: str
    title: str
    page_url: str
    image_url: Optional[str] = None
    image_file: Optional[str] = None
    engine_family: Optional[str] = None
    displacement_ci: Optional[float] = None
    cam_info: Optional[str] = None
    exhaust_info: Optional[str] = None
    notes: Optional[str] = None
    max_power_hp: Optional[float] = None
    max_power_rpm: Optional[float] = None
    max_torque_ftlb: Optional[float] = None
    max_torque_rpm: Optional[float] = None

    def __post_init__(self) -> None:
        self.id = self.id.strip()
        self.category = self.category.strip()
        self.title = self.title.strip()
        self.page_url = self.page_url.strip()
        self.image_url = _clean_optional_str(self.image_url)
        self.image_file = _clean_optional_str(self.image_file)
        self.engine_family = _clean_optional_str(self.engine_family)
        self.displacement_ci = _coerce_optional_float(self.displacement_ci)
        self.cam_info = _clean_optional_str(self.cam_info)
        self.exhaust_info = _clean_optional_str(self.exhaust_info)
        self.notes = _clean_optional_str(self.notes)
        self.max_power_hp = _coerce_optional_float(self.max_power_hp)
        self.max_power_rpm = _coerce_optional_float(self.max_power_rpm)
        self.max_torque_ftlb = _coerce_optional_float(self.max_torque_ftlb)
        self.max_torque_rpm = _coerce_optional_float(self.max_torque_rpm)


@dataclass
class DynoCurveSpec:
    idle_rpm: float
    redline_rpm: float
    hp_peak_rpm: float
    max_hp: float
    tq_peak_rpm: float
    max_tq: float
    engine_family: str
    displacement_ci: float


def slugify_title(source: str, title: str) -> str:
    """
    Convert title to deterministic slug and prefix with source.

    Lowercases, replaces non-alphanumeric characters with underscores,
    collapses repeats, and strips leading/trailing underscores.
    """
    normalized = re.sub(r"[^a-z0-9]+", "_", title.lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    source_prefix = re.sub(r"[^a-z0-9]+", "_", source.lower()).strip("_")
    return f"{source_prefix}_{normalized}" if normalized else source_prefix


META_FIELD_ORDER: tuple[str, ...] = tuple(f.name for f in fields(DynoChartMeta))

_FLOAT_FIELDS = {
    "displacement_ci",
    "max_power_hp",
    "max_power_rpm",
    "max_torque_ftlb",
    "max_torque_rpm",
}


def meta_to_row(meta: DynoChartMeta, *, include_notes: bool = True) -> dict[str, str]:
    """
    Convert DynoChartMeta to a CSV-ready dictionary.

    Empty / None values are rendered as empty strings to keep CSV lean.
    """
    row: dict[str, str] = {}
    for name in META_FIELD_ORDER:
        if not include_notes and name == "notes":
            continue
        value = getattr(meta, name)
        row[name] = "" if value is None else str(value)
    return row


def meta_from_row(row: dict[str, str]) -> DynoChartMeta:
    """Instantiate DynoChartMeta from CSV row values."""
    clean_row: dict[str, object] = {}
    for key in META_FIELD_ORDER:
        if key not in row:
            continue
        value = row[key]
        if key in _FLOAT_FIELDS:
            clean_row[key] = _coerce_optional_float(value)
        elif row[key] == "":
            clean_row[key] = None
        else:
            clean_row[key] = row[key]
    return DynoChartMeta(**clean_row)  # type: ignore[arg-type]


__all__: Iterable[str] = [
    "DynoChartMeta",
    "DynoCurveSpec",
    "slugify_title",
    "meta_to_row",
    "meta_from_row",
    "META_FIELD_ORDER",
]
