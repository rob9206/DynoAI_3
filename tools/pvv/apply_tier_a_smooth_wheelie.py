r"""Apply a smoothed Tier A wheelie patch to the O2-disabled Fuel Moto PVV.

This variant keeps the same O2-off, PE-entry, and acceleration-enrichment
changes as the first Tier A patch, but smooths the low-gear throttle blade
asymptote so it is less abrupt at 1500-2000 rpm.

Input:
    c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off.pvv

Output:
    c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off_wheelieA_smooth.pvv

Only scalar flags and DBW/AE delivery cells are touched. VE, spark, AFR target,
knock control, injector size, displacement, and RPM limit remain unchanged.
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from defusedxml import ElementTree as DefusedET

SRC = Path(r"c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off.pvv")
DST = Path(r"c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off_wheelieA_smooth.pvv")


@dataclass
class Op:
    kind: str
    item: str
    old: str
    new: str
    row_label: str | None = None
    cell_idx: int | None = None
    cell_idx_end: int | None = None


OPERATIONS: list[Op] = [
    # PE entry/exit: same as Tier A.
    Op("scalar", "PE Enable RPM", "3.5", "2.8"),
    Op("scalar", "PE Enable TPS", "65", "55"),
    Op("scalar", "PE Disable RPM", "3.25", "2.6"),
    Op("scalar", "PE Disable TPS", "60", "50"),
    # Acceleration Enrichment hot-engine throttle-whack cells.
    Op("row_cell", "Acceleration Enrichment", "1.05", "1.15", row_label="0", cell_idx=3),
    Op("row_cell", "Acceleration Enrichment", "0.84", "1.00", row_label="0", cell_idx=4),
    Op("row_cell", "Acceleration Enrichment", "0.67", "0.80", row_label="0", cell_idx=5),
    # Throttle Blade Control Low Gear.
    # Columns are: 0, 2.5, 5, 10, 15, 20, 25, 30, 40, 60, 80, 100...
    Op("row_cell", "Throttle Blade Control Low Gear", "39", "44", row_label="1.5", cell_idx=8),
    Op("row_cell", "Throttle Blade Control Low Gear", "39", "50", row_label="1.5", cell_idx=9),
    Op("row_cells_range", "Throttle Blade Control Low Gear", "39", "54", row_label="1.5", cell_idx=10, cell_idx_end=16),
    Op("row_cell", "Throttle Blade Control Low Gear", "39", "44", row_label="1.75", cell_idx=8),
    Op("row_cell", "Throttle Blade Control Low Gear", "54", "59", row_label="1.75", cell_idx=9),
    Op("row_cells_range", "Throttle Blade Control Low Gear", "54", "69", row_label="1.75", cell_idx=10, cell_idx_end=16),
    Op("row_cell", "Throttle Blade Control Low Gear", "39", "44", row_label="2", cell_idx=8),
    Op("row_cell", "Throttle Blade Control Low Gear", "59", "69", row_label="2", cell_idx=9),
    Op("row_cells_range", "Throttle Blade Control Low Gear", "69", "89", row_label="2", cell_idx=10, cell_idx_end=16),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_item(root: ET.Element, name: str) -> ET.Element:
    matches = [it for it in root.findall("Item") if it.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"item {name!r}: expected 1 match, got {len(matches)}")
    if not matches[0].get("id"):
        raise ValueError(f"item {name!r}: missing `id` attribute")
    return matches[0]


def find_row(item: ET.Element, row_label: str) -> ET.Element:
    matches = [row for row in item.findall(".//Row") if row.get("label") == row_label]
    if len(matches) != 1:
        raise ValueError(
            f"item {item.get('name')!r}: row label {row_label!r} matched {len(matches)} rows"
        )
    return matches[0]


def apply_op(root: ET.Element, op: Op) -> list[tuple[str, str, str]]:
    item = find_item(root, op.item)

    if op.kind == "scalar":
        cells = item.findall(".//Cell")
        if len(cells) != 1:
            raise ValueError(f"scalar {op.item!r}: expected 1 Cell, got {len(cells)}")
        current = cells[0].get("value", "")
        if current != op.old:
            raise ValueError(f"scalar {op.item!r}: expected {op.old!r}, got {current!r}")
        cells[0].set("value", op.new)
        return [(op.item, current, op.new)]

    if op.kind == "row_cell":
        if op.row_label is None or op.cell_idx is None:
            raise ValueError(f"{op}: row_cell requires row_label and cell_idx")
        row = find_row(item, op.row_label)
        cells = row.findall("Cell")
        if op.cell_idx >= len(cells):
            raise ValueError(f"{op.item!r}: cell index {op.cell_idx} out of range")
        current = cells[op.cell_idx].get("value", "")
        if current != op.old:
            raise ValueError(
                f"{op.item!r} row={op.row_label} cell={op.cell_idx}: "
                f"expected {op.old!r}, got {current!r}"
            )
        cells[op.cell_idx].set("value", op.new)
        return [(f"{op.item}[row={op.row_label},cell={op.cell_idx}]", current, op.new)]

    if op.kind == "row_cells_range":
        if op.row_label is None or op.cell_idx is None or op.cell_idx_end is None:
            raise ValueError(f"{op}: range op requires row_label, cell_idx, and cell_idx_end")
        row = find_row(item, op.row_label)
        cells = row.findall("Cell")
        if op.cell_idx_end >= len(cells):
            raise ValueError(f"{op.item!r}: cell index {op.cell_idx_end} out of range")
        changes: list[tuple[str, str, str]] = []
        for idx in range(op.cell_idx, op.cell_idx_end + 1):
            current = cells[idx].get("value", "")
            if current != op.old:
                raise ValueError(
                    f"{op.item!r} row={op.row_label} cell={idx}: "
                    f"expected {op.old!r}, got {current!r}"
                )
            cells[idx].set("value", op.new)
            changes.append((f"{op.item}[row={op.row_label},cell={idx}]", current, op.new))
        return changes

    raise ValueError(f"unknown operation kind: {op.kind}")


def main() -> None:
    if not SRC.exists():
        raise FileNotFoundError(SRC)

    print(f"input:  {SRC}")
    print(f"input sha256:  {sha256(SRC)}")
    print(f"input bytes:   {SRC.stat().st_size}")

    parser = DefusedET.DefusedXMLParser(
        target=ET.TreeBuilder(insert_comments=True),
        forbid_dtd=True,
        forbid_entities=True,
        forbid_external=True,
    )
    tree = DefusedET.parse(SRC, parser=parser)
    root = tree.getroot()
    if root.tag != "PVV":
        raise ValueError(f"unexpected root tag: {root.tag}")

    n_items_in = len(root.findall("Item"))
    all_changes: list[tuple[str, str, str]] = []

    print("\nApplying operations:")
    for op in OPERATIONS:
        changes = apply_op(root, op)
        for locator, old, new in changes:
            print(f"  [chg] {locator:60s} {old:>6s} -> {new}")
        all_changes.extend(changes)

    tree.write(DST, encoding="utf-8", xml_declaration=False)

    out_root = DefusedET.parse(DST).getroot()
    out_items = out_root.findall("Item")
    items_with_id = sum(1 for item in out_items if item.get("id"))

    print(f"\noutput: {DST}")
    print(f"output sha256: {sha256(DST)}")
    print(f"output bytes:  {DST.stat().st_size}")
    print(f"items in: {n_items_in}, items out: {len(out_items)}")
    print(f"total cells changed: {len(all_changes)}")
    print(f"items with id: {items_with_id} / {len(out_items)}")

    if n_items_in != len(out_items):
        raise ValueError("Item count changed during write")
    if items_with_id != len(out_items):
        raise ValueError("`id` attributes dropped during write")

    print("\nverify: PASS  (all patched cells applied, all Item `id` attrs preserved)")


if __name__ == "__main__":
    main()
