"""
Reliability Agent API Routes

Provides endpoints for monitoring system reliability,
viewing circuit breaker status, and health metrics.
"""

import asyncio
import logging
from flask import Blueprint, jsonify, request

from api.reliability_agent import get_reliability_agent
from api.reliability_helpers import (
    health_check_jetdrive,
    health_check_jetstream,
)

logger = logging.getLogger(__name__)

reliability_bp = Blueprint("reliability", __name__)


@reliability_bp.route("/reliability/health", methods=["GET"])
def get_system_health():
    """
    Get overall system health status.
    
    Returns circuit breaker states, health monitor statuses,
    and recent alerts.
    
    ---
    GET /api/reliability/health
    
    Response:
        {
            "status": "healthy|degraded|unhealthy",
            "timestamp": 1234567890.123,
            "circuit_breakers": {
                "jetdrive": {
                    "name": "jetdrive",
                    "state": "closed",
                    "failure_count": 0,
                    "success_rate": 1.0
                }
            },
            "health_monitors": {
                "jetdrive": {
                    "name": "jetdrive",
                    "status": "healthy",
                    "success_rate": 0.95,
                    "avg_latency_ms": 123.4
                }
            },
            "recent_alerts": [...],
            "stats": {
                "total_circuits": 2,
                "open_circuits": 0,
                "unhealthy_monitors": 0,
                "alerts_count": 5
            }
        }
    """
    agent = get_reliability_agent()
    health = agent.get_system_health()
    return jsonify(health), 200


@reliability_bp.route("/reliability/circuits", methods=["GET"])
def get_circuit_breakers():
    """
    Get detailed circuit breaker status.
    
    ---
    GET /api/reliability/circuits
    
    Response:
        {
            "circuits": [
                {
                    "name": "jetdrive",
                    "state": "closed",
                    "failure_count": 0,
                    "success_rate": 1.0,
                    "last_failure": null
                }
            ]
        }
    """
    agent = get_reliability_agent()
    circuits = [cb.get_health() for cb in agent.circuit_breakers.values()]
    return jsonify({"circuits": circuits}), 200


@reliability_bp.route("/reliability/monitors", methods=["GET"])
def get_health_monitors():
    """
    Get detailed health monitor status.
    
    ---
    GET /api/reliability/monitors
    
    Response:
        {
            "monitors": [
                {
                    "name": "jetdrive",
                    "status": "healthy",
                    "success_rate": 0.95,
                    "avg_latency_ms": 123.4,
                    "consecutive_failures": 0,
                    "last_check": 1234567890.123
                }
            ]
        }
    """
    agent = get_reliability_agent()
    monitors = [mon.get_health_summary() for mon in agent.health_monitors.values()]
    return jsonify({"monitors": monitors}), 200


@reliability_bp.route("/reliability/alerts", methods=["GET"])
def get_alerts():
    """
    Get recent reliability alerts.
    
    Query params:
        limit: Number of alerts to return (default: 50, max: 100)
    
    ---
    GET /api/reliability/alerts?limit=20
    
    Response:
        {
            "alerts": [
                {
                    "type": "health_degraded",
                    "message": "Health check failed: timeout",
                    "timestamp": 1234567890.123,
                    "data": {}
                }
            ]
        }
    """
    agent = get_reliability_agent()
    limit = min(int(request.args.get("limit", 50)), 100)
    alerts = list(agent.alerts)[-limit:]
    return jsonify({"alerts": alerts}), 200


@reliability_bp.route("/reliability/circuits/<name>/reset", methods=["POST"])
def reset_circuit_breaker(name: str):
    """
    Manually reset a circuit breaker to closed state.
    
    Useful for forcing recovery after fixing underlying issues.
    
    ---
    POST /api/reliability/circuits/jetdrive/reset
    
    Response:
        {
            "success": true,
            "message": "Circuit breaker 'jetdrive' reset to CLOSED"
        }
    """
    agent = get_reliability_agent()
    
    if name not in agent.circuit_breakers:
        return jsonify({
            "error": f"Circuit breaker '{name}' not found"
        }), 404
    
    circuit = agent.circuit_breakers[name]
    circuit._close_circuit()
    
    logger.info(f"Manual reset of circuit breaker '{name}'")
    
    return jsonify({
        "success": True,
        "message": f"Circuit breaker '{name}' reset to CLOSED",
        "state": circuit.get_health(),
    }), 200


@reliability_bp.route("/reliability/health/jetdrive", methods=["GET"])
def check_jetdrive_health():
    """
    Perform immediate JetDrive health check.
    
    ---
    GET /api/reliability/health/jetdrive
    
    Response:
        {
            "status": "healthy|degraded|unhealthy",
            "providers": 1,
            "latency_ms": 123.4,
            "message": "..."
        }
    """
    try:
        result = asyncio.run(health_check_jetdrive())
        status_code = 200 if result["status"] == "healthy" else 503
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"JetDrive health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "message": "JetDrive health check failed",
            "error_type": type(e).__name__,
        }), 503


@reliability_bp.route("/reliability/health/jetstream", methods=["GET"])
def check_jetstream_health():
    """
    Perform immediate Jetstream health check.
    
    ---
    GET /api/reliability/health/jetstream
    
    Response:
        {
            "status": "healthy|unhealthy",
            "latency_ms": 123.4,
            "message": "..."
        }
    """
    try:
        # Import here to avoid circular dependency
        from api.jetstream.client import JetstreamClient
        from api.jetstream.config import get_jetstream_config
        
        config = get_jetstream_config()
        if not config.api_key:
            return jsonify({
                "status": "unconfigured",
                "message": "Jetstream API key not configured",
            }), 200
        
        client = JetstreamClient(config.base_url, config.api_key)
        result = health_check_jetstream(client)
        
        status_code = 200 if result["status"] == "healthy" else 503
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Jetstream health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "message": "Jetstream health check failed",
            "error_type": type(e).__name__,
        }), 503


@reliability_bp.route("/reliability/stats", methods=["GET"])
def get_reliability_stats():
    """
    Get aggregated reliability statistics.
    
    ---
    GET /api/reliability/stats
    
    Response:
        {
            "uptime_percentage": 99.5,
            "total_checks": 1000,
            "failed_checks": 5,
            "avg_latency_ms": 123.4,
            "circuits": {
                "total": 3,
                "open": 0,
                "half_open": 0,
                "closed": 3
            }
        }
    """
    agent = get_reliability_agent()
    
    # Aggregate stats across all monitors
    total_checks = 0
    total_failures = 0
    latencies = []
    
    for monitor in agent.health_monitors.values():
        total_checks += len(monitor.history)
        for metric in monitor.history:
            if metric.status == "unhealthy":
                total_failures += 1
            if metric.latency_ms is not None:
                latencies.append(metric.latency_ms)
    
    avg_latency = sum(latencies) / len(latencies) if latencies else None
    uptime_pct = ((total_checks - total_failures) / total_checks * 100) if total_checks > 0 else 100
    
    # Circuit states
    circuit_states = {"open": 0, "half_open": 0, "closed": 0}
    for circuit in agent.circuit_breakers.values():
        circuit_states[circuit.state.value.replace("-", "_")] += 1
    
    return jsonify({
        "uptime_percentage": round(uptime_pct, 2),
        "total_checks": total_checks,
        "failed_checks": total_failures,
        "avg_latency_ms": round(avg_latency, 2) if avg_latency else None,
        "circuits": {
            "total": len(agent.circuit_breakers),
            **circuit_states,
        },
    }), 200

