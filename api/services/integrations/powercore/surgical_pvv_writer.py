"""
Surgical PVV writer for VE correction patches.

This module provides a flash-safe path for applying VE correction matrices to an
existing PowerVision tune file by mutating only approved table Item ids.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class TableAxes:
    """Axis metadata for a VE table in a PVV file."""

    table_id: str
    row_axis: np.ndarray
    col_axis: np.ndarray
    col_units: str
    shape: tuple[int, int]


@dataclass(frozen=True)
class SurgicalWriteResult:
    """Result metadata for a completed surgical write."""

    output_path: Path
    manifest_path: Path
    sha256: str
    changed_ids: list[str]
    table_stats: list[dict]
    capped_cells: int


@dataclass(frozen=True)
class _TableData:
    """Parsed table data with mutable cell references."""

    row_axis: np.ndarray
    col_axis: np.ndarray
    col_units: str
    values: np.ndarray
    cell_elements: list[list[ET.Element]]


def _format_value(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    if text in {"-0", "-0.0"}:
        return "0"
    return text


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_item_by_id(root: ET.Element, item_id: str) -> ET.Element:
    for item in root.findall("Item"):
        if item.get("id") == item_id:
            return item
    raise ValueError(f"Could not find Item id={item_id!r}")


def _parse_table(root: ET.Element, item_id: str) -> _TableData:
    item = _find_item_by_id(root, item_id)
    columns_el = item.find("./Columns")
    if columns_el is None:
        raise ValueError(f"Table item {item_id!r} is missing Columns")

    col_elements = columns_el.findall("Col")
    row_elements = item.findall("./Rows/Row")
    if not col_elements or not row_elements:
        raise ValueError(f"Table item {item_id!r} missing rows/columns")

    col_axis = np.array(
        [float(col.get("label", "0")) for col in col_elements], dtype=float
    )
    row_axis: list[float] = []
    values: list[list[float]] = []
    cell_elements: list[list[ET.Element]] = []

    for row in row_elements:
        row_axis.append(float(row.get("label", "0")))
        cells = row.findall("Cell")
        if len(cells) != len(col_elements):
            raise ValueError(
                f"Table {item_id!r} row has {len(cells)} cells; "
                f"expected {len(col_elements)}"
            )
        cell_elements.append(cells)
        values.append([float(cell.get("value", "0")) for cell in cells])

    return _TableData(
        row_axis=np.array(row_axis, dtype=float),
        col_axis=col_axis,
        col_units=columns_el.get("units", ""),
        values=np.array(values, dtype=float),
        cell_elements=cell_elements,
    )


def _collect_item_cells(root: ET.Element) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for item in root.findall("Item"):
        item_id = item.get("id", "")
        out[item_id] = [
            cell.get("value", "")
            for row in item.findall("./Rows/Row")
            for cell in row.findall("Cell")
        ]
    return out


def _verify_output_integrity(
    input_root: ET.Element,
    output_root: ET.Element,
    allowed_changed_ids: set[str],
) -> list[str]:
    in_items = input_root.findall("Item")
    out_items = output_root.findall("Item")
    if len(in_items) != len(out_items):
        raise RuntimeError(
            f"Output Item count changed ({len(in_items)} -> {len(out_items)})"
        )
    in_ids = {item.get("id", "") for item in in_items}
    out_ids = {item.get("id", "") for item in out_items}
    if in_ids != out_ids:
        raise RuntimeError("Output Item id set does not match input")

    in_cells = _collect_item_cells(input_root)
    out_cells = _collect_item_cells(output_root)
    changed_ids = sorted(
        item_id for item_id in in_cells if in_cells[item_id] != out_cells[item_id]
    )
    unexpected = sorted(
        item_id for item_id in changed_ids if item_id not in allowed_changed_ids
    )
    if unexpected:
        raise RuntimeError(
            f"Unexpected non-approved item ids changed: {', '.join(unexpected)}"
        )
    return changed_ids


def _mutate_table_cells(table: _TableData, new_values: np.ndarray) -> None:
    if table.values.shape != new_values.shape:
        raise ValueError("New value shape mismatch")
    rows, cols = new_values.shape
    for r in range(rows):
        for c in range(cols):
            table.cell_elements[r][c].set("value", _format_value(float(new_values[r, c])))


def load_ve_table_axes(
    base_pvv_path: Path | str,
    table_ids: Iterable[str],
) -> dict[str, TableAxes]:
    """
    Parse VE table axes from a base PVV file.

    Args:
        base_pvv_path: Path to source PVV.
        table_ids: Iterable of table Item ids to load.

    Returns:
        Dict of table id -> TableAxes.
    """
    path = Path(base_pvv_path)
    if not path.exists():
        raise FileNotFoundError(path)

    requested_ids = [table_id for table_id in table_ids if table_id]
    if not requested_ids:
        raise ValueError("table_ids must contain at least one id")

    root = ET.parse(path).getroot()
    axes_by_id: dict[str, TableAxes] = {}
    for table_id in requested_ids:
        table = _parse_table(root, table_id)
        axes_by_id[table_id] = TableAxes(
            table_id=table_id,
            row_axis=table.row_axis.copy(),
            col_axis=table.col_axis.copy(),
            col_units=table.col_units,
            shape=table.values.shape,
        )

    return axes_by_id


def write_ve_correction_patch(
    base_pvv_path: Path | str,
    output_pvv_path: Path | str,
    corrections: dict[str, np.ndarray],
    *,
    ve_cap: float | None = None,
    ve_floor: float | None = None,
    allowed_changed_ids: set[str] | None = None,
    manifest_extra: dict | None = None,
) -> SurgicalWriteResult:
    """
    Apply VE correction multipliers to selected table ids in an existing PVV.

    Corrections must be multiplier matrices where 1.0 means "no change".
    """
    base_path = Path(base_pvv_path)
    output_path = Path(output_pvv_path)

    if not base_path.exists():
        raise FileNotFoundError(base_path)
    if not corrections:
        raise ValueError("corrections must contain at least one table")

    original_root = ET.parse(base_path).getroot()
    tree = ET.parse(base_path)
    root = tree.getroot()

    table_stats: list[dict] = []
    changed_cells_by_table: dict[str, list[dict[str, float]]] = {}
    capped_cells = 0

    for table_id in sorted(corrections):
        correction_matrix = np.asarray(corrections[table_id], dtype=float)
        table = _parse_table(root, table_id)
        if table.values.shape != correction_matrix.shape:
            raise ValueError(
                f"Shape mismatch for {table_id}: "
                f"table={table.values.shape}, correction={correction_matrix.shape}"
            )

        before = table.values.copy()
        after = before * correction_matrix
        unclamped = after.copy()

        if ve_floor is not None:
            after = np.maximum(after, ve_floor)
        if ve_cap is not None:
            after = np.minimum(after, ve_cap)

        capped_cells += int(np.sum(np.abs(after - unclamped) > 1e-9))

        _mutate_table_cells(table, after)

        delta = after - before
        changed_mask = np.abs(delta) > 1e-9
        changed_indices = np.argwhere(changed_mask)

        changed_cells_by_table[table_id] = [
            {
                "row_axis": float(table.row_axis[r]),
                "col_axis": float(table.col_axis[c]),
                "before": float(before[r, c]),
                "after": float(after[r, c]),
                "delta": float(delta[r, c]),
                "correction_multiplier": float(correction_matrix[r, c]),
            }
            for r, c in changed_indices
        ]

        table_stats.append(
            {
                "table_id": table_id,
                "cells_total": int(before.size),
                "cells_changed": int(np.sum(changed_mask)),
                "before_min": float(np.min(before)),
                "before_max": float(np.max(before)),
                "after_min": float(np.min(after)),
                "after_max": float(np.max(after)),
                "delta_min": float(np.min(delta)),
                "delta_max": float(np.max(delta)),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)

    try:
        output_root = ET.parse(output_path).getroot()
        allowed = allowed_changed_ids or set(corrections.keys())
        changed_ids = _verify_output_integrity(original_root, output_root, allowed)
    except Exception:
        if output_path.exists():
            output_path.unlink()
        raise

    output_sha = _sha256(output_path)
    manifest_path = output_path.with_suffix(".manifest.json")
    manifest = {
        "kind": "ve_correction_surgical_patch",
        "inputs": {
            "base_pvv": str(base_path),
            "base_sha256": _sha256(base_path),
        },
        "policy": {
            "ve_cap": ve_cap,
            "ve_floor": ve_floor,
            "allowed_changed_ids": sorted(allowed_changed_ids or set(corrections.keys())),
        },
        "table_stats": table_stats,
        "changed_cells_by_table": changed_cells_by_table,
        "output": {
            "pvv": str(output_path),
            "sha256": output_sha,
            "changed_ids": changed_ids,
            "capped_cells": capped_cells,
        },
    }
    if manifest_extra:
        manifest["extra"] = manifest_extra
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return SurgicalWriteResult(
        output_path=output_path,
        manifest_path=manifest_path,
        sha256=output_sha,
        changed_ids=changed_ids,
        table_stats=table_stats,
        capped_cells=capped_cells,
    )


__all__ = [
    "SurgicalWriteResult",
    "TableAxes",
    "load_ve_table_axes",
    "write_ve_correction_patch",
]
