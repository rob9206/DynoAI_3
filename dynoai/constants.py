"""DynoAI Constants - Single source of truth for bin definitions and grid dimensions.

This module defines the standard RPM and kPa bins used throughout DynoAI for
VE table grids, coverage analysis, and correction calculations.

Usage:
    from dynoai.constants import RPM_BINS, KPA_BINS, validate_grid_dimensions
    
    # Use in grid operations
    grid = [[None] * len(KPA_BINS) for _ in range(len(RPM_BINS))]
    
    # Validate grid dimensions
    validate_grid_dimensions(grid)
"""

from typing import List, Optional, Sequence

# ============================================================================
# Standard Bin Definitions
# ============================================================================

# Standard RPM bins (11 bins: 1500-6500 by 500 RPM)
# Extended range to 6500 RPM for high-performance applications
RPM_BINS: List[int] = [1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]

# Standard kPa bins (5 bins: 35-95 by varying intervals)
# Represents manifold absolute pressure (MAP) sensor readings
# 35 kPa = idle/low load, 95 kPa = high load/boost
KPA_BINS: List[int] = [35, 50, 65, 80, 95]

# ============================================================================
# Derived Grid Dimensions
# ============================================================================

# Grid dimensions (rows × columns)
GRID_ROWS: int = len(RPM_BINS)  # 11 rows
GRID_COLS: int = len(KPA_BINS)   # 5 columns
GRID_CELLS: int = GRID_ROWS * GRID_COLS  # 55 total cells

# ============================================================================
# Performance Optimization - Bin Index Lookup Caches
# ============================================================================

# Pre-computed index lookup dictionaries for O(1) access
# These avoid repeated O(n) list.index() calls in hot loops
RPM_INDEX: dict[int, int] = {rpm: i for i, rpm in enumerate(RPM_BINS)}
KPA_INDEX: dict[int, int] = {kpa: i for i, kpa in enumerate(KPA_BINS)}

# ============================================================================
# Validation Functions
# ============================================================================

def validate_grid_dimensions(
    grid: Sequence[Sequence[Optional[float]]],
    expected_rows: Optional[int] = None,
    expected_cols: Optional[int] = None
) -> None:
    """Validate grid matches expected dimensions.
    
    Args:
        grid: 2D grid to validate (list of lists)
        expected_rows: Expected row count (default: GRID_ROWS)
        expected_cols: Expected column count (default: GRID_COLS)
        
    Raises:
        ValueError: If grid dimensions don't match expected values
        
    Example:
        >>> grid = [[1.0, 2.0, 3.0, 4.0, 5.0] for _ in range(11)]
        >>> validate_grid_dimensions(grid)  # OK
        >>> bad_grid = [[1.0, 2.0] for _ in range(5)]
        >>> validate_grid_dimensions(bad_grid)  # Raises ValueError
    """
    if expected_rows is None:
        expected_rows = GRID_ROWS
    if expected_cols is None:
        expected_cols = GRID_COLS
    
    actual_rows = len(grid)
    if actual_rows != expected_rows:
        raise ValueError(
            f"Grid row count mismatch: expected {expected_rows}, got {actual_rows}\n"
            f"Expected dimensions: {expected_rows}×{expected_cols} = {expected_rows * expected_cols} cells\n"
            f"Hint: Standard DynoAI grids are {GRID_ROWS}×{GRID_COLS} = {GRID_CELLS} cells"
        )
    
    for i, row in enumerate(grid):
        actual_cols = len(row)
        if actual_cols != expected_cols:
            raise ValueError(
                f"Grid column count mismatch in row {i} (RPM={RPM_BINS[i] if i < len(RPM_BINS) else '?'}): "
                f"expected {expected_cols}, got {actual_cols}\n"
                f"Expected dimensions: {expected_rows}×{expected_cols} = {expected_rows * expected_cols} cells"
            )


def get_rpm_index(rpm: int) -> Optional[int]:
    """Get the index of an RPM bin value.
    
    Args:
        rpm: RPM value to find
        
    Returns:
        Index in RPM_BINS, or None if not found
        
    Example:
        >>> get_rpm_index(3000)
        3
        >>> get_rpm_index(9999)
        None
    """
    try:
        return RPM_BINS.index(rpm)
    except ValueError:
        return None


def get_kpa_index(kpa: int) -> Optional[int]:
    """Get the index of a kPa bin value.
    
    Args:
        kpa: kPa value to find
        
    Returns:
        Index in KPA_BINS, or None if not found
        
    Example:
        >>> get_kpa_index(65)
        2
        >>> get_kpa_index(100)
        None
    """
    try:
        return KPA_BINS.index(kpa)
    except ValueError:
        return None


def nearest_rpm_bin(rpm: float) -> int:
    """Find the nearest RPM bin for a given value.
    
    Args:
        rpm: Measured RPM value
        
    Returns:
        Nearest RPM bin value
        
    Example:
        >>> nearest_rpm_bin(2780.5)
        3000
        >>> nearest_rpm_bin(1200)
        1500
    """
    return min(RPM_BINS, key=lambda x: abs(x - rpm))


def nearest_kpa_bin(kpa: float) -> int:
    """Find the nearest kPa bin for a given value.
    
    Args:
        kpa: Measured kPa value
        
    Returns:
        Nearest kPa bin value
        
    Example:
        >>> nearest_kpa_bin(72.3)
        65
        >>> nearest_kpa_bin(100)
        95
    """
    return min(KPA_BINS, key=lambda x: abs(x - kpa))


# ============================================================================
# Engine and Fuel Constants
# ============================================================================

# Stoichiometric air-fuel ratio for gasoline
STOICH_AFR_GASOLINE: float = 14.57

# Torque to horsepower conversion factor
# Formula: HP = (Torque × RPM) / 5252
# Inverse: Torque = (HP × 5252) / RPM
TORQUE_HP_CONVERSION: float = 5252.0

# Invalid AFR sentinel value used by some dyno software
# WinPEP sometimes outputs 5.1 to indicate missing/invalid AFR readings
INVALID_AFR_SENTINEL: float = 5.1

# Hot intake air temperature threshold (°F)
# Above this temperature, additional spark retard is applied for safety
HOT_IAT_THRESHOLD_F: float = 120.0

# Minimum required data points per grid cell for analysis
# Cells with fewer samples are marked as insufficient data (None)
MIN_CELL_HITS: int = 10

# ============================================================================
# Sensor Value Ranges (for validation)
# ============================================================================

# Valid AFR measurement range
# Below 9.0 = extremely rich (likely sensor error)
# Above 18.0 = extremely lean (likely sensor error)
AFR_RANGE_MIN: float = 9.0
AFR_RANGE_MAX: float = 18.0

# Valid lambda range
# 0.6 = very rich (race fuel mixtures)
# 1.3 = lean cruise conditions
LAMBDA_RANGE_MIN: float = 0.6
LAMBDA_RANGE_MAX: float = 1.3

# Valid intake air temperature range (°F)
# Below 30°F = extremely cold (unlikely in dyno conditions)
# Above 300°F = dangerously hot (immediate concern)
IAT_RANGE_MIN_F: float = 30.0
IAT_RANGE_MAX_F: float = 300.0

# ============================================================================
# Grid Type Aliases
# ============================================================================

# Type alias for immutable grids (read-only)
Grid = Sequence[Sequence[Optional[float]]]

# Type alias for mutable grids (computation)
GridList = List[List[Optional[float]]]


# ============================================================================
# Module Documentation
# ============================================================================

__all__ = [
    # Bin definitions
    "RPM_BINS",
    "KPA_BINS",
    # Grid dimensions
    "GRID_ROWS",
    "GRID_COLS",
    "GRID_CELLS",
    # Engine and fuel constants
    "STOICH_AFR_GASOLINE",
    "TORQUE_HP_CONVERSION",
    "INVALID_AFR_SENTINEL",
    "HOT_IAT_THRESHOLD_F",
    "MIN_CELL_HITS",
    # Sensor ranges
    "AFR_RANGE_MIN",
    "AFR_RANGE_MAX",
    "LAMBDA_RANGE_MIN",
    "LAMBDA_RANGE_MAX",
    "IAT_RANGE_MIN_F",
    "IAT_RANGE_MAX_F",
    # Validation
    "validate_grid_dimensions",
    # Utilities
    "get_rpm_index",
    "get_kpa_index",
    "nearest_rpm_bin",
    "nearest_kpa_bin",
    # Type aliases
    "Grid",
    "GridList",
]
