"""
Tuning Workspace REST API.

Endpoints:

    GET    /api/workspace/vehicles
    POST   /api/workspace/vehicles
    GET    /api/workspace/vehicles/<vid>
    PATCH  /api/workspace/vehicles/<vid>

    GET    /api/workspace/vehicles/<vid>/sessions
    POST   /api/workspace/vehicles/<vid>/sessions
    GET    /api/workspace/vehicles/<vid>/sessions/<sid>
    PATCH  /api/workspace/vehicles/<vid>/sessions/<sid>
    GET    /api/workspace/vehicles/<vid>/sessions/<sid>/status

    POST   /api/workspace/vehicles/<vid>/sessions/<sid>/iterations
    GET    /api/workspace/vehicles/<vid>/sessions/<sid>/iterations

    POST   /api/workspace/vehicles/<vid>/sessions/<sid>/upload
           -- multipart form: files[]=<one or more>, iteration_id=<iter_N> (optional)

    GET    /api/workspace/vehicles/<vid>/sessions/<sid>/iterations/<iid>/pulls
    GET    /api/workspace/vehicles/<vid>/sessions/<sid>/iterations/<iid>/patches
    GET    /api/workspace/vehicles/<vid>/sessions/<sid>/iterations/<iid>/analyses

The /upload route runs each file through the ingest sniffer and routes by content:
PVV -> base tune or patch; WP8/TXT/CSV -> pulls.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from api.errors import ValidationError, with_error_handling
from api.services.ingest.sniffer import classify_upload
from api.services.ingest.watcher import get_watcher
from api.services.sessions.dispatch_readiness import evaluate_dispatch_readiness
from api.services.sessions.p0_plausibility_checker import evaluate_p0_plausibility
from api.services.sessions.phased_pull_controller import (
    compute_phase_snapshot,
    mark_phase_complete,
)
from api.services.tuning_workspace import (
    WorkspaceError,
    get_workspace,
)
from api.services.workspace_analyzer import analyze_iteration

logger = logging.getLogger(__name__)
workspace_bp = Blueprint("workspace", __name__, url_prefix="/api/workspace")


def _not_found_error(message: str = "resource not found"):
    """Return sanitized NOT_FOUND payload without leaking internals."""
    return jsonify({"error": {"code": "NOT_FOUND", "message": message}}), 404

# =============================================================================
# Vehicles
# =============================================================================


@workspace_bp.route("/vehicles", methods=["GET"])
@with_error_handling
def list_vehicles():
    ws = get_workspace()
    return jsonify([v.to_dict() for v in ws.list_vehicles()]), 200


@workspace_bp.route("/vehicles", methods=["POST"])
@with_error_handling
def create_vehicle():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("name is required")
    try:
        vehicle = get_workspace().create_vehicle(
            name=name,
            year=data.get("year"),
            make=data.get("make", ""),
            model=data.get("model", ""),
            displacement_ci=data.get("displacement_ci"),
            vehicle_id=data.get("id"),
            watch_folder=data.get("watch_folder"),
            notes=data.get("notes", ""),
        )
    except WorkspaceError as exc:
        raise ValidationError(str(exc)) from exc
    return jsonify(vehicle.to_dict()), 201


@workspace_bp.route("/vehicles/<vid>", methods=["GET"])
@with_error_handling
def get_vehicle(vid: str):
    try:
        vehicle = get_workspace().get_vehicle(vid)
    except WorkspaceError:
        return _not_found_error()
    return jsonify(vehicle.to_dict()), 200


@workspace_bp.route("/vehicles/<vid>", methods=["PATCH"])
@with_error_handling
def patch_vehicle(vid: str):
    data = request.get_json(silent=True) or {}
    try:
        vehicle = get_workspace().update_vehicle(vid, **data)
    except WorkspaceError:
        return _not_found_error()
    return jsonify(vehicle.to_dict()), 200


# =============================================================================
# Sessions
# =============================================================================


@workspace_bp.route("/vehicles/<vid>/sessions", methods=["GET"])
@with_error_handling
def list_sessions(vid: str):
    try:
        get_workspace().get_vehicle(vid)
    except WorkspaceError:
        return _not_found_error()
    sessions = get_workspace().list_sessions(vid)
    return jsonify([s.to_dict() for s in sessions]), 200


@workspace_bp.route("/vehicles/<vid>/sessions", methods=["POST"])
@with_error_handling
def create_session(vid: str):
    data = request.get_json(silent=True) or {}
    try:
        session = get_workspace().create_session(
            vehicle_id=vid,
            session_id=data.get("id"),
            notes=data.get("notes", ""),
        )
    except WorkspaceError as exc:
        raise ValidationError(str(exc)) from exc
    return jsonify(session.to_dict()), 201


@workspace_bp.route("/vehicles/<vid>/sessions/<sid>", methods=["GET"])
@with_error_handling
def get_session(vid: str, sid: str):
    try:
        session = get_workspace().get_session(vid, sid)
    except WorkspaceError:
        return _not_found_error()
    return jsonify(session.to_dict()), 200


@workspace_bp.route("/vehicles/<vid>/sessions/<sid>", methods=["PATCH"])
@with_error_handling
def patch_session(vid: str, sid: str):
    data = request.get_json(silent=True) or {}
    try:
        session = get_workspace().update_session(vid, sid, **data)
    except WorkspaceError:
        return _not_found_error()
    return jsonify(session.to_dict()), 200


@workspace_bp.route("/vehicles/<vid>/sessions/<sid>/v3", methods=["GET"])
@with_error_handling
def get_session_v3(vid: str, sid: str):
    ws = get_workspace()
    try:
        session = ws.get_session(vid, sid)
    except WorkspaceError:
        return _not_found_error()
    if not session.v3:
        return (
            jsonify(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"session has no v3 payload: {vid}/{sid}",
                    }
                }
            ),
            404,
        )
    return jsonify(session.v3), 200


@workspace_bp.route("/vehicles/<vid>/sessions/<sid>/v3", methods=["POST"])
@with_error_handling
def upsert_session_v3(vid: str, sid: str):
    ws = get_workspace()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("v3 payload must be a JSON object")
    payload.setdefault("schema_version", "dynoai.session.v3")
    payload.setdefault("session_id", sid)
    try:
        session = ws.set_session_v3(vid, sid, payload)
    except WorkspaceError:
        return _not_found_error()
    return jsonify(session.to_dict()), 200


@workspace_bp.route(
    "/vehicles/<vid>/sessions/<sid>/v3/resolve_blocker", methods=["POST"]
)
@with_error_handling
def resolve_session_v3_blocker(vid: str, sid: str):
    ws = get_workspace()
    data = request.get_json(silent=True) or {}
    field_name = (data.get("field") or "").strip()
    if not field_name:
        raise ValidationError("field is required")
    try:
        session = ws.resolve_session_v3_blocker(
            vid,
            sid,
            field_name=field_name,
            resolved_by=data.get("resolved_by"),
            evidence=data.get("evidence"),
        )
    except WorkspaceError:
        return _not_found_error()
    return jsonify(session.to_dict()), 200


@workspace_bp.route(
    "/vehicles/<vid>/sessions/<sid>/dispatch_readiness", methods=["GET"]
)
@with_error_handling
def get_dispatch_readiness(vid: str, sid: str):
    ws = get_workspace()
    try:
        session = ws.get_session(vid, sid)
    except WorkspaceError:
        return _not_found_error()
    status = ws.compute_status(vid, sid)
    readiness = evaluate_dispatch_readiness(session, status)
    return jsonify(readiness), 200


@workspace_bp.route("/vehicles/<vid>/sessions/<sid>/phases", methods=["GET"])
@with_error_handling
def get_session_phases(vid: str, sid: str):
    ws = get_workspace()
    try:
        v3 = ws.get_session_v3(vid, sid)
    except WorkspaceError:
        return _not_found_error()
    if not v3:
        return (
            jsonify(
                {"error": {"code": "NOT_FOUND", "message": "session has no v3 payload"}}
            ),
            404,
        )
    return jsonify(compute_phase_snapshot(v3).to_dict()), 200


@workspace_bp.route("/vehicles/<vid>/sessions/<sid>/phases/complete", methods=["POST"])
@with_error_handling
def complete_session_phase(vid: str, sid: str):
    ws = get_workspace()
    data = request.get_json(silent=True) or {}
    phase_id = (data.get("phase_id") or "").strip()
    if not phase_id:
        raise ValidationError("phase_id is required")
    try:
        v3 = ws.get_session_v3(vid, sid)
    except WorkspaceError:
        return _not_found_error()
    if not v3:
        return (
            jsonify(
                {"error": {"code": "NOT_FOUND", "message": "session has no v3 payload"}}
            ),
            404,
        )

    try:
        updated_payload = mark_phase_complete(v3, phase_id)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    ws.set_session_v3(vid, sid, updated_payload)
    return jsonify(compute_phase_snapshot(updated_payload).to_dict()), 200


@workspace_bp.route("/vehicles/<vid>/sessions/<sid>/p0_plausibility", methods=["POST"])
@with_error_handling
def run_p0_plausibility(vid: str, sid: str):
    ws = get_workspace()
    data = request.get_json(silent=True) or {}
    try:
        session = ws.get_session(vid, sid)
        vehicle = ws.get_vehicle(vid)
    except WorkspaceError:
        return _not_found_error()

    v3 = session.v3 or {}
    build = v3.get("build_spec") if isinstance(v3, dict) else {}
    known_ci = data.get("known_displacement_ci")
    if known_ci is None and isinstance(build, dict):
        known_ci = build.get("displacement_ci")
    if known_ci is None:
        known_ci = vehicle.displacement_ci
    if known_ci is None:
        raise ValidationError("known_displacement_ci is required")

    result = evaluate_p0_plausibility(
        known_displacement_ci=float(known_ci),
        measured_displacement_ci=data.get("measured_displacement_ci"),
        peak_tq_ftlb=data.get("peak_tq_ftlb"),
        peak_tq_rpm=data.get("peak_tq_rpm"),
        bmep_psi=data.get("bmep_psi"),
        bsfc_lb_hp_hr=data.get("bsfc_lb_hp_hr"),
    )

    checks = v3.setdefault("checks", {})
    checks["p0_plausibility"] = result.to_dict()
    session = ws.set_session_v3(vid, sid, v3)
    return (
        jsonify({"p0_plausibility": result.to_dict(), "session": session.to_dict()}),
        200,
    )


@workspace_bp.route("/vehicles/<vid>/sessions/<sid>/status", methods=["GET"])
@with_error_handling
def get_session_status(vid: str, sid: str):
    status = get_workspace().compute_status(vid, sid)
    return jsonify(status.to_dict()), 200


# =============================================================================
# Iterations
# =============================================================================


@workspace_bp.route("/vehicles/<vid>/sessions/<sid>/iterations", methods=["GET"])
@with_error_handling
def list_iterations(vid: str, sid: str):
    try:
        get_workspace().get_session(vid, sid)
    except WorkspaceError:
        return _not_found_error()
    iters = get_workspace().list_iterations(vid, sid)
    return jsonify([i.to_dict() for i in iters]), 200


@workspace_bp.route("/vehicles/<vid>/sessions/<sid>/iterations", methods=["POST"])
@with_error_handling
def create_iteration(vid: str, sid: str):
    data = request.get_json(silent=True) or {}
    try:
        iteration = get_workspace().create_iteration(
            vid, sid, patch_filename=data.get("patch_filename")
        )
    except WorkspaceError as exc:
        raise ValidationError(str(exc)) from exc
    return jsonify(iteration.to_dict()), 201


# =============================================================================
# Artifact listings
# =============================================================================


@workspace_bp.route(
    "/vehicles/<vid>/sessions/<sid>/iterations/<iid>/pulls", methods=["GET"]
)
@with_error_handling
def list_pulls(vid: str, sid: str, iid: str):
    ws = get_workspace()
    try:
        ws.get_iteration(vid, sid, iid)
    except WorkspaceError:
        return _not_found_error()
    files = ws.list_pulls(vid, sid, iid)
    return jsonify([_file_summary(p) for p in files]), 200


@workspace_bp.route(
    "/vehicles/<vid>/sessions/<sid>/iterations/<iid>/patches", methods=["GET"]
)
@with_error_handling
def list_patches(vid: str, sid: str, iid: str):
    ws = get_workspace()
    try:
        ws.get_iteration(vid, sid, iid)
    except WorkspaceError:
        return _not_found_error()
    files = ws.list_patches(vid, sid, iid)
    return jsonify([_file_summary(p) for p in files]), 200


@workspace_bp.route(
    "/vehicles/<vid>/sessions/<sid>/iterations/<iid>/analyses", methods=["GET"]
)
@with_error_handling
def list_analyses(vid: str, sid: str, iid: str):
    ws = get_workspace()
    try:
        ws.get_iteration(vid, sid, iid)
    except WorkspaceError:
        return _not_found_error()
    files = ws.list_analyses(vid, sid, iid)
    return jsonify([_file_summary(p) for p in files]), 200


# =============================================================================
# Analyze
# =============================================================================


@workspace_bp.route("/vehicles/<vid>/sessions/<sid>/analyze", methods=["POST"])
@with_error_handling
def analyze_active_iteration(vid: str, sid: str):
    """Run AutoTune analysis on the active (or specified) iteration."""
    data = request.get_json(silent=True) or {}
    iteration_id = data.get("iteration_id")
    try:
        result = analyze_iteration(vid, sid, iteration_id)
    except WorkspaceError:
        return _not_found_error()
    status_code = 200 if result.success else 400
    return jsonify(result.to_dict()), status_code


@workspace_bp.route(
    "/vehicles/<vid>/sessions/<sid>/iterations/<iid>/analyze",
    methods=["POST"],
)
@with_error_handling
def analyze_specific_iteration(vid: str, sid: str, iid: str):
    try:
        result = analyze_iteration(vid, sid, iid)
    except WorkspaceError:
        return _not_found_error()
    status_code = 200 if result.success else 400
    return jsonify(result.to_dict()), status_code


# =============================================================================
# Smart upload
# =============================================================================


@workspace_bp.route("/vehicles/<vid>/sessions/<sid>/upload", methods=["POST"])
@with_error_handling
def upload_to_session(vid: str, sid: str):
    """Accept one or more files, sniff content, route to the right slot."""
    ws = get_workspace()

    try:
        ws.get_session(vid, sid)
    except WorkspaceError:
        return _not_found_error()

    files = request.files.getlist("files")
    if not files:
        single = request.files.get("file")
        if single:
            files = [single]
    if not files:
        raise ValidationError("no files uploaded (field must be 'files' or 'file')")

    iteration_override = request.form.get("iteration_id") or request.args.get(
        "iteration_id"
    )
    treat_as = (request.form.get("treat_as") or "").strip().lower() or None

    active_iteration = None
    if iteration_override:
        try:
            active_iteration = ws.get_iteration(vid, sid, iteration_override)
        except WorkspaceError as exc:
            raise ValidationError(str(exc)) from exc
    else:
        try:
            active_iteration = ws.get_active_iteration(vid, sid)
        except WorkspaceError as exc:
            raise ValidationError(str(exc)) from exc

    routed: list[dict] = []
    rejected: list[dict] = []

    for fs in files:
        if not fs or not fs.filename:
            rejected.append({"name": "<empty>", "reason": "no filename"})
            continue

        raw = fs.read()
        if not raw:
            rejected.append({"name": fs.filename, "reason": "empty file"})
            continue

        safe_name = secure_filename(fs.filename) or "upload.bin"

        try:
            classification = classify_upload(raw, safe_name, override=treat_as)
        except Exception:
            logger.exception("sniffer failed on %s", safe_name)
            rejected.append({"name": safe_name, "reason": "could not classify file"})
            continue

        file_type = classification.get("file_type")
        detail = classification.get("detail", {})
        target_slot = classification.get("routed_to", "pulls")

        try:
            if target_slot == "base_tune":
                result = ws.set_base_tune(vid, sid, raw)
                routed.append(
                    {
                        "name": safe_name,
                        "type": file_type,
                        "slot": "base_tune",
                        "path": result["path"],
                        "sha256": result["sha256"],
                        "detail": detail,
                    }
                )
            elif target_slot == "patches":
                dst = ws.add_patch(vid, sid, active_iteration.id, safe_name, raw)
                routed.append(
                    {
                        "name": safe_name,
                        "type": file_type,
                        "slot": "patches",
                        "iteration_id": active_iteration.id,
                        "path": str(dst),
                        "detail": detail,
                    }
                )
            else:
                dst = ws.add_pull(vid, sid, active_iteration.id, safe_name, raw)
                routed.append(
                    {
                        "name": safe_name,
                        "type": file_type,
                        "slot": "pulls",
                        "iteration_id": active_iteration.id,
                        "path": str(dst),
                        "detail": detail,
                    }
                )
        except WorkspaceError as exc:
            rejected.append({"name": safe_name, "reason": str(exc)})
        except Exception:
            logger.exception("routing failed for %s", safe_name)
            rejected.append(
                {"name": safe_name, "reason": "server error while routing file"}
            )

    status = ws.compute_status(vid, sid)
    return (
        jsonify(
            {
                "routed": routed,
                "rejected": rejected,
                "status": status.to_dict(),
                "active_iteration_id": active_iteration.id,
            }
        ),
        200 if routed else 400,
    )


# =============================================================================
# Hot-folder watcher
# =============================================================================


@workspace_bp.route("/watcher/start", methods=["POST"])
@with_error_handling
def watcher_start():
    watcher = get_watcher()
    ok = watcher.start()
    return (
        jsonify(
            {
                "available": watcher.available,
                "running": ok,
                "watched": watcher.rescan() if ok else 0,
            }
        ),
        200,
    )


@workspace_bp.route("/watcher/stop", methods=["POST"])
@with_error_handling
def watcher_stop():
    get_watcher().stop()
    return jsonify({"running": False}), 200


@workspace_bp.route("/watcher/events", methods=["GET"])
@with_error_handling
def watcher_events():
    limit = int(request.args.get("limit", 50))
    return jsonify(get_watcher().recent_events(limit=limit)), 200


# =============================================================================
# Helpers
# =============================================================================


def _file_summary(path) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "path": str(path),
    }
