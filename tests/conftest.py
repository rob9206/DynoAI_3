"""
Root conftest.py for DynoAI tests.

Ensures the project root is in sys.path for all tests.
"""

import os
import sys
from pathlib import Path

import pytest

# Add project root to path for imports IMMEDIATELY
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Set common test environment variables
os.environ["DYNOAI_DEBUG"] = "false"
os.environ["JETSTREAM_STUB_MODE"] = "true"
os.environ["JETSTREAM_ENABLED"] = "false"


def pytest_configure(config):
    """Pytest hook called early in configuration."""
    # Ensure path is set for all pytest operations
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
