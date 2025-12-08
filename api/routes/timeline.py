"""
VE Table Time Machine - Timeline API Routes

Endpoints for session replay, snapshots, and diff visualization.
"""

import re
from pathlib import Path
from typing import Any, Dict

from flask import Blueprint, jsonify, request, send_file

from api.config import RUNS_DIR
from api.errors import APIError
from api.services.session_logger import SessionLogger

timeline_bp = Blueprint("timeline", __name__, url_prefix="/api/timeline")


def validate_snapshot_id(snapshot_id: str) -> str:
    """
    Validate snapshot ID format to prevent path traversal.

    Expected format: snap_<8 hex chars>
    """
    if not re.match(r"^snap_[a-f0-9]{8}$", snapshot_id):
        raise APIError(f"Invalid snapshot ID format: {snapshot_id}", status_code=400)
    return snapshot_id


def get_run_dir(run_id: str) -> Path:
    """Get run directory path, validating it exists."""
    # Check runs folder first (for Jetstream runs)
    run_dir = Path(RUNS_DIR) / run_id
    if run_dir.exists():
        return run_dir

    # Check outputs folder (for direct uploads)
    from api.config import get_config

    config = get_config()
    output_dir = config.storage.output_folder / run_id
    if output_dir.exists():
        return output_dir

    raise APIError(f"Run not found: {run_id}", status_code=404)


@timeline_bp.route("/<run_id>", methods=["GET"])
def get_timeline(run_id: str) -> Any:
    """
    Get the complete timeline for a run.

    Query params:
        limit: Maximum events to return (default: 50, max: 200)
        offset: Number of events to skip (default: 0)

    Returns:
        {
            "run_id": "...",
            "summary": {...},
            "events": [...],
            "pagination": {
                "total": N,
                "limit": M,
                "offset": K,
                "has_more": bool
            }
        }
    """
    run_dir = get_run_dir(run_id)
    logger = SessionLogger(run_dir)

    # Parse pagination params
    try:
        limit = min(int(request.args.get("limit", 50)), 200)  # Cap at 200
        offset = max(int(request.args.get("offset", 0)), 0)
    except (ValueError, TypeError):
        raise APIError("Invalid pagination parameters", status_code=400)

    all_events = logger.get_timeline()
    total = len(all_events)

    # Paginate events
    paginated_events = all_events[offset: offset + limit]

    return jsonify(
        {
            "run_id": run_id,
            "summary": logger.get_session_summary(),
            "events": paginated_events,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total,
            },
        }
    )


@timeline_bp.route("/<run_id>/events/<event_id>", methods=["GET"])
def get_event(run_id: str, event_id: str) -> Any:
    """
    Get details for a specific timeline event.

    Returns:
        TimelineEvent object with full metadata
    """
    run_dir = get_run_dir(run_id)
    logger = SessionLogger(run_dir)

    event = logger.get_event(event_id)
    if not event:
        raise APIError(f"Event not found: {event_id}", status_code=404)

    return jsonify(event)


@timeline_bp.route("/<run_id>/snapshots/<snapshot_id>", methods=["GET"])
def get_snapshot(run_id: str, snapshot_id: str) -> Any:
    """
    Get parsed data for a snapshot.

    Query params:
        format: "json" (default) or "csv"

    Returns:
        JSON: { "rpm": [...], "load": [...], "data": [[...], ...] }
        CSV: Raw CSV file download
    """
    # Validate snapshot ID format
    snapshot_id = validate_snapshot_id(snapshot_id)

    run_dir = get_run_dir(run_id)
    logger = SessionLogger(run_dir)

    output_format = request.args.get("format", "json")

    if output_format == "csv":
        path = logger.get_snapshot_path(snapshot_id)
        if not path:
            raise APIError(f"Snapshot not found: {snapshot_id}", status_code=404)
        return send_file(path, mimetype="text/csv", as_attachment=True)

    data = logger.get_snapshot_data(snapshot_id)
    if not data:
        raise APIError(f"Snapshot not found: {snapshot_id}", status_code=404)

    return jsonify({"snapshot_id": snapshot_id, **data})


@timeline_bp.route("/<run_id>/diff", methods=["GET"])
def get_diff(run_id: str) -> Any:
    """
    Compute difference between two snapshots.

    Query params:
        from: Source snapshot ID
        to: Target snapshot ID

    Returns:
        {
            "rpm": [...],
            "load": [...],
            "diff": [[...], ...],
            "summary": {
                "cells_changed": N,
                "avg_change": X,
                ...
            },
            "changes": [top 20 changed cells]
        }
    """
    run_dir = get_run_dir(run_id)
    logger = SessionLogger(run_dir)

    from_id = request.args.get("from")
    to_id = request.args.get("to")

    if not from_id or not to_id:
        raise APIError(
            "Both 'from' and 'to' snapshot IDs are required", status_code=400
        )

    diff = logger.compute_diff(from_id, to_id)
    if not diff:
        raise APIError(
            f"Could not compute diff between {from_id} and {to_id}. "
            "Check that both snapshots exist and have matching dimensions.",
            status_code=400,
        )

    return jsonify(diff)


@timeline_bp.route("/<run_id>/compare-events", methods=["GET"])
def compare_events(run_id: str) -> Any:
    """
    Compare VE state between two events (convenience endpoint).

    Query params:
        from_event: Source event ID (uses snapshot_after)
        to_event: Target event ID (uses snapshot_after)

    Returns:
        Diff data plus event metadata
    """
    run_dir = get_run_dir(run_id)
    logger = SessionLogger(run_dir)

    from_event_id = request.args.get("from_event")
    to_event_id = request.args.get("to_event")

    if not from_event_id or not to_event_id:
        raise APIError(
            "Both 'from_event' and 'to_event' IDs are required", status_code=400
        )

    from_event = logger.get_event(from_event_id)
    to_event = logger.get_event(to_event_id)

    if not from_event:
        raise APIError(f"Event not found: {from_event_id}", status_code=404)
    if not to_event:
        raise APIError(f"Event not found: {to_event_id}", status_code=404)

    # Get the "after" snapshot from each event
    from_snapshot = from_event.get("snapshot_after")
    to_snapshot = to_event.get("snapshot_after")

    if not from_snapshot:
        raise APIError(f"Event {from_event_id} has no snapshot_after", status_code=400)
    if not to_snapshot:
        raise APIError(f"Event {to_event_id} has no snapshot_after", status_code=400)

    diff = logger.compute_diff(from_snapshot["id"], to_snapshot["id"])
    if not diff:
        raise APIError("Could not compute diff between events", status_code=400)

    return jsonify({"from_event": from_event, "to_event": to_event, **diff})


@timeline_bp.route("/<run_id>/replay/<int:step>", methods=["GET"])
def replay_step(run_id: str, step: int) -> Any:
    """
    Get the VE state at a specific step in the timeline.

    Args:
        step: 1-based step number (sequence number)

    Returns:
        Event at that step plus its snapshot data
    """
    run_dir = get_run_dir(run_id)
    logger = SessionLogger(run_dir)

    timeline = logger.get_timeline()

    if step < 1 or step > len(timeline):
        raise APIError(
            f"Step {step} out of range. Timeline has {len(timeline)} events.",
            status_code=400,
        )

    event = timeline[step - 1]

    # Get snapshot data (prefer after, fallback to before)
    snapshot_id = None
    if event.get("snapshot_after"):
        snapshot_id = event["snapshot_after"]["id"]
    elif event.get("snapshot_before"):
        snapshot_id = event["snapshot_before"]["id"]

    snapshot_data = None
    if snapshot_id:
        snapshot_data = logger.get_snapshot_data(snapshot_id)

    return jsonify(
        {
            "step": step,
            "total_steps": len(timeline),
            "event": event,
            "snapshot": snapshot_data,
            "has_previous": step > 1,
            "has_next": step < len(timeline),
        }
    )
