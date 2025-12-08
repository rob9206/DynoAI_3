"""
Tests for /api/runs endpoints.

The runs endpoint provides listing and details for analysis runs.
"""

import pytest


class TestRunsListEndpoint:
    """Tests for the /api/runs endpoint."""

    def test_runs_returns_200(self, client):
        """Runs endpoint returns 200 status code."""
        response = client.get("/api/runs")
        assert response.status_code == 200

    def test_runs_returns_json(self, client):
        """Runs endpoint returns JSON content type."""
        response = client.get("/api/runs")
        assert response.content_type == "application/json"

    def test_runs_returns_list(self, client):
        """Runs endpoint returns runs list in response."""
        response = client.get("/api/runs")
        data = response.get_json()
        assert "runs" in data
        assert isinstance(data["runs"], list)

    def test_runs_with_mock_data(self, client, mock_output_folder):
        """Runs endpoint returns run data when available."""
        response = client.get("/api/runs")
        assert response.status_code == 200
        data = response.get_json()
        assert "runs" in data
        # Check if our mock run is present
        run_ids = [run.get("runId") for run in data["runs"]]
        assert mock_output_folder["run_id"] in run_ids


class TestRunsListEndpointMethods:
    """Tests for runs endpoint HTTP method handling."""

    def test_runs_rejects_post(self, client):
        """Runs endpoint rejects POST requests."""
        response = client.post("/api/runs")
        assert response.status_code == 405

    def test_runs_rejects_put(self, client):
        """Runs endpoint rejects PUT requests."""
        response = client.put("/api/runs")
        assert response.status_code == 405

    def test_runs_rejects_delete(self, client):
        """Runs endpoint rejects DELETE requests."""
        response = client.delete("/api/runs")
        assert response.status_code == 405


class TestStatusEndpoint:
    """Tests for the /api/status/<run_id> endpoint."""

    def test_status_returns_404_for_missing_run(self, client):
        """Status endpoint returns 404 for non-existent run."""
        response = client.get("/api/status/nonexistent-run-id")
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_status_returns_valid_response_structure(self, client, sample_csv_file):
        """Status endpoint returns properly structured response."""
        # First create a job
        with open(sample_csv_file, "rb") as f:
            create_response = client.post(
                "/api/analyze",
                data={"file": (f, "test.csv")},
                content_type="multipart/form-data",
            )

        if create_response.status_code == 202:
            run_id = create_response.get_json()["runId"]
            response = client.get(f"/api/status/{run_id}")
            assert response.status_code == 200
            data = response.get_json()
            assert "runId" in data
            assert "status" in data
            assert data["runId"] == run_id


class TestStatusEndpointMethods:
    """Tests for status endpoint HTTP method handling."""

    def test_status_rejects_post(self, client):
        """Status endpoint rejects POST requests."""
        response = client.post("/api/status/some-run-id")
        assert response.status_code == 405

    def test_status_rejects_put(self, client):
        """Status endpoint rejects PUT requests."""
        response = client.put("/api/status/some-run-id")
        assert response.status_code == 405

    def test_status_rejects_delete(self, client):
        """Status endpoint rejects DELETE requests."""
        response = client.delete("/api/status/some-run-id")
        assert response.status_code == 405
