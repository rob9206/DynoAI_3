"""Verify iter_10 vs iter_9: only rear spark changed and rear mirrors front."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import generate_iter2_patch as g2  # noqa: E402

ITER9 = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline"
    r"\iterations\iter_9\patch\iter_9_patched.pvv"
)
ITER10 = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline"
    r"\iterations\iter_10\patch\iter_10_patched.pvv"
)
EXPECTED = [g2.SPARK_REAR_TABLE]


def _items_by_name(path: Path) -> dict[str, ET.Element]:
    root = ET.parse(str(path)).getroot()
    return {it.get("name"): it for it in root.findall("Item") if it.get("name")}


def _cells_changed(a: ET.Element, b: ET.Element) -> int:
    ac = a.findall(".//Cell")
    bc = b.findall(".//Cell")
    if len(ac) != len(bc):
        raise RuntimeError("cell count mismatch")
    n = 0
    for ai, bi in zip(ac, bc):
        av = (ai.get("value", "") or "").strip()
        bv = (bi.get("value", "") or "").strip()
        if av != bv:
            n += 1
    return n


def main() -> int:
    if not ITER9.exists() or not ITER10.exists():
        print("ERROR: iter_9 or iter_10 patch missing", file=sys.stderr)
        return 2

    a = _items_by_name(ITER9)
    b = _items_by_name(ITER10)
    common = set(a) & set(b)
    changed = sorted(name for name in common if _cells_changed(a[name], b[name]) > 0)
    print(f"iter_9 SHA-256:  {g2.sha256(ITER9)}")
    print(f"iter_10 SHA-256: {g2.sha256(ITER10)}")
    print(f"Tables changed: {changed}")
    if changed != EXPECTED:
        print(f"FAIL: expected only {EXPECTED}")
        return 1

    root10 = ET.parse(str(ITER10)).getroot()
    sf_item = g2.find_item_by_name(root10, g2.SPARK_FRONT_TABLE)
    sr_item = g2.find_item_by_name(root10, g2.SPARK_REAR_TABLE)
    _, _, sf = g2.read_table(sf_item)
    _, _, sr = g2.read_table(sr_item)

    for r in range(len(sf)):
        for c in range(len(sf[0])):
            if abs(sf[r][c] - sr[r][c]) > 1e-9:
                print(
                    f"FAIL: rear!=front at r={r}, c={c}: "
                    f"{sr[r][c]:.2f} vs {sf[r][c]:.2f}"
                )
                return 1

    changed_cells = _cells_changed(a[g2.SPARK_REAR_TABLE], b[g2.SPARK_REAR_TABLE])
    print(f"Rear spark changed cells: {changed_cells}")
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
