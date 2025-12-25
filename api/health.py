"""
DynoAI Health Check Endpoints.

Provides detailed health status for monitoring and orchestration.
"""

import logging
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Blueprint, Response, jsonify

from api.config import get_config

logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__, url_prefix="/api/health")


@dataclass
class ComponentHealth:
    """Health status of a single component."""

    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    message: Optional[str] = None
    latency_ms: Optional[float] = None


@dataclass
class SystemHealth:
    """Overall system health status."""

    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    version: str
    uptime_seconds: float
    components: List[Dict[str, Any]]


# Track startup time
_startup_time = datetime.utcnow()


def check_disk_space(path: Path, min_free_gb: float = 1.0) -> ComponentHealth:
    """Check available disk space."""
    try:
        usage = shutil.disk_usage(path)
        free_gb = usage.free / (1024**3)

        if free_gb < min_free_gb:
            return ComponentHealth(
                name="disk_space",
                status="unhealthy",
                message=f"Low disk space: {free_gb:.1f}GB free (min: {min_free_gb}GB)",
            )
        elif free_gb < min_free_gb * 2:
            return ComponentHealth(
                name="disk_space",
                status="degraded",
                message=f"Disk space warning: {free_gb:.1f}GB free",
            )
        return ComponentHealth(
            name="disk_space", status="healthy", message=f"{free_gb:.1f}GB free"
        )
    except Exception as e:
        # Log full error for debugging but return sanitized message
        logger.warning("Disk space check failed", exc_info=e)
        return ComponentHealth(
            name="disk_space",
            status="unhealthy",
            message="Unable to check disk space",
        )


def check_folder_writable(path: Path, name: str) -> ComponentHealth:
    """Check if a folder is writable."""
    try:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

        test_file = path / ".health_check"
        test_file.write_text("test")
        test_file.unlink()

        return ComponentHealth(
            name=f"{name}_writable",
            status="healthy",
            message=f"{name} folder is writable",
        )
    except Exception as e:
        # Log full error for debugging but return sanitized message
        logger.warning("Folder writability check failed for %s", name, exc_info=e)
        return ComponentHealth(
            name=f"{name}_writable",
            status="unhealthy",
            message=f"Cannot write to {name} folder",
        )


def check_jetstream_connectivity() -> ComponentHealth:
    """Check Jetstream API connectivity (if configured)."""
    config = get_config()

    if not config.jetstream.api_url:
        return ComponentHealth(
            name="jetstream", status="healthy", message="Not configured (optional)"
        )

    try:
        import requests

        start = datetime.utcnow()
        response = requests.get(f"{config.jetstream.api_url}/health", timeout=5)
        latency = (datetime.utcnow() - start).total_seconds() * 1000

        if response.ok:
            return ComponentHealth(
                name="jetstream", status="healthy", latency_ms=latency
            )
        else:
            return ComponentHealth(
                name="jetstream",
                status="degraded",
                message=f"HTTP {response.status_code}",
                latency_ms=latency,
            )
    except Exception as e:
        # Log full error for debugging but return sanitized message
        logger.warning("Jetstream connectivity check failed", exc_info=e)
        return ComponentHealth(
            name="jetstream",
            status="unhealthy",
            message="Connection failed",
        )


def get_system_health() -> SystemHealth:
    """Get comprehensive system health."""
    config = get_config()

    components = [
        check_disk_space(config.storage.output_folder),
        check_folder_writable(config.storage.upload_folder, "uploads"),
        check_folder_writable(config.storage.output_folder, "outputs"),
        check_jetstream_connectivity(),
    ]

    # Determine overall status
    statuses = [c.status for c in components]
    if "unhealthy" in statuses:
        overall = "unhealthy"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    uptime = (datetime.utcnow() - _startup_time).total_seconds()

    return SystemHealth(
        status=overall,
        timestamp=datetime.utcnow().isoformat() + "Z",
        version=config.version,
        uptime_seconds=uptime,
        components=[asdict(c) for c in components],
    )


@health_bp.route("", methods=["GET"])
@health_bp.route("/", methods=["GET"])
def health_detailed() -> Response:
    """
    Detailed health check.
    ---
    tags:
      - Health
    summary: Get detailed health status with component checks
    description: |
      Returns comprehensive health status including:
      - Overall system status (healthy, degraded, unhealthy)
      - Individual component checks (disk space, folder writability, Jetstream)
      - Server uptime and version information

      **Status codes:**
      - 200: System is healthy or degraded
      - 503: System is unhealthy
    responses:
      200:
        description: System is healthy or degraded
        schema:
          $ref: '#/definitions/HealthResponse'
      503:
        description: System is unhealthy
        schema:
          $ref: '#/definitions/HealthResponse'
    """
    health = get_system_health()
    status_code = 200 if health.status != "unhealthy" else 503
    return jsonify(asdict(health)), status_code


@health_bp.route("/live", methods=["GET"])
def liveness() -> Response:
    """
    Liveness probe.
    ---
    tags:
      - Health
    summary: Kubernetes liveness probe
    description: |
      Simple check that returns 200 if the service is running.
      Used by Kubernetes to determine if the container should be restarted.

      **Note:** This endpoint performs no dependency checks and will return
      200 as long as the Flask process is running.
    responses:
      200:
        description: Service is alive
        schema:
          type: object
          properties:
            status:
              type: string
              example: "alive"
            timestamp:
              type: string
              format: date-time
    """
    return (
        jsonify({"status": "alive", "timestamp": datetime.utcnow().isoformat() + "Z"}),
        200,
    )


@health_bp.route("/diagnostics", methods=["GET"])
def system_diagnostics() -> Response:
    """
    System diagnostics endpoint.
    ---
    tags:
      - Health
    summary: Get comprehensive system diagnostics
    description: |
      Returns aggregated system diagnostics including:
      - API status and version
      - Active job/queue counts
      - Virtual-tune orchestrator session count
      - File index statistics
      - Database status
    responses:
      200:
        description: Diagnostics retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
            version:
              type: string
            uptime_seconds:
              type: number
            active_jobs:
              type: integer
            virtual_tune_sessions:
              type: integer
            file_index_entries:
              type: integer
            database_status:
              type: string
    """
    config = get_config()
    uptime = (datetime.utcnow() - _startup_time).total_seconds()

    diagnostics = {
        "status": "ok",
        "version": config.version,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "uptime_seconds": round(uptime, 1),
        "active_jobs": 0,
        "virtual_tune_sessions": 0,
        "file_index_entries": 0,
        "database_status": "unknown",
        "components": {},
    }

    # Count active analysis jobs
    try:
        # Import here to avoid circular imports
        import api.app as app_module
        if hasattr(app_module, 'active_jobs'):
            diagnostics["active_jobs"] = len(app_module.active_jobs)
    except Exception:
        pass

    # Count virtual tuning sessions
    try:
        from api.routes.virtual_tune import _orchestrator
        if _orchestrator:
            diagnostics["virtual_tune_sessions"] = len(_orchestrator._active_sessions)
    except Exception:
        pass

    # File index statistics
    try:
        from api.services.file_index import get_file_index
        file_index = get_file_index()
        diagnostics["file_index_entries"] = len(file_index._index)
    except Exception:
        pass

    # Database status
    try:
        from api.services.database import test_connection
        diagnostics["database_status"] = "connected" if test_connection() else "disconnected"
    except Exception:
        diagnostics["database_status"] = "unavailable"

    # Jetstream poller status
    try:
        from api.jetstream.poller import get_poller
        poller = get_poller()
        if poller:
            diagnostics["components"]["jetstream"] = {
                "running": poller.is_running,
                "last_poll": poller.last_poll_time.isoformat() if poller.last_poll_time else None,
            }
    except Exception:
        pass

    # Health component summary
    health = get_system_health()
    diagnostics["health_status"] = health.status
    diagnostics["components"]["health"] = {c["name"]: c["status"] for c in health.components}

    return jsonify(diagnostics), 200


@health_bp.route("/ready", methods=["GET"])
def readiness() -> Response:
    """
    Readiness probe.
    ---
    tags:
      - Health
    summary: Kubernetes readiness probe
    description: |
      Checks if the service is ready to accept traffic by verifying:
      - Upload folder is writable
      - Output folder is writable

      Used by Kubernetes to determine if the container should receive requests.
      Returns 503 if critical components are unhealthy.
    responses:
      200:
        description: Service is ready
        schema:
          type: object
          properties:
            status:
              type: string
              example: "ready"
            timestamp:
              type: string
              format: date-time
      503:
        description: Service is not ready
        schema:
          type: object
          properties:
            status:
              type: string
              example: "not_ready"
            reason:
              type: string
              example: "Critical components unhealthy"
            timestamp:
              type: string
              format: date-time
    """
    health = get_system_health()

    # Only ready if all critical components are healthy
    critical_unhealthy = any(
        c["status"] == "unhealthy"
        for c in health.components
        if c["name"] in ["uploads_writable", "outputs_writable"]
    )

    if critical_unhealthy:
        return (
            jsonify(
                {
                    "status": "not_ready",
                    "reason": "Critical components unhealthy",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            ),
            503,
        )

    return (
        jsonify({"status": "ready", "timestamp": datetime.utcnow().isoformat() + "Z"}),
        200,
    )
