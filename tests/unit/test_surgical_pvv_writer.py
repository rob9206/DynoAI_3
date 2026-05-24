from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

from api.services.integrations.powercore import surgical_pvv_writer as writer

VE_TABLE_IDS = ["tbl_ve_tps_based_front_cyl", "tbl_ve_tps_based_rear_cyl"]


def _fixture_pvv_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return (
        repo_root
        / "vehicles"
        / "seanbike"
        / "sessions"
        / "dai_2026_0518_pcv_bake_verify"
        / "iterations"
        / "iter_0"
        / "patches"
        / "newnenww_emergency_rich_v5_stepup.pvv"
    )


def _table_values(root: ET.Element, table_id: str) -> np.ndarray:
    table = writer._parse_table(root, table_id)
    return table.values.copy()


def _all_cell_values_by_id(root: ET.Element) -> dict[str, list[str]]:
    return writer._collect_item_cells(root)


def _corrections_from_axes(fill_value: float) -> dict[str, np.ndarray]:
    axes = writer.load_ve_table_axes(_fixture_pvv_path(), VE_TABLE_IDS)
    return {table_id: np.full(meta.shape, fill_value) for table_id, meta in axes.items()}


def test_identity_correction_round_trips_byte_identical_cells(tmp_path: Path) -> None:
    base_path = _fixture_pvv_path()
    out_path = tmp_path / "identity_out.pvv"
    result = writer.write_ve_correction_patch(
        base_path,
        out_path,
        corrections=_corrections_from_axes(1.0),
    )

    assert result.changed_ids == []

    base_root = ET.parse(base_path).getroot()
    out_root = ET.parse(out_path).getroot()

    base_ids = {item.get("id", "") for item in base_root.findall("Item")}
    out_ids = {item.get("id", "") for item in out_root.findall("Item")}
    assert base_ids == out_ids
    assert _all_cell_values_by_id(base_root) == _all_cell_values_by_id(out_root)


def test_uniform_plus_10pct_matches_exact_arithmetic(tmp_path: Path) -> None:
    base_path = _fixture_pvv_path()
    out_path = tmp_path / "plus10_out.pvv"
    writer.write_ve_correction_patch(
        base_path,
        out_path,
        corrections=_corrections_from_axes(1.10),
    )

    base_root = ET.parse(base_path).getroot()
    out_root = ET.parse(out_path).getroot()

    for table_id in VE_TABLE_IDS:
        before = _table_values(base_root, table_id)
        after = _table_values(out_root, table_id)
        expected = before * 1.10
        assert np.allclose(after, expected, rtol=0.0, atol=1e-4), table_id


def test_ve_cap_clamps_high_cells(tmp_path: Path) -> None:
    base_path = _fixture_pvv_path()
    out_path = tmp_path / "cap_out.pvv"
    result = writer.write_ve_correction_patch(
        base_path,
        out_path,
        corrections=_corrections_from_axes(10.0),
        ve_cap=140.0,
    )

    out_root = ET.parse(out_path).getroot()
    maxima = []
    has_cap_hit = False
    for table_id in VE_TABLE_IDS:
        values = _table_values(out_root, table_id)
        maxima.append(float(np.max(values)))
        has_cap_hit = has_cap_hit or bool(np.any(np.isclose(values, 140.0)))

    assert max(maxima) <= 140.0 + 1e-9
    assert has_cap_hit
    assert result.capped_cells > 0


def test_unauthorized_change_raises_and_deletes_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_path = _fixture_pvv_path()
    out_path = tmp_path / "unauthorized_out.pvv"

    original_verify = writer._verify_output_integrity

    def _mutating_verify(
        input_root: ET.Element, output_root: ET.Element, allowed_changed_ids: set[str]
    ) -> list[str]:
        afr_item = writer._find_item_by_id(output_root, "tbl_afr")
        afr_cell = afr_item.find("./Rows/Row/Cell")
        assert afr_cell is not None
        afr_cell.set("value", "999.99")
        return original_verify(input_root, output_root, allowed_changed_ids)

    monkeypatch.setattr(writer, "_verify_output_integrity", _mutating_verify)

    with pytest.raises(RuntimeError, match="Unexpected non-approved item ids changed"):
        writer.write_ve_correction_patch(
            base_path,
            out_path,
            corrections=_corrections_from_axes(1.05),
        )

    assert not out_path.exists()


def test_manifest_contains_required_fields(tmp_path: Path) -> None:
    base_path = _fixture_pvv_path()
    out_path = tmp_path / "manifest_out.pvv"
    result = writer.write_ve_correction_patch(
        base_path,
        out_path,
        corrections=_corrections_from_axes(1.05),
        manifest_extra={"session_id": "s_test"},
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert manifest["kind"] == "ve_correction_surgical_patch"
    assert "base_pvv" in manifest["inputs"]
    assert "base_sha256" in manifest["inputs"]
    assert "output" in manifest
    assert "sha256" in manifest["output"]
    assert "changed_ids" in manifest["output"]
    assert "table_stats" in manifest
    assert manifest["table_stats"]
    assert manifest["extra"]["session_id"] == "s_test"
