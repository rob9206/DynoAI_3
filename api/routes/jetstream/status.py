"""Jetstream status route."""

from flask import Blueprint, jsonify

from api.jetstream.models import PollerStatus
from api.jetstream.poller import get_poller
from api.jetstream.stub_data import get_stub_status, is_stub_mode_enabled

status_bp = Blueprint("jetstream_status", __name__)


@status_bp.route("/status", methods=["GET"])
def get_status():
    """
    Get Jetstream status.
    ---
    tags:
      - Jetstream
    summary: Get Jetstream connection and poller status
    description: |
      Returns the current status of the Jetstream integration including:
      - Connection status
      - Last and next poll timestamps
      - Number of pending runs
      - Currently processing run (if any)
      - Any error messages
    responses:
      200:
        description: Jetstream status
        schema:
          $ref: '#/definitions/JetstreamStatus'
        examples:
          application/json:
            connected: true
            last_poll: "2025-11-25T14:30:00Z"
            next_poll: "2025-11-25T14:30:30Z"
            pending_runs: 2
            processing_run: "run_abc123"
            error: null
    """
    if is_stub_mode_enabled():
        return jsonify(get_stub_status()), 200

    poller = get_poller()

    if poller:
        status = poller.status
    else:
        # No poller initialized
        status = PollerStatus(connected=False, error="Jetstream poller not initialized")

    return jsonify(status.to_dict()), 200
