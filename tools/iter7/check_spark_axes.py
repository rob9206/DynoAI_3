"""Inspect Spark Advance axis labels and metadata."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ITER6 = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline"
    r"\iterations\iter_6\patch\iter_6_patched.pvv"
)


def main() -> int:
    root = ET.parse(str(ITER6)).getroot()
    for tbl in ("Spark Advance (Front Cyl)", "Spark Advance (Rear Cyl)"):
        item = next(it for it in root.findall("Item") if it.get("name") == tbl)
        print(f"\n=== {tbl} ===")
        print("Item attribs:")
        for k, v in item.attrib.items():
            print(f"  {k}={v}")
        cols = item.find("Columns")
        rows = item.find("Rows")
        print("Columns attribs:", dict(cols.attrib) if cols is not None else "MISSING")
        if cols is not None:
            col_labels = [c.get("label", "") for c in cols.findall("Col")]
            col_units = [c.get("units", "") for c in cols.findall("Col")]
            print(f"  Col labels: {col_labels}")
            print(f"  Col units: {set(col_units)}")
        print("Rows attribs:", dict(rows.attrib) if rows is not None else "MISSING")
        if rows is not None:
            row_labels = [r.get("label", "") for r in rows.findall("Row")]
            print(f"  Row labels: {row_labels}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
