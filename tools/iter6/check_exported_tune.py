"""Compare the user-exported tune (read off the ECU) against iter_6 and iter_3."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

ITER_DIR = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations"
)
EXPORTED = ITER_DIR / "iter_6" / "patch" / "exporte6.pvv"
ITER6 = ITER_DIR / "iter_6" / "patch" / "iter_6_patched.pvv"
ITER3 = ITER_DIR / "iter_3" / "patch" / "iter_3_patched.pvv"
ITER5 = ITER_DIR / "iter_5" / "patch" / "iter_5_patched.pvv"
DYNOJET = (
    Path(
        r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\base_tune"
    )
    / "dynojet_stage.pvv"
)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def items_by_name(p: Path) -> dict[str, ET.Element]:
    root = ET.parse(str(p)).getroot()
    return {it.get("name", ""): it for it in root.findall("Item")}


def diff_items(label: str, a: dict[str, ET.Element], b: dict[str, ET.Element]) -> list[str]:
    common = set(a.keys()) & set(b.keys())
    changed: list[str] = []
    for n in sorted(common):
        if ET.tostring(a[n]) != ET.tostring(b[n]):
            changed.append(n)
    print(f"\n{label}: {len(changed)} table(s) differ")
    for n in changed:
        print(f"  - {n}")
    return changed


def displacement(p: Path) -> str:
    items = items_by_name(p)
    e = items.get("Engine Displacement")
    if e is None:
        return "Engine Displacement: MISSING"
    cell = e.find(".//Cell")
    return f"Engine Displacement: {cell.get('value') if cell is not None else 'no Cell'}"


def main() -> int:
    print("file existence:")
    for p in (EXPORTED, ITER6, ITER3, ITER5, DYNOJET):
        print(f"  {p.name}  exists={p.exists()}  size={p.stat().st_size if p.exists() else 'n/a'}")

    if not EXPORTED.exists():
        print("\nABORT: exported tune missing")
        return 1

    print("\nSHA-256:")
    for p in (EXPORTED, ITER6, ITER3, ITER5, DYNOJET):
        if p.exists():
            print(f"  {p.name}  {sha256(p)}")

    print("\nDisplacement:")
    for p in (EXPORTED, ITER6, ITER3, ITER5, DYNOJET):
        if p.exists():
            print(f"  {p.name}  {displacement(p)}")

    exp = items_by_name(EXPORTED)
    if ITER6.exists():
        diff_items("EXPORTED vs iter_6", exp, items_by_name(ITER6))
    if ITER3.exists():
        diff_items("EXPORTED vs iter_3", exp, items_by_name(ITER3))
    if ITER5.exists():
        diff_items("EXPORTED vs iter_5", exp, items_by_name(ITER5))
    if DYNOJET.exists():
        diff_items("EXPORTED vs dynojet_stage", exp, items_by_name(DYNOJET))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
