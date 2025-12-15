"""
DynoAI VE Math Module - Versioned VE Correction Calculations

MATH VERSION: 2.0.0

This module provides the core VE (Volumetric Efficiency) correction calculations
for DynoAI. It supports multiple math versions for backwards compatibility and
comparison purposes.

Math Versions:
- v1.0.0: Linear 7% per AFR point (legacy approximation)
- v2.0.0: Ratio model AFR_measured/AFR_target (physically accurate)

The v2.0.0 ratio model is derived from first principles:
    VE_correction = AFR_measured / AFR_target

This directly represents the fuel delivery error ratio and is mathematically
exact, unlike the v1.0.0 linear approximation which loses accuracy at large
AFR deviations.

Usage:
    from dynoai.core.ve_math import calculate_ve_correction, MathVersion
    
    # Default v2.0.0 (ratio model)
    correction = calculate_ve_correction(14.0, 13.0)
    
    # Explicit version selection
    correction = calculate_ve_correction(14.0, 13.0, version=MathVersion.V2_0_0)
    
    # Legacy v1.0.0 mode
    correction = calculate_ve_correction(14.0, 13.0, version=MathVersion.V1_0_0)

References:
    - docs/MATH_V2_SPECIFICATION.md
    - docs/DETERMINISTIC_MATH_SPECIFICATION.md
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple
import logging

# Import environmental corrections
from dynoai.core.environmental import (
    EnvironmentalCorrector,
    EnvironmentalConditions,
    EnvironmentalCorrectionResult,
)

__all__ = [
    "MathVersion",
    "MathConfig",
    "calculate_ve_correction",
    "calculate_ve_correction_batch",
    "calculate_ve_correction_with_environment",
    "get_default_config",
    "VEMathError",
    "AFR_MIN",
    "AFR_MAX",
    "EnvironmentalConditions",  # Re-export for convenience
]

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Valid AFR range for gasoline engines
AFR_MIN: float = 9.0   # Below this = extreme rich or sensor error
AFR_MAX: float = 20.0  # Above this = extreme lean or sensor error

# Stoichiometric AFR for gasoline (used for reference, not in calculation)
STOICH_AFR_GASOLINE: float = 14.7

# v1.0.0 linear model constant
V1_VE_PER_AFR_POINT: float = 0.07  # 7% per AFR point


# =============================================================================
# Enums and Configuration
# =============================================================================

class MathVersion(Enum):
    """
    VE calculation math version selector.
    
    V1_0_0: Legacy linear approximation (7% per AFR point)
        Formula: VE_correction = 1 + (AFR_error * 0.07)
        Where: AFR_error = AFR_measured - AFR_target
        
    V2_0_0: Ratio model (physically accurate)
        Formula: VE_correction = AFR_measured / AFR_target
        Derived from fuel mass balance equations
    """
    V1_0_0 = "1.0.0"
    V2_0_0 = "2.0.0"
    
    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class MathConfig:
    """
    Immutable configuration for VE math calculations.
    
    Attributes:
        version: Math version to use (default: V2_0_0)
        max_correction_pct: Maximum correction percentage (default: 15.0 for ±15%)
        afr_min: Minimum valid AFR value (default: 9.0)
        afr_max: Maximum valid AFR value (default: 20.0)
        clamp_enabled: Whether to apply safety clamping (default: True)
    """
    version: MathVersion = MathVersion.V2_0_0
    max_correction_pct: float = 15.0
    afr_min: float = AFR_MIN
    afr_max: float = AFR_MAX
    clamp_enabled: bool = True
    
    def __post_init__(self) -> None:
        if self.max_correction_pct <= 0:
            raise ValueError("max_correction_pct must be positive")
        if self.afr_min >= self.afr_max:
            raise ValueError("afr_min must be less than afr_max")
        if self.afr_min <= 0:
            raise ValueError("afr_min must be positive")


# Default configurations
_DEFAULT_CONFIG = MathConfig(version=MathVersion.V2_0_0)
_LEGACY_CONFIG = MathConfig(version=MathVersion.V1_0_0)


def get_default_config() -> MathConfig:
    """Get the default math configuration (v2.0.0)."""
    return _DEFAULT_CONFIG


def get_legacy_config() -> MathConfig:
    """Get the legacy math configuration (v1.0.0)."""
    return _LEGACY_CONFIG


# =============================================================================
# Exceptions
# =============================================================================

class VEMathError(Exception):
    """Base exception for VE math errors."""
    pass


class AFRValidationError(VEMathError):
    """Raised when AFR values are outside valid range."""
    pass


# =============================================================================
# Core Calculation Functions
# =============================================================================

def _validate_afr(
    afr: float,
    name: str,
    afr_min: float = AFR_MIN,
    afr_max: float = AFR_MAX,
) -> None:
    """
    Validate an AFR value is within acceptable range.
    
    Args:
        afr: AFR value to validate
        name: Name for error messages (e.g., "measured", "target")
        afr_min: Minimum valid AFR
        afr_max: Maximum valid AFR
        
    Raises:
        AFRValidationError: If AFR is outside valid range
    """
    if afr is None:
        raise AFRValidationError(f"AFR {name} is None")
    if not isinstance(afr, (int, float)):
        raise AFRValidationError(f"AFR {name} must be numeric, got {type(afr)}")
    if afr != afr:  # NaN check
        raise AFRValidationError(f"AFR {name} is NaN")
    if not (afr_min <= afr <= afr_max):
        raise AFRValidationError(
            f"AFR {name} ({afr:.2f}) outside valid range [{afr_min}, {afr_max}]"
        )


def _calculate_v1_correction(afr_measured: float, afr_target: float) -> float:
    """
    Calculate VE correction using v1.0.0 linear model.
    
    Formula: VE_correction = 1 + (AFR_error * 0.07)
    Where: AFR_error = AFR_measured - AFR_target
    
    This is the legacy "7% per AFR point" approximation.
    
    Args:
        afr_measured: Measured AFR from wideband sensor
        afr_target: Target/commanded AFR
        
    Returns:
        VE correction multiplier
    """
    afr_error = afr_measured - afr_target
    return 1.0 + (afr_error * V1_VE_PER_AFR_POINT)


def _calculate_v2_correction(afr_measured: float, afr_target: float) -> float:
    """
    Calculate VE correction using v2.0.0 ratio model.
    
    Formula: VE_correction = AFR_measured / AFR_target
    
    This is the physically accurate model derived from fuel mass balance.
    
    Args:
        afr_measured: Measured AFR from wideband sensor
        afr_target: Target/commanded AFR
        
    Returns:
        VE correction multiplier
    """
    return afr_measured / afr_target


def _clamp_correction(
    correction: float,
    max_correction_pct: float,
) -> Tuple[float, bool]:
    """
    Apply safety clamping to a VE correction value.
    
    Args:
        correction: Raw VE correction multiplier
        max_correction_pct: Maximum adjustment percentage (e.g., 15.0 for ±15%)
        
    Returns:
        Tuple of (clamped_correction, was_clamped)
    """
    min_val = 1.0 - (max_correction_pct / 100.0)
    max_val = 1.0 + (max_correction_pct / 100.0)
    
    if correction < min_val:
        return min_val, True
    elif correction > max_val:
        return max_val, True
    else:
        return correction, False


def calculate_ve_correction(
    afr_measured: float,
    afr_target: float,
    version: Optional[MathVersion] = None,
    config: Optional[MathConfig] = None,
    clamp: bool = True,
) -> float:
    """
    Calculate VE correction factor from AFR measurements.
    
    This is the primary VE calculation function for DynoAI. It supports
    multiple math versions for backwards compatibility.
    
    Math Versions:
        v1.0.0: VE_correction = 1 + (AFR_error * 0.07)  [legacy]
        v2.0.0: VE_correction = AFR_measured / AFR_target  [default]
    
    Interpretation:
        - correction > 1.0: Running lean, need MORE fuel (increase VE)
        - correction < 1.0: Running rich, need LESS fuel (decrease VE)
        - correction = 1.0: On target, no change needed
    
    Args:
        afr_measured: Measured AFR from wideband O2 sensor
        afr_target: Target/commanded AFR from tune
        version: Math version to use (overrides config if provided)
        config: Math configuration (uses default if not provided)
        clamp: Whether to apply safety clamping (default: True)
        
    Returns:
        VE correction multiplier (e.g., 1.077 means +7.7% fuel)
        
    Raises:
        AFRValidationError: If AFR values are invalid
        VEMathError: If calculation fails
        
    Examples:
        >>> calculate_ve_correction(14.0, 13.0)  # Lean
        1.0769230769230769
        
        >>> calculate_ve_correction(12.0, 13.0)  # Rich
        0.9230769230769231
        
        >>> calculate_ve_correction(13.0, 13.0)  # On target
        1.0
    """
    # Resolve configuration
    if config is None:
        config = _DEFAULT_CONFIG
    
    # Version override takes precedence
    math_version = version if version is not None else config.version
    
    # Validate inputs
    _validate_afr(afr_measured, "measured", config.afr_min, config.afr_max)
    _validate_afr(afr_target, "target", config.afr_min, config.afr_max)
    
    # Calculate based on version
    if math_version == MathVersion.V1_0_0:
        correction = _calculate_v1_correction(afr_measured, afr_target)
    elif math_version == MathVersion.V2_0_0:
        correction = _calculate_v2_correction(afr_measured, afr_target)
    else:
        raise VEMathError(f"Unknown math version: {math_version}")
    
    # Apply clamping if enabled
    if clamp and config.clamp_enabled:
        correction, was_clamped = _clamp_correction(
            correction, config.max_correction_pct
        )
        if was_clamped:
            logger.debug(
                "VE correction clamped: AFR %.2f/%.2f -> %.4f (clamped to ±%.1f%%)",
                afr_measured,
                afr_target,
                correction,
                config.max_correction_pct,
            )
    
    return correction


def calculate_ve_correction_batch(
    afr_measured_list: list,
    afr_target_list: list,
    version: Optional[MathVersion] = None,
    config: Optional[MathConfig] = None,
    clamp: bool = True,
    skip_invalid: bool = False,
) -> list:
    """
    Calculate VE corrections for multiple AFR measurements.
    
    Batch version of calculate_ve_correction() for efficiency when
    processing multiple data points.
    
    Args:
        afr_measured_list: List of measured AFR values
        afr_target_list: List of target AFR values (same length as measured)
        version: Math version to use
        config: Math configuration
        clamp: Whether to apply safety clamping
        skip_invalid: If True, return None for invalid entries instead of raising
        
    Returns:
        List of VE correction multipliers (or None for invalid entries if skip_invalid)
        
    Raises:
        ValueError: If input lists have different lengths
        AFRValidationError: If any AFR value is invalid (unless skip_invalid=True)
    """
    if len(afr_measured_list) != len(afr_target_list):
        raise ValueError(
            f"List length mismatch: measured={len(afr_measured_list)}, "
            f"target={len(afr_target_list)}"
        )
    
    results = []
    for measured, target in zip(afr_measured_list, afr_target_list):
        try:
            correction = calculate_ve_correction(
                measured, target, version=version, config=config, clamp=clamp
            )
            results.append(correction)
        except (AFRValidationError, VEMathError) as e:
            if skip_invalid:
                results.append(None)
            else:
                raise
    
    return results


# =============================================================================
# Utility Functions
# =============================================================================

def correction_to_percentage(correction: float) -> float:
    """
    Convert VE correction multiplier to percentage change.
    
    Args:
        correction: VE correction multiplier (e.g., 1.077)
        
    Returns:
        Percentage change (e.g., 7.7 for +7.7%)
        
    Examples:
        >>> correction_to_percentage(1.077)
        7.7
        >>> correction_to_percentage(0.923)
        -7.7
    """
    return (correction - 1.0) * 100.0


def percentage_to_correction(percentage: float) -> float:
    """
    Convert percentage change to VE correction multiplier.
    
    Args:
        percentage: Percentage change (e.g., 7.7 for +7.7%)
        
    Returns:
        VE correction multiplier (e.g., 1.077)
        
    Examples:
        >>> percentage_to_correction(7.7)
        1.077
        >>> percentage_to_correction(-7.7)
        0.923
    """
    return 1.0 + (percentage / 100.0)


def compare_versions(
    afr_measured: float,
    afr_target: float,
) -> dict:
    """
    Compare VE corrections from different math versions.
    
    Useful for analysis and migration validation.
    
    Args:
        afr_measured: Measured AFR
        afr_target: Target AFR
        
    Returns:
        Dictionary with version comparisons
        
    Examples:
        >>> compare_versions(14.0, 13.0)
        {
            'v1_0_0': 1.07,
            'v2_0_0': 1.0769...,
            'difference': 0.0069...,
            'difference_pct': 0.69...,
        }
    """
    v1 = calculate_ve_correction(
        afr_measured, afr_target, version=MathVersion.V1_0_0, clamp=False
    )
    v2 = calculate_ve_correction(
        afr_measured, afr_target, version=MathVersion.V2_0_0, clamp=False
    )
    
    diff = abs(v2 - v1)
    diff_pct = (diff / v2) * 100.0 if v2 != 0 else 0.0
    
    return {
        "afr_measured": afr_measured,
        "afr_target": afr_target,
        "v1_0_0": v1,
        "v2_0_0": v2,
        "v1_0_0_pct": correction_to_percentage(v1),
        "v2_0_0_pct": correction_to_percentage(v2),
        "difference": diff,
        "difference_pct": diff_pct,
    }


def get_version_info() -> dict:
    """
    Get information about the current math version configuration.
    
    Returns:
        Dictionary with version information
    """
    return {
        "default_version": str(_DEFAULT_CONFIG.version),
        "available_versions": [str(v) for v in MathVersion],
        "v1_formula": "VE_correction = 1 + (AFR_error * 0.07)",
        "v2_formula": "VE_correction = AFR_measured / AFR_target",
        "default_max_correction_pct": _DEFAULT_CONFIG.max_correction_pct,
        "afr_range": [AFR_MIN, AFR_MAX],
    }


# =============================================================================
# Environmental Correction Integration
# =============================================================================

def calculate_ve_correction_with_environment(
    afr_measured: float,
    afr_target: float,
    environmental_conditions: Optional[EnvironmentalConditions] = None,
    version: Optional[MathVersion] = None,
    config: Optional[MathConfig] = None,
    clamp: bool = True,
) -> Tuple[float, dict]:
    """
    Calculate VE correction with environmental compensation.
    
    This extends the standard VE correction to account for atmospheric
    conditions that affect air density and fuel requirements:
    - Barometric pressure / altitude
    - Ambient temperature
    - Humidity
    - Engine coolant temperature (ECT)
    
    The environmental correction is applied as a multiplier to the base
    VE correction:
        final_correction = base_correction * environmental_factor
    
    Args:
        afr_measured: Measured AFR from wideband O2 sensor
        afr_target: Target/commanded AFR from tune
        environmental_conditions: Current atmospheric conditions
            (if None, uses standard conditions = no environmental adjustment)
        version: Math version to use (overrides config if provided)
        config: Math configuration (uses default if not provided)
        clamp: Whether to apply safety clamping (default: True)
        
    Returns:
        Tuple of:
        - final_correction: VE correction with environmental adjustment
        - details: Dictionary with breakdown of corrections
        
    Examples:
        Standard conditions (no adjustment):
        >>> corr, details = calculate_ve_correction_with_environment(14.0, 13.0)
        >>> corr
        1.077
        
        High altitude (Denver, ~5000 ft):
        >>> conditions = EnvironmentalConditions(barometric_pressure_inhg=24.89)
        >>> corr, details = calculate_ve_correction_with_environment(
        ...     14.0, 13.0, environmental_conditions=conditions
        ... )
        >>> corr
        0.896  # Less fuel needed at altitude
        
    Note:
        The environmental correction affects how much fuel is ultimately
        needed, but the base VE correction is still calculated from the
        AFR error. For example:
        - At sea level, 1.0 AFR lean = +7.7% fuel
        - At 5000 ft, 1.0 AFR lean = +7.7% * 0.83 altitude factor = +6.4% fuel
    """
    # Calculate base VE correction
    base_correction = calculate_ve_correction(
        afr_measured=afr_measured,
        afr_target=afr_target,
        version=version,
        config=config,
        clamp=False,  # We'll clamp after environmental adjustment
    )
    
    # Calculate environmental correction
    if environmental_conditions is None:
        # Standard conditions = no adjustment
        env_result = EnvironmentalCorrectionResult(
            total_correction=1.0,
            pressure_correction=1.0,
            temperature_correction=1.0,
            humidity_correction=1.0,
            altitude_correction=1.0,
            ect_correction=1.0,
            standard_used=None,
            is_standard_day=True,
            details={},
        )
    else:
        corrector = EnvironmentalCorrector()
        env_result = corrector.calculate(environmental_conditions)
    
    # Combine corrections
    # The environmental factor adjusts the fuel requirement based on air density
    # For lean condition: base > 1.0 (need more fuel)
    # Environmental factor < 1.0 at altitude (less dense air needs less fuel)
    # Combined effect: the lean correction is partially offset by altitude
    final_correction = base_correction * env_result.total_correction
    
    # Apply clamping if enabled
    if clamp:
        resolved_config = config if config is not None else _DEFAULT_CONFIG
        if resolved_config.clamp_enabled:
            final_correction, was_clamped = _clamp_correction(
                final_correction, resolved_config.max_correction_pct
            )
    
    # Build details dictionary
    details = {
        "base_ve_correction": base_correction,
        "base_ve_correction_pct": correction_to_percentage(base_correction),
        "environmental_factor": env_result.total_correction,
        "environmental_factor_pct": (env_result.total_correction - 1.0) * 100,
        "final_correction": final_correction,
        "final_correction_pct": correction_to_percentage(final_correction),
        "is_standard_day": env_result.is_standard_day,
        "environmental_breakdown": {
            "pressure": env_result.pressure_correction,
            "temperature": env_result.temperature_correction,
            "humidity": env_result.humidity_correction,
            "ect": env_result.ect_correction,
        },
    }
    
    if environmental_conditions is not None:
        details["conditions"] = {
            "barometric_inhg": environmental_conditions.barometric_pressure_inhg,
            "altitude_ft": environmental_conditions.altitude_ft,
            "ambient_temp_f": environmental_conditions.ambient_temp_f,
            "humidity_pct": environmental_conditions.humidity_percent,
            "ect_f": environmental_conditions.ect_f,
        }
    
    return final_correction, details


def apply_environmental_correction(
    ve_correction: float,
    environmental_conditions: EnvironmentalConditions,
) -> float:
    """
    Apply environmental correction to an existing VE correction.
    
    Use this when you have already calculated a VE correction and want
    to adjust it for current environmental conditions.
    
    Args:
        ve_correction: Pre-calculated VE correction multiplier
        environmental_conditions: Current atmospheric conditions
        
    Returns:
        Environmentally-adjusted VE correction
        
    Example:
        >>> base_corr = calculate_ve_correction(14.0, 13.0)
        >>> conditions = EnvironmentalConditions(
        ...     barometric_pressure_inhg=24.89,  # 5000 ft
        ...     ambient_temp_f=90.0,
        ... )
        >>> adjusted = apply_environmental_correction(base_corr, conditions)
    """
    corrector = EnvironmentalCorrector()
    env_result = corrector.calculate(environmental_conditions)
    return ve_correction * env_result.total_correction

