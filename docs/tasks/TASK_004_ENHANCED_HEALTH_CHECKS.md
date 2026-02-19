# Task 004: Enhanced Health Checks

## Priority: LOW
## Estimated Effort: Low (30-60 minutes)
## Dependencies: None

---

## Objective
Enhance the `/api/health` endpoint to provide detailed system status including dependency checks, useful for monitoring and orchestration (Docker, K8s).

## Current State
```python
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    })
```

## Target State
- Detailed health response with component status
- Separate liveness (`/api/health/live`) and readiness (`/api/health/ready`) endpoints
- Check disk space, folder writability, external services
- Return appropriate HTTP status codes

## Implementation

### 1. Create `api/health.py`
```python
"""
DynoAI Health Check Endpoints.

Provides detailed health status for monitoring and orchestration.
"""

import os
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from flask import Blueprint, jsonify, Response
from api.config import get_config

health_bp = Blueprint('health', __name__, url_prefix='/api/health')


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
        free_gb = usage.free / (1024 ** 3)
        
        if free_gb < min_free_gb:
            return ComponentHealth(
                name="disk_space",
                status="unhealthy",
                message=f"Low disk space: {free_gb:.1f}GB free (min: {min_free_gb}GB)"
            )
        elif free_gb < min_free_gb * 2:
            return ComponentHealth(
                name="disk_space",
                status="degraded",
                message=f"Disk space warning: {free_gb:.1f}GB free"
            )
        return ComponentHealth(
            name="disk_space",
            status="healthy",
            message=f"{free_gb:.1f}GB free"
        )
    except Exception as e:
        return ComponentHealth(
            name="disk_space",
            status="unhealthy",
            message=str(e)
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
            message=f"{path} is writable"
        )
    except Exception as e:
        return ComponentHealth(
            name=f"{name}_writable",
            status="unhealthy",
            message=f"Cannot write to {path}: {e}"
        )


def check_jetstream_connectivity() -> ComponentHealth:
    """Check Jetstream API connectivity (if configured)."""
    config = get_config()
    
    if not config.jetstream.api_url:
        return ComponentHealth(
            name="jetstream",
            status="healthy",
            message="Not configured (optional)"
        )
    
    try:
        import requests
        start = datetime.utcnow()
        response = requests.get(
            f"{config.jetstream.api_url}/health",
            timeout=5
        )
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        
        if response.ok:
            return ComponentHealth(
                name="jetstream",
                status="healthy",
                latency_ms=latency
            )
        else:
            return ComponentHealth(
                name="jetstream",
                status="degraded",
                message=f"HTTP {response.status_code}",
                latency_ms=latency
            )
    except Exception as e:
        return ComponentHealth(
            name="jetstream",
            status="unhealthy",
            message=str(e)
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
        version="1.2.0",  # TODO: Read from package
        uptime_seconds=uptime,
        components=[asdict(c) for c in components]
    )


@health_bp.route("", methods=["GET"])
@health_bp.route("/", methods=["GET"])
def health_detailed() -> Response:
    """
    Detailed health check with component status.
    
    Returns 200 if healthy/degraded, 503 if unhealthy.
    """
    health = get_system_health()
    status_code = 200 if health.status != "unhealthy" else 503
    return jsonify(asdict(health)), status_code


@health_bp.route("/live", methods=["GET"])
def liveness() -> Response:
    """
    Kubernetes liveness probe.
    
    Returns 200 if the process is running.
    Used to determine if the container should be restarted.
    """
    return jsonify({
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


@health_bp.route("/ready", methods=["GET"])
def readiness() -> Response:
    """
    Kubernetes readiness probe.
    
    Returns 200 if the service is ready to accept traffic.
    Used to determine if the container should receive requests.
    """
    health = get_system_health()
    
    # Only ready if all critical components are healthy
    critical_unhealthy = any(
        c["status"] == "unhealthy" 
        for c in health.components 
        if c["name"] in ["uploads_writable", "outputs_writable"]
    )
    
    if critical_unhealthy:
        return jsonify({
            "status": "not_ready",
            "reason": "Critical components unhealthy",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), 503
    
    return jsonify({
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200
```

### 2. Register Blueprint in `api/app.py`
```python
from api.health import health_bp
app.register_blueprint(health_bp)
```

### 3. Update Docker Health Check
In `Dockerfile`:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health/ready || exit 1
```

In `docker-compose.yml`:
```yaml
services:
  backend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/health/ready"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

## Example Responses

### `/api/health` - Detailed Health
```json
{
  "status": "healthy",
  "timestamp": "2025-12-05T15:30:00.000Z",
  "version": "1.2.0",
  "uptime_seconds": 3600.5,
  "components": [
    {
      "name": "disk_space",
      "status": "healthy",
      "message": "45.2GB free"
    },
    {
      "name": "uploads_writable",
      "status": "healthy",
      "message": "/uploads is writable"
    },
    {
      "name": "outputs_writable",
      "status": "healthy",
      "message": "/outputs is writable"
    },
    {
      "name": "jetstream",
      "status": "healthy",
      "latency_ms": 45.2
    }
  ]
}
```

### `/api/health/live` - Liveness
```json
{
  "status": "alive",
  "timestamp": "2025-12-05T15:30:00.000Z"
}
```

### `/api/health/ready` - Readiness
```json
{
  "status": "ready",
  "timestamp": "2025-12-05T15:30:00.000Z"
}
```

## Acceptance Criteria
- [ ] `/api/health` returns detailed component status
- [ ] `/api/health/live` always returns 200 if process is running
- [ ] `/api/health/ready` returns 503 if critical components fail
- [ ] Docker healthcheck uses `/api/health/ready`
- [ ] Response includes version and uptime
- [ ] Disk space and folder writability checked

## Files to Create/Modify
- Create `api/health.py`
- Update `api/app.py` - register health blueprint, remove old health route
- Update `Dockerfile` - update HEALTHCHECK
- Update `docker-compose.yml` - update healthcheck config

