"""
Input data validation for One-Pull Baseline.

Validates that input data is suitable for baseline generation.
Checks for sensor issues, extreme errors, discontinuities, etc.
"""

import numpy as np
from typing import Tuple, Optional
import logging

from .models import (
    ValidationIssue,
    ValidationSeverity,
    InputValidationResult
)

logger = logging.getLogger(__name__)

# Thresholds
MIN_DATA_POINTS = 50
RECOMMENDED_DATA_POINTS = 100
MIN_MAP_COVERAGE = 0.40
RECOMMENDED_MAP_COVERAGE = 0.60
MIN_RPM_RANGE = 2000
AFR_REASONABLE_MIN = 10.0
AFR_REASONABLE_MAX = 18.0
MAX_REASONABLE_AFR_ERROR = 25.0
AFR_DISCONTINUITY_THRESHOLD = 2.0


def validate_input_data(
    rpm_data: np.ndarray,
    map_data: np.ndarray,
    afr_commanded: np.ndarray,
    afr_measured: np.ndarray,
    map_bins: np.ndarray,
    torque_data: Optional[np.ndarray] = None
) -> InputValidationResult:
    """
    Comprehensive validation of input data.

    Checks:
    - Sufficient data points
    - MAP coverage
    - RPM range
    - AFR sensor health
    - AFR value reasonableness
    - Extreme errors (bad base tune)
    - Discontinuities (VVT/cam switching)
    - Data consistency

    Returns:
        InputValidationResult with is_valid flag and list of issues
    """
    issues = []

    n_points = len(rpm_data)

    # === Data Quantity Checks ===

    if n_points < MIN_DATA_POINTS:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            code="INSUFFICIENT_DATA",
            message=f"Only {n_points} data points. Minimum {MIN_DATA_POINTS} required.",
            details={"count": n_points, "minimum": MIN_DATA_POINTS}
        ))
    elif n_points < RECOMMENDED_DATA_POINTS:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            code="LOW_DATA_COUNT",
            message=f"{n_points} data points. {RECOMMENDED_DATA_POINTS}+ recommended for best results.",
            details={"count": n_points, "recommended": RECOMMENDED_DATA_POINTS}
        ))

    # === MAP Coverage Checks ===

    map_range = map_bins[-1] - map_bins[0]
    data_map_min = np.min(map_data)
    data_map_max = np.max(map_data)
    data_map_range = data_map_max - data_map_min
    coverage = data_map_range / map_range

    if coverage < MIN_MAP_COVERAGE:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            code="INSUFFICIENT_MAP_COVERAGE",
            message=f"MAP coverage {coverage*100:.0f}% is below {MIN_MAP_COVERAGE*100:.0f}% minimum.",
            details={
                "coverage_pct": round(coverage * 100, 1),
                "minimum_pct": MIN_MAP_COVERAGE * 100,
                "map_range": [float(data_map_min), float(data_map_max)]
            }
        ))
    elif coverage < RECOMMENDED_MAP_COVERAGE:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            code="LOW_MAP_COVERAGE",
            message=f"MAP coverage {coverage*100:.0f}%. {RECOMMENDED_MAP_COVERAGE*100:.0f}%+ recommended.",
            details={
                "coverage_pct": round(coverage * 100, 1),
                "recommended_pct": RECOMMENDED_MAP_COVERAGE * 100
            }
        ))

    # === RPM Range Checks ===

    rpm_range = np.max(rpm_data) - np.min(rpm_data)
    if rpm_range < MIN_RPM_RANGE:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            code="NARROW_RPM_RANGE",
            message=f"RPM range is only {rpm_range:.0f}. Wider sweeps improve accuracy.",
            details={
                "rpm_range": float(rpm_range),
                "rpm_min": float(np.min(rpm_data)),
                "rpm_max": float(np.max(rpm_data))
            }
        ))

    # === AFR Sensor Health Checks ===

    afr_variation = np.max(afr_measured) - np.min(afr_measured)
    if afr_variation < 0.5:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            code="AFR_SENSOR_FAULT",
            message="AFR sensor shows almost no variation. Sensor may be faulty or disconnected.",
            details={"afr_variation": float(afr_variation)}
        ))
    elif afr_variation < 1.0:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            code="AFR_LOW_VARIATION",
            message="AFR sensor shows very little variation. Check sensor connection.",
            details={"afr_variation": float(afr_variation)}
        ))

    # === AFR Reasonableness Checks ===

    afr_out_of_range = np.sum(
        (afr_measured < AFR_REASONABLE_MIN) |
        (afr_measured > AFR_REASONABLE_MAX)
    )
    if afr_out_of_range > n_points * 0.1:  # >10% out of range
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            code="AFR_VALUES_SUSPECT",
            message=f"{afr_out_of_range} AFR readings outside normal range ({AFR_REASONABLE_MIN}-{AFR_REASONABLE_MAX}).",
            details={
                "out_of_range_count": int(afr_out_of_range),
                "afr_min": float(np.min(afr_measured)),
                "afr_max": float(np.max(afr_measured))
            }
        ))

    # === Extreme Error Checks (Bad Base Tune) ===

    afr_errors = (afr_commanded - afr_measured) / afr_measured * 100
    max_error = np.max(np.abs(afr_errors))

    if max_error > MAX_REASONABLE_AFR_ERROR:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            code="EXTREME_AFR_ERRORS",
            message=f"Base tune has {max_error:.1f}% AFR errors. Baseline predictions may be less reliable.",
            details={
                "max_error_pct": float(max_error),
                "threshold_pct": MAX_REASONABLE_AFR_ERROR
            }
        ))

    # === Discontinuity Checks (VVT/Cam Switching) ===

    # Sort by RPM and look for sudden AFR jumps
    rpm_sort_idx = np.argsort(rpm_data)
    afr_sorted = afr_measured[rpm_sort_idx]
    afr_gradient = np.abs(np.diff(afr_sorted))

    discontinuities = np.sum(afr_gradient > AFR_DISCONTINUITY_THRESHOLD)
    if discontinuities > 3:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            code="AFR_DISCONTINUITIES",
            message=f"Detected {discontinuities} sudden AFR changes. May indicate VVT/cam switching.",
            details={
                "discontinuity_count": int(discontinuities),
                "max_jump": float(np.max(afr_gradient))
            }
        ))

    # === Commanded AFR Consistency ===

    afr_cmd_variation = np.max(afr_commanded) - np.min(afr_commanded)
    if afr_cmd_variation > 3.0:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            code="VARIABLE_AFR_TARGET",
            message="Commanded AFR varies significantly. This is normal but noted.",
            details={"cmd_afr_range": float(afr_cmd_variation)}
        ))

    # === Determine Overall Validity ===

    has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)

    return InputValidationResult(
        is_valid=not has_errors,
        issues=issues
    )


def validate_throttle_range(
    map_data: np.ndarray,
    tps_data: Optional[np.ndarray] = None
) -> Tuple[bool, str]:
    """
    Validate that data represents a partial-throttle pull (50-70% range).

    Uses MAP data if TPS not available.
    """
    if tps_data is not None:
        avg_tps = np.mean(tps_data)
        max_tps = np.max(tps_data)

        if max_tps > 85:
            return False, "Data includes WOT (>85% throttle). Use standard tuning instead."
        if avg_tps < 30:
            return False, "Average throttle too low (<30%). Need more load for baseline."

        return True, f"Throttle range OK: avg {avg_tps:.0f}%, max {max_tps:.0f}%"

    # Infer from MAP if no TPS
    # Assume ~100 kPa is WOT for NA engines
    max_map = np.max(map_data)
    avg_map = np.mean(map_data)

    if max_map > 95:
        return False, "Data appears to include WOT (MAP > 95 kPa). Use standard tuning."

    return True, f"Partial throttle inferred from MAP: avg {avg_map:.0f} kPa, max {max_map:.0f} kPa"
