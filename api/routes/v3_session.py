"""
DynoAI v3.0 Session API Routes
=================================

REST endpoints for the Accelerated Calibration Platform.

Prefix: ``/api/v3``
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from api.errors import NotFoundError, ValidationError, with_error_handling

logger = logging.getLogger(__name__)

v3_session_bp = Blueprint("v3_session", __name__, url_prefix="/api/v3")


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

@v3_session_bp.route("/session", methods=["POST"])
@with_error_handling
def create_session():
    """Create and initialize a new v3 tuning session."""
    data = request.get_json()
    if not data:
        raise ValidationError("Request body required (hardware config)")

    if "engine_family" not in data:
        raise ValidationError("engine_family is required")

    from api.services.v3_session_service import create_session as _create
    result = _create(data)
    return jsonify(result), 201


@v3_session_bp.route("/session/<session_id>", methods=["GET"])
@with_error_handling
def get_session(session_id: str):
    """Get session status."""
    from api.services.v3_session_service import get_session as _get
    try:
        result = _get(session_id)
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)
    return jsonify(result)


@v3_session_bp.route("/sessions", methods=["GET"])
@with_error_handling
def list_sessions():
    """List all active v3 sessions."""
    from api.services.v3_session_service import list_sessions as _list
    return jsonify({"sessions": _list()})


# ---------------------------------------------------------------------------
# Pull ingestion
# ---------------------------------------------------------------------------

@v3_session_bp.route("/session/<session_id>/pull", methods=["POST"])
@with_error_handling
def ingest_pull(session_id: str):
    """Ingest pull data into a session."""
    data = request.get_json()
    if not data:
        raise ValidationError("Request body required (pull data)")

    for field in ("rpm", "map_kpa", "ve"):
        if field not in data:
            raise ValidationError(f"'{field}' array is required")

    from api.services.v3_session_service import ingest_pull as _ingest
    try:
        result = _ingest(
            session_id,
            rpm=data["rpm"],
            map_kpa=data["map_kpa"],
            ve=data["ve"],
        )
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Imports (base VE + corrections)
# ---------------------------------------------------------------------------

@v3_session_bp.route("/session/<session_id>/import-ve", methods=["POST"])
@with_error_handling
def import_base_ve(session_id: str):
    """Import a base VE table and seed the GP surrogate."""
    data = request.get_json()
    if not data:
        raise ValidationError("Request body required (base VE import)")

    for field in ("ve_table", "rpm_bins", "map_bins"):
        if field not in data:
            raise ValidationError(f"'{field}' is required")

    from api.services.v3_session_service import import_base_ve as _import
    try:
        result = _import(
            session_id,
            ve_table=data["ve_table"],
            rpm_bins=data["rpm_bins"],
            map_bins=data["map_bins"],
        )
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)
    return jsonify(result)


@v3_session_bp.route("/session/<session_id>/import-corrections", methods=["POST"])
@with_error_handling
def import_corrections(session_id: str):
    """Import correction grid into an active session."""
    data = request.get_json()
    if not data:
        raise ValidationError("Request body required (corrections import)")

    for field in ("corrections", "rpm_bins", "map_bins", "format"):
        if field not in data:
            raise ValidationError(f"'{field}' is required")

    from api.services.v3_session_service import import_corrections as _import
    try:
        result = _import(
            session_id,
            corrections=data["corrections"],
            rpm_bins=data["rpm_bins"],
            map_bins=data["map_bins"],
            fmt=data["format"],
        )
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Finalize
# ---------------------------------------------------------------------------

@v3_session_bp.route("/session/<session_id>/finalize", methods=["POST"])
@with_error_handling
def finalize_session(session_id: str):
    """Finalize session and store template."""
    data = request.get_json()
    if not data or "ve_table_front" not in data:
        raise ValidationError("ve_table_front is required")

    from api.services.v3_session_service import finalize_session as _finalize
    try:
        result = _finalize(
            session_id,
            ve_table_front=data["ve_table_front"],
            operator=data.get("operator", "unknown"),
        )
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)
    return jsonify(result)


@v3_session_bp.route("/session/<session_id>/materialize-run", methods=["POST"])
@with_error_handling
def materialize_run(session_id: str):
    """Materialize latest v3 correction grid as a run artifact for /api/apply."""
    from api.services.v3_session_service import materialize_run as _materialize
    try:
        result = _materialize(session_id)
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Pull advisor
# ---------------------------------------------------------------------------

@v3_session_bp.route("/session/<session_id>/next-pull", methods=["GET"])
@with_error_handling
def suggest_next_pull(session_id: str):
    """Get the advisor's next pull recommendation."""
    from api.services.v3_session_service import suggest_next_pull as _suggest
    try:
        result = _suggest(session_id)
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)
    return jsonify(result)


@v3_session_bp.route("/session/<session_id>/convergence", methods=["GET"])
@with_error_handling
def check_convergence(session_id: str):
    """Get convergence status."""
    from api.services.v3_session_service import check_convergence as _check
    try:
        result = _check(session_id)
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)
    return jsonify(result)


@v3_session_bp.route("/session/<session_id>/veto", methods=["POST"])
@with_error_handling
def operator_veto(session_id: str):
    """Operator veto a suggested operating point."""
    data = request.get_json()
    if not data or "rpm" not in data or "map_kpa" not in data:
        raise ValidationError("rpm and map_kpa are required")

    from api.services.v3_session_service import operator_veto as _veto
    try:
        result = _veto(
            session_id,
            rpm=data["rpm"],
            map_kpa=data["map_kpa"],
            reason=data.get("reason", ""),
        )
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)
    return jsonify(result)


# ---------------------------------------------------------------------------
# GP surrogate
# ---------------------------------------------------------------------------

@v3_session_bp.route("/session/<session_id>/uncertainty", methods=["GET"])
@with_error_handling
def get_uncertainty_map(session_id: str):
    """Get GP uncertainty map for the session."""
    from api.services.v3_session_service import get_uncertainty_map as _unc
    try:
        result = _unc(session_id)
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Overlay
# ---------------------------------------------------------------------------

@v3_session_bp.route("/session/<session_id>/overlay", methods=["GET"])
@with_error_handling
def get_overlay_status(session_id: str):
    """Get bounded overlay status."""
    from api.services.v3_session_service import get_overlay_status as _overlay
    try:
        result = _overlay(session_id)
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)
    return jsonify(result)


@v3_session_bp.route("/session/<session_id>/kill-switch", methods=["POST"])
@with_error_handling
def kill_switch(session_id: str):
    """Activate overlay kill switch."""
    from api.services.v3_session_service import kill_switch as _kill
    try:
        result = _kill(session_id)
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@v3_session_bp.route("/templates", methods=["GET"])
@with_error_handling
def list_templates():
    """List templates in the library."""
    family = request.args.get("family")
    from api.services.v3_session_service import list_templates as _list
    return jsonify(_list(engine_family=family))


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

@v3_session_bp.route("/session/<session_id>/simulate-pull", methods=["POST"])
@with_error_handling
def simulate_pull(session_id: str):
    """
    Generate and ingest simulated pull data.

    Body (all optional):
        mode:     "quick" (random scatter) or "realistic" (DynoSimulator + AutoTune)
        rpm:      Target RPM (defaults to advisor suggestion)
        map_kpa:  Target MAP (defaults to advisor suggestion)
        n_points: Points for quick mode (default 8)
    """
    data = request.get_json() or {}
    mode = data.get("mode", "quick")

    try:
        if mode == "realistic":
            from api.services.v3_session_service import simulate_pull_realistic as _sim
            result = _sim(
                session_id,
                rpm=data.get("rpm"),
                map_kpa=data.get("map_kpa"),
            )
        else:
            from api.services.v3_session_service import simulate_pull as _sim
            result = _sim(
                session_id,
                rpm=data.get("rpm"),
                map_kpa=data.get("map_kpa"),
                n_points=data.get("n_points", 8),
            )
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)
    return jsonify(result)


@v3_session_bp.route("/session/<session_id>/auto-simulate", methods=["POST"])
@with_error_handling
def auto_simulate(session_id: str):
    """
    Auto-run simulate pulls until converged or max_pulls reached.

    Body (all optional):
        mode:      "quick" or "realistic" (default "realistic")
        max_pulls: Maximum number of pulls (default 25)
    """
    data = request.get_json() or {}
    mode = data.get("mode", "realistic")
    max_pulls = min(data.get("max_pulls", 25), 50)  # cap at 50

    from api.services.v3_session_service import (
        simulate_pull as _sim_quick,
        simulate_pull_realistic as _sim_real,
        check_convergence as _check,
    )

    results = []
    try:
        for i in range(max_pulls):
            if mode == "realistic":
                result = _sim_real(session_id)
            else:
                result = _sim_quick(session_id)

            results.append(result)

            # Check convergence
            conv = result.get("convergence")
            if conv and conv.get("converged"):
                break
    except KeyError:
        raise NotFoundError(resource="V3 Session", identifier=session_id)

    return jsonify({
        "pulls_completed": len(results),
        "converged": results[-1].get("convergence", {}).get("converged", False) if results else False,
        "final_result": results[-1] if results else None,
        "pull_summary": [
            {
                "pull_number": r.get("pull_number"),
                "observations_added": r.get("observations_added"),
                "mean_uncertainty": r.get("convergence", {}).get("mean_uncertainty") if r.get("convergence") else None,
            }
            for r in results
        ],
    })
