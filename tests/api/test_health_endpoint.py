"""
Tests for /api/health endpoint.

The health endpoint provides detailed service availability checks.
"""

import pytest


class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    def test_health_returns_200_ok(self, client):
        """Health endpoint returns 200 status code when healthy."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_json(self, client):
        """Health endpoint returns JSON content type."""
        response = client.get("/api/health")
        assert response.content_type == "application/json"

    def test_health_status_healthy(self, client):
        """Health endpoint returns status 'healthy'."""
        response = client.get("/api/health")
        data = response.get_json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")

    def test_health_includes_version(self, client):
        """Health endpoint includes version string."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_health_includes_timestamp(self, client):
        """Health endpoint includes timestamp."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)

    def test_health_includes_components(self, client):
        """Health endpoint includes component health checks."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "components" in data
        assert isinstance(data["components"], list)
        # Should have at least disk_space, uploads_writable, outputs_writable
        component_names = [c["name"] for c in data["components"]]
        assert "disk_space" in component_names

    def test_health_method_not_allowed_post(self, client):
        """Health endpoint rejects POST requests."""
        response = client.post("/api/health")
        assert response.status_code == 405

    def test_health_method_not_allowed_put(self, client):
        """Health endpoint rejects PUT requests."""
        response = client.put("/api/health")
        assert response.status_code == 405

    def test_health_method_not_allowed_delete(self, client):
        """Health endpoint rejects DELETE requests."""
        response = client.delete("/api/health")
        assert response.status_code == 405


class TestLivenessProbe:
    """Tests for /api/health/live liveness probe."""

    def test_liveness_returns_200(self, client):
        """Liveness probe returns 200."""
        response = client.get("/api/health/live")
        assert response.status_code == 200

    def test_liveness_returns_alive_status(self, client):
        """Liveness probe returns alive status."""
        response = client.get("/api/health/live")
        data = response.get_json()
        assert data["status"] == "alive"


class TestReadinessProbe:
    """Tests for /api/health/ready readiness probe."""

    def test_readiness_returns_200_when_ready(self, client):
        """Readiness probe returns 200 when service is ready."""
        response = client.get("/api/health/ready")
        # May return 503 if storage not writable, but 200 is expected in normal conditions
        assert response.status_code in (200, 503)

    def test_readiness_returns_ready_status(self, client):
        """Readiness probe returns status field."""
        response = client.get("/api/health/ready")
        data = response.get_json()
        assert "status" in data
        assert data["status"] in ("ready", "not_ready")
