"""Trace Spark Advance Front/Rear across iter_3 / iter_8 / iter_11.

Confirms which timing adjustments are present in iter_11_patched.pvv.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ITERS = {
    "iter_3":  Path("vehicles/ryantitus_fatboy_cvo/sessions/2026-05-10_4thgear_baseline/iterations/iter_3/patch/iter_3_patched.pvv"),
    "iter_6":  Path("vehicles/ryantitus_fatboy_cvo/sessions/2026-05-10_4thgear_baseline/iterations/iter_6/patch/iter_6_patched.pvv"),
    "iter_7":  Path("vehicles/ryantitus_fatboy_cvo/sessions/2026-05-10_4thgear_baseline/iterations/iter_7/patch/iter_7_patched.pvv"),
    "iter_8":  Path("vehicles/ryantitus_fatboy_cvo/sessions/2026-05-10_4thgear_baseline/iterations/iter_8/patch/iter_8_patched.pvv"),
    "iter_9":  Path("vehicles/ryantitus_fatboy_cvo/sessions/2026-05-10_4thgear_baseline/iterations/iter_9/patch/iter_9_patched.pvv"),
    "iter_10": Path("vehicles/ryantitus_fatboy_cvo/sessions/2026-05-10_4thgear_baseline/iterations/iter_10/patch/iter_10_patched.pvv"),
    "iter_11": Path("vehicles/ryantitus_fatboy_cvo/sessions/2026-05-10_4thgear_baseline/iterations/iter_11/patch/iter_11_patched.pvv"),
    "base":    Path("vehicles/ryantitus_fatboy_cvo/sessions/2026-05-10_4thgear_baseline/base_tune/base.pvv"),
}

TARGETS = ["Spark Advance (Front Cyl)", "Spark Advance (Rear Cyl)"]


def grid(path: Path, table_name: str) -> tuple[list[str], list[str], list[list[float]]]:
    if not path.exists():
        return [], [], []
    root = ET.parse(str(path)).getroot()
    item = next((it for it in root.findall("Item") if it.get("name") == table_name), None)
    if item is None:
        return [], [], []
    cols = item.find("Columns")
    rows = item.find("Rows")
    if cols is None or rows is None:
        return [], [], []
    col_labels = [c.get("label", "") for c in cols.findall("Col")]
    row_labels = [r.get("label", "") for r in rows.findall("Row")]
    grid = []
    for r in rows.findall("Row"):
        grid.append([float(c.get("value", "0")) for c in r.findall("Cell")])
    return col_labels, row_labels, grid


def diff_grids(a: list[list[float]], b: list[list[float]]) -> list[tuple[int, int, float, float, float]]:
    out = []
    for i, (ra, rb) in enumerate(zip(a, b)):
        for j, (va, vb) in enumerate(zip(ra, rb)):
            d = vb - va
            if abs(d) > 0.001:
                out.append((i, j, va, vb, d))
    return out


def main() -> int:
    for tbl in TARGETS:
        print(f"\n{'='*70}\n{tbl}\n{'='*70}")

        # Quick presence check
        for name, p in ITERS.items():
            cols, rows, g = grid(p, tbl)
            if not g:
                print(f"  {name}: TABLE NOT FOUND in {p}")
            else:
                rows_n = len(g)
                cols_n = len(g[0])
                amax = max(max(r) for r in g)
                amin = min(min(r) for r in g)
                amean = sum(sum(r) for r in g) / (rows_n * cols_n)
                print(f"  {name}: {rows_n}x{cols_n} grid  range=[{amin:.1f}, {amax:.1f}]  mean={amean:.2f}")

        # Diff iter_3 -> iter_8 (the +2 deg WOT timing change)
        _, _, g3 = grid(ITERS["iter_3"], tbl)
        _, _, g8 = grid(ITERS["iter_8"], tbl)
        _, _, g11 = grid(ITERS["iter_11"], tbl)
        col_labels, row_labels, _ = grid(ITERS["iter_3"], tbl)

        if g3 and g8:
            d_3_8 = diff_grids(g3, g8)
            print(f"\n  iter_3 -> iter_8 diffs: {len(d_3_8)} cells changed")
            for i, j, va, vb, d in d_3_8:
                rl = row_labels[i] if i < len(row_labels) else f"r{i}"
                cl = col_labels[j] if j < len(col_labels) else f"c{j}"
                print(f"    row={rl}  col={cl}  {va:.1f} -> {vb:.1f}  ({d:+.1f} deg)")

        if g8 and g11:
            d_8_11 = diff_grids(g8, g11)
            print(f"\n  iter_8 -> iter_11 diffs: {len(d_8_11)} cells changed")
            for i, j, va, vb, d in d_8_11[:20]:
                rl = row_labels[i] if i < len(row_labels) else f"r{i}"
                cl = col_labels[j] if j < len(col_labels) else f"c{j}"
                print(f"    row={rl}  col={cl}  {va:.1f} -> {vb:.1f}  ({d:+.1f} deg)")

        if g3 and g11:
            d_3_11 = diff_grids(g3, g11)
            print(f"\n  iter_3 -> iter_11 diffs: {len(d_3_11)} cells changed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
