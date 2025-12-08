"""
Tests for /api/ve-data/<run_id> endpoint.

The VE data endpoint provides VE table data for 3D visualization.
"""

import pytest


class TestVEDataEndpointBasic:
    """Basic tests for the /api/ve-data endpoint."""

    def test_ve_data_returns_404_for_missing_run(self, client):
        """VE data returns 404 for non-existent run ID."""
        response = client.get("/api/ve-data/nonexistent-run-id")
        assert response.status_code == 404

    def test_ve_data_returns_json(self, client, mock_output_folder):
        """VE data endpoint returns JSON content type."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/ve-data/{run_id}")
        assert response.status_code == 200
        assert response.content_type == "application/json"

    def test_ve_data_contains_required_fields(self, client, mock_output_folder):
        """VE data response contains all required fields."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/ve-data/{run_id}")
        assert response.status_code == 200
        data = response.get_json()

        # Check required fields
        assert "rpm" in data
        assert "load" in data
        assert "corrections" in data
        assert "before" in data
        assert "after" in data

    def test_ve_data_rpm_is_list(self, client, mock_output_folder):
        """VE data RPM field is a list of integers."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/ve-data/{run_id}")
        data = response.get_json()

        assert isinstance(data["rpm"], list)
        assert all(isinstance(x, int) for x in data["rpm"])

    def test_ve_data_load_is_list(self, client, mock_output_folder):
        """VE data load field is a list of integers."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/ve-data/{run_id}")
        data = response.get_json()

        assert isinstance(data["load"], list)
        assert all(isinstance(x, int) for x in data["load"])

    def test_ve_data_corrections_is_2d_array(self, client, mock_output_folder):
        """VE data corrections field is a 2D array of floats."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/ve-data/{run_id}")
        data = response.get_json()

        assert isinstance(data["corrections"], list)
        assert all(isinstance(row, list) for row in data["corrections"])

    def test_ve_data_before_after_same_dimensions(self, client, mock_output_folder):
        """VE data before and after arrays have same dimensions."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/ve-data/{run_id}")
        data = response.get_json()

        assert len(data["before"]) == len(data["after"])
        if data["before"]:
            assert len(data["before"][0]) == len(data["after"][0])


class TestVEDataEndpointInputValidation:
    """Tests for VE data endpoint input validation."""

    def test_ve_data_rejects_dots_only_run_id(self, client):
        """VE data rejects run_id containing only dots."""
        response = client.get("/api/ve-data/...")
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid run_id" in data["error"]["message"]

    def test_ve_data_rejects_empty_sanitized_run_id(self, client):
        """VE data rejects run_id that sanitizes to empty string."""
        response = client.get("/api/ve-data/.......")
        assert response.status_code == 400


class TestVEDataEndpointMethods:
    """Tests for VE data endpoint HTTP method handling."""

    def test_ve_data_rejects_post(self, client):
        """VE data endpoint rejects POST requests."""
        response = client.post("/api/ve-data/some-run-id")
        assert response.status_code == 405

    def test_ve_data_rejects_put(self, client):
        """VE data endpoint rejects PUT requests."""
        response = client.put("/api/ve-data/some-run-id")
        assert response.status_code == 405

    def test_ve_data_rejects_delete(self, client):
        """VE data endpoint rejects DELETE requests."""
        response = client.delete("/api/ve-data/some-run-id")
        assert response.status_code == 405
