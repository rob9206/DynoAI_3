"""
API Key Authentication for DynoAI.

Provides decorator-based API key authentication for protecting endpoints.
Supports:
- Environment variable configuration (API_KEYS)
- File-based key storage (API_KEYS_FILE)
- Optional enforcement (disabled by default for development)
- API key generation utilities
"""

import os
import secrets
import logging
from functools import wraps
from typing import Optional, Set
from pathlib import Path

from flask import request, g, jsonify

logger = logging.getLogger(__name__)


class APIKeyAuth:
    """API Key authentication handler."""

    def __init__(self):
        """Initialize auth handler and load API keys."""
        self.enabled = os.getenv("API_AUTH_ENABLED", "false").lower() == "true"
        self._valid_keys = self._load_api_keys()

        if self.enabled:
            logger.info(f"API authentication ENABLED with {len(self._valid_keys)} valid key(s)")
        else:
            logger.info("API authentication DISABLED (development mode)")

    def _load_api_keys(self) -> Set[str]:
        """
        Load valid API keys from environment or file.

        Returns:
            Set of valid API key strings
        """
        keys: Set[str] = set()

        # Load from environment (comma-separated)
        env_keys = os.getenv("API_KEYS", "")
        if env_keys:
            loaded = [k.strip() for k in env_keys.split(",") if k.strip()]
            keys.update(loaded)
            logger.debug(f"Loaded {len(loaded)} key(s) from API_KEYS environment variable")

        # Load from file if exists
        keys_file = os.getenv("API_KEYS_FILE", "")
        if keys_file:
            keys_path = Path(keys_file)
            if keys_path.exists():
                try:
                    with open(keys_path) as f:
                        file_keys = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                        keys.update(file_keys)
                        logger.debug(f"Loaded {len(file_keys)} key(s) from {keys_file}")
                except Exception as e:
                    logger.error(f"Failed to load API keys from {keys_file}: {e}")
            else:
                logger.warning(f"API_KEYS_FILE specified but not found: {keys_file}")

        if self.enabled and not keys:
            logger.warning("API authentication enabled but no keys configured!")

        return keys

    def validate_key(self, api_key: str) -> bool:
        """
        Validate an API key.

        Args:
            api_key: The API key to validate

        Returns:
            True if valid, False otherwise
        """
        if not self.enabled:
            return True

        if not api_key:
            return False

        # Constant-time comparison to prevent timing attacks
        return api_key in self._valid_keys

    def generate_key(self) -> str:
        """
        Generate a new API key.

        Returns:
            A new random API key with dynoai_ prefix
        """
        return f"dynoai_{secrets.token_urlsafe(32)}"

    def reload_keys(self) -> int:
        """
        Reload API keys from environment/file.

        Returns:
            Number of keys loaded

        Useful for hot-reloading keys without restarting the server.
        """
        self._valid_keys = self._load_api_keys()
        logger.info(f"Reloaded API keys: {len(self._valid_keys)} valid key(s)")
        return len(self._valid_keys)


# Global instance
_auth: Optional[APIKeyAuth] = None


def get_auth() -> APIKeyAuth:
    """
    Get or create the global auth instance.

    Returns:
        The global APIKeyAuth instance
    """
    global _auth
    if _auth is None:
        _auth = APIKeyAuth()
    return _auth


def require_api_key(f):
    """
    Decorator to require API key authentication on an endpoint.

    Usage:
        @app.route("/api/protected")
        @require_api_key
        def protected():
            return jsonify({"message": "Access granted"})

    The API key should be provided in the X-API-Key header.
    If authentication is disabled (development mode), this decorator does nothing.

    Returns 401 if no key is provided.
    Returns 403 if an invalid key is provided.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        auth = get_auth()

        # If auth is disabled, allow all requests
        if not auth.enabled:
            return f(*args, **kwargs)

        # Extract API key from header
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            logger.warning(
                f"Unauthorized request to {request.path} - No API key provided. "
                f"IP: {request.remote_addr}"
            )
            return (
                jsonify(
                    {
                        "error": {
                            "code": "AUTH_REQUIRED",
                            "message": "API key required. Provide X-API-Key header.",
                        }
                    }
                ),
                401,
            )

        if not auth.validate_key(api_key):
            logger.warning(
                f"Forbidden request to {request.path} - Invalid API key. "
                f"IP: {request.remote_addr}, Key prefix: {api_key[:10]}..."
            )
            return (
                jsonify(
                    {
                        "error": {
                            "code": "INVALID_API_KEY",
                            "message": "Invalid or expired API key.",
                        }
                    }
                ),
                403,
            )

        # Store the API key in Flask's g object for potential logging/auditing
        g.api_key = api_key
        g.authenticated = True

        logger.debug(f"Authenticated request to {request.path} (Key: {api_key[:10]}...)")

        return f(*args, **kwargs)

    return decorated


def generate_api_key() -> str:
    """
    Utility function to generate a new API key.

    Returns:
        A new random API key

    Example:
        >>> from api.auth import generate_api_key
        >>> key = generate_api_key()
        >>> print(f"New API key: {key}")
    """
    return get_auth().generate_key()


# CLI utility for generating keys
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        print(f"Generating {count} API key(s):\n")
        for i in range(count):
            key = generate_api_key()
            print(f"{i + 1}. {key}")
    else:
        print("Usage: python -m api.auth generate [count]")
        print("\nExample:")
        print("  python -m api.auth generate 5")
