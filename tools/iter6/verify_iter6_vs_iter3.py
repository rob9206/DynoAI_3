"""Confirm iter_6_patched.pvv differs from iter_3_patched.pvv ONLY in AE table."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations")
A = ROOT / "iter_3" / "patch" / "iter_3_patched.pvv"
B = ROOT / "iter_6" / "patch" / "iter_6_patched.pvv"


def items_by_name(path: Path) -> dict[str, ET.Element]:
    root = ET.parse(str(path)).getroot()
    return {it.get("name", ""): it for it in root.findall("Item")}


a = items_by_name(A)
b = items_by_name(B)

a_names = set(a.keys())
b_names = set(b.keys())
print(f"iter_3 items: {len(a_names)}  iter_6 items: {len(b_names)}")
print(f"missing in iter_6: {sorted(a_names - b_names) or 'none'}")
print(f"extra in iter_6: {sorted(b_names - a_names) or 'none'}")

changed: list[str] = []
for name in sorted(a_names & b_names):
    sa = ET.tostring(a[name])
    sb = ET.tostring(b[name])
    if sa != sb:
        changed.append(name)

print()
print(f"tables that differ between iter_3 and iter_6 ({len(changed)}):")
for n in changed:
    print(f"  - {n}")
