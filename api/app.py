#!/usr/bin/env python3
"""
DynoAI Flask API Server
Provides REST API endpoints for the React frontend to interact with the Python toolkit
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

from api.auth import require_api_key
from api.config import get_config
from api.docs import init_swagger
from api.errors import (
    AnalysisError,
    FileNotAllowedError,
    NotFoundError,
    ValidationError,
    register_error_handlers,
    with_error_handling,
)
from api.metrics import init_metrics, record_analysis, record_file_upload

load_dotenv()  # Load environment variables from .env if present
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Enable CORS for all API routes

# Initialize Swagger UI for API documentation (available at /api/docs)
try:
    swagger = init_swagger(app)
except Exception as e:
    print(f"[!] Warning: Swagger UI disabled due to: {e}")

# Initialize Prometheus metrics (available at /metrics)
try:
    metrics = init_metrics(app)
except Exception as e:
    print(f"[!] Warning: Prometheus metrics disabled: {e}")

# Initialize database
try:
    from api.services.database import init_database, test_connection

    if test_connection():
        init_database()
        print("[+] Database initialized successfully")
    else:
        print("[!] Warning: Database connection test failed")
except Exception as e:
    print(f"[!] Warning: Database initialization skipped: {e}")

# Register Admin UI blueprint (available at /admin)
try:
    from api.admin import admin_bp

    app.register_blueprint(admin_bp)
    print("[+] Admin UI registered at /admin")
except Exception as e:
    print(f"[!] Warning: Admin UI disabled: {e}")

# Initialize rate limiter (optional - graceful degradation if not available)
limiter = None
try:
    from api.rate_limit import init_rate_limiter

    limiter = init_rate_limiter(app)
except Exception as e:  # pragma: no cover
    print(f"[!] Warning: Could not initialize rate limiter: {e}")

# Initialize request ID middleware for request tracing
try:
    from api.middleware import init_request_id_middleware

    init_request_id_middleware(app)
except Exception as e:  # pragma: no cover
    print(f"[!] Warning: Could not initialize request ID middleware: {e}")

# Load environment variables from .env if present
load_dotenv()

# Import centralized configuration and error handling

# Get application configuration
config = get_config()


def rate_limit(limit_string: str):
    """Decorator that applies rate limiting if limiter is available."""

    def decorator(f):
        if limiter is not None:
            return limiter.limit(limit_string)(f)
        return f

    return decorator


# Register health blueprint for detailed health checks (liveness/readiness probes)
try:
    from api.health import health_bp

    app.register_blueprint(health_bp)
except Exception as e:  # pragma: no cover
    print(f"[!] Warning: Could not register health blueprint: {e}")

# Register reliability agent for system monitoring and circuit breakers
try:
    from api.reliability_integration import init_reliability

    reliability_agent = init_reliability(app)
    print("[+] Reliability agent successfully initialized!")
except Exception as e:  # pragma: no cover
    import traceback

    print(f"[!] Warning: Could not initialize reliability agent: {e}")
    traceback.print_exc()

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

    # Initialize Jetstream poller with config from environment
    jetstream_config = JetstreamConfig(
        api_url=os.environ.get("JETSTREAM_API_URL", ""),
        api_key=os.environ.get("JETSTREAM_API_KEY", ""),
        poll_interval_seconds=int(os.environ.get("JETSTREAM_POLL_INTERVAL", "30")),
        auto_process=os.environ.get("JETSTREAM_AUTO_PROCESS", "true").lower() == "true",
        enabled=os.environ.get("JETSTREAM_ENABLED", "false").lower() == "true",
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

# Configuration - use absolute paths from project root
PROJECT_ROOT = Path(__file__).parent.parent
UPLOAD_FOLDER = PROJECT_ROOT / "uploads"
OUTPUT_FOLDER = PROJECT_ROOT / "outputs"
ALLOWED_EXTENSIONS = {"csv", "txt"}

UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max file size
# Register Timeline blueprint (VE Table Time Machine)
try:
    from api.routes.timeline import timeline_bp

    app.register_blueprint(timeline_bp)
except Exception as e:  # pragma: no cover
    print(f"[!] Warning: Could not initialize Timeline integration: {e}")

# Register Tuning Wizards blueprint (Decel Pop, Stage Config, Cam Presets, Heat Soak)
try:
    from api.routes.wizards import wizards_bp

    app.register_blueprint(wizards_bp)
except Exception as e:  # pragma: no cover
    print(f"[!] Warning: Could not initialize Tuning Wizards: {e}")

# Register JetDrive Auto-Tune blueprint
try:
    from api.routes.jetdrive import jetdrive_bp

    app.register_blueprint(jetdrive_bp)
except Exception as e:  # pragma: no cover
    print(f"[!] Warning: Could not initialize JetDrive Auto-Tune: {e}")

# Register Transient Fuel Compensation blueprint
try:
    from api.routes.transient import transient_bp

    app.register_blueprint(transient_bp)
except Exception as e:  # pragma: no cover
    print(f"[!] Warning: Could not initialize Transient Fuel Compensation: {e}")

# Virtual Tuning (Closed-Loop Orchestrator)
try:
    from api.routes.virtual_tune import virtual_tune_bp

    app.register_blueprint(virtual_tune_bp)
except Exception as e:  # pragma: no cover
    print(f"[!] Warning: Could not initialize Virtual Tuning: {e}")

# Register Power Core Integration blueprint
try:
    from api.routes.powercore import powercore_bp

    app.register_blueprint(powercore_bp)
    print("[+] Power Core integration registered at /api/powercore")
except Exception as e:  # pragma: no cover
    print(f"[!] Warning: Could not initialize Power Core integration: {e}")

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
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def run_dyno_analysis(
    csv_path: Path,
    output_dir: Path,
    run_id: str,
    params: dict = None,
    progress_queue: Queue = None,
) -> dict:
    """
    Run the DynoAI analysis toolkit on a CSV file with progress tracking

    Args:
        csv_path: Path to input CSV file
        output_dir: Directory to write outputs
        run_id: Unique identifier for this analysis run
        params: Optional dict of tuning parameters
        progress_queue: Optional queue for progress updates

    Returns:
        dict: Manifest data from analysis
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

        # Per-Cylinder Auto-Balancing options
        if params.get("balance_cylinders"):
            cmd.append("--balance-cylinders")
            if "balance_mode" in params:
                cmd.extend(["--balance-mode", str(params["balance_mode"])])
            if "balance_max_correction" in params:
                cmd.extend(
                    ["--balance-max-correction", str(params["balance_max_correction"])]
                )
    else:
        # Default parameters
        cmd.extend(["--clamp", "15", "--smooth_passes", "2"])

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
        raise Exception(f"Analysis failed: {error_details}")

    # Read the manifest file
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        raise Exception("Manifest file not generated")

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
                description=f"Generated VE corrections from {Path(csv_path).name}",
            )
            print("[+] Recorded analysis in session timeline")
    except Exception as e:
        # Don't fail the analysis if timeline logging fails
        print(f"[!] Warning: Could not record timeline event: {e}")

    return manifest


def convert_manifest_to_frontend_format(manifest: dict, run_id: str) -> dict:
    """
    Convert DynoAI manifest format to frontend-expected format

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
            .get("smooth_passes", 2),
        },
    }


@app.route("/api/analyze", methods=["POST"])
@rate_limit("5/minute;20/hour")  # Expensive operation - stricter limits
def analyze():
    """
    Analyze uploaded CSV file (async)

    Expected: multipart/form-data with 'file' field and optional parameters
    Parameters:
        - smoothPasses: int (default: 2)
        - clamp: float (default: 15.0)
        - rearBias: float (default: 0.0)
        - rearRuleDeg: float (default: 2.0)
        - hotExtra: float (default: -1.0)
    Returns: Job ID for tracking progress
    """
    # Check if file is in request
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return (
            jsonify({"error": "Invalid file type. Only CSV and TXT files allowed"}),
            400,
        )

    try:
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

        # Extract cylinder balancing options from form data
        balance_cylinders = _get_bool_form("balanceCylinders", False)
        balance_mode = request.form.get("balanceMode", "equalize")
        balance_max_correction = float(request.form.get("balanceMaxCorrection", "3.0"))

        tuning_options = {
            "decel_management": decel_management,
            "decel_severity": decel_severity,
            "decel_rpm_min": decel_rpm_min,
            "decel_rpm_max": decel_rpm_max,
            "balance_cylinders": balance_cylinders,
            "balance_mode": balance_mode,
            "balance_max_correction": balance_max_correction,
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
                manifest = run_dyno_analysis(
                    upload_path, output_dir, run_id, params, tuning_options
                )
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
                {"runId": run_id, "status": "queued", "message": "Analysis started"}
            ),
            202,
        )

    except Exception as e:
        import logging

        # Record failed analysis
        record_analysis(status="error", source="upload")

        error_msg = str(e)
        print(f"[!] Error in /api/analyze: {error_msg}")
        logger = logging.getLogger(__name__)
        logger.error(f"Error in analyze endpoint: {error_msg}", exc_info=True)
        try:
            return (
                jsonify(
                    {
                        "error": error_msg,
                        # Never return stack traces to clients (logged server-side via exc_info=True)
                    }
                ),
                500,
            )
        except Exception as json_error:
            # If jsonify itself fails, return plain text
            print(f"[!] Failed to create JSON response: {json_error}")
            from flask import Response

            return Response(f"Error: {error_msg}", status=500, mimetype="text/plain")


@app.route("/api/status/<run_id>", methods=["GET"])
@rate_limit("120/minute")  # Read-only - permissive
def get_status(run_id):
    """
    Get the status of an analysis job

    Args:
        run_id: Unique run identifier

    Returns:
        JSON with current job status and progress
    """
    if run_id not in active_jobs:
        return jsonify({"error": "Job not found"}), 404

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
@rate_limit("60/minute")  # Standard - moderate limit for downloads
def download_file(run_id, filename):
    """
    Download a specific output file

    Args:
        run_id: Unique run identifier
        filename: Name of the file to download

    Returns:
        File download
    """
    try:
        # Sanitize inputs
        run_id = secure_filename(run_id)
        filename = secure_filename(filename)

        file_path = None

        # Try Jetstream runs folder first
        try:
            from api.services.run_manager import get_run_manager

            manager = get_run_manager()
            run_output_dir = manager.get_run_output_dir(run_id)
            if run_output_dir and run_output_dir.exists():
                jetstream_file = run_output_dir / filename
                if jetstream_file.exists():
                    file_path = jetstream_file
        except Exception:
            pass

        # Fall back to outputs folder
        if not file_path:
            file_path = OUTPUT_FOLDER / run_id / filename

        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404

        return send_file(file_path, as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ve-data/<run_id>", methods=["GET"])
@rate_limit("120/minute")  # Read-only - permissive
def get_ve_data(run_id):
    """
    Get VE table data for 3D visualization

    Args:
        run_id: Unique run identifier

    Returns:
        JSON with VE data in format expected by frontend
    """
    try:
        run_id = secure_filename(run_id)
        ve_delta_file = None

        # Try Jetstream run manager first
        try:
            from api.services.run_manager import get_run_manager

            manager = get_run_manager()
            run_output_dir = manager.get_run_output_dir(run_id)
            print(f"[DEBUG] Jetstream run output dir: {run_output_dir}")
            if run_output_dir and run_output_dir.exists():
                ve_delta_file = run_output_dir / "VE_Correction_Delta_DYNO.csv"
                print(
                    f"[DEBUG] VE file path: {ve_delta_file}, exists: {ve_delta_file.exists()}"
                )
        except Exception as e:
            print(f"[DEBUG] Exception in Jetstream path: {e}")
            pass

        # Fall back to old outputs folder if not found
        if not ve_delta_file or not ve_delta_file.exists():
            output_dir = OUTPUT_FOLDER / run_id
            ve_delta_file = output_dir / "VE_Correction_Delta_DYNO.csv"

        if not ve_delta_file.exists():
            return jsonify({"error": "VE data not found"}), 404

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

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/runs", methods=["GET"])
@rate_limit("120/minute")  # Read-only - permissive
def list_runs():
    """List all available analysis runs"""
    try:
        runs = []
        for run_dir in OUTPUT_FOLDER.iterdir():
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

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/diagnostics/<run_id>", methods=["GET"])
@rate_limit("120/minute")  # Read-only - permissive
def get_diagnostics(run_id):
    """
    Get diagnostics and anomaly detection results

    Args:
        run_id: Unique run identifier

    Returns:
        JSON with diagnostics data
    """
    try:
        run_id = secure_filename(run_id)
        output_dir = OUTPUT_FOLDER / run_id

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
            return jsonify({"error": "Diagnostics data not found"}), 404

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/confidence/<run_id>", methods=["GET"])
@rate_limit("120/minute")  # Read-only - permissive
def get_confidence_report(run_id):
    """
    Get tune confidence scoring report

    Args:
        run_id: Unique run identifier

    Returns:
        JSON with confidence report data
    """
    try:
        run_id = secure_filename(run_id)
        output_dir = OUTPUT_FOLDER / run_id

        # Look for confidence report file
        confidence_file = output_dir / "ConfidenceReport.json"

        if not confidence_file.exists():
            return jsonify({"error": "Confidence report not found"}), 404

        with open(confidence_file, "r") as f:
            confidence_data = json.load(f)

        return jsonify(confidence_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/runs/<run_id>/session-replay", methods=["GET"])
@rate_limit("120/minute")  # Read-only - permissive
def get_session_replay(run_id):
    """
    Get session replay log with all decisions made during tuning

    Args:
        run_id: Unique run identifier

    Returns:
        JSON with session replay data
    """
    try:
        run_id = secure_filename(run_id)

        # Try Jetstream runs folder first
        session_replay_file = None
        try:
            from api.services.run_manager import get_run_manager

            manager = get_run_manager()
            run_output_dir = manager.get_run_output_dir(run_id)
            if run_output_dir and run_output_dir.exists():
                jetstream_file = run_output_dir / "session_replay.json"
                if jetstream_file.exists():
                    session_replay_file = jetstream_file
        except Exception:
            pass

        # Fall back to outputs folder
        if not session_replay_file:
            output_dir = OUTPUT_FOLDER / run_id
            session_replay_file = output_dir / "session_replay.json"

        if not session_replay_file.exists():
            return jsonify({"error": "Session replay not found"}), 404

        with open(session_replay_file, "r", encoding="utf-8") as f:
            replay_data = json.load(f)

        return jsonify(replay_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/coverage/<run_id>", methods=["GET"])
@rate_limit("120/minute")  # Read-only - permissive
def get_coverage(run_id):
    """
    Get coverage data for heatmap visualization

    Args:
        run_id: Unique run identifier

    Returns:
        JSON with coverage data for front and rear cylinders
    """
    try:
        run_id = secure_filename(run_id)
        output_dir = OUTPUT_FOLDER / run_id

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
            return jsonify({"error": "Coverage data not found"}), 404

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# VE Apply/Rollback Endpoints (Time Machine)
# =============================================================================


@app.route("/api/apply", methods=["POST"])
@require_api_key  # Protect state-changing VE operations
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
    from dynoai.core.ve_operations import VEApply

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
        # Prevent path traversal: only allow selecting a file from the project's `tables/` dir.
        # (Clients may send a full path; we intentionally discard directories and keep only the filename.)
        base_ve_name = secure_filename(Path(str(base_ve_path)).name)
        if not base_ve_name:
            raise ValidationError("Invalid base_ve_path")

        base_ve_path = PROJECT_ROOT / "tables" / base_ve_name
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
        dry_run=False,
    )

    # Record in session timeline
    timeline_event_id = None
    try:
        logger = SessionLogger(run_dir)
        event = logger.record_apply(
            ve_before_path=ve_backup_path,
            ve_after_path=ve_output_path,
            apply_metadata=apply_metadata,
            description=f"Applied VE corrections (max ±{apply_metadata.get('max_adjust_pct', 7)}%)",
        )
        timeline_event_id = event["id"]
        print(f"[+] Recorded apply event in timeline: {timeline_event_id}")
    except Exception as e:
        print(f"[!] Warning: Could not record timeline event: {e}")

    return (
        jsonify(
            {
                "success": True,
                "applied_at": apply_metadata.get("applied_at_utc"),
                "cells_modified": apply_metadata.get("cells_modified", 0),
                "output_path": str(ve_output_path),
                "timeline_event_id": timeline_event_id,
            }
        ),
        200,
    )


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
    from dynoai.core.ve_operations import VERollback

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
        dry_run=False,
    )

    # Record in session timeline
    timeline_event_id = None
    try:
        logger = SessionLogger(run_dir)
        event = logger.record_rollback(
            ve_before_path=ve_before_rollback,
            ve_after_path=ve_restored_path,
            rollback_info=rollback_info,
            description="Rolled back VE corrections to previous state",
        )
        timeline_event_id = event["id"]
        print(f"[+] Recorded rollback event in timeline: {timeline_event_id}")
    except Exception as e:
        print(f"[!] Warning: Could not record timeline event: {e}")

    return (
        jsonify(
            {
                "success": True,
                "rolled_back_at": rollback_info.get("rolled_back_at_utc"),
                "restored_path": str(ve_restored_path),
                "timeline_event_id": timeline_event_id,
            }
        ),
        200,
    )


def print_startup_banner():
    """Print startup information banner."""
    print("\n" + "=" * 60)
    print("[*] DynoAI API Server")
    print("=" * 60)
    print(f"[>] Upload folder: {UPLOAD_FOLDER.absolute()}")
    print(f"[>] Output folder: {OUTPUT_FOLDER.absolute()}")
    print(f"[>] Python: {sys.executable}")
    rate_limit_status = "ENABLED" if limiter else "DISABLED"
    print(f"[>] Rate limiting: {rate_limit_status}")
    print("\n[*] Server running on http://localhost:5001")
    print("[*] Admin Dashboard:   http://localhost:5001/admin")
    print("[*] API Documentation: http://localhost:5001/api/docs")
    print("\n[*] Available endpoints:")
    print("  GET  /api/health              - Detailed health check")
    print("  GET  /api/health/live         - Liveness probe")
    print("  GET  /api/health/ready        - Readiness probe")
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
    print("\n[*] Tuning Wizard endpoints:")
    print("  GET  /api/wizards/config              - Get all wizard options")
    print("  POST /api/wizards/decel/preview       - Preview decel fix")
    print("  POST /api/wizards/decel/apply         - Apply decel fix (one-click)")
    print("  GET  /api/wizards/stages              - List stage presets")
    print("  GET  /api/wizards/cams                - List cam family presets")
    print("  POST /api/wizards/heat-soak/analyze   - Analyze heat soak")
    print("\n" + "=" * 60 + "\n")

    debug_flag = bool(os.getenv("DYNOAI_DEBUG", "true").lower() == "true")
    app.run(debug=debug_flag, host="0.0.0.0", port=5001, threaded=True)


# Register error handlers at app initialization
# (done once here rather than in deprecated @before_first_request)
register_error_handlers(app)

if __name__ == "__main__":
    print_startup_banner()
elif __name__ == "api.app":
    # Handle case when run as module: python -m api.app
    # Start the server directly when run as a module
    print_startup_banner()
