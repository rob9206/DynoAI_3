"""
Synthetic dyno data generation modules.

This package provides tools for generating synthetic dyno run data
from peak values (HP/TQ) or other metadata, producing WinPEP8-compatible
CSV output for testing and development.
"""

from __future__ import annotations

from typing import Iterable

from .winpep8_synthesizer import (
    EngineConfig,
    EngineFamily,
    PeakInfo,
    default_engine_config,
    generate_winpep8_like_run,
    save_winpep8_run,
)

__all__: Iterable[str] = [
    "EngineConfig",
    "EngineFamily",
    "PeakInfo",
    "default_engine_config",
    "generate_winpep8_like_run",
    "save_winpep8_run",
]
