"""
Tests for Request ID Middleware.

Verifies that:
- Every request gets a unique ID
- ID returned in X-Request-ID response header
- ID included in error responses
- Client can provide own ID via X-Request-ID header
- ID is 8-12 characters (specifically 12)
"""

import re


class TestRequestIDMiddleware:
    """Test suite for request ID middleware functionality."""

    def test_auto_generated_request_id_in_header(self, client):
        """Test that response includes auto-generated X-Request-ID header."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert request_id is not None
        assert len(request_id) == 12  # UUID hex[:12]

    def test_request_id_is_hex_format(self, client):
        """Test that generated request ID is valid hex."""
        response = client.get("/api/health")
        request_id = response.headers["X-Request-ID"]
        # Should be lowercase hex characters only
        assert re.match(r"^[a-f0-9]{12}$", request_id)

    def test_unique_request_ids(self, client):
        """Test that each request gets a unique ID."""
        ids = set()
        for _ in range(10):
            response = client.get("/api/health")
            request_id = response.headers["X-Request-ID"]
            ids.add(request_id)
        # All 10 IDs should be unique
        assert len(ids) == 10

    def test_client_provided_request_id(self, client):
        """Test that client-provided X-Request-ID is passed through."""
        custom_id = "my-custom-id-123"
        response = client.get("/api/health", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == custom_id

    def test_client_provided_id_with_special_chars(self, client):
        """Test client-provided ID with various characters."""
        custom_id = "trace-abc_123.xyz"
        response = client.get("/api/health", headers={"X-Request-ID": custom_id})
        assert response.headers["X-Request-ID"] == custom_id

    def test_request_id_in_error_response(self, client):
        """Test that request ID is included in error responses."""
        # Request a non-existent endpoint to trigger 404
        response = client.get("/api/nonexistent")
        assert response.status_code == 404

        # Check header
        assert "X-Request-ID" in response.headers
        header_id = response.headers["X-Request-ID"]

        # Check response body contains request_id
        data = response.get_json()
        assert "error" in data
        assert "request_id" in data["error"]
        assert data["error"]["request_id"] == header_id

    def test_client_id_in_error_response(self, client):
        """Test that client-provided ID appears in error responses."""
        custom_id = "client-trace-456"
        response = client.get("/api/nonexistent", headers={"X-Request-ID": custom_id})
        assert response.status_code == 404

        # Check header matches custom ID
        assert response.headers["X-Request-ID"] == custom_id

        # Check response body contains custom ID
        data = response.get_json()
        assert data["error"]["request_id"] == custom_id

    def test_request_id_on_post_requests(self, client):
        """Test request ID works on POST requests."""
        response = client.post("/api/analyze")  # Will fail validation
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 12

    def test_request_id_on_validation_error(self, client):
        """Test request ID in validation error response."""
        # Use a run status endpoint with invalid run_id to trigger validation error
        response = client.get("/api/status/invalid-run-id")
        assert response.status_code == 404

        data = response.get_json()
        assert "error" in data
        assert "request_id" in data["error"]
        assert data["error"]["request_id"] == response.headers["X-Request-ID"]

    def test_empty_client_id_generates_new(self, client):
        """Test that empty X-Request-ID header generates new ID."""
        response = client.get("/api/health", headers={"X-Request-ID": ""})
        # Empty string should trigger auto-generation
        request_id = response.headers["X-Request-ID"]
        assert request_id != ""
        assert len(request_id) == 12


class TestRequestIDHelper:
    """Test the get_request_id helper function."""

    def test_get_request_id_import(self):
        """Test that get_request_id can be imported."""
        from api.middleware import get_request_id

        assert callable(get_request_id)

    def test_get_request_id_raises_outside_context(self):
        """Test get_request_id raises RuntimeError outside request context."""
        import pytest

        from api.middleware import get_request_id

        # Outside request context, Flask g raises RuntimeError
        with pytest.raises(
            RuntimeError, match="Working outside of application context"
        ):
            get_request_id()

    def test_generate_request_id_format(self):
        """Test that generate_request_id produces correct format."""
        from api.middleware import generate_request_id

        request_id = generate_request_id()
        assert isinstance(request_id, str)
        assert len(request_id) == 12
        assert re.match(r"^[a-f0-9]{12}$", request_id)

    def test_generate_request_id_uniqueness(self):
        """Test that generate_request_id produces unique IDs."""
        from api.middleware import generate_request_id

        ids = {generate_request_id() for _ in range(100)}
        assert len(ids) == 100  # All unique
