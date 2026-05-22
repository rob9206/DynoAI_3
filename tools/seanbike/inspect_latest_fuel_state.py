from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

PVV = Path(r"C:\CommmandCenter\Customer_Files\seanbike\v3_inj30_decel_idle_lean_accel_mid.pvv")


def main() -> None:
    root = ET.parse(PVV).getroot()
    print(f"file={PVV}")
    for item_id in ("tbl_injector_size", "tbl_engine_displacement"):
        item = next(item for item in root.findall("Item") if item.get("id") == item_id)
        print(item_id, item.find("./Rows/Row/Cell").get("value"))

    for item_id in ("tbl_ve_tps_based_front_cyl", "tbl_ve_tps_based_rear_cyl"):
        item = next(item for item in root.findall("Item") if item.get("id") == item_id)
        cols = [float(col.get("label", "0")) for col in item.findall("./Columns/Col")]
        values = []
        for row in item.findall("./Rows/Row"):
            rpm = float(row.get("label", "0"))
            for col_idx, cell in enumerate(row.findall("Cell")):
                values.append((float(cell.get("value", "0")), rpm, cols[col_idx]))
        max_val, max_rpm, max_tps = max(values)
        min_val, min_rpm, min_tps = min(values)
        print(
            item_id,
            f"min={min_val:.2f}@{min_rpm:.3f}k/{min_tps:g}TPS",
            f"max={max_val:.2f}@{max_rpm:.3f}k/{max_tps:g}TPS",
        )


if __name__ == "__main__":
    main()
