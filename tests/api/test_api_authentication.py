"""
Tests for API Key Authentication.

Tests:
- Authentication enabled/disabled
- Valid/invalid API keys
- Missing API keys
- Key generation
- Protected endpoints
"""

import os
import pytest
from unittest.mock import patch, mock_open
from flask import Flask

from api.auth import APIKeyAuth, require_api_key, generate_api_key, get_auth


# =============================================================================
# Test APIKeyAuth Class
# =============================================================================


def test_auth_disabled_by_default():
    """Auth should be disabled by default (development mode)."""
    with patch.dict(os.environ, {}, clear=True):
        auth = APIKeyAuth()
        assert auth.enabled is False
        assert len(auth._valid_keys) == 0


def test_auth_enabled_from_env():
    """Auth should be enabled when API_AUTH_ENABLED=true."""
    with patch.dict(os.environ, {"API_AUTH_ENABLED": "true"}, clear=True):
        auth = APIKeyAuth()
        assert auth.enabled is True


def test_load_keys_from_environment():
    """Should load comma-separated keys from API_KEYS environment variable."""
    test_keys = "key1,key2,key3"
    with patch.dict(os.environ, {"API_KEYS": test_keys}, clear=True):
        auth = APIKeyAuth()
        assert len(auth._valid_keys) == 3
        assert "key1" in auth._valid_keys
        assert "key2" in auth._valid_keys
        assert "key3" in auth._valid_keys


def test_load_keys_from_file(tmp_path):
    """Should load keys from file specified in API_KEYS_FILE."""
    # Create a temporary keys file
    keys_file = tmp_path / "api_keys.txt"
    keys_file.write_text("file_key1\nfile_key2\n# Comment line\n\nfile_key3\n")

    with patch.dict(os.environ, {"API_KEYS_FILE": str(keys_file)}, clear=True):
        auth = APIKeyAuth()
        assert len(auth._valid_keys) == 3
        assert "file_key1" in auth._valid_keys
        assert "file_key2" in auth._valid_keys
        assert "file_key3" in auth._valid_keys
        assert "# Comment line" not in auth._valid_keys  # Comments should be skipped


def test_load_keys_from_both_sources(tmp_path):
    """Should load keys from both environment and file."""
    keys_file = tmp_path / "api_keys.txt"
    keys_file.write_text("file_key\n")

    with patch.dict(
        os.environ,
        {"API_KEYS": "env_key", "API_KEYS_FILE": str(keys_file)},
        clear=True,
    ):
        auth = APIKeyAuth()
        assert len(auth._valid_keys) == 2
        assert "env_key" in auth._valid_keys
        assert "file_key" in auth._valid_keys


def test_validate_key_when_disabled():
    """Should allow any key when auth is disabled."""
    with patch.dict(os.environ, {"API_AUTH_ENABLED": "false"}, clear=True):
        auth = APIKeyAuth()
        assert auth.validate_key("any_key") is True
        assert auth.validate_key("") is True
        assert auth.validate_key(None) is True  # type: ignore


def test_validate_valid_key():
    """Should accept valid API keys."""
    with patch.dict(
        os.environ,
        {"API_AUTH_ENABLED": "true", "API_KEYS": "valid_key"},
        clear=True,
    ):
        auth = APIKeyAuth()
        assert auth.validate_key("valid_key") is True


def test_validate_invalid_key():
    """Should reject invalid API keys."""
    with patch.dict(
        os.environ,
        {"API_AUTH_ENABLED": "true", "API_KEYS": "valid_key"},
        clear=True,
    ):
        auth = APIKeyAuth()
        assert auth.validate_key("invalid_key") is False
        assert auth.validate_key("") is False


def test_generate_key():
    """Should generate API keys with dynoai_ prefix."""
    auth = APIKeyAuth()
    key1 = auth.generate_key()
    key2 = auth.generate_key()

    assert key1.startswith("dynoai_")
    assert key2.startswith("dynoai_")
    assert key1 != key2  # Keys should be unique
    assert len(key1) > 20  # Should be reasonably long


def test_reload_keys(tmp_path):
    """Should reload keys from environment/file."""
    keys_file = tmp_path / "api_keys.txt"
    keys_file.write_text("initial_key\n")

    with patch.dict(os.environ, {"API_KEYS_FILE": str(keys_file)}, clear=True):
        auth = APIKeyAuth()
        assert len(auth._valid_keys) == 1
        assert "initial_key" in auth._valid_keys

        # Update the file
        keys_file.write_text("initial_key\nnew_key\n")

        # Reload
        count = auth.reload_keys()
        assert count == 2
        assert "new_key" in auth._valid_keys


# =============================================================================
# Test Decorator
# =============================================================================


def test_require_api_key_decorator_allows_when_disabled():
    """Decorator should allow all requests when auth is disabled."""
    app = Flask(__name__)

    @app.route("/test")
    @require_api_key
    def test_endpoint():
        return {"message": "success"}

    with patch.dict(os.environ, {"API_AUTH_ENABLED": "false"}, clear=True):
        # Reset global auth instance
        import api.auth

        api.auth._auth = None

        with app.test_client() as client:
            response = client.get("/test")
            assert response.status_code == 200
            assert response.json == {"message": "success"}


def test_require_api_key_decorator_rejects_missing_key():
    """Decorator should return 401 when no API key is provided."""
    app = Flask(__name__)

    @app.route("/test")
    @require_api_key
    def test_endpoint():
        return {"message": "success"}

    with patch.dict(
        os.environ,
        {"API_AUTH_ENABLED": "true", "API_KEYS": "valid_key"},
        clear=True,
    ):
        # Reset global auth instance
        import api.auth

        api.auth._auth = None

        with app.test_client() as client:
            response = client.get("/test")
            assert response.status_code == 401
            assert response.json["error"]["code"] == "AUTH_REQUIRED"


def test_require_api_key_decorator_rejects_invalid_key():
    """Decorator should return 403 when invalid API key is provided."""
    app = Flask(__name__)

    @app.route("/test")
    @require_api_key
    def test_endpoint():
        return {"message": "success"}

    with patch.dict(
        os.environ,
        {"API_AUTH_ENABLED": "true", "API_KEYS": "valid_key"},
        clear=True,
    ):
        # Reset global auth instance
        import api.auth

        api.auth._auth = None

        with app.test_client() as client:
            response = client.get("/test", headers={"X-API-Key": "invalid_key"})
            assert response.status_code == 403
            assert response.json["error"]["code"] == "INVALID_API_KEY"


def test_require_api_key_decorator_allows_valid_key():
    """Decorator should allow requests with valid API key."""
    app = Flask(__name__)

    @app.route("/test")
    @require_api_key
    def test_endpoint():
        return {"message": "success"}

    with patch.dict(
        os.environ,
        {"API_AUTH_ENABLED": "true", "API_KEYS": "valid_key"},
        clear=True,
    ):
        # Reset global auth instance
        import api.auth

        api.auth._auth = None

        with app.test_client() as client:
            response = client.get("/test", headers={"X-API-Key": "valid_key"})
            assert response.status_code == 200
            assert response.json == {"message": "success"}


# =============================================================================
# Test Utility Functions
# =============================================================================


def test_generate_api_key_utility():
    """Should generate API keys via utility function."""
    key = generate_api_key()
    assert key.startswith("dynoai_")
    assert len(key) > 20


def test_get_auth_singleton():
    """Should return the same auth instance."""
    auth1 = get_auth()
    auth2 = get_auth()
    assert auth1 is auth2


# =============================================================================
# Integration Tests
# =============================================================================


def test_auth_with_multiple_keys():
    """Should accept any of multiple valid keys."""
    app = Flask(__name__)

    @app.route("/test")
    @require_api_key
    def test_endpoint():
        return {"message": "success"}

    with patch.dict(
        os.environ,
        {"API_AUTH_ENABLED": "true", "API_KEYS": "key1,key2,key3"},
        clear=True,
    ):
        # Reset global auth instance
        import api.auth

        api.auth._auth = None

        with app.test_client() as client:
            # All keys should work
            for key in ["key1", "key2", "key3"]:
                response = client.get("/test", headers={"X-API-Key": key})
                assert response.status_code == 200

            # Invalid key should still be rejected
            response = client.get("/test", headers={"X-API-Key": "invalid"})
            assert response.status_code == 403

