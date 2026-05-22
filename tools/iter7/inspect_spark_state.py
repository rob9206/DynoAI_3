"""Print Spark Advance Front/Rear at the WOT cells that matter for iter_7.

Compares dynojet_stage (factory baseline), iter_3/iter_6 (current flashed),
and shows the deg already added, plus headroom vs knock cap.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ITER_DIR = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations"
)
BASE_DIR = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\base_tune"
)
DYNOJET = BASE_DIR / "dynojet_stage.pvv"
ITER3 = ITER_DIR / "iter_3" / "patch" / "iter_3_patched.pvv"
ITER6 = ITER_DIR / "iter_6" / "patch" / "iter_6_patched.pvv"

ROW_AXIS_DESC = "rpm/1000"
COL_AXIS_DESC = "tps_pct"


def load_table(p: Path, name: str) -> tuple[list[float], list[float], list[list[float]]]:
    root = ET.parse(str(p)).getroot()
    item = next(it for it in root.findall("Item") if it.get("name") == name)
    cols = item.find("Columns")
    rows = item.find("Rows")
    col_axis = [float(c.get("label", "0") or "0") for c in cols.findall("Col")]
    row_axis: list[float] = []
    grid: list[list[float]] = []
    for r in rows.findall("Row"):
        row_axis.append(float(r.get("label", "0") or "0"))
        grid.append([float(c.get("value", "0") or "0") for c in r.findall("Cell")])
    return row_axis, col_axis, grid


def print_strip(label: str, p: Path, name: str, rpm_lo: float, rpm_hi: float, tps_lo: float):
    rax, cax, grid = load_table(p, name)
    print(f"\n=== {label} :: {name} ({p.name}) ===")
    print(f"     {'rpm':>5} | " + " ".join(f"{c:>5.0f}" for c in cax if c >= tps_lo))
    for r, rpm_k in enumerate(rax):
        rpm = rpm_k * 1000.0
        if not (rpm_lo <= rpm <= rpm_hi):
            continue
        cells = [grid[r][c] for c, v in enumerate(cax) if v >= tps_lo]
        print(f"     {rpm:>5.0f} | " + " ".join(f"{x:>5.1f}" for x in cells))


def diff_strip(p_a: Path, p_b: Path, name: str, rpm_lo: float, rpm_hi: float, tps_lo: float):
    ar, ac, ag = load_table(p_a, name)
    br, bc, bg = load_table(p_b, name)
    print(f"\n=== diff {p_a.name} -> {p_b.name} :: {name} (deg added) ===")
    print(f"     {'rpm':>5} | " + " ".join(f"{c:>5.0f}" for c in ac if c >= tps_lo))
    for r, rpm_k in enumerate(ar):
        rpm = rpm_k * 1000.0
        if not (rpm_lo <= rpm <= rpm_hi):
            continue
        deltas = [bg[r][c] - ag[r][c] for c, v in enumerate(ac) if v >= tps_lo]
        print(f"     {rpm:>5.0f} | " + " ".join(f"{d:>+5.1f}" for d in deltas))


def main() -> int:
    for label, fp in (("dynojet_stage", DYNOJET), ("iter_3 = iter_6", ITER6)):
        for tbl in ("Spark Advance (Front Cyl)", "Spark Advance (Rear Cyl)"):
            print_strip(label, fp, tbl, 2500, 6000, 60)

    print("\n\n--- Cam-zone advance applied by iter_2/3/6 (vs Dynojet) ---")
    for tbl in ("Spark Advance (Front Cyl)", "Spark Advance (Rear Cyl)"):
        diff_strip(DYNOJET, ITER6, tbl, 2500, 6000, 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
