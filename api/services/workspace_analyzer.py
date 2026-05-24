"""
Workspace-aware analyzer orchestrator.

Given (vehicle_id, session_id, iteration_id?), this runs the AutoTune
pipeline on the pulls captured for that iteration and writes results
into the iteration's `analyses/` folder. It's a thin shim over the
existing AutoTuneWorkflow -- no analysis logic is duplicated here.

The orchestrator accepts:
    - Dynojet TXT exports (parsed via dynojet_txt_parser)
    - Power Vision CSV logs (parsed via parse_powervision_log)
    - WP8 (passed through parse_wp8_file)
    - Generic CSV (loaded directly by pandas)

and feeds the first usable pull into AutoTuneWorkflow.import_dataframe.
If the session has a base tune uploaded, it is loaded as well.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from api.services.autotune_workflow import AutoTuneWorkflow
from api.services.parsers.dynojet_txt_parser import (
    DynojetTxtReport,
    parse_dynojet_txt_path,
)
from api.services.tuning_workspace import (
    Iteration,
    TuningSession,
    TuningWorkspace,
    get_workspace,
)

logger = logging.getLogger(__name__)

__all__ = [
    "WorkspaceAnalysisResult",
    "analyze_iteration",
]


@dataclass
class WorkspaceAnalysisResult:
    """Summary of a workspace-scoped analysis run."""

    vehicle_id: str
    session_id: str
    iteration_id: str
    success: bool
    pulls_considered: int
    pulls_used: int
    primary_pull: Optional[str]
    data_source: Optional[str]
    afr_mean_error_pct: Optional[float] = None
    zones_adjusted: Optional[int] = None
    peak_hp: Optional[float] = None
    peak_hp_rpm: Optional[float] = None
    # Wheel speed at peak HP, captured separately from `peak_hp_rpm` because
    # Dynojet TXT exports report mph (not RPM) and the two are different
    # physical quantities. Only one will typically be populated for a pull,
    # depending on which source produced the peaks.
    peak_hp_mph: Optional[float] = None
    peak_tq: Optional[float] = None
    peak_tq_rpm: Optional[float] = None
    correction_pvv_path: Optional[str] = None
    correction_pvv_filename: Optional[str] = None
    correction_pvv_sha256: Optional[str] = None
    correction_pvv_n_changed_cells: Optional[int] = None
    correction_manifest_path: Optional[str] = None
    analysis_json_path: Optional[str] = None
    errors: list[str] = None  # type: ignore[assignment]
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        if out["errors"] is None:
            out["errors"] = []
        return out


def analyze_iteration(
    vehicle_id: str,
    session_id: str,
    iteration_id: Optional[str] = None,
    *,
    workspace: Optional[TuningWorkspace] = None,
) -> WorkspaceAnalysisResult:
    """Run the AutoTune pipeline on the specified iteration's pulls.

    If `iteration_id` is None, the session's active iteration is used.
    Returns a `WorkspaceAnalysisResult` with output paths and a summary;
    also writes `analysis.json` into the iteration's analyses/ slot.
    """
    ws = workspace or get_workspace()

    session: TuningSession = ws.get_session(vehicle_id, session_id)
    iteration: Iteration = (ws.get_iteration(vehicle_id, session_id,
                                             iteration_id) if iteration_id else
                            ws.get_active_iteration(vehicle_id, session_id))

    result = WorkspaceAnalysisResult(
        vehicle_id=session.vehicle_id,
        session_id=session.id,
        iteration_id=iteration.id,
        success=False,
        pulls_considered=0,
        pulls_used=0,
        primary_pull=None,
        data_source=None,
        errors=[],
        generated_at=_utc_now(),
    )

    pulls = ws.list_pulls(vehicle_id, session_id, iteration.id)
    result.pulls_considered = len(pulls)
    if not pulls:
        result.errors.append("no pulls on this iteration")
        return result

    chosen, df, source, peak = _select_primary_pull(pulls)
    if chosen is None or df is None or df.empty:
        result.errors.append("no parseable pull found (tried TXT, CSV, WP8)")
        return result

    result.primary_pull = chosen.name
    result.pulls_used = 1
    result.data_source = source
    if peak:
        result.peak_hp = peak.get("peak_hp")
        # `peak_hp_mph` from Dynojet TXT is wheel speed, not engine RPM.
        # Keep them in separate fields; the autotune-session fallback below
        # may still populate `peak_hp_rpm` from real RPM data when present.
        result.peak_hp_rpm = peak.get("peak_hp_rpm")
        result.peak_hp_mph = peak.get("peak_hp_mph")
        result.peak_tq = peak.get("peak_torque")

    base_tune_path = ws.get_base_tune_path(vehicle_id, session_id)
    if base_tune_path is None:
        result.errors.append("no base tune uploaded")
        return result

    try:
        guardrails = _load_tuning_guardrails(ws.vehicle_profile(vehicle_id))
    except ValueError as exc:
        result.errors.append(str(exc))
        return result

    workflow = AutoTuneWorkflow(
        base_pvv_path=base_tune_path,
        target_ve_table_ids=guardrails["ve_table_ids"],
        ve_cap=guardrails["ve_cap_pct"],
        ve_floor=guardrails["ve_floor_pct"],
    )
    autotune_session = workflow.create_session(
        run_id=f"{session.id}_{iteration.id}")

    dataframe_for_autotune = _shape_for_autotune(df)
    imported = workflow.import_dataframe(autotune_session,
                                         dataframe_for_autotune)
    if not imported:
        result.errors.extend(autotune_session.errors
                             or ["import_dataframe failed"])
        return result

    try:
        workflow.import_tune(autotune_session, str(base_tune_path))
    except Exception as exc:
        logger.warning("base tune import failed: %s", exc)
        result.errors.append(f"base tune import failed: {exc}")
        return result

    try:
        workflow.analyze_afr(autotune_session)
        workflow.calculate_corrections(autotune_session)
    except Exception as exc:
        logger.exception("AFR/correction step failed")
        result.errors.append(f"analysis failed: {exc}")
        return result

    if autotune_session.afr_analysis:
        result.afr_mean_error_pct = float(
            autotune_session.afr_analysis.mean_error_pct)
    if autotune_session.ve_corrections:
        result.zones_adjusted = int(
            autotune_session.ve_corrections.zones_adjusted)
    if not result.peak_hp and autotune_session.peak_hp:
        result.peak_hp = float(autotune_session.peak_hp)
        result.peak_hp_rpm = float(autotune_session.peak_hp_rpm)
    if not result.peak_tq and autotune_session.peak_tq:
        result.peak_tq = float(autotune_session.peak_tq)
        result.peak_tq_rpm = float(autotune_session.peak_tq_rpm)

    iter_dir = ws.iteration_dir(vehicle_id, session_id, iteration.id)
    output_dir = iter_dir / "autotune"
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        pvv_path = workflow.export_pvv_corrections(autotune_session,
                                                   str(output_dir))
        if pvv_path:
            patch_src = Path(pvv_path)
            patch_name = f"autotune_correction_{iteration.id}.pvv"
            dest_patch = ws.add_patch(
                vehicle_id,
                session_id,
                iteration.id,
                patch_name,
                patch_src.read_bytes(),
            )
            result.correction_pvv_path = str(dest_patch)
            result.correction_pvv_filename = dest_patch.name

            manifest_path = patch_src.with_suffix(".manifest.json")
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                output_meta = manifest.get("output")
                if isinstance(output_meta, dict):
                    sha256 = output_meta.get("sha256")
                    if isinstance(sha256, str) and sha256:
                        result.correction_pvv_sha256 = sha256

                table_stats = manifest.get("table_stats")
                if isinstance(table_stats, list):
                    changed = 0
                    for table in table_stats:
                        if isinstance(table, dict):
                            cells_changed = table.get("cells_changed", 0)
                            try:
                                changed += int(cells_changed)
                            except (TypeError, ValueError):
                                continue
                    result.correction_pvv_n_changed_cells = changed

                result.correction_manifest_path = str(manifest_path)
    except Exception as exc:
        logger.exception("pvv export failed")
        result.errors.append(f"pvv export failed: {exc}")

    # Finalize derived fields BEFORE persisting so the on-disk JSON matches
    # the API response. Earlier this wrote first then mutated, leaving the
    # persisted file with `success=False` and `analysis_json_path=null` even
    # when the API returned `success=True` with the correct path.
    analysis_filename = f"autotune_{_timestamp()}.json"
    analyses_dir = (ws.iteration_dir(vehicle_id, session_id, iteration.id) /
                    ws.ANALYSES_DIRNAME)
    result.analysis_json_path = str(analyses_dir / analysis_filename)
    result.success = len(
        result.errors) == 0 or result.correction_pvv_path is not None

    persisted_path = ws.add_analysis(
        vehicle_id,
        session_id,
        iteration.id,
        analysis_filename,
        result.to_dict(),
    )
    # `add_analysis` may de-duplicate to a "-1.json" suffix if the file
    # already exists; reflect the actual final path.
    if str(persisted_path) != result.analysis_json_path:
        result.analysis_json_path = str(persisted_path)
        # Re-write so the file's `analysis_json_path` field also matches.
        _atomic_rewrite_analysis_json(persisted_path, result.to_dict())
    return result


def _atomic_rewrite_analysis_json(path: Path, payload: dict[str, Any]) -> None:
    """Re-write an already-persisted analysis JSON in place.

    Used only when `add_analysis` had to disambiguate the filename and we
    need the on-disk content's self-referential `analysis_json_path` to
    match the actual final path.
    """
    import json

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    tmp.replace(path)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _coerce_optional_float(value: Any, field_name: str) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc


def _load_tuning_guardrails(profile_path: Path) -> dict[str, Any]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    guardrails = profile.get("tuning_guardrails")
    if not isinstance(guardrails, dict) or not guardrails:
        raise ValueError("profile.json missing tuning_guardrails block")

    raw_table_ids = guardrails.get("ve_table_ids")
    if not isinstance(raw_table_ids, list):
        raise ValueError("tuning_guardrails.ve_table_ids must be a list")

    table_ids = [str(item).strip() for item in raw_table_ids if str(item).strip()]
    if not table_ids:
        raise ValueError("tuning_guardrails.ve_table_ids must contain at least one table id")

    return {
        "ve_table_ids": table_ids,
        "ve_cap_pct": _coerce_optional_float(
            guardrails.get("ve_cap_pct"),
            "tuning_guardrails.ve_cap_pct",
        ),
        "ve_floor_pct": _coerce_optional_float(
            guardrails.get("ve_floor_pct"),
            "tuning_guardrails.ve_floor_pct",
        ),
    }


def _select_primary_pull(
    pulls: list[Path],
) -> tuple[Optional[Path], Optional[pd.DataFrame], Optional[str],
           Optional[dict]]:
    """Pick the richest pull file and return its DataFrame + metadata."""
    preference = {".txt": 0, ".csv": 1, ".wp8": 2}
    ordered = sorted(pulls, key=lambda p: preference.get(p.suffix.lower(), 99))
    for path in ordered:
        ext = path.suffix.lower()
        try:
            if ext == ".txt":
                df, report = parse_dynojet_txt_path(path)
                if not df.empty:
                    return path, df, "dynojet_txt", _peak_from_report(report)
            elif ext == ".csv":
                df = pd.read_csv(path)
                if not df.empty:
                    return path, df, "csv", None
            elif ext == ".wp8":
                try:
                    from api.services.parsers.wp8_parser import parse_wp8_file

                    run = parse_wp8_file(str(path))
                    if run.data is not None and not run.data.empty:
                        return path, run.data, "wp8", None
                except Exception as exc:
                    logger.info("wp8 parse failed for %s: %s", path.name, exc)
                    continue
        except Exception as exc:
            logger.info("pull parse failed for %s: %s", path.name, exc)
            continue
    return None, None, None, None


def _peak_from_report(report: DynojetTxtReport) -> dict[str, Any]:
    return {
        "peak_hp": report.peak_hp,
        "peak_hp_mph": report.peak_hp_mph,
        "peak_torque": report.peak_torque,
    }


def _shape_for_autotune(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names so AutoTuneWorkflow.import_dataframe can consume us.

    AFR handling:
        - Prefer an already-named ``AFR Meas`` / ``afr meas`` / ``afr`` / ``lc1_afr``
          column as-is.
        - Otherwise look for the canonicalized JetDrive slots produced by
          :mod:`api.services.jetdrive.wideband_rescale` (``AFR Front`` /
          ``AFR Rear``). If both front and rear are present, average them into
          a single ``AFR Meas`` column; if only one is present, use it directly.
        - As a last resort fall back to the legacy DynoWare voltage channel names
          (``LC2 Volts Petrol AFR1`` / ``LC2 Volts Petrol AFR2``). This branch
          should not normally run with live captures anymore — the rescale now
          happens in ``_live_capture_loop`` — but offline CSV imports that
          predate the fix may still carry those column names. Values on that
          legacy path are **volts**, not AFR, and we intentionally do not
          rescale here: the rescale belongs at ingest. If this branch fires,
          an error is surfaced to the caller via the ``errors`` list in
          :class:`WorkspaceAnalysisResult`.
    """
    renamed = df.copy()
    rename: dict[str, str] = {}
    lower = {c.lower(): c for c in renamed.columns}

    def pick(*candidates: str) -> Optional[str]:
        for cand in candidates:
            if cand in lower:
                return lower[cand]
        return None

    rpm_col = pick("engine rpm", "rpm")
    map_col = pick("map kpa", "map_kpa", "map")
    afr_col = pick("afr meas", "afr_meas", "afr", "lc1_afr")
    hp_col = pick("horsepower", "hp")
    tq_col = pick("torque", "torque_ftlb", "tq")

    if rpm_col and rpm_col != "Engine RPM":
        rename[rpm_col] = "Engine RPM"
    if map_col and map_col != "MAP kPa":
        rename[map_col] = "MAP kPa"
    if afr_col and afr_col != "AFR Meas":
        rename[afr_col] = "AFR Meas"
    if hp_col and hp_col != "Horsepower":
        rename[hp_col] = "Horsepower"
    if tq_col and tq_col != "Torque":
        rename[tq_col] = "Torque"
    if rename:
        renamed = renamed.rename(columns=rename)

    if "AFR Meas" not in renamed.columns:
        front_col = _find_column_ci(renamed, "AFR Front")
        rear_col = _find_column_ci(renamed, "AFR Rear")
        if front_col and rear_col:
            front = pd.to_numeric(renamed[front_col], errors="coerce")
            rear = pd.to_numeric(renamed[rear_col], errors="coerce")
            renamed["AFR Meas"] = pd.concat([front, rear],
                                            axis=1).mean(axis=1, skipna=True)
        elif front_col:
            renamed["AFR Meas"] = pd.to_numeric(renamed[front_col],
                                                errors="coerce")
        elif rear_col:
            renamed["AFR Meas"] = pd.to_numeric(renamed[rear_col],
                                                errors="coerce")

    if "Engine RPM" not in renamed.columns and "mph" in renamed.columns:
        renamed["Engine RPM"] = renamed["mph"] * 60.0
    return renamed


def _find_column_ci(df: pd.DataFrame, target: str) -> Optional[str]:
    target_l = target.lower()
    for col in df.columns:
        if col.lower() == target_l:
            return col
    return None


def _utc_now() -> str:
    return (datetime.now(timezone.utc).isoformat(
        timespec="milliseconds").replace("+00:00", "Z"))


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
