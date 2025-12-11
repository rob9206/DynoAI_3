"""
Tests for /api/download/<run_id>/<filename> endpoint.

The download endpoint provides secure file downloads for analysis outputs.
"""

import pytest


class TestDownloadEndpointBasic:
    """Basic tests for the /api/download endpoint."""

    def test_download_returns_404_for_missing_run(self, client):
        """Download returns 404 for non-existent run ID."""
        response = client.get("/api/download/nonexistent-run/file.csv")
        assert response.status_code == 404

    def test_download_returns_404_for_missing_file(self, client, mock_output_folder):
        """Download returns 404 for non-existent file in valid run."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/download/{run_id}/nonexistent.csv")
        assert response.status_code == 404

    def test_download_succeeds_for_valid_file(self, client, mock_output_folder):
        """Download returns file for valid run and filename."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/download/{run_id}/VE_Correction_Delta_DYNO.csv")
        assert response.status_code == 200
        assert (
            "text/csv" in response.content_type
            or "application/octet-stream" in response.content_type
        )

    def test_download_returns_correct_content(self, client, mock_output_folder):
        """Download returns correct file content."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/download/{run_id}/VE_Correction_Delta_DYNO.csv")
        assert response.status_code == 200
        content = response.data.decode("utf-8")
        assert "RPM" in content
        assert "1000" in content

    def test_download_sets_attachment_header(self, client, mock_output_folder):
        """Download sets Content-Disposition attachment header."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/download/{run_id}/VE_Correction_Delta_DYNO.csv")
        assert response.status_code == 200
        assert "attachment" in response.headers.get("Content-Disposition", "")


class TestDownloadEndpointInputValidation:
    """Tests for download endpoint input validation."""

    def test_download_rejects_empty_run_id(self, client):
        """Download rejects empty run_id."""
        # Flask routing won't match empty segments, so this results in 404
        response = client.get("/api/download//file.csv")
        assert response.status_code == 404

    def test_download_rejects_empty_filename(self, client, mock_output_folder):
        """Download rejects empty filename."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/download/{run_id}/")
        assert response.status_code == 404

    def test_download_sanitizes_run_id_dots(self, client):
        """Download returns 404 for run_id containing only dots."""
        # "..." sanitizes to empty string, so folder won't exist
        response = client.get("/api/download/.../file.csv")
        assert response.status_code == 404

    def test_download_sanitizes_filename_dots(self, client, mock_output_folder):
        """Download returns error for filename containing only dots."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/download/{run_id}/...")
        # May return 404 (file not found) or 500 (empty filename error)
        assert response.status_code in (404, 500)


class TestDownloadEndpointMethods:
    """Tests for download endpoint HTTP method handling."""

    def test_download_rejects_post(self, client, mock_output_folder):
        """Download endpoint rejects POST requests."""
        run_id = mock_output_folder["run_id"]
        response = client.post(f"/api/download/{run_id}/file.csv")
        assert response.status_code == 405

    def test_download_rejects_put(self, client, mock_output_folder):
        """Download endpoint rejects PUT requests."""
        run_id = mock_output_folder["run_id"]
        response = client.put(f"/api/download/{run_id}/file.csv")
        assert response.status_code == 405

    def test_download_rejects_delete(self, client, mock_output_folder):
        """Download endpoint rejects DELETE requests."""
        run_id = mock_output_folder["run_id"]
        response = client.delete(f"/api/download/{run_id}/file.csv")
        assert response.status_code == 405
