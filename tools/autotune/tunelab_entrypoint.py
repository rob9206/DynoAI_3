from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from api.services.autotune.safety_gates import SAFETY, check_block_conditions
from api.services.autotune_workflow import (
    AutoTuneWorkflow,
    DataSource,
    VECorrectionResult,
)
from api.services.jetdrive.jetdrive_mapping import lambda_to_afr
from api.services.jetdrive.wideband_rescale import (
    canonicalize_wideband_sample,
    match_wideband_channel,
)
from api.services.powercore_integration import TuneFile, TuneTable, generate_pvv_xml
from api.services.session_logger import SessionLogger
from dynoai.core.ve_operations import VEApply

LAMBDA_MIN_PLAUSIBLE = 0.5
LAMBDA_MAX_PLAUSIBLE = 1.5
APPLY_MAX_ADJUST_PCT = 15.0

DEFAULT_AFR_TARGET_SOURCE = "static_map_curve_v1"
AFR_TARGET_SOURCE_CHOICES = (DEFAULT_AFR_TARGET_SOURCE, "from_tune.AFR_Target")
BASE_REQUIRED_COLUMNS = ("Engine RPM", "MAP kPa")
CYLINDER_SPECS: dict[str, str] = {
    "front": "AFR Meas F",
    "rear": "AFR Meas R",
}
SINGLE_CYLINDER_CHOICES = ("front", "rear")
MODE_DUAL = "dual_cylinder"
MODE_SINGLE_FRONT = "single_cylinder_front"
MODE_SINGLE_REAR = "single_cylinder_rear"
MODE_CHOICES = (MODE_DUAL, MODE_SINGLE_FRONT, MODE_SINGLE_REAR)
REPO_ROOT = Path(__file__).resolve().parents[2]

# Accept common aliases that can appear in Power Core exports.
COLUMN_ALIASES = {
    "RPM": "Engine RPM",
    "MAP": "MAP kPa",
    "MAP_kPa": "MAP kPa",
    "AFR Front": "AFR Meas F",
    "AFR Rear": "AFR Meas R",
    "WBO2 F": "AFR Meas F",
    "WBO2 R": "AFR Meas R",
    "Air/Fuel Ratio 1": "AFR Meas F",
    "Air/Fuel Ratio 2": "AFR Meas R",
}


def _add_preview_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--log-csv",
        type=Path,
        required=True,
        help="Input log CSV with Engine RPM, MAP kPa, AFR Meas F, AFR Meas R.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where correction CSVs and correction_summary.json are written.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional run identifier to include in correction_summary.json metadata.",
    )
    parser.add_argument(
        "--engine-family",
        default=None,
        help="Optional engine family metadata value for correction_summary.json.",
    )
    parser.add_argument(
        "--displacement-ci",
        type=float,
        default=None,
        help="Optional displacement metadata value for correction_summary.json.",
    )
    parser.add_argument(
        "--afr-target-source",
        choices=AFR_TARGET_SOURCE_CHOICES,
        default=DEFAULT_AFR_TARGET_SOURCE,
        help=(
            '"static_map_curve_v1" (default MAP-indexed target curve) or '
            '"from_tune.AFR_Target" (reserved for F1.1).'
        ),
    )
    parser.add_argument(
        "--single-cylinder",
        choices=SINGLE_CYLINDER_CHOICES,
        default=None,
        help=(
            "Run autotune for a single cylinder only (front or rear). "
            "The other cylinder is reported as null in the summary and no "
            "CSV is emitted for it. F1 default is dual-cylinder."
        ),
    )
    parser.add_argument(
        "--emit-pvv-patch",
        action="store_true",
        help="Emit dynoai_ve_correction_<run>.pvv alongside correction CSVs.",
    )


def _add_apply_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--run-id",
        required=True,
        help="Run identifier used for session logging under runs/<run_id>/.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory containing correction_summary.json and correction CSVs.",
    )
    parser.add_argument(
        "--base-front",
        type=Path,
        required=True,
        help="Front base VE CSV read from the currently loaded tune table.",
    )
    parser.add_argument(
        "--base-rear",
        type=Path,
        required=True,
        help="Rear base VE CSV read from the currently loaded tune table.",
    )
    parser.add_argument(
        "--mode",
        choices=MODE_CHOICES,
        default=MODE_DUAL,
        help="Expected mode from correction_summary.json (apply supports dual only).",
    )
    parser.add_argument(
        "--max-adjust-pct",
        type=float,
        default=APPLY_MAX_ADJUST_PCT,
        help="VEApply clamp percent for the apply pass.",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="TuneLab F1 CLI (preview + apply).",
    )
    subparsers = parser.add_subparsers(dest="command")

    preview_parser = subparsers.add_parser(
        "preview",
        help="Generate per-cylinder correction previews.",
    )
    _add_preview_args(preview_parser)

    apply_parser = subparsers.add_parser(
        "apply",
        help="Apply preview corrections using VEApply + SessionLogger.",
    )
    _add_apply_args(apply_parser)
    return parser


def _normalize_argv(argv: Sequence[str] | None) -> list[str]:
    args = list(argv) if argv is not None else sys.argv[1:]
    if args and args[0] in {"preview", "apply", "-h", "--help"}:
        return args
    if not args:
        return ["preview"]
    return ["preview", *args]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {k: v for k, v in COLUMN_ALIASES.items() if k in df.columns}
    if not rename_map:
        return df
    return df.rename(columns=rename_map)


def _convert_voltage_columns_to_afr(df: pd.DataFrame) -> pd.DataFrame:
    """Convert any LC-1/LC-2 voltage columns to canonical AFR columns.

    Delegates all math to ``api.services.jetdrive.wideband_rescale`` so the
    repo rule "single point of conversion" stays intact.
    """
    for column in list(df.columns):
        canonical = match_wideband_channel(column)
        if canonical is None:
            continue

        target_column = {
            "AFR Front": "AFR Meas F",
            "AFR Rear": "AFR Meas R",
            "AFR": "AFR Meas",
        }.get(canonical)
        if target_column is None or target_column in df.columns:
            continue

        numeric_volts = pd.to_numeric(df[column], errors="coerce")
        converted: list[float | None] = []
        for raw in numeric_volts:
            if pd.isna(raw):
                converted.append(None)
                continue
            sample = canonicalize_wideband_sample(column, float(raw))
            converted.append(sample.afr if sample is not None else None)
        df[target_column] = converted

    return df


def _match_lambda_column(column_name: str) -> str | None:
    """Return the canonical AFR column name if this column looks like Lambda.

    Conservative: requires "lambda" in the column name. Distinguishes front
    vs rear by suffix tokens ("1", "front", "f") / ("2", "rear", "r").
    """
    lowered = column_name.lower()
    if "lambda" not in lowered:
        return None
    if "1" in lowered or "front" in lowered or lowered.endswith(" f"):
        return "AFR Meas F"
    if "2" in lowered or "rear" in lowered or lowered.endswith(" r"):
        return "AFR Meas R"
    return "AFR Meas"


def _convert_lambda_columns_to_afr(df: pd.DataFrame) -> pd.DataFrame:
    """Convert any Lambda columns to canonical AFR columns.

    Uses ``api.services.jetdrive.jetdrive_mapping.lambda_to_afr`` (stoich
    gasoline: AFR = lambda * 14.7) so conversion math stays centralized.
    Only rescales values that fall in a plausible Lambda range; stray
    non-Lambda noise gets dropped to NaN to avoid silent AFR inflation.
    """
    for column in list(df.columns):
        canonical_afr = _match_lambda_column(column)
        if canonical_afr is None:
            continue
        if canonical_afr in df.columns:
            continue

        numeric = pd.to_numeric(df[column], errors="coerce")
        converted: list[float | None] = []
        for raw in numeric:
            if pd.isna(raw):
                converted.append(None)
                continue
            value = float(raw)
            if not (LAMBDA_MIN_PLAUSIBLE <= value <= LAMBDA_MAX_PLAUSIBLE):
                converted.append(None)
                continue
            converted.append(lambda_to_afr(value))
        df[canonical_afr] = converted

    return df


def _rescale_lambda_values_in_afr_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rescue: if a column named "AFR ..." actually holds Lambda values.

    Some Power Core / DynoWare rigs mis-configure channel scaling so that
    an ``AFR`` channel carries Lambda (0.5-1.5) values instead. The main
    symptom is AutoTuneWorkflow rejecting values like 0.58 or 0.90 as
    "outside valid AFR range". When the median of an AFR column sits in
    the Lambda window, multiply by the stoich constant (delegated to
    ``jetdrive_mapping.lambda_to_afr``) so downstream math gets AFR.
    """
    for column in list(df.columns):
        lower = column.lower()
        if "afr" not in lower:
            continue

        numeric = pd.to_numeric(df[column], errors="coerce")
        valid = numeric.dropna()
        if valid.empty:
            continue

        median_value = float(valid.median())
        if not (LAMBDA_MIN_PLAUSIBLE <= median_value <= LAMBDA_MAX_PLAUSIBLE):
            continue

        df[column] = [
            (
                None
                if pd.isna(v)
                else (
                    lambda_to_afr(float(v))
                    if LAMBDA_MIN_PLAUSIBLE <= float(v) <= LAMBDA_MAX_PLAUSIBLE
                    else None
                )
            )
            for v in numeric
        ]

    return df


def _load_log_dataframe(log_csv: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(log_csv)
    except Exception as exc:
        raise RuntimeError(f"unable_to_read_csv: {exc}") from exc
    df = _normalize_columns(df)
    df = _convert_voltage_columns_to_afr(df)
    df = _convert_lambda_columns_to_afr(df)
    df = _rescale_lambda_values_in_afr_columns(df)
    return df


def _validate_required_columns(df: pd.DataFrame, active_sides: Sequence[str]) -> None:
    required = list(BASE_REQUIRED_COLUMNS)
    for side in active_sides:
        required.append(CYLINDER_SPECS[side])
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise RuntimeError(f"missing_column: {missing[0]}")


def _default_run_id(log_csv: Path) -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"auto/{date_part}/{log_csv.stem}"


def _format_axis_value(value: float) -> str:
    as_float = float(value)
    if as_float.is_integer():
        return str(int(as_float))
    return f"{as_float:.3f}".rstrip("0").rstrip(".")


def _write_correction_csv(corrections: VECorrectionResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        map_axis = [_format_axis_value(v) for v in corrections.map_axis]
        handle.write("RPM\\MAP," + ",".join(map_axis) + "\n")
        for row_idx, rpm in enumerate(corrections.rpm_axis):
            values = [
                f"{float(corrections.correction_table[row_idx, col_idx]):.4f}"
                for col_idx in range(len(corrections.map_axis))
            ]
            handle.write(_format_axis_value(rpm) + "," + ",".join(values) + "\n")


def _build_cylinder_dataframe(df: pd.DataFrame, *, afr_column: str) -> pd.DataFrame:
    non_afr_columns = [c for c in df.columns if "AFR" not in c]
    out_df = df[non_afr_columns].copy()
    out_df["AFR Meas"] = pd.to_numeric(df[afr_column], errors="coerce")
    out_df["Engine RPM"] = pd.to_numeric(out_df["Engine RPM"], errors="coerce")
    out_df["MAP kPa"] = pd.to_numeric(out_df["MAP kPa"], errors="coerce")
    out_df = out_df.dropna(subset=["Engine RPM", "MAP kPa", "AFR Meas"])
    if out_df.empty:
        raise RuntimeError(f"no_valid_samples: {afr_column}")
    return out_df


def _run_for_cylinder(
    source_df: pd.DataFrame,
    *,
    run_id: str,
    cylinder_name: str,
    afr_column: str,
    output_dir: Path,
) -> dict[str, Any]:
    workflow = AutoTuneWorkflow()
    session = workflow.create_session(
        run_id=f"{run_id}_{cylinder_name}",
        data_source=DataSource.CSV,
    )

    cylinder_df = _build_cylinder_dataframe(source_df, afr_column=afr_column)
    if not workflow.import_dataframe(session, cylinder_df, source=DataSource.CSV):
        detail = session.errors[-1] if session.errors else "unknown_import_failure"
        raise RuntimeError(f"import_failed_{cylinder_name}: {detail}")

    if workflow.analyze_afr(session) is None:
        detail = session.errors[-1] if session.errors else "unknown_analyze_failure"
        raise RuntimeError(f"analyze_failed_{cylinder_name}: {detail}")

    corrections = workflow.calculate_corrections(session)
    if corrections is None:
        detail = session.errors[-1] if session.errors else "unknown_correction_failure"
        raise RuntimeError(f"correction_failed_{cylinder_name}: {detail}")

    csv_name = f"VE_{cylinder_name.capitalize()}_Correction_2D.csv"
    csv_path = output_dir / csv_name
    _write_correction_csv(corrections, csv_path)

    session_summary = workflow.get_session_summary(session)
    analysis = session_summary.get("analysis", {})
    corr_summary = session_summary.get("ve_corrections", {})
    hit_counts = (
        session.afr_analysis.hit_count_by_zone.values.tolist()
        if session.afr_analysis is not None
        else []
    )
    requested_max_pct = max(
        abs(float(analysis.get("max_lean_pct", 0.0))),
        abs(float(analysis.get("max_rich_pct", 0.0))),
    )

    return {
        "csv": csv_name,
        "csv_path": str(csv_path.resolve()),
        "zones_adjusted": int(corr_summary.get("zones_adjusted", 0)),
        "max_pct": float(corr_summary.get("max_correction_pct", 0.0)),
        "min_pct": float(corr_summary.get("min_correction_pct", 0.0)),
        "clipped_zones": int(corr_summary.get("clipped_zones", 0)),
        "mean_afr_error": float(analysis.get("mean_afr_error", 0.0)),
        "mean_ve_delta_pct": float(analysis.get("mean_ve_delta_pct", 0.0)),
        "requested_max_pct": float(requested_max_pct),
        "rpm_axis": list(corrections.rpm_axis),
        "map_axis": list(corrections.map_axis),
        "correction_grid": corrections.correction_table.tolist(),
        "hit_count_grid": hit_counts,
    }


def _cylinder_section(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "csv": result["csv"],
        "zones_adjusted": result["zones_adjusted"],
        "max_pct": result["max_pct"],
        "min_pct": result["min_pct"],
        "clipped_zones": result["clipped_zones"],
        "mean_afr_error": result["mean_afr_error"],
        "mean_ve_delta_pct": result["mean_ve_delta_pct"],
    }


def _neutral_grid(rows: int, cols: int, value: float) -> list[list[float]]:
    return [[float(value) for _ in range(cols)] for _ in range(rows)]


def _build_dual_grids_for_safety(
    results: dict[str, dict[str, Any]],
    active_sides: Sequence[str],
) -> tuple[
    dict[str, list[list[float]]], dict[str, list[list[float]]], list[float], list[float]
]:
    reference_side = active_sides[0]
    rpm_axis = [float(v) for v in results[reference_side]["rpm_axis"]]
    map_axis = [float(v) for v in results[reference_side]["map_axis"]]
    rows = len(rpm_axis)
    cols = len(map_axis)

    corrections = {
        "front": (
            results["front"]["correction_grid"]
            if "front" in results
            else _neutral_grid(rows, cols, 1.0)
        ),
        "rear": (
            results["rear"]["correction_grid"]
            if "rear" in results
            else _neutral_grid(rows, cols, 1.0)
        ),
    }
    hit_counts = {
        "front": (
            results["front"]["hit_count_grid"]
            if "front" in results and results["front"]["hit_count_grid"]
            else _neutral_grid(rows, cols, 0.0)
        ),
        "rear": (
            results["rear"]["hit_count_grid"]
            if "rear" in results and results["rear"]["hit_count_grid"]
            else _neutral_grid(rows, cols, 0.0)
        ),
    }
    return corrections, hit_counts, rpm_axis, map_axis


def _safe_run_slug(run_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", run_id.strip())
    return slug.strip("_") or "run"


def _emit_pvv_patch(
    *,
    run_id: str,
    output_dir: Path,
    results: dict[str, dict[str, Any]],
    active_sides: Sequence[str],
) -> Path:
    tune = TuneFile()
    for side in active_sides:
        side_result = results[side]
        tune.tables[f"VE Correction {side.capitalize()}"] = TuneTable(
            name=f"VE Correction {side.capitalize()}",
            units="%",
            row_axis=[float(rpm) for rpm in side_result["rpm_axis"]],
            row_units="RPM",
            col_axis=[float(map_kpa) for map_kpa in side_result["map_axis"]],
            col_units="MAP (KPa)",
            values=np.array(side_result["correction_grid"], dtype=float) * 100.0,
        )
    slug = _safe_run_slug(run_id)
    pvv_path = output_dir / f"dynoai_ve_correction_{slug}.pvv"
    pvv_path.write_text(generate_pvv_xml(tune), encoding="utf-8")
    return pvv_path


def _build_safety_block(
    *,
    results: dict[str, dict[str, Any]],
    active_sides: Sequence[str],
    overall_max_pct: float,
) -> dict[str, Any]:
    corrections, hit_counts, rpm_axis, map_axis = _build_dual_grids_for_safety(
        results,
        active_sides,
    )
    rows = len(rpm_axis)
    cols = len(map_axis)
    base_ve = {
        "front": _neutral_grid(rows, cols, 100.0),
        "rear": _neutral_grid(rows, cols, 100.0),
    }
    block_reasons = check_block_conditions(
        base_ve=base_ve,  # type: ignore[arg-type]
        corrections=corrections,  # type: ignore[arg-type]
        hit_counts=hit_counts,  # type: ignore[arg-type]
        rpm_axis=rpm_axis,
        map_axis=map_axis,
    )
    block_threshold = float(SAFETY["block_raw_delta_pct"])
    warn_threshold = float(SAFETY["warn_raw_delta_pct"])
    over_block_threshold = bool(overall_max_pct > block_threshold)
    has_extreme_reason = any(
        reason.get("type") == "extreme_correction" for reason in block_reasons
    )
    if over_block_threshold and not has_extreme_reason:
        block_reasons.append(
            {
                "type": "extreme_correction",
                "message": (
                    "Requested correction exceeds ±%.0f%% before clamp "
                    "(overall_max_pct=%.2f%%)." % (block_threshold, overall_max_pct)
                ),
            }
        )
    return {
        "block_threshold_pct": block_threshold,
        "warn_threshold_pct": warn_threshold,
        "over_block_threshold": over_block_threshold,
        "apply_blocked": bool(block_reasons),
        "apply_blocked_reasons": block_reasons,
    }


def _load_multiplier_csv(
    multiplier_csv: Path,
) -> tuple[list[str], list[int], list[list[float]]]:
    try:
        frame = pd.read_csv(multiplier_csv)
    except Exception as exc:
        raise RuntimeError(
            f"unable_to_read_multiplier_csv: {multiplier_csv} ({exc})"
        ) from exc

    if frame.empty or len(frame.columns) < 2:
        raise RuntimeError(f"invalid_multiplier_csv: {multiplier_csv}")

    first_col = frame.columns[0]
    frame = frame.rename(columns={first_col: "RPM"})
    rpm_values = pd.to_numeric(frame["RPM"], errors="coerce")
    if rpm_values.isna().any():
        raise RuntimeError(f"invalid_rpm_column: {multiplier_csv}")
    rpm_axis = [int(float(v)) for v in rpm_values.tolist()]

    map_columns = [str(col) for col in frame.columns[1:]]
    numeric_values = frame.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
    if numeric_values.isna().any().any():
        raise RuntimeError(f"invalid_multiplier_values: {multiplier_csv}")

    return map_columns, rpm_axis, numeric_values.to_numpy(dtype=float).tolist()


def _write_percent_factor_csv(
    *,
    multiplier_csv: Path,
    factor_csv: Path,
) -> None:
    map_axis, rpm_axis, multiplier_grid = _load_multiplier_csv(multiplier_csv)
    factor_csv.parent.mkdir(parents=True, exist_ok=True)
    with factor_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["RPM", *map_axis])
        for rpm, multiplier_row in zip(rpm_axis, multiplier_grid):
            percent_row = [
                f"{(float(multiplier) - 1.0) * 100.0:.6f}"
                for multiplier in multiplier_row
            ]
            writer.writerow([rpm, *percent_row])


def _resolve_run_dir(run_id: str) -> Path:
    """Resolve runs/<sanitized_run_id> within REPO_ROOT.

    Sanitizes each path segment via ``_safe_run_slug`` so values containing
    ``..``, drive letters, or stray separators cannot escape the runs root.
    The final resolved path is also re-checked against ``runs_root.resolve()``
    as a defense-in-depth guard.
    """
    runs_root = (REPO_ROOT / "runs").resolve()
    raw_parts = [
        part for part in run_id.replace("\\", "/").split("/") if part.strip()
    ]
    safe_parts = [_safe_run_slug(part) for part in raw_parts]
    safe_parts = [part for part in safe_parts if part and part not in (".", "..")]
    if not safe_parts:
        raise RuntimeError(f"invalid_run_id_after_sanitization: {run_id!r}")

    run_dir = runs_root
    for part in safe_parts:
        run_dir = run_dir / part
    resolved = run_dir.resolve()
    try:
        resolved.relative_to(runs_root)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(
            f"run_id_escapes_runs_root: {run_id!r} -> {resolved}"
        ) from exc
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _load_summary(summary_path: Path) -> dict[str, Any]:
    try:
        return json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"unable_to_read_summary: {exc}") from exc


def _get_required_section(summary: dict[str, Any], side: str) -> dict[str, Any]:
    section = summary.get(side)
    if not isinstance(section, dict):
        raise RuntimeError(f"missing_summary_section: {side}")
    if "csv" not in section:
        raise RuntimeError(f"missing_summary_csv_field: {side}")
    return section


def _flatten_reason_messages(reasons: list[dict[str, Any]]) -> str:
    messages = [str(reason.get("message", "")).strip() for reason in reasons]
    non_empty = [message for message in messages if message]
    return "; ".join(non_empty) if non_empty else "Safety gates blocked apply."


def run_preview_cli(
    *,
    log_csv: Path,
    output_dir: Path,
    run_id: str | None,
    engine_family: str | None,
    displacement_ci: float | None,
    afr_target_source: str,
    single_cylinder: str | None = None,
    emit_pvv_patch: bool = False,
) -> Path:
    if afr_target_source == "from_tune.AFR_Target":
        raise RuntimeError("unsupported_afr_target_source: from_tune.AFR_Target (F1.1)")

    if single_cylinder is not None and single_cylinder not in SINGLE_CYLINDER_CHOICES:
        raise RuntimeError(f"invalid_single_cylinder: {single_cylinder}")

    if single_cylinder == "front":
        active_sides = ["front"]
        mode = MODE_SINGLE_FRONT
    elif single_cylinder == "rear":
        active_sides = ["rear"]
        mode = MODE_SINGLE_REAR
    else:
        active_sides = ["front", "rear"]
        mode = MODE_DUAL

    output_dir.mkdir(parents=True, exist_ok=True)
    source_df = _load_log_dataframe(log_csv)
    _validate_required_columns(source_df, active_sides)

    resolved_run_id = run_id or _default_run_id(log_csv)
    results: dict[str, dict[str, Any]] = {}
    for side in active_sides:
        results[side] = _run_for_cylinder(
            source_df,
            run_id=resolved_run_id,
            cylinder_name=side,
            afr_column=CYLINDER_SPECS[side],
            output_dir=output_dir,
        )

    overall_max_pct = max(
        float(results[side]["requested_max_pct"]) for side in active_sides
    )
    safety = _build_safety_block(
        results=results,
        active_sides=active_sides,
        overall_max_pct=overall_max_pct,
    )
    warn_threshold = float(safety["warn_threshold_pct"])

    reference_side = active_sides[0]
    summary: dict[str, Any] = {
        "schema_version": 1,
        "log_csv": str(log_csv.resolve()),
        "run_id": resolved_run_id,
        "mode": mode,
        "afr_target_source": afr_target_source,
        "grid": {
            "rpm_axis": results[reference_side]["rpm_axis"],
            "map_axis": results[reference_side]["map_axis"],
        },
        "front": _cylinder_section(results["front"]) if "front" in results else None,
        "rear": _cylinder_section(results["rear"]) if "rear" in results else None,
        "overall_max_pct": overall_max_pct,
        "warn_threshold_pct": warn_threshold,
        "over_warn_threshold": overall_max_pct > warn_threshold,
        "safety": safety,
    }

    if engine_family is not None:
        summary["engine_family"] = engine_family
    if displacement_ci is not None:
        summary["displacement_ci"] = displacement_ci
    if emit_pvv_patch:
        pvv_path = _emit_pvv_patch(
            run_id=resolved_run_id,
            output_dir=output_dir,
            results=results,
            active_sides=active_sides,
        )
        summary["pvv_patch"] = pvv_path.name

    summary_path = output_dir / "correction_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary_path.resolve()


def run_apply_cli(
    *,
    run_id: str,
    output_dir: Path,
    base_front: Path,
    base_rear: Path,
    mode: str = MODE_DUAL,
    max_adjust_pct: float = APPLY_MAX_ADJUST_PCT,
) -> tuple[Path, Path, Path]:
    summary_path = output_dir / "correction_summary.json"
    if not summary_path.exists():
        raise RuntimeError(f"missing_summary: {summary_path}")

    summary = _load_summary(summary_path)
    summary_mode = str(summary.get("mode", MODE_DUAL))
    if mode != MODE_DUAL or summary_mode != MODE_DUAL:
        raise RuntimeError(
            f"apply_requires_dual_cylinder_mode: requested={mode} summary={summary_mode}"
        )

    safety = summary.get("safety", {})
    if bool(safety.get("apply_blocked")):
        reasons_raw = safety.get("apply_blocked_reasons", [])
        reasons = [reason for reason in reasons_raw if isinstance(reason, dict)]
        raise RuntimeError(f"apply_blocked: {_flatten_reason_messages(reasons)}")

    front_section = _get_required_section(summary, "front")
    rear_section = _get_required_section(summary, "rear")

    front_multiplier_csv = output_dir / str(front_section["csv"])
    rear_multiplier_csv = output_dir / str(rear_section["csv"])
    if not front_multiplier_csv.exists():
        raise RuntimeError(f"missing_front_multiplier_csv: {front_multiplier_csv}")
    if not rear_multiplier_csv.exists():
        raise RuntimeError(f"missing_rear_multiplier_csv: {rear_multiplier_csv}")
    if not base_front.exists():
        raise RuntimeError(f"missing_base_front: {base_front}")
    if not base_rear.exists():
        raise RuntimeError(f"missing_base_rear: {base_rear}")

    front_factor_pct_csv = output_dir / "VE_Front_Correction_Pct.csv"
    rear_factor_pct_csv = output_dir / "VE_Rear_Correction_Pct.csv"
    _write_percent_factor_csv(
        multiplier_csv=front_multiplier_csv,
        factor_csv=front_factor_pct_csv,
    )
    _write_percent_factor_csv(
        multiplier_csv=rear_multiplier_csv,
        factor_csv=rear_factor_pct_csv,
    )

    front_applied_csv = output_dir / "VE_Front_Applied.csv"
    rear_applied_csv = output_dir / "VE_Rear_Applied.csv"
    applier = VEApply(max_adjust_pct=max_adjust_pct)
    front_meta = applier.apply(
        base_ve_path=base_front,
        factor_path=front_factor_pct_csv,
        output_path=front_applied_csv,
        dry_run=False,
    )
    rear_meta = applier.apply(
        base_ve_path=base_rear,
        factor_path=rear_factor_pct_csv,
        output_path=rear_applied_csv,
        dry_run=False,
    )

    resolved_run_id = run_id or str(summary.get("run_id", "")).strip()
    if not resolved_run_id:
        raise RuntimeError("missing_run_id")

    run_dir = _resolve_run_dir(resolved_run_id)
    logger = SessionLogger(run_dir)
    logger.record_apply(
        ve_before_path=base_front,
        ve_after_path=front_applied_csv,
        apply_metadata={**front_meta, "cylinder": "front"},
        description=f"Applied front VE corrections (max ±{max_adjust_pct:.1f}%)",
    )
    logger.record_apply(
        ve_before_path=base_rear,
        ve_after_path=rear_applied_csv,
        apply_metadata={**rear_meta, "cylinder": "rear"},
        description=f"Applied rear VE corrections (max ±{max_adjust_pct:.1f}%)",
    )
    session_log_path = run_dir / "session_log.json"
    return (
        front_applied_csv.resolve(),
        rear_applied_csv.resolve(),
        session_log_path.resolve(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    normalized_argv = _normalize_argv(argv)
    args = parser.parse_args(normalized_argv)

    try:
        if args.command == "preview":
            summary_path = run_preview_cli(
                log_csv=args.log_csv,
                output_dir=args.output_dir,
                run_id=args.run_id,
                engine_family=args.engine_family,
                displacement_ci=args.displacement_ci,
                afr_target_source=args.afr_target_source,
                single_cylinder=args.single_cylinder,
                emit_pvv_patch=args.emit_pvv_patch,
            )
            print(f"[F1][OK] summary={summary_path}")
            return 0
        if args.command == "apply":
            apply_front, apply_rear, session_log = run_apply_cli(
                run_id=args.run_id,
                output_dir=args.output_dir,
                base_front=args.base_front,
                base_rear=args.base_rear,
                mode=args.mode,
                max_adjust_pct=args.max_adjust_pct,
            )
            print(
                f"[F1][OK] apply_front={apply_front} "
                f"apply_rear={apply_rear} session_log={session_log}"
            )
            return 0
        raise RuntimeError(f"unsupported_command: {args.command}")
    except Exception as exc:
        print(f"[F1][ERR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
