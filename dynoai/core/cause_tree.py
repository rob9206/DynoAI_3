"""
DynoAI NextGen Cause Tree - ECU-Coupling-Aware Diagnosis

Deterministic hypothesis generation reflecting the ECU mental model:
- VE is a correction layer; closed-loop can mask VE error
- Spark is base + modifiers; knock always has authority
- VE and spark are coupled via combustion efficiency and knock

Categories:
- transient: Tip-in/tip-out fueling issues (wall wetting, enrichment lag)
- knock_limit: Knock-limited timing, cylinder asymmetry (often rear-dominant)
- temp_trim: Heat soak, thermal compensation affecting spark/fuel
- fuel_model: VE errors, AFR deviations
- data_quality: Insufficient data for confident analysis

IMPORTANT: This module outputs diagnosis + recommended test/logging checks only.
It does NOT output calibration changes like "change table X by Y".

Usage:
    from dynoai.core.cause_tree import build_cause_tree, CauseTreeResult

    result = build_cause_tree(
        mode_summary=mode_result.summary_counts,
        surfaces=surfaces,
        spark_valley=valley_findings,
    )

    for h in result.hypotheses:
        print(f"[{h.confidence:.0%}] {h.title}")
        for e in h.evidence:
            print(f"  - {e}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dynoai.core.spark_valley import SparkValleyFinding
from dynoai.core.surface_builder import Surface2D

__all__ = [
    "Hypothesis",
    "CauseTreeResult",
    "build_cause_tree",
    "HypothesisCategory",
]

# =============================================================================
# Constants
# =============================================================================


class HypothesisCategory:
    """Category constants for hypotheses."""

    TRANSIENT = "transient"
    LOAD_SIGNAL = "load_signal"
    KNOCK_LIMIT = "knock_limit"
    TEMP_TRIM = "temp_trim"
    FUEL_MODEL = "fuel_model"
    DATA_QUALITY = "data_quality"


# =============================================================================
# ECU-Coupling-Aware Thresholds (Deterministic)
# =============================================================================

# Transient hypothesis thresholds
TRANSIENT_TIP_IN_MIN_SAMPLES = 30  # Minimum tip-in samples to analyze
TRANSIENT_AFR_LEAN_THRESHOLD = 0.4  # AFR error > this is "lean excursion"
TRANSIENT_AFR_RICH_THRESHOLD = -0.4  # AFR error < this is "rich excursion"
TRANSIENT_AFR_VARIANCE_HIGH = 0.6  # High variance threshold

# Knock-limit hypothesis thresholds
KNOCK_VALLEY_MIN_DEPTH = 3.0  # Minimum valley depth to consider knock-limited
KNOCK_VALLEY_SIGNIFICANT_DEPTH = 5.0  # Significant valley depth
KNOCK_RATE_CORRELATION_THRESHOLD = 0.5  # Knock rate threshold for correlation
KNOCK_CYLINDER_ASYMMETRY_THRESHOLD = 2.0  # Degrees difference for asymmetry

# Temperature hypothesis thresholds
TEMP_SPARK_REDUCTION_THRESHOLD = 2.0  # Degrees of spark reduction
TEMP_HEAT_SOAK_MIN_SAMPLES = 20  # Minimum heat soak samples

# High MAP band definition (for knock analysis)
HIGH_MAP_THRESHOLD = 80  # kPa - high load threshold
MID_RPM_LOW = 2500  # RPM - midrange low
MID_RPM_HIGH = 5000  # RPM - midrange high

# =============================================================================
# Helper Functions
# =============================================================================


def _get_high_map_slice_stats(surface: Surface2D) -> Dict[str, Any]:
    """
    Extract statistics from the high-MAP band of a surface.

    Returns dict with: values, mean, min, max, rpm_at_min, rpm_at_max
    """
    result = {
        "values": [],
        "mean": None,
        "min": None,
        "max": None,
        "rpm_at_min": None,
        "rpm_at_max": None,
        "valid_cells": 0,
    }

    map_bins = surface.map_axis.bins
    rpm_bins = surface.rpm_axis.bins

    # Find high-MAP bin indices (>= HIGH_MAP_THRESHOLD)
    high_map_indices = [
        i for i, m in enumerate(map_bins) if m >= HIGH_MAP_THRESHOLD
    ]

    if not high_map_indices:
        return result

    # Extract values in high-MAP band
    values_with_rpm = []
    for rpm_idx, rpm in enumerate(rpm_bins):
        cell_values = []
        for map_idx in high_map_indices:
            val = surface.values[rpm_idx][map_idx]
            if val is not None:
                cell_values.append(val)

        if cell_values:
            avg_val = sum(cell_values) / len(cell_values)
            values_with_rpm.append((rpm, avg_val))
            result["values"].append(avg_val)
            result["valid_cells"] += len(cell_values)

    if result["values"]:
        result["mean"] = sum(result["values"]) / len(result["values"])

        # Find min/max with RPM
        if values_with_rpm:
            min_item = min(values_with_rpm, key=lambda x: x[1])
            max_item = max(values_with_rpm, key=lambda x: x[1])
            result["min"] = min_item[1]
            result["max"] = max_item[1]
            result["rpm_at_min"] = min_item[0]
            result["rpm_at_max"] = max_item[0]

    return result


def _get_midrange_rpm_stats(surface: Surface2D,
                            rpm_low: int = MID_RPM_LOW,
                            rpm_high: int = MID_RPM_HIGH) -> Dict[str, Any]:
    """
    Extract statistics from the midrange RPM band at high MAP.
    """
    result = {
        "values": [],
        "mean": None,
        "min": None,
        "max": None,
        "rpm_at_min": None,
        "valid_cells": 0,
    }

    map_bins = surface.map_axis.bins
    rpm_bins = surface.rpm_axis.bins

    # Find indices
    high_map_indices = [
        i for i, m in enumerate(map_bins) if m >= HIGH_MAP_THRESHOLD
    ]
    mid_rpm_indices = [
        i for i, r in enumerate(rpm_bins) if rpm_low <= r <= rpm_high
    ]

    if not high_map_indices or not mid_rpm_indices:
        return result

    values_with_rpm = []
    for rpm_idx in mid_rpm_indices:
        rpm = rpm_bins[rpm_idx]
        cell_values = []
        for map_idx in high_map_indices:
            val = surface.values[rpm_idx][map_idx]
            if val is not None:
                cell_values.append(val)

        if cell_values:
            avg_val = sum(cell_values) / len(cell_values)
            values_with_rpm.append((rpm, avg_val))
            result["values"].append(avg_val)
            result["valid_cells"] += len(cell_values)

    if result["values"]:
        result["mean"] = sum(result["values"]) / len(result["values"])
        if values_with_rpm:
            min_item = min(values_with_rpm, key=lambda x: x[1])
            max_item = max(values_with_rpm, key=lambda x: x[1])
            result["min"] = min_item[1]
            result["max"] = max_item[1]
            result["rpm_at_min"] = min_item[0]

    return result


def _check_knock_correlation_with_valley(
    knock_surface: Optional[Surface2D],
    valley: SparkValleyFinding,
) -> Dict[str, Any]:
    """
    Check if knock activity correlates with a spark valley location.

    Returns dict with: has_correlation, knock_in_band, knock_peak_rpm
    """
    result = {
        "has_correlation": False,
        "knock_in_band": 0.0,
        "knock_peak_rpm": None,
        "evidence": [],
    }

    if knock_surface is None:
        result["evidence"].append(
            "No knock data available - cannot confirm knock correlation")
        return result

    rpm_bins = knock_surface.rpm_axis.bins
    map_bins = knock_surface.map_axis.bins

    # Find RPM indices in valley band
    valley_rpm_low, valley_rpm_high = valley.rpm_band
    valley_rpm_indices = [
        i for i, r in enumerate(rpm_bins)
        if valley_rpm_low <= r <= valley_rpm_high
    ]
    high_map_indices = [
        i for i, m in enumerate(map_bins) if m >= HIGH_MAP_THRESHOLD
    ]

    if not valley_rpm_indices or not high_map_indices:
        return result

    # Calculate knock in valley band vs outside
    knock_in_band = []
    knock_outside_band = []
    knock_with_rpm = []

    for rpm_idx, rpm in enumerate(rpm_bins):
        for map_idx in high_map_indices:
            val = knock_surface.values[rpm_idx][map_idx]
            if val is not None and val > 0:
                knock_with_rpm.append((rpm, val))
                if rpm_idx in valley_rpm_indices:
                    knock_in_band.append(val)
                else:
                    knock_outside_band.append(val)

    if knock_in_band:
        result["knock_in_band"] = sum(knock_in_band) / len(knock_in_band)

        # Find peak knock RPM
        if knock_with_rpm:
            peak = max(knock_with_rpm, key=lambda x: x[1])
            result["knock_peak_rpm"] = peak[0]

        # Check if knock is higher in valley band
        avg_outside = (sum(knock_outside_band) /
                       len(knock_outside_band) if knock_outside_band else 0)
        if result["knock_in_band"] > avg_outside * 1.2:
            result["has_correlation"] = True
            result["evidence"].append(
                f"Knock activity is {result['knock_in_band']:.2f} in valley band vs {avg_outside:.2f} outside"
            )

        if (result["knock_peak_rpm"] and
                valley_rpm_low <= result["knock_peak_rpm"] <= valley_rpm_high):
            result["has_correlation"] = True
            result["evidence"].append(
                f"Peak knock at {result['knock_peak_rpm']} RPM falls within valley band"
            )

    return result


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Hypothesis:
    """
    A diagnostic hypothesis with confidence and evidence.

    Attributes:
        hypothesis_id: Unique identifier
        title: Short human-readable title
        confidence: Confidence score 0.0 to 1.0
        category: One of HypothesisCategory values
        evidence: List of evidence strings supporting this hypothesis
        distinguishing_checks: Actions to confirm or eliminate this hypothesis
    """

    hypothesis_id: str
    title: str
    confidence: float
    category: str
    evidence: List[str] = field(default_factory=list)
    distinguishing_checks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Serialize to JSON-compatible dict."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "title": self.title,
            "confidence": round(self.confidence, 2),
            "category": self.category,
            "evidence": self.evidence,
            "distinguishing_checks": self.distinguishing_checks,
        }


@dataclass
class CauseTreeResult:
    """
    Result of cause tree analysis.

    Contains ranked hypotheses and a summary string.
    """

    hypotheses: List[Hypothesis]
    summary: str
    analysis_notes: List[str] = field(default_factory=list)

    def get_top_hypothesis(self) -> Optional[Hypothesis]:
        """Get the highest-confidence hypothesis."""
        if not self.hypotheses:
            return None
        return max(self.hypotheses, key=lambda h: h.confidence)

    def get_by_category(self, category: str) -> List[Hypothesis]:
        """Get hypotheses in a specific category."""
        return [h for h in self.hypotheses if h.category == category]

    def to_dict(self) -> Dict:
        """Serialize to JSON-compatible dict."""
        return {
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "summary": self.summary,
            "analysis_notes": self.analysis_notes,
        }


# =============================================================================
# Hypothesis Generators
# =============================================================================


def _check_transient_issues(
    mode_summary: Dict[str, int],
    surfaces: Dict[str, Surface2D],
    has_knock: bool = False,
) -> List[Hypothesis]:
    """
    ECU-Coupling-Aware Transient Hypothesis (Rule A):

    Tip-in hesitation likely transient fuel issue.

    Trigger: TIP_IN mode has sustained AFR error lean excursion and/or high variance.

    ECU Mental Model Context:
    - VE is a correction layer; transient enrichment compensates for wall wetting
    - Closed-loop can mask VE error at steady state but not during fast transients
    - If knock spikes coincide with lean tip-in, combustion efficiency is compromised
    """
    hypotheses: List[Hypothesis] = []

    total_samples = sum(mode_summary.values())
    if total_samples == 0:
        return hypotheses

    tip_in_count = mode_summary.get("tip_in", 0)
    tip_out_count = mode_summary.get("tip_out", 0)
    wot_count = mode_summary.get("wot", 0)

    # Need minimum tip-in samples to analyze
    if tip_in_count < TRANSIENT_TIP_IN_MIN_SAMPLES:
        return hypotheses

    transient_pct = (tip_in_count + tip_out_count) / total_samples * 100

    # Get AFR error surface for analysis
    afr_surface = None
    afr_surface_name = "global"
    for key in ["afr_error_front", "afr_error_rear", "afr_error_global"]:
        if key in surfaces:
            afr_surface = surfaces[key]
            afr_surface_name = key.split("_")[-1]
            break

    if afr_surface is None:
        return hypotheses

    # Analyze AFR error characteristics
    mean_error = afr_surface.stats.mean or 0
    p05 = afr_surface.stats.p05 or 0
    p95 = afr_surface.stats.p95 or 0
    variance = (p95 - p05) if (p95 is not None and p05 is not None) else 0

    # Check for lean excursion during tip-in
    is_lean = mean_error > TRANSIENT_AFR_LEAN_THRESHOLD
    is_rich = mean_error < TRANSIENT_AFR_RICH_THRESHOLD
    high_variance = variance > TRANSIENT_AFR_VARIANCE_HIGH

    if is_lean or high_variance:
        evidence = []
        confidence = 0.5  # Base confidence

        # Build evidence
        evidence.append(
            f"TIP_IN mode: {tip_in_count} samples ({transient_pct:.1f}% of data)"
        )

        if is_lean:
            evidence.append(
                f"Mean AFR error is lean: +{mean_error:.2f} (threshold: +{TRANSIENT_AFR_LEAN_THRESHOLD})"
            )
            evidence.append(
                "Lean tip-in indicates insufficient transient enrichment or wall wetting compensation"
            )
            confidence += 0.15

        if high_variance:
            evidence.append(
                f"High AFR variance: {variance:.2f} (5th-95th percentile spread)"
            )
            evidence.append(
                "High variance suggests inconsistent fuel delivery during transients"
            )
            confidence += 0.1

        # ECU coupling insight
        evidence.append(
            "ECU context: VE is a correction layer; transient enrichment compensates for wall wetting lag"
        )

        # Check for knock correlation (ECU coupling)
        if has_knock and "knock_activity" in surfaces:
            knock_surface = surfaces["knock_activity"]
            if knock_surface.stats.max and knock_surface.stats.max > 0:
                evidence.append(
                    "Knock activity detected - lean tip-in may cause knock spikes"
                )
                evidence.append(
                    "ECU coupling: Lean combustion reduces knock margin")
                confidence += 0.1
        elif not has_knock:
            evidence.append(
                "No knock data available - cannot assess knock correlation with lean tip-in"
            )
            confidence -= 0.05

        confidence = min(0.85, confidence)

        hypotheses.append(
            Hypothesis(
                hypothesis_id="transient_tipin_hesitation",
                title="Tip-In Hesitation Likely Transient Fuel Issue",
                confidence=confidence,
                category=HypothesisCategory.TRANSIENT,
                evidence=evidence,
                distinguishing_checks=[
                    "Compare TIP_IN AFR vs steady WOT AFR in same RPM/MAP band",
                    "Log controlled roll-on tip-ins at 2-3 second throttle rate",
                    "Check if lean spikes correlate with throttle opening rate (TPSdot)",
                    "Compare warm engine vs cold engine transient response",
                    "If knock data available, check if knock spikes coincide with lean tip-in",
                ],
            ))

    # Check for tip-in rich (over-enrichment)
    if is_rich:
        evidence = [
            f"TIP_IN mode: {tip_in_count} samples",
            f"Mean AFR error is rich: {mean_error:.2f} (threshold: {TRANSIENT_AFR_RICH_THRESHOLD})",
            "Rich tip-in may indicate excessive transient enrichment or wall wetting overshoot",
            "ECU context: Over-enrichment wastes fuel and can foul plugs",
        ]

        hypotheses.append(
            Hypothesis(
                hypothesis_id="transient_tipin_rich",
                title="Tip-In Over-Enrichment Detected",
                confidence=0.6,
                category=HypothesisCategory.TRANSIENT,
                evidence=evidence,
                distinguishing_checks=[
                    "Compare TIP_IN AFR vs steady WOT AFR in same RPM/MAP band",
                    "Check if rich condition persists after throttle stabilizes",
                    "Log at different throttle rates to assess enrichment scaling",
                ],
            ))

    return hypotheses


def _check_knock_issues(
    surfaces: Dict[str, Surface2D],
    spark_valley: List[SparkValleyFinding],
    has_knock: bool = False,
) -> List[Hypothesis]:
    """
    ECU-Coupling-Aware Knock-Limit Hypothesis (Rule B):

    Midrange high-load spark valley is knock-limited (often rear-dominant).

    Trigger: High-MAP band shows spark valley AND knock_rate peaks in same RPM band.

    ECU Mental Model Context:
    - Spark is base + modifiers; knock always has authority
    - VE and spark are coupled via combustion efficiency
    - Knock retard reduces power and can mask VE errors
    - Rear cylinder is typically hotter on V-twins (more knock-prone)
    """
    hypotheses: List[Hypothesis] = []

    # Get knock surface if available
    knock_surface = surfaces.get("knock_activity")

    # Analyze spark valley findings with knock correlation
    if spark_valley:
        for finding in spark_valley:
            if finding.depth_deg < KNOCK_VALLEY_MIN_DEPTH:
                continue

            evidence = []
            confidence = 0.5  # Base confidence

            # Basic valley evidence
            evidence.append(
                f"Spark valley at {finding.rpm_center} RPM in high-MAP band")
            evidence.append(
                f"Valley depth: {finding.depth_deg:.1f}° (threshold: {KNOCK_VALLEY_MIN_DEPTH}°)"
            )
            evidence.append(
                f"Valley RPM range: {finding.rpm_band[0]}-{finding.rpm_band[1]} RPM"
            )
            evidence.append(
                f"Timing drops from {finding.pre_valley_deg:.1f}° to {finding.valley_min_deg:.1f}° then rises to {finding.post_valley_deg:.1f}°"
            )

            # ECU coupling insight
            evidence.append(
                "ECU context: Spark is base + modifiers; knock always has authority to retard timing"
            )

            # Significant depth increases confidence
            if finding.depth_deg >= KNOCK_VALLEY_SIGNIFICANT_DEPTH:
                confidence += 0.15
                evidence.append(
                    f"Valley depth is significant (>= {KNOCK_VALLEY_SIGNIFICANT_DEPTH}°)"
                )

            # Check knock correlation
            if has_knock and knock_surface is not None:
                knock_corr = _check_knock_correlation_with_valley(
                    knock_surface, finding)

                if knock_corr["has_correlation"]:
                    confidence += 0.2
                    evidence.append(
                        "Knock activity correlates with spark valley location")
                    evidence.extend(knock_corr["evidence"])
                    evidence.append(
                        "ECU coupling: Knock-limited timing confirmed by knock sensor data"
                    )
                else:
                    evidence.append(
                        "Knock data present but no strong correlation with valley"
                    )
                    evidence.append(
                        "Valley may be calibrated conservatively or knock sensor sensitivity low"
                    )
            elif not has_knock:
                confidence -= 0.1
                evidence.append(
                    "No knock data available - cannot confirm knock correlation"
                )
                evidence.append(
                    "Lower confidence: valley could be knock-limited or conservatively calibrated"
                )

            confidence = min(0.9, max(0.4, confidence))

            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"knock_limit_valley_{finding.cylinder}",
                    title=f"Midrange High-Load Spark Valley is Knock-Limited ({finding.cylinder.title()})",
                    confidence=confidence,
                    category=HypothesisCategory.KNOCK_LIMIT,
                    evidence=evidence,
                    distinguishing_checks=[
                        f"Log knock count/retard specifically at {finding.rpm_center} RPM WOT",
                        "Compare valley depth with and without knock channel logged",
                        "Check if valley deepens with higher IAT (heat increases knock)",
                        "If no knock data: add knock sensor logging to confirm hypothesis",
                        "Compare front vs rear cylinder knock activity in valley band",
                    ],
                ))

        # Check for rear-dominant knock (common on V-twins)
        front = next((f for f in spark_valley if f.cylinder == "front"), None)
        rear = next((f for f in spark_valley if f.cylinder == "rear"), None)

        if front and rear:
            depth_diff = rear.depth_deg - front.depth_deg

            if depth_diff >= KNOCK_CYLINDER_ASYMMETRY_THRESHOLD:
                evidence = [
                    f"Rear cylinder valley: {rear.depth_deg:.1f}°",
                    f"Front cylinder valley: {front.depth_deg:.1f}°",
                    f"Rear is {depth_diff:.1f}° deeper than front",
                    "Rear-dominant knock is common on V-twins due to heat soak",
                    "ECU context: Rear cylinder runs hotter, more knock-prone",
                ]

                confidence = 0.75

                # Check knock surface for cylinder asymmetry
                if has_knock and knock_surface is not None:
                    # This would require per-cylinder knock surfaces
                    evidence.append(
                        "Check per-cylinder knock data to confirm rear-dominant knock"
                    )
                else:
                    confidence -= 0.1
                    evidence.append(
                        "No knock data to confirm cylinder asymmetry")

                hypotheses.append(
                    Hypothesis(
                        hypothesis_id="knock_rear_dominant",
                        title="Rear Cylinder is More Knock-Limited Than Front",
                        confidence=confidence,
                        category=HypothesisCategory.KNOCK_LIMIT,
                        evidence=evidence,
                        distinguishing_checks=[
                            "Log per-cylinder knock counts if available",
                            "Compare cylinder head temperatures",
                            "Check if rear runs richer (knock compensation)",
                            "Evaluate if per-cylinder timing offset is appropriate",
                        ],
                    ))

            elif depth_diff <= -KNOCK_CYLINDER_ASYMMETRY_THRESHOLD:
                # Front is deeper (unusual)
                hypotheses.append(
                    Hypothesis(
                        hypothesis_id="knock_front_dominant",
                        title="Front Cylinder is More Knock-Limited Than Rear (Unusual)",
                        confidence=0.6,
                        category=HypothesisCategory.KNOCK_LIMIT,
                        evidence=[
                            f"Front cylinder valley: {front.depth_deg:.1f}°",
                            f"Rear cylinder valley: {rear.depth_deg:.1f}°",
                            f"Front is {abs(depth_diff):.1f}° deeper than rear",
                            "This is unusual - typically rear is hotter/more knock-prone",
                            "May indicate front cylinder cooling issue or sensor anomaly",
                        ],
                        distinguishing_checks=[
                            "Verify knock sensor placement and sensitivity",
                            "Check front cylinder cooling (airflow, thermostat)",
                            "Compare fuel quality between fills",
                        ],
                    ))

    return hypotheses


def _check_fuel_model_issues(
    surfaces: Dict[str, Surface2D],
    mode_summary: Dict[str, int],
) -> List[Hypothesis]:
    """
    Check for VE/fuel model issues.

    Signals:
    - Large mean AFR error
    - High variance in AFR error
    - Systematic lean or rich bias
    """
    hypotheses: List[Hypothesis] = []

    # Analyze AFR error surfaces
    for surface_id in [
            "afr_error_front", "afr_error_rear", "afr_error_global"
    ]:
        if surface_id not in surfaces:
            continue

        surface = surfaces[surface_id]
        cylinder = surface_id.split("_")[-1]

        if surface.stats.mean is None:
            continue

        mean_error = surface.stats.mean

        # Check for systematic lean
        if mean_error > 0.5:
            confidence = min(0.85, 0.4 + abs(mean_error) / 5)
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"ve_lean_{cylinder}",
                    title=f"VE Table May Be Low ({cylinder.title()} Cylinder)",
                    confidence=confidence,
                    category=HypothesisCategory.FUEL_MODEL,
                    evidence=[
                        f"Mean AFR error: +{mean_error:.2f} (lean)",
                        "Positive AFR error means measured AFR > commanded",
                        "VE table may be underestimating airflow",
                    ],
                    distinguishing_checks=[
                        "Compare measured vs commanded AFR across operating range",
                        "Check if lean condition is worse at specific RPM/MAP",
                        "Verify O2 sensor calibration",
                    ],
                ))

        # Check for systematic rich
        elif mean_error < -0.5:
            confidence = min(0.85, 0.4 + abs(mean_error) / 5)
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"ve_rich_{cylinder}",
                    title=f"VE Table May Be High ({cylinder.title()} Cylinder)",
                    confidence=confidence,
                    category=HypothesisCategory.FUEL_MODEL,
                    evidence=[
                        f"Mean AFR error: {mean_error:.2f} (rich)",
                        "Negative AFR error means measured AFR < commanded",
                        "VE table may be overestimating airflow",
                    ],
                    distinguishing_checks=[
                        "Compare measured vs commanded AFR across operating range",
                        "Check if rich condition is worse at specific RPM/MAP",
                        "Verify injector flow rates match calibration",
                    ],
                ))

        # Check for high variance (inconsistent fueling)
        if surface.stats.p95 is not None and surface.stats.p05 is not None:
            spread = surface.stats.p95 - surface.stats.p05
            if spread > 2.0:
                hypotheses.append(
                    Hypothesis(
                        hypothesis_id=f"ve_inconsistent_{cylinder}",
                        title=f"Inconsistent AFR Across Operating Range ({cylinder.title()})",
                        confidence=0.6,
                        category=HypothesisCategory.FUEL_MODEL,
                        evidence=[
                            f"AFR error spread (5th-95th percentile): {spread:.1f}",
                            "Large spread suggests VE table shape doesn't match engine",
                        ],
                        distinguishing_checks=[
                            "Identify RPM/MAP regions with largest errors",
                            "Check for systematic patterns vs random noise",
                            "Compare steady-state vs transient AFR accuracy",
                        ],
                    ))

    return hypotheses


def _check_temp_issues(
    mode_summary: Dict[str, int],
    surfaces: Dict[str, Surface2D],
    has_iat: bool = False,
) -> List[Hypothesis]:
    """
    ECU-Coupling-Aware Temperature Hypothesis (Rule C):

    Heat/temperature trims dominating high load.

    Trigger: Spark reduced broadly at high MAP correlated with high IAT/ECT segments.

    ECU Mental Model Context:
    - Spark is base + modifiers; temperature trims reduce timing for safety
    - VE and spark are coupled via combustion efficiency
    - Heat soak increases knock tendency, triggering more retard
    - Temperature effects are broad (not localized to torque-peak band)
    """
    hypotheses: List[Hypothesis] = []

    total_samples = sum(mode_summary.values())
    if total_samples == 0:
        return hypotheses

    heat_soak_count = mode_summary.get("heat_soak", 0)
    heat_soak_pct = heat_soak_count / total_samples * 100

    # Get spark surface for analysis
    spark_surface = None
    spark_name = "global"
    for key in ["spark_front", "spark_rear", "spark_global"]:
        if key in surfaces:
            spark_surface = surfaces[key]
            spark_name = key.split("_")[-1]
            break

    # Check for heat soak with spark analysis
    if heat_soak_count >= TEMP_HEAT_SOAK_MIN_SAMPLES or heat_soak_pct > 5:
        evidence = []
        confidence = 0.5

        evidence.append(
            f"Heat soak detected: {heat_soak_count} samples ({heat_soak_pct:.1f}% of data)"
        )
        evidence.append(
            "High IAT + low airflow conditions trigger temperature trims")
        evidence.append(
            "ECU context: Temperature trims reduce spark timing for knock safety"
        )

        # Analyze spark reduction at high MAP
        if spark_surface is not None:
            high_map_stats = _get_high_map_slice_stats(spark_surface)

            if high_map_stats["mean"] is not None and high_map_stats[
                    "min"] is not None:
                spark_range = (high_map_stats["max"]
                               or 0) - (high_map_stats["min"] or 0)

                if spark_range > TEMP_SPARK_REDUCTION_THRESHOLD:
                    evidence.append(
                        f"Spark timing varies {spark_range:.1f}° across high-MAP band"
                    )
                    evidence.append(
                        f"Minimum spark: {high_map_stats['min']:.1f}° at {high_map_stats['rpm_at_min']} RPM"
                    )
                    evidence.append(
                        "Broad spark reduction suggests temperature trims active"
                    )
                    confidence += 0.15

        # IAT availability affects confidence
        if has_iat:
            evidence.append(
                "IAT data available - can correlate spark reduction with temperature"
            )
            confidence += 0.1
        else:
            evidence.append(
                "No IAT data - cannot directly correlate spark with temperature"
            )
            evidence.append(
                "Heat soak mode detected via other signals (low RPM, low airflow)"
            )
            confidence -= 0.1

        confidence = min(0.8, max(0.4, confidence))

        hypotheses.append(
            Hypothesis(
                hypothesis_id="temp_trim_high_load",
                title="Heat/Temperature Trims Dominating High Load",
                confidence=confidence,
                category=HypothesisCategory.TEMP_TRIM,
                evidence=evidence,
                distinguishing_checks=[
                    "Compare spark timing early vs late in logging session (heat buildup)",
                    "Log IAT throughout session to correlate with spark changes",
                    "Check if spark reduction is broad (temp trim) vs localized (knock limit)",
                    "Allow engine to cool between pulls to isolate heat soak effect",
                    "Compare hot-start vs cold-start spark timing at same RPM/MAP",
                ],
            ))

    # Check for broad spark reduction at high MAP (even without heat soak mode)
    if spark_surface is not None:
        high_map_stats = _get_high_map_slice_stats(spark_surface)
        midrange_stats = _get_midrange_rpm_stats(spark_surface)

        if (high_map_stats["mean"] is not None
                and midrange_stats["mean"] is not None
                and high_map_stats["valid_cells"] >= 5):
            # Check if spark is broadly reduced at high MAP (not just at torque peak)
            spark_mean = high_map_stats["mean"]
            spark_min = high_map_stats["min"] or spark_mean
            spark_max = high_map_stats["max"] or spark_mean

            # If spark is uniformly low across high MAP (not a valley pattern)
            if (spark_max - spark_min < 3.0
                    and spark_mean < 25):  # Relatively flat and low
                evidence = [
                    f"Spark timing is broadly reduced at high MAP: mean {spark_mean:.1f}°",
                    f"Spark range at high MAP: {spark_min:.1f}° to {spark_max:.1f}° (relatively flat)",
                    "Broad reduction suggests temperature trims rather than localized knock limit",
                    "ECU context: Temperature trims affect entire high-load region uniformly",
                ]

                if not has_iat:
                    evidence.append(
                        "Add IAT logging to confirm temperature correlation")

                hypotheses.append(
                    Hypothesis(
                        hypothesis_id="temp_trim_broad_reduction",
                        title="Broad Spark Reduction at High Load (Temperature Trim Pattern)",
                        confidence=0.55,
                        category=HypothesisCategory.TEMP_TRIM,
                        evidence=evidence,
                        distinguishing_checks=[
                            "Compare early-run vs late-run spark at same RPM/MAP",
                            "Log ECT and IAT to correlate with spark timing",
                            "Check if reduction is consistent across RPM (temp) vs localized (knock)",
                            "Verify cooling system is functioning properly",
                        ],
                    ))

    return hypotheses


def _check_data_quality(
    mode_summary: Dict[str, int],
    surfaces: Dict[str, Surface2D],
) -> List[Hypothesis]:
    """
    Check for data quality issues.

    Signals:
    - Low sample counts
    - Poor coverage
    - High proportion of unknown modes
    """
    hypotheses: List[Hypothesis] = []

    total_samples = sum(mode_summary.values())

    # Check for low total samples
    if total_samples < 500:
        hypotheses.append(
            Hypothesis(
                hypothesis_id="low_sample_count",
                title="Limited Data Available for Analysis",
                confidence=0.9,
                category=HypothesisCategory.DATA_QUALITY,
                evidence=[
                    f"Total samples: {total_samples}",
                    "More data would improve analysis confidence",
                ],
                distinguishing_checks=[
                    "Extend logging duration",
                    "Ensure data is being captured at full rate",
                    "Verify logging software configuration",
                ],
            ))

    # Check surface coverage
    for surface_id, surface in surfaces.items():
        coverage = surface.stats.coverage_pct
        if coverage < 30:
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"low_coverage_{surface_id}",
                    title=f"Low Data Coverage in {surface.title}",
                    confidence=0.7,
                    category=HypothesisCategory.DATA_QUALITY,
                    evidence=[
                        f"Coverage: {coverage:.1f}% of cells",
                        f"Valid cells: {surface.stats.non_nan_cells}/{surface.stats.total_cells}",
                    ],
                    distinguishing_checks=[
                        "Log across wider RPM/MAP range",
                        "Ensure WOT pulls reach high MAP",
                        "Add cruise and part-throttle logging",
                    ],
                ))
            break  # Only report once

    return hypotheses


# =============================================================================
# Main Builder Function
# =============================================================================


def build_cause_tree(
    mode_summary: Dict[str, int],
    surfaces: Dict[str, Surface2D],
    spark_valley: Optional[List[SparkValleyFinding]] = None,
    transient_result: Optional[Any] = None,
    heat_profile: Optional[Any] = None,
    has_knock: Optional[bool] = None,
    has_iat: Optional[bool] = None,
) -> CauseTreeResult:
    """
    Build an ECU-coupling-aware cause tree from analysis results.

    This is a deterministic hypothesis generator that examines patterns
    in the data to suggest likely root causes for tuning issues.

    ECU Mental Model:
    - VE is a correction layer; closed-loop can mask VE error
    - Spark is base + modifiers; knock always has authority
    - VE and spark are coupled via combustion efficiency and knock

    IMPORTANT: Outputs diagnosis + recommended test/logging checks only.
    Does NOT output calibration changes like "change table X by Y".

    Args:
        mode_summary: Dict of mode -> sample count from mode detection
        surfaces: Dict of surface_id -> Surface2D
        spark_valley: List of SparkValleyFinding from valley detection
        transient_result: Optional TransientFuelResult (if available)
        heat_profile: Optional HeatProfile (if available)
        has_knock: Whether knock data is available (auto-detected if None)
        has_iat: Whether IAT data is available (auto-detected if None)

    Returns:
        CauseTreeResult with ranked hypotheses
    """
    spark_valley = spark_valley or []
    all_hypotheses: List[Hypothesis] = []
    analysis_notes: List[str] = []

    # Auto-detect channel availability if not specified
    if has_knock is None:
        has_knock = "knock_activity" in surfaces

    if has_iat is None:
        # Check if heat_soak mode was detected (implies IAT was available)
        has_iat = mode_summary.get("heat_soak", 0) > 0

    # Add ECU model context to analysis notes
    analysis_notes.append(
        "ECU Model: VE is correction layer, spark has knock authority, VE/spark coupled via combustion"
    )

    # Run ECU-coupling-aware hypothesis generators
    # Rule A: Transient fuel issues
    all_hypotheses.extend(
        _check_transient_issues(mode_summary, surfaces, has_knock))

    # Rule B: Knock-limited timing
    all_hypotheses.extend(
        _check_knock_issues(surfaces, spark_valley, has_knock))

    # Rule C: Temperature trims
    all_hypotheses.extend(_check_temp_issues(mode_summary, surfaces, has_iat))

    # Supporting checks (fuel model, data quality)
    all_hypotheses.extend(_check_fuel_model_issues(surfaces, mode_summary))
    all_hypotheses.extend(_check_data_quality(mode_summary, surfaces))

    # Sort by confidence (highest first)
    all_hypotheses.sort(key=lambda h: h.confidence, reverse=True)

    # Build summary
    if not all_hypotheses:
        summary = "No significant issues detected. Data appears nominal."
    else:
        top = all_hypotheses[0]
        num_high_conf = sum(1 for h in all_hypotheses if h.confidence >= 0.7)
        summary = (
            f"Top hypothesis: {top.title} ({top.confidence:.0%} confidence). "
            f"{num_high_conf} high-confidence hypothesis(es) identified.")

        # Add category breakdown
        categories = set(h.category for h in all_hypotheses)
        if len(categories) > 1:
            summary += f" Issues span {len(categories)} categories."

        # Note if knock data was missing
        if not has_knock:
            summary += " Note: No knock data - some hypotheses have reduced confidence."

    # Add analysis notes
    total_samples = sum(mode_summary.values())
    analysis_notes.append(
        f"Analyzed {total_samples} samples across {len(surfaces)} surfaces")
    analysis_notes.append(f"Generated {len(all_hypotheses)} hypotheses")
    analysis_notes.append(f"Knock data available: {has_knock}")
    analysis_notes.append(f"IAT data available: {has_iat}")

    if spark_valley:
        analysis_notes.append(
            f"Detected {len(spark_valley)} spark valley finding(s)")

    # Note graceful degradation
    if not has_knock:
        analysis_notes.append(
            "Graceful degradation: Knock-related confidence reduced without knock data"
        )

    return CauseTreeResult(
        hypotheses=all_hypotheses,
        summary=summary,
        analysis_notes=analysis_notes,
    )
