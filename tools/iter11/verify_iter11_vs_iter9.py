"""Verify iter_11 vs iter_9: only VE F/R changed, lean-only, scope respected."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import generate_iter2_patch as g2  # noqa: E402

ITER9 = (
    g2.SESSION_DIR / "iterations" / "iter_9" / "patch" / "iter_9_patched.pvv"
)
ITER11 = (
    g2.SESSION_DIR / "iterations" / "iter_11" / "patch" / "iter_11_patched.pvv"
)
EXPECTED = sorted([g2.VE_FRONT_TABLE, g2.VE_REAR_TABLE])
RPM_LO = 1.5
RPM_HI = 5.5
TPS_SCOPE = {5.0, 7.3, 10.0, 15.0, 20.0, 25.0, 30.0}
MAX_TRIM = -0.10


def _items_by_name(p: Path) -> dict[str, ET.Element]:
    root = ET.parse(str(p)).getroot()
    return {it.get("name"): it for it in root.findall("Item") if it.get("name")}


def _cells_changed(a: ET.Element, b: ET.Element) -> int:
    ac = a.findall(".//Cell")
    bc = b.findall(".//Cell")
    if len(ac) != len(bc):
        raise RuntimeError("cell count mismatch")
    n = 0
    for ai, bi in zip(ac, bc):
        if (ai.get("value", "") or "").strip() != (bi.get("value", "") or "").strip():
            n += 1
    return n


def _verify_ve(a: ET.Element, b: ET.Element, label: str) -> tuple[int, list[str]]:
    rpm, tps, ag = g2.read_table(a)
    _, _, bg = g2.read_table(b)
    errs: list[str] = []
    n = 0
    for r in range(len(rpm)):
        for c in range(len(tps)):
            if abs(ag[r][c] - bg[r][c]) < 1e-9:
                continue
            n += 1
            in_rpm = RPM_LO <= rpm[r] <= RPM_HI
            in_tps = tps[c] in TPS_SCOPE
            if not in_rpm or not in_tps:
                errs.append(
                    f"{label} OUT OF SCOPE rpm_k={rpm[r]:g} tps={tps[c]:g}"
                )
            base = ag[r][c]
            new = bg[r][c]
            if new > base + 1e-9:
                errs.append(
                    f"{label} ENRICHED rpm_k={rpm[r]:g} tps={tps[c]:g} {base:.2f}->{new:.2f}"
                )
            pct = (new - base) / base if abs(base) > 1e-9 else 0.0
            if pct < MAX_TRIM - 1e-3:
                errs.append(
                    f"{label} BEYOND CAP rpm_k={rpm[r]:g} tps={tps[c]:g} pct={pct * 100:+.2f}%"
                )
    return n, errs


def main() -> int:
    a = _items_by_name(ITER9)
    b = _items_by_name(ITER11)
    common = set(a) & set(b)
    changed = sorted(name for name in common if _cells_changed(a[name], b[name]) > 0)
    print(f"iter_9 SHA-256:  {g2.sha256(ITER9)}")
    print(f"iter_11 SHA-256: {g2.sha256(ITER11)}")
    print(f"Tables changed: {changed}")
    fail = False
    if changed != EXPECTED:
        print(f"FAIL: expected only {EXPECTED}")
        fail = True

    nf, errf = _verify_ve(a[g2.VE_FRONT_TABLE], b[g2.VE_FRONT_TABLE], "VE Front")
    nr, errr = _verify_ve(a[g2.VE_REAR_TABLE], b[g2.VE_REAR_TABLE], "VE Rear")
    for e in errf + errr:
        print("  " + e)
        fail = True
    print(f"VE Front cells changed: {nf}")
    print(f"VE Rear cells changed:  {nr}")
    if fail:
        print("VERDICT: FAIL")
        return 1
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
