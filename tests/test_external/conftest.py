"""
Pytest configuration and fixtures for external scraper tests.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def mock_network_in_tests(monkeypatch):
    """
    Prevent accidental network calls in unit tests.

    Tests that need network access should explicitly mock the fetch function.
    """
    import external_scrapers.http_utils as http_utils

    def _blocked_fetch(*args, **kwargs):
        raise RuntimeError(
            "Network calls are blocked in tests. "
            "Use @patch('external_scrapers.http_utils.fetch') to mock."
        )

    # Only block fetch, not the module-level imports
    monkeypatch.setattr(http_utils, "fetch", _blocked_fetch)
