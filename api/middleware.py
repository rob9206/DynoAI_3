"""
DynoAI Request Middleware.

Provides request ID tracking and other cross-cutting concerns.
"""

import uuid
from typing import Optional

from flask import Flask, Response, g, request


def generate_request_id() -> str:
    """Generate a short, unique request ID."""
    return uuid.uuid4().hex[:12]  # 12 chars is enough for tracing


def init_request_id_middleware(app: Flask) -> None:
    """
    Initialize request ID middleware.

    - Generates or accepts request ID for each request
    - Stores in Flask's g object for access during request
    - Adds to response headers
    """

    @app.before_request
    def set_request_id() -> None:
        """Set request ID from header or generate new one."""
        # Accept client-provided ID or generate new one
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = generate_request_id()
        g.request_id = request_id

    @app.after_request
    def add_request_id_header(response: Response) -> Response:
        """Add request ID to response headers."""
        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response


def get_request_id() -> Optional[str]:
    """Get current request ID, if available."""
    return getattr(g, "request_id", None)

