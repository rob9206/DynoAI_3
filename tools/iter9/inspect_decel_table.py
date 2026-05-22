"""Inspect Deceleration Enleanment table structure in iter_8."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ITER8 = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline"
    r"\iterations\iter_8\patch\iter_8_patched.pvv"
)


def main() -> int:
    root = ET.parse(str(ITER8)).getroot()
    item = next(it for it in root.findall("Item") if it.get("name") == "Deceleration Enleanment")
    print("Item attribs:", dict(item.attrib))
    cols = item.find("Columns")
    rows = item.find("Rows")
    print("Columns attribs:", dict(cols.attrib) if cols is not None else "MISSING")
    if cols is not None:
        col_labels = [c.get("label", "") for c in cols.findall("Col")]
        print(f"  Col labels ({len(col_labels)}): {col_labels}")
    print("Rows attribs:", dict(rows.attrib) if rows is not None else "MISSING")
    if rows is not None:
        row_elems = rows.findall("Row")
        print(f"  Row count: {len(row_elems)}")
        for r_idx, r in enumerate(row_elems):
            row_label = r.get("label", "")
            cells = [c.get("value", "") for c in r.findall("Cell")]
            print(f"  Row[{r_idx}] label={row_label!r}: {cells}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
