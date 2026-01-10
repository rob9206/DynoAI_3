"""
JetDrive Auto-Tune API Routes

Provides REST endpoints for:
- Running JetDrive autotune analysis (unified workflow)
- Simulating dyno runs
- Analyzing existing CSV data
- Exporting PVV corrections
- Hardware diagnostics and discovery

Uses the unified AutoTuneWorkflow engine for all analysis.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import re
import socket
import struct
import subprocess
import sys
import threading
import time
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from api.services.autotune_workflow import AutoTuneWorkflow, DataSource
from dynoai.core.weighted_binning import LogarithmicWeighting

logger = logging.getLogger(__name__)

jetdrive_bp = Blueprint("jetdrive", __name__, url_prefix="/api/jetdrive")

# Singleton workflow instance for unified analysis
_workflow: AutoTuneWorkflow | None = None

# TuneLab-style analysis configuration
# Can be overridden via environment variables or API
TUNELAB_CONFIG = {
    # Signal filtering (TuneLab-style)
    "enable_filtering": os.environ.get("DYNOAI_ENABLE_FILTERING", "true").lower()
    == "true",
    "lowpass_rc_ms": float(os.environ.get("DYNOAI_LOWPASS_RC_MS", "500.0")),
    "afr_min": float(os.environ.get("DYNOAI_AFR_MIN", "10.0")),
    "afr_max": float(os.environ.get("DYNOAI_AFR_MAX", "19.0")),
    "exclude_time_ms": float(os.environ.get("DYNOAI_EXCLUDE_TIME_MS", "50.0")),
    "enable_statistical_filter": os.environ.get(
        "DYNOAI_ENABLE_STATISTICAL_FILTER", "true"
    ).lower()
    == "true",
    "sigma_threshold": float(os.environ.get("DYNOAI_SIGMA_THRESHOLD", "2.0")),
    # Distance-weighted binning (TuneLab-style)
    "use_weighted_binning": os.environ.get(
        "DYNOAI_USE_WEIGHTED_BINNING", "true"
    ).lower()
    == "true",
}


def get_workflow() -> AutoTuneWorkflow:
    """Get or create the unified workflow instance with TuneLab features."""
    global _workflow
    if _workflow is None:
        _workflow = AutoTuneWorkflow(
            # TuneLab-style filtering
            enable_filtering=TUNELAB_CONFIG["enable_filtering"],
            lowpass_rc_ms=TUNELAB_CONFIG["lowpass_rc_ms"],
            afr_min=TUNELAB_CONFIG["afr_min"],
            afr_max=TUNELAB_CONFIG["afr_max"],
            exclude_time_ms=TUNELAB_CONFIG["exclude_time_ms"],
            enable_statistical_filter=TUNELAB_CONFIG["enable_statistical_filter"],
            sigma_threshold=TUNELAB_CONFIG["sigma_threshold"],
            # TuneLab-style weighted binning
            use_weighted_binning=TUNELAB_CONFIG["use_weighted_binning"],
            weighting_strategy=LogarithmicWeighting(),
        )
        logger.info(
            f"AutoTuneWorkflow initialized with TuneLab features: "
            f"filtering={TUNELAB_CONFIG['enable_filtering']}, "
            f"weighted_binning={TUNELAB_CONFIG['use_weighted_binning']}"
        )
    return _workflow


def reset_workflow() -> None:
    """Reset the workflow instance (e.g., after config change)."""
    global _workflow
    _workflow = None


# =============================================================================
# TuneLab Configuration Endpoint
# =============================================================================


@jetdrive_bp.route("/tunelab/config", methods=["GET"])
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


@jetdrive_bp.route("/tunelab/config", methods=["POST"])
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

        # Update configuration
        for key in TUNELAB_CONFIG:
            if key in data:
                value = data[key]
                # Type conversion
                if key in [
                    "enable_filtering",
                    "enable_statistical_filter",
                    "use_weighted_binning",
                ]:
                    TUNELAB_CONFIG[key] = bool(value)
                else:
                    TUNELAB_CONFIG[key] = float(value)

        # Reset workflow to apply new config
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


def get_project_root() -> Path:
    """Get project root directory."""
    # 0) Standalone mode - use user data directory
    if os.environ.get("DYNOAI_STANDALONE") or hasattr(sys, "_MEIPASS"):
        # In standalone mode, use user's home directory for data
        data_dir = Path.home() / "DynoAI"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    # 1) Explicit env override (useful for tests and deployments)
    env_root = os.getenv("DYNOAI_PROJECT_ROOT") or os.getenv("DYNOAI_ROOT")
    if env_root:
        try:
            p = Path(env_root).expanduser().resolve()
            if p.exists() and p.is_dir():
                return p
        except Exception:
            # Fall through to auto-detection
            pass

    # 2) If the process was started from the project root, prefer CWD
    try:
        cwd = Path.cwd().resolve()
        # Heuristic: repo root contains the `api/` directory.
        if (cwd / "api").is_dir():
            return cwd
    except Exception:
        pass

    # 3) Fallback: derive from this file location (`api/routes/jetdrive.py`)
    return Path(__file__).resolve().parent.parent.parent


# =============================================================================
# Configuration endpoints
# =============================================================================


@jetdrive_bp.route("/dyno/config", methods=["GET"])
def get_dyno_config():
    """Return Dyno configuration used for calculations and display."""
    try:
        from api.config import get_config

        cfg = get_config().dyno
        return jsonify({"success": True, "config": cfg.to_dict()})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


def sanitize_run_id(run_id: str) -> str:
    """
    Sanitize run_id to prevent path traversal attacks.
    Only allow alphanumeric, underscore, and hyphen characters.
    """
    if not run_id:
        raise ValueError("run_id cannot be empty")
    # Remove any path separators and dangerous characters
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", run_id)
    # Ensure it doesn't start with dots or dashes
    sanitized = sanitized.lstrip(".-")
    if not sanitized:
        raise ValueError("Invalid run_id after sanitization")
    return sanitized


def safe_path_in_runs(run_id: str, filename: str) -> Path:
    """
    Create a safe path within the runs directory.
    Validates that the resulting path is within the runs directory.
    """
    project_root = get_project_root()
    runs_dir = project_root / "runs"

    # Sanitize run_id
    safe_run_id = sanitize_run_id(run_id)

    # Build path and resolve to absolute
    target_path = (runs_dir / safe_run_id / filename).resolve()

    # Ensure the path is within runs directory
    try:
        target_path.relative_to(runs_dir.resolve())
    except ValueError:
        raise ValueError(f"Path traversal attempt detected: {run_id}")

    return target_path


def validate_csv_path(csv_path: str) -> Path:
    """
    Ensure the provided CSV path exists and is constrained to trusted directories.
    Allowed roots: uploads/ or runs/ under the project root.
    """
    project_root = get_project_root()
    allowed_dirs = [project_root / "uploads", project_root / "runs"]

    path = Path(csv_path).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        raise ValueError("CSV path not found")

    if not resolved.is_file():
        raise ValueError("CSV path must be a file")

    for allowed in allowed_dirs:
        try:
            resolved.relative_to(allowed.resolve())
            return resolved
        except ValueError:
            continue

    raise ValueError("CSV path must be under uploads/ or runs/")


def _compute_power_curve_from_run_csv(
    run_id: str, rpm_bin_size: int = 100
) -> list[dict[str, float]] | None:
    """
    Best-effort power curve extraction for UI overlay charts.

    Compatibility fallback for older runs whose manifest.json doesn't yet include
    analysis.power_curve. This does NOT write back to disk.
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


def _infer_run_source_from_manifest(manifest: dict[str, Any]) -> str:
    """
    Infer the run source for UI comparison/filtering.

    Returns one of:
    - simulator_pull: captured pull from built-in simulator (analyzed from CSV but origin is simulator)
    - simulate: fully synthetic simulated data (--simulate)
    - real: non-synthetic file-backed runs (hardware capture or imported logs)
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
            # Any other file-backed source is treated as "real" for UI purposes.
            if src_norm.endswith(".csv") or src_norm.endswith(".wp8"):
                return "real"

        return "unknown"
    except Exception:
        return "unknown"


# =============================================================================
# Status Routes
# =============================================================================


@jetdrive_bp.route("/test-mode", methods=["GET"])
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


@jetdrive_bp.route("/status", methods=["GET"])
def get_status():
    """Check JetDrive autotune status and available runs."""
    project_root = get_project_root()
    runs_dir = project_root / "runs"

    source_filter = request.args.get("source")
    if source_filter is not None:
        source_filter = str(source_filter).strip().lower()
        if source_filter not in {"simulator_pull", "real", "simulate", "unknown"}:
            return jsonify({"error": "Invalid source filter"}), 400

    runs = []
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

                        # Support multiple historical key conventions
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
            "runs": runs[:20],  # Limit to 20 most recent
        }
    )


# =============================================================================
# Analysis Routes
# =============================================================================


@jetdrive_bp.route("/power-opportunities/<run_id>", methods=["GET"])
def get_power_opportunities(run_id: str):
    """
    Get power opportunities analysis for a completed run.

    Returns the PowerOpportunities.json file if it exists.
    """
    try:
        # Sanitize run_id
        safe_run_id = sanitize_run_id(run_id)

        # Look for PowerOpportunities.json in the run directory
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

        # Read and return the power opportunities data
        with open(power_opp_path, "r") as f:
            data = json.load(f)

        return jsonify({"success": True, "run_id": safe_run_id, "data": data}), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error fetching power opportunities: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@jetdrive_bp.route("/analyze", methods=["POST"])
def analyze_run():
    """
    Run JetDrive autotune analysis.

    Request body:
    {
        "run_id": "my_run",
        "mode": "simulate" | "csv" | "simulator_pull",
        "csv_path": "path/to/file.csv",  // Required if mode=csv
        "afr_targets": {                  // Optional AFR targets by MAP (kPa)
            "20": 14.7,
            "30": 14.7,
            "40": 14.5,
            "50": 14.0,
            "60": 13.5,
            "70": 13.0,
            "80": 12.8,
            "90": 12.5,
            "100": 12.2
        }
    }

    mode="simulator_pull" will automatically save the last simulator pull data
    and analyze it.
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
        mode = data.get("mode", "simulate")
        # Normalize mode: strip whitespace and convert to lowercase for comparison
        if mode:
            mode = str(mode).strip().lower()
        else:
            mode = "simulate"

        csv_path = data.get("csv_path")
        afr_targets = data.get("afr_targets")

        # Log the mode for debugging
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

        # Build command
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
        # Save simulator pull data first
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

            from api.services.dyno_simulator import get_simulator

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

        # Validate pull data has required fields
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

        # Check for required fields in first data point
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

        # Save pull data to CSV
        uploads_dir = project_root / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        csv_filename = f"{run_id}_pull.csv"
        csv_path = str(uploads_dir / csv_filename)

        try:
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
                    # Use average of front/rear AFR
                    afr_avg = (
                        row.get("AFR Meas F", 14.7) + row.get("AFR Meas R", 14.7)
                    ) / 2

                    writer.writerow(
                        {
                            "timestamp_ms": i
                            * 20,  # 50Hz = 20ms per sample (NOT 50ms!)
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

        # Now analyze the saved CSV
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

    # Pass AFR targets as JSON string if provided
    if afr_targets:
        cmd.extend(["--afr-targets", json.dumps(afr_targets)])

    # Run analysis
    # Note: Keep simulator active flag set during analysis
    # to prevent UI from switching views mid-analysis
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
            # Restore simulator active state if it was active before
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

        # Load results using safe path
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

        # Persist the requested mode into the manifest so the UI can filter runs by source.
        # (Important for simulator_pull: it analyzes a CSV, but origin is simulator.)
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

        # Read VE correction grid
        ve_csv_path = safe_path_in_runs(run_id, "VE_Corrections_2D.csv")
        ve_grid = []
        if ve_csv_path.exists():
            with open(ve_csv_path) as f:
                lines = f.readlines()
                for line in lines[1:]:  # Skip header
                    parts = line.strip().split(",")
                    if parts:
                        ve_grid.append(
                            {
                                "rpm": int(parts[0]),
                                "values": [float(v) for v in parts[1:]],
                            }
                        )

        # Ensure simulator stays active after analysis if it was active before
        if was_simulator_active:
            _set_simulator_active(True)

        response_data = {
            "success": True,
            "run_id": run_id,
            "mode": mode,  # Include mode so frontend knows what was analyzed
            "output_dir": str(output_dir),
            "analysis": manifest.get("analysis", {}),
            "grid": manifest.get("grid", {}),
            "ve_grid": ve_grid,
            "outputs": manifest.get("outputs", {}),
        }
        return jsonify(response_data)

    except subprocess.TimeoutExpired:
        # Restore simulator active state if it was active before
        if was_simulator_active:
            _set_simulator_active(True)
        logger.error("Analysis timed out after 60 seconds", exc_info=True)
        return jsonify({"success": False, "error": "Analysis timed out"}), 500
    except Exception as e:
        # Restore simulator active state if it was active before
        if was_simulator_active:
            _set_simulator_active(True)
        # Log full exception with traceback for debugging
        logger.error(f"Error in analyze_run endpoint: {e}", exc_info=True)
        # Return detailed error in development, generic in production
        import traceback

        error_detail = str(e)
        if os.getenv("FLASK_ENV") == "development" or os.getenv("DYNOAI_DEBUG"):
            error_detail += f"\nTraceback: {''.join(traceback.format_exc())}"
        return jsonify({"success": False, "error": error_detail}), 500


@jetdrive_bp.route("/analyze-unified", methods=["POST"])
def analyze_unified():
    """
    Run JetDrive analysis using the unified AutoTuneWorkflow engine.

    This uses the same analysis engine as Power Vision logs,
    ensuring consistent results across all data sources.

    Request body:
    {
        "run_id": "my_run",
        "csv_path": "path/to/file.csv"  // Path to JetDrive CSV
    }
    """
    data = request.get_json()
    if not data or "run_id" not in data or "csv_path" not in data:
        return jsonify({"error": "Missing 'run_id' or 'csv_path' in request body"}), 400

    try:
        run_id = sanitize_run_id(data["run_id"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        csv_path = validate_csv_path(data["csv_path"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    project_root = get_project_root()
    output_dir = project_root / "runs" / run_id

    try:
        workflow = get_workflow()

        # Run the unified workflow with JetDrive data source
        session = workflow.run_full_workflow(
            log_path=str(csv_path),
            output_dir=str(output_dir),
            data_source=DataSource.JETDRIVE,
        )

        if session.status == "error":
            return (
                jsonify({"success": False, "errors": session.errors}),
                500,
            )

        # Get session summary (which includes all the analysis results)
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


@jetdrive_bp.route("/workflow/session", methods=["POST"])
def create_workflow_session():
    """Create a new unified workflow session."""
    data = request.get_json() or {}
    run_id = data.get("run_id")

    try:
        if run_id:
            run_id = sanitize_run_id(run_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    workflow = get_workflow()
    session = workflow.create_session(run_id=run_id, data_source=DataSource.JETDRIVE)

    return jsonify({"success": True, "session_id": session.id})


@jetdrive_bp.route("/workflow/session/<session_id>", methods=["GET"])
def get_workflow_session(session_id: str):
    """Get the status of a workflow session."""
    workflow = get_workflow()
    session = workflow.sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(workflow.get_session_summary(session))


@jetdrive_bp.route("/run/<run_id>", methods=["GET"])
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

    # Backfill power curve for older runs (do not write back to disk)
    try:
        analysis = manifest.get("analysis")
        if isinstance(analysis, dict) and not analysis.get("power_curve"):
            curve = _compute_power_curve_from_run_csv(run_id)
            if curve:
                analysis["power_curve"] = curve
    except Exception:
        pass

    # Read VE correction grid
    ve_csv_path = safe_path_in_runs(run_id, "VE_Corrections_2D.csv")
    ve_grid = []
    if ve_csv_path.exists():
        with open(ve_csv_path) as f:
            lines = f.readlines()
            for line in lines[1:]:  # Skip header
                parts = line.strip().split(",")
                if parts:
                    ve_grid.append(
                        {"rpm": int(parts[0]), "values": [float(v) for v in parts[1:]]}
                    )

    # Read hit count grid
    hits_csv_path = safe_path_in_runs(run_id, "Hit_Count_2D.csv")
    hit_grid = []
    if hits_csv_path.exists():
        with open(hits_csv_path) as f:
            lines = f.readlines()
            for line in lines[1:]:
                parts = line.strip().split(",")
                if parts:
                    hit_grid.append(
                        {"rpm": int(parts[0]), "values": [int(v) for v in parts[1:]]}
                    )

    # Read AFR error grid
    afr_csv_path = safe_path_in_runs(run_id, "AFR_Error_2D.csv")
    afr_grid = []
    if afr_csv_path.exists():
        with open(afr_csv_path) as f:
            lines = f.readlines()
            for line in lines[1:]:
                parts = line.strip().split(",")
                if parts:
                    values = []
                    for v in parts[1:]:
                        try:
                            values.append(float(v))
                        except ValueError:
                            # Keep shape stable; treat invalid entries as 0.0
                            values.append(0.0)
                    afr_grid.append({"rpm": int(parts[0]), "values": values})

    # Read confidence report if available
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


@jetdrive_bp.route("/run/<run_id>/pvv", methods=["GET"])
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


@jetdrive_bp.route("/run/<run_id>/report", methods=["GET"])
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


@jetdrive_bp.route("/run/<run_id>/export-text", methods=["GET"])
def export_text(run_id: str):
    """
    Export a comprehensive text summary of the run for sharing with AI assistants.

    This generates a human-readable text file containing:
    - Run metadata
    - Performance summary (peak HP, TQ)
    - AFR analysis results
    - VE correction grid
    - Zone-by-zone breakdown
    """
    try:
        manifest_path = safe_path_in_runs(run_id, "manifest.json")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not manifest_path.exists():
        return jsonify({"error": "Run not found"}), 404

    # Load manifest
    with open(manifest_path) as f:
        manifest = json.load(f)

    # Build text export
    lines = []
    lines.append("=" * 80)
    lines.append("DYNOAI AUTO-TUNE ANALYSIS REPORT")
    lines.append("=" * 80)
    lines.append("")

    # Run metadata
    lines.append("RUN INFORMATION")
    lines.append("-" * 80)
    lines.append(f"Run ID: {run_id}")
    lines.append(f"Timestamp: {manifest.get('timestamp', 'N/A')}")
    lines.append(f"Data Source: {manifest.get('data_source', 'N/A')}")
    lines.append("")

    # Performance summary
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

    # AFR analysis
    if analysis:
        lines.append("AFR ANALYSIS")
        lines.append("-" * 80)
        lines.append(f"Overall Status: {analysis.get('overall_status', 'N/A')}")
        lines.append(f"Lean Cells: {analysis.get('lean_cells', 0)}")
        lines.append(f"Rich Cells: {analysis.get('rich_cells', 0)}")
        lines.append(f"OK Cells: {analysis.get('ok_cells', 0)}")
        lines.append(f"No Data Cells: {analysis.get('no_data_cells', 0)}")
        lines.append("")

    # VE correction grid
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

    # AFR error grid
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

    # Hit count grid
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

    # Diagnostics report
    report_path = safe_path_in_runs(run_id, "Diagnostics_Report.txt")
    if report_path.exists():
        lines.append("DIAGNOSTICS REPORT")
        lines.append("-" * 80)
        with open(report_path, encoding="utf-8") as f:
            lines.append(f.read())
        lines.append("")

    # Grid configuration
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

    # Footer
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


# =============================================================================
# File Upload Route
# =============================================================================


@jetdrive_bp.route("/upload", methods=["POST"])
def upload_csv():
    """Upload a CSV file for analysis."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.endswith(".csv"):
        return jsonify({"error": "File must be a CSV"}), 400

    # Secure the filename to prevent path traversal
    safe_filename = secure_filename(file.filename)
    if not safe_filename or not safe_filename.endswith(".csv"):
        return jsonify({"error": "Invalid filename"}), 400

    project_root = get_project_root()
    uploads_dir = project_root / "uploads"
    uploads_dir.mkdir(exist_ok=True)

    # Save file with secured name
    filepath = uploads_dir / safe_filename

    # Verify path is within uploads directory
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


# =============================================================================
# Hardware Diagnostics Routes
# =============================================================================

# JetDrive defaults
# 224.0.2.10 = Official Dynojet/JetDrive vendor multicast address
JETDRIVE_MCAST_GROUP = os.getenv("JETDRIVE_MCAST_GROUP", "224.0.2.10")
JETDRIVE_PORT = int(os.getenv("JETDRIVE_PORT", "22344"))
JETDRIVE_IFACE = os.getenv("JETDRIVE_IFACE", "0.0.0.0")


def get_network_interfaces() -> list[dict[str, Any]]:
    """Get available network interfaces."""
    interfaces = []

    try:
        import netifaces

        for iface_name in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface_name)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr.get("addr", "")
                    if ip:
                        interfaces.append(
                            {
                                "name": iface_name,
                                "ip": ip,
                                "is_loopback": ip.startswith("127."),
                            }
                        )
    except ImportError:
        # Fallback: use socket
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            interfaces.append(
                {
                    "name": "default",
                    "ip": ip,
                    "is_loopback": ip.startswith("127."),
                }
            )
        except socket.error:
            pass

        interfaces.append(
            {
                "name": "loopback",
                "ip": "127.0.0.1",
                "is_loopback": True,
            }
        )

    return interfaces


def test_multicast_support(interface_ip: str = "0.0.0.0") -> tuple[bool, str]:
    """Test if multicast is supported."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        mreq = struct.pack(
            "4s4s",
            socket.inet_aton(JETDRIVE_MCAST_GROUP),
            socket.inet_aton(interface_ip),
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.close()
        return True, "Multicast join successful"
    except OSError as e:
        return False, f"Multicast error: {e}"
    except Exception as e:
        return False, f"Unknown error: {e}"


def test_port_available(port: int) -> tuple[bool, str]:
    """Test if port is available."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", port))
        sock.close()
        return True, f"Port {port} is available"
    except OSError as e:
        return False, f"Port {port} unavailable: {e}"


@jetdrive_bp.route("/hardware/diagnostics", methods=["GET"])
def run_diagnostics():
    """
    Run hardware diagnostics for JetDrive connectivity.

    Returns diagnostic information about:
    - Network interfaces
    - Multicast support
    - Port availability
    - Environment configuration
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": "ok",
        "checks": [],
    }

    errors = 0

    # 1. Network interfaces
    interfaces = get_network_interfaces()
    results["checks"].append(
        {
            "name": "network_interfaces",
            "status": "ok" if interfaces else "error",
            "message": f"Found {len(interfaces)} interface(s)",
            "details": interfaces,
        }
    )
    if not interfaces:
        errors += 1

    # 2. Multicast support
    multicast_results = []
    multicast_ok = False

    for iface in interfaces:
        if iface["is_loopback"]:
            continue
        ok, msg = test_multicast_support(iface["ip"])
        multicast_results.append(
            {
                "interface": iface["ip"],
                "status": "ok" if ok else "warning",
                "message": msg,
            }
        )
        if ok:
            multicast_ok = True

    # Also test 0.0.0.0
    ok, msg = test_multicast_support("0.0.0.0")
    multicast_results.append(
        {
            "interface": "0.0.0.0 (any)",
            "status": "ok" if ok else "error",
            "message": msg,
        }
    )
    if ok:
        multicast_ok = True
    else:
        errors += 1

    results["checks"].append(
        {
            "name": "multicast_support",
            "status": "ok" if multicast_ok else "error",
            "message": f"Multicast group: {JETDRIVE_MCAST_GROUP}",
            "details": multicast_results,
        }
    )

    # 3. Port availability
    ok, msg = test_port_available(JETDRIVE_PORT)
    results["checks"].append(
        {
            "name": "port_availability",
            "status": "ok" if ok else "error",
            "message": msg,
            "details": {"port": JETDRIVE_PORT},
        }
    )
    if not ok:
        errors += 1

    # 4. Environment configuration
    results["checks"].append(
        {
            "name": "environment",
            "status": "ok",
            "message": "Environment configuration",
            "details": {
                "JETDRIVE_MCAST_GROUP": JETDRIVE_MCAST_GROUP,
                "JETDRIVE_PORT": JETDRIVE_PORT,
                "JETDRIVE_IFACE": JETDRIVE_IFACE,
            },
        }
    )

    # Overall status
    if errors > 0:
        results["overall_status"] = "error"
        results["error_count"] = errors

    return jsonify(results)


@jetdrive_bp.route("/hardware/discover", methods=["GET"])
def discover_providers():
    """
    Discover JetDrive providers on the network.

    Query params:
    - timeout: Discovery timeout in seconds (default: 3)
    """
    timeout = float(request.args.get("timeout", 3.0))

    try:
        # Import the async discover function
        project_root = get_project_root()
        sys.path.insert(0, str(project_root))

        from api.services.jetdrive_client import (
            JetDriveConfig,
        )
        from api.services.jetdrive_client import discover_providers as async_discover

        config = JetDriveConfig(
            multicast_group=JETDRIVE_MCAST_GROUP,
            port=JETDRIVE_PORT,
            iface=JETDRIVE_IFACE,
        )

        # Run async discovery
        providers = asyncio.run(async_discover(config, timeout=timeout))

        # Convert to JSON-serializable format
        provider_list = []
        for p in providers:
            channels = []
            for chan_id, chan in p.channels.items():
                channels.append(
                    {
                        "id": chan_id,
                        "name": chan.name,
                        "unit": chan.unit,
                    }
                )

            provider_list.append(
                {
                    "provider_id": p.provider_id,
                    "provider_id_hex": f"0x{p.provider_id:04X}",
                    "name": p.name,
                    "host": p.host,
                    "port": p.port,
                    "channels": channels,
                    "channel_count": len(channels),
                }
            )

        return jsonify(
            {
                "success": True,
                "timeout": timeout,
                "providers_found": len(provider_list),
                "providers": provider_list,
            }
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "providers_found": 0,
                    "providers": [],
                }
            ),
            500,
        )


@jetdrive_bp.route("/hardware/discover/multi", methods=["GET"])
def discover_providers_multi():
    """
    Discover JetDrive providers on multiple multicast addresses.

    Tests both the old default (224.0.2.10) and new address (239.255.60.60)
    to help identify which one the hardware is actually using.

    Query params:
    - timeout: Discovery timeout per address in seconds (default: 3)
    """
    timeout = float(request.args.get("timeout", 3.0))

    # Test both multicast addresses
    multicast_groups = [
        "224.0.2.10",      # Official Dynojet/JetDrive vendor address (PRIMARY)
        "239.255.60.60",   # Alternative address
    ]

    results = {}

    try:
        from api.services.jetdrive_client import JetDriveConfig, discover_providers

        for mcast_group in multicast_groups:
            try:
                config = JetDriveConfig(
                    multicast_group=mcast_group,
                    port=JETDRIVE_PORT,
                    iface=JETDRIVE_IFACE,
                )

                # Run async discovery
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    providers = loop.run_until_complete(
                        discover_providers(config, timeout=timeout)
                    )
                finally:
                    try:
                        loop.close()
                    except Exception:
                        pass

                # Convert to JSON-serializable format
                provider_list = []
                for p in providers:
                    channels = []
                    for chan_id, chan in p.channels.items():
                        channels.append(
                            {
                                "id": chan_id,
                                "name": chan.name,
                                "unit": chan.unit,
                            }
                        )

                    provider_list.append(
                        {
                            "provider_id": p.provider_id,
                            "provider_id_hex": f"0x{p.provider_id:04X}",
                            "name": p.name,
                            "host": p.host,
                            "port": p.port,
                            "channels": channels,
                            "channel_count": len(channels),
                        }
                    )

                results[mcast_group] = {
                    "success": True,
                    "providers_found": len(provider_list),
                    "providers": provider_list,
                    "error": None,
                }

            except Exception as e:
                results[mcast_group] = {
                    "success": False,
                    "providers_found": 0,
                    "providers": [],
                    "error": str(e),
                }
                logger.error(f"Discovery error for {mcast_group}: {e}", exc_info=True)

        # Determine which address found providers
        best_address = None
        best_count = 0
        for mcast_group, result in results.items():
            if result["success"] and result["providers_found"] > best_count:
                best_count = result["providers_found"]
                best_address = mcast_group

        return jsonify(
            {
                "success": True,
                "timeout": timeout,
                "results": results,
                "recommendation": {
                    "best_address": best_address,
                    "providers_found": best_count,
                    "message": (
                        f"Use multicast address: {best_address}"
                        if best_address
                        else "No providers found on either address. Check Power Core settings and network connection."
                    ),
                },
            }
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "results": results,
                }
            ),
            500,
        )


# Global state for connection monitoring
_monitor_state: dict[str, Any] = {
    "running": False,
    "last_check": None,
    "providers": [],
    "history": [],
}
_monitor_lock = threading.Lock()


def _monitor_loop():
    """Background thread for connection monitoring."""
    global _monitor_state

    project_root = get_project_root()
    sys.path.insert(0, str(project_root))

    from api.services.jetdrive_client import (
        JetDriveConfig,
    )
    from api.services.jetdrive_client import discover_providers as async_discover

    config = JetDriveConfig(
        multicast_group=JETDRIVE_MCAST_GROUP,
        port=JETDRIVE_PORT,
        iface=JETDRIVE_IFACE,
    )

    while True:
        with _monitor_lock:
            if not _monitor_state["running"]:
                break

        try:
            providers = asyncio.run(async_discover(config, timeout=2.0))

            provider_list = []
            for p in providers:
                provider_list.append(
                    {
                        "provider_id": p.provider_id,
                        "name": p.name,
                        "host": p.host,
                        "channel_count": len(p.channels),
                    }
                )

            with _monitor_lock:
                _monitor_state["last_check"] = datetime.now().isoformat()
                _monitor_state["providers"] = provider_list
                _monitor_state["history"].append(
                    {
                        "timestamp": _monitor_state["last_check"],
                        "connected": len(provider_list) > 0,
                        "provider_count": len(provider_list),
                    }
                )
                # Keep only last 60 entries (about 3 minutes at 3s interval)
                if len(_monitor_state["history"]) > 60:
                    _monitor_state["history"] = _monitor_state["history"][-60:]

        except Exception:
            with _monitor_lock:
                _monitor_state["last_check"] = datetime.now().isoformat()
                _monitor_state["providers"] = []
                _monitor_state["history"].append(
                    {
                        "timestamp": _monitor_state["last_check"],
                        "connected": False,
                        "provider_count": 0,
                        "error": True,
                    }
                )

        time.sleep(3.0)


@jetdrive_bp.route("/hardware/monitor/start", methods=["POST"])
def start_monitor():
    """Start the connection monitor."""
    global _monitor_state

    with _monitor_lock:
        if _monitor_state["running"]:
            return jsonify({"status": "already_running"})

        _monitor_state["running"] = True
        _monitor_state["history"] = []

    thread = threading.Thread(target=_monitor_loop, daemon=True)
    thread.start()

    return jsonify({"status": "started"})


@jetdrive_bp.route("/hardware/monitor/stop", methods=["POST"])
def stop_monitor():
    """Stop the connection monitor."""
    global _monitor_state

    with _monitor_lock:
        _monitor_state["running"] = False

    return jsonify({"status": "stopped"})


@jetdrive_bp.route("/hardware/monitor/status", methods=["GET"])
def get_monitor_status():
    """Get current monitor status."""
    global _monitor_state

    with _monitor_lock:
        return jsonify(
            {
                "running": _monitor_state["running"],
                "last_check": _monitor_state["last_check"],
                "providers": _monitor_state["providers"],
                "connected": len(_monitor_state["providers"]) > 0,
                "history": _monitor_state["history"][-20:],  # Last 20 entries
            }
        )


# =============================================================================
# Live Data Streaming
# =============================================================================

# Store for live channel values
_live_data: dict[str, Any] = {
    "channels": {},
    "last_update": None,
    "capturing": False,
}
_live_data_lock = threading.Lock()


def _live_capture_loop():
    """Background thread to capture live channel data continuously."""
    global _live_data

    from api.services.jetdrive_client import (
        JetDriveConfig,
        JetDriveSample,
        discover_providers,
        subscribe,
    )

    config = JetDriveConfig.from_env()
    # Create a single event loop for the entire capture session
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Discover providers first - use longer timeout to ensure ChannelInfo packets arrive
        # Power Core broadcasts ChannelInfo periodically (not immediately on request)
        logger.info("Discovering JetDrive providers (waiting for ChannelInfo)...")
        providers = loop.run_until_complete(discover_providers(config, timeout=10.0))
        if not providers:
            logger.warning(
                "No JetDrive providers found. Check network connection and multicast settings."
            )
            with _live_data_lock:
                _live_data["channels"] = {}
                _live_data["last_update"] = datetime.now().isoformat()
                _live_data["error"] = "No providers found"
            return

        provider = providers[0]
        logger.info(
            f"Connected to provider: {provider.name} (ID: 0x{provider.provider_id:04X}, Host: {provider.host})"
        )
        # Channel values dictionary - updated continuously
        channel_values: dict[str, dict[str, Any]] = {}

        def on_sample(s: JetDriveSample):
            """Callback for each received sample - updates channel values immediately."""
            entry = {
                "id": s.channel_id,
                "name": s.channel_name,
                "value": s.value,
                "timestamp": s.timestamp_ms,
                "updated_at": datetime.now().isoformat(),
            }
            channel_values[s.channel_name] = entry
            # Also add a stable chan_<id> alias so the frontend can fall back
            # even if the provider's channel_name differs from expected.
            chan_key = f"chan_{s.channel_id}"
            if s.channel_name != chan_key and chan_key not in channel_values:
                channel_values[chan_key] = entry

            # Update live data immediately (with lock for thread safety)
            with _live_data_lock:
                _live_data["channels"] = dict(
                    channel_values
                )  # Copy to avoid race conditions
                _live_data["last_update"] = datetime.now().isoformat()
                if "error" in _live_data:
                    del _live_data["error"]

        # Create stop event that checks the global capturing flag
        stop_event = asyncio.Event()

        async def check_stop_periodically():
            """Periodically check if we should stop capturing."""
            while True:
                await asyncio.sleep(0.5)  # Check every 500ms
                with _live_data_lock:
                    if not _live_data.get("capturing", False):
                        stop_event.set()
                        break

        # Start the periodic check task
        check_task = loop.create_task(check_stop_periodically())

        # Start continuous subscription - this will run until stop_event is set
        logger.info("Starting continuous data capture...")
        logger.info(f"Provider channels: {list(provider.channels.keys())}")

        # Track statistics for diagnostics
        sample_count = [0]  # Use list to allow modification in nested function
        last_sample_time = [None]
        stats_dict = {"total_frames": 0, "dropped_frames": 0, "non_provider_frames": 0}

        def on_sample_with_stats(s: JetDriveSample):
            sample_count[0] += 1
            last_sample_time[0] = datetime.now()
            if sample_count[0] % 100 == 0:  # Log every 100 samples
                logger.info(
                    f"Received {sample_count[0]} samples, latest: {s.channel_name}={s.value}"
                )
            on_sample(s)

        # Wrap subscribe to capture stats
        async def subscribe_with_stats():
            from api.services.jetdrive_client import subscribe

            try:
                stats = await subscribe(
                    provider,
                    [],  # Empty list means subscribe to all channels
                    on_sample_with_stats,
                    config=config,
                    stop_event=stop_event,
                    recv_timeout=2.0,  # 2 second timeout for receiving data
                    debug=True,  # Enable debug logging
                    return_stats=True,  # Return statistics
                )
                if stats:
                    stats_dict.update(stats)
                return stats
            except Exception as e:
                logger.error(f"Subscribe error: {e}", exc_info=True)
                raise

        try:
            # Start subscription - this will run until stop_event is set
            logger.info(
                f"Subscribing to provider {provider.name} (ID: 0x{provider.provider_id:04X})"
            )
            logger.info(f"Available channels: {list(provider.channels.keys())}")

            stats = loop.run_until_complete(subscribe_with_stats())

            # Log final statistics
            logger.info(f"Capture ended. Statistics: {stats_dict}")
            logger.info(f"Total samples received: {sample_count[0]}")

            if stats_dict.get("total_frames", 0) == 0:
                logger.warning("No frames received during capture period. Check:")
                logger.warning("  1. DynoWare RT-150 is powered on and connected")
                logger.warning("  2. JetDrive is enabled in Power Core")
                logger.warning("  3. Network connection is active")
                logger.warning("  4. Firewall allows UDP port 22344")
                with _live_data_lock:
                    if not _live_data.get("error"):
                        _live_data["error"] = (
                            "No data frames received. Check dyno connection and JetDrive settings."
                        )
            elif stats_dict.get("non_provider_frames", 0) > 0:
                logger.warning(
                    f"Received {stats_dict['non_provider_frames']} frames from other providers"
                )

            if sample_count[0] == 0 and stats_dict.get("total_frames", 0) > 0:
                logger.warning(
                    "Frames received but no valid samples parsed. Provider ID may not match."
                )
                with _live_data_lock:
                    if not _live_data.get("error"):
                        _live_data["error"] = (
                            f"Received frames but no samples. Provider ID: 0x{provider.provider_id:04X}"
                        )
            elif sample_count[0] > 0:
                logger.info(
                    f"Successfully received {sample_count[0]} samples from provider"
                )

        except Exception as e:
            logger.error(f"Error during data capture: {e}", exc_info=True)
            with _live_data_lock:
                _live_data["error"] = f"Capture error: {str(e)}"
        finally:
            check_task.cancel()
            try:
                loop.run_until_complete(check_task)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Live capture loop error: {e}", exc_info=True)
        with _live_data_lock:
            _live_data["channels"] = {}
            _live_data["last_update"] = datetime.now().isoformat()
            _live_data["error"] = str(e)
    finally:
        # Clean up the event loop
        try:
            pending = asyncio.all_tasks(loop)
            if pending:
                for task in pending:
                    task.cancel()
                try:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                except Exception:
                    pass
        except Exception:
            pass

        try:
            loop.close()
        except Exception:
            pass

        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass

        logger.info("Live capture loop ended")


@jetdrive_bp.route("/hardware/live/start", methods=["POST"])
def start_live_capture():
    """Start live data capture."""
    global _live_data

    with _live_data_lock:
        if _live_data["capturing"]:
            return jsonify({"status": "already_capturing"})

        _live_data["capturing"] = True
        _live_data["channels"] = {}

    thread = threading.Thread(target=_live_capture_loop, daemon=True)
    thread.start()

    return jsonify({"status": "started"})


@jetdrive_bp.route("/hardware/live/stop", methods=["POST"])
def stop_live_capture():
    """Stop live data capture."""
    global _live_data

    with _live_data_lock:
        _live_data["capturing"] = False

    return jsonify({"status": "stopped"})


@jetdrive_bp.route("/hardware/live/data", methods=["GET"])
def get_live_data():
    """Get current live channel data.

    This endpoint is exempt from rate limiting to support real-time polling
    at 100-250ms intervals for live dyno data visualization.
    
    Note: Rate limit exemption is handled by conditional limiter in app.py.
    The default rate limit (1200/minute) is sufficient for multiple pollers.
    """
    global _live_data

    # Check if simulator is active first
    if _is_simulator_active():
        from api.services.dyno_simulator import get_simulator

        sim = get_simulator()
        channels = sim.get_channels()
        state = sim.get_state().value
        return jsonify(
            {
                "capturing": True,
                "simulated": True,
                "sim_state": state,
                "last_update": datetime.now().isoformat(),
                "channels": channels,
                "channel_count": len(channels),
            }
        )

    def _get_value(channels_dict: dict[str, Any], keys: list[str]) -> float | None:
        for k in keys:
            v = channels_dict.get(k)
            if isinstance(v, dict) and "value" in v:
                try:
                    return float(v.get("value"))
                except Exception:
                    continue
        return None

    with _live_data_lock:
        # Copy so we can safely augment without racing the capture thread
        channels: dict[str, Any] = dict(_live_data.get("channels", {}) or {})
        capturing = _live_data.get("capturing", False)
        error = _live_data.get("error")
        last_update = _live_data.get("last_update")

    # Check if data is stale (older than 10 seconds)
    is_stale = False
    if last_update:
        try:
            last_update_dt = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
            age_seconds = (
                datetime.now() - last_update_dt.replace(tzinfo=None)
            ).total_seconds()
            if age_seconds > 10:
                is_stale = True
                if not error:
                    error = f"Data is stale (last update {age_seconds:.1f}s ago)"
        except Exception:
            pass

    # If the hardware stream doesn't broadcast Horsepower/Torque, compute them from Force + RPM
    try:
        from api.config import get_config

        # Channel IDs from Power Core: ID 39=Digital RPM 1, ID 9=Engine RPM, ID 36=Force Drum 1, ID 32=Force
        rpm = _get_value(channels, ["Digital RPM 1", "Engine RPM", "RPM", "chan_39", "chan_9"])
        force = _get_value(channels, ["Force Drum 1", "Force", "Force 1", "chan_36", "chan_32", "chan_34"])

        if rpm is not None and force is not None and rpm > 0:
            cfg = get_config().dyno
            # During throttle lift / coastdown, Force Drum can go negative (engine braking),
            # which would otherwise produce 0 HP due to guardrails in calculate_hp_from_force.
            # For live display, use magnitude so the trace doesn't instantly flatline.
            force_mag = abs(float(force))
            hp = cfg.calculate_hp_from_force(force_mag, rpm)
            tq = cfg.calculate_torque_from_force(force_mag)
            # Only add if not already provided by hardware
            channels.setdefault("Horsepower", {"value": hp})
            channels.setdefault("Torque", {"value": tq})
    except Exception:
        pass

    # Sanitize channel values - replace Infinity/NaN with None (valid JSON)
    import math
    for ch_name, ch_data in channels.items():
        if isinstance(ch_data, dict) and "value" in ch_data:
            val = ch_data["value"]
            if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
                ch_data["value"] = None  # Replace invalid floats with null

    response = {
        "capturing": capturing,
        "simulated": False,
        "last_update": _live_data.get("last_update"),
        "channels": channels,
        "channel_count": len(channels),
        "is_stale": is_stale,
    }

    if error:
        response["error"] = error

    return jsonify(response)


@jetdrive_bp.route("/hardware/live/debug", methods=["GET"])
def get_live_debug():
    """Get debug information about live capture status."""
    global _live_data

    import asyncio
    import socket

    from api.services.jetdrive_client import JetDriveConfig, discover_providers

    with _live_data_lock:
        capturing = _live_data.get("capturing", False)
        channels = dict(_live_data.get("channels", {}) or {})
        last_update = _live_data.get("last_update")
        error = _live_data.get("error")

    # Try to discover providers
    config = JetDriveConfig.from_env()
    providers = []
    discovery_error = None

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            providers = loop.run_until_complete(discover_providers(config, timeout=5.0))
        finally:
            try:
                loop.close()
            except Exception:
                pass
    except Exception as e:
        discovery_error = str(e)
        logger.error(f"Provider discovery error: {e}", exc_info=True)

    # Test multicast socket binding
    socket_test = {"success": False, "error": None}
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_sock.bind((config.iface, config.port))
        mreq = socket.inet_aton(config.multicast_group) + socket.inet_aton(
            config.iface or "0.0.0.0"
        )
        test_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        test_sock.close()
        socket_test = {"success": True, "error": None}
    except Exception as e:
        socket_test = {"success": False, "error": str(e)}
        logger.error(f"Socket test error: {e}", exc_info=True)

    # Calculate data freshness
    data_age = None
    if last_update:
        try:
            last_update_dt = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
            data_age = (
                datetime.now() - last_update_dt.replace(tzinfo=None)
            ).total_seconds()
        except Exception:
            pass

    # Get network interfaces
    interfaces = []
    try:
        import socket as sock_module

        hostname = sock_module.gethostname()
        local_ip = sock_module.gethostbyname(hostname)
        interfaces.append({"name": "default", "ip": local_ip})
    except Exception:
        pass

    return jsonify(
        {
            "capturing": capturing,
            "channels_received": len(channels),
            "last_update": last_update,
            "data_age_seconds": data_age,
            "error": error,
            "provider_count": len(providers),
            "providers": [
                {
                    "id": f"0x{p.provider_id:04X}",
                    "name": p.name,
                    "host": p.host,
                    "port": p.port,
                    "channels": len(p.channels),
                }
                for p in providers
            ],
            "discovery_error": discovery_error,
            "socket_test": socket_test,
            "config": {
                "multicast_group": config.multicast_group,
                "port": config.port,
                "iface": config.iface,
            },
            "troubleshooting": {
                "check_multicast_group": f"Verify DynoWare RT-150 is broadcasting to {config.multicast_group}:{config.port}",
                "check_network": "Ensure both devices are on the same network subnet",
                "check_firewall": "Windows Firewall must allow UDP port 22344 inbound",
                "check_jetdrive": "Verify JetDrive is enabled in Power Core software",
                "check_power": "Ensure DynoWare RT-150 is powered on and connected",
                "try_interface": f"Try setting JETDRIVE_IFACE to your computer's IP address (not 0.0.0.0)",
            },
        }
    )


@jetdrive_bp.route("/hardware/live/health", methods=["GET"])
def get_live_health():
    """Get comprehensive data health status for ingestion monitoring.

    Returns health metrics expected by the frontend IngestionHealthPanel.
    """
    global _live_data

    with _live_data_lock:
        channels = dict(_live_data.get("channels", {}) or {})
        capturing = _live_data.get("capturing", False)
        last_update = _live_data.get("last_update")

    # Calculate health metrics
    total_channels = len(channels)
    healthy_channels = 0
    channel_health: dict[str, Any] = {}

    now = datetime.now()

    for name, data in channels.items():
        # Determine channel health based on freshness
        if isinstance(data, dict):
            value = data.get("value")
            updated_at = data.get("updated_at")

            # Check staleness (consider stale if older than 5 seconds)
            age_seconds = 0
            health = "healthy"
            if updated_at:
                try:
                    if isinstance(updated_at, str):
                        updated_dt = datetime.fromisoformat(
                            updated_at.replace("Z", "+00:00")
                        )
                        age_seconds = (
                            now - updated_dt.replace(tzinfo=None)
                        ).total_seconds()
                    else:
                        age_seconds = (now - updated_at).total_seconds()

                    if age_seconds > 10:
                        health = "stale"
                    elif age_seconds > 5:
                        health = "warning"
                    else:
                        health = "healthy"
                        healthy_channels += 1
                except Exception:
                    health = "unknown"
            else:
                # No timestamp, assume healthy if capturing
                if capturing:
                    health = "healthy"
                    healthy_channels += 1
                else:
                    health = "unknown"

            # Sanitize Infinity/NaN values for valid JSON
            import math
            safe_value = value
            if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
                safe_value = None

            channel_health[name] = {
                "health": health,
                "value": safe_value,
                "age_seconds": age_seconds,
                "rate_hz": data.get("rate_hz", 0),
            }
        else:
            # Sanitize raw values too
            import math
            safe_data = data
            if isinstance(data, float) and (math.isinf(data) or math.isnan(data)):
                safe_data = None

            channel_health[name] = {
                "health": "unknown",
                "value": safe_data,
                "age_seconds": 0,
                "rate_hz": 0,
            }

    # Determine overall health
    if not capturing:
        overall_health = "unknown"
        health_reason = "Live capture not active"
    elif total_channels == 0:
        overall_health = "unknown"
        health_reason = "No channels detected"
    elif healthy_channels == total_channels:
        overall_health = "healthy"
        health_reason = "All channels healthy"
    elif healthy_channels > total_channels * 0.5:
        overall_health = "warning"
        health_reason = f"{total_channels - healthy_channels} channels degraded"
    else:
        overall_health = "critical"
        health_reason = f"Most channels unhealthy ({healthy_channels}/{total_channels})"

    return jsonify(
        {
            "overall_health": overall_health,
            "health_reason": health_reason,
            "healthy_channels": healthy_channels,
            "total_channels": total_channels,
            "channels": channel_health,
            "frame_stats": {
                "total_frames": _live_data.get("frame_count", 0),
                "dropped_frames": _live_data.get("dropped_frames", 0),
                "drop_rate_percent": 0.0,
            },
            "timestamp": now.timestamp(),
        }
    )


@jetdrive_bp.route("/hardware/live/health/summary", methods=["GET"])
def get_live_health_summary():
    """Get quick channel summary for lightweight polling."""
    global _live_data

    with _live_data_lock:
        channels = dict(_live_data.get("channels", {}) or {})

    now = datetime.now()
    summary: list[dict[str, Any]] = []

    for name, data in channels.items():
        if isinstance(data, dict):
            value = data.get("value", 0)
            updated_at = data.get("updated_at")
            age_seconds = 0

            if updated_at:
                try:
                    if isinstance(updated_at, str):
                        updated_dt = datetime.fromisoformat(
                            updated_at.replace("Z", "+00:00")
                        )
                        age_seconds = (
                            now - updated_dt.replace(tzinfo=None)
                        ).total_seconds()
                except Exception:
                    pass

            health = (
                "healthy"
                if age_seconds < 5
                else ("warning" if age_seconds < 10 else "stale")
            )

            # Sanitize Infinity/NaN for valid JSON
            import math
            safe_value = value if isinstance(value, (int, float)) else 0
            if isinstance(safe_value, float) and (math.isinf(safe_value) or math.isnan(safe_value)):
                safe_value = 0

            summary.append(
                {
                    "name": name,
                    "id": hash(name) & 0xFFFF,  # Generate a pseudo-ID from name
                    "health": health,
                    "value": safe_value,
                    "age_seconds": age_seconds,
                    "rate_hz": data.get("rate_hz", 0),
                }
            )

    return jsonify(
        {
            "channels": summary,
            "timestamp": now.timestamp(),
        }
    )


# =============================================================================
# Innovate Wideband AFR (DLG-1 / LC-2)
# =============================================================================

# Note: This is intentionally kept separate from the JetDrive UDP capture loop.
# The Innovate devices connect via local serial/USB and are polled/streamed via
# dedicated endpoints used by the Wideband tab in the frontend.

_innovate_lock = threading.Lock()
_innovate_client: Any | None = None
_innovate_port: str | None = None
_innovate_device_type: str | None = None
_innovate_last_error: str | None = None
_innovate_last_samples: dict[int, Any] = {}
_innovate_last_sample_at: float | None = (
    None  # wall clock (time.time()) of last sample received
)


def _innovate_parse_device_type(device_type: Any) -> str:
    """Normalize device_type input to one of: 'DLG-1', 'LC-2', 'AUTO'."""
    if not isinstance(device_type, str):
        return "AUTO"
    s = device_type.strip().upper().replace("_", "-")
    if s in {"DLG-1", "DLG1"}:
        return "DLG-1"
    if s in {"LC-2", "LC2"}:
        return "LC-2"
    return "AUTO"


def _innovate_on_sample(sample: Any) -> None:
    """Streaming callback from InnovateClient; caches latest samples for status endpoint."""
    global _innovate_last_samples, _innovate_last_sample_at
    try:
        ch = int(getattr(sample, "channel", 1))
    except Exception:
        ch = 1
    with _innovate_lock:
        _innovate_last_samples[ch] = sample
        _innovate_last_sample_at = time.time()


@jetdrive_bp.route("/innovate/ports", methods=["GET"])
def innovate_list_ports():
    """List available serial ports for Innovate devices."""
    try:
        from api.services.innovate_client import list_available_ports

        ports = list_available_ports() or []
        simplified = []
        for p in ports:
            if not isinstance(p, dict):
                continue
            port = p.get("port")
            if not isinstance(port, str) or not port:
                continue
            desc = p.get("description") if isinstance(p.get("description"), str) else ""
            simplified.append({"port": port, "description": desc})

        return jsonify({"success": True, "ports": simplified})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc), "ports": []}), 500


@jetdrive_bp.route("/innovate/connect", methods=["POST"])
def innovate_connect():
    """Connect to an Innovate device (DLG-1/LC-2) and start background streaming."""
    global _innovate_client, _innovate_port, _innovate_device_type, _innovate_last_error
    global _innovate_last_samples, _innovate_last_sample_at

    body = request.get_json(silent=True) or {}
    port = body.get("port")
    if not isinstance(port, str) or not port.strip():
        return (
            jsonify({"success": False, "connected": False, "error": "Missing 'port'"}),
            400,
        )
    port = port.strip()

    dev_type_norm = _innovate_parse_device_type(body.get("device_type"))

    # Always reset cached state on connect attempt
    with _innovate_lock:
        _innovate_last_samples = {}
        _innovate_last_sample_at = None
        _innovate_last_error = None

    try:
        from api.services.innovate_client import InnovateClient, InnovateDeviceType

        dev_enum = InnovateDeviceType.AUTO
        if dev_type_norm == "DLG-1":
            dev_enum = InnovateDeviceType.DLG1
        elif dev_type_norm == "LC-2":
            dev_enum = InnovateDeviceType.LC2

        # Replace any existing client
        with _innovate_lock:
            old = _innovate_client
            _innovate_client = None
            _innovate_port = None
            _innovate_device_type = None
        if old is not None:
            try:
                old.disconnect()
            except Exception:
                pass

        client = InnovateClient(port=port, device_type=dev_enum)
        ok = client.connect()
        if not ok:
            detail = getattr(client, "last_error", None)
            msg = f"Failed to connect to {port}"
            if isinstance(detail, str) and detail.strip():
                msg = f"{msg}: {detail.strip()}"
            with _innovate_lock:
                _innovate_last_error = msg
            return (
                jsonify(
                    {
                        "success": False,
                        "connected": False,
                        "error": msg,
                    }
                ),
                200,
            )

        # Start streaming in the background to continuously update latest samples
        started = False
        try:
            started = bool(client.start_streaming(_innovate_on_sample))
        except Exception as exc:
            # Connection can still be valid even if streaming didn't start.
            logger.warning("Innovate streaming start failed: %s", exc)

        with _innovate_lock:
            _innovate_client = client
            _innovate_port = port
            _innovate_device_type = dev_enum.value
            _innovate_last_error = None

        return jsonify(
            {
                "success": True,
                "connected": True,
                "port": port,
                "device_type": dev_enum.value,
                "streaming": started,
            }
        )

    except ImportError as exc:
        # Most commonly: pyserial missing
        with _innovate_lock:
            _innovate_last_error = str(exc)
        return jsonify({"success": False, "connected": False, "error": str(exc)}), 500
    except Exception as exc:
        with _innovate_lock:
            _innovate_last_error = str(exc)
        return jsonify({"success": False, "connected": False, "error": str(exc)}), 500


@jetdrive_bp.route("/innovate/disconnect", methods=["POST"])
def innovate_disconnect():
    """Disconnect the active Innovate device (if any)."""
    global _innovate_client, _innovate_port, _innovate_device_type, _innovate_last_error
    global _innovate_last_samples, _innovate_last_sample_at

    with _innovate_lock:
        client = _innovate_client
        _innovate_client = None
        _innovate_port = None
        _innovate_device_type = None
        _innovate_last_samples = {}
        _innovate_last_sample_at = None
        _innovate_last_error = None

    if client is not None:
        try:
            client.disconnect()
        except Exception:
            pass

    return jsonify({"success": True})


@jetdrive_bp.route("/innovate/status", methods=["GET"])
def innovate_status():
    """Return connection + latest sample status for the Innovate device."""
    with _innovate_lock:
        client = _innovate_client
        port = _innovate_port
        device_type = _innovate_device_type
        last_error = _innovate_last_error
        samples = dict(_innovate_last_samples)
        last_sample_at = _innovate_last_sample_at

    connected = bool(client is not None and getattr(client, "connected", False))
    # "running" means the stream loop is active; "streaming" means we saw data recently.
    running = bool(client is not None and getattr(client, "running", False))

    now = time.time()
    streaming = bool(
        connected
        and running
        and last_sample_at is not None
        and (now - float(last_sample_at)) < 2.0
    )

    samples_out: dict[str, Any] = {}
    for ch, s in samples.items():
        try:
            afr = float(getattr(s, "afr", 0.0))
        except Exception:
            afr = 0.0
        try:
            lam = getattr(s, "lambda_value", None)
            lam = float(lam) if lam is not None else None
        except Exception:
            lam = None
        try:
            ts = float(getattr(s, "timestamp", 0.0))
        except Exception:
            ts = 0.0
        samples_out[f"channel_{ch}"] = {"afr": afr, "lambda": lam, "timestamp": ts}

    return jsonify(
        {
            "success": True,
            "connected": connected,
            "streaming": streaming,
            "has_samples": len(samples_out) > 0,
            "port": port,
            "device_type": device_type,
            "error": last_error,
            "samples": samples_out,
        }
    )


# =============================================================================
# Hardware validation (RT-150 network + config parameters)
# =============================================================================


def _load_rt150_config() -> dict[str, Any]:
    """Load RT-150 reference configuration JSON from config folder."""
    cfg_path = get_project_root() / "config" / "dynoware_rt150.json"
    try:
        with cfg_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load RT-150 config at {cfg_path}: {exc}"
        ) from exc


@jetdrive_bp.route("/hardware/validate", methods=["GET"])
def validate_hardware():
    """Validate RT-150 network reachability and config parameters.

    Returns basic checks of the JSON reference config vs environment, and attempts a
    brief JetDrive provider discovery to verify multicast reachability on the expected port.
    """
    warnings: list[str] = []

    # Load reference JSON
    try:
        rt150 = _load_rt150_config()
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    # Pull current env-derived config
    try:
        from api.config import get_config

        env_cfg = get_config().dyno
    except Exception as exc:
        logger.error("Failed to read env config in /hardware/validate", exc_info=True)
        return jsonify({"ok": False, "error": "Failed to read environment config"}), 500

    # Compare key parameters
    ref_ip = (rt150.get("network") or {}).get("ip_address")
    ref_port = (rt150.get("network") or {}).get("jetdrive_port")

    if ref_ip and env_cfg.ip_address and str(ref_ip) != str(env_cfg.ip_address):
        warnings.append(f"IP mismatch: reference {ref_ip} vs env {env_cfg.ip_address}")
    if (
        ref_port
        and env_cfg.jetdrive_port
        and int(ref_port) != int(env_cfg.jetdrive_port)
    ):
        warnings.append(
            f"Port mismatch: reference {ref_port} vs env {env_cfg.jetdrive_port}"
        )

    # Attempt rapid multicast discovery on the configured port
    providers_info: list[dict[str, Any]] = []
    matched_provider = False
    try:
        from api.services.jetdrive_client import JetDriveConfig, discover_providers

        cfg = JetDriveConfig.from_env()
        # Prefer reference port if set
        if isinstance(ref_port, int):
            cfg.port = ref_port

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            providers = loop.run_until_complete(discover_providers(cfg, timeout=1.5))
        finally:
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass

        for p in providers:
            hostsame = bool(ref_ip) and str(p.host) == str(ref_ip)
            if hostsame:
                matched_provider = True
            providers_info.append(
                {
                    "provider_id": p.provider_id,
                    "name": p.name,
                    "host": p.host,
                    "port": p.port,
                    "channels": len(p.channels or {}),
                    "matches_expected_ip": hostsame,
                }
            )
    except Exception as exc:
        logger.warning("Discovery error in /hardware/validate", exc_info=True)
        warnings.append("Discovery error")

    result = {
        "ok": True,
        "reference": {
            "ip_address": ref_ip,
            "jetdrive_port": ref_port,
            "drum1": (rt150.get("drums") or {}).get("drum1"),
        },
        "environment": {
            "ip_address": env_cfg.ip_address,
            "jetdrive_port": env_cfg.jetdrive_port,
            "drum1": {
                "serial": env_cfg.drum1_serial,
                "mass_slugs": env_cfg.drum1_mass_slugs,
                "circumference_ft": env_cfg.drum1_circumference_ft,
                "tabs": env_cfg.drum1_tabs,
            },
        },
        "network": {
            "providers_found": len(providers_info),
            "matched_expected_ip": matched_provider,
            "providers": providers_info,
        },
        "warnings": warnings,
    }
    return jsonify(result)


@jetdrive_bp.route("/hardware/heartbeat", methods=["GET"])
def hardware_heartbeat():
    """Lightweight discovery-based heartbeat to confirm UDP responsiveness.

    Uses JetDrive provider discovery as a proxy for a ping, returning
    the number of providers and their hosts. This validates that:
      - UDP 22344 is bindable
      - Multicast join succeeds
      - Providers are actively broadcasting
    """
    try:
        from api.services.jetdrive_client import JetDriveConfig, discover_providers

        cfg = JetDriveConfig.from_env()
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            providers = loop.run_until_complete(discover_providers(cfg, timeout=1.0))
        finally:
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass

        return jsonify(
            {
                "ok": True,
                "providers": [
                    {
                        "id": p.provider_id,
                        "host": p.host,
                        "name": p.name,
                        "port": p.port,
                    }
                    for p in providers
                ],
                "count": len(providers),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@jetdrive_bp.route("/hardware/connect", methods=["POST"])
def connect_hardware():
    """Attempt to discover JetDrive providers and mark connection state."""
    try:
        from api.services.jetdrive_client import JetDriveConfig, discover_providers

        cfg = JetDriveConfig.from_env()
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            providers = loop.run_until_complete(discover_providers(cfg, timeout=2.0))
        finally:
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass

        return jsonify(
            {
                "success": True,
                "connected": len(providers) > 0,
                "providers": [
                    {
                        "id": p.provider_id,
                        "host": p.host,
                        "name": p.name,
                        "port": p.port,
                    }
                    for p in providers
                ],
                "count": len(providers),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@jetdrive_bp.route("/hardware/start", methods=["POST"])
def start_hardware_stream():
    """Alias for /hardware/live/start to simplify clients."""
    try:
        return start_live_capture()
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@jetdrive_bp.route("/hardware/stop", methods=["POST"])
def stop_hardware_stream():
    """Alias for /hardware/live/stop to simplify clients."""
    try:
        return stop_live_capture()
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@jetdrive_bp.route("/hardware/status", methods=["GET"])
def hardware_status():
    """Composite status of live capture and a quick discovery snapshot."""
    try:
        from api.services.jetdrive_client import JetDriveConfig, discover_providers

        cfg = JetDriveConfig.from_env()
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            providers = loop.run_until_complete(discover_providers(cfg, timeout=1.0))
        finally:
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass
    except Exception:
        providers = []

    with _live_data_lock:
        capturing = bool(_live_data.get("capturing"))
        last_update = _live_data.get("last_update")
        channel_count = len(_live_data.get("channels", {}))

    return jsonify(
        {
            "connected": len(providers) > 0,
            "providers": [
                {"id": p.provider_id, "host": p.host, "name": p.name, "port": p.port}
                for p in providers
            ],
            "live": {
                "capturing": capturing,
                "last_update": last_update,
                "channel_count": channel_count,
            },
            "timestamp": datetime.now().isoformat(),
        }
    )


@jetdrive_bp.route("/hardware/channels/discover", methods=["GET"])
def discover_channels():
    """
    Discover all available channels with their current values.
    Useful for debugging channel name mismatches.

    Response:
    {
        "success": true,
        "channel_count": 25,
        "channels": [
            {
                "id": 42,
                "name": "Digital RPM 1",
                "value": 3500.0,
                "sample_values": [3500, 3501, 3499, ...],
                "value_range": {"min": 0, "max": 8000},
                "suggested_config": {...}
            },
            ...
        ]
    }
    """
    try:
        # Check if simulator is active first
        if _is_simulator_active():
            from api.services.dyno_simulator import get_simulator

            sim = get_simulator()
            channels_data = sim.get_channels()
        else:
            global _live_data
            with _live_data_lock:
                channels_data = _live_data.get("channels", {})

        if not channels_data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "No channel data available. Start live capture first.",
                        "channel_count": 0,
                        "channels": [],
                    }
                ),
                404,
            )

        # Build channel discovery info
        channels = []
        for name, ch in channels_data.items():
            channel = (
                ch if isinstance(ch, dict) else {"value": ch, "id": 0, "name": name}
            )

            # Get recent values (if available in history)
            sample_values = []
            value_range = {"min": None, "max": None}

            # Suggest config based on channel name patterns and value ranges
            name_lower = name.lower()
            value = channel.get("value", 0)

            suggested_config = {
                "label": name.replace("chan_", "Channel ").replace("_", " "),
                "units": "",
                "min": 0,
                "max": 100,
                "decimals": 2,
                "color": "#888",
            }

            # Suggest units based on name patterns FIRST, then fall back to value ranges
            # Priority 1: Keyword-based detection (most reliable)
            keyword_matched = False

            if "rpm" in name_lower or "speed" in name_lower:
                suggested_config = {
                    "label": "RPM",
                    "units": "rpm",
                    "min": 0,
                    "max": 8000,
                    "decimals": 0,
                    "color": "#4ade80",
                }
                keyword_matched = True
            elif "afr" in name_lower or "air/fuel" in name_lower or "a/f" in name_lower:
                suggested_config = {
                    "label": "AFR",
                    "units": ":1",
                    "min": 10,
                    "max": 18,
                    "decimals": 2,
                    "color": "#f472b6",
                }
                keyword_matched = True
            elif "lambda" in name_lower:
                suggested_config = {
                    "label": "Lambda",
                    "units": "λ",
                    "min": 0.5,
                    "max": 2.0,
                    "decimals": 2,
                    "color": "#f472b6",
                }
                keyword_matched = True
            elif "force" in name_lower or "load" in name_lower:
                suggested_config = {
                    "label": "Force",
                    "units": "lbs",
                    "min": 0,
                    "max": 500,
                    "decimals": 1,
                    "color": "#4ade80",
                }
                keyword_matched = True
            elif "map" in name_lower or "manifold" in name_lower:
                suggested_config = {
                    "label": "MAP",
                    "units": "kPa",
                    "min": 0,
                    "max": 105,
                    "decimals": 1,
                    "color": "#06b6d4",
                }
                keyword_matched = True
            elif (
                "temp" in name_lower
                or "iat" in name_lower
                or "ect" in name_lower
                or "coolant" in name_lower
            ):
                suggested_config = {
                    "label": "Temperature",
                    "units": "°C",
                    "min": 0,
                    "max": 150,
                    "decimals": 1,
                    "color": "#f59e0b",
                }
                keyword_matched = True
            elif "tps" in name_lower or "throttle" in name_lower:
                suggested_config = {
                    "label": "Throttle",
                    "units": "%",
                    "min": 0,
                    "max": 100,
                    "decimals": 1,
                    "color": "#8b5cf6",
                }
                keyword_matched = True
            elif "volt" in name_lower or "battery" in name_lower:
                suggested_config = {
                    "label": "Voltage",
                    "units": "V",
                    "min": 0,
                    "max": 16,
                    "decimals": 2,
                    "color": "#eab308",
                }
                keyword_matched = True
            elif (
                "hp" in name_lower
                or "horsepower" in name_lower
                or "power" in name_lower
            ):
                suggested_config = {
                    "label": "Horsepower",
                    "units": "HP",
                    "min": 0,
                    "max": 500,
                    "decimals": 1,
                    "color": "#ef4444",
                }
                keyword_matched = True
            elif "torque" in name_lower:
                suggested_config = {
                    "label": "Torque",
                    "units": "ft-lb",
                    "min": 0,
                    "max": 200,
                    "decimals": 1,
                    "color": "#22c55e",
                }
                keyword_matched = True

            # Priority 2: Value-range based detection (fallback for unknown channels)
            # Use NON-OVERLAPPING ranges to avoid ambiguity
            if not keyword_matched:
                if value > 500 and value < 15000:
                    # High values likely RPM
                    suggested_config = {
                        "label": "RPM",
                        "units": "rpm",
                        "min": 0,
                        "max": 8000,
                        "decimals": 0,
                        "color": "#4ade80",
                    }
                elif value >= 9 and value <= 20:
                    # AFR range (narrower, more specific)
                    suggested_config = {
                        "label": "AFR",
                        "units": ":1",
                        "min": 10,
                        "max": 18,
                        "decimals": 2,
                        "color": "#f472b6",
                    }
                elif value > 0.5 and value < 2.0:
                    # Lambda range (distinct from others)
                    suggested_config = {
                        "label": "Lambda",
                        "units": "λ",
                        "min": 0.5,
                        "max": 2.0,
                        "decimals": 2,
                        "color": "#f472b6",
                    }
                elif value > 50 and value < 250:
                    # Temperature range (above AFR range to avoid overlap)
                    suggested_config = {
                        "label": "Temperature",
                        "units": "°C",
                        "min": 0,
                        "max": 150,
                        "decimals": 1,
                        "color": "#f59e0b",
                    }

            channels.append(
                {
                    "id": channel.get("id", 0),
                    "name": name,
                    "value": channel.get("value", 0),
                    "sample_values": sample_values,
                    "value_range": value_range,
                    "suggested_config": suggested_config,
                }
            )

        return jsonify(
            {
                "success": True,
                "channel_count": len(channels),
                "channels": channels,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error discovering channels: {e}", exc_info=True)
        return (
            jsonify(
                {"success": False, "error": str(e), "channel_count": 0, "channels": []}
            ),
            500,
        )


@jetdrive_bp.route("/hardware/health", methods=["GET"])
def check_hardware_health():
    """Check hardware connection health and latency."""
    try:
        start_time = time.time()

        # Check if we can get live data
        if _is_simulator_active():
            from api.services.dyno_simulator import get_simulator

            sim = get_simulator()
            channels = sim.get_channels()
            latency_ms = (time.time() - start_time) * 1000

            return jsonify(
                {
                    "healthy": True,
                    "connected": True,
                    "simulated": True,
                    "latency_ms": latency_ms,
                    "channel_count": len(channels),
                }
            )

        global _live_data
        with _live_data_lock:
            capturing = _live_data["capturing"]
            channel_count = len(_live_data["channels"])
            latency_ms = (time.time() - start_time) * 1000

        return jsonify(
            {
                "healthy": True,
                "connected": True,
                "simulated": False,
                "capturing": capturing,
                "latency_ms": latency_ms,
                "channel_count": channel_count,
            }
        )

    except Exception as e:
        logger.exception("Health check failed")
        return (
            jsonify({"healthy": False, "connected": False, "error": str(e)}),
            503,
        )


# =============================================================================
# Dyno Simulator Routes
# =============================================================================

# Simulator state
_sim_active: bool = False
_sim_lock = threading.Lock()


def _is_simulator_active() -> bool:
    """Thread-safe check for simulator activity."""
    # Environment override to force simulator fallback (useful for demos/CI)
    try:
        env_override = os.getenv("DYNOAI_SIMULATOR_FALLBACK", "").strip().lower()
        if env_override in {"1", "true", "yes", "on"}:
            return True
    except Exception:
        pass

    with _sim_lock:
        return _sim_active


def _set_simulator_active(state: bool) -> None:
    """Thread-safe update for simulator activity flag."""
    global _sim_active
    with _sim_lock:
        _sim_active = state


@jetdrive_bp.route("/simulator/start", methods=["POST"])
def start_simulator():
    """
    Start the dyno simulator for testing without hardware.

    Request body (optional):
    {
        "profile": "m8_114" | "m8_131" | "twin_cam_103" | "sportbike_600",
        "auto_pull": false,
        "auto_pull_interval": 15.0,
        "virtual_ecu": {
            "enabled": true,
            "scenario": "perfect" | "lean" | "rich" | "custom",
            "ve_error_pct": -10.0,
            "ve_error_std": 5.0,
            "cylinder_balance": "same" | "front_rich" | "rear_rich",
            "barometric_pressure_inhg": 29.92,
            "ambient_temp_f": 75.0
        }
    }
    """
    try:
        from api.services.dyno_simulator import (
            EngineProfile,
            SimulatorConfig,
            reset_simulator,
        )

        data = request.get_json() or {}

        # Get profile
        profile_name = data.get("profile", "m8_114")
        profiles = {
            "m8_114": EngineProfile.m8_114,
            "m8_131": EngineProfile.m8_131,
            "twin_cam_103": EngineProfile.twin_cam_103,
            "sportbike_600": EngineProfile.sportbike_600,
        }

        profile_factory = profiles.get(profile_name)
        if not profile_factory:
            return jsonify({"error": f"Unknown profile: {profile_name}"}), 400

        profile = profile_factory()

        # Build config
        config = SimulatorConfig(
            profile=profile,
            auto_pull=data.get("auto_pull", False),
            auto_pull_interval_sec=data.get("auto_pull_interval", 15.0),
        )

        # Virtual ECU configuration
        virtual_ecu = None
        ecu_config = data.get("virtual_ecu")
        if ecu_config and ecu_config.get("enabled", False):
            from api.services.virtual_ecu import (
                VirtualECU,
                create_afr_target_table,
                create_baseline_ve_table,
                create_intentionally_wrong_ve_table,
            )

            # Create baseline VE table
            baseline_ve = create_baseline_ve_table(peak_ve=0.85, peak_rpm=4000)

            # Apply scenario
            scenario = ecu_config.get("scenario", "perfect")
            if scenario == "perfect":
                ve_front = baseline_ve
                ve_rear = baseline_ve
            elif scenario == "lean":
                ve_front = create_intentionally_wrong_ve_table(
                    baseline_ve, error_pct_mean=-10.0, error_pct_std=5.0, seed=42
                )
                ve_rear = ve_front
            elif scenario == "rich":
                ve_front = create_intentionally_wrong_ve_table(
                    baseline_ve, error_pct_mean=10.0, error_pct_std=5.0, seed=42
                )
                ve_rear = ve_front
            elif scenario == "custom":
                ve_error = ecu_config.get("ve_error_pct", -10.0)
                ve_std = ecu_config.get("ve_error_std", 5.0)
                ve_front = create_intentionally_wrong_ve_table(
                    baseline_ve, error_pct_mean=ve_error, error_pct_std=ve_std, seed=42
                )
                ve_rear = ve_front
            else:
                ve_front = baseline_ve
                ve_rear = baseline_ve

            # Apply cylinder balance
            cylinder_balance = ecu_config.get("cylinder_balance", "same")
            if cylinder_balance == "front_rich":
                ve_front = ve_front * 1.05
            elif cylinder_balance == "rear_rich":
                ve_rear = ve_rear * 1.05

            # Create AFR target table
            afr_table = create_afr_target_table(cruise_afr=14.0, wot_afr=12.5)

            # Create Virtual ECU
            virtual_ecu = VirtualECU(
                ve_table_front=ve_front,
                ve_table_rear=ve_rear,
                afr_target_table=afr_table,
                barometric_pressure_inhg=ecu_config.get(
                    "barometric_pressure_inhg", 29.92
                ),
                ambient_temp_f=ecu_config.get("ambient_temp_f", 75.0),
            )

            logger.info(
                f"Virtual ECU enabled: scenario={scenario}, ve_error={ecu_config.get('ve_error_pct', 0)}"
            )

        # Reset and start simulator
        sim = reset_simulator(config, virtual_ecu=virtual_ecu)
        sim.start()
        _set_simulator_active(True)

        return jsonify(
            {
                "success": True,
                "virtual_ecu_enabled": virtual_ecu is not None,
                "status": "started",
                "profile": {
                    "name": profile.name,
                    "family": profile.family,
                    "displacement_ci": profile.displacement_ci,
                    "idle_rpm": profile.idle_rpm,
                    "redline_rpm": profile.redline_rpm,
                    "max_hp": profile.max_hp,
                    "max_tq": profile.max_tq,
                },
                "auto_pull": config.auto_pull,
            }
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to start simulator: {error_msg}", exc_info=True)

        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to start simulator: {error_msg}",
                    # Never return stack traces to clients (logged server-side via exc_info=True)
                }
            ),
            500,
        )


@jetdrive_bp.route("/simulator/stop", methods=["POST"])
def stop_simulator():
    """Stop the dyno simulator."""
    from api.services.dyno_simulator import get_simulator

    sim = get_simulator()
    sim.stop()
    _set_simulator_active(False)

    return jsonify({"success": True, "status": "stopped"})


@jetdrive_bp.route("/simulator/status", methods=["GET"])
def get_simulator_status():
    """Get current simulator status."""
    if not _is_simulator_active():
        return jsonify(
            {
                "active": False,
                "state": "stopped",
            }
        )

    from api.services.dyno_simulator import get_simulator

    try:
        sim = get_simulator()
        state = sim.get_state()
        channels = sim.get_channels()
    except Exception as e:
        # If simulator errors, don't deactivate - just return last known state
        logger.error(f"Error getting simulator status: {e}")
        return jsonify(
            {
                "active": True,  # Keep showing as active
                "state": "idle",  # Safe fallback
                "error": str(e),
            }
        )

    # Extract key values
    rpm = channels.get("Digital RPM 1", {}).get("value", 0)
    hp = channels.get("Horsepower", {}).get("value", 0)
    tq = channels.get("Torque", {}).get("value", 0)
    afr = channels.get("Air/Fuel Ratio 1", {}).get("value", 0)
    tps = channels.get("TPS", {}).get("value", 0)

    return jsonify(
        {
            "active": True,
            "state": state.value,
            "profile": sim.config.profile.name,
            "current": {
                "rpm": round(rpm, 0),
                "horsepower": round(hp, 1),
                "torque": round(tq, 1),
                "afr": round(afr, 2),
                "tps": round(tps, 1),
            },
        }
    )


@jetdrive_bp.route("/simulator/pull", methods=["POST"])
def trigger_pull():
    """Manually trigger a WOT pull in the simulator."""
    if not _is_simulator_active():
        return jsonify({"error": "Simulator not running"}), 400

    from api.services.dyno_simulator import SimState, get_simulator

    sim = get_simulator()
    current_state = sim.get_state()

    if current_state != SimState.IDLE:
        return (
            jsonify(
                {
                    "error": f"Cannot start pull in state: {current_state.value}",
                    "current_state": current_state.value,
                }
            ),
            400,
        )

    sim.trigger_pull()

    return jsonify(
        {
            "success": True,
            "status": "pull_started",
            "state": "pull",
        }
    )


@jetdrive_bp.route("/simulator/throttle", methods=["POST"])
def set_simulator_throttle():
    """
    Set simulator throttle target (TPS %) for manual operator control.

    Body:
      { "tps": 0-100 }
    """
    if not _is_simulator_active():
        return jsonify({"error": "Simulator not running"}), 400

    data = request.get_json() or {}
    try:
        tps = float(data.get("tps"))
    except Exception:
        return jsonify({"error": "Missing or invalid 'tps' (0-100)"}), 400

    if not (0.0 <= tps <= 100.0):
        return jsonify({"error": "'tps' must be between 0 and 100"}), 400

    from api.services.dyno_simulator import get_simulator

    sim = get_simulator()
    # Only allow manual throttle while simulator is running.
    sim.physics.tps_target = tps

    return jsonify({"success": True, "tps_target": tps})


@jetdrive_bp.route("/simulator/pull-data", methods=["GET"])
def get_pull_data():
    """Get data from the last completed pull."""
    if not _is_simulator_active():
        return jsonify({"error": "Simulator not running"}), 400

    from api.services.dyno_simulator import get_simulator

    sim = get_simulator()
    sim_state = sim.get_state()
    data = sim.get_pull_data()

    logger.debug(
        f"Pull data request: state={sim_state.value}, data_points={len(data) if data else 0}"
    )

    if not data or len(data) == 0:
        return jsonify(
            {
                "success": True,
                "has_data": False,
                "data": [],
                "state": sim_state.value,
            }
        )

    # Calculate peak values
    peak_hp = max((d.get("Horsepower", 0) for d in data), default=0)
    peak_tq = max((d.get("Torque", 0) for d in data), default=0)

    # Find peak RPMs
    hp_peak_rpm = next(
        (d["Engine RPM"] for d in data if d.get("Horsepower", 0) == peak_hp), 0
    )
    tq_peak_rpm = next(
        (d["Engine RPM"] for d in data if d.get("Torque", 0) == peak_tq), 0
    )

    return jsonify(
        {
            "success": True,
            "has_data": True,
            "points": len(data),
            "peak_hp": round(peak_hp, 1),
            "hp_peak_rpm": round(hp_peak_rpm, 0),
            "peak_tq": round(peak_tq, 1),
            "tq_peak_rpm": round(tq_peak_rpm, 0),
            "state": sim_state.value,
            "data": data,
        }
    )


@jetdrive_bp.route("/simulator/save-pull", methods=["POST"])
def save_simulator_pull():
    """
    Save the last simulator pull data to a CSV file.

    Request body:
    {
        "run_id": "my_run"  // Optional, will generate if not provided
    }

    Returns:
    {
        "success": true,
        "run_id": "sim_20231215_123456",
        "csv_path": "uploads/sim_20231215_123456.csv",
        "points": 160
    }
    """
    if not _is_simulator_active():
        return jsonify({"error": "Simulator not running"}), 400

    import csv
    from datetime import datetime

    from api.services.dyno_simulator import get_simulator

    sim = get_simulator()
    data = sim.get_pull_data()

    if not data:
        return jsonify({"error": "No pull data available"}), 400

    # Get or generate run_id
    request_data = request.get_json() or {}
    try:
        run_id = sanitize_run_id(
            request_data.get("run_id")
            or f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Save to uploads directory
    project_root = get_project_root()
    uploads_dir = project_root / "uploads"
    uploads_dir.mkdir(exist_ok=True)

    csv_filename = f"{run_id}.csv"
    csv_path = uploads_dir / csv_filename

    # Write CSV with proper column names for analysis
    try:
        with open(csv_path, "w", newline="") as f:
            if data:
                # Map simulator columns to expected analysis columns
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

                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for i, row in enumerate(data):
                    # Convert simulator format to analysis format
                    # Use average of front/rear AFR
                    afr_avg = (
                        row.get("AFR Meas F", 14.7) + row.get("AFR Meas R", 14.7)
                    ) / 2

                    writer.writerow(
                        {
                            "timestamp_ms": i * 50,  # 20Hz = 50ms per sample
                            "RPM": row.get("Engine RPM", 0),
                            "Torque": row.get("Torque", 0),
                            "Horsepower": row.get("Horsepower", 0),
                            "AFR": afr_avg,
                            "MAP_kPa": row.get("MAP kPa", 0),
                            "TPS": row.get("TPS", 0),
                            "IAT": row.get("IAT F", 85),
                        }
                    )

        return jsonify(
            {
                "success": True,
                "run_id": run_id,
                "csv_path": str(csv_path),
                "points": len(data),
            }
        )

    except Exception as e:
        return jsonify({"error": f"Failed to save CSV: {str(e)}"}), 500


@jetdrive_bp.route("/simulator/profiles", methods=["GET"])
def get_profiles():
    """Get available engine profiles for simulation."""
    from api.services.dyno_simulator import EngineProfile

    profiles = {
        "m8_114": EngineProfile.m8_114(),
        "m8_131": EngineProfile.m8_131(),
        "twin_cam_103": EngineProfile.twin_cam_103(),
        "sportbike_600": EngineProfile.sportbike_600(),
    }

    result = []
    for key, profile in profiles.items():
        result.append(
            {
                "id": key,
                "name": profile.name,
                "family": profile.family,
                "displacement_ci": profile.displacement_ci,
                "idle_rpm": profile.idle_rpm,
                "redline_rpm": profile.redline_rpm,
                "max_hp": profile.max_hp,
                "hp_peak_rpm": profile.hp_peak_rpm,
                "max_tq": profile.max_tq,
                "tq_peak_rpm": profile.tq_peak_rpm,
            }
        )

    return jsonify({"profiles": result})
