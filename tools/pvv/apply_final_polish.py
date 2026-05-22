r"""Final polish pass: TPS VE smoothing and High Gear throttle sync.

1. Smooths VE (TPS based/Front Cyl) and VE (TPS based/Rear Cyl) in the
   transition band (RPM 1250-4000, TPS 5-40%) using the same 3x3 algorithm.
2. Updates Throttle Blade Control High Gear to match the snappy Low Gear table,
   interpolating across the different X-axes to ensure safe ECU behavior.

Input:
    c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off_wheelieA_smooth_ve1.pvv
Output:
    c:\Users\dawso\Downloads\fuelmoto110lowrider_final.pvv
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from defusedxml import ElementTree as DefusedET

SRC = Path(r"c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off_wheelieA_smooth_ve1.pvv")
DST = Path(r"c:\Users\dawso\Downloads\fuelmoto110lowrider_final.pvv")

# TPS Smoothing band (inclusive)
RPM_MIN = 1250.0
RPM_MAX = 4000.0
TPS_MIN = 5.0
TPS_MAX = 40.0

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


def smooth_tps_band(grid: np.ndarray, row_axis: list[float], col_axis: list[float]) -> np.ndarray:
    new_grid = grid.copy()
    n_rows, n_cols = grid.shape

    row_idx = [i for i, r in enumerate(row_axis) if RPM_MIN <= (r * 1000.0) <= RPM_MAX]
    col_idx = [j for j, c in enumerate(col_axis) if TPS_MIN <= c <= TPS_MAX]

    if not row_idx or not col_idx:
        return new_grid

    for i in row_idx:
        for j in col_idx:
            old = grid[i, j]
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
            new_grid[i, j] = round(new_val, 1)

    return new_grid


def apply_grid(item: ET.Element, new_grid: np.ndarray, row_axis: list[float], col_axis: list[float],
               row_cond=None, col_cond=None) -> int:
    rows_elem = item.find("Rows")
    if rows_elem is None:
        raise ValueError("missing Rows element")

    changed = 0
    for row_i, row in enumerate(rows_elem.findall("Row")):
        if row_cond and not row_cond(row_axis[row_i]):
            continue

        cells = row.findall("Cell")
        for col_j, cell in enumerate(cells):
            if col_cond and not col_cond(col_axis[col_j]):
                continue

            old_str = cell.get("value", "")
            try:
                old_val = float(old_str)
            except ValueError:
                old_val = 0.0
            new_val = new_grid[row_i, col_j]
            if abs(new_val - old_val) > 0.05:
                # Some tables use 1 decimal (VE), some use 1 decimal (Throttle)
                new_str = f"{new_val:.1f}" if new_val == round(new_val, 1) else f"{new_val:.2f}".rstrip("0").rstrip(".")
                if "." not in new_str and new_val == float(round(new_val)):
                   new_str = str(int(new_val)) # Throttle table might use ints where possible
                cell.set("value", new_str)
                changed += 1
    return changed


def interpolate_throttle(low_grid: np.ndarray, low_cols: list[float], high_cols: list[float]) -> np.ndarray:
    n_rows = low_grid.shape[0]
    high_grid = np.zeros((n_rows, len(high_cols)))
    for i in range(n_rows):
        high_grid[i, :] = np.interp(high_cols, low_cols, low_grid[i, :])
    return high_grid


def main() -> None:
    if not SRC.exists():
        raise FileNotFoundError(SRC)

    print(f"input:  {SRC}")
    print(f"input sha256:  {sha256(SRC)}")

    tree = parse_with_comments(SRC)
    root = tree.getroot()
    if root.tag != "PVV":
        raise ValueError(f"unexpected root tag: {root.tag}")

    n_items_in = len(root.findall("Item"))
    total_changed = 0

    # 1. TPS VE Smoothing
    for name in ["VE (TPS based/Front Cyl)", "VE (TPS based/Rear Cyl)"]:
        item = get_table_item(root, name)
        row_axis, col_axis = extract_axes(item)
        grid = build_value_grid(item)
        new_grid = smooth_tps_band(grid, row_axis, col_axis)
        changed = apply_grid(item, new_grid, row_axis, col_axis,
                             row_cond=lambda r: RPM_MIN <= (r * 1000.0) <= RPM_MAX,
                             col_cond=lambda c: TPS_MIN <= c <= TPS_MAX)
        total_changed += changed
        max_abs_delta = float(np.max(np.abs(new_grid - grid)))
        print(f"  [ve ] {name:35s} cells changed: {changed:3d}  max |delta|: {max_abs_delta:.2f}")

    # 2. Sync High Gear Throttle from Low Gear
    item_low = get_table_item(root, "Throttle Blade Control Low Gear")
    row_ax_low, col_ax_low = extract_axes(item_low)
    grid_low = build_value_grid(item_low)

    item_high = get_table_item(root, "Throttle Blade Control High Gear")
    row_ax_high, col_ax_high = extract_axes(item_high)
    grid_high = build_value_grid(item_high)

    if row_ax_low[:8] != row_ax_high[:8]:
        raise ValueError("Throttle tables have different core RPM axes")

    new_grid_high = interpolate_throttle(grid_low, col_ax_low, col_ax_high)
    
    # We round high gear values to 1 decimal to match typical DBW resolution
    new_grid_high = np.round(new_grid_high, 1)

    changed_throttle = apply_grid(item_high, new_grid_high, row_ax_high, col_ax_high)
    total_changed += changed_throttle
    print(f"  [dbw] Throttle Blade Control High Gear  cells changed: {changed_throttle:3d}")

    tree.write(DST, encoding="utf-8", xml_declaration=False)

    out_tree = parse_with_comments(DST)
    out_items = out_tree.getroot().findall("Item")
    items_with_id = sum(1 for it in out_items if it.get("id"))

    print(f"\noutput: {DST}")
    print(f"output sha256: {sha256(DST)}")
    print(f"items in: {n_items_in}, items out: {len(out_items)}")
    print(f"total cells changed: {total_changed}")
    print(f"items with id: {items_with_id} / {len(out_items)}")

    if n_items_in != len(out_items):
        raise ValueError("Item count changed during write")
    if items_with_id != len(out_items):
        raise ValueError("`id` attributes were dropped — file is NOT flash-safe")

    print("\nverify: PASS")

if __name__ == "__main__":
    main()
