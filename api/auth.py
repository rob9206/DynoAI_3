"""
DynoAI API Key Authentication.

Provides API key validation and authentication decorator for protecting endpoints.
"""

import logging
import os
import secrets
from functools import wraps
from typing import Callable, Optional, Set, TypeVar

from flask import g, jsonify, request

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)


class APIKeyAuth:
    """
    API Key authentication handler.

    Supports loading API keys from:
    - Environment variable (comma-separated)
    - File (one key per line)
    """

    def __init__(self) -> None:
        """Initialize authentication handler."""
        self.enabled = os.getenv("API_AUTH_ENABLED", "false").lower() == "true"
        self._valid_keys: Set[str] = self._load_api_keys()

        if self.enabled:
            key_count = len(self._valid_keys)
            logger.info(f"API authentication enabled with {key_count} valid key(s)")
        else:
            logger.debug("API authentication disabled")

    def _load_api_keys(self) -> Set[str]:
        """
        Load valid API keys from environment or file.

        Returns:
            Set of valid API keys.
        """
        keys: Set[str] = set()

        # Load from environment variable (comma-separated)
        env_keys = os.getenv("API_KEYS", "")
        if env_keys:
            loaded_keys = [k.strip() for k in env_keys.split(",") if k.strip()]
            keys.update(loaded_keys)
            if loaded_keys:
                logger.debug(f"Loaded {len(loaded_keys)} API key(s) from environment")

        # Load from file if specified and exists
        keys_file = os.getenv("API_KEYS_FILE", "")
        if keys_file and os.path.exists(keys_file):
            try:
                with open(keys_file, "r", encoding="utf-8") as f:
                    file_keys = [
                        line.strip()
                        for line in f
                        if line.strip() and not line.strip().startswith("#")
                    ]
                    keys.update(file_keys)
                    logger.debug(f"Loaded {len(file_keys)} API key(s) from file")
            except (IOError, OSError) as e:
                logger.warning(f"Failed to load API keys from file: {e}")

        return keys

    def validate_key(self, api_key: str) -> bool:
        """
        Validate an API key.

        Args:
            api_key: The API key to validate.

        Returns:
            True if valid (or auth disabled), False otherwise.
        """
        if not self.enabled:
            return True
        return api_key in self._valid_keys

    def reload_keys(self) -> None:
        """Reload API keys from sources (useful for key rotation)."""
        self._valid_keys = self._load_api_keys()
        logger.info(f"Reloaded API keys: {len(self._valid_keys)} valid key(s)")

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new secure API key.

        Returns:
            A new API key in format 'dynoai_<random>'.
        """
        return f"dynoai_{secrets.token_urlsafe(32)}"


# Global instance (lazy loaded)
_auth: Optional[APIKeyAuth] = None


def get_auth() -> APIKeyAuth:
    """
    Get or create the global authentication instance.

    Returns:
        The APIKeyAuth instance.
    """
    global _auth
    if _auth is None:
        _auth = APIKeyAuth()
    return _auth


def reset_auth() -> None:
    """
    Reset the global authentication instance.

    Useful for testing or reloading configuration.
    """
    global _auth
    _auth = None


def require_api_key(f: F) -> F:
    """
    Decorator to require API key authentication.

    When API_AUTH_ENABLED=true:
    - Requires X-API-Key header
    - Returns 401 if header missing
    - Returns 403 if key invalid
    - Sets g.api_key for downstream use

    When API_AUTH_ENABLED=false:
    - Passes through without validation

    Usage:
        @app.route("/api/sensitive", methods=["POST"])
        @require_api_key
        def sensitive_endpoint():
            # Only accessible with valid API key
            pass
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        auth = get_auth()

        # Skip authentication if disabled
        if not auth.enabled:
            return f(*args, **kwargs)

        # Get API key from header
        api_key = request.headers.get("X-API-Key")

        # Get request ID for error responses
        request_id = getattr(g, "request_id", None)

        # Check if key is provided
        if not api_key:
            logger.warning(
                f"Authentication failed: Missing API key "
                f"(path={request.path}, ip={request.remote_addr})"
            )
            error_response = {
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "API key required. Provide X-API-Key header.",
                }
            }
            if request_id:
                error_response["error"]["request_id"] = request_id
            return jsonify(error_response), 401

        # Validate key
        if not auth.validate_key(api_key):
            # Log with masked key for security audit
            masked_key = api_key[:8] + "..." if len(api_key) > 8 else "***"
            logger.warning(
                f"Authentication failed: Invalid API key "
                f"(key={masked_key}, path={request.path}, ip={request.remote_addr})"
            )
            error_response = {
                "error": {
                    "code": "INVALID_API_KEY",
                    "message": "Invalid or expired API key.",
                }
            }
            if request_id:
                error_response["error"]["request_id"] = request_id
            return jsonify(error_response), 403

        # Store validated key in request context
        g.api_key = api_key

        # Log successful authentication at debug level
        masked_key = api_key[:8] + "..." if len(api_key) > 8 else api_key[:4] + "..."
        logger.debug(f"Authenticated request (key={masked_key}, path={request.path})")

        return f(*args, **kwargs)

    return decorated  # type: ignore
