"""
DynoAI AFR Targets - Centralized logic for target AFR lookup.

This module provides the source of truth for Air-Fuel Ratio (AFR) targets
based on engine load (MAP). It consolidates logic previously scattered
across scripts and services.
"""

from typing import Dict, Optional

# Legacy smooth targets retained for backwards compatibility.
SMOOTH_AFR_TARGETS: Dict[int, float] = {
    20: 14.6,  # Decel - prevent popping
    30: 14.6,  # Idle/Light Load
    40: 14.5,  # Light Cruise
    50: 14.2,  # Cruise
    60: 13.8,  # Heavy Cruise / Light Accel
    70: 13.2,  # Moderate Accel
    80: 12.8,  # Heavy Accel
    90: 12.5,  # WOT (Rich for power/cooling)
    100: 12.5,  # WOT
    105: 12.2,  # Boost/Extreme Load
}

# Real-world Delphi-style step profile observed in TC110 calibration:
# cruise, PE transition, and WOT enrichment as discrete bands.
TC110_AFR_TARGETS: Dict[int, float] = {
    10: 14.29,
    15: 14.29,
    20: 14.29,
    25: 14.29,
    30: 14.37,
    35: 14.37,
    40: 14.37,
    45: 14.37,
    50: 14.37,
    55: 14.37,
    60: 14.37,
    65: 14.37,
    70: 14.37,
    75: 14.39,
    85: 13.08,
    95: 12.88,
    105: 12.88,
}

# Profile registry used by callers that want engine-specific defaults.
AFR_TARGET_PROFILES: Dict[str, Dict[int, float]] = {
    "default": TC110_AFR_TARGETS,
    "tc_110": TC110_AFR_TARGETS,
    "smooth": SMOOTH_AFR_TARGETS,
}

# Default now follows the ECU-style step pattern.
DEFAULT_AFR_TARGETS: Dict[int, float] = AFR_TARGET_PROFILES["default"]


def get_afr_target_profile(profile: str = "default") -> Dict[int, float]:
    """Get a named AFR target profile, falling back to default."""
    return AFR_TARGET_PROFILES.get(profile, DEFAULT_AFR_TARGETS)


def get_target_afr_for_map(
    map_kpa: float,
    custom_targets: Optional[Dict[int, float]] = None
) -> float:
    """
    Get the target AFR for a given Manifold Absolute Pressure (MAP).

    Args:
        map_kpa: Measured MAP in kPa.
        custom_targets: Optional dictionary of MAP->AFR targets.
                        If None, uses DEFAULT_AFR_TARGETS.

    Returns:
        Target AFR (float).
    """
    targets = custom_targets or DEFAULT_AFR_TARGETS

    # Sort keys to ensure we find the nearest neighbor correctly
    sorted_map_keys = sorted(targets.keys())

    if not sorted_map_keys:
        return 14.6  # Fail-safe fallback (Stoich-ish)

    # Find nearest MAP bin (simple 1D nearest neighbor)
    nearest_map = min(sorted_map_keys, key=lambda k: abs(k - map_kpa))

    return targets[nearest_map]
