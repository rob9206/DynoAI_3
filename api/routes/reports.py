"""
DynoAI Report Generation API Routes

Endpoints for generating professional PDF reports.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from api.services.report_generator import (
    generate_comparison_report_from_runs,
    generate_report_from_run,
    get_comparison_summary_from_runs,
    load_shop_branding,
)

logger = logging.getLogger(__name__)

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def _safe_filename_component(run_id: str) -> str:
    """Convert run IDs into filesystem-safe filename components."""
    return run_id.replace("\\", "_").replace("/", "_").replace("..", "_")


def _resolve_run_path(runs_dir: Path, run_id: str) -> Path:
    """Resolve and validate a run path stays within runs_dir."""
    if not run_id or not isinstance(run_id, str):
        raise ValueError("Invalid run_id")
    candidate = (runs_dir / run_id).resolve()
    root = runs_dir.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Invalid run_id path") from exc
    return candidate


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def get_runs_dir() -> Path:
    """Get the runs directory."""
    return get_project_root() / "runs"


@reports_bp.route("/branding", methods=["GET"])
def get_branding():
    """
    Get current shop branding configuration.

    Returns:
        JSON with shop branding settings
    """
    branding = load_shop_branding()
    return jsonify(
        {
            "success": True,
            "branding": {
                "shop_name": branding.shop_name,
                "tagline": branding.tagline,
                "address": branding.address,
                "phone": branding.phone,
                "email": branding.email,
                "website": branding.website,
                "logo_path": branding.logo_path,
                "primary_color": branding.primary_color,
                "secondary_color": branding.secondary_color,
                "accent_color": branding.accent_color,
            },
        }
    )


@reports_bp.route("/branding", methods=["PUT"])
def update_branding():
    """
    Update shop branding configuration.

    Request body:
        {
            "shop_name": "My Shop",
            "tagline": "Professional Tuning",
            "address": "123 Main St",
            "phone": "555-1234",
            "email": "shop@example.com",
            "website": "www.example.com",
            "primary_color": "#F59E0B",
            "secondary_color": "#1F2937",
            "accent_color": "#10B981"
        }

    Returns:
        JSON with updated branding settings
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    config_path = get_project_root() / "config" / "shop_branding.json"

    # Load existing or create new
    existing = {}
    if config_path.exists():
        with open(config_path) as f:
            existing = json.load(f)

    # Update with new values
    allowed_fields = [
        "shop_name",
        "tagline",
        "address",
        "phone",
        "email",
        "website",
        "logo_path",
        "primary_color",
        "secondary_color",
        "accent_color",
    ]

    for field in allowed_fields:
        if field in data:
            existing[field] = data[field]

    # Save updated config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(existing, f, indent=2)

    return jsonify(
        {
            "success": True,
            "message": "Branding updated successfully",
            "branding": existing,
        }
    )


@reports_bp.route("/generate/<run_id>", methods=["POST"])
def generate_report(run_id: str):
    """
    Generate a PDF report for a specific run.

    URL Parameters:
        run_id: The run ID to generate report for

    Request body (optional):
        {
            "customer_name": "John Doe",
            "vehicle_info": "2021 Road Glide - Stage 2",
            "tuner_notes": "Bike is running great after tune...",
            "baseline_run_id": "run_20251224_baseline"
        }

    Query Parameters:
        download: If "true", returns PDF file directly
        include_heatmaps: If "false", excludes VE/AFR heatmaps
        include_power_curve: If "false", excludes power curve chart

    Returns:
        If download=true: PDF file
        Otherwise: JSON with download URL
    """
    # Validate run exists
    runs_dir = get_runs_dir()
    try:
        run_path = _resolve_run_path(runs_dir, run_id)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid run_id"}), 400

    if not run_path.exists():
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    # Parse request data
    data = request.get_json() or {}
    customer_name = data.get("customer_name", "Valued Customer")
    vehicle_info = data.get("vehicle_info", "")
    tuner_notes = data.get("tuner_notes", "")
    baseline_run_id = data.get("baseline_run_id")

    # Query params
    download = request.args.get("download", "false").lower() == "true"
    try:
        # Generate output path
        output_filename = f"DynoAI_Report_{run_id}.pdf"
        output_path = run_path / output_filename

        # Generate the report
        pdf_bytes = generate_report_from_run(
            run_id=run_id,
            runs_dir=str(runs_dir),
            customer_name=customer_name,
            vehicle_info=vehicle_info,
            tuner_notes=tuner_notes,
            baseline_run_id=baseline_run_id,
            output_path=str(output_path),
        )

        logger.info(f"Generated report for run {run_id}: {len(pdf_bytes)} bytes")

        if download:
            return send_file(
                output_path,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=output_filename,
            )

        return jsonify(
            {
                "success": True,
                "run_id": run_id,
                "report_path": str(output_path),
                "download_url": f"/api/reports/download/{run_id}",
                "size_bytes": len(pdf_bytes),
            }
        )

    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        logger.exception(f"Failed to generate report for run {run_id}")
        return jsonify({"success": False, "error": str(e)}), 500


@reports_bp.route("/compare", methods=["POST"])
def compare_runs():
    """
    Generate a side-by-side comparison report for two run IDs.
    """
    data = request.get_json() or {}
    run_a_id = data.get("run_a_id", "")
    run_b_id = data.get("run_b_id", "")
    customer_name = data.get("customer_name", "Valued Customer")
    vehicle_info = data.get("vehicle_info", "")
    tuner_notes = data.get("tuner_notes", "")

    if not run_a_id or not run_b_id:
        return (
            jsonify({"success": False, "error": "run_a_id and run_b_id are required"}),
            400,
        )
    if run_a_id == run_b_id:
        return (
            jsonify(
                {"success": False, "error": "run_a_id and run_b_id must be different"}
            ),
            400,
        )

    download = request.args.get("download", "false").lower() == "true"
    include_afr = request.args.get("include_afr", "true").lower() != "false"
    runs_dir = get_runs_dir()
    try:
        run_a_path = _resolve_run_path(runs_dir, run_a_id)
        run_b_path = _resolve_run_path(runs_dir, run_b_id)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid run_id"}), 400

    if not run_a_path.exists():
        return jsonify({"success": False, "error": f"Run not found: {run_a_id}"}), 404
    if not run_b_path.exists():
        return jsonify({"success": False, "error": f"Run not found: {run_b_id}"}), 404

    try:
        comparisons_dir = runs_dir / "comparisons"
        comparisons_dir.mkdir(parents=True, exist_ok=True)
        safe_a = _safe_filename_component(run_a_id)
        safe_b = _safe_filename_component(run_b_id)
        output_filename = f"DynoAI_Compare_{safe_a}__vs__{safe_b}.pdf"
        output_path = comparisons_dir / output_filename

        pdf_bytes = generate_comparison_report_from_runs(
            run_a_id=run_a_id,
            run_b_id=run_b_id,
            runs_dir=str(runs_dir),
            customer_name=customer_name,
            vehicle_info=vehicle_info,
            tuner_notes=tuner_notes,
            include_afr=include_afr,
            output_path=str(output_path),
        )
        summary = get_comparison_summary_from_runs(
            run_a_id, run_b_id, runs_dir=str(runs_dir)
        )

        logger.info(
            "Generated comparison report %s vs %s (%d bytes)",
            run_a_id,
            run_b_id,
            len(pdf_bytes),
        )

        if download:
            return send_file(
                output_path,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=output_filename,
            )

        return jsonify(
            {
                "success": True,
                "run_a_id": run_a_id,
                "run_b_id": run_b_id,
                "report_path": str(output_path),
                "download_url": f"/api/reports/compare/download?run_a_id={run_a_id}&run_b_id={run_b_id}",
                "size_bytes": len(pdf_bytes),
                "summary": summary,
            }
        )

    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        logger.exception(
            "Failed to generate comparison report %s vs %s", run_a_id, run_b_id
        )
        return jsonify({"success": False, "error": str(e)}), 500


@reports_bp.route("/compare/download", methods=["GET"])
def download_compare_report():
    """Download a previously generated run comparison PDF."""
    run_a_id = request.args.get("run_a_id", "")
    run_b_id = request.args.get("run_b_id", "")
    if not run_a_id or not run_b_id:
        return (
            jsonify({"success": False, "error": "run_a_id and run_b_id are required"}),
            400,
        )

    runs_dir = get_runs_dir()
    safe_a = _safe_filename_component(run_a_id)
    safe_b = _safe_filename_component(run_b_id)
    report_path = (
        runs_dir / "comparisons" / f"DynoAI_Compare_{safe_a}__vs__{safe_b}.pdf"
    )
    if not report_path.exists():
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Comparison report not found. Generate it first using POST /api/reports/compare",
                }
            ),
            404,
        )

    return send_file(
        report_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=report_path.name,
    )


@reports_bp.route("/download/<run_id>", methods=["GET"])
def download_report(run_id: str):
    """
    Download a previously generated PDF report.

    URL Parameters:
        run_id: The run ID

    Returns:
        PDF file
    """
    runs_dir = get_runs_dir()
    try:
        run_path = _resolve_run_path(runs_dir, run_id)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid run_id"}), 400
    output_filename = f"DynoAI_Report_{run_id}.pdf"
    report_path = run_path / output_filename

    if not report_path.exists():
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Report not found. Generate it first using POST /api/reports/generate/{run_id}",
                }
            ),
            404,
        )

    return send_file(
        report_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=output_filename,
    )


@reports_bp.route("/preview/<run_id>", methods=["GET"])
def preview_report_data(run_id: str):
    """
    Get report data preview without generating PDF.

    Useful for showing a preview in the UI before generating.

    URL Parameters:
        run_id: The run ID

    Returns:
        JSON with report data preview
    """
    runs_dir = get_runs_dir()
    try:
        run_path = _resolve_run_path(runs_dir, run_id)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid run_id"}), 400

    if not run_path.exists():
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    # Load manifest
    manifest_path = run_path / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)

    analysis = manifest.get("analysis", {})

    # Check for existing report
    report_exists = (run_path / f"DynoAI_Report_{run_id}.pdf").exists()

    # Load confidence
    confidence_score = None
    confidence_path = run_path / "ConfidenceReport.json"
    if confidence_path.exists():
        with open(confidence_path) as f:
            conf_data = json.load(f)
            confidence_score = conf_data.get("overall_score")

    # Count VE corrections
    ve_path = run_path / "VE_Corrections_2D.csv"
    ve_zones = 0
    if ve_path.exists():
        with open(ve_path) as f:
            lines = f.readlines()[1:]  # Skip header
            for line in lines:
                parts = line.strip().split(",")
                for val in parts[1:]:
                    try:
                        if abs(float(val)) > 0.5:
                            ve_zones += 1
                    except ValueError:
                        pass

    return jsonify(
        {
            "success": True,
            "run_id": run_id,
            "report_exists": report_exists,
            "preview": {
                "peak_hp": analysis.get("peak_hp", 0),
                "peak_hp_rpm": analysis.get("peak_hp_rpm", 0),
                "peak_tq": analysis.get("peak_tq", 0),
                "peak_tq_rpm": analysis.get("peak_tq_rpm", 0),
                "zones_corrected": ve_zones,
                "confidence_score": confidence_score,
                "has_power_curve": bool(analysis.get("power_curve")),
                "has_ve_data": ve_path.exists(),
                "has_afr_data": (run_path / "AFR_Error_2D.csv").exists(),
                "timestamp": manifest.get("created_at", ""),
            },
        }
    )


@reports_bp.route("/list-runs", methods=["GET"])
def list_reportable_runs():
    """
    List all runs that can have reports generated.

    Query Parameters:
        limit: Maximum number of runs to return (default: 20)
        offset: Offset for pagination (default: 0)

    Returns:
        JSON with list of runs
    """
    runs_dir = get_runs_dir()

    if not runs_dir.exists():
        return jsonify({"success": True, "runs": [], "total": 0})

    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)

    # Get all run directories with manifests
    runs = []
    for run_path in runs_dir.iterdir():
        if not run_path.is_dir():
            continue

        manifest_path = run_path / "manifest.json"
        if not manifest_path.exists():
            continue

        try:
            with open(manifest_path) as f:
                manifest = json.load(f)

            analysis = manifest.get("analysis", {})
            report_exists = (run_path / f"DynoAI_Report_{run_path.name}.pdf").exists()

            runs.append(
                {
                    "run_id": run_path.name,
                    "created_at": manifest.get("created_at", ""),
                    "peak_hp": analysis.get("peak_hp", 0),
                    "peak_tq": analysis.get("peak_tq", 0),
                    "report_exists": report_exists,
                }
            )
        except Exception as e:
            logger.warning(f"Failed to read manifest for {run_path.name}: {e}")

    # Sort by created_at descending
    runs.sort(key=lambda x: x["created_at"], reverse=True)

    total = len(runs)
    runs = runs[offset: offset + limit]

    return jsonify(
        {
            "success": True,
            "runs": runs,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )
