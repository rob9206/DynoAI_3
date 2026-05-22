"""Verify iter_7_patched.pvv differs from iter_6_patched.pvv ONLY in Spark Advance.

Confirms:
  1. iter_7 has the same item set as iter_6
  2. The exact 42 spark cells changed match the design (RPM 4.5/5.0/5.5 x MAP 100 x 2 cyl)
  3. Every other table is byte-identical
  4. Each spark delta is exactly +1.0 deg
  5. The 5500/95 kPa knock notch is preserved
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ITER_DIR = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations"
)
ITER6 = ITER_DIR / "iter_6" / "patch" / "iter_6_patched.pvv"
ITER7 = ITER_DIR / "iter_7" / "patch" / "iter_7_patched.pvv"

EXPECTED_RPM_K = {4.5, 5.0, 5.5}
EXPECTED_MAP_KPA = 100.0
EXPECTED_DELTA = 1.0
SPARK_TABLES = ("Spark Advance (Front Cyl)", "Spark Advance (Rear Cyl)")
KNOCK_NOTCH_RPM_K = 5.5
KNOCK_NOTCH_MAP_KPA = 95.0


def items_by_name(p: Path) -> dict[str, ET.Element]:
    return {it.get("name", ""): it for it in ET.parse(str(p)).getroot().findall("Item")}


def read_table(item: ET.Element):
    cols = item.find("Columns")
    rows = item.find("Rows")
    col_axis = [float(c.get("label", "0") or "0") for c in cols.findall("Col")]
    row_axis: list[float] = []
    grid: list[list[float]] = []
    for row in rows.findall("Row"):
        row_axis.append(float(row.get("label", "0") or "0"))
        grid.append([float(c.get("value", "0") or "0") for c in row.findall("Cell")])
    return row_axis, col_axis, grid


def main() -> int:
    a = items_by_name(ITER6)
    b = items_by_name(ITER7)
    if set(a) != set(b):
        print(f"FAIL: item sets differ. only_in_6={set(a) - set(b)} only_in_7={set(b) - set(a)}")
        return 1

    changed = [n for n in a if ET.tostring(a[n]) != ET.tostring(b[n])]
    print(f"changed tables: {changed}")
    if sorted(changed) != sorted(SPARK_TABLES):
        print(f"FAIL: expected only {SPARK_TABLES}, got {changed}")
        return 1

    total_changed_cells = 0
    for tbl in SPARK_TABLES:
        a_row, a_col, ag = read_table(a[tbl])
        b_row, b_col, bg = read_table(b[tbl])
        if a_row != b_row or a_col != b_col:
            print(f"FAIL: {tbl} axis differs")
            return 1
        for r, rpm_k in enumerate(a_row):
            for c, kpa in enumerate(a_col):
                d = bg[r][c] - ag[r][c]
                if abs(d) < 1e-9:
                    if abs(rpm_k - KNOCK_NOTCH_RPM_K) < 1e-9 and abs(kpa - KNOCK_NOTCH_MAP_KPA) < 1e-9:
                        print(f"  PRESERVED: {tbl} knock notch at rpm={rpm_k} kpa={kpa}: "
                              f"{ag[r][c]:.1f} (unchanged)")
                    continue
                total_changed_cells += 1
                if rpm_k not in EXPECTED_RPM_K:
                    print(f"FAIL: unexpected RPM change at {tbl} rpm={rpm_k} kpa={kpa}")
                    return 1
                if abs(kpa - EXPECTED_MAP_KPA) > 1e-9:
                    print(f"FAIL: unexpected MAP change at {tbl} rpm={rpm_k} kpa={kpa}")
                    return 1
                if abs(d - EXPECTED_DELTA) > 1e-3:
                    print(f"FAIL: delta {d:+.2f} != {EXPECTED_DELTA} at {tbl} rpm={rpm_k} kpa={kpa}")
                    return 1

    if total_changed_cells != 42:
        print(f"FAIL: expected 42 cells changed (3 rpm x 7 cols x 2 cyl), got {total_changed_cells}")
        return 1

    print(f"OK: 42 cells changed, all +{EXPECTED_DELTA} deg, knock notch preserved.")
    print("OK: every other table is byte-identical to iter_6.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
