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
# CRITICAL: Disable rate limiting for tests
os.environ["RATE_LIMIT_ENABLED"] = "false"
# Pin BLAS/OpenMP threads for GP determinism (NumPy Cholesky, solve)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"


def pytest_configure(config):
    """Pytest hook called early in configuration."""
    # Ensure path is set for all pytest operations
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    # Register custom markers
    config.addinivalue_line("markers", "validation: heavy holdout/parity tests (deselect with -m 'not validation')")
