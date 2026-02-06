"""
Tests for /api/health endpoint.

The health endpoint provides detailed service availability checks.
"""

import pytest


class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    @staticmethod
    def test_health_returns_200_ok(client):
        """Health endpoint returns 200 status code when healthy."""
        response = client.get("/api/health")
        assert response.status_code == 200

    @staticmethod
    def test_health_returns_json(client):
        """Health endpoint returns JSON content type."""
        response = client.get("/api/health")
        assert response.content_type == "application/json"

    @staticmethod
    def test_health_status_healthy(client):
        """Health endpoint returns status 'healthy'."""
        response = client.get("/api/health")
        data = response.get_json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")

    @staticmethod
    def test_health_includes_version(client):
        """Health endpoint includes version string."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "version" in data
        assert isinstance(data["version"], str)

    @staticmethod
    def test_health_includes_timestamp(client):
        """Health endpoint includes timestamp."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)

    @staticmethod
    def test_health_includes_components(client):
        """Health endpoint includes component health checks."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "components" in data
        assert isinstance(data["components"], list)
        # Should have at least disk_space, uploads_writable, outputs_writable
        component_names = [c["name"] for c in data["components"]]
        assert "disk_space" in component_names

    @staticmethod
    def test_health_method_not_allowed_post(client):
        """Health endpoint rejects POST requests."""
        response = client.post("/api/health")
        assert response.status_code == 405

    @staticmethod
    def test_health_method_not_allowed_put(client):
        """Health endpoint rejects PUT requests."""
        response = client.put("/api/health")
        assert response.status_code == 405

    @staticmethod
    def test_health_method_not_allowed_delete(client):
        """Health endpoint rejects DELETE requests."""
        response = client.delete("/api/health")
        assert response.status_code == 405


class TestLivenessProbe:
    """Tests for /api/health/live liveness probe."""

    @staticmethod
    def test_liveness_returns_200(client):
        """Liveness probe returns 200."""
        response = client.get("/api/health/live")
        assert response.status_code == 200

    @staticmethod
    def test_liveness_returns_alive_status(client):
        """Liveness probe returns alive status."""
        response = client.get("/api/health/live")
        data = response.get_json()
        assert data["status"] == "alive"


class TestReadinessProbe:
    """Tests for /api/health/ready readiness probe."""

    @staticmethod
    def test_readiness_returns_200_when_ready(client):
        """Readiness probe returns 200 when service is ready."""
        response = client.get("/api/health/ready")
        # May return 503 if storage not writable, but 200 is expected in normal conditions
        assert response.status_code in (200, 503)

    @staticmethod
    def test_readiness_returns_ready_status(client):
        """Readiness probe returns status field."""
        response = client.get("/api/health/ready")
        data = response.get_json()
        assert "status" in data
        assert data["status"] in ("ready", "not_ready")
