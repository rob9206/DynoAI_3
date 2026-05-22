"""Disable narrowband O2 feedback in a Fuel Moto PVV by flipping
`Closed Loop` and `Adaptive Control` flags to 0. Surgical edit using
stdlib ElementTree so every Item `id` attribute is preserved (the
high-level round-trip parser in api/services/powercore_integration.py
drops `id`s and produces a flash-unsafe file).

Input:  c:\\Users\\dawso\\Downloads\\fuelmoto110lowrider.pvv
Output: c:\\Users\\dawso\\Downloads\\fuelmoto110lowrider_o2off.pvv
"""
from __future__ import annotations

import hashlib
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

SRC = Path(r"c:\Users\dawso\Downloads\fuelmoto110lowrider.pvv")
DST = Path(r"c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off.pvv")

# Cells to flip: Item name -> expected current value -> new value
PATCHES: dict[str, tuple[str, str]] = {
    "Closed Loop": ("1", "0"),
    "Adaptive Control": ("1", "0"),
}
# Flag we just sanity-check (no change)
EXPECTED_UNCHANGED: dict[str, str] = {
    "Heated O2 Sensors": "0",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_pvv(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)

    print(f"input:  {src}")
    print(f"input sha256:  {sha256(src)}")
    print(f"input bytes:   {src.stat().st_size}")

    # Preserve XML comments (Power Vision writes the source-file name as a
    # top-level comment for provenance — stdlib ET.parse strips it by default).
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    tree = ET.parse(src, parser=parser)
    root = tree.getroot()
    if root.tag != "PVV":
        raise ValueError(f"unexpected root tag: {root.tag}")

    total_items = 0
    matched = {name: False for name in {**PATCHES, **EXPECTED_UNCHANGED}}
    changes: list[tuple[str, str, str]] = []  # (name, old, new)

    for item in root.findall("Item"):
        total_items += 1
        name = item.get("name", "")
        if name not in PATCHES and name not in EXPECTED_UNCHANGED:
            continue

        item_id = item.get("id", "")
        if not item_id:
            raise ValueError(
                f"flag item {name!r} has no `id` attribute — refusing to write"
            )

        cells = item.findall(".//Cell")
        if len(cells) != 1:
            raise ValueError(
                f"flag item {name!r} expected exactly 1 Cell, got {len(cells)}"
            )
        cell = cells[0]
        current = cell.get("value", "")

        if name in EXPECTED_UNCHANGED:
            expected = EXPECTED_UNCHANGED[name]
            if current != expected:
                raise ValueError(
                    f"flag {name!r} expected current={expected!r}, got {current!r}"
                )
            matched[name] = True
            print(f"  [ok ] {name:25s} id={item_id:30s} value={current} (unchanged)")
            continue

        expected_current, new_value = PATCHES[name]
        if current != expected_current:
            raise ValueError(
                f"flag {name!r} expected current={expected_current!r}, "
                f"got {current!r}; aborting to avoid corrupting an already-modified file"
            )
        cell.set("value", new_value)
        changes.append((name, current, new_value))
        matched[name] = True
        print(f"  [chg] {name:25s} id={item_id:30s} value={current} -> {new_value}")

    missing = [n for n, ok in matched.items() if not ok]
    if missing:
        raise ValueError(f"items not found in PVV: {missing}")

    if not changes:
        print("no changes required — file already had O2 feedback disabled")
        if dst != src:
            shutil.copy2(src, dst)
        return

    # Match the original file format exactly: no XML declaration on line 1
    # (Power Vision writes raw <PVV> as the first line).
    tree.write(dst, encoding="utf-8", xml_declaration=False)

    print(f"\noutput: {dst}")
    print(f"output sha256: {sha256(dst)}")
    print(f"output bytes:  {dst.stat().st_size}")
    print(f"items in file: {total_items}  (must match input)")
    print(f"cells changed: {len(changes)}")

    # Re-parse output and verify the patched cells stuck and nothing else moved
    tree2 = ET.parse(dst)
    root2 = tree2.getroot()
    out_items = root2.findall("Item")
    if len(out_items) != total_items:
        raise ValueError(
            f"item count drift after write: in={total_items}, out={len(out_items)}"
        )
    for item in out_items:
        name = item.get("name", "")
        if name in PATCHES:
            cells = item.findall(".//Cell")
            got = cells[0].get("value", "")
            want = PATCHES[name][1]
            if got != want:
                raise ValueError(
                    f"verify failed for {name!r}: want {want!r}, got {got!r}"
                )
            if not item.get("id"):
                raise ValueError(
                    f"verify failed for {name!r}: `id` attribute lost during write"
                )

    # Count how many <Item> elements in the output still have an `id` attribute.
    # If even one Item lost its id, the output is not flash-safe.
    items_with_id = sum(1 for it in out_items if it.get("id"))
    print(f"items with id: {items_with_id} / {total_items}")
    if items_with_id != total_items:
        raise ValueError(
            "`id` attributes were dropped during write — file is NOT flash-safe"
        )

    print("\nverify: PASS  (only the requested cells changed, all `id` attrs preserved)")


if __name__ == "__main__":
    patch_pvv(SRC, DST)
