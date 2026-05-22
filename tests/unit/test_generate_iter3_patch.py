"""
Tests for tools/generate_iter3_patch.py (iter_2 v3 + VE from DWRT findings).
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import generate_iter2_patch as g2  # noqa: E402
import generate_iter3_patch as g3  # noqa: E402

SESSION_DIR = g2.SESSION_DIR
BASE_PVV = SESSION_DIR / "base_tune" / "dynojet_stage.pvv"
FINDINGS = SESSION_DIR / "iterations" / "iter_2" / "analyses" / "iter2_dwrt_findings.json"


@pytest.fixture()
def base_pvv_path() -> Path:
    if not BASE_PVV.exists():
        pytest.skip(f"dynojet_stage.pvv missing at {BASE_PVV}")
    return BASE_PVV


@pytest.fixture()
def findings_path() -> Path:
    if not FINDINGS.exists():
        pytest.skip(f"findings missing at {FINDINGS}")
    return FINDINGS


def _run_iter3(tmp_path: Path, base: Path, findings: Path) -> Path:
    iter3 = tmp_path / "iter_3"
    rc = g3.main(["--base", str(base), "--iter3-dir", str(iter3), "--findings", str(findings)])
    assert rc == 0
    patched = iter3 / "patch" / "iter_3_patched.pvv"
    assert patched.exists()
    return patched


def _items(root: ET.Element) -> dict[str, ET.Element]:
    return {it.get("name", ""): it for it in root.findall("Item")}


def test_happy_path_iter3(tmp_path: Path, base_pvv_path: Path, findings_path: Path) -> None:
    patched = _run_iter3(tmp_path, base_pvv_path, findings_path)
    root = ET.parse(str(patched)).getroot()
    assert len(root.findall("Item")) == 32


def test_only_eight_tables_changed(
    tmp_path: Path, base_pvv_path: Path, findings_path: Path
) -> None:
    patched = _run_iter3(tmp_path, base_pvv_path, findings_path)
    pb = _items(ET.parse(str(patched)).getroot())
    bb = _items(ET.parse(str(base_pvv_path)).getroot())
    changed = [n for n in pb if ET.tostring(pb[n]) != ET.tostring(bb[n])]
    assert set(changed) == set(g3.EXPECTED_CHANGED_ITER3)


def test_iter3_carries_all_iter2_changes(
    tmp_path: Path, base_pvv_path: Path, findings_path: Path
) -> None:
    patched = _run_iter3(tmp_path, base_pvv_path, findings_path)
    items = _items(ET.parse(str(patched)).getroot())
    assert items[g2.DISPLACEMENT_TABLE].find(".//Cell").get("value") == "103"
    for cell in items[g2.DECEL_ENLEANMENT_TABLE].findall(".//Cell"):
        assert cell.get("value") == "1"
    for cell in items[g2.KNOCK_RETARD_TABLE].findall(".//Cell"):
        assert float(cell.get("value", "0")) <= 4.01
    for cell in items[g2.RPM_LIMIT_TABLE].findall(".//Cell"):
        assert cell.get("value") == "6.2"


def test_ve_cells_within_ten_percent_of_stage(
    tmp_path: Path, base_pvv_path: Path, findings_path: Path
) -> None:
    patched = _run_iter3(tmp_path, base_pvv_path, findings_path)
    base = _items(ET.parse(str(base_pvv_path)).getroot())
    new = _items(ET.parse(str(patched)).getroot())
    for table in (g2.VE_FRONT_TABLE, g2.VE_REAR_TABLE):
        _, _, sg = g2.read_table(base[table])
        _, _, ng = g2.read_table(new[table])
        for r, row in enumerate(sg):
            for c, b in enumerate(row):
                n = ng[r][c]
                if abs(n - b) < 1e-9:
                    continue
                assert abs(n - b) / abs(b) <= g3.VE_MAX_FRAC_CHANGE + 1e-5


def test_afr_tables_byte_identical_to_stage(
    tmp_path: Path, base_pvv_path: Path, findings_path: Path
) -> None:
    patched = _run_iter3(tmp_path, base_pvv_path, findings_path)
    base = _items(ET.parse(str(base_pvv_path)).getroot())
    new = _items(ET.parse(str(patched)).getroot())
    for t in (g2.AFR_TARGET_TABLE, g2.AFR_STOICH_TABLE):
        assert ET.tostring(new[t]) == ET.tostring(base[t])


def test_dynojet_safety_items_byte_identical(
    tmp_path: Path, base_pvv_path: Path, findings_path: Path
) -> None:
    patched = _run_iter3(tmp_path, base_pvv_path, findings_path)
    base = _items(ET.parse(str(base_pvv_path)).getroot())
    new = _items(ET.parse(str(patched)).getroot())
    for t in (
        g2.CAL_ID_TABLE,
        g2.SPEEDO_TABLE,
        g2.ACCEL_ENRICH_TABLE,
        g2.SPARK_ECT_ADJUST_TABLE,
    ):
        assert ET.tostring(new[t]) == ET.tostring(base[t])


def test_idempotency_iter3(tmp_path: Path, base_pvv_path: Path, findings_path: Path) -> None:
    a = _run_iter3(tmp_path / "a", base_pvv_path, findings_path)
    b = _run_iter3(tmp_path / "b", base_pvv_path, findings_path)
    assert g2.sha256(a) == g2.sha256(b)


def test_ve_correction_from_minimal_findings(tmp_path: Path, base_pvv_path: Path) -> None:
    """One-cell findings produces matching VE delta on both tables."""
    tree = ET.parse(str(base_pvv_path))
    root = tree.getroot()
    ve = g2.find_item_by_name(root, g2.VE_FRONT_TABLE)
    assert ve is not None
    row_axis, col_axis, grid = g2.read_table(ve)
    r, c = 10, 8
    base_val = grid[r][c]
    findings = {
        "sources": [{"name": "fixture", "sha256": "0", "samples": 1}],
        "ve_correction_grid": [
            {
                "row_idx": r,
                "col_idx": c,
                "rpm_k": row_axis[r],
                "tps_pct": col_axis[c],
                "n": 99,
                "median_err_pct": -2.0,
                "ve_delta_pct": -2.0,
            }
        ],
        "warnings": [],
    }
    fp = tmp_path / "findings.json"
    fp.write_text(json.dumps(findings), encoding="utf-8")
    patched = _run_iter3(tmp_path / "iter3_one", base_pvv_path, fp)
    items = _items(ET.parse(str(patched)).getroot())
    _, _, ngf = g2.read_table(items[g2.VE_FRONT_TABLE])
    _, _, ngr = g2.read_table(items[g2.VE_REAR_TABLE])
    exp = base_val * 0.98
    assert abs(ngf[r][c] - exp) < 0.02
    br = g2.read_table(g2.find_item_by_name(ET.parse(str(base_pvv_path)).getroot(), g2.VE_REAR_TABLE))[2][r][c]
    expr = br * 0.98
    assert abs(ngr[r][c] - expr) < 0.02


def test_verify_patch_gates_iter3_rejects_afr_touch(
    tmp_path: Path, base_pvv_path: Path, findings_path: Path
) -> None:
    patched = _run_iter3(tmp_path, base_pvv_path, findings_path)
    tree = ET.parse(str(patched))
    root = tree.getroot()
    items = _items(root)
    cell = items[g2.AFR_STOICH_TABLE].find(".//Cell")
    assert cell is not None
    cell.set("value", "20")
    bad = tmp_path / "bad_afr.pvv"
    tree.write(str(bad), encoding="utf-8", xml_declaration=True)

    items_b = _items(ET.parse(str(base_pvv_path)).getroot())
    f_item = items_b[g2.SPARK_FRONT_TABLE]
    r_item = items_b[g2.SPARK_REAR_TABLE]
    f_row, f_col, f_sb, f_sn, _ = g2.apply_spark_changes(f_item)
    r_row, r_col, r_sb, r_sn, _ = g2.apply_spark_changes(r_item)

    vf_s = g2.read_table(items[g2.VE_FRONT_TABLE])[2]
    vf_n = g2.read_table(items[g2.VE_FRONT_TABLE])[2]
    vr_s = g2.read_table(items[g2.VE_REAR_TABLE])[2]
    vr_n = g2.read_table(items[g2.VE_REAR_TABLE])[2]

    with pytest.raises(RuntimeError, match="Gate 2|Gate 5"):
        g2.verify_patch_gates(
            bad,
            base_pvv_path,
            g3.EXPECTED_CHANGED_ITER3,
            g3.UNTOUCHABLE_ITER3,
            (f_sb, f_sn),
            (r_sb, r_sn),
            ve_stage_front=vf_s,
            ve_patched_front=vf_n,
            ve_stage_rear=vr_s,
            ve_patched_rear=vr_n,
            ve_max_frac_change=g3.VE_MAX_FRAC_CHANGE,
        )


def test_gate6_trips_when_ve_frac_exceeds_cap(
    tmp_path: Path, base_pvv_path: Path, findings_path: Path
) -> None:
    patched = _run_iter3(tmp_path, base_pvv_path, findings_path)
    vf_s = [[10.0, 20.0], [30.0, 40.0]]
    vf_n = [[10.0, 20.0], [30.0, 55.0]]
    vr_s = [[10.0, 20.0], [30.0, 40.0]]
    vr_n = [[10.0, 20.0], [30.0, 40.0]]
    with pytest.raises(RuntimeError, match="Gate 6"):
        g2.verify_patch_gates(
            patched,
            base_pvv_path,
            g3.EXPECTED_CHANGED_ITER3,
            g3.UNTOUCHABLE_ITER3,
            (vf_s, vf_s),
            (vr_s, vr_s),
            ve_stage_front=vf_s,
            ve_patched_front=vf_n,
            ve_stage_rear=vr_s,
            ve_patched_rear=vr_n,
            ve_max_frac_change=0.10,
        )


def test_parse_dwrt_log_smoke() -> None:
    sys.path.insert(0, str(TOOLS_DIR / "iter3"))
    from parse_dwrt_log import parse_dwrt_log  # noqa: E402

    src = SESSION_DIR / "iterations" / "iter_2" / "pulls" / "6th gear load then wot.txt"
    if not src.exists():
        pytest.skip("DWRT log not ingested")
    df, rep = parse_dwrt_log(src)
    assert "lc2_pegged" in df.columns
    assert rep.row_count == len(df)
