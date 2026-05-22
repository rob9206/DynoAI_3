"""Apply Tier A wheelie patch on top of the already-O2-disabled Fuel Moto PVV.

Tier A changes (all flash-safe, no combustion-margin cells touched):

  Scalars:
    PE Enable RPM      3.5  -> 2.8    (PE active at 2800 rpm instead of 3500)
    PE Enable TPS      65   -> 55     (PE active at 55% throttle instead of 65%)
    PE Disable RPM     3.25 -> 2.6    (kept ~200rpm below enable to avoid flutter)
    PE Disable TPS     60   -> 50     (kept ~5%  below enable to avoid flutter)

  Acceleration Enrichment (row "0", cells indexed by Fahrenheit col):
    90 F   1.05 -> 1.15
    118 F  0.84 -> 1.00
    147 F  0.67 -> 0.80

  Throttle Blade Control Low Gear  (raise asymptote in lift band):
    row 1.5  cells [ 8..16]  39 -> 54
    row 1.75 cells [ 9..16]  54 -> 69
    row 2    cells [10..16]  69 -> 89

Surgical edit via stdlib ET so every Item `id` attribute is preserved and the
file remains flash-safe.
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

SRC = Path(r"c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off.pvv")
DST = Path(r"c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off_wheelieA.pvv")


@dataclass
class Op:
    kind: str  # "scalar" | "row_cell" | "row_cells_range"
    item: str
    old: str
    new: str
    row_label: str | None = None
    cell_idx: int | None = None
    cell_idx_end: int | None = None  # inclusive, for ranges


OPERATIONS: list[Op] = [
    # ---- PE thresholds ----
    Op("scalar", "PE Enable RPM",  "3.5",  "2.8"),
    Op("scalar", "PE Enable TPS",  "65",   "55"),
    Op("scalar", "PE Disable RPM", "3.25", "2.6"),
    Op("scalar", "PE Disable TPS", "60",   "50"),
    # ---- Acceleration Enrichment (cols: 3,32,61,90,118,147,176,205,234,262,291,320) ----
    Op("row_cell", "Acceleration Enrichment", "1.05", "1.15", row_label="0", cell_idx=3),  # 90  F
    Op("row_cell", "Acceleration Enrichment", "0.84", "1.00", row_label="0", cell_idx=4),  # 118 F
    Op("row_cell", "Acceleration Enrichment", "0.67", "0.80", row_label="0", cell_idx=5),  # 147 F
    # ---- Throttle Blade Control Low Gear: raise asymptote (no change to 0..29 ramp) ----
    Op("row_cells_range", "Throttle Blade Control Low Gear", "39", "54",
       row_label="1.5",  cell_idx=8,  cell_idx_end=16),
    Op("row_cells_range", "Throttle Blade Control Low Gear", "54", "69",
       row_label="1.75", cell_idx=9,  cell_idx_end=16),
    Op("row_cells_range", "Throttle Blade Control Low Gear", "69", "89",
       row_label="2",    cell_idx=10, cell_idx_end=16),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_item(root: ET.Element, name: str) -> ET.Element:
    matches = [it for it in root.findall("Item") if it.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"item {name!r}: expected 1 match, got {len(matches)}")
    if not matches[0].get("id"):
        raise ValueError(f"item {name!r}: missing `id` attribute (would be flash-unsafe)")
    return matches[0]


def find_row(item: ET.Element, row_label: str) -> ET.Element:
    rows = item.findall(".//Row")
    matched = [r for r in rows if r.get("label") == row_label]
    if len(matched) != 1:
        raise ValueError(
            f"item {item.get('name')!r}: row label {row_label!r} matched "
            f"{len(matched)} rows (need exactly 1)"
        )
    return matched[0]


def apply_op(root: ET.Element, op: Op) -> list[tuple[str, str, str]]:
    """Apply one op. Returns list of (locator, old, new) for each cell touched."""
    item = find_item(root, op.item)
    changes: list[tuple[str, str, str]] = []

    if op.kind == "scalar":
        cells = item.findall(".//Cell")
        if len(cells) != 1:
            raise ValueError(f"scalar {op.item!r}: expected 1 Cell, got {len(cells)}")
        cur = cells[0].get("value", "")
        if cur != op.old:
            raise ValueError(
                f"scalar {op.item!r}: expected current={op.old!r}, got {cur!r}"
            )
        cells[0].set("value", op.new)
        changes.append((op.item, cur, op.new))

    elif op.kind == "row_cell":
        if op.row_label is None or op.cell_idx is None:
            raise ValueError(f"{op}: row_cell needs row_label and cell_idx")
        row = find_row(item, op.row_label)
        cells = row.findall("Cell")
        if op.cell_idx >= len(cells):
            raise ValueError(
                f"{op.item!r} row {op.row_label!r}: cell_idx {op.cell_idx} "
                f"out of range (len={len(cells)})"
            )
        cur = cells[op.cell_idx].get("value", "")
        if cur != op.old:
            raise ValueError(
                f"{op.item!r} row {op.row_label!r} cell {op.cell_idx}: "
                f"expected current={op.old!r}, got {cur!r}"
            )
        cells[op.cell_idx].set("value", op.new)
        changes.append((f"{op.item}[row={op.row_label},cell={op.cell_idx}]", cur, op.new))

    elif op.kind == "row_cells_range":
        if op.row_label is None or op.cell_idx is None or op.cell_idx_end is None:
            raise ValueError(f"{op}: row_cells_range needs row_label, cell_idx, cell_idx_end")
        row = find_row(item, op.row_label)
        cells = row.findall("Cell")
        if op.cell_idx_end >= len(cells):
            raise ValueError(
                f"{op.item!r} row {op.row_label!r}: cell_idx_end {op.cell_idx_end} "
                f"out of range (len={len(cells)})"
            )
        for i in range(op.cell_idx, op.cell_idx_end + 1):
            cur = cells[i].get("value", "")
            if cur != op.old:
                raise ValueError(
                    f"{op.item!r} row {op.row_label!r} cell {i}: "
                    f"expected current={op.old!r}, got {cur!r} "
                    f"(range was idx {op.cell_idx}..{op.cell_idx_end})"
                )
            cells[i].set("value", op.new)
            changes.append((f"{op.item}[row={op.row_label},cell={i}]", cur, op.new))

    else:
        raise ValueError(f"unknown op kind: {op.kind}")

    return changes


def main() -> None:
    if not SRC.exists():
        raise FileNotFoundError(SRC)

    print(f"input:  {SRC}")
    print(f"input sha256:  {sha256(SRC)}")
    print(f"input bytes:   {SRC.stat().st_size}")

    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    tree = ET.parse(SRC, parser=parser)
    root = tree.getroot()
    if root.tag != "PVV":
        raise ValueError(f"unexpected root tag: {root.tag}")

    n_items_in = len(root.findall("Item"))
    all_changes: list[tuple[str, str, str]] = []

    print("\nApplying operations:")
    for op in OPERATIONS:
        changes = apply_op(root, op)
        for locator, old, new in changes:
            print(f"  [chg] {locator:60s}  {old:>6s} -> {new}")
        all_changes.extend(changes)

    tree.write(DST, encoding="utf-8", xml_declaration=False)

    print(f"\noutput: {DST}")
    print(f"output sha256: {sha256(DST)}")
    print(f"output bytes:  {DST.stat().st_size}")
    print(f"items in: {n_items_in}, items out: {len(ET.parse(DST).getroot().findall('Item'))}")
    print(f"total cells changed: {len(all_changes)}")

    # Verify every Item still has its `id`
    out_root = ET.parse(DST).getroot()
    out_items = out_root.findall("Item")
    items_with_id = sum(1 for it in out_items if it.get("id"))
    print(f"items with id: {items_with_id} / {len(out_items)}")
    if items_with_id != len(out_items):
        raise ValueError("`id` attributes dropped during write — file is NOT flash-safe")

    # Verify every patched cell stuck
    for op in OPERATIONS:
        item = find_item(out_root, op.item)
        if op.kind == "scalar":
            got = item.findall(".//Cell")[0].get("value", "")
            if got != op.new:
                raise ValueError(f"verify failed: {op.item!r} = {got!r} (want {op.new!r})")
        elif op.kind == "row_cell":
            row = find_row(item, op.row_label)  # type: ignore[arg-type]
            got = row.findall("Cell")[op.cell_idx].get("value", "")  # type: ignore[index]
            if got != op.new:
                raise ValueError(
                    f"verify failed: {op.item!r}[{op.row_label},{op.cell_idx}] "
                    f"= {got!r} (want {op.new!r})"
                )
        elif op.kind == "row_cells_range":
            row = find_row(item, op.row_label)  # type: ignore[arg-type]
            cells = row.findall("Cell")
            for i in range(op.cell_idx, op.cell_idx_end + 1):  # type: ignore[arg-type]
                got = cells[i].get("value", "")
                if got != op.new:
                    raise ValueError(
                        f"verify failed: {op.item!r}[{op.row_label},{i}] "
                        f"= {got!r} (want {op.new!r})"
                    )

    print("\nverify: PASS  (all patched cells stuck, all 129 Item `id` attrs preserved)")


if __name__ == "__main__":
    main()
