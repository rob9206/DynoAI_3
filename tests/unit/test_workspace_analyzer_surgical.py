"""Integration tests for workspace analyzer surgical PVV path."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from api.services import integrations
from api.services.tuning_workspace import TuningWorkspace
from api.services.workspace_analyzer import analyze_iteration

VE_TABLE_IDS = ["tbl_ve_tps_based_front_cyl", "tbl_ve_tps_based_rear_cyl"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _seanbike_base_pvv() -> Path:
    return (
        _repo_root()
        / "vehicles"
        / "seanbike"
        / "sessions"
        / "dai_2026_0518_pcv_bake_verify"
        / "iterations"
        / "iter_0"
        / "patches"
        / "newnenww_emergency_rich_v5_stepup.pvv"
    )


def _seanbike_pull_path() -> Path:
    return (
        _repo_root()
        / "vehicles"
        / "seanbike"
        / "sessions"
        / "dai_2026_0518_pcv_bake_verify"
        / "iterations"
        / "iter_0"
        / "pulls"
        / "runnning_9.txt"
    )


def _normalize_running9() -> bytes:
    raw = pd.read_csv(_seanbike_pull_path())
    raw.columns = [str(c).strip() for c in raw.columns]

    rpm_col = "(DWRT CPU) Engine RPM"
    tps_col = "(PV) Throttle Position"
    afr_col = "(DWRT CPU) LC1 Volts Petrol AFR"

    normalized = pd.DataFrame(
        {
            "Engine RPM": pd.to_numeric(raw[rpm_col], errors="coerce"),
            "Throttle Position": pd.to_numeric(raw[tps_col], errors="coerce"),
            "AFR Meas": pd.to_numeric(raw[afr_col], errors="coerce"),
        }
    ).dropna(subset=["Engine RPM", "Throttle Position", "AFR Meas"])

    normalized = normalized[
        (normalized["Engine RPM"] > 0.5)
        & (normalized["Engine RPM"] <= 8.0)
        & (normalized["Throttle Position"] >= 0)
        & (normalized["Throttle Position"] <= 100)
        & (normalized["AFR Meas"] >= 7.0)
        & (normalized["AFR Meas"] <= 23.0)
    ].reset_index(drop=True)

    return normalized.to_csv(index=False).encode("utf-8")


def _changed_item_ids(base_root: ET.Element, out_root: ET.Element) -> list[str]:
    base_cells = integrations.powercore.surgical_pvv_writer._collect_item_cells(base_root)
    out_cells = integrations.powercore.surgical_pvv_writer._collect_item_cells(out_root)
    return sorted(item_id for item_id in base_cells if base_cells[item_id] != out_cells[item_id])


def _make_workspace(tmp_path: Path, *, with_guardrails: bool = True, with_base_tune: bool = True) -> tuple[TuningWorkspace, str, str]:
    ws = TuningWorkspace(root=tmp_path / "vehicles")

    vehicle = ws.create_vehicle(
        name="Seanbike test",
        vehicle_id="seanbike_test",
        tuning_guardrails=(
            {
                "ve_table_ids": VE_TABLE_IDS,
                "ve_cap_pct": 155.0,
                "ve_floor_pct": 70.0,
                "max_correction_pct_per_cell": 10.0,
            }
            if with_guardrails
            else {}
        ),
    )
    session = ws.create_session(vehicle_id=vehicle.id, session_id="session_1")

    if with_base_tune:
        ws.set_base_tune(vehicle.id, session.id, _seanbike_base_pvv().read_bytes())

    ws.add_pull(vehicle.id, session.id, "iter_0", "running9_normalized.csv", _normalize_running9())
    return ws, vehicle.id, session.id


def test_workspace_analyzer_uses_surgical_writer_and_surfaces_metadata(tmp_path: Path) -> None:
    ws, vehicle_id, session_id = _make_workspace(tmp_path)

    result = analyze_iteration(vehicle_id, session_id, workspace=ws)

    assert result.success is True
    assert result.errors == []
    assert result.correction_pvv_path is not None
    assert result.correction_pvv_filename is not None
    assert result.correction_pvv_sha256 is not None
    assert result.correction_pvv_n_changed_cells is not None
    assert result.correction_pvv_n_changed_cells > 0
    assert result.correction_manifest_path is not None

    output_pvv = Path(result.correction_pvv_path)
    assert output_pvv.exists()
    ET.parse(output_pvv)

    manifest_path = Path(result.correction_manifest_path)
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert sorted(manifest["output"]["changed_ids"]) == sorted(VE_TABLE_IDS)
    assert manifest["output"]["sha256"] == result.correction_pvv_sha256

    base_root = ET.parse(_seanbike_base_pvv()).getroot()
    out_root = ET.parse(output_pvv).getroot()
    assert _changed_item_ids(base_root, out_root) == sorted(VE_TABLE_IDS)

    rerun = analyze_iteration(vehicle_id, session_id, workspace=ws)
    assert rerun.success is True
    assert rerun.correction_pvv_sha256 == result.correction_pvv_sha256


def test_workspace_analyzer_requires_base_tune(tmp_path: Path) -> None:
    ws, vehicle_id, session_id = _make_workspace(tmp_path, with_base_tune=False)

    result = analyze_iteration(vehicle_id, session_id, workspace=ws)

    assert result.success is False
    assert "no base tune uploaded" in result.errors


def test_workspace_analyzer_requires_tuning_guardrails(tmp_path: Path) -> None:
    ws, vehicle_id, session_id = _make_workspace(tmp_path, with_guardrails=False)

    result = analyze_iteration(vehicle_id, session_id, workspace=ws)

    assert result.success is False
    assert "profile.json missing tuning_guardrails block" in result.errors
