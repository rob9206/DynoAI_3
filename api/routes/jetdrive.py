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
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from api.rate_limit import get_limiter
from api.services.autotune_workflow import AutoTuneWorkflow, DataSource

logger = logging.getLogger(__name__)

jetdrive_bp = Blueprint("jetdrive", __name__, url_prefix="/api/jetdrive")

# Singleton workflow instance for unified analysis
_workflow: AutoTuneWorkflow | None = None


def get_workflow() -> AutoTuneWorkflow:
    """Get or create the unified workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = AutoTuneWorkflow()
    return _workflow


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent.parent


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

    runs = []
    if runs_dir.exists():
        for run_dir in sorted(runs_dir.iterdir(), reverse=True):
            if run_dir.is_dir():
                manifest_path = run_dir / "manifest.json"
                if manifest_path.exists():
                    try:
                        with open(manifest_path) as f:
                            manifest = json.load(f)
                        runs.append(
                            {
                                "run_id": run_dir.name,
                                "timestamp": manifest.get("timestamp", ""),
                                "peak_hp": manifest.get("analysis", {}).get(
                                    "peak_hp", 0
                                ),
                                "peak_tq": manifest.get("analysis", {}).get(
                                    "peak_tq", 0
                                ),
                                "status": manifest.get("analysis", {}).get(
                                    "overall_status", ""
                                ),
                            }
                        )
                    except Exception:
                        runs.append(
                            {
                                "run_id": run_dir.name,
                                "timestamp": "",
                                "status": "unknown",
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
    data = request.get_json()
    if not data or "run_id" not in data:
        return jsonify({"error": "Missing 'run_id' in request body"}), 400

    try:
        run_id = sanitize_run_id(data["run_id"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

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
        return jsonify({"error": "Autotune script not found"}), 500

    # Build command
    cmd = [sys.executable, str(script_path), "--run-id", run_id]

    if mode == "simulate":
        cmd.append("--simulate")
    elif mode == "csv":
        if not csv_path:
            return jsonify({"error": "Missing 'csv_path' for CSV mode"}), 400
        cmd.extend(["--csv", csv_path])
    elif mode == "simulator_pull":
        # Save simulator pull data first
        logger.info(f"Analyzing with simulator_pull mode for run_id={run_id}")

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
        from datetime import datetime

        from api.services.dyno_simulator import SimState, get_simulator

        sim = get_simulator()
        sim_state = sim.get_state()
        logger.info(f"Simulator state: {sim_state.value}")

        pull_data = sim.get_pull_data()
        logger.info(f"Pull data retrieved: {len(pull_data) if pull_data else 0} points")

        if not pull_data:
            logger.warning("No pull data available from simulator")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "No simulator pull data available. Please run a pull first by clicking 'Trigger Pull' in the simulator controls.",
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

        return jsonify(
            {
                "success": True,
                "run_id": run_id,
                "mode": mode,  # Include mode so frontend knows what was analyzed
                "output_dir": str(output_dir),
                "analysis": manifest.get("analysis", {}),
                "grid": manifest.get("grid", {}),
                "ve_grid": ve_grid,
                "outputs": manifest.get("outputs", {}),
            }
        )

    except subprocess.TimeoutExpired:
        # Restore simulator active state if it was active before
        if was_simulator_active:
            _set_simulator_active(True)
        return jsonify({"success": False, "error": "Analysis timed out"}), 500
    except Exception as e:
        # Restore simulator active state if it was active before
        if was_simulator_active:
            _set_simulator_active(True)
        return jsonify({"success": False, "error": str(e)}), 500


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
                            values.append(None)
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
    """Background thread to capture live channel data."""
    global _live_data

    from api.services.jetdrive_client import (
        JetDriveConfig,
        JetDriveSample,
        discover_providers,
    )

    config = JetDriveConfig.from_env()

    while True:
        with _live_data_lock:
            if not _live_data["capturing"]:
                break

        # Create a fresh event loop per iteration (thread-local). Ensure it is
        # always closed, even if discovery/capture throws.
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)

            # Discover and capture a quick sample
            providers = loop.run_until_complete(discover_providers(config, timeout=2.0))

            if providers:
                provider = providers[0]

                # Quick capture for 1 second
                samples: list[JetDriveSample] = []

                def on_sample(s: JetDriveSample):
                    samples.append(s)

                async def capture_brief():
                    from api.services.jetdrive_client import subscribe

                    # Create after loop is running to avoid RuntimeError: no running event loop
                    stop_event = asyncio.Event()

                    # Schedule stop
                    async def stop_after():
                        await asyncio.sleep(1.0)
                        stop_event.set()

                    asyncio.create_task(stop_after())
                    await subscribe(
                        provider, [], on_sample, config=config, stop_event=stop_event
                    )

                loop.run_until_complete(capture_brief())

                # Update live data with latest values
                channel_values = {}
                for s in samples:
                    channel_values[s.channel_name] = {
                        "id": s.channel_id,
                        "name": s.channel_name,
                        "value": s.value,
                        "timestamp": s.timestamp_ms,
                    }

                with _live_data_lock:
                    _live_data["channels"] = channel_values
                    _live_data["last_update"] = datetime.now().isoformat()

        except Exception as e:
            logger.warning("Live capture error: %s", e)
        finally:
            # Avoid leaving a closed loop as the thread's current loop.
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass

            # Cancel any leftover tasks before closing to prevent warnings/leaks.
            try:
                pending = asyncio.all_tasks(loop)
            except Exception:
                pending = set()

            if pending:
                for task in pending:
                    task.cancel()
                try:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                except Exception:
                    pass

            try:
                loop.close()
            except Exception:
                pass

        time.sleep(2.0)  # Update every 2 seconds


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

    Note: Higher rate limit (600/minute) to support real-time polling
    at 250ms intervals for live dyno data visualization.
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

    with _live_data_lock:
        return jsonify(
            {
                "capturing": _live_data["capturing"],
                "simulated": False,
                "last_update": _live_data["last_update"],
                "channels": _live_data["channels"],
                "channel_count": len(_live_data["channels"]),
            }
        )


# =============================================================================
# Dyno Simulator Routes
# =============================================================================

# Simulator state
_sim_active: bool = False
_sim_lock = threading.Lock()


def _is_simulator_active() -> bool:
    """Thread-safe check for simulator activity."""
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
        import traceback

        error_msg = str(e)
        traceback_str = traceback.format_exc()
        logger.error(f"Failed to start simulator: {error_msg}", exc_info=True)

        # Try to get debug mode, but don't fail if current_app is not available
        try:
            is_debug = current_app.debug
        except RuntimeError:
            # Not in request context, default to False
            is_debug = False

        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to start simulator: {error_msg}",
                    "details": traceback_str if is_debug else None,
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


@jetdrive_bp.route("/simulator/pull-data", methods=["GET"])
def get_pull_data():
    """Get data from the last completed pull."""
    if not _is_simulator_active():
        return jsonify({"error": "Simulator not running"}), 400

    from api.services.dyno_simulator import SimState, get_simulator

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


# =============================================================================
# Debug and Diagnostics Routes
# =============================================================================


def suggest_channel_config(channel_name: str, channel_data: dict) -> dict:
    """
    Suggest configuration for a channel based on its name and value characteristics.
    Used by channel discovery endpoint.
    """
    name_lower = channel_name.lower()
    value = channel_data.get("value", 0)

    # Common channel patterns
    if "rpm" in name_lower:
        return {
            "label": "RPM",
            "units": "rpm",
            "min": 0,
            "max": 10000,
            "decimals": 0,
            "color": "#4ade80",
        }
    elif "afr" in name_lower or "air/fuel" in name_lower or "air-fuel" in name_lower:
        return {
            "label": "AFR",
            "units": ":1",
            "min": 10,
            "max": 18,
            "decimals": 2,
            "color": "#f472b6",
        }
    elif "lambda" in name_lower:
        return {
            "label": "Lambda",
            "units": "λ",
            "min": 0.7,
            "max": 1.3,
            "decimals": 3,
            "color": "#a78bfa",
        }
    elif "force" in name_lower or "load" in name_lower or "drum" in name_lower:
        return {
            "label": "Force",
            "units": "lbs",
            "min": 0,
            "max": 500,
            "decimals": 1,
            "color": "#4ade80",
        }
    elif "hp" in name_lower or "horsepower" in name_lower or "power" in name_lower:
        return {
            "label": "Horsepower",
            "units": "HP",
            "min": 0,
            "max": 200,
            "decimals": 1,
            "color": "#10b981",
        }
    elif "tq" in name_lower or "torque" in name_lower:
        return {
            "label": "Torque",
            "units": "ft-lb",
            "min": 0,
            "max": 150,
            "decimals": 1,
            "color": "#8b5cf6",
        }
    elif "map" in name_lower and "kpa" not in name_lower:
        return {
            "label": "MAP",
            "units": "kPa",
            "min": 0,
            "max": 105,
            "decimals": 1,
            "color": "#06b6d4",
        }
    elif "tps" in name_lower or "throttle" in name_lower:
        return {
            "label": "TPS",
            "units": "%",
            "min": 0,
            "max": 100,
            "decimals": 1,
            "color": "#14b8a6",
        }
    elif "temp" in name_lower or "iat" in name_lower or "ect" in name_lower:
        # Guess based on value range
        if value > 100:  # Likely Fahrenheit
            return {
                "label": "Temperature",
                "units": "°F",
                "min": 0,
                "max": 250,
                "decimals": 0,
                "color": "#f97316",
            }
        else:  # Likely Celsius
            return {
                "label": "Temperature",
                "units": "°C",
                "min": 0,
                "max": 120,
                "decimals": 1,
                "color": "#f97316",
            }
    elif "humid" in name_lower:
        return {
            "label": "Humidity",
            "units": "%",
            "min": 0,
            "max": 100,
            "decimals": 1,
            "color": "#60a5fa",
        }
    elif "pressure" in name_lower or "baro" in name_lower:
        return {
            "label": "Pressure",
            "units": "kPa",
            "min": 90,
            "max": 110,
            "decimals": 2,
            "color": "#a78bfa",
        }
    elif "volt" in name_lower or "vbatt" in name_lower or "battery" in name_lower:
        return {
            "label": "Voltage",
            "units": "V",
            "min": 0,
            "max": 15,
            "decimals": 2,
            "color": "#eab308",
        }
    else:
        # Generic fallback
        return {
            "label": channel_name,
            "units": "",
            "min": 0,
            "max": 100,
            "decimals": 2,
            "color": "#888888",
        }


@jetdrive_bp.route("/hardware/channels/discover", methods=["GET"])
def discover_channels():
    """
    Discover all available channels with their current values.
    Useful for debugging channel name mismatches.
    """
    try:
        # Get live data (works with both real hardware and simulator)
        if _is_simulator_active():
            from api.services.dyno_simulator import get_simulator

            sim = get_simulator()
            channels_data = sim.get_channels()
        else:
            with _live_data_lock:
                channels_data = _live_data.get("channels", {})

        channels = []
        for name, ch in channels_data.items():
            # Build channel info
            channel_info = {
                "id": ch.get("id", 0),
                "name": name,
                "value": ch.get("value", 0),
                "timestamp": ch.get("timestamp", 0),
                "suggested_config": suggest_channel_config(name, ch),
            }

            channels.append(channel_info)

        # Sort by ID for consistency
        channels.sort(key=lambda x: x["id"])

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
        return jsonify({"success": False, "error": str(e)}), 500


@jetdrive_bp.route("/hardware/health", methods=["GET"])
def check_hardware_health():
    """
    Check hardware connection health with latency measurement.
    """
    try:
        start_time = time.time()

        # Check if we're using simulator
        if _is_simulator_active():
            latency_ms = (time.time() - start_time) * 1000
            from api.services.dyno_simulator import get_simulator

            sim = get_simulator()
            state = sim.get_state().value

            return jsonify(
                {
                    "healthy": True,
                    "connected": True,
                    "simulated": True,
                    "sim_state": state,
                    "latency_ms": latency_ms,
                    "mode": "simulator",
                }
            )

        # Check real hardware connection
        with _live_data_lock:
            capturing = _live_data.get("capturing", False)
            channel_count = len(_live_data.get("channels", {}))
            last_update = _live_data.get("last_update")

        latency_ms = (time.time() - start_time) * 1000

        # Consider healthy if we have channels and recent updates
        is_healthy = capturing and channel_count > 0

        if last_update:
            try:
                last_update_dt = datetime.fromisoformat(last_update)
                age_seconds = (datetime.now() - last_update_dt).total_seconds()

                # Stale if no update in last 5 seconds
                if age_seconds > 5:
                    is_healthy = False
            except:
                pass

        return jsonify(
            {
                "healthy": is_healthy,
                "connected": capturing,
                "simulated": False,
                "latency_ms": latency_ms,
                "channel_count": channel_count,
                "last_update": last_update,
                "mode": "hardware",
            }
        )

    except Exception as e:
        logger.error(f"Error checking hardware health: {e}", exc_info=True)
        return jsonify({"healthy": False, "connected": False, "error": str(e)}), 503
