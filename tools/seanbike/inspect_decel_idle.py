"""Dump decel/idle/accel/warmup tables for inspection."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

PVV = Path(r"C:\CommmandCenter\Customer_Files\seanbike\v3_plus_inj_minus30pct.pvv")


def dump(root: ET.Element, item_id: str) -> None:
    for it in root.findall("Item"):
        if it.get("id") == item_id:
            name = it.get("name", "")
            print(f"\n=== {item_id} ({name}) ===")
            cols = it.findall("./Columns/Col")
            print("  Col labels:", [c.get("label") for c in cols])
            for r in it.findall("./Rows/Row"):
                vals = [c.get("value") for c in r.findall("Cell")]
                print(f'  Row {r.get("label")}: {vals}')
            return
    print(f"NOT FOUND: {item_id}")


def main() -> None:
    root = ET.parse(PVV).getroot()

    dump(root, "tbl_deceleration_enleanment")
    dump(root, "tbl_idle_rpm_old")
    print()
    print("Decel/idle/accel/warmup/ego items found:")
    needles = (
        "decel",
        "enleanment",
        "accel_enrich",
        "accel_enrichment",
        "ego",
        "closed_loop",
        "warmup",
        "warm_up",
        "startup",
        "idle",
        "ego",
        "cold",
        "iac",
    )
    for it in root.findall("Item"):
        iid = (it.get("id") or "").lower()
        name = it.get("name", "")
        if any(n in iid for n in needles):
            rows = it.findall("./Rows/Row")
            cells = [c.get("value", "") for r in rows for c in r.findall("Cell")]
            print(f"  {iid:55s} {name[:30]:30s} cells={len(cells)} first5={cells[:5]}")


if __name__ == "__main__":
    main()
