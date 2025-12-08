"""
Security tests for Flask API endpoints.

Tests for path traversal prevention, input validation, and security hardening.
"""

import pytest


class TestPathTraversalPreventionDownload:
    """Tests for path traversal vulnerability prevention in download endpoint."""

    def test_download_rejects_path_traversal_in_run_id(self, client):
        """Download rejects ../.. in run_id."""
        response = client.get("/api/download/../../../etc/passwd/file.csv")
        assert response.status_code in (400, 404)

    def test_download_rejects_path_traversal_in_filename(
        self, client, mock_output_folder
    ):
        """Download rejects ../.. in filename."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/download/{run_id}/../../../etc/passwd")
        assert response.status_code in (400, 404)

    def test_download_rejects_backslash_traversal_run_id(self, client):
        """Download rejects backslash traversal in run_id."""
        response = client.get("/api/download/..\\..\\..\\windows\\system32/file.csv")
        assert response.status_code in (400, 404)

    def test_download_rejects_encoded_traversal_run_id(self, client):
        """Download handles URL-encoded traversal attempts in run_id."""
        response = client.get("/api/download/%2e%2e%2f%2e%2e%2f/file.csv")
        assert response.status_code in (400, 404)

    def test_download_rejects_null_byte_run_id(self, client):
        """Download rejects null byte injection in run_id."""
        response = client.get("/api/download/valid-run%00.csv/file.csv")
        assert response.status_code in (400, 404)

    def test_download_rejects_dots_only_run_id(self, client):
        """Download rejects run_id containing only dots."""
        response = client.get("/api/download/.../file.csv")
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid run_id" in data["error"]["message"]

    def test_download_rejects_dots_only_filename(self, client, mock_output_folder):
        """Download rejects filename containing only dots."""
        run_id = mock_output_folder["run_id"]
        response = client.get(f"/api/download/{run_id}/...")
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid filename" in data["error"]["message"]


class TestPathTraversalPreventionVEData:
    """Tests for path traversal prevention in VE data endpoint."""

    def test_ve_data_rejects_path_traversal(self, client):
        """VE data rejects ../.. in run_id."""
        response = client.get("/api/ve-data/../../../etc/passwd")
        assert response.status_code in (400, 404)

    def test_ve_data_rejects_dots_only(self, client):
        """VE data rejects run_id that sanitizes to empty string."""
        response = client.get("/api/ve-data/...")
        assert response.status_code == 400

    def test_ve_data_rejects_backslash_traversal(self, client):
        """VE data rejects backslash traversal."""
        response = client.get("/api/ve-data/..\\..\\..\\windows\\system32")
        assert response.status_code in (400, 404)


class TestPathTraversalPreventionDiagnostics:
    """Tests for path traversal prevention in diagnostics endpoint."""

    def test_diagnostics_rejects_path_traversal(self, client):
        """Diagnostics rejects ../.. in run_id."""
        response = client.get("/api/diagnostics/../../../etc")
        assert response.status_code in (400, 404)

    def test_diagnostics_rejects_dots_only(self, client):
        """Diagnostics rejects run_id that sanitizes to empty string."""
        response = client.get("/api/diagnostics/...")
        assert response.status_code == 400

    def test_diagnostics_rejects_double_dots_many(self, client):
        """Diagnostics rejects multiple dot sequences."""
        response = client.get("/api/diagnostics/.......")
        assert response.status_code == 400


class TestPathTraversalPreventionCoverage:
    """Tests for path traversal prevention in coverage endpoint."""

    def test_coverage_rejects_path_traversal(self, client):
        """Coverage rejects ../.. in run_id."""
        response = client.get("/api/coverage/../../../etc")
        assert response.status_code in (400, 404)

    def test_coverage_rejects_dots_only(self, client):
        """Coverage rejects run_id that sanitizes to empty string."""
        response = client.get("/api/coverage/...")
        assert response.status_code == 400


class TestInputValidation:
    """Tests for general input validation across endpoints."""

    def test_analyze_rejects_special_characters_in_filename(self, client, tmp_path):
        """Analyze handles special characters in filename safely."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("timestamp,rpm\n0,1000")

        with open(csv_file, "rb") as f:
            # werkzeug's secure_filename will sanitize this
            response = client.post(
                "/api/analyze",
                data={"file": (f, "../../etc/passwd.csv")},
                content_type="multipart/form-data",
            )
        # Should either sanitize and accept or reject - but NOT traverse
        assert response.status_code in (202, 400)

    def test_analyze_sanitizes_unicode_filename(self, client, tmp_path):
        """Analyze handles unicode characters in filename."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("timestamp,rpm\n0,1000")

        with open(csv_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"file": (f, "тест_файл.csv")},
                content_type="multipart/form-data",
            )
        # Should either accept (with sanitized name) or reject
        assert response.status_code in (202, 400)


class TestFileTypeValidation:
    """Tests for file type validation security."""

    def test_analyze_rejects_script_files(self, client, tmp_path):
        """Analyze rejects script file types."""
        script_file = tmp_path / "malicious.sh"
        script_file.write_text("#!/bin/bash\nrm -rf /")

        with open(script_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"file": (f, "malicious.sh")},
                content_type="multipart/form-data",
            )
        assert response.status_code == 400

    def test_analyze_rejects_html_files(self, client, tmp_path):
        """Analyze rejects HTML file types."""
        html_file = tmp_path / "xss.html"
        html_file.write_text("<script>alert('xss')</script>")

        with open(html_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"file": (f, "xss.html")},
                content_type="multipart/form-data",
            )
        assert response.status_code == 400

    def test_analyze_rejects_json_files(self, client, tmp_path):
        """Analyze rejects JSON file types (not in allowed list)."""
        json_file = tmp_path / "data.json"
        json_file.write_text('{"malicious": true}')

        with open(json_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"file": (f, "data.json")},
                content_type="multipart/form-data",
            )
        assert response.status_code == 400

    def test_analyze_rejects_python_files(self, client, tmp_path):
        """Analyze rejects Python file types."""
        py_file = tmp_path / "exploit.py"
        py_file.write_text("import os; os.system('whoami')")

        with open(py_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"file": (f, "exploit.py")},
                content_type="multipart/form-data",
            )
        assert response.status_code == 400


class TestErrorResponseSecurity:
    """Tests for secure error responses."""

    def test_404_does_not_reveal_file_paths(self, client):
        """404 errors do not reveal internal file system paths."""
        response = client.get("/api/download/nonexistent/file.csv")
        data = response.get_json()

        # Ensure no file system paths in error
        error_str = str(data)
        assert "C:\\" not in error_str
        assert "/home/" not in error_str
        assert "/var/" not in error_str

    def test_400_does_not_reveal_internal_details(self, client):
        """400 errors do not reveal internal implementation details."""
        response = client.get("/api/ve-data/...")
        data = response.get_json()

        error_str = str(data)
        # Should not reveal stack traces or internal paths
        assert "Traceback" not in error_str
        assert 'File "' not in error_str


class TestHTTPMethodSecurity:
    """Tests for HTTP method restrictions."""

    def test_health_only_allows_get(self, client):
        """Health endpoint only allows GET method."""
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/health").status_code == 405
        assert client.put("/api/health").status_code == 405
        assert client.delete("/api/health").status_code == 405
        assert client.patch("/api/health").status_code == 405

    def test_runs_only_allows_get(self, client):
        """Runs endpoint only allows GET method."""
        assert client.get("/api/runs").status_code == 200
        assert client.post("/api/runs").status_code == 405
        assert client.put("/api/runs").status_code == 405
        assert client.delete("/api/runs").status_code == 405

    def test_analyze_only_allows_post(self, client):
        """Analyze endpoint only allows POST method."""
        assert client.get("/api/analyze").status_code == 405
        assert client.put("/api/analyze").status_code == 405
        assert client.delete("/api/analyze").status_code == 405


class TestContentTypeHeaders:
    """Tests for proper content type headers in responses."""

    def test_json_responses_have_correct_content_type(self, client):
        """JSON responses have application/json content type."""
        response = client.get("/api/health")
        assert "application/json" in response.content_type

    def test_error_responses_have_correct_content_type(self, client):
        """Error responses also use JSON content type."""
        response = client.get("/api/nonexistent-endpoint")
        assert response.status_code == 404
        assert "application/json" in response.content_type
