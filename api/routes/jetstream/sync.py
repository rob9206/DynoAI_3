"""Jetstream sync route for manual polling."""

from flask import Blueprint, jsonify
from api.jetstream.poller import get_poller
from api.jetstream.stub_data import get_stub_sync_response, is_stub_mode_enabled

sync_bp = Blueprint("jetstream_sync", __name__)


@sync_bp.route("/sync", methods=["POST"])
def trigger_sync():
    """
    Force an immediate poll of the Jetstream API.

    Returns list of newly found run IDs.

    Response:
    {
        "new_runs_found": 2,
        "run_ids": ["run_abc123", "run_def456"]
    }
    """
    if is_stub_mode_enabled():
        return jsonify(get_stub_sync_response()), 200

    poller = get_poller()

    if not poller:
        return (
            jsonify(
                {
                    "error": "Jetstream poller not initialized",
                    "new_runs_found": 0,
                    "run_ids": [],
                }
            ),
            503,
        )

    try:
        new_run_ids = poller.trigger_sync()
        return (
            jsonify({"new_runs_found": len(new_run_ids), "run_ids": new_run_ids}),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e), "new_runs_found": 0, "run_ids": []}), 500
