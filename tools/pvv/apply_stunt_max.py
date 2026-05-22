r"""Apply the stunt-max patch on top of fuelmoto110lowrider_final.pvv.

Five stunt-focused refinements selected by the user (rideability secondary,
"pure stunt rig"). No combustion-margin cells in the lift band are touched.
No spark advance, VE, AFR target, knock guardrail, or injector cell changes.

Operations (25 cells total):
  1. Deceleration Enleanment (147..320 F):  0.43/0.38/0.35/0.34x4  ->  0.55/0.50/0.50/0.50x4
  2. EITMS Mode 2 Enable Temp scalar:       329  ->  600
     EITMS Mode 3 Enable Temp scalar:       248  ->  600
  3. Closed Throttle Spark (Front+Rear) row "1" cells 3 (90 F) and 4 (118 F): 25 -> 28
  4. Twistgrip Sensor Entry scalar:         1.6   ->  1.4
     Twistgrip Sensor Exit scalar:          1.95  ->  1.75
  5. RPM Limit Threshold scalar:            5.7   ->  6
     RPM Limit table row "0", cells 0..8:   6.2   ->  6.5

Input:
    c:\Users\dawso\Downloads\fuelmoto110lowrider_final.pvv

Output:
    c:\Users\dawso\Downloads\fuelmoto110lowrider_stuntmax.pvv

Surgical edit via defusedxml parser + stdlib ElementTree write so every
Item `id` attribute is preserved and the file remains flash-safe.
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from defusedxml import ElementTree as DefusedET

SRC = Path(r"c:\Users\dawso\Downloads\fuelmoto110lowrider_final.pvv")
DST = Path(r"c:\Users\dawso\Downloads\fuelmoto110lowrider_stuntmax.pvv")


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
    # ---- 1. Decel Enleanment richer (147..320 F) -----------------------------
    # Cold cells 3..118 F left as-is to preserve cold-engine decel fueling.
    Op("row_cell", "Deceleration Enleanment", "0.43", "0.55", row_label="0", cell_idx=5),  # 147 F
    Op("row_cell", "Deceleration Enleanment", "0.38", "0.50", row_label="0", cell_idx=6),  # 176 F
    Op("row_cell", "Deceleration Enleanment", "0.35", "0.50", row_label="0", cell_idx=7),  # 205 F
    Op("row_cell", "Deceleration Enleanment", "0.34", "0.50", row_label="0", cell_idx=8),  # 234 F
    Op("row_cell", "Deceleration Enleanment", "0.34", "0.50", row_label="0", cell_idx=9),  # 262 F
    Op("row_cell", "Deceleration Enleanment", "0.34", "0.50", row_label="0", cell_idx=10), # 291 F
    Op("row_cell", "Deceleration Enleanment", "0.34", "0.50", row_label="0", cell_idx=11), # 320 F
    # ---- 2. EITMS effectively disabled --------------------------------------
    Op("scalar", "EITMS Mode 2 Enable Temp", "329", "600"),
    Op("scalar", "EITMS Mode 3 Enable Temp", "248", "600"),
    # ---- 3. Idle bump via Closed Throttle Spark (no flat idle-target scalar) -
    # Bump CTS row "1" (1000 rpm idle zone) at warm temp cells 90 F and 118 F.
    Op("row_cell", "Closed Throttle Spark (Front Cyl)", "25", "28", row_label="1", cell_idx=3),  # 90 F
    Op("row_cell", "Closed Throttle Spark (Front Cyl)", "25", "28", row_label="1", cell_idx=4),  # 118 F
    Op("row_cell", "Closed Throttle Spark (Rear Cyl)",  "25", "28", row_label="1", cell_idx=3),  # 90 F
    Op("row_cell", "Closed Throttle Spark (Rear Cyl)",  "25", "28", row_label="1", cell_idx=4),  # 118 F
    # ---- 4. Twistgrip deadband tightened ------------------------------------
    Op("scalar", "Twistgrip Sensor Entry", "1.6",  "1.4"),
    Op("scalar", "Twistgrip Sensor Exit",  "1.95", "1.75"),
    # ---- 5. Rev limit raised 300 rpm ----------------------------------------
    Op("scalar", "RPM Limit Threshold", "5.7", "6"),
    Op("row_cells_range", "RPM Limit", "6.2", "6.5", row_label="0", cell_idx=0, cell_idx_end=8),
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
    matched = [r for r in item.findall(".//Row") if r.get("label") == row_label]
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

    out_tree = DefusedET.parse(DST)
    out_root = out_tree.getroot()
    out_items = out_root.findall("Item")
    items_with_id = sum(1 for it in out_items if it.get("id"))

    print(f"\noutput: {DST}")
    print(f"output sha256: {sha256(DST)}")
    print(f"output bytes:  {DST.stat().st_size}")
    print(f"items in: {n_items_in}, items out: {len(out_items)}")
    print(f"total cells changed: {len(all_changes)}")
    print(f"items with id: {items_with_id} / {len(out_items)}")

    if n_items_in != len(out_items):
        raise ValueError("Item count changed during write")
    if items_with_id != len(out_items):
        raise ValueError("`id` attributes dropped during write -- file is NOT flash-safe")

    # Verify every patched cell stuck
    for op in OPERATIONS:
        item = find_item(out_root, op.item)
        if op.kind == "scalar":
            got = item.findall(".//Cell")[0].get("value", "")
            if got != op.new:
                raise ValueError(f"verify failed: {op.item!r} = {got!r} (want {op.new!r})")
        elif op.kind == "row_cell":
            assert op.row_label is not None and op.cell_idx is not None
            row = find_row(item, op.row_label)
            got = row.findall("Cell")[op.cell_idx].get("value", "")
            if got != op.new:
                raise ValueError(
                    f"verify failed: {op.item!r}[{op.row_label},{op.cell_idx}] "
                    f"= {got!r} (want {op.new!r})"
                )
        elif op.kind == "row_cells_range":
            assert op.row_label is not None and op.cell_idx is not None and op.cell_idx_end is not None
            row = find_row(item, op.row_label)
            cells = row.findall("Cell")
            for i in range(op.cell_idx, op.cell_idx_end + 1):
                got = cells[i].get("value", "")
                if got != op.new:
                    raise ValueError(
                        f"verify failed: {op.item!r}[{op.row_label},{i}] "
                        f"= {got!r} (want {op.new!r})"
                    )

    print("\nverify: PASS  (all patched cells stuck, all Item `id` attrs preserved)")


if __name__ == "__main__":
    main()
