"""Quantify roughness in iter_6 VE tables to decide a smoothing scope.

For each cell we compute:
  - the local 3x3 mean (excluding the cell itself when neighbours exist)
  - the residual (cell - local mean)
  - the absolute residual

Cells with high abs residual are 'spikes' that smoothing would round off.

Output: per-cell residual heatmap printed for both cyls, plus a summary of
biggest spikes by absolute residual.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ITER_DIR = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations"
)
ITER6 = ITER_DIR / "iter_6" / "patch" / "iter_6_patched.pvv"


def read_table(p: Path, name: str) -> tuple[list[float], list[float], list[list[float]]]:
    root = ET.parse(str(p)).getroot()
    item = next(it for it in root.findall("Item") if it.get("name") == name)
    cols = item.find("Columns")
    rows = item.find("Rows")
    col_axis = [float(c.get("label", "0") or "0") for c in cols.findall("Col")]
    row_axis: list[float] = []
    grid: list[list[float]] = []
    for row in rows.findall("Row"):
        row_axis.append(float(row.get("label", "0") or "0"))
        grid.append([float(c.get("value", "0") or "0") for c in row.findall("Cell")])
    return row_axis, col_axis, grid


def local_mean_3x3(grid: list[list[float]], r: int, c: int) -> float:
    R = len(grid)
    C = len(grid[0])
    s = 0.0
    n = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < R and 0 <= cc < C:
                s += grid[rr][cc]
                n += 1
    return s / n if n else grid[r][c]


def analyze(label: str, grid: list[list[float]], row_axis: list[float], col_axis: list[float]) -> None:
    R = len(grid)
    C = len(grid[0])
    spikes: list[tuple[float, int, int, float, float, float]] = []
    print(f"\n=== {label} residuals (cell - 3x3 neighbour mean) ===")
    print("rpm\\tps  " + "  ".join(f"{c:>5.0f}" for c in col_axis))
    for r in range(R):
        rpm = int(row_axis[r] * 1000)
        line = f"{rpm:>5d}    "
        for c in range(C):
            mean = local_mean_3x3(grid, r, c)
            res = grid[r][c] - mean
            line += f"  {res:+5.1f}"
            if abs(res) >= 1.5:
                spikes.append((abs(res), r, c, grid[r][c], mean, res))
        print(line)

    spikes.sort(reverse=True)
    print(f"\n  spikes with |residual| >= 1.5 (top 20):")
    for abs_res, r, c, val, mean, res in spikes[:20]:
        print(
            f"    rpm={int(row_axis[r] * 1000):>4d}  tps={col_axis[c]:>5.0f}  "
            f"VE={val:>6.2f}  neigh_mean={mean:>6.2f}  resid={res:+.2f}"
        )
    print(f"  total cells with |residual| >= 1.0: "
          f"{sum(1 for r in range(R) for c in range(C) if abs(grid[r][c] - local_mean_3x3(grid, r, c)) >= 1.0)}")
    print(f"  total cells with |residual| >= 1.5: {len(spikes)}")
    print(f"  total cells with |residual| >= 2.5: "
          f"{sum(1 for x in spikes if x[0] >= 2.5)}")


def main() -> int:
    for tbl in ("VE (TPS based/Front Cyl)", "VE (TPS based/Rear Cyl)"):
        rax, cax, grid = read_table(ITER6, tbl)
        analyze(tbl, grid, rax, cax)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
