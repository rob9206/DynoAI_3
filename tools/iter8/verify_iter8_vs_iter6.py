"""Verify iter_8_patched.pvv against iter_6_patched.pvv.

Expected differences:
  - Spark Advance Front/Rear: +2 deg only at RPM 4.5/5.0/5.5 and MAP=100 kPa.
  - VE Front/Rear: smoothed only at RPM 1.5-5.0 and TPS 0-60.

Protected:
  - WOT VE TPS 80/100 columns unchanged.
  - Spark 5500/95 kPa knock notch unchanged.
  - All non spark/VE tables byte-identical.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ITER_DIR = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations"
)
ITER6 = ITER_DIR / "iter_6" / "patch" / "iter_6_patched.pvv"
ITER8 = ITER_DIR / "iter_8" / "patch" / "iter_8_patched.pvv"

SPARK_TABLES = ("Spark Advance (Front Cyl)", "Spark Advance (Rear Cyl)")
VE_TABLES = ("VE (TPS based/Front Cyl)", "VE (TPS based/Rear Cyl)")
EXPECTED_CHANGED = sorted([*SPARK_TABLES, *VE_TABLES])
SPARK_RPM_K = {4.5, 5.0, 5.5}
SPARK_MAP_KPA = 100.0
SPARK_DELTA = 2.0
VE_RPM_LO = 1.5
VE_RPM_HI = 5.0
VE_TPS_LO = 0.0
VE_TPS_HI = 60.0
VE_MAX_FRAC = 0.03


def items_by_name(path: Path) -> dict[str, ET.Element]:
    root = ET.parse(str(path)).getroot()
    return {item.get("name", ""): item for item in root.findall("Item")}


def read_table(item: ET.Element) -> tuple[list[float], list[float], list[list[float]]]:
    cols = item.find("Columns")
    rows = item.find("Rows")
    if cols is None or rows is None:
        raise RuntimeError(f"{item.get('name')} missing Columns/Rows")
    col_axis = [float(col.get("label", "0") or "0") for col in cols.findall("Col")]
    row_axis: list[float] = []
    grid: list[list[float]] = []
    for row in rows.findall("Row"):
        row_axis.append(float(row.get("label", "0") or "0"))
        grid.append([float(cell.get("value", "0") or "0") for cell in row.findall("Cell")])
    return row_axis, col_axis, grid


def verify_spark(base_items: dict[str, ET.Element], new_items: dict[str, ET.Element]) -> int:
    changed_cells = 0
    for table in SPARK_TABLES:
        base_rows, base_cols, base_grid = read_table(base_items[table])
        new_rows, new_cols, new_grid = read_table(new_items[table])
        if base_rows != new_rows or base_cols != new_cols:
            raise RuntimeError(f"{table}: axes changed")
        for r, rpm_k in enumerate(base_rows):
            for c, map_kpa in enumerate(base_cols):
                delta = new_grid[r][c] - base_grid[r][c]
                if abs(delta) < 1e-9:
                    if abs(rpm_k - 5.5) < 1e-9 and abs(map_kpa - 95.0) < 1e-9:
                        print(
                            f"  PRESERVED: {table} knock notch rpm=5500 map=95 "
                            f"value={base_grid[r][c]:.1f}"
                        )
                    continue
                changed_cells += 1
                if rpm_k not in SPARK_RPM_K:
                    raise RuntimeError(f"{table}: unexpected spark RPM change rpm={rpm_k}")
                if abs(map_kpa - SPARK_MAP_KPA) > 1e-9:
                    raise RuntimeError(f"{table}: unexpected spark MAP change map={map_kpa}")
                if abs(delta - SPARK_DELTA) > 1e-6:
                    raise RuntimeError(
                        f"{table}: expected +{SPARK_DELTA}, got {delta:+.3f} "
                        f"at rpm={rpm_k} map={map_kpa}"
                    )
    if changed_cells != 42:
        raise RuntimeError(f"expected 42 spark cells, got {changed_cells}")
    return changed_cells


def verify_ve(base_items: dict[str, ET.Element], new_items: dict[str, ET.Element]) -> int:
    changed_cells = 0
    for table in VE_TABLES:
        base_rows, base_cols, base_grid = read_table(base_items[table])
        new_rows, new_cols, new_grid = read_table(new_items[table])
        if base_rows != new_rows or base_cols != new_cols:
            raise RuntimeError(f"{table}: axes changed")
        for r, rpm_k in enumerate(base_rows):
            for c, tps in enumerate(base_cols):
                base = base_grid[r][c]
                delta = new_grid[r][c] - base
                if abs(delta) < 1e-9:
                    continue
                changed_cells += 1
                if not (VE_RPM_LO <= rpm_k <= VE_RPM_HI and VE_TPS_LO <= tps <= VE_TPS_HI):
                    raise RuntimeError(
                        f"{table}: VE change outside smoothing scope rpm={rpm_k} tps={tps}"
                    )
                if tps >= 80.0:
                    raise RuntimeError(f"{table}: WOT VE changed at rpm={rpm_k} tps={tps}")
                frac = abs(delta) / abs(base) if abs(base) > 1e-9 else 0.0
                if frac > VE_MAX_FRAC + 1e-6:
                    raise RuntimeError(
                        f"{table}: VE delta exceeds cap at rpm={rpm_k} tps={tps}: {frac:.4f}"
                    )
    if changed_cells != 179:
        raise RuntimeError(f"expected 179 VE cells, got {changed_cells}")
    return changed_cells


def main() -> int:
    base_items = items_by_name(ITER6)
    new_items = items_by_name(ITER8)
    if set(base_items) != set(new_items):
        raise RuntimeError("item sets differ")

    changed_tables = sorted(
        name for name in base_items if ET.tostring(base_items[name]) != ET.tostring(new_items[name])
    )
    print(f"changed tables: {changed_tables}")
    if changed_tables != EXPECTED_CHANGED:
        raise RuntimeError(f"expected changed tables {EXPECTED_CHANGED}, got {changed_tables}")

    spark_cells = verify_spark(base_items, new_items)
    ve_cells = verify_ve(base_items, new_items)
    print(f"OK: spark cells changed = {spark_cells}, all +2 deg in target WOT cells")
    print(f"OK: VE cells changed = {ve_cells}, all in smoothing scope and <=3%")
    print("OK: all other tables byte-identical to iter_6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
