"""Test the auto-tune workflow with real Power Vision data."""

import sys
import xml.etree.ElementTree as ET
import json
from pathlib import Path

import pandas as pd

from api.services.autotune_workflow import AutoTuneWorkflow, DataSource
from api.services.integrations.powercore import surgical_pvv_writer as writer
from api.services.powercore_integration import find_log_files

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_full_workflow():
    """Test the complete auto-tune workflow."""
    print("=== Testing Auto-Tune Workflow ===")
    print()

    # Find a log file
    logs = find_log_files()
    if not logs:
        print("No log files found - skipping test")
        return

    # Use the largest log file
    log_file = max(logs, key=lambda p: p.stat().st_size)
    print(f"Using log: {log_file.name} ({log_file.stat().st_size / 1024:.1f} KB)")
    print()

    # Create workflow
    workflow = AutoTuneWorkflow()

    # Run full workflow
    output_dir = "outputs/autotune_test"
    session = workflow.run_full_workflow(
        log_path=str(log_file),
        output_dir=output_dir,
    )

    # Print summary
    summary = workflow.get_session_summary(session)
    print("=== Session Summary ===")
    print(f"ID: {summary.get('run_id', 'N/A')}")
    print(f"Status: {summary.get('status', 'unknown')}")
    print()

    if "afr_analysis" in summary:
        afr = summary["afr_analysis"]
        print("AFR Analysis:")
        print(f"  Mean Error: {afr['mean_error_pct']}%")
        print(f"  Zones Lean: {afr['zones_lean']}")
        print(f"  Zones Rich: {afr['zones_rich']}")
        print(f"  Zones OK: {afr['zones_ok']}")
        print()

    if "ve_corrections" in summary:
        corr = summary["ve_corrections"]
        print("VE Corrections:")
        print(f"  Zones Adjusted: {corr['zones_adjusted']}")
        print(f"  Max Correction: {corr['max_correction_pct']}%")
        print(f"  Min Correction: {corr['min_correction_pct']}%")
        print(f"  Clipped Zones: {corr['clipped_zones']}")
        print()

    if summary.get("output_tunelab_script"):
        print(f"TuneLab Script: {summary['output_tunelab_script']}")
    if summary.get("output_pvv_file"):
        print(f"PVV File: {summary['output_pvv_file']}")

    if summary.get("errors"):
        print(f"Errors: {summary['errors']}")

    print()
    print("=== Workflow Test Complete ===")

    # Verify outputs exist
    if summary.get("output_tunelab_script"):
        assert Path(summary["output_tunelab_script"]).exists()
    if summary.get("output_pvv_file"):
        assert Path(summary["output_pvv_file"]).exists()


if __name__ == "__main__":
    test_full_workflow()


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


def _normalize_running9_to_workflow_csv(tmp_path: Path) -> Path:
    raw = pd.read_csv(_seanbike_pull_path())
    raw.columns = [str(c).strip() for c in raw.columns]

    rpm_col = "(DWRT CPU) Engine RPM"
    tps_col = "(PV) Throttle Position"
    afr_col = "(DWRT CPU) LC1 Volts Petrol AFR"
    if rpm_col not in raw.columns or tps_col not in raw.columns or afr_col not in raw.columns:
        raise AssertionError(
            "Expected Seanbike columns missing from runnning_9.txt: "
            f"need {rpm_col}, {tps_col}, {afr_col}"
        )

    normalized = pd.DataFrame(
        {
            "Engine RPM": pd.to_numeric(raw[rpm_col], errors="coerce"),
            "Throttle Position": pd.to_numeric(raw[tps_col], errors="coerce"),
            "AFR Meas": pd.to_numeric(raw[afr_col], errors="coerce"),
        }
    ).dropna(subset=["Engine RPM", "Throttle Position", "AFR Meas"])

    # Keep only physically plausible rows so hit-count bins represent true data.
    normalized = normalized[
        # DynoWare exports kRPM for this channel (e.g. 2.5 == 2500 RPM).
        (normalized["Engine RPM"] > 0.5)
        & (normalized["Engine RPM"] <= 8.0)
        & (normalized["Throttle Position"] >= 0)
        & (normalized["Throttle Position"] <= 100)
        & (normalized["AFR Meas"] >= 7.0)
        & (normalized["AFR Meas"] <= 23.0)
    ].reset_index(drop=True)

    csv_path = tmp_path / "running9_normalized.csv"
    normalized.to_csv(csv_path, index=False)
    return csv_path


def _changed_item_ids(base_root: ET.Element, out_root: ET.Element) -> list[str]:
    base_cells = writer._collect_item_cells(base_root)
    out_cells = writer._collect_item_cells(out_root)
    return sorted(
        item_id for item_id in base_cells.keys() if base_cells[item_id] != out_cells[item_id]
    )


def test_workflow_configures_grid_from_base_pvv() -> None:
    base_pvv = _seanbike_base_pvv()
    workflow = AutoTuneWorkflow(
        base_pvv_path=base_pvv,
        target_ve_table_ids=VE_TABLE_IDS,
    )
    axes = writer.load_ve_table_axes(base_pvv, VE_TABLE_IDS)[VE_TABLE_IDS[0]]

    assert workflow.rpm_axis == [float(v) for v in axes.row_axis.tolist()]
    assert workflow.load_axis == [float(v) for v in axes.col_axis.tolist()]
    assert workflow.map_axis == [float(v) for v in axes.col_axis.tolist()]
    assert workflow.load_channel == "TPS"


def test_full_workflow_produces_flashable_pvv(tmp_path: Path) -> None:
    base_pvv = _seanbike_base_pvv()
    normalized_log = _normalize_running9_to_workflow_csv(tmp_path)

    workflow = AutoTuneWorkflow(
        base_pvv_path=base_pvv,
        target_ve_table_ids=VE_TABLE_IDS,
        ve_cap=155.0,
        max_correction_pct=10.0,
    )
    session = workflow.run_full_workflow(
        log_path=str(normalized_log),
        output_dir=str(tmp_path / "workflow_out"),
        tune_path=str(base_pvv),
        data_source=DataSource.JETDRIVE,
    )

    assert session.errors == []
    assert session.output_pvv_file is not None

    output_pvv = Path(session.output_pvv_file)
    assert output_pvv.exists()
    ET.parse(output_pvv)  # parse succeeds => well-formed XML

    base_root = ET.parse(base_pvv).getroot()
    out_root = ET.parse(output_pvv).getroot()

    base_ids = {item.get("id", "") for item in base_root.findall("Item")}
    out_ids = {item.get("id", "") for item in out_root.findall("Item")}
    assert base_ids == out_ids

    changed_ids = _changed_item_ids(base_root, out_root)
    assert changed_ids == sorted(VE_TABLE_IDS)

    patch_manifest_path = output_pvv.with_suffix(".manifest.json")
    assert patch_manifest_path.exists()
    patch_manifest = json.loads(patch_manifest_path.read_text(encoding="utf-8"))
    assert sorted(patch_manifest["output"]["changed_ids"]) == sorted(VE_TABLE_IDS)
