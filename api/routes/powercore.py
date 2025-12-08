"""
Power Core Integration API Routes

Provides REST endpoints for:
- Importing Power Vision logs
- Parsing tune files
- Running auto-tune workflow
- Exporting corrections
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from api.services.autotune_workflow import AutoTuneWorkflow
from api.services.livelink_client import LiveLinkClient
from api.services.powercore_integration import (
    check_powercore_running,
    find_log_files,
    find_powercore_data_dirs,
    find_tune_files,
    generate_tunelab_script,
    parse_powervision_log,
    parse_pvv_tune,
    powervision_log_to_dynoai_format,
)
from api.services.wp8_parser import find_wp8_files, list_wp8_channels, parse_wp8_file

powercore_bp = Blueprint("powercore", __name__, url_prefix="/api/powercore")

# Singleton LiveLink client
_livelink: LiveLinkClient | None = None


def get_livelink() -> LiveLinkClient:
    """Get or create the LiveLink client instance."""
    global _livelink
    if _livelink is None:
        _livelink = LiveLinkClient(mode="auto")
    return _livelink


# Singleton workflow instance
_workflow: AutoTuneWorkflow | None = None


def get_workflow() -> AutoTuneWorkflow:
    """Get or create the workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = AutoTuneWorkflow()
    return _workflow


# =============================================================================
# Status & Discovery Routes
# =============================================================================


@powercore_bp.route("/status", methods=["GET"])
def get_status():
    """Check Power Core integration status."""
    return jsonify(
        {
            "powercore_running": check_powercore_running(),
            "data_dirs": [str(d) for d in find_powercore_data_dirs()],
        }
    )


@powercore_bp.route("/discover/logs", methods=["GET"])
def discover_logs():
    """Discover available log files."""
    logs = find_log_files()
    return jsonify(
        {
            "count": len(logs),
            "files": [
                {
                    "path": str(f),
                    "name": f.name,
                    "size_kb": round(f.stat().st_size / 1024, 1),
                }
                for f in logs[:50]  # Limit to 50
            ],
        }
    )


@powercore_bp.route("/discover/tunes", methods=["GET"])
def discover_tunes():
    """Discover available tune files."""
    tunes = find_tune_files()
    return jsonify(
        {
            "count": len(tunes),
            "files": [
                {
                    "path": str(f),
                    "name": f.name,
                    "extension": f.suffix,
                }
                for f in tunes[:50]
            ],
        }
    )


@powercore_bp.route("/discover/wp8", methods=["GET"])
def discover_wp8():
    """Discover available WP8 dyno run files."""
    wp8_files = find_wp8_files()
    return jsonify(
        {
            "count": len(wp8_files),
            "files": [
                {
                    "path": str(f),
                    "name": f.name,
                    "size_kb": round(f.stat().st_size / 1024, 1),
                }
                for f in wp8_files[:50]
            ],
        }
    )


# =============================================================================
# Parsing Routes
# =============================================================================


@powercore_bp.route("/parse/log", methods=["POST"])
def parse_log():
    """Parse a Power Vision log file."""
    data = request.get_json()
    if not data or "path" not in data:
        return jsonify({"error": "Missing 'path' in request body"}), 400

    try:
        pv_log = parse_powervision_log(data["path"])
        dynoai_df = powervision_log_to_dynoai_format(pv_log)

        return jsonify(
            {
                "success": True,
                "format": pv_log.format_version,
                "signals": len(pv_log.signals),
                "rows": len(pv_log.data),
                "signal_list": [
                    {
                        "index": sig.index,
                        "name": sig.name,
                        "units": sig.units,
                        "description": sig.description,
                    }
                    for sig in pv_log.signals.values()
                ],
                "dynoai_columns": list(dynoai_df.columns),
                "preview": dynoai_df.head(10).to_dict(orient="records"),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@powercore_bp.route("/parse/tune", methods=["POST"])
def parse_tune():
    """Parse a PVV tune file."""
    data = request.get_json()
    if not data or "path" not in data:
        return jsonify({"error": "Missing 'path' in request body"}), 400

    try:
        tune = parse_pvv_tune(data["path"])

        return jsonify(
            {
                "success": True,
                "tables": len(tune.tables),
                "scalars": len(tune.scalars),
                "flags": len(tune.flags),
                "table_list": [
                    {
                        "name": t.name,
                        "units": t.units,
                        "rows": len(t.row_axis),
                        "cols": len(t.col_axis),
                        "row_units": t.row_units,
                        "col_units": t.col_units,
                    }
                    for t in tune.tables.values()
                ],
                "scalar_list": tune.scalars,
                "flag_list": tune.flags,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@powercore_bp.route("/parse/wp8", methods=["POST"])
def parse_wp8():
    """Parse a WP8 dyno run file."""
    data = request.get_json()
    if not data or "path" not in data:
        return jsonify({"error": "Missing 'path' in request body"}), 400

    try:
        run = parse_wp8_file(data["path"])

        return jsonify(
            {
                "success": True,
                "channels": len(run.channels),
                "metadata": run.metadata,
                "channel_list": [
                    {
                        "id": ch.channel_id,
                        "name": ch.name,
                        "units": ch.units,
                        "device": ch.device,
                        "category": ch.category,
                    }
                    for ch in run.channels.values()
                ],
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# Auto-Tune Workflow Routes
# =============================================================================


@powercore_bp.route("/autotune/session", methods=["POST"])
def create_session():
    """Create a new auto-tune session."""
    workflow = get_workflow()
    session = workflow.create_session()
    return jsonify({"success": True, "session_id": session.id})


@powercore_bp.route("/autotune/import-log", methods=["POST"])
def import_log():
    """Import a log file into an auto-tune session."""
    data = request.get_json()
    if not data or "session_id" not in data or "path" not in data:
        return (
            jsonify({"error": "Missing 'session_id' or 'path' in request body"}),
            400,
        )

    workflow = get_workflow()
    session = workflow.sessions.get(data["session_id"])
    if not session:
        return jsonify({"error": "Session not found"}), 404

    success = workflow.import_log(session, data["path"])
    return jsonify(
        {
            "success": success,
            "status": session.status,
            "errors": session.errors,
            "log_signals": len(session.pv_log.signals) if session.pv_log else 0,
            "log_rows": len(session.pv_log.data) if session.pv_log else 0,
        }
    )


@powercore_bp.route("/autotune/analyze", methods=["POST"])
def analyze_afr():
    """Run AFR analysis on an auto-tune session."""
    data = request.get_json()
    if not data or "session_id" not in data:
        return jsonify({"error": "Missing 'session_id' in request body"}), 400

    workflow = get_workflow()
    session = workflow.sessions.get(data["session_id"])
    if not session:
        return jsonify({"error": "Session not found"}), 404

    result = workflow.analyze_afr(session)
    if result is None:
        return jsonify({"success": False, "errors": session.errors}), 400

    return jsonify(
        {
            "success": True,
            "analysis": {
                "mean_error_pct": round(result.mean_error_pct, 2),
                "zones_lean": result.zones_lean,
                "zones_rich": result.zones_rich,
                "zones_ok": result.zones_ok,
                "max_lean_pct": round(result.max_lean_pct, 2),
                "max_rich_pct": round(result.max_rich_pct, 2),
                "error_matrix": result.error_by_zone.round(2).to_dict(),
                "hit_matrix": result.hit_count_by_zone.to_dict(),
            },
        }
    )


@powercore_bp.route("/autotune/calculate", methods=["POST"])
def calculate_corrections():
    """Calculate VE corrections for an auto-tune session."""
    data = request.get_json()
    if not data or "session_id" not in data:
        return jsonify({"error": "Missing 'session_id' in request body"}), 400

    workflow = get_workflow()
    session = workflow.sessions.get(data["session_id"])
    if not session:
        return jsonify({"error": "Session not found"}), 404

    result = workflow.calculate_corrections(session)
    if result is None:
        return jsonify({"success": False, "errors": session.errors}), 400

    return jsonify(
        {
            "success": True,
            "corrections": {
                "zones_adjusted": result.zones_adjusted,
                "max_correction_pct": round(result.max_correction_pct, 2),
                "min_correction_pct": round(result.min_correction_pct, 2),
                "clipped_zones": result.clipped_zones,
                "correction_table": result.correction_table.round(4).tolist(),
                "rpm_axis": result.rpm_axis,
                "map_axis": result.map_axis,
            },
        }
    )


@powercore_bp.route("/autotune/export", methods=["POST"])
def export_corrections():
    """Export corrections from an auto-tune session."""
    data = request.get_json()
    if not data or "session_id" not in data or "output_dir" not in data:
        return (
            jsonify({"error": "Missing 'session_id' or 'output_dir' in request body"}),
            400,
        )

    workflow = get_workflow()
    session = workflow.sessions.get(data["session_id"])
    if not session:
        return jsonify({"error": "Session not found"}), 404

    output_dir = data["output_dir"]
    script_path = workflow.export_tunelab_script(session, output_dir)
    pvv_path = workflow.export_pvv_corrections(session, output_dir)

    return jsonify(
        {
            "success": True,
            "tunelab_script": script_path,
            "pvv_file": pvv_path,
        }
    )


@powercore_bp.route("/autotune/full-workflow", methods=["POST"])
def full_workflow():
    """Run the complete auto-tune workflow."""
    data = request.get_json()
    if not data or "log_path" not in data or "output_dir" not in data:
        return (
            jsonify({"error": "Missing 'log_path' or 'output_dir' in request body"}),
            400,
        )

    workflow = get_workflow()
    session = workflow.run_full_workflow(
        log_path=data["log_path"],
        output_dir=data["output_dir"],
        tune_path=data.get("tune_path"),
    )

    return jsonify(workflow.get_session_summary(session))


@powercore_bp.route("/autotune/session/<session_id>", methods=["GET"])
def get_session(session_id: str):
    """Get the status of an auto-tune session."""
    workflow = get_workflow()
    session = workflow.sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(workflow.get_session_summary(session))


# =============================================================================
# Script Generation Routes
# =============================================================================


@powercore_bp.route("/generate/tunelab-script", methods=["POST"])
def generate_script():
    """Generate a TuneLab script with custom parameters."""
    data = request.get_json() or {}

    script = generate_tunelab_script(
        correction_table=data.get("correction_table", "Volumetric Efficiency"),
        afr_channel=data.get("afr_channel", "Air/Fuel Ratio 1"),
        smoothing=data.get("smoothing", 500.0),
        min_afr=data.get("min_afr", 10.0),
        max_afr=data.get("max_afr", 19.0),
    )

    return jsonify({"success": True, "script": script})


# =============================================================================
# LiveLink Real-time Data Routes
# =============================================================================


@powercore_bp.route("/livelink/connect", methods=["POST"])
def livelink_connect():
    """Connect to LiveLink service."""
    data = request.get_json() or {}
    mode = data.get("mode", "auto")

    client = get_livelink()
    if client.connected:
        return jsonify(
            {"success": True, "status": "already_connected", "mode": client.mode}
        )

    # Update mode if specified
    client.mode = mode
    success = client.connect()

    return jsonify(
        {
            "success": success,
            "status": "connected" if success else "failed",
            "mode": client.mode,
        }
    )


@powercore_bp.route("/livelink/disconnect", methods=["POST"])
def livelink_disconnect():
    """Disconnect from LiveLink service."""
    client = get_livelink()
    client.disconnect()
    return jsonify({"success": True, "status": "disconnected"})


@powercore_bp.route("/livelink/status", methods=["GET"])
def livelink_status():
    """Get LiveLink connection status."""
    client = get_livelink()
    return jsonify(
        {
            "connected": client.connected,
            "mode": client.mode,
            "running": client.running,
        }
    )


@powercore_bp.route("/livelink/snapshot", methods=["GET"])
def livelink_snapshot():
    """Get current data snapshot."""
    client = get_livelink()
    if not client.connected:
        return jsonify({"error": "Not connected"}), 400

    snapshot = client.get_snapshot()
    return jsonify(
        {
            "timestamp": snapshot.timestamp,
            "channels": snapshot.channels,
            "units": snapshot.units,
        }
    )


@powercore_bp.route("/livelink/channel/<channel_name>", methods=["GET"])
def livelink_channel(channel_name: str):
    """Get value for a specific channel."""
    client = get_livelink()
    if not client.connected:
        return jsonify({"error": "Not connected"}), 400

    value = client.get_channel_value(channel_name)
    if value is None:
        return jsonify({"error": f"Channel not found: {channel_name}"}), 404

    snapshot = client.get_snapshot()
    return jsonify(
        {
            "channel": channel_name,
            "value": value,
            "units": snapshot.units.get(channel_name, ""),
            "timestamp": snapshot.timestamp,
        }
    )


@powercore_bp.route("/livelink/samples", methods=["GET"])
def livelink_samples():
    """Get recent samples from buffer."""
    client = get_livelink()
    if not client.connected:
        return jsonify({"error": "Not connected"}), 400

    count = request.args.get("count", 100, type=int)
    samples = client.get_samples(count)

    return jsonify(
        {
            "count": len(samples),
            "samples": [
                {
                    "timestamp": s.timestamp,
                    "channel_id": s.channel_id,
                    "channel_name": s.channel_name,
                    "value": s.value,
                    "units": s.units,
                }
                for s in samples
            ],
        }
    )
