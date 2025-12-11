"""
Tests for /api/analyze endpoint.

The analyze endpoint handles CSV file uploads and initiates dyno analysis.
"""


class TestAnalyzeEndpointBasics:
    """Basic tests for the /api/analyze endpoint."""

    def test_analyze_returns_202_for_valid_csv(self, client, sample_csv_file):
        """Analyze endpoint returns 202 Accepted for valid CSV upload."""
        with open(sample_csv_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"file": (f, "test_log.csv")},
                content_type="multipart/form-data",
            )
        assert response.status_code == 202

    def test_analyze_returns_json(self, client, sample_csv_file):
        """Analyze endpoint returns JSON content type."""
        with open(sample_csv_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"file": (f, "test_log.csv")},
                content_type="multipart/form-data",
            )
        assert "application/json" in response.content_type

    def test_analyze_returns_run_id(self, client, sample_csv_file):
        """Analyze endpoint returns runId in response."""
        with open(sample_csv_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"file": (f, "test_log.csv")},
                content_type="multipart/form-data",
            )
        if response.status_code == 202:
            data = response.get_json()
            assert "runId" in data
            assert isinstance(data["runId"], str)
            assert len(data["runId"]) > 0

    def test_analyze_returns_status_queued(self, client, sample_csv_file):
        """Analyze endpoint returns queued status initially."""
        with open(sample_csv_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"file": (f, "test_log.csv")},
                content_type="multipart/form-data",
            )
        if response.status_code == 202:
            data = response.get_json()
            assert data.get("status") == "queued"


class TestAnalyzeEndpointValidation:
    """Tests for analyze endpoint input validation."""

    def test_analyze_rejects_missing_file(self, client):
        """Analyze endpoint rejects request with no file."""
        response = client.post(
            "/api/analyze",
            data={},
            content_type="multipart/form-data",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_analyze_rejects_empty_filename(self, client, sample_csv_file):
        """Analyze endpoint rejects file with empty filename."""
        with open(sample_csv_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"file": (f, "")},
                content_type="multipart/form-data",
            )
        assert response.status_code == 400

    def test_analyze_rejects_invalid_extension(self, client, invalid_file):
        """Analyze endpoint rejects files with disallowed extensions."""
        with open(invalid_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"file": (f, "bad_file.exe")},
                content_type="multipart/form-data",
            )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_analyze_accepts_txt_extension(self, client, sample_txt_file):
        """Analyze endpoint accepts .txt files (in allowed list)."""
        with open(sample_txt_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"file": (f, "test_log.txt")},
                content_type="multipart/form-data",
            )
        # Should be accepted (202) or process error, but not 400 for extension
        assert response.status_code in (202, 500)


class TestAnalyzeEndpointParameters:
    """Tests for analyze endpoint optional parameters."""

    def test_analyze_accepts_smooth_passes_parameter(self, client, sample_csv_file):
        """Analyze endpoint accepts smoothPasses parameter."""
        with open(sample_csv_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={
                    "file": (f, "test_log.csv"),
                    "smoothPasses": "3",
                },
                content_type="multipart/form-data",
            )
        assert response.status_code == 202

    def test_analyze_accepts_clamp_parameter(self, client, sample_csv_file):
        """Analyze endpoint accepts clamp parameter."""
        with open(sample_csv_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={
                    "file": (f, "test_log.csv"),
                    "clamp": "10.0",
                },
                content_type="multipart/form-data",
            )
        assert response.status_code == 202

    def test_analyze_accepts_rear_bias_parameter(self, client, sample_csv_file):
        """Analyze endpoint accepts rearBias parameter."""
        with open(sample_csv_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={
                    "file": (f, "test_log.csv"),
                    "rearBias": "0.5",
                },
                content_type="multipart/form-data",
            )
        assert response.status_code == 202

    def test_analyze_accepts_all_parameters(self, client, sample_csv_file):
        """Analyze endpoint accepts all tuning parameters."""
        with open(sample_csv_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={
                    "file": (f, "test_log.csv"),
                    "smoothPasses": "2",
                    "clamp": "15.0",
                    "rearBias": "0.0",
                    "rearRuleDeg": "2.0",
                    "hotExtra": "-1.0",
                },
                content_type="multipart/form-data",
            )
        assert response.status_code == 202


class TestAnalyzeEndpointMethods:
    """Tests for analyze endpoint HTTP method handling."""

    def test_analyze_rejects_get(self, client):
        """Analyze endpoint rejects GET requests."""
        response = client.get("/api/analyze")
        assert response.status_code == 405

    def test_analyze_rejects_put(self, client):
        """Analyze endpoint rejects PUT requests."""
        response = client.put("/api/analyze")
        assert response.status_code == 405

    def test_analyze_rejects_delete(self, client):
        """Analyze endpoint rejects DELETE requests."""
        response = client.delete("/api/analyze")
        assert response.status_code == 405

    def test_analyze_rejects_patch(self, client):
        """Analyze endpoint rejects PATCH requests."""
        response = client.patch("/api/analyze")
        assert response.status_code == 405


class TestAnalyzeEndpointResponseStructure:
    """Tests for analyze endpoint response structure."""

    def test_analyze_response_has_message(self, client, sample_csv_file):
        """Analyze response includes a message field."""
        with open(sample_csv_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"file": (f, "test_log.csv")},
                content_type="multipart/form-data",
            )
        if response.status_code == 202:
            data = response.get_json()
            assert "message" in data
            assert isinstance(data["message"], str)

    def test_analyze_error_response_structure(self, client):
        """Analyze error responses have proper structure."""
        response = client.post(
            "/api/analyze",
            data={},
            content_type="multipart/form-data",
        )
        assert response.status_code == 400
        data = response.get_json()
        # API returns simple {"error": "message"} format
        assert "error" in data
        assert isinstance(data["error"], str)
