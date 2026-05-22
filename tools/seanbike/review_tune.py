"""Comprehensive review of a PVV tune file.

Inspects scalars, VE tables, AFR/lambda targets, spark, enrichment tables,
decel enleanment, idle settings, and flags potential issues.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import NamedTuple

PVV_PATH = Path(r"C:\CommmandCenter\Customer_Files\seanbike\v3_inj30_decel_soft.pvv")


class TableInfo(NamedTuple):
    item_id: str
    name: str
    n_rows: int
    n_cols: int
    min_val: float | None
    max_val: float | None
    mean_val: float | None


def parse_scalar(root: ET.Element, item_id: str) -> float | None:
    for it in root.findall("Item"):
        if it.get("id") == item_id:
            cell = it.find("./Rows/Row/Cell")
            if cell is not None:
                try:
                    return float(cell.get("value", ""))
                except ValueError:
                    return None
    return None


def parse_table(root: ET.Element, item_id: str) -> TableInfo | None:
    for it in root.findall("Item"):
        if it.get("id") == item_id:
            name = it.get("name", "")
            rows = it.findall("./Rows/Row")
            if not rows:
                return None
            n_rows = len(rows)
            n_cols = len(rows[0].findall("Cell"))
            vals: list[float] = []
            for r in rows:
                for c in r.findall("Cell"):
                    try:
                        vals.append(float(c.get("value", "")))
                    except ValueError:
                        pass
            if vals:
                return TableInfo(
                    item_id=item_id,
                    name=name,
                    n_rows=n_rows,
                    n_cols=n_cols,
                    min_val=min(vals),
                    max_val=max(vals),
                    mean_val=sum(vals) / len(vals),
                )
    return None


def main() -> None:
    root = ET.parse(PVV_PATH).getroot()

    print("=" * 80)
    print(f"TUNE REVIEW: {PVV_PATH.name}")
    print("=" * 80)

    # Scalars
    print("\n--- SCALARS ---")
    inj = parse_scalar(root, "tbl_injector_size")
    disp = parse_scalar(root, "tbl_engine_displacement")
    stoich = parse_scalar(root, "tbl_stoich_afr")
    print(f"  injector_size:       {inj}")
    print(f"  engine_displacement: {disp}")
    print(f"  stoich_afr:          {stoich}")

    # Sanity gates
    print("\n--- SANITY GATES ---")
    issues = []
    if inj is not None:
        if not (3.5 <= inj <= 6.0) and not (20.0 <= inj <= 35.0):
            issues.append(f"injector_size {inj} looks suspicious (neither 3.5-6 nor 20-35 range)")
        elif inj < 20:
            issues.append(f"injector_size {inj} < 20 -- may be wrong units or wrong injector")
    if disp is not None:
        if not (85 <= disp <= 120):
            issues.append(f"displacement {disp} outside 85-120 CID range")
    if issues:
        for i in issues:
            print(f"  [WARN] {i}")
    else:
        print("  All scalars within expected ranges (or overridden).")

    # VE tables
    print("\n--- VE TABLES ---")
    for iid in ("tbl_ve_tps_based_front_cyl", "tbl_ve_tps_based_rear_cyl"):
        t = parse_table(root, iid)
        if t:
            print(f"  {t.item_id:40s} {t.n_rows:2d}x{t.n_cols:2d}  min={t.min_val:7.2f} max={t.max_val:7.2f} mean={t.mean_val:7.2f}")

    # AFR / Lambda targets
    print("\n--- AFR / LAMBDA TARGETS ---")
    for iid in ("tbl_afr_front", "tbl_afr_rear", "tbl_lambda_front", "tbl_lambda_rear", "tbl_desired_lambda"):
        t = parse_table(root, iid)
        if t:
            print(f"  {t.item_id:40s} {t.n_rows:2d}x{t.n_cols:2d}  min={t.min_val:7.3f} max={t.max_val:7.3f}")

    # Spark
    print("\n--- SPARK ADVANCE ---")
    for iid in ("tbl_spark_advance_front", "tbl_spark_advance_rear", "tbl_base_spark_front", "tbl_base_spark_rear"):
        t = parse_table(root, iid)
        if t:
            print(f"  {t.item_id:40s} {t.n_rows:2d}x{t.n_cols:2d}  min={t.min_val:6.2f} max={t.max_val:6.2f}")

    # Enrichment / Enleanment
    print("\n--- ENRICHMENT / ENLEANMENT ---")
    for iid in ("tbl_deceleration_enleanment", "tbl_accel_enrichment", "tbl_warmup_fuel", "tbl_cranking_fuel"):
        t = parse_table(root, iid)
        if t:
            print(f"  {t.item_id:40s} {t.n_rows:2d}x{t.n_cols:2d}  min={t.min_val:6.3f} max={t.max_val:6.3f}")

    # Idle / IAC
    print("\n--- IDLE / IAC ---")
    for iid in ("tbl_idle_rpm_old", "tbl_iac_warmup_steps", "tbl_iac_crank_steps_vs_temp"):
        t = parse_table(root, iid)
        if t:
            print(f"  {t.item_id:40s} {t.n_rows:2d}x{t.n_cols:2d}  min={t.min_val:8.2f} max={t.max_val:8.2f}")

    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS / OBSERVATIONS")
    print("=" * 80)

    ve_f = parse_table(root, "tbl_ve_tps_based_front_cyl")
    ve_r = parse_table(root, "tbl_ve_tps_based_rear_cyl")
    if ve_f and ve_r:
        if ve_f.max_val and ve_f.max_val > 140:
            print(f"  [INFO] VE max {ve_f.max_val:.1f} (front) -- high but within flashable range for modified tune.")
        if abs((ve_f.max_val or 0) - (ve_r.max_val or 0)) > 10:
            print(f"  [INFO] Front/rear VE max differ by >10 -- check cylinder balance if WOT pulls show imbalance.")

    decel = parse_table(root, "tbl_deceleration_enleanment")
    if decel and decel.min_val and decel.min_val < 0.45:
        print(f"  [INFO] Decel enleanment min {decel.min_val:.3f} -- still fairly aggressive at coldest hot-cell.")
        print("         If die-flat on decel persists, consider raising hot cells further (0.80+).")

    if inj and inj < 25:
        print(f"  [INFO] injector_size = {inj} -- this is ~30% below OEM 31.07.")
        print("         If idle is rough, the longer commanded PW may be pushing injectors into non-linear region.")
        print("         Consider verifying actual injector flow rate before further scalar moves.")

    print("\n  [NEXT STEPS SUGGESTED]")
    print("  1. If decel die-flat is resolved and idle is acceptable -> done for now.")
    print("  2. If idle remains rough -> one-pass patch on idle lambda target + IAC steps.")
    print("  3. If WOT AFR still >16.5 after next pull -> hardware limit reached (injector swap).")
    print("  4. Log a 4th-gear part-throttle pull (TPS 40-60%, 3500-5000 rpm) and drop to inbox.")
    print("     Watch folder will ingest; we will diff AFR vs commanded and decide next move.")


if __name__ == "__main__":
    main()
