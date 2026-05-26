"""Shared surgical PVV I/O primitives.

Every helper here has byte-identical SHA test coverage via the four tool
slice tests in tests/unit/. Any modification that shifts output bytes will
break at least one of:

  - test_spark_feathered_ramp_slice.py   (SHA b5a69006...)
  - test_spark_knock_hotspot_slice.py    (SHA b246b8b3...)
  - test_gp_smooth_idle_cruise_ve_slice.py (SHA 1fbaad31...)
  - test_wot_ve_graft_slice.py           (SHA c9b970b0...)

That's the regression contract. Touch with care.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List, Mapping, Optional, Set

import numpy as np


@dataclass(frozen=True)
class TableData:
    """A parsed PVV table with mutable XML cell element references.

    `cell_elements[r][c]` is the live `<Cell>` element from the original
    tree; mutating its `value` attribute is what `mutate_table_cells`
    does.

    `row_axis` and `col_axis` carry the float values from each row/col's
    `label` attr. Units are tune-dependent (kRPM for VE/spark RPM axes,
    kPa or % for load axes).
    """

    row_axis: np.ndarray
    col_axis: np.ndarray
    values: np.ndarray
    cell_elements: List[List[ET.Element]]


def format_value(value: float) -> str:
    """Numeric -> XML attribute string, matching the seanbike serialization.

    Format: .4f, then rstrip("0"), then rstrip(".").  -0 / -0.0 -> "0".
    Anything else (e.g. `repr()`, `%g`, more decimals) shifts output bytes
    and breaks the SHA pin in the four slice tests.
    """
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    if text in {"-0", "-0.0"}:
        return "0"
    return text


def sha256(path: Path) -> str:
    """Streaming SHA-256 of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_item_by_id(root: ET.Element, item_id: str) -> ET.Element:
    """Locate an `<Item id=...>` child of root. Raises ValueError if absent."""
    for item in root.findall("Item"):
        if item.get("id") == item_id:
            return item
    raise ValueError(f"Could not find Item id={item_id!r}")


def parse_table(root: ET.Element, item_id: str) -> TableData:
    """Parse a 2D table Item: returns axes + values + cell element refs."""
    item = find_item_by_id(root, item_id)
    col_elements = item.findall("./Columns/Col")
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
    return TableData(
        row_axis=np.array(row_axis, dtype=float),
        col_axis=col_axis,
        values=np.array(values, dtype=float),
        cell_elements=cell_elements,
    )


def parse_scalar(root: ET.Element, item_id: str) -> float:
    """Parse a single-Cell scalar Item (e.g. displacement, injector size)."""
    item = find_item_by_id(root, item_id)
    cell = item.find("./Rows/Row/Cell")
    if cell is None:
        raise ValueError(f"Scalar item {item_id!r} missing Cell value")
    return float(cell.get("value", "0"))


def mutate_scalar(root: ET.Element, item_id: str, value: float) -> None:
    """Set a single-Cell scalar Item's value via format_value.

    Counterpart to parse_scalar. Used by tools that rewrite scalars like
    `tbl_injector_size` and `tbl_engine_displacement` (e.g. injector
    rescaling). Same byte-stable formatting as mutate_table_cells.
    """
    item = find_item_by_id(root, item_id)
    cell = item.find("./Rows/Row/Cell")
    if cell is None:
        raise ValueError(f"Scalar item {item_id!r} missing Cell value")
    cell.set("value", format_value(float(value)))


def collect_item_cells(root: ET.Element) -> dict[str, list[str]]:
    """Return every Item's id -> list of cell value strings.

    Used for the post-write integrity diff: compare input root's cells to
    output root's cells; any Item whose list changed is "changed".
    """
    out: dict[str, list[str]] = {}
    for item in root.findall("Item"):
        item_id = item.get("id", "")
        out[item_id] = [
            cell.get("value", "")
            for row in item.findall("./Rows/Row")
            for cell in row.findall("Cell")
        ]
    return out


def mutate_table_cells(table: TableData, new_values: np.ndarray) -> None:
    """Set the `value` attr of each `<Cell>` from new_values via format_value."""
    if table.values.shape != new_values.shape:
        raise ValueError("New value shape mismatch")
    rows, cols = new_values.shape
    for r in range(rows):
        for c in range(cols):
            table.cell_elements[r][c].set(
                "value", format_value(float(new_values[r, c]))
            )


def write_xml_tree(tree: ET.ElementTree, output_path: Path) -> None:
    """Serialize the tree to disk with the byte-stable invariants.

    encoding="utf-8" + xml_declaration=True are the ONLY parameters used by
    any tool. Adding pretty-print, changing encoding, or stripping the
    declaration would shift output bytes and break SHA pins.
    """
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def verify_integrity_or_cleanup(
    output_path: Path,
    original_root: ET.Element,
    allowed_changed_ids: Set[str],
    *,
    integrity_gate,
):
    """Re-parse the output PVV, diff cells, run the integrity gate.

    Returns:
      (None, in_cells, out_cells, changed_ids) on success.
      (GateFailure, None, None, None) on integrity failure.
        Output file is unlinked before return.
      (GateFailure, None, None, None) on post-write parse failure.
        Output file is unlinked before return.

    The shape "tuple with failure or in_cells" lets the caller continue
    to build the manifest without re-parsing.
    """
    from dynoai.tools.gates import GateFailure  # local import: avoid cycle

    try:
        output_root = ET.parse(output_path).getroot()
    except Exception as exc:  # noqa: BLE001
        if output_path.exists():
            output_path.unlink()
        return (
            GateFailure(
                gate=getattr(integrity_gate, "name", "item_integrity"),
                reason=f"post-write parse failed: {exc}",
            ),
            None,
            None,
            None,
        )

    in_cells = collect_item_cells(original_root)
    out_cells = collect_item_cells(output_root)
    failure = integrity_gate.check_xml_roots(
        in_cells, out_cells, allowed_changed_ids
    )
    if failure is not None:
        if output_path.exists():
            output_path.unlink()
        return failure, None, None, None

    changed_ids = sorted(
        item_id for item_id in in_cells if in_cells[item_id] != out_cells[item_id]
    )
    return None, in_cells, out_cells, changed_ids
