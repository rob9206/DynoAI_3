"""DynoAI Core Package - Motorcycle dyno tuning analysis system."""

__version__ = "1.2.1"
__author__ = "DynoAI Team"

from dynoai.constants import (
    GRID_CELLS,
    GRID_COLS,
    GRID_ROWS,
    KPA_BINS,
    RPM_BINS,
    validate_grid_dimensions,
)

__all__ = [
    "RPM_BINS",
    "KPA_BINS",
    "GRID_ROWS",
    "GRID_COLS",
    "GRID_CELLS",
    "validate_grid_dimensions",
]
