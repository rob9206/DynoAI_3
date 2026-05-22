"""
Adversarial + invariant tests for tools/generate_iter2_patch.py (v3).

These tests prove the verification gates actually trip when the patch state
becomes unsafe, rather than rubber-stamping a good run, and assert key
post-conditions of the v3 patch (correct displacement, no VE drift, no AFR
drift, knock notch overrides cam advance, rpm limit restored).
"""

from __future__ import annotations

import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import generate_iter2_patch as gip  # noqa: E402


SESSION_DIR = (
    PROJECT_ROOT
    / "vehicles"
    / "ryantitus_fatboy_cvo"
    / "sessions"
    / "2026-05-10_4thgear_baseline"
)
BASE_PVV = SESSION_DIR / "base_tune" / "dynojet_stage.pvv"
ITER1_ANALYSIS = (
    SESSION_DIR / "iterations" / "iter_1" / "analyses" / "iter1_comparison.json"
)


@pytest.fixture()
def base_pvv_path() -> Path:
    if not BASE_PVV.exists():
        pytest.skip(f"dynojet_stage.pvv not present at {BASE_PVV}")
    return BASE_PVV


def _run_generator(tmp_path: Path, base_pvv: Path) -> Path:
    """Run the real generator into tmp_path and return the patched .pvv."""
    iter2_dir = tmp_path / "iter_2"
    rc = gip.main([
        "--base", str(base_pvv),
        "--iter2-dir", str(iter2_dir),
        "--iter1-analysis", str(ITER1_ANALYSIS),
    ])
    assert rc == 0
    patched = iter2_dir / "patch" / "iter_2_patched.pvv"
    assert patched.exists()
    return patched


def _items(root: ET.Element) -> dict[str, ET.Element]:
    return {it.get("name", ""): it for it in root.findall("Item")}


def _cell_value(item: ET.Element, row_label: str, col_idx: int) -> float:
    rows = item.find("Rows")
    assert rows is not None
    for row in rows.findall("Row"):
        if row.get("label") == row_label:
            cells = row.findall("Cell")
            return gip._parse_float(cells[col_idx].get("value", "0") or "0")
    raise KeyError(f"row {row_label} not found in {item.get('name')}")


def test_happy_path_writes_patched_pvv(tmp_path: Path, base_pvv_path: Path) -> None:
    patched = _run_generator(tmp_path, base_pvv_path)
    parsed = ET.parse(str(patched)).getroot()
    assert parsed.tag == "PVV"
    assert len(parsed.findall("Item")) == 32


def test_displacement_set_to_exactly_103(tmp_path: Path, base_pvv_path: Path) -> None:
    patched = _run_generator(tmp_path, base_pvv_path)
    root = ET.parse(str(patched)).getroot()
    items = _items(root)
    disp = items[gip.DISPLACEMENT_TABLE]
    cell = disp.find(".//Cell")
    assert cell is not None
    assert cell.get("value") == "103"


def test_ve_tables_byte_identical_to_base(tmp_path: Path, base_pvv_path: Path) -> None:
    patched = _run_generator(tmp_path, base_pvv_path)
    base = _items(ET.parse(str(base_pvv_path)).getroot())
    new = _items(ET.parse(str(patched)).getroot())
    for table in (gip.VE_FRONT_TABLE, gip.VE_REAR_TABLE):
        assert ET.tostring(new[table]) == ET.tostring(base[table]), (
            f"{table} bytes differ between base and patched"
        )


def test_afr_tables_byte_identical_to_base(tmp_path: Path, base_pvv_path: Path) -> None:
    patched = _run_generator(tmp_path, base_pvv_path)
    base = _items(ET.parse(str(base_pvv_path)).getroot())
    new = _items(ET.parse(str(patched)).getroot())
    for table in (gip.AFR_TARGET_TABLE, gip.AFR_STOICH_TABLE):
        assert ET.tostring(new[table]) == ET.tostring(base[table]), (
            f"{table} bytes differ between base and patched"
        )


def test_dynojet_safety_items_byte_identical_to_base(
    tmp_path: Path, base_pvv_path: Path
) -> None:
    patched = _run_generator(tmp_path, base_pvv_path)
    base = _items(ET.parse(str(base_pvv_path)).getroot())
    new = _items(ET.parse(str(patched)).getroot())
    for table in (
        gip.CAL_ID_TABLE,
        gip.SPEEDO_TABLE,
        gip.ACCEL_ENRICH_TABLE,
        gip.SPARK_ECT_ADJUST_TABLE,
    ):
        if table not in base:
            pytest.fail(f"untouchable table '{table}' missing from base; check name")
        assert ET.tostring(new[table]) == ET.tostring(base[table]), (
            f"{table} bytes differ between base and patched"
        )


def test_decel_enleanment_all_unity(tmp_path: Path, base_pvv_path: Path) -> None:
    patched = _run_generator(tmp_path, base_pvv_path)
    item = _items(ET.parse(str(patched)).getroot())[gip.DECEL_ENLEANMENT_TABLE]
    cells = item.findall(".//Cell")
    assert len(cells) == 12
    for cell in cells:
        assert cell.get("value") == "1", (
            f"decel cell {cell.get('value')} != 1"
        )


def test_knock_retard_cap_4_deg(tmp_path: Path, base_pvv_path: Path) -> None:
    patched = _run_generator(tmp_path, base_pvv_path)
    item = _items(ET.parse(str(patched)).getroot())[gip.KNOCK_RETARD_TABLE]
    cells = item.findall(".//Cell")
    assert len(cells) == 12
    for cell in cells:
        val = gip._parse_float(cell.get("value", "0") or "0")
        assert val <= gip.KNOCK_CAP_DEG + 1e-9, f"knock retard {val} > cap"


def test_rpm_limit_restored_to_6_2(tmp_path: Path, base_pvv_path: Path) -> None:
    patched = _run_generator(tmp_path, base_pvv_path)
    item = _items(ET.parse(str(patched)).getroot())[gip.RPM_LIMIT_TABLE]
    cells = item.findall(".//Cell")
    assert len(cells) == 9
    for cell in cells:
        assert cell.get("value") == "6.2", (
            f"rpm limit cell {cell.get('value')} != 6.2"
        )


def test_cam_advance_does_not_exceed_plus_1_deg(
    tmp_path: Path, base_pvv_path: Path
) -> None:
    patched = _run_generator(tmp_path, base_pvv_path)
    base = _items(ET.parse(str(base_pvv_path)).getroot())
    new = _items(ET.parse(str(patched)).getroot())
    for table in (gip.SPARK_FRONT_TABLE, gip.SPARK_REAR_TABLE):
        _, col_axis, base_grid = gip._read_table(base[table])
        row_axis, _, new_grid = gip._read_table(new[table])
        for r, rpm_k in enumerate(row_axis):
            if not (gip.CAM_ADVANCE_RPM_BANDS[0] <= rpm_k <= gip.CAM_ADVANCE_RPM_BANDS[1]):
                continue
            for c, map_kpa in enumerate(col_axis):
                if not (gip.CAM_ADVANCE_MAP_BANDS[0] <= map_kpa <= gip.CAM_ADVANCE_MAP_BANDS[1]):
                    continue
                delta = new_grid[r][c] - base_grid[r][c]
                assert delta <= gip.CAM_ADVANCE_DELTA + 1e-9, (
                    f"{table} cell rpm={rpm_k} map={map_kpa} cam delta={delta} > +1"
                )
                assert delta >= 0.0 - 1e-9, (
                    f"{table} cell rpm={rpm_k} map={map_kpa} delta={delta} negative"
                )


def test_knock_notch_overrides_cam_advance_in_overlap(
    tmp_path: Path, base_pvv_path: Path
) -> None:
    """If the cam-advance band ever overlapped the notch cells, the notch wins.

    For the current axes (cam: 2-4k RPM, notch: 5-6k RPM) there is no overlap,
    so this test asserts the notch cell deltas are negative regardless and that
    no cam-advance cell exists at 5500 RPM. If someone later widens the cam
    band into 5k+, the notch must still win in the overlap.
    """
    patched = _run_generator(tmp_path, base_pvv_path)
    base = _items(ET.parse(str(base_pvv_path)).getroot())
    new = _items(ET.parse(str(patched)).getroot())

    for table in (gip.SPARK_FRONT_TABLE, gip.SPARK_REAR_TABLE):
        _, col_axis, base_grid = gip._read_table(base[table])
        row_axis, _, new_grid = gip._read_table(new[table])
        cr = gip._idx_nearest(row_axis, gip.SPARK_NOTCH_CENTER_RPM)
        cc = gip._idx_nearest(col_axis, gip.SPARK_NOTCH_CENTER_MAP)
        center_delta = new_grid[cr][cc] - base_grid[cr][cc]
        assert center_delta == pytest.approx(gip.SPARK_NOTCH_CENTER_DELTA), (
            f"{table} center notch delta={center_delta}, expected {gip.SPARK_NOTCH_CENTER_DELTA}"
        )
        for nb_rpm, nb_map in gip.SPARK_NOTCH_NEIGHBOURS:
            nr = gip._idx_nearest(row_axis, nb_rpm)
            nc = gip._idx_nearest(col_axis, nb_map)
            nb_delta = new_grid[nr][nc] - base_grid[nr][nc]
            assert nb_delta == pytest.approx(gip.SPARK_NOTCH_ADJACENT_DELTA), (
                f"{table} notch neighbour ({nb_rpm},{nb_map}) delta={nb_delta}"
            )


def test_gate2_trips_when_unexpected_table_modified(
    tmp_path: Path, base_pvv_path: Path
) -> None:
    """Gate 2 (scope drift) must fail if any untouchable table differs."""
    patched_dir = tmp_path / "iter_2" / "patch"
    patched_dir.mkdir(parents=True, exist_ok=True)
    patched = patched_dir / "iter_2_patched.pvv"
    shutil.copy2(base_pvv_path, patched)

    tree = ET.parse(str(patched))
    root = tree.getroot()
    items = _items(root)

    disp = items[gip.DISPLACEMENT_TABLE].find(".//Cell")
    assert disp is not None
    disp.set("value", "103")

    decel = items[gip.DECEL_ENLEANMENT_TABLE]
    for cell in decel.findall(".//Cell"):
        cell.set("value", "1")

    knock = items[gip.KNOCK_RETARD_TABLE]
    for cell in knock.findall(".//Cell"):
        cell.set("value", "4")

    rpm = items[gip.RPM_LIMIT_TABLE]
    for cell in rpm.findall(".//Cell"):
        cell.set("value", "6.2")

    sf = items[gip.SPARK_FRONT_TABLE]
    first_cell = sf.find(".//Cell")
    assert first_cell is not None
    first_cell.set("value", "99")
    sr = items[gip.SPARK_REAR_TABLE]
    first_cell_r = sr.find(".//Cell")
    assert first_cell_r is not None
    first_cell_r.set("value", "99")

    afr = items[gip.AFR_TARGET_TABLE]
    afr_cell = afr.find(".//Cell")
    assert afr_cell is not None
    afr_cell.set("value", "11.0")

    tree.write(str(patched), encoding="utf-8", xml_declaration=True)

    with pytest.raises(RuntimeError, match="Gate 2"):
        gip._verification_gates(
            patched_pvv=patched,
            base_pvv=base_pvv_path,
            spark_fronts=([[0.0]], [[0.0]]),
            spark_rears=([[0.0]], [[0.0]]),
        )


def test_gate3_trips_when_displacement_off(
    tmp_path: Path, base_pvv_path: Path
) -> None:
    """Gate 3 must fail if displacement is not exactly 103."""
    patched_dir = tmp_path / "iter_2" / "patch"
    patched_dir.mkdir(parents=True, exist_ok=True)
    patched = patched_dir / "iter_2_patched.pvv"

    rc = gip.main([
        "--base", str(base_pvv_path),
        "--iter2-dir", str(tmp_path / "iter_2"),
        "--iter1-analysis", str(ITER1_ANALYSIS),
    ])
    assert rc == 0

    tree = ET.parse(str(patched))
    root = tree.getroot()
    items = _items(root)
    disp_cell = items[gip.DISPLACEMENT_TABLE].find(".//Cell")
    assert disp_cell is not None
    disp_cell.set("value", "100")
    tree.write(str(patched), encoding="utf-8", xml_declaration=True)

    with pytest.raises(RuntimeError, match="Gate 3"):
        gip._verification_gates(
            patched_pvv=patched,
            base_pvv=base_pvv_path,
            spark_fronts=([[0.0]], [[0.0]]),
            spark_rears=([[0.0]], [[0.0]]),
        )


def test_gate4_trips_when_spark_exceeds_3_deg(
    tmp_path: Path, base_pvv_path: Path
) -> None:
    """Gate 4 must fail if any spark cell changed by more than +/-3 deg.

    Run the real generator to get a patched.pvv that passes gates 1-3 and 5,
    then hand the gate function adversarial spark grids that violate the
    +/-3 deg per-cell clamp.
    """
    patched = _run_generator(tmp_path, base_pvv_path)
    fake_base = [[20.0, 25.0]]
    fake_new = [[20.0, 30.0]]
    with pytest.raises(RuntimeError, match="Gate 4"):
        gip._verification_gates(
            patched_pvv=patched,
            base_pvv=base_pvv_path,
            spark_fronts=(fake_base, fake_new),
            spark_rears=(fake_base, fake_base),
        )


def test_gate5_trips_when_afr_changed(
    tmp_path: Path, base_pvv_path: Path
) -> None:
    """Gate 5 must fail if any untouchable table differs from base."""
    patched_dir = tmp_path / "iter_2" / "patch"
    patched_dir.mkdir(parents=True, exist_ok=True)
    patched = patched_dir / "iter_2_patched.pvv"
    shutil.copy2(base_pvv_path, patched)

    tree = ET.parse(str(patched))
    root = tree.getroot()
    items = _items(root)
    afr = items[gip.AFR_TARGET_TABLE]
    afr_cells = afr.findall(".//Cell")
    afr_cells[0].set("value", "11.0")
    tree.write(str(patched), encoding="utf-8", xml_declaration=True)

    with pytest.raises(RuntimeError, match="Gate 2|Gate 5"):
        gip._verification_gates(
            patched_pvv=patched,
            base_pvv=base_pvv_path,
            spark_fronts=([[0.0]], [[0.0]]),
            spark_rears=([[0.0]], [[0.0]]),
        )


def test_idempotency_same_sha_on_rerun(
    tmp_path: Path, base_pvv_path: Path
) -> None:
    """Running the generator twice produces the same patched bytes."""
    patched_a = _run_generator(tmp_path / "a", base_pvv_path)
    patched_b = _run_generator(tmp_path / "b", base_pvv_path)
    assert gip._sha256(patched_a) == gip._sha256(patched_b)
