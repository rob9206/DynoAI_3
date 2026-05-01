"""Tests for the TuneLab autotune preview CLI entrypoint."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[2]
CLI_MODULE = "tools.autotune.tunelab_entrypoint"


def _run_cli(
    *,
    log_csv: Path,
    output_dir: Path,
    extra_args: list[str] | None = None,
    run_id: str = "tests/f1_cli",
):
    cmd = [
        sys.executable,
        "-m",
        CLI_MODULE,
        "--log-csv",
        str(log_csv),
        "--output-dir",
        str(output_dir),
        "--run-id",
        run_id,
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)


def _run_apply_cli(
    *,
    run_id: str,
    output_dir: Path,
    base_front: Path,
    base_rear: Path,
    extra_args: list[str] | None = None,
):
    cmd = [
        sys.executable,
        "-m",
        CLI_MODULE,
        "apply",
        "--run-id",
        run_id,
        "--output-dir",
        str(output_dir),
        "--base-front",
        str(base_front),
        "--base-rear",
        str(base_rear),
        "--mode",
        "dual_cylinder",
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)


def _build_dual_afr_frame(*, front_afr: float, rear_afr: float) -> pd.DataFrame:
    rows: list[dict[str, float]] = []
    # Provide enough hits per cell for workflow MIN_HITS_PER_ZONE=3.
    base_cells = [(2000, 40), (3000, 60), (4000, 80)]
    timestamp = 0
    for rpm, map_kpa in base_cells:
        for _ in range(6):
            rows.append(
                {
                    "timestamp_ms": timestamp,
                    "Engine RPM": float(rpm),
                    "MAP kPa": float(map_kpa),
                    "AFR Meas F": float(front_afr),
                    "AFR Meas R": float(rear_afr),
                    "TPS": 25.0,
                }
            )
            timestamp += 10
    return pd.DataFrame(rows)


def _load_summary(summary_path: Path) -> dict:
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _load_grid(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, index_col=0)
    df.index = df.index.astype(int)
    df.columns = df.columns.astype(int)
    return df


def _write_base_ve_csv(path: Path, rpm_axis: list[float], map_axis: list[float], value: float) -> None:
    def _fmt(axis_value: float) -> str:
        as_float = float(axis_value)
        if as_float.is_integer():
            return str(int(as_float))
        return f"{as_float:.3f}".rstrip("0").rstrip(".")

    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("RPM," + ",".join(_fmt(v) for v in map_axis) + "\n")
        for rpm in rpm_axis:
            row = [f"{float(value):.4f}" for _ in map_axis]
            handle.write(_fmt(rpm) + "," + ",".join(row) + "\n")


def test_cli_missing_afr_column_returns_nonzero(tmp_path: Path) -> None:
    frame = _build_dual_afr_frame(front_afr=14.0, rear_afr=13.5).drop(columns=["AFR Meas R"])
    log_csv = tmp_path / "missing_rear.csv"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=tmp_path / "out")

    assert result.returncode != 0
    assert "[F1][ERR] missing_column: AFR Meas R" in result.stderr


def test_cli_happy_path_emits_both_csvs_and_summary(tmp_path: Path) -> None:
    frame = _build_dual_afr_frame(front_afr=14.2, rear_afr=13.1)
    log_csv = tmp_path / "input.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=out_dir)

    assert result.returncode == 0, result.stderr
    front_csv = out_dir / "VE_Front_Correction_2D.csv"
    rear_csv = out_dir / "VE_Rear_Correction_2D.csv"
    summary_json = out_dir / "correction_summary.json"
    assert front_csv.exists()
    assert rear_csv.exists()
    assert summary_json.exists()

    front_grid = _load_grid(front_csv)
    rear_grid = _load_grid(rear_csv)
    assert front_grid.shape == (11, 9)
    assert rear_grid.shape == (11, 9)
    assert front_grid.apply(pd.to_numeric, errors="coerce").notna().all().all()
    assert rear_grid.apply(pd.to_numeric, errors="coerce").notna().all().all()


def test_cli_summary_schema_v1_fields_present(tmp_path: Path) -> None:
    frame = _build_dual_afr_frame(front_afr=14.0, rear_afr=13.2)
    log_csv = tmp_path / "schema.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=out_dir)

    assert result.returncode == 0, result.stderr
    summary = _load_summary(out_dir / "correction_summary.json")
    expected_top_level = {
        "schema_version",
        "log_csv",
        "run_id",
        "mode",
        "afr_target_source",
        "grid",
        "front",
        "rear",
        "overall_max_pct",
        "warn_threshold_pct",
        "over_warn_threshold",
        "safety",
    }
    assert expected_top_level.issubset(summary.keys())
    assert summary["mode"] == "dual_cylinder"


def test_preview_summary_includes_safety_block(tmp_path: Path) -> None:
    frame = _build_dual_afr_frame(front_afr=14.0, rear_afr=13.2)
    log_csv = tmp_path / "safety_block.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=out_dir)

    assert result.returncode == 0, result.stderr
    summary = _load_summary(out_dir / "correction_summary.json")
    safety = summary.get("safety")
    assert isinstance(safety, dict)
    assert float(safety["block_threshold_pct"]) == 25.0
    assert float(safety["warn_threshold_pct"]) == 10.0
    assert safety["apply_blocked"] is False
    assert safety["apply_blocked_reasons"] == []


def test_preview_blocks_on_extreme_correction(tmp_path: Path) -> None:
    frame = _build_dual_afr_frame(front_afr=20.5, rear_afr=20.1)
    log_csv = tmp_path / "extreme.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=out_dir)

    assert result.returncode == 0, result.stderr
    summary = _load_summary(out_dir / "correction_summary.json")
    safety = summary["safety"]
    assert safety["apply_blocked"] is True
    assert any(reason["type"] == "extreme_correction" for reason in safety["apply_blocked_reasons"])


def test_preview_blocks_in_single_cylinder_mode(tmp_path: Path) -> None:
    frame = _build_dual_afr_frame(front_afr=14.1, rear_afr=13.1).drop(columns=["AFR Meas F"])
    log_csv = tmp_path / "single_mode.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(
        log_csv=log_csv,
        output_dir=out_dir,
        extra_args=["--single-cylinder", "rear"],
    )

    assert result.returncode == 0, result.stderr
    summary = _load_summary(out_dir / "correction_summary.json")
    safety = summary["safety"]
    assert safety["apply_blocked"] is True
    assert any(reason["type"] == "partial_cylinder" for reason in safety["apply_blocked_reasons"])


def test_preview_emit_pvv_patch_writes_pvv(tmp_path: Path) -> None:
    frame = _build_dual_afr_frame(front_afr=14.0, rear_afr=13.3)
    log_csv = tmp_path / "emit_pvv.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(
        log_csv=log_csv,
        output_dir=out_dir,
        extra_args=["--emit-pvv-patch"],
    )

    assert result.returncode == 0, result.stderr
    summary = _load_summary(out_dir / "correction_summary.json")
    pvv_name = summary.get("pvv_patch")
    assert isinstance(pvv_name, str) and pvv_name.endswith(".pvv")
    pvv_path = out_dir / pvv_name
    assert pvv_path.exists()
    root = ET.parse(pvv_path).getroot()
    item_names = {item.attrib.get("name", "") for item in root.findall("Item")}
    assert any(name.startswith("VE Correction") for name in item_names)


def test_preview_pvv_patch_default_off(tmp_path: Path) -> None:
    frame = _build_dual_afr_frame(front_afr=14.0, rear_afr=13.3)
    log_csv = tmp_path / "pvv_default_off.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=out_dir)
    assert result.returncode == 0, result.stderr
    summary = _load_summary(out_dir / "correction_summary.json")
    assert "pvv_patch" not in summary
    assert list(out_dir.glob("*.pvv")) == []


def test_apply_subcommand_writes_ve_applied_and_session_log(tmp_path: Path) -> None:
    run_id = f"tests_apply_{tmp_path.name}"
    run_dir = ROOT / "runs" / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    try:
        frame = _build_dual_afr_frame(front_afr=14.2, rear_afr=13.1)
        log_csv = tmp_path / "apply_input.csv"
        out_dir = tmp_path / "out"
        frame.to_csv(log_csv, index=False)

        preview_result = _run_cli(log_csv=log_csv, output_dir=out_dir, run_id=run_id)
        assert preview_result.returncode == 0, preview_result.stderr

        summary = _load_summary(out_dir / "correction_summary.json")
        rpm_axis = summary["grid"]["rpm_axis"]
        map_axis = summary["grid"]["map_axis"]
        base_front = tmp_path / "base_front.csv"
        base_rear = tmp_path / "base_rear.csv"
        _write_base_ve_csv(base_front, rpm_axis, map_axis, 100.0)
        _write_base_ve_csv(base_rear, rpm_axis, map_axis, 102.0)

        apply_result = _run_apply_cli(
            run_id=run_id,
            output_dir=out_dir,
            base_front=base_front,
            base_rear=base_rear,
        )
        assert apply_result.returncode == 0, apply_result.stderr
        assert "apply_front=" in apply_result.stdout
        assert "apply_rear=" in apply_result.stdout
        assert "session_log=" in apply_result.stdout

        line = next(
            line for line in apply_result.stdout.splitlines() if line.startswith("[F1][OK]")
        )
        match = re.search(
            r"apply_front=(\S+)\s+apply_rear=(\S+)\s+session_log=(\S+)",
            line,
        )
        assert match is not None
        apply_front_path = Path(match.group(1))
        apply_rear_path = Path(match.group(2))
        session_log_path = Path(match.group(3))
        assert apply_front_path.exists()
        assert apply_rear_path.exists()
        assert session_log_path.exists()

        applied_front_grid = _load_grid(apply_front_path)
        applied_rear_grid = _load_grid(apply_rear_path)
        assert applied_front_grid.shape == (11, 9)
        assert applied_rear_grid.shape == (11, 9)

        session_log = json.loads(session_log_path.read_text(encoding="utf-8"))
        apply_events = [
            event for event in session_log.get("events", []) if event.get("type") == "apply"
        ]
        assert len(apply_events) >= 2
    finally:
        if run_dir.exists():
            shutil.rmtree(run_dir)


def test_preview_schema_v1_adds_safety_field(tmp_path: Path) -> None:
    frame = _build_dual_afr_frame(front_afr=14.0, rear_afr=13.2)
    log_csv = tmp_path / "schema_safety.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=out_dir)
    assert result.returncode == 0, result.stderr
    summary = _load_summary(out_dir / "correction_summary.json")
    assert "safety" in summary


def test_cli_afr_target_source_defaults_to_static_map_curve_v1(tmp_path: Path) -> None:
    frame = _build_dual_afr_frame(front_afr=14.0, rear_afr=13.3)
    log_csv = tmp_path / "target_source.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=out_dir)

    assert result.returncode == 0, result.stderr
    summary = _load_summary(out_dir / "correction_summary.json")
    assert summary["afr_target_source"] == "static_map_curve_v1"


def test_cli_summary_flags_over_threshold(tmp_path: Path) -> None:
    # Very lean front/rear AFR values should trigger warn threshold gating.
    frame = _build_dual_afr_frame(front_afr=20.0, rear_afr=19.8)
    log_csv = tmp_path / "lean.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=out_dir)

    assert result.returncode == 0, result.stderr
    summary = _load_summary(out_dir / "correction_summary.json")
    assert float(summary["warn_threshold_pct"]) == 10.0
    assert summary["over_warn_threshold"] is True
    assert float(summary["overall_max_pct"]) > 10.0


def test_cli_front_and_rear_correction_differ(tmp_path: Path) -> None:
    rows: list[dict[str, float]] = []
    timestamp = 0
    # Target at MAP=60 is 13.5. Make front lean and rear rich in the same cell.
    for _ in range(10):
        rows.append(
            {
                "timestamp_ms": timestamp,
                "Engine RPM": 3000.0,
                "MAP kPa": 60.0,
                "AFR Meas F": 15.2,
                "AFR Meas R": 12.6,
            }
        )
        timestamp += 10
    # Add another populated cell so both runs have multiple valid bins.
    for _ in range(10):
        rows.append(
            {
                "timestamp_ms": timestamp,
                "Engine RPM": 4000.0,
                "MAP kPa": 80.0,
                "AFR Meas F": 12.9,
                "AFR Meas R": 12.9,
            }
        )
        timestamp += 10

    frame = pd.DataFrame(rows)
    log_csv = tmp_path / "diff.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=out_dir)

    assert result.returncode == 0, result.stderr
    front_grid = _load_grid(out_dir / "VE_Front_Correction_2D.csv")
    rear_grid = _load_grid(out_dir / "VE_Rear_Correction_2D.csv")

    front_cell = float(front_grid.loc[3000, 60])
    rear_cell = float(rear_grid.loc[3000, 60])
    assert front_cell > 1.0
    assert rear_cell < 1.0
    assert abs(front_cell - rear_cell) > 0.001


def test_cli_accepts_lc2_voltage_columns(tmp_path: Path) -> None:
    """Voltage-labeled LC-2 columns should be converted server-side via wideband_rescale."""
    # LC-2 default: 0V->7.35 AFR, 5V->22.39 AFR (slope 3.008, intercept 7.35).
    # Voltages chosen to stay inside AutoTuneWorkflow's valid AFR range [9, 20].
    #   v=3.5V -> ~17.88 AFR (lean vs target ~13.5 @ MAP 60)
    #   v=2.0V -> ~13.37 AFR (near target)
    rows: list[dict[str, float]] = []
    timestamp = 0
    for rpm, map_kpa, v_front, v_rear in [
        (3000, 60, 3.5, 2.0),
        (4000, 80, 3.4, 2.05),
    ]:
        for _ in range(8):
            rows.append(
                {
                    "timestamp_ms": timestamp,
                    "Engine RPM": float(rpm),
                    "MAP kPa": float(map_kpa),
                    "LC2 Volts Petrol AFR1": float(v_front),
                    "LC2 Volts Petrol AFR2": float(v_rear),
                }
            )
            timestamp += 10
    frame = pd.DataFrame(rows)
    log_csv = tmp_path / "voltage.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=out_dir)

    assert result.returncode == 0, result.stderr
    front_grid = _load_grid(out_dir / "VE_Front_Correction_2D.csv")
    rear_grid = _load_grid(out_dir / "VE_Rear_Correction_2D.csv")
    # 4.5 V -> ~20.9 AFR (lean) -> request more fuel -> front correction > 1 somewhere.
    # 2.0 V -> ~13.4 AFR (near target at MAP=60 -> 13.5), so rear should hover near 1.
    assert front_grid.values.max() > 1.0
    assert abs(front_grid.loc[3000, 60] - rear_grid.loc[3000, 60]) > 0.01


def test_cli_single_cylinder_rear_only_emits_rear_outputs(tmp_path: Path) -> None:
    """--single-cylinder rear with only rear AFR present must succeed and write only rear CSV."""
    frame = _build_dual_afr_frame(front_afr=14.0, rear_afr=13.2).drop(columns=["AFR Meas F"])
    log_csv = tmp_path / "rear_only.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(
        log_csv=log_csv,
        output_dir=out_dir,
        extra_args=["--single-cylinder", "rear"],
    )

    assert result.returncode == 0, result.stderr
    assert (out_dir / "VE_Rear_Correction_2D.csv").exists()
    assert not (out_dir / "VE_Front_Correction_2D.csv").exists()

    summary = _load_summary(out_dir / "correction_summary.json")
    assert summary["mode"] == "single_cylinder_rear"
    assert summary["front"] is None
    assert isinstance(summary["rear"], dict)


def test_cli_single_cylinder_front_only_emits_front_outputs(tmp_path: Path) -> None:
    """--single-cylinder front with only front AFR present must succeed and write only front CSV."""
    frame = _build_dual_afr_frame(front_afr=14.5, rear_afr=13.2).drop(columns=["AFR Meas R"])
    log_csv = tmp_path / "front_only.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(
        log_csv=log_csv,
        output_dir=out_dir,
        extra_args=["--single-cylinder", "front"],
    )

    assert result.returncode == 0, result.stderr
    assert (out_dir / "VE_Front_Correction_2D.csv").exists()
    assert not (out_dir / "VE_Rear_Correction_2D.csv").exists()

    summary = _load_summary(out_dir / "correction_summary.json")
    assert summary["mode"] == "single_cylinder_front"
    assert summary["rear"] is None
    assert isinstance(summary["front"], dict)


def test_cli_single_cylinder_flag_overrides_missing_column_error(tmp_path: Path) -> None:
    """Without the flag, missing AFR Meas F errors. With --single-cylinder rear, CLI succeeds."""
    frame = _build_dual_afr_frame(front_afr=14.0, rear_afr=13.2).drop(columns=["AFR Meas F"])
    log_csv = tmp_path / "needs_override.csv"
    frame.to_csv(log_csv, index=False)

    # Baseline: no flag -> error.
    strict_result = _run_cli(log_csv=log_csv, output_dir=tmp_path / "strict")
    assert strict_result.returncode != 0
    assert "missing_column: AFR Meas F" in strict_result.stderr

    # With flag -> success.
    override_result = _run_cli(
        log_csv=log_csv,
        output_dir=tmp_path / "single",
        extra_args=["--single-cylinder", "rear"],
    )
    assert override_result.returncode == 0, override_result.stderr


def test_cli_accepts_lambda_columns(tmp_path: Path) -> None:
    """Lambda-labeled columns should be converted to AFR via the canonical helper.

    Math check at MAP=60 kPa (target AFR = 13.5):
      lambda 0.95 -> 13.965 AFR (slightly lean) -> correction > 1.0
      lambda 0.88 -> 12.936 AFR (slightly rich) -> correction < 1.0
    """
    rows: list[dict[str, float]] = []
    timestamp = 0
    for rpm, map_kpa, lam_front, lam_rear in [
        (3000, 60, 0.95, 0.88),
        (4000, 80, 0.93, 0.90),
    ]:
        for _ in range(8):
            rows.append(
                {
                    "timestamp_ms": timestamp,
                    "Engine RPM": float(rpm),
                    "MAP kPa": float(map_kpa),
                    "WBO2 LAMBDA Front": float(lam_front),
                    "WBO2 LAMBDA Rear": float(lam_rear),
                }
            )
            timestamp += 10
    frame = pd.DataFrame(rows)
    log_csv = tmp_path / "lambda.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=out_dir)

    assert result.returncode == 0, result.stderr
    front_grid = _load_grid(out_dir / "VE_Front_Correction_2D.csv")
    rear_grid = _load_grid(out_dir / "VE_Rear_Correction_2D.csv")
    # Front (0.95 lambda) -> lean -> correction > 1.0 at (3000, 60).
    # Rear  (0.88 lambda) -> rich -> correction < 1.0 at (3000, 60).
    assert front_grid.loc[3000, 60] > 1.0
    assert rear_grid.loc[3000, 60] < 1.0


def test_cli_rescales_lambda_values_in_afr_columns(tmp_path: Path) -> None:
    """Rescue path: an 'AFR Meas' column whose values are in Lambda range
    (0.5-1.5) should be auto-rescaled to AFR via lambda_to_afr, so the
    workflow doesn't reject 0.90 with the old 'outside valid range' error.
    """
    rows: list[dict[str, float]] = []
    timestamp = 0
    for rpm, map_kpa, afr_front_lambda, afr_rear_lambda in [
        (3000, 60, 0.95, 0.88),
        (4000, 80, 0.93, 0.90),
    ]:
        for _ in range(8):
            rows.append(
                {
                    "timestamp_ms": timestamp,
                    "Engine RPM": float(rpm),
                    "MAP kPa": float(map_kpa),
                    # AFR-named columns but values are Lambda-range.
                    "AFR Meas F": float(afr_front_lambda),
                    "AFR Meas R": float(afr_rear_lambda),
                }
            )
            timestamp += 10
    frame = pd.DataFrame(rows)
    log_csv = tmp_path / "afr_but_lambda.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=out_dir)

    assert result.returncode == 0, result.stderr
    front_grid = _load_grid(out_dir / "VE_Front_Correction_2D.csv")
    rear_grid = _load_grid(out_dir / "VE_Rear_Correction_2D.csv")
    assert front_grid.shape == (11, 9)
    assert rear_grid.shape == (11, 9)


def test_cli_stdout_summary_line_format(tmp_path: Path) -> None:
    frame = _build_dual_afr_frame(front_afr=14.2, rear_afr=13.0)
    log_csv = tmp_path / "stdout.csv"
    out_dir = tmp_path / "out"
    frame.to_csv(log_csv, index=False)

    result = _run_cli(log_csv=log_csv, output_dir=out_dir)

    assert result.returncode == 0, result.stderr
    assert re.search(
        r"^\[F1\]\[OK\] summary=.+correction_summary\.json$",
        result.stdout.strip(),
        flags=re.MULTILINE,
    )
