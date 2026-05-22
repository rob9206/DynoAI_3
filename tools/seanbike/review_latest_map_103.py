from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

PVV = Path(r"C:\CommmandCenter\Customer_Files\seanbike\v3_inj30_decel_idle_lean_accel_mid.pvv")


def find(root: ET.Element, item_id: str) -> ET.Element | None:
    for item in root.findall("Item"):
        if item.get("id") == item_id:
            return item
    return None


def scalar(root: ET.Element, item_id: str) -> float | None:
    item = find(root, item_id)
    if item is None:
        return None
    cell = item.find("./Rows/Row/Cell")
    if cell is None:
        return None
    return float(cell.get("value", "0"))


def table_values(root: ET.Element, item_id: str) -> tuple[list[float], list[float], list[float]]:
    item = find(root, item_id)
    if item is None:
        return [], [], []
    cols = [float(col.get("label", "0")) for col in item.findall("./Columns/Col")]
    rows = [float(row.get("label", "0")) for row in item.findall("./Rows/Row")]
    vals = [
        float(cell.get("value", "0"))
        for row in item.findall("./Rows/Row")
        for cell in row.findall("Cell")
    ]
    return rows, cols, vals


def one_row(root: ET.Element, item_id: str) -> tuple[list[float], list[float]]:
    item = find(root, item_id)
    if item is None:
        return [], []
    cols = [float(col.get("label", "0")) for col in item.findall("./Columns/Col")]
    row = item.find("./Rows/Row")
    if row is None:
        return cols, []
    vals = [float(cell.get("value", "0")) for cell in row.findall("Cell")]
    return cols, vals


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def summarize_ve(root: ET.Element, item_id: str) -> None:
    rows, cols, vals = table_values(root, item_id)
    print(f"{item_id}:")
    print(f"  shape={len(rows)}x{len(cols)} min={min(vals):.2f} max={max(vals):.2f} mean={sum(vals)/len(vals):.2f}")

    item = find(root, item_id)
    assert item is not None
    idle_vals = []
    cruise_vals = []
    wot_vals = []
    for row in item.findall("./Rows/Row"):
        rpm = float(row.get("label", "0"))
        for col_idx, cell in enumerate(row.findall("Cell")):
            tps = cols[col_idx]
            val = float(cell.get("value", "0"))
            if rpm <= 1.5 and tps <= 10:
                idle_vals.append(val)
            if 2.0 <= rpm <= 4.0 and 20 <= tps <= 40:
                cruise_vals.append(val)
            if rpm >= 3.0 and tps >= 80:
                wot_vals.append(val)
    print(f"  idle zone min/max/mean={min(idle_vals):.2f}/{max(idle_vals):.2f}/{sum(idle_vals)/len(idle_vals):.2f}")
    print(f"  cruise zone min/max/mean={min(cruise_vals):.2f}/{max(cruise_vals):.2f}/{sum(cruise_vals)/len(cruise_vals):.2f}")
    print(f"  WOT zone min/max/mean={min(wot_vals):.2f}/{max(wot_vals):.2f}/{sum(wot_vals)/len(wot_vals):.2f}")


def main() -> None:
    root = ET.parse(PVV).getroot()
    print(f"file={PVV}")
    print(f"sha256={sha256(PVV)}")
    print()

    print("SCALARS")
    print(f"  injector_size={scalar(root, 'tbl_injector_size')}")
    print(f"  engine_displacement={scalar(root, 'tbl_engine_displacement')}")
    print()

    print("VE TABLES")
    summarize_ve(root, "tbl_ve_tps_based_front_cyl")
    summarize_ve(root, "tbl_ve_tps_based_rear_cyl")
    print()

    print("TEMP TABLES")
    for item_id in ("tbl_deceleration_enleanment", "tbl_accel_enrichment", "tbl_idle_rpm_old", "tbl_iac_warmup_steps"):
        temps, vals = one_row(root, item_id)
        print(item_id)
        print("  " + " ".join(f"{int(t):>4}" for t in temps))
        print("  " + " ".join(f"{v:>4.2f}" for v in vals))
    print()

    print("TARGETS / SPARK")
    for item_id in ("tbl_afr", "tbl_pe_air_fuel_ratio_lambda", "tbl_spark_advance_front_cyl", "tbl_spark_advance_rear_cyl"):
        _, _, vals = table_values(root, item_id)
        if vals:
            print(f"  {item_id}: min={min(vals):.2f} max={max(vals):.2f} mean={sum(vals)/len(vals):.2f}")


if __name__ == "__main__":
    main()
