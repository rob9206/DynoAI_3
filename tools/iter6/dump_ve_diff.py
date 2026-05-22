"""Print VE Front/Rear tables for exported, iter_6, iter_3, side-by-side at 100kPa column."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ITER_DIR = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations"
)
EXPORTED = ITER_DIR / "iter_6" / "patch" / "exporte6.pvv"
ITER6 = ITER_DIR / "iter_6" / "patch" / "iter_6_patched.pvv"
ITER3 = ITER_DIR / "iter_3" / "patch" / "iter_3_patched.pvv"


def parse_ve(p: Path, name: str) -> tuple[list[float], list[float], list[list[float]]]:
    root = ET.parse(str(p)).getroot()
    item = next((it for it in root.findall("Item") if it.get("name") == name), None)
    if item is None:
        raise KeyError(name)
    cols_elem = item.find("Columns")
    rows_elem = item.find("Rows")
    col_axis = [float(c.get("label", "0") or "0") for c in cols_elem.findall("Col")]
    row_axis: list[float] = []
    grid: list[list[float]] = []
    for row in rows_elem.findall("Row"):
        row_axis.append(float(row.get("label", "0") or "0"))
        grid.append([float(c.get("value", "0") or "0") for c in row.findall("Cell")])
    return row_axis, col_axis, grid


def print_table(label: str, p: Path, name: str) -> None:
    rows, cols, grid = parse_ve(p, name)
    print(f"\n=== {label} :: {name} ===  ({p.name})")
    header = "rpm_k\\tps  " + "  ".join(f"{c:>5.0f}" for c in cols)
    print(header)
    for r, rpm_k in enumerate(rows):
        line = f"{rpm_k:>5.2f}      " + "  ".join(f"{grid[r][c]:>5.1f}" for c in range(len(cols)))
        print(line)


def diff_grids(label: str, a: Path, b: Path, table: str) -> None:
    ar, ac, ag = parse_ve(a, table)
    br, bc, bg = parse_ve(b, table)
    print(f"\n=== diff {label} :: {table} (rows: rpm_k, cols: tps_pct) ===")
    print("Showing |delta| > 0.1.  Format = a -> b (delta%)")
    diffs: list[tuple[float, float, float, float, float]] = []
    for r in range(len(ar)):
        for c in range(len(ac)):
            d = bg[r][c] - ag[r][c]
            if abs(d) < 0.1:
                continue
            pct = (d / ag[r][c] * 100.0) if abs(ag[r][c]) > 1e-9 else 0.0
            diffs.append((ar[r], ac[c], ag[r][c], bg[r][c], pct))
    diffs.sort(key=lambda x: (x[0], x[1]))
    for rpm_k, tps, av, bv, pct in diffs:
        print(f"  rpm={int(rpm_k * 1000):>4d}  tps={tps:>5.0f}  {av:>6.2f} -> {bv:>6.2f}  ({pct:+.1f}%)")


def main() -> int:
    print(">>> EXPORTED tune (read off ECU) vs iter_6 (your patch on disk)")
    diff_grids("exported -> iter_6", EXPORTED, ITER6, "VE (TPS based/Front Cyl)")
    diff_grids("exported -> iter_6", EXPORTED, ITER6, "VE (TPS based/Rear Cyl)")
    print("\n\n>>> EXPORTED tune (read off ECU) vs iter_3 (proven 91-92 hp baseline)")
    diff_grids("exported -> iter_3", EXPORTED, ITER3, "VE (TPS based/Front Cyl)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
