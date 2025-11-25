"""Jetstream status route."""

import sys
from pathlib import Path

from flask import Blueprint, jsonify

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jetstream.poller import get_poller
from jetstream.models import PollerStatus

status_bp = Blueprint("jetstream_status", __name__)


@status_bp.route("/status", methods=["GET"])
def get_status():
    """
    Get Jetstream connection and poller status.

    Returns:
    {
        "connected": true,
        "last_poll": "2025-11-25T14:30:00Z",
        "next_poll": "2025-11-25T14:30:30Z",
        "pending_runs": 2,
        "processing_run": "run_abc123",
        "error": null
    }
    """
    poller = get_poller()

    if poller:
        status = poller.status
    else:
        # No poller initialized
        status = PollerStatus(
            connected=False,
            error="Jetstream poller not initialized"
        )

    return jsonify(status.to_dict()), 200
