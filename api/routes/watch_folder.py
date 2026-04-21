"""Power Core watch-folder routes."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, jsonify, request

from api.services.run_ingestion import promote_path
from api.services.watch_folder import get_service

watch_bp = Blueprint("powercore_watch", __name__, url_prefix="/api/powercore/watch")


@watch_bp.route("/status", methods=["GET"])
def watch_status():
    """Get watch-folder service status."""
    return jsonify(get_service().status())


@watch_bp.route("/recent", methods=["GET"])
def watch_recent():
    """Get recent watch-folder events."""
    try:
        limit = int(request.args.get("limit", "20"))
    except ValueError:
        limit = 20
    bounded_limit = max(1, min(limit, 200))
    return jsonify({"events": get_service().recent(limit=bounded_limit)})


@watch_bp.route("/stream", methods=["GET"])
def watch_stream():
    """SSE stream for watch-folder events."""
    return Response(
        get_service().stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@watch_bp.route("/rescan", methods=["POST"])
def watch_rescan():
    """Rescan one configured watch folder with bounded file count."""
    data = request.get_json(silent=True) or {}
    folder_raw = data.get("folder")
    if not folder_raw:
        return jsonify({"error": "Missing required field: folder"}), 400

    try:
        limit = int(data.get("limit", 50))
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400

    try:
        summary = get_service().rescan(Path(str(folder_raw)), limit=limit)
        return jsonify(summary)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


@watch_bp.route("/promote", methods=["POST"])
def watch_promote():
    """Manually promote an already-watched file path into runs/."""
    data = request.get_json(silent=True) or {}
    path_raw = data.get("path")
    if not path_raw:
        return jsonify({"error": "Missing required field: path"}), 400

    path = Path(str(path_raw)).expanduser().resolve(strict=False)
    if not path.exists() or not path.is_file():
        return jsonify({"error": "path must exist and be a file"}), 400

    service = get_service()
    roots = [p.resolve(strict=False) for p in service.folders]
    if not roots:
        return jsonify({"error": "watch service has no configured folders"}), 400
    if not any(_is_within(path, root) for root in roots):
        return jsonify({"error": "path must be inside a configured watch folder"}), 400

    try:
        result = promote_path(path, runs_dir=Path("runs"))
        return jsonify(result.to_json())
    except Exception as exc:
        return jsonify({"error": f"promotion failed: {exc}"}), 400


@watch_bp.route("/promotions", methods=["GET"])
def watch_promotions():
    """List recent run promotion events."""
    try:
        limit = int(request.args.get("limit", "20"))
    except ValueError:
        limit = 20
    bounded_limit = max(1, min(limit, 200))
    events = [
        event
        for event in get_service().recent(limit=200)
        if event.get("event_type") == "run_promoted"
    ]
    return jsonify({"events": events[:bounded_limit]})
