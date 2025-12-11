"""
JetDrive Auto-Tune API Routes

Provides REST endpoints for:
- Running JetDrive autotune analysis
- Simulating dyno runs
- Analyzing existing CSV data
- Exporting PVV corrections
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

jetdrive_bp = Blueprint("jetdrive", __name__, url_prefix="/api/jetdrive")


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
