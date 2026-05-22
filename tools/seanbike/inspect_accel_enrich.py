"""Inspect tbl_accel_enrichment table structure."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

p = Path(r"C:\CommmandCenter\Customer_Files\seanbike\v3_inj30_decel_idle_lean.pvv")
root = ET.parse(p).getroot()

for it in root.findall("Item"):
    if it.get("id") == "tbl_accel_enrichment":
        print("=== tbl_accel_enrichment ===")
        print(f"Name: {it.get('name', '')}")
        cols = it.findall("./Columns/Col")
        print("Col labels:", [c.get("label") for c in cols])
        for r in it.findall("./Rows/Row"):
            print(f"Row {r.get('label')}: ", [c.get("value") for c in r.findall("Cell")])
        break
