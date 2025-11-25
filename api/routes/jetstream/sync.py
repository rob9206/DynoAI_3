"""Jetstream sync route for manual polling."""

import sys
from pathlib import Path

from flask import Blueprint, jsonify
from jetstream.poller import get_poller

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
