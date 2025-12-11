"""
DynoAI Tuning Wizards API Routes

Provides REST endpoints for:
- Decel Pop Wizard (one-click fix)
- Stage Configuration presets
- Cam Family presets
- Heat Soak Warning analysis
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from tuning_wizards import (
    PullMetrics,
    analyze_heat_soak,
    generate_decel_fix_overlay,
    generate_idle_ve_overlay,
    get_cam_preset,
    get_stage_preset,
    list_cam_presets,
    list_stage_presets,
)

wizards_bp = Blueprint("wizards", __name__, url_prefix="/api/wizards")

# Output folder for generated overlays
OUTPUT_FOLDER = Path(__file__).parent.parent.parent / "outputs"

# ============================================================================
# Decel Pop Wizard Endpoints
# ============================================================================


@wizards_bp.route("/decel/preview", methods=["POST"])
def preview_decel_fix():
    """
    Preview the Decel Pop fix without applying.

    Request body:
        {
            "severity": "low" | "medium" | "high",
            "rpm_min": 1750,
            "rpm_max": 5500,
            "cam_family": "stock" | "bolt_in" | "performance" | "race"
        }

    Returns:
        Preview of cells to be modified and enrichment values
    """
    data = request.get_json() or {}

    severity = data.get("severity", "medium")
    rpm_min = int(data.get("rpm_min", 1750))
    rpm_max = int(data.get("rpm_max", 5500))
    cam_family = data.get("cam_family", "stock")

    result = generate_decel_fix_overlay(
        severity=severity,
        rpm_min=rpm_min,
        rpm_max=rpm_max,
        cam_family=cam_family,
    )

    return jsonify(result.to_dict()), 200


@wizards_bp.route("/decel/apply", methods=["POST"])
def apply_decel_fix():
    """
    Apply the Decel Pop fix and generate overlay CSV.

    Request body:
        {
            "severity": "low" | "medium" | "high",
            "rpm_min": 1750,
            "rpm_max": 5500,
            "cam_family": "stock" | "bolt_in" | "performance" | "race",
            "run_id": "optional-run-id-to-associate"
        }

    Returns:
        {
            "success": true,
            "overlay_path": "path/to/overlay.csv",
            "download_url": "/api/wizards/decel/download/...",
            "result": { ... preview data ... }
        }
    """
    from dynoai.constants import KPA_BINS, RPM_BINS

    data = request.get_json() or {}

    severity = data.get("severity", "medium")
    rpm_min = int(data.get("rpm_min", 1750))
    rpm_max = int(data.get("rpm_max", 5500))
    cam_family = data.get("cam_family", "stock")
    run_id = data.get("run_id")

    # Generate the overlay
    result = generate_decel_fix_overlay(
        severity=severity,
        rpm_min=rpm_min,
        rpm_max=rpm_max,
        cam_family=cam_family,
    )

    # Create output directory
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_id = run_id or f"decel_fix_{timestamp}"
    output_dir = OUTPUT_FOLDER / output_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write overlay CSV
    overlay_path = output_dir / "Decel_Pop_Fix_Overlay.csv"
    _write_overlay_csv(
        overlay_path, result.overlay_data, list(RPM_BINS), list(KPA_BINS)
    )

    # Write metadata JSON
    metadata_path = output_dir / "Decel_Pop_Fix_Meta.json"
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "severity": severity,
        "rpm_range": [rpm_min, rpm_max],
        "cam_family": cam_family,
        "cells_modified": result.cells_modified,
        "enrichment_summary": result.enrichment_preview,
        "warnings": result.warnings,
        "recommendations": result.recommendations,
    }
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return (
        jsonify(
            {
                "success": True,
                "overlay_path": str(overlay_path),
                "metadata_path": str(metadata_path),
                "download_url": f"/api/wizards/decel/download/{output_id}",
                "result": result.to_dict(),
            }
        ),
        200,
    )


@wizards_bp.route("/decel/download/<output_id>", methods=["GET"])
def download_decel_overlay(output_id: str):
    """Download the generated Decel Pop Fix overlay CSV."""
    output_id = secure_filename(output_id)
    overlay_path = OUTPUT_FOLDER / output_id / "Decel_Pop_Fix_Overlay.csv"

    if not overlay_path.exists():
        return jsonify({"error": "Overlay not found"}), 404

    return send_file(
        overlay_path,
        as_attachment=True,
        download_name="Decel_Pop_Fix_Overlay.csv",
    )


# ============================================================================
# Stage Configuration Endpoints
# ============================================================================


@wizards_bp.route("/stages", methods=["GET"])
def get_stages():
    """
    Get all available stage configuration presets.

    Returns:
        List of stage presets with VE scaling, AFR targets, and notes
    """
    return (
        jsonify(
            {
                "presets": list_stage_presets(),
            }
        ),
        200,
    )


@wizards_bp.route("/stages/<stage_level>", methods=["GET"])
def get_stage_detail(stage_level: str):
    """
    Get detailed configuration for a specific stage level.

    Args:
        stage_level: stock, stage_1, stage_2, stage_3, stage_4

    Returns:
        Stage preset details including recommended tuning parameters
    """
    preset = get_stage_preset(stage_level)
    return jsonify(preset.to_dict()), 200


# ============================================================================
# Cam Family Endpoints
# ============================================================================


@wizards_bp.route("/cams", methods=["GET"])
def get_cams():
    """
    Get all available cam family presets.

    Returns:
        List of cam presets with idle characteristics and AFR targets
    """
    return (
        jsonify(
            {
                "presets": list_cam_presets(),
            }
        ),
        200,
    )


@wizards_bp.route("/cams/<cam_family>", methods=["GET"])
def get_cam_detail(cam_family: str):
    """
    Get detailed configuration for a specific cam family.

    Args:
        cam_family: stock, bolt_in, performance, race

    Returns:
        Cam preset details including idle VE offset and AFR targets
    """
    preset = get_cam_preset(cam_family)
    return jsonify(preset.to_dict()), 200


@wizards_bp.route("/cams/<cam_family>/idle-overlay", methods=["POST"])
def get_cam_idle_overlay(cam_family: str):
    """
    Generate idle VE overlay for a cam family.

    Args:
        cam_family: stock, bolt_in, performance, race

    Request body (optional):
        {
            "run_id": "optional-run-id-to-associate"
        }

    Returns:
        Idle VE overlay data and download URL
    """
    from dynoai.constants import KPA_BINS, RPM_BINS

    # Sanitize cam_family input - only allow known values
    allowed_families = {"stock", "bolt_in", "performance", "race"}
    safe_cam_family = secure_filename(cam_family)
    if safe_cam_family not in allowed_families:
        safe_cam_family = "stock"

    data = request.get_json() or {}
    run_id = data.get("run_id")

    preset = get_cam_preset(safe_cam_family)
    overlay = generate_idle_ve_overlay(preset)

    # Count modified cells
    cells_modified = sum(1 for row in overlay for val in row if val != 0.0)

    # Create output if requested
    output_info = {}
    if run_id:
        safe_run_id = secure_filename(run_id)
        output_id = f"{safe_run_id}_cam_idle"
        output_dir = OUTPUT_FOLDER / output_id
        output_dir.mkdir(parents=True, exist_ok=True)

        overlay_path = output_dir / f"Cam_Idle_VE_Overlay_{safe_cam_family}.csv"
        _write_overlay_csv(overlay_path, overlay, list(RPM_BINS), list(KPA_BINS))

        output_info = {
            "overlay_path": str(overlay_path),
            "download_url": f"/api/wizards/cams/{safe_cam_family}/download/{output_id}",
        }

    return (
        jsonify(
            {
                "cam_family": safe_cam_family,
                "preset": preset.to_dict(),
                "idle_ve_offset_pct": preset.idle_ve_offset,
                "cells_modified": cells_modified,
                "overlay_data": overlay,
                **output_info,
            }
        ),
        200,
    )


# ============================================================================
# Heat Soak Warning Endpoints
# ============================================================================


@wizards_bp.route("/heat-soak/analyze", methods=["POST"])
def analyze_heat_soak_endpoint():
    """
    Analyze heat soak across multiple dyno pulls.

    Request body:
        {
            "pulls": [
                {
                    "pull_number": 1,
                    "peak_hp": 95.2,
                    "peak_torque": 105.3,
                    "peak_rpm": 5500,
                    "iat_start": 95.0,
                    "iat_end": 110.0,
                    "iat_peak": 115.0,
                    "ambient_temp": 75.0  // optional
                },
                // ... more pulls
            ]
        }

    Returns:
        Heat soak analysis with recommendations
    """
    data = request.get_json()

    if not data or "pulls" not in data:
        return jsonify({"error": "pulls array is required"}), 400

    # Parse pull data
    pulls = []
    for p in data["pulls"]:
        try:
            pull = PullMetrics(
                pull_number=int(p.get("pull_number", len(pulls) + 1)),
                peak_hp=float(p["peak_hp"]),
                peak_torque=float(p["peak_torque"]),
                peak_rpm=int(p["peak_rpm"]),
                iat_start=float(p["iat_start"]),
                iat_end=float(p["iat_end"]),
                iat_peak=float(p["iat_peak"]),
                ambient_temp=(
                    float(p["ambient_temp"]) if p.get("ambient_temp") else None
                ),
            )
            pulls.append(pull)
        except (KeyError, TypeError, ValueError):
            # Don't expose internal error details to client
            return (
                jsonify(
                    {
                        "error": "Invalid pull data format",
                        "required_fields": [
                            "peak_hp",
                            "peak_torque",
                            "peak_rpm",
                            "iat_start",
                            "iat_end",
                            "iat_peak",
                        ],
                    }
                ),
                400,
            )

    # Analyze
    analysis = analyze_heat_soak(pulls)

    return jsonify(analysis.to_dict()), 200


@wizards_bp.route("/heat-soak/quick-check", methods=["POST"])
def quick_heat_check():
    """
    Quick heat soak check with just HP values.

    Request body:
        {
            "hp_values": [95.2, 94.1, 92.8, 91.5],
            "iat_values": [95, 105, 115, 125]  // optional
        }

    Returns:
        Quick assessment of heat soak status
    """
    data = request.get_json()

    if not data or "hp_values" not in data:
        return jsonify({"error": "hp_values array is required"}), 400

    hp_values = [float(v) for v in data["hp_values"]]
    iat_values = data.get("iat_values", [100] * len(hp_values))

    if len(hp_values) < 2:
        return (
            jsonify(
                {
                    "status": "insufficient_data",
                    "message": "Need at least 2 pulls to analyze",
                }
            ),
            200,
        )

    # Create synthetic pull metrics
    pulls = []
    for i, (hp, iat) in enumerate(zip(hp_values, iat_values)):
        pulls.append(
            PullMetrics(
                pull_number=i + 1,
                peak_hp=hp,
                peak_torque=hp * 1.1,  # Estimate
                peak_rpm=5500,
                iat_start=iat - 5,
                iat_end=iat + 5,
                iat_peak=iat + 10,
            )
        )

    analysis = analyze_heat_soak(pulls)

    return (
        jsonify(
            {
                "status": "heat_soaked" if analysis.is_heat_soaked else "ok",
                "hp_degradation_pct": round(analysis.hp_degradation_pct, 1),
                "recommendation": analysis.recommendation,
                "warnings": analysis.warnings,
                "use_baseline_pull": analysis.baseline_pull,
            }
        ),
        200,
    )


# ============================================================================
# Combined Configuration Endpoint
# ============================================================================


@wizards_bp.route("/config", methods=["GET"])
def get_all_wizard_config():
    """
    Get all wizard configuration options in one call.

    Returns:
        Combined stage presets, cam presets, and decel severity options
    """
    return (
        jsonify(
            {
                "stages": list_stage_presets(),
                "cams": list_cam_presets(),
                "decel_severities": [
                    {
                        "value": "low",
                        "label": "Low",
                        "description": "Minimal enrichment, may have some popping",
                        "fuel_economy_impact": "-0.3 to -0.5 MPG",
                    },
                    {
                        "value": "medium",
                        "label": "Medium (Recommended)",
                        "description": "Balanced - eliminates most popping",
                        "fuel_economy_impact": "-0.5 to -1.0 MPG",
                    },
                    {
                        "value": "high",
                        "label": "High",
                        "description": "Aggressive - eliminates all popping",
                        "fuel_economy_impact": "-1.0 to -2.0 MPG",
                    },
                ],
            }
        ),
        200,
    )


# ============================================================================
# Helper Functions
# ============================================================================


def _sanitize_csv_cell(value: str) -> str:
    """
    Sanitize CSV cell value to prevent formula injection.

    Cells starting with =, +, -, @ can be interpreted as formulas
    by spreadsheet software. We prefix them with a single quote.
    """
    if value and value[0] in ("=", "+", "-", "@"):
        return f"'{value}"
    return value


def _write_overlay_csv(
    path: Path,
    overlay: list[list[float]],
    rpm_bins: list[int],
    kpa_bins: list[int],
):
    """Write VE overlay to CSV file with formula injection protection."""
    # Use QUOTE_ALL to prevent formula injection by quoting all cells
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)

        # Header row - all values are numeric, safe
        writer.writerow(["RPM"] + [str(k) for k in kpa_bins])

        # Data rows - all values are derived from internal floats, not user input
        for i, rpm in enumerate(rpm_bins):
            row = [str(rpm)]
            for j in range(len(kpa_bins)):
                # Format as percentage with + sign for positive values
                val = overlay[i][j] * 100
                if val > 0:
                    # Sanitize to prevent formula injection
                    row.append(_sanitize_csv_cell(f"+{val:.2f}"))
                else:
                    row.append(f"{val:.2f}")
            writer.writerow(row)
