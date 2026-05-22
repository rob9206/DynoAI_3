"""Show the RPM and TPS axes of the VE tables so we can pick the idle zone."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

PVV = Path(r"C:\CommmandCenter\Customer_Files\seanbike\v3_inj30_decel_soft.pvv")

root = ET.parse(PVV).getroot()
for it in root.findall("Item"):
    if it.get("id") == "tbl_ve_tps_based_front_cyl":
        print("=== tbl_ve_tps_based_front_cyl ===")
        cols = [c.get("label", "?") for c in it.findall("./Columns/Col")]
        rows = it.findall("./Rows/Row")
        row_labels = [r.get("label", "?") for r in rows]
        print(f"  Columns (TPS%):", cols)
        print(f"  Rows (RPM kRPM):", row_labels)
        print(f"  Shape: {len(rows)} rows x {len(cols)} cols")

        print("\n  Idle-zone cells (low RPM x low TPS):")
        for r_idx, row in enumerate(rows[:6]):
            cells = row.findall("Cell")
            row_label = row.get("label", "?")
            vals = [cells[i].get("value", "?") for i in range(min(6, len(cells)))]
            print(f"    RPM={row_label:>5s}: TPS{cols[0]:>3s}..{cols[5]:>3s}: {vals}")

        print("\n  WOT-zone cells (high RPM x high TPS):")
        for r_idx, row in enumerate(rows[-6:]):
            cells = row.findall("Cell")
            row_label = row.get("label", "?")
            vals = [cells[i].get("value", "?") for i in range(max(0, len(cells) - 6), len(cells))]
            print(f"    RPM={row_label:>5s}: TPS{cols[-6]:>3s}..{cols[-1]:>3s}: {vals}")
        break
