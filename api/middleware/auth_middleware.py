"""
Auth middleware for DynoAI Flask API.

Re-exports the JWT authentication decorator from the auth routes module
so other parts of the application can import it from a consistent location.
"""

from api.routes.auth import require_jwt  # noqa: F401

__all__ = ["require_jwt"]
