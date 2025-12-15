"""
Virtual Tuning API Routes - Closed-loop tuning orchestration endpoints.

Provides REST API for managing virtual tuning sessions:
- Start new tuning session
- Get session status and progress
- Stop running session
- Get session results
"""

import logging
import time

from flask import Blueprint, jsonify, request

from api.services.dyno_simulator import EngineProfile
from api.services.virtual_tuning_session import (
    TuningSessionConfig,
    TuningStatus,
    get_orchestrator,
)

logger = logging.getLogger(__name__)

virtual_tune_bp = Blueprint("virtual_tune", __name__, url_prefix="/api/virtual-tune")


@virtual_tune_bp.route("/start", methods=["POST"])
def start_tuning_session():
    """
    Start a new closed-loop virtual tuning session.

    Request body:
    {
        "engine_profile": "m8_114" | "m8_131" | "twin_cam_103" | "sportbike_600",
        "base_ve_scenario": "perfect" | "lean" | "rich" | "custom",
        "base_ve_error_pct": -10.0,  // For custom scenario
        "base_ve_error_std": 5.0,
        "max_iterations": 10,
        "convergence_threshold_afr": 0.3,
        "convergence_cell_pct": 90.0,
        "max_correction_per_iteration_pct": 15.0,
        "oscillation_detection_enabled": true,
        "barometric_pressure_inhg": 29.92,
        "ambient_temp_f": 75.0
    }

    Response:
    {
        "success": true,
        "session_id": "tune_1234567890_5678",
        "status": "running",
        "config": {...}
    }
    """
    try:
        data = request.get_json() or {}

        # Get engine profile
        profile_name = data.get("engine_profile", "m8_114")
        profiles = {
            "m8_114": EngineProfile.m8_114,
            "m8_131": EngineProfile.m8_131,
            "twin_cam_103": EngineProfile.twin_cam_103,
            "sportbike_600": EngineProfile.sportbike_600,
        }

        profile_factory = profiles.get(profile_name)
        if not profile_factory:
            return jsonify({"error": f"Unknown profile: {profile_name}"}), 400

        profile = profile_factory()

        # Build config
        config = TuningSessionConfig(
            engine_profile=profile,
            base_ve_scenario=data.get("base_ve_scenario", "lean"),
            base_ve_error_pct=data.get("base_ve_error_pct", -10.0),
            base_ve_error_std=data.get("base_ve_error_std", 5.0),
            max_iterations=data.get("max_iterations", 10),
            convergence_threshold_afr=data.get("convergence_threshold_afr", 0.3),
            convergence_cell_pct=data.get("convergence_cell_pct", 90.0),
            max_correction_per_iteration_pct=data.get(
                "max_correction_per_iteration_pct", 15.0
            ),
            oscillation_detection_enabled=data.get(
                "oscillation_detection_enabled", True
            ),
            barometric_pressure_inhg=data.get("barometric_pressure_inhg", 29.92),
            ambient_temp_f=data.get("ambient_temp_f", 75.0),
        )

        # Create session
        orchestrator = get_orchestrator()
        session = orchestrator.create_session(config)

        # Start tuning in background (non-blocking for now)
        # In production, this would be a background task (Celery, etc.)
        import threading

        def run_session_with_error_handling(session):
            """Wrapper to catch and log exceptions in the background thread."""
            try:
                orchestrator.run_session(session)
            except Exception as e:
                logger.error(
                    f"Exception in tuning session {session.session_id}: {e}",
                    exc_info=True,
                )
                session.status = TuningStatus.FAILED
                session.error_message = str(e)
                session.end_time = time.time()

        thread = threading.Thread(
            target=run_session_with_error_handling,
            args=(session,),
            daemon=True,
            name=f"tuning-{session.session_id}",
        )
        thread.start()

        logger.info(f"Started tuning session: {session.session_id}")

        return jsonify(
            {
                "success": True,
                "session_id": session.session_id,
                "status": session.status.value,
                "config": {
                    "engine_profile": profile.name,
                    "base_ve_scenario": config.base_ve_scenario,
                    "max_iterations": config.max_iterations,
                    "convergence_threshold_afr": config.convergence_threshold_afr,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error starting tuning session: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@virtual_tune_bp.route("/status/<session_id>", methods=["GET"])
def get_session_status(session_id: str):
    """
    Get status and progress of a tuning session.

    Response:
    {
        "session_id": "tune_1234567890_5678",
        "status": "running" | "converged" | "failed" | "stopped" | "max_iterations",
        "current_iteration": 3,
        "max_iterations": 10,
        "converged": false,
        "iterations": [
            {
                "iteration": 1,
                "max_afr_error": 1.4,
                "mean_afr_error": 0.8,
                "max_ve_correction_pct": 10.5,
                "converged": false
            },
            ...
        ],
        "duration_sec": 12.5,
        "error_message": null
    }
    """
    try:
        orchestrator = get_orchestrator()
        session = orchestrator.get_session(session_id)

        if not session:
            return jsonify({"error": "Session not found"}), 404

        return jsonify(session.to_dict())

    except Exception as e:
        logger.error(f"Error getting session status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@virtual_tune_bp.route("/stop/<session_id>", methods=["POST"])
def stop_session(session_id: str):
    """
    Stop a running tuning session.

    Response:
    {
        "success": true,
        "session_id": "tune_1234567890_5678",
        "status": "stopped"
    }
    """
    try:
        orchestrator = get_orchestrator()
        stopped = orchestrator.stop_session(session_id)

        if not stopped:
            return jsonify({"error": "Session not found or not running"}), 404

        session = orchestrator.get_session(session_id)

        return jsonify(
            {
                "success": True,
                "session_id": session_id,
                "status": session.status.value if session else "stopped",
            }
        )

    except Exception as e:
        logger.error(f"Error stopping session: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@virtual_tune_bp.route("/sessions", methods=["GET"])
def list_sessions():
    """
    List all tuning sessions.

    Response:
    {
        "sessions": [
            {
                "session_id": "tune_1234567890_5678",
                "status": "converged",
                "current_iteration": 4,
                "max_iterations": 10,
                "duration_sec": 15.2
            },
            ...
        ]
    }
    """
    try:
        orchestrator = get_orchestrator()

        sessions_list = []
        for session_id, session in orchestrator.sessions.items():
            sessions_list.append(
                {
                    "session_id": session_id,
                    "status": session.status.value,
                    "current_iteration": session.current_iteration,
                    "max_iterations": session.config.max_iterations,
                    "duration_sec": (
                        (session.end_time or 0) - session.start_time
                        if session.end_time
                        else None
                    ),
                    "converged": session.status.value == "converged",
                }
            )

        # Sort by start time (newest first)
        sessions_list.sort(key=lambda x: x["session_id"], reverse=True)

        return jsonify({"sessions": sessions_list})

    except Exception as e:
        logger.error(f"Error listing sessions: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@virtual_tune_bp.route("/results/<session_id>", methods=["GET"])
def get_session_results(session_id: str):
    """
    Get detailed results from a completed tuning session.

    Response:
    {
        "session_id": "tune_1234567890_5678",
        "status": "converged",
        "iterations": [...],
        "final_metrics": {
            "total_iterations": 4,
            "final_max_afr_error": 0.2,
            "final_mean_afr_error": 0.1,
            "convergence_rate": "fast",
            "time_to_convergence_sec": 15.2
        },
        "ve_evolution": {
            "initial_error_pct": -10.0,
            "final_error_pct": -0.5,
            "total_correction_pct": 9.5
        }
    }
    """
    try:
        orchestrator = get_orchestrator()
        session = orchestrator.get_session(session_id)

        if not session:
            return jsonify({"error": "Session not found"}), 404

        # Calculate final metrics
        final_metrics = {}
        if session.iterations:
            last_iteration = session.iterations[-1]
            final_metrics = {
                "total_iterations": session.current_iteration,
                "final_max_afr_error": round(last_iteration.max_afr_error, 3),
                "final_mean_afr_error": round(last_iteration.mean_afr_error, 3),
                "final_rms_afr_error": round(last_iteration.rms_afr_error, 3),
                "convergence_rate": (
                    "fast"
                    if session.current_iteration <= 3
                    else "normal"
                    if session.current_iteration <= 6
                    else "slow"
                ),
                "time_to_convergence_sec": (
                    round((session.end_time or 0) - session.start_time, 1)
                    if session.end_time
                    else None
                ),
            }

        # VE evolution
        ve_evolution = {}
        if session.baseline_ve is not None and session.current_ve_front is not None:
            initial_error = (
                (
                    (session.iterations[0].ve_table_front - session.baseline_ve)
                    / session.baseline_ve
                    * 100
                ).mean()
                if session.iterations
                else 0
            )
            final_error = (
                (session.current_ve_front - session.baseline_ve)
                / session.baseline_ve
                * 100
            ).mean()
            ve_evolution = {
                "initial_error_pct": round(initial_error, 2),
                "final_error_pct": round(final_error, 2),
                "total_correction_pct": round(initial_error - final_error, 2),
            }

        response = session.to_dict()
        response["final_metrics"] = final_metrics
        response["ve_evolution"] = ve_evolution

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting session results: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
