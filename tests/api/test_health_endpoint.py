"""
Tests for /api/health endpoint.

The health endpoint provides basic service availability checks.
"""

import pytest


class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    def test_health_returns_200_ok(self, client):
        """Health endpoint returns 200 status code."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_json(self, client):
        """Health endpoint returns JSON content type."""
        response = client.get("/api/health")
        assert response.content_type == "application/json"

    def test_health_status_ok(self, client):
        """Health endpoint returns status 'ok'."""
        response = client.get("/api/health")
        data = response.get_json()
        assert data["status"] == "ok"

    def test_health_includes_version(self, client):
        """Health endpoint includes version string."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_health_includes_app_name(self, client):
        """Health endpoint includes application name."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "app" in data
        assert data["app"] == "DynoAI"

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
