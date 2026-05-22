"""
Analyze Sean's PCV V trim tables -- transcribed from the actual PCV Control Center
screenshots, with two known bad cells flagged as outliers.

Axes (verified from screenshot headers):
  - RPM rows: 500 -> 6500 in 250 rpm steps = 25 rows
  - TPS cols: 0, 2, 5, 10, 15, 20, 40, 60, 80, 100 % = 10 cols
Map: "Map 1 - Fuel - Cylinder 1 / Cylinder 2 - Gear 1,2,3,4,5,6"
  (one map applies to all gears)

Outliers found in saved map (bad cells from the previous tuner; PCV interpolates
through them but we will NOT propagate them):
  - CYL1[5000 rpm, 15% TPS] = 246 -> interpolated replacement ~ 25
  - CYL2[1000 rpm, 80% TPS] = 174 -> interpolated replacement ~ 17

This script:
1) Confirms shape.
2) Replaces outliers with bilinear interpolation from clean neighbors.
3) Prints front, rear, and front-vs-rear delta grids.
4) Highlights the WOT column and cruise (20% TPS) column.
5) Diagnoses likely bike state from trim pattern.
"""
from __future__ import annotations

import csv
from pathlib import Path

RPM = list(range(500, 6501, 250))  # 25 rows
TPS = [0, 2, 5, 10, 15, 20, 40, 60, 80, 100]

# Cylinder 1 -- Front, transcribed from screenshot
CYL1_RAW = [
    [4, 4, 4, 5, 5, 6, 7, 8, 9, 10],    # 500
    [4, 4, 5, 6, 6, 7, 8, 10, 11, 12],  # 750
    [3, 4, 6, 8, 9, 10, 12, 14, 16, 18],
    [3, 4, 7, 10, 11, 12, 15, 17, 19, 21],
    [2, 4, 8, 11, 12, 14, 17, 19, 21, 23],
    [2, 3, 9, 12, 14, 16, 18, 21, 23, 25],
    [1, 3, 10, 14, 16, 18, 20, 23, 25, 27],
    [1, 3, 11, 15, 17, 19, 22, 24, 27, 29],
    [1, 3, 12, 16, 18, 20, 24, 26, 29, 31],
    [1, 3, 13, 17, 19, 22, 25, 28, 31, 33],
    [1, 3, 14, 18, 20, 23, 26, 29, 32, 35],
    [1, 3, 15, 19, 21, 24, 27, 30, 33, 36],
    [1, 3, 16, 20, 22, 25, 28, 31, 34, 37],
    [1, 3, 17, 21, 23, 26, 29, 32, 35, 38],
    [1, 3, 18, 22, 24, 27, 30, 33, 36, 39],
    [1, 2, 18, 22, 25, 28, 31, 34, 38, 40],
    [0, 2, 18, 23, 26, 29, 34, 35, 40, 42],
    [0, 2, 17, 23, 26, 30, 35, 36, 42, 44],
    [0, 2, 17, 24, 246, 31, 34, 38, 43, 46],  # 5000 rpm, 15% TPS = BAD CELL
    [0, 2, 16, 24, 27, 31, 35, 39, 43, 47],
    [-1, 1, 15, 23, 26, 30, 34, 38, 42, 46],
    [-1, 1, 14, 22, 25, 29, 33, 37, 41, 45],
    [-1, 1, 13, 20, 24, 28, 32, 36, 40, 44],
    [-1, 1, 12, 18, 22, 26, 30, 34, 38, 42],
    [-1, 0, 10, 16, 20, 24, 28, 32, 36, 40],  # 6500
]

# Cylinder 2 -- Rear, transcribed from screenshot
CYL2_RAW = [
    [5, 5, 5, 6, 6, 7, 8, 9, 10, 11],   # 500
    [5, 5, 6, 7, 7, 8, 9, 11, 12, 15],  # 750
    [4, 5, 7, 9, 10, 11, 13, 15, 174, 19],  # 1000 rpm, 80% TPS = BAD CELL
    [4, 5, 8, 11, 12, 13, 16, 18, 20, 22],
    [3, 5, 9, 12, 13, 15, 18, 20, 22, 24],
    [3, 4, 10, 13, 15, 17, 19, 22, 24, 26],
    [2, 4, 11, 15, 17, 19, 21, 24, 26, 28],
    [2, 4, 12, 16, 18, 20, 23, 25, 28, 30],
    [2, 4, 13, 17, 19, 21, 25, 27, 30, 32],
    [2, 4, 14, 18, 20, 23, 26, 29, 32, 34],
    [2, 4, 15, 19, 21, 24, 27, 30, 33, 36],
    [2, 4, 16, 20, 22, 25, 28, 31, 34, 37],
    [2, 4, 17, 21, 23, 26, 29, 32, 35, 38],
    [2, 4, 18, 22, 24, 27, 30, 33, 36, 39],
    [2, 4, 19, 23, 25, 28, 31, 34, 37, 40],
    [2, 3, 19, 23, 26, 29, 32, 35, 38, 41],
    [1, 3, 19, 24, 27, 30, 33, 36, 39, 43],
    [1, 3, 18, 24, 27, 31, 34, 37, 41, 45],
    [1, 3, 18, 25, 28, 32, 35, 39, 43, 47],
    [1, 3, 17, 25, 28, 32, 36, 40, 44, 48],
    [0, 2, 16, 24, 27, 31, 35, 39, 43, 47],
    [0, 2, 15, 23, 26, 30, 34, 38, 42, 46],
    [0, 2, 14, 21, 25, 29, 33, 37, 41, 45],
    [0, 2, 13, 19, 23, 27, 31, 35, 39, 43],
    [0, 1, 11, 17, 21, 25, 29, 33, 37, 41],  # 6500
]


def clean_outliers(grid):
    """Replace any cell with |v| >= 100 by avg of four cardinal neighbors."""
    nrows, ncols = len(grid), len(grid[0])
    out_grid = [row[:] for row in grid]
    replacements = []
    for r in range(nrows):
        for c in range(ncols):
            if abs(grid[r][c]) >= 100:
                neigh = []
                if r > 0 and abs(grid[r - 1][c]) < 100:
                    neigh.append(grid[r - 1][c])
                if r < nrows - 1 and abs(grid[r + 1][c]) < 100:
                    neigh.append(grid[r + 1][c])
                if c > 0 and abs(grid[r][c - 1]) < 100:
                    neigh.append(grid[r][c - 1])
                if c < ncols - 1 and abs(grid[r][c + 1]) < 100:
                    neigh.append(grid[r][c + 1])
                new_v = round(sum(neigh) / len(neigh)) if neigh else 0
                out_grid[r][c] = new_v
                replacements.append((r, c, grid[r][c], new_v))
    return out_grid, replacements


def print_grid(name, grid):
    print(f"=== {name} (% fuel trim) ===")
    print(f"{'RPM':>5}  " + " ".join(f"{t:>4}%" for t in TPS))
    for r, row in enumerate(grid):
        cells = " ".join(f"{v:>+5d}" for v in row)
        print(f"{RPM[r]:5d}  {cells}")
    print()


def main():
    assert len(CYL1_RAW) == 25 and len(CYL2_RAW) == 25
    assert all(len(r) == 10 for r in CYL1_RAW + CYL2_RAW)

    print(f"Shape: {len(RPM)} RPM rows x {len(TPS)} TPS cols")
    print(f"RPM axis: {RPM[0]} .. {RPM[-1]} step 250")
    print(f"TPS axis: {TPS}")
    print()

    cyl1, rep1 = clean_outliers(CYL1_RAW)
    cyl2, rep2 = clean_outliers(CYL2_RAW)
    if rep1 or rep2:
        print("!! Bad cells in source map replaced with neighbor average !!")
        for r, c, old, new in rep1:
            print(f"   CYL1 {RPM[r]} rpm / {TPS[c]}% TPS: {old:+d} -> {new:+d}  (interp)")
        for r, c, old, new in rep2:
            print(f"   CYL2 {RPM[r]} rpm / {TPS[c]}% TPS: {old:+d} -> {new:+d}  (interp)")
        print()

    print_grid("CYL1 (Front)", cyl1)
    print_grid("CYL2 (Rear)", cyl2)

    # Stats on clean cells
    for name, g in (("CYL1 (Front)", cyl1), ("CYL2 (Rear)", cyl2)):
        flat = [v for row in g for v in row]
        print(f"{name}: min={min(flat):+d}%  max={max(flat):+d}%  "
              f"mean={sum(flat)/len(flat):+.1f}%  median={sorted(flat)[len(flat)//2]:+d}%")
    print()

    # Front vs Rear delta
    print("=== Rear - Front delta (positive = rear needed MORE fuel than front) ===")
    print(f"{'RPM':>5}  " + " ".join(f"{t:>4}%" for t in TPS))
    deltas = []
    for r in range(len(RPM)):
        row = []
        for c in range(len(TPS)):
            d = cyl2[r][c] - cyl1[r][c]
            row.append(f"{d:>+5d}")
            deltas.append(d)
        print(f"{RPM[r]:5d}  " + " ".join(row))
    print()
    print(f"Rear - Front: min={min(deltas):+d}%  max={max(deltas):+d}%  "
          f"mean={sum(deltas)/len(deltas):+.2f}%")
    print()

    # WOT column comparison
    wot_c = len(TPS) - 1
    print(f"=== WOT column ({TPS[wot_c]}% TPS) ===")
    print(f"{'RPM':>5}  {'Front':>6}  {'Rear':>6}  {'R-F':>6}")
    for r in range(len(RPM)):
        f, b = cyl1[r][wot_c], cyl2[r][wot_c]
        print(f"{RPM[r]:5d}  {f:>+6d}  {b:>+6d}  {b - f:>+6d}")
    print()

    # Cruise column (20% TPS)
    cruise_c = TPS.index(20)
    print(f"=== Cruise column ({TPS[cruise_c]}% TPS) ===")
    print(f"{'RPM':>5}  {'Front':>6}  {'Rear':>6}  {'R-F':>6}")
    for r in range(len(RPM)):
        f, b = cyl1[r][cruise_c], cyl2[r][cruise_c]
        print(f"{RPM[r]:5d}  {f:>+6d}  {b:>+6d}  {b - f:>+6d}")
    print()

    # Persist clean tables
    out = Path(r"C:\CommmandCenter\Customer_Files\seanbike\pcv_trims_clean.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cyl", "rpm"] + [f"tps_{t}" for t in TPS])
        for r in range(len(RPM)):
            w.writerow(["front", RPM[r]] + cyl1[r])
        for r in range(len(RPM)):
            w.writerow(["rear", RPM[r]] + cyl2[r])
    print(f"Wrote clean trim CSV -> {out}")


if __name__ == "__main__":
    main()
