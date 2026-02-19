"""
Operator Training API Routes

Provides REST endpoints for the virtual dyno operator training simulator:
- Training session control (start/stop/reset)
- Dyno configuration (type selection)
- Load control and RPM hold
- Safety scenario triggers
- Real-time state polling

Add these routes to your existing jetdrive.py or register as a separate blueprint.
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Blueprint for operator training routes
# Can be merged into jetdrive_bp or registered separately
training_bp = Blueprint("training", __name__, url_prefix="/api/training")


def _get_training_simulator():
    """Lazy import to avoid circular dependencies."""
    try:
        from api.services.simulation.operator_training import (
            get_training_simulator,
            DynoType,
            TrainingScenario,
        )
        return get_training_simulator(), DynoType, TrainingScenario
    except ImportError as e:
        logger.error(f"Training simulator not available: {e}")
        return None, None, None


# =============================================================================
# Training Session Control
# =============================================================================


@training_bp.route("/status", methods=["GET"])
def get_training_status():
    """
    Get current training simulator status.
    
    Returns comprehensive state including:
    - Engine parameters (RPM, TPS, torque, HP)
    - Load control state
    - Thermal readings (EGT, oil, coolant)
    - Safety alerts
    - Active scenario
    """
    sim, _, _ = _get_training_simulator()
    if sim is None:
        return jsonify({"error": "Training simulator not available"}), 503
        
    try:
        state = sim.get_state()
        return jsonify({
            "success": True,
            "running": sim._running,
            "state": state
        })
    except Exception as e:
        logger.error(f"Error getting training status: {e}")
        return jsonify({"error": str(e)}), 500


@training_bp.route("/start", methods=["POST"])
def start_training():
    """Start the training simulator."""
    sim, _, _ = _get_training_simulator()
    if sim is None:
        return jsonify({"error": "Training simulator not available"}), 503
        
    try:
        sim.start()
        return jsonify({
            "success": True,
            "message": "Training simulator started"
        })
    except Exception as e:
        logger.error(f"Error starting training: {e}")
        return jsonify({"error": str(e)}), 500


@training_bp.route("/stop", methods=["POST"])
def stop_training():
    """Stop the training simulator."""
    sim, _, _ = _get_training_simulator()
    if sim is None:
        return jsonify({"error": "Training simulator not available"}), 503
        
    try:
        sim.stop()
        return jsonify({
            "success": True,
            "message": "Training simulator stopped"
        })
    except Exception as e:
        logger.error(f"Error stopping training: {e}")
        return jsonify({"error": str(e)}), 500


@training_bp.route("/reset", methods=["POST"])
def reset_training():
    """Reset training state (scores, alerts, scenarios)."""
    sim, _, _ = _get_training_simulator()
    if sim is None:
        return jsonify({"error": "Training simulator not available"}), 503
        
    try:
        sim.reset()
        return jsonify({
            "success": True,
            "message": "Training state reset"
        })
    except Exception as e:
        logger.error(f"Error resetting training: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Dyno Configuration
# =============================================================================


@training_bp.route("/dyno-config", methods=["GET"])
def get_dyno_config():
    """Get current dyno configuration."""
    sim, DynoType, _ = _get_training_simulator()
    if sim is None:
        return jsonify({"error": "Training simulator not available"}), 503
        
    config = sim.dyno_config
    return jsonify({
        "success": True,
        "config": {
            "dyno_type": config.dyno_type.value,
            "max_brake_torque": config.max_brake_torque,
            "brake_response_rate": config.brake_response_rate,
        },
        "available_types": [t.value for t in DynoType]
    })


@training_bp.route("/dyno-config", methods=["POST"])
def set_dyno_config():
    """
    Set dyno configuration.
    
    Request body:
    {
        "dyno_type": "inertia" | "inertia_load" | "load_holding",
        "max_brake_torque": 800,  // optional
        "brake_response_rate": 100  // optional
    }
    """
    sim, DynoType, _ = _get_training_simulator()
    if sim is None:
        return jsonify({"error": "Training simulator not available"}), 503
        
    data = request.get_json() or {}
    
    try:
        # Set dyno type
        if "dyno_type" in data:
            dyno_type_str = data["dyno_type"]
            dyno_type = DynoType(dyno_type_str)
            sim.set_dyno_type(dyno_type)
            
        # Set other config
        if "max_brake_torque" in data:
            sim.dyno_config.max_brake_torque = float(data["max_brake_torque"])
        if "brake_response_rate" in data:
            sim.dyno_config.brake_response_rate = float(data["brake_response_rate"])
            
        return jsonify({
            "success": True,
            "message": "Dyno configuration updated",
            "config": {
                "dyno_type": sim.dyno_config.dyno_type.value,
                "max_brake_torque": sim.dyno_config.max_brake_torque,
                "brake_response_rate": sim.dyno_config.brake_response_rate,
            }
        })
    except ValueError as e:
        return jsonify({"error": f"Invalid dyno type: {e}"}), 400
    except Exception as e:
        logger.error(f"Error setting dyno config: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Control Inputs
# =============================================================================


@training_bp.route("/throttle", methods=["POST"])
def set_throttle():
    """
    Set throttle position.
    
    Request body:
    {
        "tps": 0-100
    }
    """
    sim, _, _ = _get_training_simulator()
    if sim is None:
        return jsonify({"error": "Training simulator not available"}), 503
        
    data = request.get_json() or {}
    
    try:
        tps = float(data.get("tps", 0))
        sim.set_throttle(tps)
        return jsonify({
            "success": True,
            "tps": tps
        })
    except Exception as e:
        logger.error(f"Error setting throttle: {e}")
        return jsonify({"error": str(e)}), 400


@training_bp.route("/load", methods=["POST"])
def set_load():
    """
    Set brake load target.
    
    Request body:
    {
        "load": 0-100
    }
    
    Note: Only effective on inertia_load or load_holding dyno types.
    """
    sim, _, _ = _get_training_simulator()
    if sim is None:
        return jsonify({"error": "Training simulator not available"}), 503
        
    data = request.get_json() or {}
    
    try:
        load = float(data.get("load", 0))
        sim.set_load_target(load)
        return jsonify({
            "success": True,
            "load_target": load,
            "dyno_type": sim.dyno_config.dyno_type.value
        })
    except Exception as e:
        logger.error(f"Error setting load: {e}")
        return jsonify({"error": str(e)}), 400


@training_bp.route("/rpm-hold", methods=["POST"])
def set_rpm_hold():
    """
    Enable/disable RPM hold mode.
    
    Request body:
    {
        "active": true/false,
        "target_rpm": 3500  // optional
    }
    
    Note: Only available on load_holding dyno type.
    """
    sim, _, _ = _get_training_simulator()
    if sim is None:
        return jsonify({"error": "Training simulator not available"}), 503
        
    data = request.get_json() or {}
    
    try:
        active = bool(data.get("active", False))
        target_rpm = data.get("target_rpm")
        
        if target_rpm is not None:
            target_rpm = float(target_rpm)
            
        sim.set_rpm_hold(active, target_rpm)
        
        return jsonify({
            "success": True,
            "rpm_hold_active": active,
            "rpm_hold_target": sim.training_state.rpm_hold_target,
            "dyno_type": sim.dyno_config.dyno_type.value
        })
    except Exception as e:
        logger.error(f"Error setting RPM hold: {e}")
        return jsonify({"error": str(e)}), 400


# =============================================================================
# Safety & Training Scenarios
# =============================================================================


@training_bp.route("/scenario", methods=["POST"])
def trigger_scenario():
    """
    Trigger a training scenario.
    
    Request body:
    {
        "scenario": "overrev" | "lean" | "thermal" | "knock" | "load_shed",
        "duration": 10  // optional, seconds
    }
    """
    sim, _, TrainingScenario = _get_training_simulator()
    if sim is None:
        return jsonify({"error": "Training simulator not available"}), 503
        
    data = request.get_json() or {}
    
    try:
        scenario_str = data.get("scenario", "none")
        duration = float(data.get("duration", 10.0))
        
        scenario = TrainingScenario(scenario_str)
        sim.trigger_scenario(scenario, duration)
        
        return jsonify({
            "success": True,
            "scenario": scenario.value,
            "duration": duration,
            "message": f"Scenario '{scenario.value}' triggered for {duration}s"
        })
    except ValueError as e:
        return jsonify({"error": f"Invalid scenario: {e}"}), 400
    except Exception as e:
        logger.error(f"Error triggering scenario: {e}")
        return jsonify({"error": str(e)}), 500


@training_bp.route("/acknowledge", methods=["POST"])
def acknowledge_alert():
    """
    Acknowledge a safety alert.
    
    Request body:
    {
        "alert_type": "overrev" | "lean" | "thermal" | "knock" | "oil_temp"
    }
    
    Acknowledging alerts affects the training safety score.
    """
    sim, _, _ = _get_training_simulator()
    if sim is None:
        return jsonify({"error": "Training simulator not available"}), 503
        
    data = request.get_json() or {}
    
    try:
        alert_type = data.get("alert_type")
        if not alert_type:
            return jsonify({"error": "alert_type required"}), 400
            
        sim.acknowledge_alert(alert_type)
        
        return jsonify({
            "success": True,
            "acknowledged": alert_type,
            "safety_score": sim.safety_monitor.safety_score
        })
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        return jsonify({"error": str(e)}), 500


@training_bp.route("/safety-score", methods=["GET"])
def get_safety_score():
    """Get current safety training score and statistics."""
    sim, _, _ = _get_training_simulator()
    if sim is None:
        return jsonify({"error": "Training simulator not available"}), 503
        
    monitor = sim.safety_monitor
    return jsonify({
        "success": True,
        "safety_score": monitor.safety_score,
        "total_alerts": monitor.total_alerts,
        "acknowledged_alerts": monitor.acknowledged_alerts,
        "pending_alerts": len(monitor.response_timers)
    })


@training_bp.route("/safety-limits", methods=["GET"])
def get_safety_limits():
    """Get current safety threshold limits."""
    sim, _, _ = _get_training_simulator()
    if sim is None:
        return jsonify({"error": "Training simulator not available"}), 503
        
    limits = sim.safety_monitor.limits
    return jsonify({
        "success": True,
        "limits": {
            "rpm_warning": limits.rpm_warning,
            "rpm_critical": limits.rpm_critical,
            "afr_lean_warning": limits.afr_lean_warning,
            "afr_lean_critical": limits.afr_lean_critical,
            "egt_front_warning": limits.egt_front_warning,
            "egt_front_critical": limits.egt_front_critical,
            "egt_rear_warning": limits.egt_rear_warning,
            "egt_rear_critical": limits.egt_rear_critical,
            "knock_threshold": limits.knock_threshold,
            "oil_temp_warning": limits.oil_temp_warning,
            "oil_temp_critical": limits.oil_temp_critical,
        }
    })


# =============================================================================
# Available Scenarios Info
# =============================================================================


@training_bp.route("/scenarios", methods=["GET"])
def get_available_scenarios():
    """Get list of available training scenarios with descriptions."""
    return jsonify({
        "success": True,
        "scenarios": [
            {
                "id": "overrev",
                "name": "Over-Rev Emergency",
                "description": "Simulates sudden load drop causing dangerous RPM spike. Practice emergency throttle reduction.",
                "training_goal": "React within 2 seconds to prevent engine damage"
            },
            {
                "id": "lean",
                "name": "Lean Condition",
                "description": "Simulates fuel delivery problem causing dangerous lean AFR at WOT.",
                "training_goal": "Recognize lean AFR and abort pull before damage"
            },
            {
                "id": "thermal",
                "name": "Thermal Overload",
                "description": "Simulates extended WOT causing rapid EGT rise.",
                "training_goal": "Monitor EGT and initiate cooldown before critical temps"
            },
            {
                "id": "knock",
                "name": "Detonation Event",
                "description": "Simulates engine knock/detonation at moderate load.",
                "training_goal": "Recognize knock indicators and reduce timing/load"
            },
            {
                "id": "load_shed",
                "name": "Brake Failure",
                "description": "Simulates dyno brake failure with sudden load loss.",
                "training_goal": "Quickly reduce throttle to prevent over-rev"
            }
        ]
    })


# =============================================================================
# Registration helper
# =============================================================================

def register_training_routes(app):
    """
    Register training routes with Flask app.
    
    Usage in api/app.py:
        from api.routes.training import register_training_routes
        register_training_routes(app)
    
    Or merge into jetdrive_bp by copying the route functions.
    """
    app.register_blueprint(training_bp)
    logger.info("Operator training routes registered")


__all__ = ["training_bp", "register_training_routes"]
