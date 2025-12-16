"""Centralized DynoAI version information."""

from __future__ import annotations

__all__ = ["__version__", "get_version"]

# Single authoritative version string for the entire project.
__version__ = "1.2.1"


def get_version() -> str:
    """Return the current DynoAI version."""
    return __version__

