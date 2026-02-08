"""
JetDrive Auto-Tune – Analysis & Run Management Routes.

Sub-blueprint for:
- TuneLab configuration
- Dyno configuration
- Status / test-mode
- Power opportunities
- Analyze (subprocess + unified workflow)
- Workflow sessions
- Run details (manifest, PVV, report, export-text)
- CSV upload
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from ._shared import (
    TUNELAB_CONFIG,
    _get_autotune_types,
    _is_simulator_active,
    _set_simulator_active,
    get_project_root,
    get_workflow,
    logger,
    reset_workflow,
    safe_path_in_runs,
    sanitize_run_id,
    validate_csv_path,
)

analysis_bp = Blueprint("jetdrive_analysis", __name__)

# ---------------------------------------------------------------------------
# TuneLab Configuration
# ---------------------------------------------------------------------------


@analysis_bp.route("/tunelab/config", methods=["GET"])
def get_tunelab_config():
    """
    Get current TuneLab-style analysis configuration.

    Returns:
        JSON with current filtering and binning settings
    """
    return jsonify(
        {
            "success": True,
            "config": TUNELAB_CONFIG,
            "description": {
                "enable_filtering": "Enable TuneLab-style AFR signal filtering",
                "lowpass_rc_ms": "RC time constant for lowpass filter (higher = more smoothing)",
                "afr_min": "Minimum valid AFR (below = rejected)",
                "afr_max": "Maximum valid AFR (above = rejected)",
                "exclude_time_ms": "Time to exclude around outliers (±ms)",
                "enable_statistical_filter": "Enable 2σ statistical outlier rejection",
                "sigma_threshold": "Standard deviations for outlier rejection",
                "use_weighted_binning": "Use TuneLab-style distance-weighted cell accumulation",
            },
        }
    )


@analysis_bp.route("/tunelab/config", methods=["POST"])
def set_tunelab_config():
    """
    Update TuneLab-style analysis configuration.

    Request body (JSON):
        Any subset of TUNELAB_CONFIG keys with new values

    Example:
        {"enable_filtering": true, "lowpass_rc_ms": 300.0}
    """
    try:
        data = request.get_json() or {}

        for key in TUNELAB_CONFIG:
            if key in data:
                value = data[key]
                if key in [
                    "enable_filtering",
                    "enable_statistical_filter",
                    "use_weighted_binning",
                ]:
                    TUNELAB_CONFIG[key] = bool(value)
                else:
                    TUNELAB_CONFIG[key] = float(value)

        reset_workflow()

        logger.info(f"TuneLab config updated: {TUNELAB_CONFIG}")

        return jsonify(
            {
                "success": True,
                "message": "Configuration updated. Workflow will use new settings.",
                "config": TUNELAB_CONFIG,
            }
        )
    except Exception as e:
        logger.error(f"Failed to update TuneLab config: {e}")
        return jsonify({"success": False, "error": str(e)}), 400


# ---------------------------------------------------------------------------
# Configuration endpoints
# ---------------------------------------------------------------------------


@analysis_bp.route("/dyno/config", methods=["GET"])
def get_dyno_config():
    """Return Dyno configuration used for calculations and display."""
    try:
        from api.config import get_config

        cfg = get_config().dyno
        return jsonify({"success": True, "config": cfg.to_dict()})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Status Routes
# ---------------------------------------------------------------------------


@analysis_bp.route("/test-mode", methods=["GET"])
def test_mode_validation():
    """Test endpoint to verify mode validation logic is loaded."""
    test_mode = "simulator_pull"
    normalized = str(test_mode).strip().lower()
    is_valid = normalized in ["simulate", "csv", "simulator_pull"]
    return jsonify(
        {
            "original": test_mode,
            "normalized": normalized,
            "is_valid": is_valid,
            "code_version": "v2_with_normalization",
        }
    )


def _infer_run_source_from_manifest(manifest: dict[str, Any]) -> str:
    """
    Infer the run source for UI comparison/filtering.

    Returns one of:
    - simulator_pull: captured pull from built-in simulator
    - simulate: fully synthetic simulated data
    - real: non-synthetic file-backed runs
    - unknown: cannot determine
    """
    try:
        inputs = (
            manifest.get("inputs") if isinstance(manifest.get("inputs"), dict) else {}
        )
        mode = inputs.get("mode")
        if isinstance(mode, str):
            mode_norm = mode.strip().lower()
            if mode_norm in {"simulator_pull", "simulate"}:
                return mode_norm

        src = manifest.get("source_file", "")
        if src == "simulated":
            return "simulate"

        if isinstance(src, str):
            src_norm = src.replace("\\", "/").lower()
            if src_norm.endswith("_pull.csv"):
                return "simulator_pull"
            if src_norm.endswith(".csv") or src_norm.endswith(".wp8"):
                return "real"

        return "unknown"
    except Exception:
        return "unknown"


@analysis_bp.route("/status", methods=["GET"])
def get_status():
    """Check JetDrive autotune status and available runs."""
    project_root = get_project_root()
    runs_dir = project_root / "runs"

    source_filter = request.args.get("source")
    if source_filter is not None:
        source_filter = str(source_filter).strip().lower()
        if source_filter not in {"simulator_pull", "real", "simulate", "unknown"}:
            return jsonify({"error": "Invalid source filter"}), 400

    runs: list[dict[str, Any]] = []
    if runs_dir.exists():
        for run_dir in sorted(runs_dir.iterdir(), reverse=True):
            if run_dir.is_dir():
                manifest_path = run_dir / "manifest.json"
                if manifest_path.exists():
                    try:
                        with open(manifest_path) as f:
                            manifest = json.load(f)
                        analysis = manifest.get("analysis", {}) or {}
                        peak_perf = manifest.get("peak_performance", {}) or {}

                        peak_hp = (
                            analysis.get("peak_hp")
                            or peak_perf.get("peak_hp")
                            or manifest.get("peak_hp")
                            or 0
                        )
                        peak_tq = (
                            analysis.get("peak_tq")
                            or analysis.get("peak_torque")
                            or peak_perf.get("peak_tq")
                            or peak_perf.get("peak_torque")
                            or manifest.get("peak_tq")
                            or manifest.get("peak_torque")
                            or 0
                        )
                        source = (
                            _infer_run_source_from_manifest(manifest)
                            if isinstance(manifest, dict)
                            else "unknown"
                        )
                        if source_filter and source != source_filter:
                            continue
                        runs.append(
                            {
                                "run_id": run_dir.name,
                                "timestamp": manifest.get("timestamp", ""),
                                "peak_hp": peak_hp or 0,
                                "peak_tq": peak_tq or 0,
                                "status": analysis.get("overall_status", ""),
                                "source": source,
                            }
                        )
                    except Exception:
                        runs.append(
                            {
                                "run_id": run_dir.name,
                                "timestamp": "",
                                "status": "unknown",
                                "source": "unknown",
                            }
                        )

    return jsonify(
        {
            "available": True,
            "runs_count": len(runs),
            "runs": runs[:20],
        }
    )


# ---------------------------------------------------------------------------
# Analysis Routes
# ---------------------------------------------------------------------------


def _compute_power_curve_from_run_csv(
    run_id: str, rpm_bin_size: int = 100
) -> list[dict[str, float]] | None:
    """
    Best-effort power curve extraction for UI overlay charts.
    """
    try:
        csv_path = safe_path_in_runs(run_id, "run.csv")
        if not csv_path.exists():
            return None

        buckets: dict[int, dict[str, float]] = {}
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rpm_raw = row.get("RPM") or row.get("Engine RPM") or row.get("rpm")
                hp_raw = row.get("Horsepower") or row.get("HP") or row.get("hp")
                tq_raw = row.get("Torque") or row.get("TQ") or row.get("tq")
                if rpm_raw is None or hp_raw is None or tq_raw is None:
                    continue
                try:
                    rpm = float(rpm_raw)
                    hp = float(hp_raw)
                    tq = float(tq_raw)
                except (TypeError, ValueError):
                    continue
                if not (isfinite(rpm) and isfinite(hp) and isfinite(tq)):
                    continue
                if rpm <= 0 or rpm >= 20000:
                    continue
                rpm_bin = int(round(rpm / float(rpm_bin_size)) * rpm_bin_size)
                b = buckets.get(rpm_bin)
                if b is None:
                    buckets[rpm_bin] = {"hp": hp, "tq": tq}
                else:
                    if hp > b["hp"]:
                        b["hp"] = hp
                    if tq > b["tq"]:
                        b["tq"] = tq

        if not buckets:
            return None

        return [
            {
                "rpm": float(rpm_bin),
                "hp": round(vals["hp"], 2),
                "tq": round(vals["tq"], 2),
            }
            for rpm_bin, vals in sorted(buckets.items(), key=lambda kv: kv[0])
        ]
    except Exception:
        return None


@analysis_bp.route("/power-opportunities/<run_id>", methods=["GET"])
def get_power_opportunities(run_id: str):
    """Get power opportunities analysis for a completed run."""
    try:
        safe_run_id = sanitize_run_id(run_id)
        power_opp_path = safe_path_in_runs(safe_run_id, "PowerOpportunities.json")

        if not power_opp_path.exists():
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Power opportunities analysis not found for this run",
                    }
                ),
                404,
            )

        with open(power_opp_path, "r") as f:
            data = json.load(f)

        return jsonify({"success": True, "run_id": safe_run_id, "data": data}), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error fetching power opportunities: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@analysis_bp.route("/analyze", methods=["POST"])
def analyze_run():
    """
    Run JetDrive autotune analysis.

    Request body:
    {
        "run_id": "my_run",
        "mode": "simulate" | "csv" | "simulator_pull",
        "csv_path": "path/to/file.csv",
        "afr_targets": { ... }
    }
    """
    try:
        data = request.get_json()
        if data is None:
            logger.error("Failed to parse JSON from request body")
            return jsonify({"error": "Invalid JSON in request body"}), 400
    except Exception as e:
        logger.error(f"Error parsing JSON request: {e}", exc_info=True)
        return jsonify({"error": f"Failed to parse request JSON: {str(e)}"}), 400

    if not data or "run_id" not in data:
        return jsonify({"error": "Missing 'run_id' in request body"}), 400

    try:
        run_id = sanitize_run_id(data["run_id"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", run_id):
            return (
                jsonify(
                    {
                        "error": "Invalid 'run_id'. Must be 1-64 characters of letters, numbers, '_' or '-'."
                    }
                ),
                400,
            )

        mode = data.get("mode", "simulate")
        if mode:
            mode = str(mode).strip().lower()
        else:
            mode = "simulate"

        csv_path = data.get("csv_path")
        afr_targets = data.get("afr_targets")

        logger.info(
            f"Analyze request: run_id={run_id}, mode={mode!r}, simulator_active={_is_simulator_active()}"
        )

        project_root = get_project_root()
        script_path = project_root / "scripts" / "jetdrive_autotune.py"

        if not script_path.exists():
            logger.error(f"Autotune script not found at: {script_path}")
            return (
                jsonify({"error": f"Autotune script not found at: {script_path}"}),
                500,
            )

        cmd = [sys.executable, str(script_path), "--run-id", run_id]
    except Exception as e:
        logger.error(f"Error in analyze_run setup: {e}", exc_info=True)
        import traceback

        error_detail = str(e)
        if os.getenv("FLASK_ENV") == "development" or os.getenv("DYNOAI_DEBUG"):
            error_detail += f"\nTraceback: {''.join(traceback.format_exc())}"
        return jsonify({"success": False, "error": error_detail}), 500

    if mode == "simulate":
        cmd.append("--simulate")
    elif mode == "csv":
        if not csv_path:
            return jsonify({"error": "Missing 'csv_path' for CSV mode"}), 400
        cmd.extend(["--csv", csv_path])
    elif mode == "simulator_pull":
        logger.info(f"Analyzing with simulator_pull mode for run_id={run_id}")
        try:
            if not _is_simulator_active():
                logger.warning("Simulator not active when trying to analyze pull data")
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Simulator is not running. Please start the simulator first.",
                        }
                    ),
                    400,
                )

            import csv as csv_module

            from api.services.simulation.dyno_simulator import get_simulator

            sim = get_simulator()
            sim_state = sim.get_state()
            logger.info(f"Simulator state: {sim_state.value}")

            pull_data = sim.get_pull_data()
            logger.info(
                f"Pull data retrieved: {len(pull_data) if pull_data else 0} points"
            )
        except Exception as e:
            logger.error(f"Error getting simulator pull data: {e}", exc_info=True)
            import traceback

            error_detail = str(e)
            if os.getenv("FLASK_ENV") == "development" or os.getenv("DYNOAI_DEBUG"):
                error_detail += f"\nTraceback: {''.join(traceback.format_exc())}"
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Failed to get simulator pull data: {error_detail}",
                    }
                ),
                500,
            )

        if not pull_data:
            logger.warning("No pull data available from simulator")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": (
                            "No simulator pull data available. Please run a pull first by clicking "
                            "'Trigger Pull' in the simulator controls."
                        ),
                    }
                ),
                400,
            )

        if len(pull_data) == 0:
            logger.warning("Pull data is empty list")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Simulator pull data is empty. Please run a pull first.",
                    }
                ),
                400,
            )

        first_point = pull_data[0]
        logger.info(f"First data point keys: {list(first_point.keys())}")
        required_fields = ["Engine RPM", "Torque", "Horsepower"]
        missing_fields = [f for f in required_fields if f not in first_point]
        if missing_fields:
            logger.error(f"Missing required fields in pull data: {missing_fields}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Simulator pull data is missing required fields: {', '.join(missing_fields)}",
                    }
                ),
                400,
            )

        uploads_dir = project_root / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        csv_filename = f"{run_id}_pull.csv"
        csv_path = str(uploads_dir / csv_filename)

        try:
            import csv as csv_module

            with open(csv_path, "w", newline="") as f:
                fieldnames = [
                    "timestamp_ms",
                    "RPM",
                    "Torque",
                    "Horsepower",
                    "AFR",
                    "MAP_kPa",
                    "TPS",
                    "IAT",
                ]
                writer = csv_module.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for i, row in enumerate(pull_data):
                    afr_avg = (
                        row.get("AFR Meas F", 14.7) + row.get("AFR Meas R", 14.7)
                    ) / 2
                    writer.writerow(
                        {
                            "timestamp_ms": i * 20,
                            "RPM": row.get("Engine RPM", 0),
                            "Torque": row.get("Torque", 0),
                            "Horsepower": row.get("Horsepower", 0),
                            "AFR": afr_avg,
                            "MAP_kPa": row.get("MAP kPa", 0),
                            "TPS": row.get("TPS", 0),
                            "IAT": row.get("IAT F", 85),
                        }
                    )
        except Exception as e:
            return jsonify({"error": f"Failed to save simulator data: {str(e)}"}), 500

        cmd.extend(["--csv", csv_path])
    else:
        valid_modes = ["simulate", "csv", "simulator_pull"]
        return (
            jsonify(
                {
                    "error": f"Invalid mode: {mode!r}. Valid modes are: {', '.join(valid_modes)}"
                }
            ),
            400,
        )

    if afr_targets:
        cmd.extend(["--afr-targets", json.dumps(afr_targets)])

    was_simulator_active = _is_simulator_active()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env={**dict(__import__("os").environ), "PYTHONPATH": str(project_root)},
            timeout=60,
        )

        if result.returncode != 0:
            if was_simulator_active:
                _set_simulator_active(True)
            return (
                jsonify(
                    {
                        "success": False,
                        "error": result.stderr or "Analysis failed",
                        "stdout": result.stdout,
                    }
                ),
                500,
            )

        try:
            manifest_path = safe_path_in_runs(run_id, "manifest.json")
            output_dir = manifest_path.parent
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        if not manifest_path.exists():
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Analysis completed but no manifest found",
                    }
                ),
                500,
            )

        with open(manifest_path) as f:
            manifest = json.load(f)

        try:
            if isinstance(manifest, dict):
                inputs = manifest.get("inputs")
                if not isinstance(inputs, dict):
                    inputs = {}
                    manifest["inputs"] = inputs
                inputs["mode"] = mode
                inputs["mode_recorded_at"] = datetime.utcnow().isoformat() + "Z"
                with open(manifest_path, "w", encoding="utf-8") as wf:
                    json.dump(manifest, wf, indent=2)
        except Exception:
            logger.warning(
                "Failed to persist inputs.mode into manifest.json", exc_info=True
            )

        ve_csv_path = safe_path_in_runs(run_id, "VE_Corrections_2D.csv")
        ve_grid: list[dict[str, Any]] = []
        if ve_csv_path.exists():
            with open(ve_csv_path) as f:
                lines = f.readlines()
                for line in lines[1:]:
                    parts = line.strip().split(",")
                    if parts:
                        ve_grid.append(
                            {
                                "rpm": int(parts[0]),
                                "values": [float(v) for v in parts[1:]],
                            }
                        )

        if was_simulator_active:
            _set_simulator_active(True)

        response_data = {
            "success": True,
            "run_id": run_id,
            "mode": mode,
            "output_dir": str(output_dir),
            "analysis": manifest.get("analysis", {}),
            "grid": manifest.get("grid", {}),
            "ve_grid": ve_grid,
            "outputs": manifest.get("outputs", {}),
        }
        return jsonify(response_data)

    except subprocess.TimeoutExpired:
        if was_simulator_active:
            _set_simulator_active(True)
        logger.error("Analysis timed out after 60 seconds", exc_info=True)
        return jsonify({"success": False, "error": "Analysis timed out"}), 500
    except Exception as e:
        if was_simulator_active:
            _set_simulator_active(True)
        logger.error(f"Error in analyze_run endpoint: {e}", exc_info=True)
        import traceback

        error_detail = str(e)
        if os.getenv("FLASK_ENV") == "development" or os.getenv("DYNOAI_DEBUG"):
            error_detail += f"\nTraceback: {''.join(traceback.format_exc())}"
        return jsonify({"success": False, "error": error_detail}), 500


@analysis_bp.route("/analyze-unified", methods=["POST"])
def analyze_unified():
    """
    Run JetDrive analysis using the unified AutoTuneWorkflow engine.
    """
    data = request.get_json()
    if not data or "run_id" not in data or "csv_path" not in data:
        return jsonify({"error": "Missing 'run_id' or 'csv_path' in request body"}), 400

    try:
        run_id = sanitize_run_id(data["run_id"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        csv_path_val = validate_csv_path(data["csv_path"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    project_root = get_project_root()
    output_dir = project_root / "runs" / run_id

    try:
        _, DataSource, _ = _get_autotune_types()
        workflow = get_workflow()
        session = workflow.run_full_workflow(
            log_path=str(csv_path_val),
            output_dir=str(output_dir),
            data_source=DataSource.JETDRIVE,
        )

        if session.status == "error":
            return (
                jsonify({"success": False, "errors": session.errors}),
                500,
            )

        summary = workflow.get_session_summary(session)
        return jsonify(
            {
                "success": True,
                "run_id": run_id,
                "output_dir": str(output_dir),
                **summary,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@analysis_bp.route("/workflow/session", methods=["POST"])
def create_workflow_session():
    """Create a new unified workflow session."""
    data = request.get_json() or {}
    run_id = data.get("run_id")

    try:
        if run_id:
            run_id = sanitize_run_id(run_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    _, DataSource, _ = _get_autotune_types()
    workflow = get_workflow()
    session = workflow.create_session(run_id=run_id, data_source=DataSource.JETDRIVE)

    return jsonify({"success": True, "session_id": session.id})


@analysis_bp.route("/workflow/session/<session_id>", methods=["GET"])
def get_workflow_session(session_id: str):
    """Get the status of a workflow session."""
    workflow = get_workflow()
    session = workflow.sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(workflow.get_session_summary(session))


@analysis_bp.route("/run/<run_id>", methods=["GET"])
def get_run(run_id: str):
    """Get details for a specific run."""
    try:
        manifest_path = safe_path_in_runs(run_id, "manifest.json")
        output_dir = manifest_path.parent
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not output_dir.exists():
        return jsonify({"error": "Run not found"}), 404

    if not manifest_path.exists():
        return jsonify({"error": "Run manifest not found"}), 404

    with open(manifest_path) as f:
        manifest = json.load(f)

    try:
        analysis = manifest.get("analysis")
        if isinstance(analysis, dict) and not analysis.get("power_curve"):
            curve = _compute_power_curve_from_run_csv(run_id)
            if curve:
                analysis["power_curve"] = curve
    except Exception:
        pass

    ve_csv_path = safe_path_in_runs(run_id, "VE_Corrections_2D.csv")
    ve_grid: list[dict[str, Any]] = []
    if ve_csv_path.exists():
        with open(ve_csv_path) as f:
            lines = f.readlines()
            for line in lines[1:]:
                parts = line.strip().split(",")
                if parts:
                    ve_grid.append(
                        {"rpm": int(parts[0]), "values": [float(v) for v in parts[1:]]}
                    )

    hits_csv_path = safe_path_in_runs(run_id, "Hit_Count_2D.csv")
    hit_grid: list[dict[str, Any]] = []
    if hits_csv_path.exists():
        with open(hits_csv_path) as f:
            lines = f.readlines()
            for line in lines[1:]:
                parts = line.strip().split(",")
                if parts:
                    hit_grid.append(
                        {"rpm": int(parts[0]), "values": [int(v) for v in parts[1:]]}
                    )

    afr_csv_path = safe_path_in_runs(run_id, "AFR_Error_2D.csv")
    afr_grid: list[dict[str, Any]] = []
    if afr_csv_path.exists():
        with open(afr_csv_path) as f:
            lines = f.readlines()
            for line in lines[1:]:
                parts = line.strip().split(",")
                if parts:
                    values: list[float] = []
                    for v in parts[1:]:
                        try:
                            values.append(float(v))
                        except ValueError:
                            values.append(0.0)
                    afr_grid.append({"rpm": int(parts[0]), "values": values})

    confidence_path = safe_path_in_runs(run_id, "ConfidenceReport.json")
    confidence = None
    if confidence_path.exists():
        try:
            with open(confidence_path) as f:
                confidence = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load confidence report for {run_id}: {e}")

    return jsonify(
        {
            "run_id": run_id,
            "manifest": manifest,
            "ve_grid": ve_grid,
            "hit_grid": hit_grid,
            "afr_grid": afr_grid,
            "confidence": confidence,
            "files": {
                "pvv": str(output_dir / "VE_Correction.pvv"),
                "csv": str(output_dir / "run.csv"),
                "report": str(output_dir / "Diagnostics_Report.txt"),
            },
        }
    )


@analysis_bp.route("/run/<run_id>/pvv", methods=["GET"])
def get_pvv(run_id: str):
    """Get the PVV XML content for a run."""
    try:
        pvv_path = safe_path_in_runs(run_id, "VE_Correction.pvv")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not pvv_path.exists():
        return jsonify({"error": "PVV file not found"}), 404

    with open(pvv_path, encoding="utf-8") as f:
        content = f.read()

    return jsonify(
        {
            "run_id": sanitize_run_id(run_id),
            "filename": "VE_Correction.pvv",
            "content": content,
        }
    )


@analysis_bp.route("/run/<run_id>/report", methods=["GET"])
def get_report(run_id: str):
    """Get the diagnostics report for a run."""
    try:
        report_path = safe_path_in_runs(run_id, "Diagnostics_Report.txt")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not report_path.exists():
        return jsonify({"error": "Report not found"}), 404

    with open(report_path, encoding="utf-8") as f:
        content = f.read()

    return jsonify(
        {
            "run_id": sanitize_run_id(run_id),
            "filename": "Diagnostics_Report.txt",
            "content": content,
        }
    )


@analysis_bp.route("/run/<run_id>/export-text", methods=["GET"])
def export_text(run_id: str):
    """Export a comprehensive text summary of the run for sharing with AI assistants."""
    try:
        manifest_path = safe_path_in_runs(run_id, "manifest.json")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not manifest_path.exists():
        return jsonify({"error": "Run not found"}), 404

    with open(manifest_path) as f:
        manifest = json.load(f)

    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("DYNOAI AUTO-TUNE ANALYSIS REPORT")
    lines.append("=" * 80)
    lines.append("")

    lines.append("RUN INFORMATION")
    lines.append("-" * 80)
    lines.append(f"Run ID: {run_id}")
    lines.append(f"Timestamp: {manifest.get('timestamp', 'N/A')}")
    lines.append(f"Data Source: {manifest.get('data_source', 'N/A')}")
    lines.append("")

    analysis = manifest.get("analysis", {})
    if analysis:
        lines.append("PERFORMANCE SUMMARY")
        lines.append("-" * 80)
        peak_hp = analysis.get("peak_hp", 0)
        peak_hp_rpm = analysis.get("peak_hp_rpm", analysis.get("hp_peak_rpm", 0))
        peak_tq = analysis.get("peak_tq", analysis.get("peak_torque", 0))
        peak_tq_rpm = analysis.get(
            "peak_tq_rpm",
            analysis.get("tq_peak_rpm", analysis.get("torque_peak_rpm", 0)),
        )
        lines.append(f"Peak Horsepower: {peak_hp:.2f} HP @ {peak_hp_rpm:.0f} RPM")
        lines.append(f"Peak Torque: {peak_tq:.2f} lb-ft @ {peak_tq_rpm:.0f} RPM")
        lines.append(f"Total Samples: {analysis.get('total_samples', 0)}")
        lines.append(f"Duration: {analysis.get('duration_ms', 0) / 1000:.1f} seconds")
        lines.append("")

    if analysis:
        lines.append("AFR ANALYSIS")
        lines.append("-" * 80)
        lines.append(f"Overall Status: {analysis.get('overall_status', 'N/A')}")
        lines.append(f"Lean Cells: {analysis.get('lean_cells', 0)}")
        lines.append(f"Rich Cells: {analysis.get('rich_cells', 0)}")
        lines.append(f"OK Cells: {analysis.get('ok_cells', 0)}")
        lines.append(f"No Data Cells: {analysis.get('no_data_cells', 0)}")
        lines.append("")

    ve_csv_path = safe_path_in_runs(run_id, "VE_Corrections_2D.csv")
    if ve_csv_path.exists():
        lines.append("VE CORRECTION GRID (2D)")
        lines.append("-" * 80)
        lines.append("Format: RPM | MAP bins (kPa)")
        lines.append("")
        with open(ve_csv_path, encoding="utf-8") as f:
            ve_lines = f.readlines()
            for line in ve_lines:
                lines.append(line.rstrip())
        lines.append("")

    afr_csv_path = safe_path_in_runs(run_id, "AFR_Error_2D.csv")
    if afr_csv_path.exists():
        lines.append("AFR ERROR GRID (2D)")
        lines.append("-" * 80)
        lines.append("Format: RPM | AFR error in AFR points")
        lines.append("")
        with open(afr_csv_path, encoding="utf-8") as f:
            afr_lines = f.readlines()
            for line in afr_lines:
                lines.append(line.rstrip())
        lines.append("")

    hits_csv_path = safe_path_in_runs(run_id, "Hit_Count_2D.csv")
    if hits_csv_path.exists():
        lines.append("HIT COUNT GRID (2D)")
        lines.append("-" * 80)
        lines.append("Format: RPM | Sample count per cell")
        lines.append("")
        with open(hits_csv_path, encoding="utf-8") as f:
            hit_lines = f.readlines()
            for line in hit_lines:
                lines.append(line.rstrip())
        lines.append("")

    report_path = safe_path_in_runs(run_id, "Diagnostics_Report.txt")
    if report_path.exists():
        lines.append("DIAGNOSTICS REPORT")
        lines.append("-" * 80)
        with open(report_path, encoding="utf-8") as f:
            lines.append(f.read())
        lines.append("")

    grid = manifest.get("grid", {})
    if grid:
        lines.append("GRID CONFIGURATION")
        lines.append("-" * 80)
        rpm_bins = grid.get("rpm_bins", [])
        map_bins = grid.get("map_bins", [])
        lines.append(f"RPM Bins: {rpm_bins}")
        lines.append(f"MAP Bins: {map_bins}")
        lines.append(
            f"Grid Size: {len(rpm_bins)} x {len(map_bins)} = {len(rpm_bins) * len(map_bins)} cells"
        )
        lines.append("")

    lines.append("=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)

    content = "\n".join(lines)

    return jsonify(
        {
            "run_id": sanitize_run_id(run_id),
            "filename": f"DynoAI_Analysis_{run_id}.txt",
            "content": content,
        }
    )


# ---------------------------------------------------------------------------
# File Upload Route
# ---------------------------------------------------------------------------


@analysis_bp.route("/upload", methods=["POST"])
def upload_csv():
    """Upload a CSV file for analysis."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.endswith(".csv"):
        return jsonify({"error": "File must be a CSV"}), 400

    safe_filename = secure_filename(file.filename)
    if not safe_filename or not safe_filename.endswith(".csv"):
        return jsonify({"error": "Invalid filename"}), 400

    project_root = get_project_root()
    uploads_dir = project_root / "uploads"
    uploads_dir.mkdir(exist_ok=True)

    filepath = uploads_dir / safe_filename

    try:
        filepath.resolve().relative_to(uploads_dir.resolve())
    except ValueError:
        return jsonify({"error": "Invalid file path"}), 400

    file.save(str(filepath))

    return jsonify(
        {
            "success": True,
            "filename": safe_filename,
            "path": str(filepath),
        }
    )
