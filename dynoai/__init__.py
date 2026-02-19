"""DynoAI Core Package - Motorcycle dyno tuning analysis system."""

from dynoai.version import __version__

__author__ = "DynoAI Team"

from dynoai.constants import (
    RPM_BINS,
    KPA_BINS,
    GRID_ROWS,
    GRID_COLS,
    GRID_CELLS,
    validate_grid_dimensions,
)

__all__ = [
    "__version__",
    "RPM_BINS",
    "KPA_BINS",
    "GRID_ROWS",
    "GRID_COLS",
    "GRID_CELLS",
    "validate_grid_dimensions",
]
