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

load_dotenv()  # Load environment variables from .env if present
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Enable CORS for all API routes

# Lazy import/register of xAI blueprint if available
try:
    from dynoai.api.xai_blueprint import xai_bp  # type: ignore

    app.register_blueprint(xai_bp)
except Exception:  # pragma: no cover
    pass

# Register Jetstream blueprint
try:
    from jetstream.models import JetstreamConfig
    from jetstream.poller import init_poller
    from jetstream.stub_data import initialize_stub_data, is_stub_mode_enabled
    from routes.jetstream import jetstream_bp

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

# Register Baseline blueprint
try:
    from routes.baseline import baseline_bp
    app.register_blueprint(baseline_bp)
except Exception as e:  # pragma: no cover
    print(f"[!] Warning: Could not initialize Baseline integration: {e}")

# Configuration
UPLOAD_FOLDER = Path("uploads")
OUTPUT_FOLDER = Path("outputs")
ALLOWED_EXTENSIONS = {"csv", "txt"}

UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max file size

# Store active analysis jobs
active_jobs = {}


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


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "version": "1.0.0"})


@app.route("/api/analyze", methods=["POST"])
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
        upload_path = UPLOAD_FOLDER / run_id / filename
        upload_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"[>] Saving uploaded file to: {upload_path}")
        file.save(str(upload_path))

        # Verify file was saved
        if not upload_path.exists():
            raise Exception(f"File upload failed - file not found at {upload_path}")

        file_size = upload_path.stat().st_size
        print(f"[+] File saved successfully ({file_size} bytes)")

        # Create output directory
        output_dir = OUTPUT_FOLDER / run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Extract tuning parameters from form data
        params = {
            "smooth_passes": int(request.form.get("smoothPasses", 2)),
            "clamp": float(request.form.get("clamp", 15.0)),
            "rear_bias": float(request.form.get("rearBias", 0.0)),
            "rear_rule_deg": float(request.form.get("rearRuleDeg", 2.0)),
            "hot_extra": float(request.form.get("hotExtra", -1.0)),
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
                manifest = run_dyno_analysis(upload_path, output_dir, run_id, params)
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
        return jsonify({"error": str(e)}), 500


@app.route("/api/status/<run_id>", methods=["GET"])
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

        file_path = OUTPUT_FOLDER / run_id / filename

        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404

        return send_file(file_path, as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ve-data/<run_id>", methods=["GET"])
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
            from services.run_manager import get_run_manager

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

        return (
            jsonify(
                {
                    "rpm": rpm_points,
                    "load": load_points,
                    "corrections": corrections,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/runs", methods=["GET"])
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


@app.route("/api/coverage/<run_id>", methods=["GET"])
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


if __name__ == "__main__":
    # See docs/test_failures_baseline.md - Issue #2: Use ASCII for Windows compatibility
    print("\n" + "=" * 60)
    print("[*] DynoAI API Server")
    print("=" * 60)
    print(f"[>] Upload folder: {Path(app.config['UPLOAD_FOLDER']).absolute()}")
    print(f"[>] Output folder: {Path(app.config['OUTPUT_FOLDER']).absolute()}")
    print(f"[>] Python: {sys.executable}")
    print("\n[*] Server running on http://localhost:5001")
    print("\n[*] Available endpoints:")
    print("  GET  /api/health              - Health check")
    print("  POST /api/analyze             - Upload and analyze CSV (async)")
    print("  GET  /api/status/<run_id>     - Get analysis status")
    print("  GET  /api/download/<run>/<f>  - Download output file")
    print("  GET  /api/ve-data/<run_id>    - Get VE data for visualization")
    print("  GET  /api/runs                - List all runs")
    print("  GET  /api/diagnostics/<id>    - Get diagnostics data")
    print("  GET  /api/coverage/<id>       - Get coverage data")
    print("  POST /api/xai/chat            - Proxy chat to xAI (Grok)")
    print("\n[*] Baseline endpoints:")
    print("  POST /api/baseline/generate   - Generate One-Pull Baseline")
    print("  POST /api/baseline/preview    - Preview baseline (no save)")
    print("\n[*] Jetstream endpoints:")
    print("  GET  /api/jetstream/config    - Get Jetstream configuration")
    print("  PUT  /api/jetstream/config    - Update Jetstream configuration")
    print("  GET  /api/jetstream/status    - Get Jetstream poller status")
    print("  GET  /api/jetstream/runs      - List Jetstream runs")
    print("  GET  /api/jetstream/runs/<id> - Get specific run details")
    print("  POST /api/jetstream/sync      - Force immediate poll")
    print("  GET  /api/jetstream/progress/<id> - SSE progress stream")
    print("\n" + "=" * 60 + "\n")

    debug_flag = bool(os.getenv("DYNOAI_DEBUG", "true").lower() == "true")
    app.run(debug=debug_flag, host="0.0.0.0", port=5001, threaded=True)
