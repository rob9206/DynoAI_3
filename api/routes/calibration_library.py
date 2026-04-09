"""
Calibration Library API routes.

Endpoints:
  - POST   /api/v3/calibration-library/ingest
  - GET    /api/v3/calibration-library
  - GET    /api/v3/calibration-library/<calibration_id>
  - DELETE /api/v3/calibration-library/<calibration_id>
  - POST   /api/v3/calibration-library/blend
  - GET    /api/v3/calibration-library/stats
"""

from __future__ import annotations

import json

from flask import Blueprint, jsonify, request

from api.errors import NotFoundError, ValidationError, with_error_handling

calibration_library_bp = Blueprint(
    "calibration_library",
    __name__,
    url_prefix="/api/v3/calibration-library",
)


@calibration_library_bp.route("/ingest", methods=["POST"])
@with_error_handling
def ingest_calibration():
    """Ingest a PVV file into the calibration library."""
    file = request.files.get("file")
    if file is None:
        raise ValidationError("multipart field 'file' is required")
    if not file.filename:
        raise ValidationError("Uploaded file must have a filename")
    if not file.filename.lower().endswith(".pvv"):
        raise ValidationError("Only .pvv files are supported")

    config_raw = request.form.get("config")
    if not config_raw:
        raise ValidationError("form field 'config' is required (JSON)")

    try:
        config_payload = json.loads(config_raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("form field 'config' must be valid JSON") from exc

    operator = request.form.get("operator", "unknown")
    notes = request.form.get("notes", "")

    from ..services.calibration_library_service import ingest_calibration as _ingest

    result = _ingest(
        file=file,
        config_dict=config_payload,
        operator=operator,
        notes=notes,
    )
    return jsonify(result), 201


@calibration_library_bp.route("", methods=["GET"])
@with_error_handling
def list_calibrations():
    """List calibration library entries."""
    engine_family = request.args.get("engine_family")
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)

    if limit is None or limit < 0:
        raise ValidationError("limit must be >= 0")
    if offset is None or offset < 0:
        raise ValidationError("offset must be >= 0")

    from ..services.calibration_library_service import list_calibrations as _list

    result = _list(engine_family=engine_family, limit=limit, offset=offset)
    return jsonify(result)


@calibration_library_bp.route("/<calibration_id>", methods=["GET"])
@with_error_handling
def get_calibration(calibration_id: str):
    """Get details for a calibration library entry."""
    from ..services.calibration_library_service import get_calibration as _get

    try:
        result = _get(calibration_id)
    except KeyError:
        raise NotFoundError(resource="Calibration", identifier=calibration_id)

    return jsonify(result)


@calibration_library_bp.route("/<calibration_id>", methods=["DELETE"])
@with_error_handling
def delete_calibration(calibration_id: str):
    """Delete a calibration library entry."""
    from ..services.calibration_library_service import delete_calibration as _delete

    deleted = _delete(calibration_id)
    if not deleted:
        raise NotFoundError(resource="Calibration", identifier=calibration_id)

    return jsonify({"deleted": True, "calibration_id": calibration_id})


@calibration_library_bp.route("/blend", methods=["POST"])
@with_error_handling
def blend_calibration():
    """Blend top-N matched calibrations for a hardware config."""
    payload = request.get_json()
    if not payload:
        raise ValidationError("Request body required")

    top_n = int(payload.get("top_n", 5))
    if top_n <= 0:
        raise ValidationError("top_n must be > 0")
    min_similarity = float(payload.get("min_similarity", 0.0))
    if min_similarity < 0.0 or min_similarity > 1.0:
        raise ValidationError("min_similarity must be between 0 and 1")

    config_payload = payload.get("config", payload)

    from ..services.calibration_library_service import blend_calibration as _blend

    result = _blend(
        config_dict=config_payload,
        top_n=top_n,
        min_similarity=min_similarity,
    )
    return jsonify(result)


@calibration_library_bp.route("/stats", methods=["GET"])
@with_error_handling
def calibration_stats():
    """Get calibration library aggregate stats."""
    from ..services.calibration_library_service import get_stats as _stats

    return jsonify(_stats())
