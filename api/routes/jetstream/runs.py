"""Jetstream runs routes."""

import json
from pathlib import Path

from flask import Blueprint, jsonify, request

from api.jetstream.models import RunStatus
from api.services.run_manager import get_run_manager

runs_bp = Blueprint("jetstream_runs", __name__)


@runs_bp.route("/runs", methods=["GET"])
def list_runs():
    """
    List runs with optional filtering.

    Query params:
        - status: Filter by status (pending, downloading, converting, validating, processing, complete, error)
        - source: Filter by source (jetstream, manual_upload)
        - limit: Max number of runs (default: 100)
        - offset: Number to skip (default: 0)

    Returns:
    {
        "runs": [
            {
                "run_id": "run_2025-11-25T14-30-00Z-abc123",
                "status": "complete",
                "source": "jetstream",
                "jetstream_id": "js_xyz789",
                "created_at": "2025-11-25T14:30:00Z",
                "updated_at": "2025-11-25T14:35:00Z",
                ...
            }
        ],
        "total": 42
    }
    """
    # Parse query parameters
    status_filter = request.args.get("status")
    source_filter = request.args.get("source")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    # Validate status if provided
    status = None
    if status_filter:
        try:
            status = RunStatus(status_filter)
        except ValueError:
            return jsonify({"error": f"Invalid status: {status_filter}"}), 400

    # Get runs from manager
    run_manager = get_run_manager()
    result = run_manager.list_runs(
        status=status,
        source=source_filter,
        limit=limit,
        offset=offset,
    )

    return jsonify(result), 200


@runs_bp.route("/runs/<run_id>", methods=["GET"])
def get_run(run_id: str):
    """
    Get full details for a specific run.

    Returns run state, metadata, processing info, results summary, and file list.
    """
    run_manager = get_run_manager()
    run_state = run_manager.get_run(run_id)

    if not run_state:
        return jsonify({"error": "Run not found"}), 404

    # Build full response
    response = run_state.to_dict()

    # Add output files list
    output_dir = run_manager.get_run_output_dir(run_id)
    if output_dir and output_dir.exists():
        files = []
        for file_path in output_dir.iterdir():
            if file_path.is_file():
                files.append(
                    {
                        "name": file_path.name,
                        "size": file_path.stat().st_size,
                        "url": f"/api/jetstream/runs/{run_id}/files/{file_path.name}",
                    }
                )
        response["output_files"] = files

    # Load jetstream metadata if available
    run_dir = run_manager.get_run_dir(run_id)
    if run_dir:
        metadata_path = run_dir / "jetstream_metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    response["jetstream_metadata"] = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Load manifest if available
        manifest_path = run_dir / "output" / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    response["manifest"] = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

    return jsonify(response), 200


@runs_bp.route("/runs/<run_id>/files/<filename>", methods=["GET"])
def download_run_file(run_id: str, filename: str):
    """Download a specific output file from a run."""
    from flask import send_file
    from werkzeug.utils import secure_filename

    # Sanitize filename
    filename = secure_filename(filename)

    run_manager = get_run_manager()
    output_dir = run_manager.get_run_output_dir(run_id)

    if not output_dir:
        return jsonify({"error": "Run not found"}), 404

    file_path = output_dir / filename
    if not file_path.exists():
        return jsonify({"error": "File not found"}), 404

    return send_file(file_path, as_attachment=True, download_name=filename)
