"""Compare key scalars/tables across known PVVs to confirm the new file."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(r"C:\CommmandCenter\Customer_Files\seanbike")
FILES = [
    ("OEM read",            "exportedreadfrompv4.pvv"),
    ("inj-12 only",         "v3_plus_inj_minus12pct.pvv"),
    ("inj-30 + decel soft", "v3_inj30_decel_soft.pvv"),
    ("inj-12 + decel soft", "v3_inj12_decel_soft.pvv"),
]

print(f"{'label':25s} {'inj_size':>10s} {'decel hot med':>15s}")
print("-" * 60)
for label, fname in FILES:
    p = BASE / fname
    root = ET.parse(p).getroot()
    inj = "-"
    decel_hot: list[float] = []
    for it in root.findall("Item"):
        if it.get("id") == "tbl_injector_size":
            cell = it.find("./Rows/Row/Cell")
            if cell is not None:
                inj = cell.get("value", "-")
        if it.get("id") == "tbl_deceleration_enleanment":
            cols = it.findall("./Columns/Col")
            cells = it.findall("./Rows/Row/Cell")
            for col, cell in zip(cols, cells):
                try:
                    t = float(col.get("label", "0"))
                    v = float(cell.get("value", "0"))
                except ValueError:
                    continue
                if t >= 147:
                    decel_hot.append(v)
    hot_med = sorted(decel_hot)[len(decel_hot) // 2] if decel_hot else 0.0
    print(f"{label:25s} {inj:>10s} {hot_med:>15.3f}")
