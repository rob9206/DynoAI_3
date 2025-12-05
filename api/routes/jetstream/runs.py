"""Jetstream runs routes."""

import json
import re
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from api.jetstream.models import RunStatus
from api.services.run_manager import get_run_manager

runs_bp = Blueprint("jetstream_runs", __name__)


def _sanitize_run_id(run_id: str) -> str:
    """
    Sanitize run_id to prevent path traversal attacks.

    Valid run_ids follow the pattern: run_YYYY-MM-DDTHH-MM-SSZ-hexsuffix
    or similar safe alphanumeric patterns with underscores and dashes.

    Args:
        run_id: The raw run_id from the request

    Returns:
        Sanitized run_id safe for filesystem operations

    Raises:
        ValueError: If run_id contains invalid characters
    """
    if not run_id:
        raise ValueError("Run ID cannot be empty")

    # Remove any path separators and parent directory references
    sanitized = run_id.replace("/", "").replace("\\", "").replace("..", "")

    # Only allow alphanumeric, underscore, dash, and limited special chars
    if not re.match(r"^[a-zA-Z0-9_\-]+$", sanitized):
        raise ValueError(f"Invalid run_id format: {run_id}")

    # Ensure we didn't completely sanitize away the ID
    if not sanitized or sanitized != run_id:
        raise ValueError(f"Run ID contains invalid characters: {run_id}")

    return sanitized


def _validate_path_within_base(path: Path, base_dir: Path) -> bool:
    """
    Validate that a resolved path is within the base directory.

    Uses Path.is_relative_to() for safe directory containment checking.
    This prevents false positives like /runs matching /runsomething/file.csv
    that would occur with simple string prefix matching.

    Args:
        path: Path to validate
        base_dir: Base directory that path must be within

    Returns:
        True if path is within base_dir, False otherwise
    """
    try:
        resolved_path = path.resolve()
        resolved_base = base_dir.resolve()
        # Use is_relative_to() for proper directory containment check
        # This is safer than string prefix matching which could have false positives
        return resolved_path.is_relative_to(resolved_base)
    except (OSError, ValueError, TypeError):
        return False


@runs_bp.route("/runs", methods=["GET"])
def list_runs():
    """
    List Jetstream runs.
    ---
    tags:
      - Jetstream
    summary: List runs with optional filtering
    description: |
      Returns a paginated list of analysis runs. Can filter by status and source.
      Supports pagination with limit and offset parameters.
    parameters:
      - name: status
        in: query
        type: string
        required: false
        enum: [pending, downloading, converting, validating, processing, complete, error]
        description: Filter by run status
      - name: source
        in: query
        type: string
        required: false
        enum: [jetstream, manual_upload]
        description: Filter by run source
      - name: limit
        in: query
        type: integer
        required: false
        default: 100
        minimum: 1
        maximum: 1000
        description: Maximum number of runs to return
      - name: offset
        in: query
        type: integer
        required: false
        default: 0
        minimum: 0
        description: Number of runs to skip (for pagination)
    responses:
      200:
        description: List of runs
        schema:
          type: object
          properties:
            runs:
              type: array
              items:
                $ref: '#/definitions/JetstreamRun'
            total:
              type: integer
              description: Total number of runs matching filter
        examples:
          application/json:
            runs:
              - run_id: "run_2025-11-25T14-30-00Z-abc123"
                status: "complete"
                source: "jetstream"
                jetstream_id: "JS-ALPHA-001"
                created_at: "2025-11-25T14:30:00Z"
            total: 42
      400:
        description: Invalid status or pagination parameter
        schema:
          $ref: '#/definitions/Error'
    """
    # Parse query parameters
    status_filter = request.args.get("status")
    source_filter = request.args.get("source")

    try:
        limit = min(int(request.args.get("limit", 100)), 1000)  # Cap at 1000
        offset = max(int(request.args.get("offset", 0)), 0)  # Ensure non-negative
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid limit or offset parameter"}), 400

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
    Get run details.
    ---
    tags:
      - Jetstream
    summary: Get full details for a specific run
    description: |
      Returns comprehensive run information including:
      - Run state and metadata
      - Processing progress and stage
      - Results summary (when complete)
      - List of output files with download URLs
      - Jetstream metadata (if available)
    parameters:
      - name: run_id
        in: path
        type: string
        required: true
        description: Unique run identifier
    responses:
      200:
        description: Run details retrieved successfully
        schema:
          allOf:
            - $ref: '#/definitions/JetstreamRun'
            - type: object
              properties:
                output_files:
                  type: array
                  items:
                    type: object
                    properties:
                      name:
                        type: string
                      size:
                        type: integer
                      url:
                        type: string
                jetstream_metadata:
                  type: object
                manifest:
                  type: object
      400:
        description: Invalid run_id format
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Run not found
        schema:
          $ref: '#/definitions/Error'
    """
    # Sanitize run_id to prevent path traversal
    try:
        safe_run_id = _sanitize_run_id(run_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    run_manager = get_run_manager()
    run_state = run_manager.get_run(safe_run_id)

    if not run_state:
        return jsonify({"error": "Run not found"}), 404

    # Build full response
    response = run_state.to_dict()

    # Add output files list
    output_dir = run_manager.get_run_output_dir(safe_run_id)
    if output_dir and output_dir.exists():
        # Validate output_dir is within expected runs directory
        runs_base = run_manager._runs_dir
        if not _validate_path_within_base(output_dir, runs_base):
            return jsonify({"error": "Invalid run directory"}), 400

        files = []
        for file_path in output_dir.iterdir():
            if file_path.is_file():
                # Use secure_filename for the display name
                safe_name = secure_filename(file_path.name)
                files.append(
                    {
                        "name": safe_name,
                        "size": file_path.stat().st_size,
                        "url": f"/api/jetstream/runs/{safe_run_id}/files/{safe_name}",
                    }
                )
        response["output_files"] = files

    # Load jetstream metadata if available
    run_dir = run_manager.get_run_dir(safe_run_id)
    if run_dir:
        # Validate run_dir is within expected runs directory
        runs_base = run_manager._runs_dir
        if not _validate_path_within_base(run_dir, runs_base):
            return jsonify({"error": "Invalid run directory"}), 400

        metadata_path = run_dir / "jetstream_metadata.json"
        # Double-check the constructed path is still within bounds
        if metadata_path.exists() and _validate_path_within_base(
            metadata_path, runs_base
        ):
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    response["jetstream_metadata"] = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Load manifest if available
        manifest_path = run_dir / "output" / "manifest.json"
        if manifest_path.exists() and _validate_path_within_base(
            manifest_path, runs_base
        ):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    response["manifest"] = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

    return jsonify(response), 200


@runs_bp.route("/runs/<run_id>/files/<filename>", methods=["GET"])
def download_run_file(run_id: str, filename: str):
    """
    Download run file.
    ---
    tags:
      - Jetstream
    summary: Download a specific output file from a run
    description: |
      Download an output file from a Jetstream run. The file list is available
      in the run details endpoint.
    produces:
      - application/octet-stream
      - text/csv
      - application/json
      - text/plain
    parameters:
      - name: run_id
        in: path
        type: string
        required: true
        description: Unique run identifier
      - name: filename
        in: path
        type: string
        required: true
        description: Name of the file to download
    responses:
      200:
        description: File content
        schema:
          type: file
      400:
        description: Invalid run_id or filename
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Run or file not found
        schema:
          $ref: '#/definitions/Error'
    """
    # Sanitize both run_id and filename to prevent path traversal
    try:
        safe_run_id = _sanitize_run_id(run_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Use secure_filename for the filename
    safe_filename = secure_filename(filename)
    if not safe_filename:
        return jsonify({"error": "Invalid filename"}), 400

    run_manager = get_run_manager()
    output_dir = run_manager.get_run_output_dir(safe_run_id)

    if not output_dir:
        return jsonify({"error": "Run not found"}), 404

    # Validate output_dir is within expected runs directory
    runs_base = run_manager._runs_dir
    if not _validate_path_within_base(output_dir, runs_base):
        return jsonify({"error": "Invalid run directory"}), 400

    file_path = output_dir / safe_filename

    # Final validation: ensure file_path is within output_dir
    if not _validate_path_within_base(file_path, output_dir):
        return jsonify({"error": "Invalid file path"}), 400

    if not file_path.exists():
        return jsonify({"error": "File not found"}), 404

    return send_file(file_path, as_attachment=True, download_name=safe_filename)
