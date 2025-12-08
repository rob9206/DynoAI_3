"""
Tests for API key authentication functionality.

Tests cover:
- Authentication enabled/disabled behavior
- Missing API key (401)
- Invalid API key (403)
- Valid API key (200)
- Health endpoints remain public
- Key loading from env and file
"""

import os
import tempfile
from unittest.mock import patch

import pytest
from flask import Flask


class TestAPIKeyAuthClass:
    """Tests for the APIKeyAuth class."""

    def test_auth_disabled_by_default(self):
        """Authentication is disabled by default."""
        from api.auth import APIKeyAuth, reset_auth

        reset_auth()
        with patch.dict(os.environ, {}, clear=True):
            # Remove the env vars to test defaults
            os.environ.pop("API_AUTH_ENABLED", None)
            os.environ.pop("API_KEYS", None)
            auth = APIKeyAuth()
            assert auth.enabled is False

    def test_auth_enabled_via_env(self):
        """Authentication can be enabled via environment variable."""
        from api.auth import APIKeyAuth, reset_auth

        reset_auth()
        with patch.dict(os.environ, {"API_AUTH_ENABLED": "true"}):
            auth = APIKeyAuth()
            assert auth.enabled is True

    def test_load_keys_from_env(self):
        """API keys can be loaded from API_KEYS environment variable."""
        from api.auth import APIKeyAuth, reset_auth

        reset_auth()
        with patch.dict(
            os.environ, {"API_AUTH_ENABLED": "true", "API_KEYS": "key1,key2,key3"}
        ):
            auth = APIKeyAuth()
            assert auth.validate_key("key1") is True
            assert auth.validate_key("key2") is True
            assert auth.validate_key("key3") is True
            assert auth.validate_key("invalid") is False

    def test_load_keys_from_env_with_whitespace(self):
        """API keys are trimmed of whitespace."""
        from api.auth import APIKeyAuth, reset_auth

        reset_auth()
        with patch.dict(
            os.environ, {"API_AUTH_ENABLED": "true", "API_KEYS": " key1 , key2 , key3 "}
        ):
            auth = APIKeyAuth()
            assert auth.validate_key("key1") is True
            assert auth.validate_key(" key1 ") is False  # Not trimmed input

    def test_load_keys_from_file(self):
        """API keys can be loaded from a file."""
        from api.auth import APIKeyAuth, reset_auth

        reset_auth()
        # Create temp file and close it before use (Windows compatibility)
        fd, filepath = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(fd, "w") as f:
                f.write("file_key_1\n")
                f.write("file_key_2\n")
                f.write("# comment line\n")
                f.write("file_key_3\n")

            with patch.dict(
                os.environ, {"API_AUTH_ENABLED": "true", "API_KEYS_FILE": filepath}
            ):
                auth = APIKeyAuth()
                assert auth.validate_key("file_key_1") is True
                assert auth.validate_key("file_key_2") is True
                assert auth.validate_key("file_key_3") is True
                assert auth.validate_key("# comment line") is False
        finally:
            os.unlink(filepath)

    def test_load_keys_from_env_and_file(self):
        """API keys can be loaded from both env and file."""
        from api.auth import APIKeyAuth, reset_auth

        reset_auth()
        # Create temp file and close it before use (Windows compatibility)
        fd, filepath = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(fd, "w") as f:
                f.write("file_key\n")

            with patch.dict(
                os.environ,
                {
                    "API_AUTH_ENABLED": "true",
                    "API_KEYS": "env_key",
                    "API_KEYS_FILE": filepath,
                },
            ):
                auth = APIKeyAuth()
                assert auth.validate_key("env_key") is True
                assert auth.validate_key("file_key") is True
        finally:
            os.unlink(filepath)

    def test_validate_key_when_disabled(self):
        """When auth disabled, all keys are valid."""
        from api.auth import APIKeyAuth, reset_auth

        reset_auth()
        with patch.dict(os.environ, {"API_AUTH_ENABLED": "false", "API_KEYS": "key1"}):
            auth = APIKeyAuth()
            assert auth.validate_key("any_key") is True
            assert auth.validate_key("another_key") is True

    def test_generate_key_format(self):
        """Generated keys have correct format."""
        from api.auth import APIKeyAuth

        key = APIKeyAuth.generate_key()
        assert key.startswith("dynoai_")
        assert len(key) > 20  # Should be reasonably long

    def test_generate_key_uniqueness(self):
        """Generated keys are unique."""
        from api.auth import APIKeyAuth

        keys = [APIKeyAuth.generate_key() for _ in range(100)]
        assert len(keys) == len(set(keys))  # All unique

    def test_reload_keys(self):
        """Keys can be reloaded at runtime."""
        from api.auth import APIKeyAuth, reset_auth

        reset_auth()
        with patch.dict(os.environ, {"API_AUTH_ENABLED": "true", "API_KEYS": "key1"}):
            auth = APIKeyAuth()
            assert auth.validate_key("key1") is True
            assert auth.validate_key("key2") is False

            # Simulate adding a new key
            with patch.dict(os.environ, {"API_KEYS": "key1,key2"}):
                auth.reload_keys()
                assert auth.validate_key("key2") is True


class TestRequireApiKeyDecorator:
    """Tests for the @require_api_key decorator."""

    @pytest.fixture
    def app_with_auth_enabled(self):
        """Flask app with auth enabled."""
        from api.auth import require_api_key, reset_auth

        reset_auth()

        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.route("/protected", methods=["GET", "POST"])
        @require_api_key
        def protected():
            return {"message": "success"}

        @app.route("/public", methods=["GET"])
        def public():
            return {"message": "public"}

        with patch.dict(
            os.environ, {"API_AUTH_ENABLED": "true", "API_KEYS": "valid_key,test_key"}
        ):
            reset_auth()
            with app.test_client() as client:
                yield client

        reset_auth()

    @pytest.fixture
    def app_with_auth_disabled(self):
        """Flask app with auth disabled."""
        from api.auth import require_api_key, reset_auth

        reset_auth()

        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.route("/protected", methods=["GET", "POST"])
        @require_api_key
        def protected():
            return {"message": "success"}

        with patch.dict(os.environ, {"API_AUTH_ENABLED": "false"}):
            reset_auth()
            with app.test_client() as client:
                yield client

        reset_auth()

    def test_returns_401_when_key_missing(self, app_with_auth_enabled):
        """Returns 401 when X-API-Key header is missing."""
        response = app_with_auth_enabled.get("/protected")
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"]["code"] == "AUTH_REQUIRED"
        assert "X-API-Key" in data["error"]["message"]

    def test_returns_403_when_key_invalid(self, app_with_auth_enabled):
        """Returns 403 when X-API-Key is invalid."""
        response = app_with_auth_enabled.get(
            "/protected", headers={"X-API-Key": "wrong_key"}
        )
        assert response.status_code == 403
        data = response.get_json()
        assert data["error"]["code"] == "INVALID_API_KEY"

    def test_returns_200_when_key_valid(self, app_with_auth_enabled):
        """Returns 200 when X-API-Key is valid."""
        response = app_with_auth_enabled.get(
            "/protected", headers={"X-API-Key": "valid_key"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["message"] == "success"

    def test_accepts_multiple_valid_keys(self, app_with_auth_enabled):
        """Accepts any of the configured valid keys."""
        response1 = app_with_auth_enabled.get(
            "/protected", headers={"X-API-Key": "valid_key"}
        )
        assert response1.status_code == 200

        response2 = app_with_auth_enabled.get(
            "/protected", headers={"X-API-Key": "test_key"}
        )
        assert response2.status_code == 200

    def test_works_with_post_requests(self, app_with_auth_enabled):
        """Works with POST requests."""
        response = app_with_auth_enabled.post(
            "/protected", headers={"X-API-Key": "valid_key"}
        )
        assert response.status_code == 200

    def test_public_endpoints_unaffected(self, app_with_auth_enabled):
        """Endpoints without decorator are unaffected."""
        response = app_with_auth_enabled.get("/public")
        assert response.status_code == 200

    def test_auth_disabled_allows_all(self, app_with_auth_disabled):
        """When auth disabled, all requests pass through."""
        # No header
        response = app_with_auth_disabled.get("/protected")
        assert response.status_code == 200

        # Invalid header
        response = app_with_auth_disabled.get(
            "/protected", headers={"X-API-Key": "any_key"}
        )
        assert response.status_code == 200


class TestAuthIntegrationWithMainApp:
    """Integration tests with the main DynoAI app."""

    @pytest.fixture
    def client_auth_disabled(self):
        """Test client with auth disabled (default)."""
        from api.auth import reset_auth

        reset_auth()
        with patch.dict(os.environ, {"API_AUTH_ENABLED": "false"}):
            reset_auth()
            from api.app import app

            app.config["TESTING"] = True
            with app.test_client() as client:
                yield client

        reset_auth()

    @pytest.fixture
    def client_auth_enabled(self):
        """Test client with auth enabled."""
        from api.auth import reset_auth

        reset_auth()
        with patch.dict(
            os.environ,
            {"API_AUTH_ENABLED": "true", "API_KEYS": "dynoai_test_key_12345"},
        ):
            reset_auth()
            from api.app import app

            app.config["TESTING"] = True
            with app.test_client() as client:
                yield client

        reset_auth()

    def test_health_endpoint_always_public(self, client_auth_enabled):
        """Health endpoint works without authentication."""
        response = client_auth_enabled.get("/api/health")
        assert response.status_code == 200

    def test_health_live_endpoint_always_public(self, client_auth_enabled):
        """Health live endpoint works without authentication."""
        response = client_auth_enabled.get("/api/health/live")
        assert response.status_code == 200

    def test_health_ready_endpoint_always_public(self, client_auth_enabled):
        """Health ready endpoint works without authentication."""
        response = client_auth_enabled.get("/api/health/ready")
        assert response.status_code == 200

    def test_runs_endpoint_public(self, client_auth_disabled):
        """Runs endpoint works without authentication (read-only)."""
        response = client_auth_disabled.get("/api/runs")
        assert response.status_code == 200

    def test_analyze_requires_auth_when_enabled(self, client_auth_enabled):
        """Analyze endpoint requires auth when enabled."""
        # Without key
        response = client_auth_enabled.post("/api/analyze")
        assert response.status_code == 401

        # With invalid key
        response = client_auth_enabled.post(
            "/api/analyze", headers={"X-API-Key": "wrong"}
        )
        assert response.status_code == 403

    def test_analyze_works_with_valid_key(self, client_auth_enabled, tmp_path):
        """Analyze endpoint works with valid API key."""
        # Create a sample CSV file
        csv_content = "timestamp,rpm,afr_front,afr_rear\n0,1000,14.7,14.7"
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        with open(csv_file, "rb") as f:
            response = client_auth_enabled.post(
                "/api/analyze",
                data={"file": (f, "test.csv")},
                content_type="multipart/form-data",
                headers={"X-API-Key": "dynoai_test_key_12345"},
            )
        # Should be 202 (accepted) or similar, not auth error
        assert response.status_code in [200, 202, 400, 500]  # Not 401 or 403

    def test_analyze_works_when_auth_disabled(self, client_auth_disabled):
        """Analyze endpoint works without key when auth disabled."""
        response = client_auth_disabled.post("/api/analyze")
        # May fail for other reasons (no file), but not auth
        assert response.status_code != 401
        assert response.status_code != 403


class TestAuthErrorResponses:
    """Tests for authentication error response format."""

    @pytest.fixture
    def client(self):
        """Flask app with auth enabled for error format testing."""
        from api.auth import require_api_key, reset_auth

        reset_auth()

        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.route("/test", methods=["GET"])
        @require_api_key
        def test_endpoint():
            return {"ok": True}

        with patch.dict(os.environ, {"API_AUTH_ENABLED": "true", "API_KEYS": "key"}):
            reset_auth()
            with app.test_client() as client:
                yield client

        reset_auth()

    def test_401_response_structure(self, client):
        """401 response has proper error structure."""
        response = client.get("/test")
        assert response.status_code == 401
        assert response.content_type == "application/json"

        data = response.get_json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert data["error"]["code"] == "AUTH_REQUIRED"

    def test_403_response_structure(self, client):
        """403 response has proper error structure."""
        response = client.get("/test", headers={"X-API-Key": "invalid"})
        assert response.status_code == 403
        assert response.content_type == "application/json"

        data = response.get_json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert data["error"]["code"] == "INVALID_API_KEY"


class TestGlobalAuthInstance:
    """Tests for global auth instance management."""

    def test_get_auth_returns_singleton(self):
        """get_auth returns the same instance."""
        from api.auth import get_auth, reset_auth

        reset_auth()
        auth1 = get_auth()
        auth2 = get_auth()
        assert auth1 is auth2

    def test_reset_auth_clears_instance(self):
        """reset_auth clears the global instance."""
        from api.auth import get_auth, reset_auth

        auth1 = get_auth()
        reset_auth()
        auth2 = get_auth()
        assert auth1 is not auth2
