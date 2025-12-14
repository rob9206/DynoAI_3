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

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

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


@jetdrive_bp.route("/analyze", methods=["POST"])
def analyze_run():
    """
    Run JetDrive autotune analysis.

    Request body:
    {
        "run_id": "my_run",
        "mode": "simulate" | "csv",
        "csv_path": "path/to/file.csv"  // Required if mode=csv
    }
    """
    data = request.get_json()
    if not data or "run_id" not in data:
        return jsonify({"error": "Missing 'run_id' in request body"}), 400

    try:
        run_id = sanitize_run_id(data["run_id"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    mode = data.get("mode", "simulate")
    csv_path = data.get("csv_path")

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
    else:
        return jsonify({"error": f"Invalid mode: {mode}"}), 400

    # Run analysis
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

        return jsonify(
            {
                "success": True,
                "run_id": run_id,
                "output_dir": str(output_dir),
                "analysis": manifest.get("analysis", {}),
                "grid": manifest.get("grid", {}),
                "ve_grid": ve_grid,
                "outputs": manifest.get("outputs", {}),
            }
        )

    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Analysis timed out"}), 500
    except Exception as e:
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

    return jsonify(
        {
            "run_id": run_id,
            "manifest": manifest,
            "ve_grid": ve_grid,
            "hit_grid": hit_grid,
            "afr_grid": afr_grid,
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
        lines.append(
            f"Peak Horsepower: {analysis.get('peak_hp', 0):.2f} HP @ {analysis.get('peak_hp_rpm', 0):.0f} RPM"
        )
        lines.append(
            f"Peak Torque: {analysis.get('peak_tq', 0):.2f} lb-ft @ {analysis.get('peak_tq_rpm', 0):.0f} RPM"
        )
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
                stop_event = asyncio.Event()

                def on_sample(s: JetDriveSample):
                    samples.append(s)

                async def capture_brief():
                    from api.services.jetdrive_client import subscribe

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
    """Get current live channel data."""
    global _live_data

    with _live_data_lock:
        return jsonify(
            {
                "capturing": _live_data["capturing"],
                "last_update": _live_data["last_update"],
                "channels": _live_data["channels"],
                "channel_count": len(_live_data["channels"]),
            }
        )
