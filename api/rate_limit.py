"""
DynoAI Rate Limiting Configuration.

Protects API endpoints from abuse with configurable rate limits.
"""

import os
from typing import Optional

from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def get_client_identifier() -> str:
    """
    Get client identifier for rate limiting.

    Uses X-Forwarded-For header if behind a proxy, otherwise remote address.
    Can be extended to use API keys for authenticated clients.
    """
    # Check for API key first (future enhancement)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"api_key:{api_key}"

    # Use forwarded address if behind proxy
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()

    return get_remote_address()


# Module-level limiter instance (initialized by init_rate_limiter)
_limiter: Optional[Limiter] = None


def get_limiter() -> Optional[Limiter]:
    """Get the rate limiter instance."""
    return _limiter


def init_rate_limiter(app: Flask) -> Limiter:
    """
    Initialize rate limiter with configuration from environment.

    Environment variables:
        RATE_LIMIT_ENABLED: "true" or "false" (default: "true")
        RATE_LIMIT_DEFAULT: Default limit (default: "100/minute")
        RATE_LIMIT_STORAGE: Storage backend URL (default: "memory://")
    """
    global _limiter

    enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    default_limit = os.getenv("RATE_LIMIT_DEFAULT", "100/minute")
    storage_uri = os.getenv("RATE_LIMIT_STORAGE", "memory://")

    limiter = Limiter(
        key_func=get_client_identifier,
        app=app,
        default_limits=[default_limit] if enabled else [],
        storage_uri=storage_uri,
        strategy="fixed-window",
        headers_enabled=True,  # Add X-RateLimit-* headers
    )

    # Custom error handler for rate limit exceeded
    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        request_id = getattr(g, "request_id", None)
        response = {
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please slow down.",
                "details": {
                    "retry_after": str(e.description) if e.description else "60 seconds"
                },
            }
        }
        if request_id:
            response["error"]["request_id"] = request_id
        return jsonify(response), 429

    _limiter = limiter
    return limiter


class RateLimits:
    """Pre-defined rate limits for different endpoint types."""

    # Expensive operations (file upload, analysis)
    EXPENSIVE = "5/minute;20/hour"

    # Standard API calls
    STANDARD = "60/minute"

    # Read-only operations
    READ_ONLY = "120/minute"

    # Health checks (very permissive)
    HEALTH = "300/minute"
