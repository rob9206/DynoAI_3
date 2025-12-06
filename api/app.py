#!/usr/bin/env python3
"""
DynoAI Flask API Server

Provides REST API endpoints for the React frontend to interact with the Python toolkit.
"""

import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from queue import Queue

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

from api.config import get_config
from api.errors import (
    AnalysisError,
    FileNotAllowedError,
    NotFoundError,
    ValidationError,
    register_error_handlers,
    with_error_handling,
)

# Load environment variables from .env if present
load_dotenv()

# Import centralized configuration and error handling

# Get application configuration
config = get_config()

# Initialize Flask app
app = Flask(__name__)

# Apply configuration
app.config["UPLOAD_FOLDER"] = config.storage.upload_folder
app.config["OUTPUT_FOLDER"] = config.storage.output_folder
app.config["MAX_CONTENT_LENGTH"] = config.storage.max_content_length

# Enable CORS
CORS(app, resources=config.cors.resources)

# Register centralized error handlers
register_error_handlers(app)

# Lazy import/register of xAI blueprint if available
try:
    from dynoai.api.xai_blueprint import xai_bp  # type: ignore

    app.register_blueprint(xai_bp)
except Exception:  # pragma: no cover
    pass

# Register Jetstream blueprint
try:
    from api.jetstream.models import JetstreamConfig
    from api.jetstream.poller import init_poller
    from api.jetstream.stub_data import initialize_stub_data, is_stub_mode_enabled
    from api.routes.jetstream import jetstream_bp

    app.register_blueprint(jetstream_bp, url_prefix="/api/jetstream")

    # Initialize Jetstream poller with config from centralized config
    jetstream_config = JetstreamConfig(
        api_url=config.jetstream.api_url,
        api_key=config.jetstream.api_key,
        poll_interval_seconds=config.jetstream.poll_interval_seconds,
        auto_process=config.jetstream.auto_process,
        enabled=config.jetstream.enabled,
    )
    if is_stub_mode_enabled():
        initialize_stub_data()
        poller = None
    else:
        poller = init_poller(jetstream_config)
        if jetstream_config.enabled:
            poller.start()
except Exception as e:  # pragma: no cover
    print(f"[!] Warning: Could not initialize Jetstream integration: {e}")

# Register Timeline blueprint (VE Table Time Machine)
try:
    from api.routes.timeline import timeline_bp

    app.register_blueprint(timeline_bp)
except Exception as e:  # pragma: no cover
    print(f"[!] Warning: Could not initialize Timeline integration: {e}")

# Store active analysis jobs
active_jobs = {}


# Helper functions for form data parsing
def _get_bool_form(key: str, default: bool = False) -> bool:
    """Parse boolean value from form data."""
    value = request.form.get(key, str(default)).lower()
    return value in ("true", "1", "yes")


def _get_int_form(key: str, default: int) -> int:
    """Parse integer value from form data."""
    try:
        return int(request.form.get(key, default))
    except (ValueError, TypeError):
        return default


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in config.storage.allowed_extensions
    )


def run_dyno_analysis(
    csv_path: Path,
    output_dir: Path,
    run_id: str,
    params: dict = None,
    progress_queue: Queue = None,
) -> dict:
    """
    Run the DynoAI analysis toolkit on a CSV file with progress tracking.

    Args:
        csv_path: Path to input CSV file
        output_dir: Directory to write outputs
        run_id: Unique identifier for this analysis run
        params: Optional dict of tuning parameters
        progress_queue: Optional queue for progress updates

    Returns:
        dict: Manifest data from analysis

    Raises:
        AnalysisError: If analysis fails
    """
    # Ensure we're running from the project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Find Python executable
    venv_python = Path(".venv/Scripts/python.exe")
    if not venv_python.exists():
        venv_python = Path(".venv/bin/python")  # Unix/Mac

    if not venv_python.exists():
        venv_python = Path("python")  # Fallback to system Python

    # Build command with optional parameters
    cmd = [
        str(venv_python),
        "ai_tuner_toolkit_dyno_v1_2.py",
        "--csv",
        str(csv_path),
        "--outdir",
        str(output_dir),
    ]

    # Add optional parameters if provided
    if params:
        if "smooth_passes" in params:
            cmd.extend(["--smooth_passes", str(params["smooth_passes"])])
        if "clamp" in params:
            cmd.extend(["--clamp", str(params["clamp"])])
        if "rear_bias" in params:
            cmd.extend(["--rear_bias", str(params["rear_bias"])])
        if "rear_rule_deg" in params:
            cmd.extend(["--rear_rule_deg", str(params["rear_rule_deg"])])
        if "hot_extra" in params:
            cmd.extend(["--hot_extra", str(params["hot_extra"])])

        # Decel Fuel Management options
        if params.get("decel_management"):
            cmd.append("--decel-management")
            if "decel_severity" in params:
                cmd.extend(["--decel-severity", str(params["decel_severity"])])
            if "decel_rpm_min" in params:
                cmd.extend(["--decel-rpm-min", str(params["decel_rpm_min"])])
            if "decel_rpm_max" in params:
                cmd.extend(["--decel-rpm-max", str(params["decel_rpm_max"])])
    else:
        # Use default parameters from config
        cmd.extend(
            [
                "--clamp",
                str(config.analysis.default_clamp),
                "--smooth_passes",
                str(config.analysis.default_smooth_passes),
            ]
        )

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        # Collect both stdout and stderr for better debugging
        stdout_msg = result.stdout.strip() if result.stdout else ""
        stderr_msg = result.stderr.strip() if result.stderr else "No error output"
        error_details = (
            f"[STDOUT] {stdout_msg}\n[STDERR] {stderr_msg}"
            if stdout_msg
            else f"[ERROR] {stderr_msg}"
        )
        raise AnalysisError(error_details, stage="analysis")

    # Read the manifest file
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        raise AnalysisError("Manifest file not generated", stage="export")

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    # Record analysis in session timeline (Time Machine)
    try:
        from api.services.session_logger import SessionLogger

        # Determine run directory (may be outputs/{run_id} or runs/{run_id})
        run_dir = output_dir.parent if output_dir.name == "output" else output_dir
        logger = SessionLogger(run_dir)

        # Look for VE correction file to snapshot
        ve_correction_path = output_dir / "VE_Correction_Delta_DYNO.csv"
        if ve_correction_path.exists():
            logger.record_analysis(
                correction_path=ve_correction_path,
                manifest=manifest,
                description=f"Generated VE corrections from {Path(csv_path).name}"
            )
            print("[+] Recorded analysis in session timeline")
    except Exception as e:
        # Don't fail the analysis if timeline logging fails
        print(f"[!] Warning: Could not record timeline event: {e}")

    return manifest


def convert_manifest_to_frontend_format(manifest: dict, run_id: str) -> dict:
    """
    Convert DynoAI manifest format to frontend-expected format.

    Args:
        manifest: DynoAI manifest dict
        run_id: Unique run identifier

    Returns:
        dict: Frontend-compatible manifest
    """
    return {
        "runId": run_id,
        "timestamp": manifest.get("timing", {}).get(
            "start", datetime.utcnow().isoformat()
        ),
        "inputFile": manifest.get("input", {}).get("path", "unknown.csv"),
        "rowsProcessed": manifest.get("stats", {}).get("rows_read", 0),
        "correctionsApplied": manifest.get("stats", {}).get("front_accepted", 0)
        + manifest.get("stats", {}).get("rear_accepted", 0),
        "outputFiles": [
            {
                "name": (output.get("name") or Path(output.get("path", "")).name),
                "type": (
                    "VE Table"
                    if "VE" in (output.get("name") or output.get("path", ""))
                    else "Analysis Data"
                ),
                "url": f"/api/download/{run_id}/{Path(output.get('path') or output.get('name', '')).name}",
            }
            for output in manifest.get("outputs", [])
        ],
        "analysisMetrics": {
            "avgCorrection": 2.5,  # Calculate from actual corrections if available
            "maxCorrection": 7.0,
            "targetAFR": 14.7,
            "iterations": manifest.get("config", {})
            .get("args", {})
            .get("smooth_passes", config.analysis.default_smooth_passes),
        },
    }


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify(
        {
            "status": "ok",
            "version": config.version,
            "app": config.app_name,
        }
    )


@app.route("/api/analyze", methods=["POST"])
@with_error_handling
def analyze():
    """
    Analyze uploaded CSV file (async).

    Expected: multipart/form-data with 'file' field and optional parameters.

    Parameters:
        - smoothPasses: int (default: 2)
        - clamp: float (default: 15.0)
        - rearBias: float (default: 0.0)
        - rearRuleDeg: float (default: 2.0)
        - hotExtra: float (default: -1.0)

    Returns:
        Job ID for tracking progress
    """
    # Check if file is in request
    if "file" not in request.files:
        raise ValidationError("No file provided")

    file = request.files["file"]

    if file.filename == "":
        raise ValidationError("No file selected")

    if not allowed_file(file.filename):
        raise FileNotAllowedError(
            file.filename,
            allowed_types=list(config.storage.allowed_extensions),
        )

    # Generate unique run ID
    run_id = str(uuid.uuid4())

    # Save uploaded file
    filename = secure_filename(file.filename)
    upload_path = config.storage.upload_folder / run_id / filename
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[>] Saving uploaded file to: {upload_path}")
    file.save(str(upload_path))

    # Verify file was saved
    if not upload_path.exists():
        raise AnalysisError(f"File upload failed - file not found at {upload_path}")

    file_size = upload_path.stat().st_size
    print(f"[+] File saved successfully ({file_size} bytes)")

    # Create output directory
    output_dir = config.storage.output_folder / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract tuning parameters from form data
    params = {
        "smooth_passes": int(
            request.form.get("smoothPasses", config.analysis.default_smooth_passes)
        ),
        "clamp": float(request.form.get("clamp", config.analysis.default_clamp)),
        "rear_bias": float(
            request.form.get("rearBias", config.analysis.default_rear_bias)
        ),
        "rear_rule_deg": float(
            request.form.get("rearRuleDeg", config.analysis.default_rear_rule_deg)
        ),
        "hot_extra": float(
            request.form.get("hotExtra", config.analysis.default_hot_extra)
        ),
    }

    # Extract decel tuning options from form data
    decel_management = _get_bool_form("decelManagement", False)
    decel_severity = request.form.get("decelSeverity", "medium")
    decel_rpm_min = _get_int_form("decelRpmMin", 1500)
    decel_rpm_max = _get_int_form("decelRpmMax", 5500)

    tuning_options = {
        "decel_management": decel_management,
        "decel_severity": decel_severity,
        "decel_rpm_min": decel_rpm_min,
        "decel_rpm_max": decel_rpm_max,
    }

    # Initialize job tracking
    active_jobs[run_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Starting analysis...",
        "filename": filename,
        "params": params,
        "started_at": datetime.utcnow().isoformat(),
    }

    # Run analysis in background thread
    def run_analysis_thread():
        try:
            active_jobs[run_id]["status"] = "running"
            active_jobs[run_id]["message"] = "Running analysis..."
            manifest = run_dyno_analysis(upload_path, output_dir, run_id, params, tuning_options)
            active_jobs[run_id]["manifest"] = manifest
            active_jobs[run_id]["status"] = "completed"
            active_jobs[run_id]["message"] = "Analysis complete"
        except Exception as e:
            active_jobs[run_id]["status"] = "error"
            active_jobs[run_id]["error"] = str(e)
            active_jobs[run_id]["message"] = f"Error: {str(e)}"

    thread = threading.Thread(target=run_analysis_thread, daemon=True)
    thread.start()

    return (
        jsonify(
            {
                "runId": run_id,
                "status": "queued",
                "message": "Analysis started",
            }
        ),
        202,
    )


@app.route("/api/status/<run_id>", methods=["GET"])
@with_error_handling
def get_status(run_id):
    """
    Get the status of an analysis job.

    Args:
        run_id: Unique run identifier

    Returns:
        JSON with current job status and progress
    """
    if run_id not in active_jobs:
        raise NotFoundError("Job", run_id)

    job = active_jobs[run_id]
    response = {
        "runId": run_id,
        "status": job["status"],
        "progress": job.get("progress", 0),
        "message": job.get("message", ""),
        "filename": job.get("filename", ""),
    }

    if job["status"] == "error":
        response["error"] = job.get("error", "Unknown error")

    if job["status"] == "completed" and "manifest" in job:
        response["manifest"] = convert_manifest_to_frontend_format(
            job["manifest"], run_id
        )

    return jsonify(response), 200


@app.route("/api/download/<run_id>/<filename>", methods=["GET"])
@with_error_handling
def download_file(run_id, filename):
    """
    Download a specific output file.

    Args:
        run_id: Unique run identifier
        filename: Name of the file to download

    Returns:
        File download
    """
    # Sanitize inputs and validate results
    safe_run_id = secure_filename(run_id)
    safe_filename = secure_filename(filename)

    # Validate sanitized values are not empty (secure_filename can return "" for inputs like "...")
    if not safe_run_id:
        raise ValidationError(f"Invalid run_id: {run_id}")
    if not safe_filename:
        raise ValidationError(f"Invalid filename: {filename}")

    file_path = config.storage.output_folder / safe_run_id / safe_filename

    if not file_path.exists():
        raise NotFoundError("File", safe_filename)

    return send_file(file_path, as_attachment=True, download_name=safe_filename)


@app.route("/api/ve-data/<run_id>", methods=["GET"])
@with_error_handling
def get_ve_data(run_id):
    """
    Get VE table data for 3D visualization.

    Args:
        run_id: Unique run identifier

    Returns:
        JSON with VE data in format expected by frontend
    """
    # Sanitize and validate run_id
    safe_run_id = secure_filename(run_id)
    if not safe_run_id:
        raise ValidationError(f"Invalid run_id: {run_id}")

    ve_delta_file = None

    # Try Jetstream run manager first
    try:
        from api.services.run_manager import get_run_manager

        manager = get_run_manager()
        run_output_dir = manager.get_run_output_dir(safe_run_id)
        print(f"[DEBUG] Jetstream run output dir: {run_output_dir}")
        if run_output_dir and run_output_dir.exists():
            ve_delta_file = run_output_dir / "VE_Correction_Delta_DYNO.csv"
            print(
                f"[DEBUG] VE file path: {ve_delta_file}, exists: {ve_delta_file.exists()}"
            )
    except Exception as e:
        print(f"[DEBUG] Exception in Jetstream path: {e}")

    # Fall back to old outputs folder if not found
    if not ve_delta_file or not ve_delta_file.exists():
        output_dir = config.storage.output_folder / safe_run_id
        ve_delta_file = output_dir / "VE_Correction_Delta_DYNO.csv"

    if not ve_delta_file.exists():
        raise NotFoundError("VE data", safe_run_id)

    # Parse VE delta CSV
    import csv

    with open(ve_delta_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)

        # Extract kPa bins from header (skip first "RPM" column)
        load_points = [int(h) for h in header[1:]]

        rpm_points = []
        corrections = []

        for row in reader:
            rpm_points.append(int(row[0]))
            # Remove '+' prefix and convert to float
            corrections.append(
                [float(val.replace("+", "").replace("'", "")) for val in row[1:]]
            )

    # Generate before/after data from corrections
    # Assume baseline VE of 100 for all cells
    baseline_ve = 100.0
    before_data = [[baseline_ve for _ in load_points] for _ in rpm_points]
    after_data = [
        [baseline_ve + corrections[i][j] for j in range(len(load_points))]
        for i in range(len(rpm_points))
    ]

    return (
        jsonify(
            {
                "rpm": rpm_points,
                "load": load_points,
                "corrections": corrections,
                "before": before_data,
                "after": after_data,
            }
        ),
        200,
    )


@app.route("/api/runs", methods=["GET"])
@with_error_handling
def list_runs():
    """List all available analysis runs."""
    runs = []
    for run_dir in config.storage.output_folder.iterdir():
        if run_dir.is_dir():
            manifest_path = run_dir / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                runs.append(
                    {
                        "runId": run_dir.name,
                        "timestamp": manifest.get("timing", {}).get("start"),
                        "inputFile": manifest.get("input", {}).get("path"),
                    }
                )

    return jsonify({"runs": runs}), 200


@app.route("/api/diagnostics/<run_id>", methods=["GET"])
@with_error_handling
def get_diagnostics(run_id):
    """
    Get diagnostics and anomaly detection results.

    Args:
        run_id: Unique run identifier

    Returns:
        JSON with diagnostics data
    """
    # Sanitize and validate run_id
    safe_run_id = secure_filename(run_id)
    if not safe_run_id:
        raise ValidationError(f"Invalid run_id: {run_id}")

    output_dir = config.storage.output_folder / safe_run_id

    # Look for diagnostics files
    diagnostics_file = output_dir / "Diagnostics_Report.txt"
    anomalies_file = output_dir / "Anomaly_Hypotheses.json"

    result = {}

    if diagnostics_file.exists():
        with open(diagnostics_file, "r") as f:
            result["report"] = f.read()

    if anomalies_file.exists():
        with open(anomalies_file, "r") as f:
            result["anomalies"] = json.load(f)

    if not result:
        raise NotFoundError("Diagnostics data", safe_run_id)

    return jsonify(result), 200


@app.route("/api/coverage/<run_id>", methods=["GET"])
@with_error_handling
def get_coverage(run_id):
    """
    Get coverage data for heatmap visualization.

    Args:
        run_id: Unique run identifier

    Returns:
        JSON with coverage data for front and rear cylinders
    """
    # Sanitize and validate run_id
    safe_run_id = secure_filename(run_id)
    if not safe_run_id:
        raise ValidationError(f"Invalid run_id: {run_id}")

    output_dir = config.storage.output_folder / safe_run_id

    # Look for coverage files
    coverage_front = output_dir / "Coverage_Front.csv"
    coverage_rear = output_dir / "Coverage_Rear.csv"

    result = {}

    # Parse coverage CSV files
    import csv

    if coverage_front.exists():
        with open(coverage_front, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            load_points = [int(h) for h in header[1:]]

            rpm_points = []
            coverage_data = []

            for row in reader:
                rpm_points.append(int(row[0]))
                coverage_data.append([int(val) if val else 0 for val in row[1:]])

            result["front"] = {
                "rpm": rpm_points,
                "load": load_points,
                "data": coverage_data,
            }

    if coverage_rear.exists():
        with open(coverage_rear, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            load_points = [int(h) for h in header[1:]]

            rpm_points = []
            coverage_data = []

            for row in reader:
                rpm_points.append(int(row[0]))
                coverage_data.append([int(val) if val else 0 for val in row[1:]])

            result["rear"] = {
                "rpm": rpm_points,
                "load": load_points,
                "data": coverage_data,
            }

    if not result:
        raise NotFoundError("Coverage data", safe_run_id)

    return jsonify(result), 200


# =============================================================================
# VE Apply/Rollback Endpoints (Time Machine)
# =============================================================================


@app.route("/api/apply", methods=["POST"])
@with_error_handling
def apply_ve_corrections():
    """
    Apply VE corrections from an analysis run to a base VE table.

    Request body:
        {
            "run_id": "...",
            "base_ve_path": "path/to/base_ve.csv" (optional, uses default if not provided)
        }

    Returns:
        {
            "success": true,
            "applied_at": "...",
            "cells_modified": N,
            "output_path": "...",
            "timeline_event_id": "..."
        }
    """
    from api.services.session_logger import SessionLogger
    from ve_operations import VEApply

    data = request.get_json()
    if not data or "run_id" not in data:
        raise ValidationError("run_id is required")

    run_id = secure_filename(data["run_id"])
    if not run_id:
        raise ValidationError("Invalid run_id")

    # Find the run directory (check both outputs and runs folders)
    run_dir = None
    output_dir = None

    # Check runs folder first (for Jetstream runs)
    runs_path = config.storage.runs_folder / run_id
    if runs_path.exists():
        run_dir = runs_path
        output_dir = runs_path / "output"
    else:
        # Check outputs folder (for direct uploads)
        outputs_path = config.storage.output_folder / run_id
        if outputs_path.exists():
            run_dir = outputs_path
            output_dir = outputs_path

    if not run_dir or not output_dir:
        raise NotFoundError("Run", run_id)

    # Find VE correction file
    ve_correction_path = output_dir / "VE_Correction_Delta_DYNO.csv"
    if not ve_correction_path.exists():
        raise NotFoundError("VE corrections", run_id)

    # Get base VE path (from request or default)
    base_ve_path = data.get("base_ve_path")
    if base_ve_path:
        base_ve_path = Path(base_ve_path)
        if not base_ve_path.exists():
            raise NotFoundError("Base VE file", str(base_ve_path))
    else:
        # Use default base VE from tables folder
        base_ve_path = Path("tables/FXDLS_Wheelie_VE_Base_Front_fixed.csv")
        if not base_ve_path.exists():
            raise ValidationError("No base VE file specified and default not found")

    # Create output paths
    ve_output_path = output_dir / "VE_Applied.csv"
    ve_backup_path = output_dir / "VE_Before_Apply.csv"

    # Backup the base VE before applying
    import shutil
    shutil.copy2(base_ve_path, ve_backup_path)

    # Apply corrections
    applier = VEApply(max_adjust_pct=7.0)
    apply_metadata = applier.apply(
        base_ve_path=base_ve_path,
        factor_path=ve_correction_path,
        output_path=ve_output_path,
        dry_run=False
    )

    # Record in session timeline
    timeline_event_id = None
    try:
        logger = SessionLogger(run_dir)
        event = logger.record_apply(
            ve_before_path=ve_backup_path,
            ve_after_path=ve_output_path,
            apply_metadata=apply_metadata,
            description=f"Applied VE corrections (max ±{apply_metadata.get('max_adjust_pct', 7)}%)"
        )
        timeline_event_id = event["id"]
        print(f"[+] Recorded apply event in timeline: {timeline_event_id}")
    except Exception as e:
        print(f"[!] Warning: Could not record timeline event: {e}")

    return jsonify({
        "success": True,
        "applied_at": apply_metadata.get("applied_at_utc"),
        "cells_modified": apply_metadata.get("cells_modified", 0),
        "output_path": str(ve_output_path),
        "timeline_event_id": timeline_event_id,
    }), 200


@app.route("/api/rollback", methods=["POST"])
@with_error_handling
def rollback_ve_corrections():
    """
    Rollback VE corrections to restore previous VE table.

    Request body:
        {
            "run_id": "..."
        }

    Returns:
        {
            "success": true,
            "rolled_back_at": "...",
            "restored_path": "...",
            "timeline_event_id": "..."
        }
    """
    from api.services.session_logger import SessionLogger
    from ve_operations import VERollback

    data = request.get_json()
    if not data or "run_id" not in data:
        raise ValidationError("run_id is required")

    run_id = secure_filename(data["run_id"])
    if not run_id:
        raise ValidationError("Invalid run_id")

    # Find the run directory
    run_dir = None
    output_dir = None

    runs_path = config.storage.runs_folder / run_id
    if runs_path.exists():
        run_dir = runs_path
        output_dir = runs_path / "output"
    else:
        outputs_path = config.storage.output_folder / run_id
        if outputs_path.exists():
            run_dir = outputs_path
            output_dir = outputs_path

    if not run_dir or not output_dir:
        raise NotFoundError("Run", run_id)

    # Find the applied VE and metadata
    ve_applied_path = output_dir / "VE_Applied.csv"
    metadata_path = output_dir / "VE_Applied_meta.json"

    if not ve_applied_path.exists():
        raise ValidationError("No VE corrections have been applied to this run")

    if not metadata_path.exists():
        raise ValidationError("Cannot rollback: metadata file not found")

    # Create output path for restored VE
    ve_restored_path = output_dir / "VE_Restored.csv"

    # Backup current state
    ve_before_rollback = output_dir / "VE_Before_Rollback.csv"
    import shutil
    shutil.copy2(ve_applied_path, ve_before_rollback)

    # Perform rollback
    roller = VERollback()
    rollback_info = roller.rollback(
        current_ve_path=ve_applied_path,
        metadata_path=metadata_path,
        output_path=ve_restored_path,
        dry_run=False
    )

    # Record in session timeline
    timeline_event_id = None
    try:
        logger = SessionLogger(run_dir)
        event = logger.record_rollback(
            ve_before_path=ve_before_rollback,
            ve_after_path=ve_restored_path,
            rollback_info=rollback_info,
            description="Rolled back VE corrections to previous state"
        )
        timeline_event_id = event["id"]
        print(f"[+] Recorded rollback event in timeline: {timeline_event_id}")
    except Exception as e:
        print(f"[!] Warning: Could not record timeline event: {e}")

    return jsonify({
        "success": True,
        "rolled_back_at": rollback_info.get("rolled_back_at_utc"),
        "restored_path": str(ve_restored_path),
        "timeline_event_id": timeline_event_id,
    }), 200


def print_startup_banner():
    """Print startup information banner."""
    print("\n" + "=" * 60)
    print(f"[*] {config.app_name} API Server v{config.version}")
    print("=" * 60)
    print(f"[>] Upload folder: {config.storage.upload_folder.absolute()}")
    print(f"[>] Output folder: {config.storage.output_folder.absolute()}")
    print(f"[>] Runs folder: {config.storage.runs_folder.absolute()}")
    print(f"[>] Python: {sys.executable}")
    print(f"\n[*] Server running on http://{config.server.host}:{config.server.port}")
    print("\n[*] Available endpoints:")
    print("  GET  /api/health              - Health check")
    print("  POST /api/analyze             - Upload and analyze CSV (async)")
    print("  GET  /api/status/<run_id>     - Get analysis status")
    print("  GET  /api/download/<run>/<f>  - Download output file")
    print("  GET  /api/ve-data/<run_id>    - Get VE data for visualization")
    print("  GET  /api/runs                - List all runs")
    print("  GET  /api/diagnostics/<id>    - Get diagnostics data")
    print("  GET  /api/coverage/<id>       - Get coverage data")
    print("  POST /api/apply               - Apply VE corrections")
    print("  POST /api/rollback            - Rollback VE corrections")
    print("  POST /api/xai/chat            - Proxy chat to xAI (Grok)")
    print("\n[*] Jetstream endpoints:")
    print("  GET  /api/jetstream/config    - Get Jetstream configuration")
    print("  PUT  /api/jetstream/config    - Update Jetstream configuration")
    print("  GET  /api/jetstream/status    - Get Jetstream poller status")
    print("  GET  /api/jetstream/runs      - List Jetstream runs")
    print("  GET  /api/jetstream/runs/<id> - Get specific run details")
    print("  POST /api/jetstream/sync      - Force immediate poll")
    print("  GET  /api/jetstream/progress/<id> - SSE progress stream")
    print("\n[*] Timeline endpoints (VE Table Time Machine):")
    print("  GET  /api/timeline/<run_id>           - Get session timeline")
    print("  GET  /api/timeline/<run_id>/replay/<n>- Replay step N")
    print("  GET  /api/timeline/<run_id>/snapshots/<id> - Get snapshot")
    print("  GET  /api/timeline/<run_id>/diff      - Compute diff")
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    print_startup_banner()
    app.run(
        debug=config.server.debug,
        host=config.server.host,
        port=config.server.port,
        threaded=config.server.threaded,
    )
