"""Tests ensuring version metadata stays in sync."""

from __future__ import annotations

import importlib.metadata as metadata

import pytest

import dynoai
from dynoai.version import __version__ as SOURCE_VERSION


def test_runtime_version_matches_source_file() -> None:
    """dynoai.__version__ should mirror the single source definition."""
    assert dynoai.__version__ == SOURCE_VERSION


def test_metadata_matches_runtime_version() -> None:
    """Installed package metadata should align with dynoai.__version__."""
    try:
        installed_version = metadata.version("dynoai")
    except metadata.PackageNotFoundError:
        pytest.skip("dynoai distribution not installed (run `pip install -e .`).")
    assert installed_version == dynoai.__version__








