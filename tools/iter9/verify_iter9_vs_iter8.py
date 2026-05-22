"""Verify iter_9_patched.pvv vs iter_8_patched.pvv -- decel + low-TPS VE only."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import generate_iter2_patch as g2  # noqa: E402

BASE = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline"
    r"\iterations\iter_8\patch\iter_8_patched.pvv"
)
NEW = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline"
    r"\iterations\iter_9\patch\iter_9_patched.pvv"
)

EXPECTED_CHANGED = {
    g2.DECEL_ENLEANMENT_TABLE,
    g2.VE_FRONT_TABLE,
    g2.VE_REAR_TABLE,
}


def items_by_name(p: Path) -> dict[str, ET.Element]:
    root = ET.parse(str(p)).getroot()
    return {it.get("name"): it for it in root.findall("Item") if it.get("name")}


def cells_changed(a: ET.Element, b: ET.Element) -> int:
    ac = a.findall(".//Cell")
    bc = b.findall(".//Cell")
    if len(ac) != len(bc):
        raise RuntimeError("Cell count mismatch")
    n = 0
    for ai, bi in zip(ac, bc):
        if (ai.get("value", "") or "").strip() != (bi.get("value", "") or "").strip():
            n += 1
    return n


def verify_decel(a: ET.Element, b: ET.Element) -> list[str]:
    err: list[str] = []
    cols_a = a.find("Columns")
    cols_b = b.find("Columns")
    labels = [int(c.get("label", "0") or "0") for c in cols_a.findall("Col")]
    a_cells = [g2.parse_float(c.get("value", "0") or "0") for c in a.find("Rows").find("Row").findall("Cell")]
    b_cells = [g2.parse_float(c.get("value", "0") or "0") for c in b.find("Rows").find("Row").findall("Cell")]
    cold = {3, 32, 61}
    for label, av, bv in zip(labels, a_cells, b_cells):
        if label in cold:
            if abs(bv - 1.0) > 1e-6:
                err.append(f"  decel cold col {label} F should be 1.0, got {bv}")
        else:
            if abs(bv - 0.92) > 1e-6:
                err.append(f"  decel hot col {label} F should be 0.92, got {bv}")
    return err


def verify_ve(a: ET.Element, b: ET.Element, label: str) -> list[str]:
    err: list[str] = []
    row_axis, col_axis, ag = g2.read_table(a)
    _, _, bg = g2.read_table(b)
    allowed_tps = {0.0, 2.0, 5.0, 7.0, 10.0}
    for r, rpm_k in enumerate(row_axis):
        for c, tps in enumerate(col_axis):
            av = ag[r][c]
            bv = bg[r][c]
            if abs(av - bv) < 1e-9:
                continue
            in_scope = (1.5 <= rpm_k <= 5.0) and (tps in allowed_tps)
            if not in_scope:
                err.append(
                    f"  VE {label} OUT OF SCOPE rpm={int(rpm_k * 1000)} tps={tps:g}: {av:.2f} -> {bv:.2f}"
                )
                continue
            pct = (bv - av) / av if abs(av) > 1e-9 else 0.0
            if pct < -0.071 or pct > 0.0:
                err.append(
                    f"  VE {label} delta out of [-7%, 0] rpm={int(rpm_k * 1000)} tps={tps:g}: {pct * 100:+.2f}%"
                )
            if abs(pct + 0.07) > 1e-3:
                err.append(
                    f"  VE {label} delta should be -7% rpm={int(rpm_k * 1000)} tps={tps:g}: {pct * 100:+.2f}%"
                )
    return err


def main() -> int:
    if not BASE.exists() or not NEW.exists():
        print("ERROR: iter_8 or iter_9 patch missing", file=sys.stderr)
        return 2

    a = items_by_name(BASE)
    b = items_by_name(NEW)
    common = set(a) & set(b)
    changed = {n for n in common if cells_changed(a[n], b[n]) > 0}

    print(f"iter_8 SHA-256: {g2.sha256(BASE)}")
    print(f"iter_9 SHA-256: {g2.sha256(NEW)}")
    print(f"Tables changed: {sorted(changed)}")

    extra = changed - EXPECTED_CHANGED
    missing = EXPECTED_CHANGED - changed
    fail = False
    if extra:
        print(f"FAIL: unexpected tables changed: {sorted(extra)}")
        fail = True
    if missing:
        print(f"FAIL: expected tables NOT changed: {sorted(missing)}")
        fail = True

    decel_err = verify_decel(a[g2.DECEL_ENLEANMENT_TABLE], b[g2.DECEL_ENLEANMENT_TABLE])
    ve_f_err = verify_ve(a[g2.VE_FRONT_TABLE], b[g2.VE_FRONT_TABLE], "front")
    ve_r_err = verify_ve(a[g2.VE_REAR_TABLE], b[g2.VE_REAR_TABLE], "rear")

    for e in decel_err + ve_f_err + ve_r_err:
        print(e)
        fail = True

    if fail:
        print("VERDICT: FAIL")
        return 1

    decel_n = cells_changed(a[g2.DECEL_ENLEANMENT_TABLE], b[g2.DECEL_ENLEANMENT_TABLE])
    vf_n = cells_changed(a[g2.VE_FRONT_TABLE], b[g2.VE_FRONT_TABLE])
    vr_n = cells_changed(a[g2.VE_REAR_TABLE], b[g2.VE_REAR_TABLE])
    print(f"  Decel Enleanment: {decel_n} cells changed (expect 9 hot temps)")
    print(f"  VE Front:         {vf_n} cells changed")
    print(f"  VE Rear:          {vr_n} cells changed")
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
