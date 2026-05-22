"""Quick inspection of iter_2 patch outputs vs base.pvv (read-only)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "vehicles/ryantitus_fatboy_cvo/sessions/2026-05-10_4thgear_baseline/base_tune/base.pvv"
PATCHED = ROOT / "vehicles/ryantitus_fatboy_cvo/sessions/2026-05-10_4thgear_baseline/iterations/iter_2/patch/iter_2_patched.pvv"


def find(root: ET.Element, name: str) -> ET.Element:
    for item in root.findall("Item"):
        if item.get("name") == name:
            return item
    raise KeyError(name)


def main() -> None:
    r1 = ET.parse(str(BASE)).getroot()
    r2 = ET.parse(str(PATCHED)).getroot()

    for table_name in (
        "Max Knock Retard vs RPM",
        "Spark Advance (Front Cyl)",
        "Spark Advance (Rear Cyl)",
        "VE (TPS based/Rear Cyl)",
        "PE Air-Fuel Ratio",
    ):
        i1 = find(r1, table_name)
        i2 = find(r2, table_name)
        id1 = i1.get("id")
        id2 = i2.get("id")
        print(f"\n=== {table_name} ===")
        print(f"  id base    : {id1}")
        print(f"  id patched : {id2}")
        print(f"  changed    : {ET.tostring(i1) != ET.tostring(i2)}")

    # Show full knock retard before/after
    print("\nKnock retard row (cols are RPM 0..8800 step 800):")
    k1 = find(r1, "Max Knock Retard vs RPM")
    k2 = find(r2, "Max Knock Retard vs RPM")
    print("  base:    ", [c.get("value") for c in k1.find("Rows").find("Row").findall("Cell")])
    print("  patched: ", [c.get("value") for c in k2.find("Rows").find("Row").findall("Cell")])

    # Show notched rows of spark advance front
    print("\nSpark Advance (Front Cyl) RPM 5.0, 5.5, 6.0 rows (cols include MAP 90 95 100 ...):")
    s1 = find(r1, "Spark Advance (Front Cyl)")
    s2 = find(r2, "Spark Advance (Front Cyl)")
    for label in ("5", "5.5", "6"):
        b = next(r for r in s1.find("Rows").findall("Row") if r.get("label") == label)
        n = next(r for r in s2.find("Rows").findall("Row") if r.get("label") == label)
        print(f"  RPM {label}k base:    ", [c.get("value") for c in b.findall("Cell")])
        print(f"  RPM {label}k patched: ", [c.get("value") for c in n.findall("Cell")])

    # Show one VE rear row (3.5 = hot zone)
    print("\nVE (TPS based/Rear Cyl) RPM 3.5 and 5 rows (cols are TPS%):")
    v1 = find(r1, "VE (TPS based/Rear Cyl)")
    v2 = find(r2, "VE (TPS based/Rear Cyl)")
    for label in ("3.5", "5"):
        b = next(r for r in v1.find("Rows").findall("Row") if r.get("label") == label)
        n = next(r for r in v2.find("Rows").findall("Row") if r.get("label") == label)
        print(f"  RPM {label}k base:    ", [c.get("value") for c in b.findall("Cell")])
        print(f"  RPM {label}k patched: ", [c.get("value") for c in n.findall("Cell")])

    # PE AFR untouched
    print("\nPE AFR row (must be identical):")
    p1 = find(r1, "PE Air-Fuel Ratio")
    p2 = find(r2, "PE Air-Fuel Ratio")
    b = p1.find("Rows").find("Row")
    n = p2.find("Rows").find("Row")
    print("  base:    ", [c.get("value") for c in b.findall("Cell")])
    print("  patched: ", [c.get("value") for c in n.findall("Cell")])


if __name__ == "__main__":
    main()
