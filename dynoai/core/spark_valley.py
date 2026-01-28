"""
DynoAI NextGen Spark Valley Detection

Detects and describes the WOT spark timing valley behavior for front and rear cylinders.
The spark valley is a region in the mid-RPM range at high MAP where spark timing dips
due to knock limiting before recovering at higher RPM.

The valley detection algorithm:
1. Extracts high-MAP band (average of top 2-3 MAP bins)
2. Smooths the curve using moving average
3. Finds a midrange minimum bracketed by higher timing on both sides
4. Calculates valley depth, center, and bounds
5. Assigns confidence based on data coverage and pattern strength

Usage:
    from dynoai.core.spark_valley import detect_spark_valley, SparkValleyFinding
    from dynoai.core.surface_builder import Surface2D

    findings = detect_spark_valley(spark_surface, high_map_min_kpa=80.0)
    for finding in findings:
        print(f"{finding.cylinder}: Valley at {finding.rpm_center} RPM, depth {finding.depth_deg}°")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from dynoai.core.surface_builder import Surface2D

__all__ = [
    "SparkValleyFinding",
    "detect_spark_valley",
    "detect_valleys_multi_cylinder",
]

# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SparkValleyFinding:
    """
    Description of a detected spark timing valley.

    The valley represents knock-limited timing in the torque peak RPM band
    at high MAP, where cylinder pressure is highest.
    """

    cylinder: str  # "front", "rear", or "global"
    rpm_center: float  # RPM at valley minimum
    rpm_band: Tuple[float, float]  # (low_rpm, high_rpm) bounds
    depth_deg: float  # Peak-to-valley depth in degrees
    valley_min_deg: float  # Timing at valley minimum
    pre_valley_deg: float  # Timing before valley (at lower RPM)
    post_valley_deg: float  # Timing after valley (at higher RPM)
    map_band_used: float  # Average MAP value used for analysis
    confidence: float  # 0.0 to 1.0
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Serialize to JSON-compatible dict."""
        return {
            "cylinder": self.cylinder,
            "rpm_center": self.rpm_center,
            "rpm_band": list(self.rpm_band),
            "depth_deg": round(self.depth_deg, 2),
            "valley_min_deg": round(self.valley_min_deg, 2),
            "pre_valley_deg": round(self.pre_valley_deg, 2),
            "post_valley_deg": round(self.post_valley_deg, 2),
            "map_band_used": round(self.map_band_used, 1),
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
        }


# =============================================================================
# Core Detection Functions
# =============================================================================


def _smooth_curve(
    values: List[Optional[float]],
    window: int = 3,
) -> List[Optional[float]]:
    """
    Apply simple moving average smoothing to a curve.

    Handles None values by interpolating or carrying forward.
    """
    n = len(values)
    if n == 0:
        return []

    # Replace None with interpolated values where possible
    filled = list(values)
    for i in range(n):
        if filled[i] is None:
            # Look for nearest non-None values
            left_val = None
            right_val = None
            for j in range(i - 1, -1, -1):
                if filled[j] is not None:
                    left_val = filled[j]
                    break
            for j in range(i + 1, n):
                if filled[j] is not None:
                    right_val = filled[j]
                    break

            if left_val is not None and right_val is not None:
                filled[i] = (left_val + right_val) / 2
            elif left_val is not None:
                filled[i] = left_val
            elif right_val is not None:
                filled[i] = right_val

    # Apply moving average
    smoothed: List[Optional[float]] = []
    half_window = window // 2

    for i in range(n):
        start = max(0, i - half_window)
        end = min(n, i + half_window + 1)
        window_vals = [
            filled[j] for j in range(start, end) if filled[j] is not None
        ]

        if window_vals:
            smoothed.append(sum(window_vals) / len(window_vals))
        else:
            smoothed.append(None)

    return smoothed


def _find_valley(
    rpm_bins: List[float],
    values: List[Optional[float]],
    min_depth_deg: float = 2.0,
) -> Optional[Tuple[int, float, float, float]]:
    """
    Find a valley (local minimum) in the timing curve.

    A valley is defined as a minimum that is:
    - At least min_depth_deg below adjacent peaks on both sides
    - In the midrange of RPM (not at the edges)

    Args:
        rpm_bins: RPM axis values
        values: Smoothed timing values
        min_depth_deg: Minimum depth to be considered a valley

    Returns:
        Tuple of (valley_idx, valley_value, pre_peak, post_peak) or None
    """
    n = len(values)
    if n < 5:  # Need at least 5 points for meaningful valley detection
        return None

    # Find valid (non-None) values
    valid_indices = [i for i in range(n) if values[i] is not None]
    if len(valid_indices) < 5:
        return None

    # Search for local minimum in the middle region
    # Exclude first and last 20% of the range
    start_idx = max(1, int(n * 0.2))
    end_idx = min(n - 1, int(n * 0.8))

    best_valley = None
    best_depth = 0.0

    for i in range(start_idx, end_idx):
        if values[i] is None:
            continue

        # Find the maximum value before this point
        pre_max = None
        pre_max_idx = None
        for j in range(i - 1, -1, -1):
            if values[j] is not None:
                if pre_max is None or values[j] > pre_max:
                    pre_max = values[j]
                    pre_max_idx = j

        # Find the maximum value after this point
        post_max = None
        post_max_idx = None
        for j in range(i + 1, n):
            if values[j] is not None:
                if post_max is None or values[j] > post_max:
                    post_max = values[j]
                    post_max_idx = j

        if pre_max is None or post_max is None:
            continue

        # Check if this is a valley (minimum with higher values on both sides)
        valley_val = values[i]
        pre_drop = pre_max - valley_val
        post_rise = post_max - valley_val

        # Valley must be below both sides by at least min_depth_deg
        if pre_drop >= min_depth_deg and post_rise >= min_depth_deg:
            total_depth = pre_drop + post_rise
            if total_depth > best_depth:
                best_depth = total_depth
                best_valley = (i, valley_val, pre_max, post_max)

    return best_valley


def detect_spark_valley(
    surface: Surface2D,
    high_map_min_kpa: float = 80.0,
    cylinder: str = "global",
    smoothing_window: int = 3,
    min_depth_deg: float = 2.0,
) -> List[SparkValleyFinding]:
    """
    Detect spark timing valley from a spark surface.

    The detection algorithm:
    1. Extract high-MAP slice (average of bins >= high_map_min_kpa)
    2. Smooth the curve
    3. Find local minimum bracketed by higher values
    4. Calculate valley metrics and confidence

    Args:
        surface: Spark timing Surface2D
        high_map_min_kpa: Minimum MAP to include in high-load band
        cylinder: Cylinder identifier for the finding
        smoothing_window: Moving average window size
        min_depth_deg: Minimum depth to detect valley

    Returns:
        List of SparkValleyFinding (usually 0 or 1)
    """
    findings: List[SparkValleyFinding] = []
    evidence: List[str] = []

    # Get RPM bins
    rpm_bins = surface.rpm_axis.bins
    map_bins = surface.map_axis.bins

    # Find high-MAP bins
    high_map_indices = [
        i for i, m in enumerate(map_bins) if m >= high_map_min_kpa
    ]

    if not high_map_indices:
        # No high-MAP data, try using top 2 bins
        high_map_indices = list(range(max(0,
                                          len(map_bins) - 2), len(map_bins)))
        evidence.append(
            f"Using top {len(high_map_indices)} MAP bins (no bins >= {high_map_min_kpa} kPa)"
        )

    if not high_map_indices:
        return []

    # Calculate average MAP value used
    avg_map = sum(map_bins[i]
                  for i in high_map_indices) / len(high_map_indices)

    # Extract high-MAP slice (average across high MAP bins for each RPM)
    raw_values: List[Optional[float]] = []
    hit_counts: List[int] = []

    for rpm_idx in range(len(rpm_bins)):
        cell_values = []
        total_hits = 0
        for map_idx in high_map_indices:
            val = surface.values[rpm_idx][map_idx]
            hits = surface.hit_count[rpm_idx][map_idx]
            if val is not None:
                cell_values.append(val)
            total_hits += hits

        if cell_values:
            raw_values.append(sum(cell_values) / len(cell_values))
        else:
            raw_values.append(None)
        hit_counts.append(total_hits)

    evidence.append(
        f"Analyzed {len(high_map_indices)} MAP bins (avg {avg_map:.0f} kPa)")

    # Count valid data points
    valid_count = sum(1 for v in raw_values if v is not None)
    total_count = len(raw_values)
    coverage_pct = valid_count / total_count * 100 if total_count > 0 else 0

    if valid_count < 5:
        evidence.append(
            f"Insufficient data: only {valid_count} valid RPM points")
        return []

    evidence.append(
        f"Data coverage: {valid_count}/{total_count} RPM bins ({coverage_pct:.0f}%)"
    )

    # Smooth the curve
    smoothed = _smooth_curve(raw_values, window=smoothing_window)

    # Find valley
    valley_result = _find_valley(rpm_bins, smoothed, min_depth_deg)

    if valley_result is None:
        evidence.append(
            f"No valley detected (min depth threshold: {min_depth_deg}°)")
        return []

    valley_idx, valley_val, pre_peak, post_peak = valley_result

    # Calculate valley metrics
    valley_rpm = rpm_bins[valley_idx]
    depth = ((pre_peak - valley_val) + (post_peak - valley_val)) / 2

    # Find RPM band (where timing is within 50% of depth from minimum)
    threshold = valley_val + depth * 0.5
    band_start_idx = valley_idx
    band_end_idx = valley_idx

    for i in range(valley_idx - 1, -1, -1):
        if smoothed[i] is not None and smoothed[i] <= threshold:
            band_start_idx = i
        else:
            break

    for i in range(valley_idx + 1, len(smoothed)):
        if smoothed[i] is not None and smoothed[i] <= threshold:
            band_end_idx = i
        else:
            break

    rpm_band = (rpm_bins[band_start_idx], rpm_bins[band_end_idx])

    # Calculate confidence
    confidence = _calculate_valley_confidence(
        coverage_pct=coverage_pct,
        depth=depth,
        hit_counts=hit_counts,
        valley_idx=valley_idx,
    )

    evidence.append(f"Valley center: {valley_rpm} RPM")
    evidence.append(f"Valley depth: {depth:.1f}°")
    evidence.append(f"Valley band: {rpm_band[0]}-{rpm_band[1]} RPM")
    evidence.append(
        f"Pre-valley timing: {pre_peak:.1f}° | Post-valley: {post_peak:.1f}°")

    finding = SparkValleyFinding(
        cylinder=cylinder,
        rpm_center=valley_rpm,
        rpm_band=rpm_band,
        depth_deg=depth,
        valley_min_deg=valley_val,
        pre_valley_deg=pre_peak,
        post_valley_deg=post_peak,
        map_band_used=avg_map,
        confidence=confidence,
        evidence=evidence,
    )

    findings.append(finding)
    return findings


def _calculate_valley_confidence(
    coverage_pct: float,
    depth: float,
    hit_counts: List[int],
    valley_idx: int,
) -> float:
    """
    Calculate confidence score for a valley finding.

    Factors:
    - Data coverage (more = higher confidence)
    - Valley depth (deeper = clearer pattern)
    - Hit count around valley (more samples = more reliable)
    """
    confidence = 0.0

    # Coverage factor (0-0.4)
    if coverage_pct >= 80:
        confidence += 0.4
    elif coverage_pct >= 60:
        confidence += 0.3
    elif coverage_pct >= 40:
        confidence += 0.2
    else:
        confidence += 0.1

    # Depth factor (0-0.3)
    if depth >= 6.0:
        confidence += 0.3
    elif depth >= 4.0:
        confidence += 0.25
    elif depth >= 2.0:
        confidence += 0.15
    else:
        confidence += 0.05

    # Hit count factor around valley (0-0.3)
    if hit_counts:
        valley_hits = hit_counts[valley_idx] if valley_idx < len(
            hit_counts) else 0
        # Check neighboring bins too
        neighbor_hits = 0
        if valley_idx > 0:
            neighbor_hits += hit_counts[valley_idx - 1]
        if valley_idx < len(hit_counts) - 1:
            neighbor_hits += hit_counts[valley_idx + 1]

        total_valley_hits = valley_hits + neighbor_hits
        if total_valley_hits >= 30:
            confidence += 0.3
        elif total_valley_hits >= 15:
            confidence += 0.2
        elif total_valley_hits >= 5:
            confidence += 0.1

    return min(1.0, confidence)


def detect_valleys_multi_cylinder(
    surfaces: Dict[str, Surface2D],
    high_map_min_kpa: float = 80.0,
) -> List[SparkValleyFinding]:
    """
    Detect spark valleys from multiple cylinder surfaces.

    Looks for surfaces named "spark_front", "spark_rear", or "spark_global"
    and runs valley detection on each.

    Args:
        surfaces: Dict of surface_id -> Surface2D
        high_map_min_kpa: Minimum MAP for high-load band

    Returns:
        List of SparkValleyFinding for all cylinders
    """
    findings: List[SparkValleyFinding] = []

    # Check for per-cylinder surfaces
    if "spark_front" in surfaces:
        findings.extend(
            detect_spark_valley(
                surfaces["spark_front"],
                high_map_min_kpa=high_map_min_kpa,
                cylinder="front",
            ))

    if "spark_rear" in surfaces:
        findings.extend(
            detect_spark_valley(
                surfaces["spark_rear"],
                high_map_min_kpa=high_map_min_kpa,
                cylinder="rear",
            ))

    # Fall back to global surface if no per-cylinder
    if not findings and "spark_global" in surfaces:
        findings.extend(
            detect_spark_valley(
                surfaces["spark_global"],
                high_map_min_kpa=high_map_min_kpa,
                cylinder="global",
            ))

    return findings


def compare_cylinder_valleys(
        findings: List[SparkValleyFinding], ) -> Optional[Dict]:
    """
    Compare front vs rear cylinder valley findings.

    Identifies asymmetries that may indicate cylinder-specific issues
    like thermal asymmetry or sensor differences.

    Args:
        findings: List of SparkValleyFinding

    Returns:
        Dict with comparison metrics, or None if insufficient data
    """
    front = next((f for f in findings if f.cylinder == "front"), None)
    rear = next((f for f in findings if f.cylinder == "rear"), None)

    if front is None or rear is None:
        return None

    rpm_diff = rear.rpm_center - front.rpm_center
    depth_diff = rear.depth_deg - front.depth_deg
    min_timing_diff = rear.valley_min_deg - front.valley_min_deg

    comparison = {
        "front_rpm_center": front.rpm_center,
        "rear_rpm_center": rear.rpm_center,
        "rpm_center_diff": rpm_diff,
        "front_depth_deg": front.depth_deg,
        "rear_depth_deg": rear.depth_deg,
        "depth_diff": depth_diff,
        "front_valley_min": front.valley_min_deg,
        "rear_valley_min": rear.valley_min_deg,
        "valley_min_diff": min_timing_diff,
    }

    # Add observations
    observations = []

    if abs(depth_diff) >= 2.0:
        deeper_cyl = "rear" if depth_diff > 0 else "front"
        observations.append(
            f"{deeper_cyl} cylinder valley is {abs(depth_diff):.1f}° deeper")

    if abs(rpm_diff) >= 500:
        earlier_cyl = "front" if rpm_diff > 0 else "rear"
        observations.append(
            f"{earlier_cyl} cylinder valley occurs at lower RPM")

    if abs(min_timing_diff) >= 3.0:
        more_retarded = "rear" if min_timing_diff < 0 else "front"
        observations.append(
            f"{more_retarded} runs {abs(min_timing_diff):.1f}° more retarded at valley"
        )

    comparison["observations"] = observations

    return comparison
