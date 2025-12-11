"""
Tests for /api/diagnostics/<run_id> endpoint.

The diagnostics endpoint provides diagnostics and anomaly detection results.
"""

import pytest


class TestDiagnosticsEndpointBasic:
    """Basic tests for the /api/diagnostics endpoint."""

    def test_diagnostics_returns_404_for_missing_run(self, client):
        """Diagnostics returns 404 for non-existent run ID."""
        response = client.get("/api/diagnostics/nonexistent-run-id")
        assert response.status_code == 404

    def test_diagnostics_returns_json(self, client, mock_output_folder):
        """Diagnostics endpoint returns JSON content type."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/diagnostics/{run_id}")
        assert response.status_code == 200
        assert response.content_type == "application/json"

    def test_diagnostics_contains_report(self, client, mock_output_folder):
        """Diagnostics response contains report field."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/diagnostics/{run_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert "report" in data
        assert isinstance(data["report"], str)

    def test_diagnostics_contains_anomalies(self, client, mock_output_folder):
        """Diagnostics response contains anomalies field."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/diagnostics/{run_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert "anomalies" in data

    def test_diagnostics_report_has_content(self, client, mock_output_folder):
        """Diagnostics report field contains actual content."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/diagnostics/{run_id}")
        data = response.get_json()
        assert len(data["report"]) > 0


class TestDiagnosticsEndpointInputValidation:
    """Tests for diagnostics endpoint input validation."""

    def test_diagnostics_rejects_dots_only_run_id(self, client):
        """Diagnostics returns 404 for invalid run_id patterns."""
        # Run IDs with only dots get sanitized and won't match any folder
        response = client.get("/api/diagnostics/...")
        assert response.status_code == 404

    def test_diagnostics_rejects_empty_sanitized_run_id(self, client):
        """Diagnostics returns 404 for run_id that sanitizes to empty."""
        response = client.get("/api/diagnostics/.......")
        assert response.status_code == 404


class TestDiagnosticsEndpointMethods:
    """Tests for diagnostics endpoint HTTP method handling."""

    def test_diagnostics_rejects_post(self, client):
        """Diagnostics endpoint rejects POST requests."""
        response = client.post("/api/diagnostics/some-run-id")
        assert response.status_code == 405

    def test_diagnostics_rejects_put(self, client):
        """Diagnostics endpoint rejects PUT requests."""
        response = client.put("/api/diagnostics/some-run-id")
        assert response.status_code == 405

    def test_diagnostics_rejects_delete(self, client):
        """Diagnostics endpoint rejects DELETE requests."""
        response = client.delete("/api/diagnostics/some-run-id")
        assert response.status_code == 405


class TestCoverageEndpointBasic:
    """Basic tests for the /api/coverage endpoint."""

    def test_coverage_returns_404_for_missing_run(self, client):
        """Coverage returns 404 for non-existent run ID."""
        response = client.get("/api/coverage/nonexistent-run-id")
        assert response.status_code == 404

    def test_coverage_returns_json(self, client, mock_output_folder):
        """Coverage endpoint returns JSON content type."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/coverage/{run_id}")
        assert response.status_code == 200
        assert response.content_type == "application/json"

    def test_coverage_contains_front_data(self, client, mock_output_folder):
        """Coverage response contains front cylinder data."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/coverage/{run_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert "front" in data
        assert "rpm" in data["front"]
        assert "load" in data["front"]
        assert "data" in data["front"]

    def test_coverage_contains_rear_data(self, client, mock_output_folder):
        """Coverage response contains rear cylinder data."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/coverage/{run_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert "rear" in data
        assert "rpm" in data["rear"]
        assert "load" in data["rear"]
        assert "data" in data["rear"]


class TestCoverageEndpointInputValidation:
    """Tests for coverage endpoint input validation."""

    def test_coverage_rejects_dots_only_run_id(self, client):
        """Coverage returns 404 for invalid run_id patterns."""
        response = client.get("/api/coverage/...")
        assert response.status_code == 404

    def test_coverage_rejects_empty_sanitized_run_id(self, client):
        """Coverage returns 404 for run_id that sanitizes to empty."""
        response = client.get("/api/coverage/.......")
        assert response.status_code == 404
