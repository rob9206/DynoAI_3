"""
Tests for /api/runs endpoints.

The runs endpoint provides listing and details for analysis runs.
"""

import pytest
from datetime import datetime


class TestRunsListEndpoint:
    """Tests for the /api/runs endpoint."""

    @staticmethod
    def test_runs_returns_200(client):
        """Runs endpoint returns 200 status code."""
        response = client.get("/api/runs")
        assert response.status_code == 200

    @staticmethod
    def test_runs_returns_json(client):
        """Runs endpoint returns JSON content type."""
        response = client.get("/api/runs")
        assert response.content_type == "application/json"

    @staticmethod
    def test_runs_returns_list(client):
        """Runs endpoint returns runs list in response."""
        response = client.get("/api/runs")
        data = response.get_json()
        assert "runs" in data
        assert isinstance(data["runs"], list)

    @staticmethod
    def test_runs_with_mock_data(client, mock_output_folder):
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

    @staticmethod
    def test_runs_rejects_post(client):
        """Runs endpoint rejects POST requests."""
        response = client.post("/api/runs")
        assert response.status_code == 405

    @staticmethod
    def test_runs_rejects_put(client):
        """Runs endpoint rejects PUT requests."""
        response = client.put("/api/runs")
        assert response.status_code == 405

    @staticmethod
    def test_runs_rejects_delete(client):
        """Runs endpoint rejects DELETE requests."""
        response = client.delete("/api/runs")
        assert response.status_code == 405


class TestStatusEndpoint:
    """Tests for the /api/status/<run_id> endpoint."""

    @staticmethod
    def test_status_returns_404_for_missing_run(client):
        """Status endpoint returns 404 for non-existent run."""
        response = client.get("/api/status/nonexistent-run-id")
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    @staticmethod
    def test_status_returns_valid_response_structure(client, sample_csv_file):
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

    @staticmethod
    def test_status_rejects_post(client):
        """Status endpoint rejects POST requests."""
        response = client.post("/api/status/some-run-id")
        assert response.status_code == 405

    @staticmethod
    def test_status_rejects_put(client):
        """Status endpoint rejects PUT requests."""
        response = client.put("/api/status/some-run-id")
        assert response.status_code == 405

    @staticmethod
    def test_status_rejects_delete(client):
        """Status endpoint rejects DELETE requests."""
        response = client.delete("/api/status/some-run-id")
        assert response.status_code == 405


class TestManifestConversion:
    """Tests for convert_manifest_to_frontend_format function."""

    @staticmethod
    def test_manifest_conversion_uses_stats_avg_correction():
        """convert_manifest_to_frontend_format reads avgCorrection from stats."""
        from api.app import convert_manifest_to_frontend_format

        manifest = {
            "timing": {"start": "2025-01-01T00:00:00Z"},
            "input": {"path": "test.csv"},
            "stats": {
                "rows_read": 500,
                "front_accepted": 120,
                "rear_accepted": 80,
                "avg_correction": 3.75,
                "max_correction": 9.5,
            },
            "outputs": [],
            "config": {"args": {"smooth_passes": 2}},
        }
        result = convert_manifest_to_frontend_format(manifest, "run-123")
        assert result["analysisMetrics"]["avgCorrection"] == 3.75

    @staticmethod
    def test_manifest_conversion_uses_stats_max_correction():
        """convert_manifest_to_frontend_format reads maxCorrection from stats."""
        from api.app import convert_manifest_to_frontend_format

        manifest = {
            "timing": {"start": "2025-01-01T00:00:00Z"},
            "input": {"path": "test.csv"},
            "stats": {
                "rows_read": 500,
                "front_accepted": 120,
                "rear_accepted": 80,
                "avg_correction": 3.75,
                "max_correction": 9.5,
            },
            "outputs": [],
            "config": {"args": {"smooth_passes": 2}},
        }
        result = convert_manifest_to_frontend_format(manifest, "run-123")
        assert result["analysisMetrics"]["maxCorrection"] == 9.5

    @staticmethod
    def test_manifest_conversion_defaults_to_zero_when_stats_absent():
        """convert_manifest_to_frontend_format defaults metrics to 0.0 when missing."""
        from api.app import convert_manifest_to_frontend_format

        manifest = {
            "timing": {"start": "2025-01-01T00:00:00Z"},
            "input": {"path": "test.csv"},
            "stats": {
                "rows_read": 100,
                "front_accepted": 50,
                "rear_accepted": 30,
            },
            "outputs": [],
            "config": {"args": {}},
        }
        result = convert_manifest_to_frontend_format(manifest, "run-abc")
        assert result["analysisMetrics"]["avgCorrection"] == 0.0
        assert result["analysisMetrics"]["maxCorrection"] == 0.0

    @staticmethod
    def test_manifest_conversion_rows_processed():
        """convert_manifest_to_frontend_format maps rows_read to rowsProcessed."""
        from api.app import convert_manifest_to_frontend_format

        manifest = {
            "timing": {"start": "2025-01-01T00:00:00Z"},
            "input": {"path": "test.csv"},
            "stats": {"rows_read": 750, "front_accepted": 200, "rear_accepted": 150},
            "outputs": [],
            "config": {"args": {}},
        }
        result = convert_manifest_to_frontend_format(manifest, "run-xyz")
        assert result["rowsProcessed"] == 750

    @staticmethod
    def test_manifest_conversion_corrections_applied():
        """convert_manifest_to_frontend_format sums front+rear accepted as correctionsApplied."""
        from api.app import convert_manifest_to_frontend_format

        manifest = {
            "timing": {"start": "2025-01-01T00:00:00Z"},
            "input": {"path": "test.csv"},
            "stats": {"rows_read": 400, "front_accepted": 110, "rear_accepted": 90},
            "outputs": [],
            "config": {"args": {}},
        }
        result = convert_manifest_to_frontend_format(manifest, "run-xyz")
        assert result["correctionsApplied"] == 200

    @staticmethod
    def test_manifest_conversion_output_files_include_download_url():
        """convert_manifest_to_frontend_format includes correct download URLs."""
        from api.app import convert_manifest_to_frontend_format

        manifest = {
            "timing": {"start": "2025-01-01T00:00:00Z"},
            "input": {"path": "test.csv"},
            "stats": {"rows_read": 100, "front_accepted": 50, "rear_accepted": 30},
            "outputs": [
                {"name": "VE_Correction_Delta_DYNO.csv", "path": "VE_Correction_Delta_DYNO.csv"},
            ],
            "config": {"args": {}},
        }
        result = convert_manifest_to_frontend_format(manifest, "run-42")
        assert len(result["outputFiles"]) == 1
        assert result["outputFiles"][0]["url"] == "/api/download/run-42/VE_Correction_Delta_DYNO.csv"
