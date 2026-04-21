"""
Stable ECU fingerprint for a Power Vision `.pvv` tune file.

Goal: two PVVs of the *same base calibration* should produce the same
signature even after cosmetic re-saves (whitespace, attribute order,
comment changes). Two different base calibrations must produce different
signatures.

Approach: parse the XML, extract `(item_name, sorted cell values)` for a
stable set of core tables, hash the canonical text. Designed to be
resilient when some tables are missing or renamed.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable, Optional

__all__ = ["compute_pvv_signature"]

# Tables that change only when the calibration truly changes.
# Any one of these present is enough to fingerprint the tune; we use the
# union of whatever we find.
CORE_TABLE_HINTS: tuple[str, ...] = (
    "tbl_ve_tps_based_front_cyl",
    "tbl_ve_tps_based_rear_cyl",
    "tbl_ve_front_cyl",
    "tbl_ve_rear_cyl",
    "tbl_afr_stoich",
    "tbl_spark_advance_front_cyl",
    "tbl_spark_advance_rear_cyl",
    "ve front cyl",
    "ve rear cyl",
    "afr stoich",
    "spark advance front",
    "spark advance rear",
)

_ITEM_RE = re.compile(
    r'<Item\b[^>]*\bname="([^"]+)"[^>]*>(.*?)</Item>',
    re.IGNORECASE | re.DOTALL,
)
_CELL_RE = re.compile(r'<Cell\b[^>]*\bvalue="([^"]*)"', re.IGNORECASE)


def compute_pvv_signature(
    raw_xml: str | bytes,
    extra_hints: Optional[Iterable[str]] = None,
) -> Optional[str]:
    """Return a hex SHA256 fingerprint, or None if we cannot fingerprint.

    Accepts either raw XML text or raw bytes (any UTF-8-ish encoding).
    `extra_hints` lets callers add vehicle-specific table names.
    """
    if isinstance(raw_xml, bytes):
        try:
            text = raw_xml.decode("utf-8", errors="replace")
        except Exception:
            return None
    else:
        text = raw_xml

    if "<PVV" not in text and "<pvv" not in text:
        return None

    hints: list[str] = [h.lower() for h in CORE_TABLE_HINTS]
    if extra_hints:
        hints.extend(h.lower() for h in extra_hints)

    items: list[tuple[str, list[str]]] = []
    for match in _ITEM_RE.finditer(text):
        name = match.group(1).strip()
        name_lower = name.lower()
        if not any(h in name_lower for h in hints):
            continue
        cells = _CELL_RE.findall(match.group(2))
        if not cells:
            continue
        items.append((name_lower, cells))

    if not items:
        digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        return "weak:" + digest[:32]

    items.sort(key=lambda pair: pair[0])
    canonical_parts: list[str] = []
    for name, cells in items:
        canonical_parts.append(name)
        canonical_parts.extend(cells)
    canonical = "\n".join(canonical_parts)

    return hashlib.sha256(canonical.encode("utf-8", errors="replace")).hexdigest()
