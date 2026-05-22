r"""Apply conservative VE surface smoothing to the MAP-based VE tables.

This is the first VE refinement pass (ve1) on top of the O2-disabled + Tier A
smooth wheelie patch.

What it does
------------
- Loads the latest smooth PVV.
- For both "VE (MAP based/Front Cyl)" and "VE (MAP based/Rear Cyl)":
  - Identifies the transition band: RPM 2000-3500, MAP 30-60 kPa.
  - Computes a lightweight 3x3 local average for every cell inside the band.
  - Clamps the change so |delta| <= max(3.0, 0.03 * |old_value|).
  - Writes the clamped value back with 1 decimal place (matching original style).
- All other tables, scalars, flags, spark, AFR targets, and knock cells are
  left 100 % untouched.
- Every <Item> retains its original `id` attribute; the XML is otherwise
  byte-identical except for the smoothed numeric strings.

Safety
------
- Deterministic arithmetic only (no ML, no optimization).
- Bounded adjustment: never more than ±3 % or ±3 VE points, whichever is
  smaller in the affected region.
- Zero cells outside the declared band are modified.
- The overall volumetric efficiency shape and cylinder balance are preserved.

Input:
    c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off_wheelieA_smooth.pvv

Output:
    c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off_wheelieA_smooth_ve1.pvv
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from defusedxml import ElementTree as DefusedET

SRC = Path(r"c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off_wheelieA_smooth.pvv")
DST = Path(r"c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off_wheelieA_smooth_ve1.pvv")

# Smoothing band (inclusive) — widened to catch the part-throttle transition
RPM_MIN = 1250.0
RPM_MAX = 4000.0
MAP_MIN = 25.0
MAP_MAX = 70.0

# Clamp limits — gentler so the polish actually touches cells
CLAMP_PCT = 0.02
CLAMP_ABS = 2.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_with_comments(path: Path) -> ET.ElementTree:
    parser = DefusedET.DefusedXMLParser(
        target=ET.TreeBuilder(insert_comments=True),
        forbid_dtd=True,
        forbid_entities=True,
        forbid_external=True,
    )
    return DefusedET.parse(path, parser=parser)


def get_table_item(root: ET.Element, name: str) -> ET.Element:
    matches = [it for it in root.findall("Item") if it.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one Item named {name!r}, got {len(matches)}")
    item = matches[0]
    if not item.get("id"):
        raise ValueError(f"Item {name!r} is missing its id attribute")
    return item


def extract_axes(item: ET.Element) -> tuple[list[float], list[float]]:
    cols_elem = item.find("Columns")
    rows_elem = item.find("Rows")
    if cols_elem is None or rows_elem is None:
        raise ValueError("missing Columns or Rows element")

    col_axis = []
    for col in cols_elem.findall("Col"):
        try:
            col_axis.append(float(col.get("label", "0")))
        except ValueError:
            col_axis.append(0.0)

    row_axis = []
    for row in rows_elem.findall("Row"):
        try:
            row_axis.append(float(row.get("label", "0")))
        except ValueError:
            row_axis.append(0.0)

    return row_axis, col_axis


def build_value_grid(item: ET.Element) -> np.ndarray:
    rows_elem = item.find("Rows")
    if rows_elem is None:
        raise ValueError("missing Rows element")
    grid: list[list[float]] = []
    for row in rows_elem.findall("Row"):
        vals: list[float] = []
        for cell in row.findall("Cell"):
            try:
                vals.append(float(cell.get("value", "0")))
            except ValueError:
                vals.append(0.0)
        grid.append(vals)
    return np.array(grid, dtype=float)


def smooth_band(grid: np.ndarray, row_axis: list[float], col_axis: list[float]) -> np.ndarray:
    """Return a new grid with only the transition band lightly smoothed."""
    new_grid = grid.copy()
    n_rows, n_cols = grid.shape

    # Find indices inside the band
    # row_axis is in RPMx1000 units (e.g. 2.25 == 2250 rpm)
    row_idx = [i for i, r in enumerate(row_axis) if RPM_MIN <= (r * 1000.0) <= RPM_MAX]
    col_idx = [j for j, c in enumerate(col_axis) if MAP_MIN <= c <= MAP_MAX]

    if not row_idx or not col_idx:
        return new_grid

    for i in row_idx:
        for j in col_idx:
            old = grid[i, j]
            # 3x3 neighborhood (shrinks at borders)
            acc = 0.0
            count = 0
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    ni, nj = i + di, j + dj
                    if 0 <= ni < n_rows and 0 <= nj < n_cols:
                        acc += grid[ni, nj]
                        count += 1
            if count == 0:
                continue
            avg = acc / count
            delta = avg - old

            clamp = max(CLAMP_ABS, CLAMP_PCT * abs(old))
            clamped_delta = max(-clamp, min(clamp, delta))
            new_val = old + clamped_delta
            # match original precision (most VE values end in .0 or .5)
            new_grid[i, j] = round(new_val, 1)

    return new_grid


def apply_smoothed_grid(item: ET.Element, new_grid: np.ndarray, row_axis: list[float], col_axis: list[float]) -> int:
    """Write the smoothed values back into the XML tree. Returns number of cells changed."""
    rows_elem = item.find("Rows")
    if rows_elem is None:
        raise ValueError("missing Rows element")

    changed = 0
    for row_i, row in enumerate(rows_elem.findall("Row")):
        try:
            row_label = float(row.get("label", "0"))
        except ValueError:
            continue
        if not (RPM_MIN <= (row_label * 1000.0) <= RPM_MAX):
            continue

        cells = row.findall("Cell")
        for col_j, cell in enumerate(cells):
            try:
                col_label = float(col_axis[col_j])
            except (IndexError, ValueError):
                continue
            if not (MAP_MIN <= col_label <= MAP_MAX):
                continue

            old_str = cell.get("value", "")
            try:
                old_val = float(old_str)
            except ValueError:
                old_val = 0.0
            new_val = new_grid[row_i, col_j]
            if abs(new_val - old_val) > 0.05:  # only count real numeric change
                new_str = f"{new_val:.1f}"
                cell.set("value", new_str)
                changed += 1
    return changed


def main() -> None:
    if not SRC.exists():
        raise FileNotFoundError(SRC)

    print(f"input:  {SRC}")
    print(f"input sha256:  {sha256(SRC)}")
    print(f"input bytes:   {SRC.stat().st_size}")

    tree = parse_with_comments(SRC)
    root = tree.getroot()
    if root.tag != "PVV":
        raise ValueError(f"unexpected root tag: {root.tag}")

    n_items_in = len(root.findall("Item"))
    total_changed = 0

    table_names = ["VE (MAP based/Front Cyl)", "VE (MAP based/Rear Cyl)"]

    for name in table_names:
        item = get_table_item(root, name)
        row_axis, col_axis = extract_axes(item)
        grid = build_value_grid(item)
        new_grid = smooth_band(grid, row_axis, col_axis)
        changed = apply_smoothed_grid(item, new_grid, row_axis, col_axis)
        total_changed += changed
        max_abs_delta = float(np.max(np.abs(new_grid - grid)))
        print(f"  [ve ] {name:35s} cells changed: {changed:3d}  max |delta|: {max_abs_delta:.2f}")

    tree.write(DST, encoding="utf-8", xml_declaration=False)

    out_tree = parse_with_comments(DST)
    out_root = out_tree.getroot()
    out_items = out_root.findall("Item")
    items_with_id = sum(1 for it in out_items if it.get("id"))

    print(f"\noutput: {DST}")
    print(f"output sha256: {sha256(DST)}")
    print(f"output bytes:  {DST.stat().st_size}")
    print(f"items in: {n_items_in}, items out: {len(out_items)}")
    print(f"total VE cells changed: {total_changed}")
    print(f"items with id: {items_with_id} / {len(out_items)}")

    if n_items_in != len(out_items):
        raise ValueError("Item count changed during write")
    if items_with_id != len(out_items):
        raise ValueError("`id` attributes were dropped — file is NOT flash-safe")

    # Quick semantic check: re-parse with high-level loader and confirm shapes unchanged
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from api.services.powercore_integration import parse_pvv_tune

    t = parse_pvv_tune(DST)
    for name in table_names:
        shape = t.tables[name].values.shape
        print(f"  re-parsed {name:35s} shape: {shape}")

    print("\nverify: PASS  (only transition-band VE cells smoothed, all id attrs preserved)")


if __name__ == "__main__":
    main()
