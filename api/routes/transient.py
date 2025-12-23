"""
Transient Fuel Compensation API Routes

Provides REST endpoints for:
- Analyzing transient events in dyno data
- Generating enrichment tables
- Exporting to Power Vision format
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from io import StringIO

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename
import pandas as pd

from dynoai.core.transient_fuel import TransientFuelAnalyzer, TransientFuelResult

transient_bp = Blueprint("transient", __name__, url_prefix="/api/transient")

# Output folder for generated exports
OUTPUT_FOLDER = Path(__file__).parent.parent.parent / "outputs"


@transient_bp.route("/analyze", methods=["POST"])
def analyze_transients():
    """
    Analyze transient events in uploaded dyno data.

    Request body:
        {
            "csv_data": "string (CSV content)",
            "target_afr": 13.0,  // optional, default 13.0
            "map_rate_threshold": 50.0,  // optional, kPa/sec
            "tps_rate_threshold": 20.0,  // optional, %/sec
            "run_id": "optional run ID"
        }

    Returns:
        {
            "success": true,
            "run_id": "transient_xxx",
            "events_detected": 3,
            "analysis": {
                "accel_events": 2,
                "decel_events": 1,
                "recommendations": [...],
                "map_rate_table": [...],
                "tps_rate_table": [...],
                "wall_wetting_factors": {...}
            },
            "download_url": "/api/transient/export/xxx"
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Get CSV data
    csv_data = data.get("csv_data")
    if not csv_data:
        return jsonify({"error": "csv_data is required"}), 400

    # Parse CSV
    try:
        df = pd.read_csv(StringIO(csv_data))
    except Exception as e:
        return jsonify({"error": f"Failed to parse CSV: {str(e)}"}), 400

    # Get parameters
    target_afr = float(data.get("target_afr", 13.0))
    map_rate_threshold = float(data.get("map_rate_threshold", 50.0))
    tps_rate_threshold = float(data.get("tps_rate_threshold", 20.0))
    
    # Sanitize run_id to prevent path traversal - always sanitize user input
    raw_run_id = data.get("run_id")
    run_id = secure_filename(raw_run_id) if raw_run_id else None

    # Create analyzer
    analyzer = TransientFuelAnalyzer(
        target_afr=target_afr,
        map_rate_threshold=map_rate_threshold,
        tps_rate_threshold=tps_rate_threshold,
    )

    # Analyze
    try:
        result = analyzer.analyze_transients(df)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

    # Generate run ID
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_id = run_id or f"transient_{timestamp}"

    # Save results
    output_dir = OUTPUT_FOLDER / output_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save export file
    export_path = output_dir / "transient_compensation.txt"
    analyzer.export_power_vision(result, str(export_path))

    # Save metadata
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_afr": target_afr,
        "map_rate_threshold": map_rate_threshold,
        "tps_rate_threshold": tps_rate_threshold,
        "events_detected": len(result.detected_events),
        "accel_events": sum(1 for e in result.detected_events if e.event_type == "accel"),
        "decel_events": sum(1 for e in result.detected_events if e.event_type == "decel"),
    }
    with open(output_dir / "transient_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # Prepare response
    accel_events = [e for e in result.detected_events if e.event_type == "accel"]
    decel_events = [e for e in result.detected_events if e.event_type == "decel"]

    return jsonify({
        "success": True,
        "run_id": output_id,
        "events_detected": len(result.detected_events),
        "analysis": {
            "accel_events": len(accel_events),
            "decel_events": len(decel_events),
            "events": [
                {
                    "type": e.event_type,
                    "severity": e.severity,
                    "start_time": e.start_time,
                    "end_time": e.end_time,
                    "peak_map_rate": round(e.peak_map_rate, 1),
                    "peak_tps_rate": round(e.peak_tps_rate, 1),
                    "avg_rpm": round(e.avg_rpm, 0),
                    "afr_error_avg": round(e.afr_error_avg, 2),
                    "afr_error_peak": round(e.afr_error_peak, 2),
                }
                for e in result.detected_events
            ],
            "recommendations": result.recommendations,
            "map_rate_table": result.map_rate_table.to_dict(orient="records"),
            "tps_rate_table": result.tps_rate_table.to_dict(orient="records"),
            "wall_wetting_factors": result.wall_wetting_factor,
        },
        "download_url": f"/api/transient/export/{output_id}",
    }), 200


@transient_bp.route("/analyze-from-run/<run_id>", methods=["POST"])
def analyze_from_run(run_id: str):
    """
    Analyze transient events from a previously captured JetDrive run.

    Request body:
        {
            "target_afr": 13.0,  // optional
            "map_rate_threshold": 50.0,  // optional
            "tps_rate_threshold": 20.0   // optional
        }
    """
    # Sanitize run_id to prevent path traversal
    run_id = secure_filename(run_id)
    if not run_id:
        return jsonify({"error": "Invalid run_id"}), 400
    
    # Look for run data
    runs_folder = OUTPUT_FOLDER.parent / "runs"
    run_path = runs_folder / run_id

    if not run_path.exists():
        return jsonify({"error": f"Run not found: {run_id}"}), 404

    # Find CSV file
    csv_files = list(run_path.glob("*.csv"))
    if not csv_files:
        return jsonify({"error": "No CSV data found in run"}), 404

    # Load CSV
    try:
        df = pd.read_csv(csv_files[0])
    except Exception as e:
        return jsonify({"error": f"Failed to load run data: {str(e)}"}), 500

    # Get parameters
    data = request.get_json() or {}
    target_afr = float(data.get("target_afr", 13.0))
    map_rate_threshold = float(data.get("map_rate_threshold", 50.0))
    tps_rate_threshold = float(data.get("tps_rate_threshold", 20.0))

    # Create analyzer
    analyzer = TransientFuelAnalyzer(
        target_afr=target_afr,
        map_rate_threshold=map_rate_threshold,
        tps_rate_threshold=tps_rate_threshold,
    )

    # Analyze
    try:
        result = analyzer.analyze_transients(df)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

    # Save results
    output_id = f"{run_id}_transient"
    output_dir = OUTPUT_FOLDER / output_id
    output_dir.mkdir(parents=True, exist_ok=True)

    export_path = output_dir / "transient_compensation.txt"
    analyzer.export_power_vision(result, str(export_path))

    # Prepare response
    accel_events = [e for e in result.detected_events if e.event_type == "accel"]
    decel_events = [e for e in result.detected_events if e.event_type == "decel"]

    return jsonify({
        "success": True,
        "run_id": output_id,
        "source_run": run_id,
        "events_detected": len(result.detected_events),
        "analysis": {
            "accel_events": len(accel_events),
            "decel_events": len(decel_events),
            "events": [
                {
                    "type": e.event_type,
                    "severity": e.severity,
                    "start_time": e.start_time,
                    "end_time": e.end_time,
                    "peak_map_rate": round(e.peak_map_rate, 1),
                    "peak_tps_rate": round(e.peak_tps_rate, 1),
                    "avg_rpm": round(e.avg_rpm, 0),
                    "afr_error_avg": round(e.afr_error_avg, 2),
                    "afr_error_peak": round(e.afr_error_peak, 2),
                }
                for e in result.detected_events
            ],
            "recommendations": result.recommendations,
            "map_rate_table": result.map_rate_table.to_dict(orient="records"),
            "tps_rate_table": result.tps_rate_table.to_dict(orient="records"),
            "wall_wetting_factors": result.wall_wetting_factor,
        },
        "download_url": f"/api/transient/export/{output_id}",
    }), 200


@transient_bp.route("/export/<output_id>", methods=["GET"])
def download_export(output_id: str):
    """Download transient compensation export file."""
    from werkzeug.utils import secure_filename

    safe_id = secure_filename(output_id)
    export_path = OUTPUT_FOLDER / safe_id / "transient_compensation.txt"

    if not export_path.exists():
        return jsonify({"error": "Export not found"}), 404

    return send_file(
        export_path,
        as_attachment=True,
        download_name=f"Transient_Compensation_{safe_id}.txt",
    )


@transient_bp.route("/config", methods=["GET"])
def get_config():
    """
    Get transient analysis configuration options.

    Returns default values and valid ranges for configuration parameters.
    """
    return jsonify({
        "defaults": {
            "target_afr": 13.0,
            "map_rate_threshold": 50.0,
            "tps_rate_threshold": 20.0,
            "afr_tolerance": 0.5,
        },
        "ranges": {
            "target_afr": {"min": 10.0, "max": 16.0, "step": 0.1},
            "map_rate_threshold": {"min": 20.0, "max": 150.0, "step": 5.0},
            "tps_rate_threshold": {"min": 10.0, "max": 80.0, "step": 5.0},
        },
        "severity_descriptions": {
            "mild": "Gradual throttle application, typically during normal driving",
            "moderate": "Quick throttle response, typical WOT pulls",
            "aggressive": "Rapid snap throttle, racing-style inputs",
        },
    }), 200

