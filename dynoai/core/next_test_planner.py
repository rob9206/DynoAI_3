"""
DynoAI NextGen Test Planner

Produces a prioritized next-test plan that reduces uncertainty and increases
coverage where it matters most.

Uses hit_count matrices to identify coverage gaps in high-impact regions:
- High MAP midrange (torque peak, knock-sensitive)
- Idle/low MAP (stability, sensor quality)
- Tip-in transition zones (transient fueling)

The planner generates human-readable test recommendations, not machine
control commands. Operators decide how to execute based on their dyno setup.

Usage:
    from dynoai.core.next_test_planner import generate_test_plan, NextTestPlan

    plan = generate_test_plan(surfaces, cause_tree, mode_summary)
    for step in plan.steps:
        print(f"{step.name}: {step.goal}")
        print(f"  RPM: {step.rpm_range}, MAP: {step.map_range}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from dynoai.core.cause_tree import CauseTreeResult, Hypothesis, HypothesisCategory
from dynoai.core.surface_builder import Surface2D

__all__ = [
    "TestStep",
    "NextTestPlan",
    "CoverageGap",
    "generate_test_plan",
    "identify_coverage_gaps",
    "generate_inertia_dyno_tests",
    "generate_street_tests",
    "score_test_efficiency",
]

# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class TestStep:
    """
    A single test step recommendation.

    This is human-readable guidance, not machine control commands.
    """

    name: str
    goal: str
    rpm_range: Optional[Tuple[int, int]] = None
    map_range: Optional[Tuple[int, int]] = None
    test_type: str = (
        "general"  # steady_state_sweep, wot_pull, transient_rolloff, idle_hold
    )
    constraints: str = ""
    required_channels: List[str] = field(default_factory=list)
    success_criteria: str = ""
    risk_notes: str = ""
    priority: int = 1  # 1 = highest priority
    expected_coverage_gain: float = 0.0  # Expected % coverage increase
    efficiency_score: float = 0.0  # Coverage gain per unit time (0.0-1.0)

    def to_dict(self) -> Dict:
        """Serialize to JSON-compatible dict."""
        return {
            "name": self.name,
            "goal": self.goal,
            "rpm_range": list(self.rpm_range) if self.rpm_range else None,
            "map_range": list(self.map_range) if self.map_range else None,
            "test_type": self.test_type,
            "constraints": self.constraints,
            "required_channels": self.required_channels,
            "success_criteria": self.success_criteria,
            "risk_notes": self.risk_notes,
            "priority": self.priority,
            "expected_coverage_gain": round(self.expected_coverage_gain, 2),
            "efficiency_score": round(self.efficiency_score, 2),
        }


@dataclass
class NextTestPlan:
    """
    Complete test plan with prioritized steps.
    """

    steps: List[TestStep]
    priority_rationale: str
    coverage_gaps: List[str]  # String descriptions for backward compatibility
    coverage_gaps_detailed: List[CoverageGap] = field(default_factory=list)
    total_estimated_pulls: int = 0

    def get_high_priority_steps(self) -> List[TestStep]:
        """Get steps with priority 1 or 2."""
        return [s for s in self.steps if s.priority <= 2]

    def get_dyno_steps(self) -> List[TestStep]:
        """Get steps suitable for inertia dyno."""
        return [s for s in self.steps if s.test_type == "wot_pull"]

    def get_street_steps(self) -> List[TestStep]:
        """Get steps suitable for street logging."""
        return [
            s for s in self.steps
            if s.test_type in ["transient_rolloff", "steady_state_sweep"]
        ]

    def to_dict(self) -> Dict:
        """Serialize to JSON-compatible dict."""
        return {
            "steps": [s.to_dict() for s in self.steps],
            "priority_rationale":
            self.priority_rationale,
            "coverage_gaps":
            self.coverage_gaps,
            "coverage_gaps_detailed":
            ([g.to_dict() for g in self.coverage_gaps_detailed]
             if self.coverage_gaps_detailed else []),
            "total_estimated_pulls":
            self.total_estimated_pulls,
            "dyno_step_count":
            len(self.get_dyno_steps()),
            "street_step_count":
            len(self.get_street_steps()),
        }


# =============================================================================
# Coverage Analysis
# =============================================================================


@dataclass
class CoverageGap:
    """Describes a coverage gap in the data."""

    rpm_low: int
    rpm_high: int
    map_low: int
    map_high: int
    empty_cells: int
    total_cells: int
    impact: str  # "high", "medium", "low"
    description: str
    region_type: str = (
        "general"  # "high_map_midrange", "idle_low_map", "tip_in", "general"
    )

    def to_dict(self) -> Dict:
        """Serialize to JSON-compatible dict."""
        return {
            "rpm_range": [self.rpm_low, self.rpm_high],
            "map_range": [self.map_low, self.map_high],
            "empty_cells":
            self.empty_cells,
            "total_cells":
            self.total_cells,
            "coverage_pct":
            (round((self.total_cells - self.empty_cells) / self.total_cells *
                   100, 1) if self.total_cells > 0 else 0),
            "impact":
            self.impact,
            "region_type":
            self.region_type,
            "description":
            self.description,
        }


def identify_coverage_gaps(
    surfaces: Dict[str, Surface2D],
    min_hits_threshold: int = 3,
) -> List[CoverageGap]:
    """
    Identify coverage gaps in the surfaces.

    Prioritizes gaps in high-impact regions for inertia dyno + street logging:
    - High MAP midrange (80-100 kPa at 2500-4500 RPM) - knock sensitive, dyno-critical
    - Idle/low MAP (20-40 kPa at <1500 RPM) - stability critical
    - Tip-in zones (high TPSdot/MAPdot segments) - transient sensitive

    Args:
        surfaces: Dict of surface_id -> Surface2D
        min_hits_threshold: Minimum hits to consider a cell "covered"

    Returns:
        List of CoverageGap sorted by impact
    """
    gaps: List[CoverageGap] = []

    # Use the first available surface for hit count analysis
    ref_surface = None
    for key in [
            "spark_front",
            "spark_rear",
            "afr_error_front",
            "afr_error_rear",
            "spark_global",
            "afr_error_global",
    ]:
        if key in surfaces:
            ref_surface = surfaces[key]
            break

    if ref_surface is None:
        return gaps

    rpm_bins = ref_surface.rpm_axis.bins
    map_bins = ref_surface.map_axis.bins
    hit_counts = ref_surface.hit_count

    # Define high-impact regions optimized for inertia dyno + street
    # (name, rpm_range, map_range, impact_level, region_type)
    high_impact_regions = [
        # High MAP midrange - critical for inertia dyno (fast ramps)
        (
            "High MAP midrange (dyno-critical)",
            (2500, 4500),
            (80, 100),
            "high",
            "high_map_midrange",
        ),
        ("WOT torque peak", (4000, 5500), (85, 100), "high",
         "high_map_midrange"),
        ("High MAP low-mid RPM", (2000, 3000), (80, 100), "high",
         "high_map_midrange"),
        # Idle/low MAP - stability critical (street logging)
        ("Idle stability", (800, 1500), (20, 40), "medium", "idle_low_map"),
        ("Low load cruise", (1500, 2500), (30, 50), "medium", "idle_low_map"),
        # Tip-in transition zones (street logging)
        ("Tip-in transition low", (2000, 3500), (50, 70), "high", "tip_in"),
        ("Tip-in transition mid", (3000, 4500), (60, 85), "high", "tip_in"),
        # Part throttle cruise (street logging)
        ("Cruise part-throttle", (2500, 4000), (45, 65), "medium", "general"),
    ]

    for region_name, rpm_range, map_range, impact, region_type in high_impact_regions:
        rpm_low, rpm_high = rpm_range
        map_low, map_high = map_range

        # Find bins in this region
        rpm_indices = [
            i for i, r in enumerate(rpm_bins) if rpm_low <= r <= rpm_high
        ]
        map_indices = [
            i for i, m in enumerate(map_bins) if map_low <= m <= map_high
        ]

        if not rpm_indices or not map_indices:
            continue

        # Count empty cells
        empty_cells = 0
        total_cells = len(rpm_indices) * len(map_indices)

        for ri in rpm_indices:
            for mi in map_indices:
                if hit_counts[ri][mi] < min_hits_threshold:
                    empty_cells += 1

        if empty_cells > 0:
            coverage_pct = (total_cells - empty_cells) / total_cells * 100
            gaps.append(
                CoverageGap(
                    rpm_low=rpm_low,
                    rpm_high=rpm_high,
                    map_low=map_low,
                    map_high=map_high,
                    empty_cells=empty_cells,
                    total_cells=total_cells,
                    impact=impact,
                    region_type=region_type,
                    description=f"{region_name}: {empty_cells}/{total_cells} cells need data ({coverage_pct:.0f}% covered)",
                ))

    # Sort by impact (high first) then by empty cells
    impact_order = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: (impact_order.get(g.impact, 2), -g.empty_cells))

    return gaps


# =============================================================================
# Inertia Dyno Test Generators
# =============================================================================


def generate_inertia_dyno_tests(
    gaps: List[CoverageGap],
    mode_summary: Optional[Dict[str, int]] = None,
) -> List[TestStep]:
    """
    Generate test steps optimized for inertia dyno (fast ramps, limited steady-state).

    Inertia dynos excel at:
    - Full WOT pulls from low RPM
    - Consistent, repeatable ramps
    - High MAP data collection

    Args:
        gaps: Coverage gaps to address
        mode_summary: Optional mode distribution

    Returns:
        List of TestStep for inertia dyno
    """
    steps: List[TestStep] = []

    # Focus on high MAP midrange gaps (dyno strength)
    high_map_gaps = [g for g in gaps if g.region_type == "high_map_midrange"]

    if high_map_gaps:
        # Group gaps by RPM range for efficient pulls
        rpm_ranges = set()
        for gap in high_map_gaps:
            rpm_ranges.add((gap.rpm_low, gap.rpm_high))

        for rpm_low, rpm_high in sorted(rpm_ranges):
            # Suggest start RPM and gear for inertia dyno
            start_rpm = max(1500, rpm_low - 500)  # Start 500 RPM below target

            # Gear suggestion based on RPM range
            if rpm_high <= 4000:
                gear_suggestion = "3rd or 4th gear (lower gear = faster ramp)"
            elif rpm_high <= 5500:
                gear_suggestion = "4th or 5th gear"
            else:
                gear_suggestion = (
                    "5th or 6th gear (higher gear = slower ramp for top end)")

            steps.append(
                TestStep(
                    name=f"Inertia Dyno Pull: {rpm_low}-{rpm_high} RPM",
                    goal=f"Fill high-MAP coverage in {rpm_low}-{rpm_high} RPM range",
                    rpm_range=(start_rpm, rpm_high + 500),
                    map_range=(80, 100),
                    test_type="wot_pull",
                    constraints=f"Start at {start_rpm} RPM, full WOT to {rpm_high + 500} RPM. {gear_suggestion}",
                    required_channels=[
                        "afr_meas_f",
                        "afr_meas_r",
                        "spark_f",
                        "spark_r",
                        "knock",
                    ],
                    success_criteria=f"≥3 samples per cell in {rpm_low}-{rpm_high} RPM @ 80-100 kPa",
                    risk_notes="Monitor knock sensor; abort if excessive detonation",
                    priority=1,
                ))

    # Add general WOT pull if insufficient high-load data
    if mode_summary:
        wot_samples = mode_summary.get("wot", 0)
        if wot_samples < 100:
            steps.append(
                TestStep(
                    name="Baseline WOT Pull Sequence",
                    goal="Establish baseline high-load data across full RPM range",
                    rpm_range=(2000, 6500),
                    map_range=(85, 100),
                    test_type="wot_pull",
                    constraints="3-5 consecutive WOT pulls from 2000 RPM to redline. Cool 30-60s between pulls.",
                    required_channels=[
                        "afr_meas_f",
                        "afr_meas_r",
                        "spark_f",
                        "spark_r",
                        "knock",
                        "iat",
                    ],
                    success_criteria="≥100 WOT samples with consistent AFR and spark readings",
                    risk_notes="Watch IAT rise; abort if >130°F. Monitor knock closely.",
                    priority=1,
                ))

    # Add repeatable pull for consistency check
    steps.append(
        TestStep(
            name="Consistency Check Pulls",
            goal="Verify repeatability of AFR and spark readings",
            rpm_range=(3000, 5500),
            map_range=(85, 100),
            test_type="wot_pull",
            constraints="3 identical WOT pulls from 3000 RPM. Same gear, same conditions.",
            required_channels=[
                "afr_meas_f", "afr_meas_r", "spark_f", "spark_r"
            ],
            success_criteria="AFR variation <0.3 AFR between pulls at same RPM/MAP cell",
            risk_notes="If variation >0.5 AFR, check for sensor issues or inconsistent fueling",
            priority=2,
        ))

    return steps


def generate_street_tests(
    gaps: List[CoverageGap],
    mode_summary: Optional[Dict[str, int]] = None,
) -> List[TestStep]:
    """
    Generate test steps optimized for street logging (transients, cruise, idle).

    Street logging excels at:
    - Transient events (tip-in, tip-out)
    - Cruise/part-throttle data
    - Idle stability
    - Heat soak conditions

    Args:
        gaps: Coverage gaps to address
        mode_summary: Optional mode distribution

    Returns:
        List of TestStep for street logging
    """
    steps: List[TestStep] = []

    # Tip-in gaps (street strength)
    tipin_gaps = [g for g in gaps if g.region_type == "tip_in"]
    if tipin_gaps:
        steps.append(
            TestStep(
                name="Street Route: Controlled Roll-On Tip-Ins",
                goal="Capture transient AFR during throttle tip-in events",
                rpm_range=(2000, 4500),
                map_range=(50, 85),
                test_type="transient_rolloff",
                constraints=("Route script: From steady 2500 RPM cruise, smoothly roll on throttle "
                             "to 70-80% over 2-3 seconds. Hold briefly, then lift. Repeat 5-8 times."
                             ),
                required_channels=[
                    "afr_meas_f", "afr_meas_r", "tps", "map_kpa"
                ],
                success_criteria="Capture 5+ tip-in events with consistent throttle rate",
                risk_notes="Avoid full WOT on street; stay in safe RPM range",
                priority=1,
            ))

    # Idle/low MAP gaps
    idle_gaps = [g for g in gaps if g.region_type == "idle_low_map"]
    if idle_gaps:
        steps.append(
            TestStep(
                name="Street Route: Idle Stability Logging",
                goal="Capture idle and low-load data for VE accuracy",
                rpm_range=(800, 2000),
                map_range=(20, 45),
                test_type="steady_state_sweep",
                constraints=("Route script: Park in safe location. Log 60+ seconds at idle. "
                             "Then log 30s each at 1200, 1500, 1800 RPM with light throttle."
                             ),
                required_channels=["afr_meas_f", "afr_meas_r", "iat", "ect"],
                success_criteria="≥50 samples at idle, ≥20 samples at each elevated RPM",
                risk_notes="Ensure engine is at operating temperature before logging",
                priority=2,
            ))

    # Cruise data
    if mode_summary:
        cruise_samples = mode_summary.get("cruise", 0)
        if cruise_samples < 200:
            steps.append(
                TestStep(
                    name="Street Route: Steady Cruise Logging",
                    goal="Collect part-throttle cruise data across RPM range",
                    rpm_range=(2000, 4000),
                    map_range=(40, 70),
                    test_type="steady_state_sweep",
                    constraints=("Route script: Find a flat road or highway. Hold steady speeds: "
                                 "35 mph (5s), 45 mph (5s), 55 mph (5s), 65 mph (5s). "
                                 "Repeat in different gears if possible."),
                    required_channels=[
                        "afr_meas_f",
                        "afr_meas_r",
                        "spark_f",
                        "spark_r",
                    ],
                    success_criteria="≥200 cruise samples across RPM/MAP grid",
                    risk_notes="Obey traffic laws; use safe roads",
                    priority=2,
                ))

    # Tip-out / decel events
    steps.append(
        TestStep(
            name="Street Route: Lift Tip-Out Events",
            goal="Capture decel fuel cut and tip-out transients",
            rpm_range=(2500, 5000),
            map_range=(20, 50),
            test_type="transient_rolloff",
            constraints=("Route script: Accelerate to 4000+ RPM, then fully lift throttle. "
                         "Let RPM drop naturally (no braking). Repeat 5+ times."),
            required_channels=["afr_meas_f", "afr_meas_r", "tps", "map_kpa"],
            success_criteria="Capture 5+ decel events showing fuel cut behavior",
            risk_notes="Ensure safe following distance; watch for traffic",
            priority=2,
        ))

    # Heat soak segment
    if mode_summary:
        heat_soak_samples = mode_summary.get("heat_soak", 0)
        if heat_soak_samples < 50:
            steps.append(
                TestStep(
                    name="Street Route: Heat Soak Segment",
                    goal="Capture heat soak conditions for IAT compensation analysis",
                    rpm_range=(1000, 2500),
                    map_range=(25, 50),
                    test_type="steady_state_sweep",
                    constraints=("Route script: After a spirited drive, park and idle for 2-3 minutes "
                                 "while logging. Watch IAT rise. Then do a short low-load drive."
                                 ),
                    required_channels=[
                        "afr_meas_f", "afr_meas_r", "iat", "ect"
                    ],
                    success_criteria="Capture IAT >120°F with corresponding AFR data",
                    risk_notes="Don't overheat; abort if coolant temp exceeds safe limits",
                    priority=3,
                ))

    return steps


# =============================================================================
# Test Step Generators (Legacy)
# =============================================================================


def _generate_coverage_tests(gaps: List[CoverageGap], ) -> List[TestStep]:
    """Generate test steps to fill coverage gaps."""
    steps: List[TestStep] = []

    for gap in gaps:
        if gap.impact == "high":
            priority = 1
        elif gap.impact == "medium":
            priority = 2
        else:
            priority = 3

        # Determine test type based on MAP range
        if gap.map_high >= 85:
            test_type = "wot_pull"
            constraints = "Full WOT required; monitor knock and temperatures"
            risk_notes = "High load - watch for knock events"
        elif gap.map_low <= 50:
            test_type = "steady_state_sweep"
            constraints = "Maintain stable throttle; allow readings to settle"
            risk_notes = "Low load - ensure adequate airflow for stable readings"
        else:
            test_type = "steady_state_sweep"
            constraints = "Part throttle hold; 3-5 seconds per point"
            risk_notes = ""

        step = TestStep(
            name=f"Fill {gap.rpm_low}-{gap.rpm_high} RPM @ {gap.map_low}-{gap.map_high} kPa",
            goal=gap.description,
            rpm_range=(gap.rpm_low, gap.rpm_high),
            map_range=(gap.map_low, gap.map_high),
            test_type=test_type,
            constraints=constraints,
            required_channels=[
                "afr_meas_f", "afr_meas_r", "spark_f", "spark_r"
            ],
            success_criteria=f"≥3 samples per cell in {gap.empty_cells} empty cells",
            risk_notes=risk_notes,
            priority=priority,
        )
        steps.append(step)

    return steps


def _generate_hypothesis_tests(
        hypotheses: List[Hypothesis], ) -> List[TestStep]:
    """Generate test steps to investigate hypotheses."""
    steps: List[TestStep] = []

    for hyp in hypotheses:
        if hyp.confidence < 0.5:
            continue  # Skip low-confidence hypotheses

        if hyp.category == HypothesisCategory.TRANSIENT:
            steps.append(
                TestStep(
                    name="Transient Response Characterization",
                    goal="Quantify tip-in/tip-out AFR behavior",
                    rpm_range=(2000, 4000),
                    map_range=(40, 80),
                    test_type="transient_rolloff",
                    constraints="Controlled throttle rate; 2-3 second tip-in from cruise",
                    required_channels=[
                        "afr_meas_f", "afr_meas_r", "tps", "map_kpa"
                    ],
                    success_criteria="Capture AFR during 3+ tip-in events with consistent rate",
                    risk_notes="Avoid full WOT if knock is a concern",
                    priority=1 if hyp.confidence >= 0.7 else 2,
                ))

        elif hyp.category == HypothesisCategory.KNOCK_LIMIT:
            if "rear" in hyp.hypothesis_id.lower():
                target_cyl = "rear"
            elif "front" in hyp.hypothesis_id.lower():
                target_cyl = "front"
            else:
                target_cyl = "both"

            steps.append(
                TestStep(
                    name=f"Knock Characterization ({target_cyl} cylinder)",
                    goal=f"Measure knock activity at suspected limit: {hyp.title}",
                    rpm_range=(3000, 5000),
                    map_range=(85, 100),
                    test_type="wot_pull",
                    constraints="Full WOT; monitor knock closely; abort if excessive",
                    required_channels=[
                        "knock",
                        "spark_f",
                        "spark_r",
                        "afr_meas_f",
                        "afr_meas_r",
                    ],
                    success_criteria="Log knock count/retard during 3+ WOT pulls",
                    risk_notes="High detonation risk - monitor closely",
                    priority=1,
                ))

        elif hyp.category == HypothesisCategory.TEMP_TRIM:
            steps.append(
                TestStep(
                    name="Thermal Stability Baseline",
                    goal="Log at stable temperature to isolate heat soak effects",
                    rpm_range=(1500, 4500),
                    map_range=(30, 90),
                    test_type="steady_state_sweep",
                    constraints="Allow engine to heat-stabilize (10+ min at operating temp)",
                    required_channels=[
                        "iat", "ect", "afr_meas_f", "afr_meas_r"
                    ],
                    success_criteria="IAT stable within 5°F during logging",
                    risk_notes="Avoid excessive idle time to prevent heat soak",
                    priority=2,
                ))

    # Deduplicate similar steps
    seen_names = set()
    unique_steps = []
    for step in steps:
        if step.name not in seen_names:
            seen_names.add(step.name)
            unique_steps.append(step)

    return unique_steps


# =============================================================================
# Efficiency Scoring
# =============================================================================


def score_test_efficiency(
    step: TestStep,
    current_coverage: float,
    aggregated_hit_count: Optional[Dict[str, list[list[int]]]] = None,
) -> Tuple[float, float]:
    """
    Score test efficiency: expected coverage gain / estimated time.

    Args:
        step: Test step to score
        current_coverage: Current coverage percentage (0-100)
        aggregated_hit_count: Optional cumulative hit count matrices

    Returns:
        Tuple of (expected_coverage_gain, efficiency_score)
        - expected_coverage_gain: Estimated % coverage increase (0-100)
        - efficiency_score: Normalized efficiency (0.0-1.0)
    """
    # Estimate cells that will be hit by this test
    estimated_new_cells = 0

    if step.rpm_range and step.map_range:
        rpm_min, rpm_max = step.rpm_range
        map_min, map_max = step.map_range

        # Rough cell count estimation
        # Standard bins: 16 RPM bins, 12 MAP bins
        rpm_span = rpm_max - rpm_min
        map_span = map_max - map_min

        # Estimate cells covered (rough approximation)
        rpm_cells = max(1, rpm_span // 500)  # ~500 RPM per bin
        map_cells = max(1, map_span // 10)  # ~10 kPa per bin
        estimated_new_cells = rpm_cells * map_cells

    # Adjust for test type (some tests cover more cells)
    type_multipliers = {
        "wot_pull": 1.5,  # Sweeps across RPM
        "steady_state_sweep": 1.2,
        "transient_rolloff": 1.0,
        "idle_hold": 0.5,  # Small region
        "general": 1.0,
    }
    multiplier = type_multipliers.get(step.test_type, 1.0)
    estimated_new_cells *= multiplier

    # Estimated time per test type (minutes)
    estimated_times = {
        "wot_pull": 2.0,  # Quick ramp + cool down
        "steady_state_sweep": 5.0,
        "transient_rolloff": 3.0,
        "idle_hold": 1.0,
        "general": 3.0,
    }
    estimated_time = estimated_times.get(step.test_type, 3.0)

    # Calculate expected coverage gain
    # Assume ~200 total cells in a standard surface
    total_cells = 200
    expected_coverage_gain = min(
        (estimated_new_cells / total_cells) * 100,
        100 - current_coverage,  # Can't exceed 100%
    )

    # Calculate efficiency score (cells per minute, normalized)
    cells_per_minute = estimated_new_cells / estimated_time
    max_cells_per_minute = 50  # Theoretical max (very efficient WOT pull)
    efficiency_score = min(cells_per_minute / max_cells_per_minute, 1.0)

    # Boost efficiency for high-priority tests
    if step.priority == 1:
        efficiency_score = min(efficiency_score * 1.3, 1.0)

    return expected_coverage_gain, efficiency_score


# =============================================================================
# Main Planner Function
# =============================================================================


def generate_test_plan(
    surfaces: Dict[str, Surface2D],
    cause_tree: Optional[CauseTreeResult] = None,
    mode_summary: Optional[Dict[str, int]] = None,
    test_environment: str = "both",  # "inertia_dyno", "street", "both"
    cumulative_coverage: Optional[float] = None,
) -> NextTestPlan:
    """
    Generate a prioritized next-test plan optimized for inertia dyno + street logging.

    The plan focuses on:
    1. Filling coverage gaps in high-impact regions
    2. Inertia dyno tests for high-MAP data (fast ramps, repeatable)
    3. Street tests for transients, cruise, idle, heat soak
    4. Investigating high-confidence hypotheses (minimal in v1)

    Args:
        surfaces: Dict of surface_id -> Surface2D
        cause_tree: Optional CauseTreeResult from cause tree analysis
        mode_summary: Optional mode distribution from mode detection
        test_environment: Which test environment to generate for
        cumulative_coverage: Optional cumulative coverage percentage across runs

    Returns:
        NextTestPlan with prioritized steps and efficiency scoring
    """
    all_steps: List[TestStep] = []
    coverage_gaps: List[CoverageGap] = []

    # Calculate current coverage for efficiency scoring
    if cumulative_coverage is None:
        # Estimate from current surfaces
        total_cells = sum(s.stats.total_cells for s in surfaces.values()
                          if s.stats)
        covered_cells = sum(s.stats.non_nan_cells for s in surfaces.values()
                            if s.stats)
        current_coverage = ((covered_cells / total_cells *
                             100) if total_cells > 0 else 0.0)
    else:
        current_coverage = cumulative_coverage

    # 1. Identify coverage gaps
    gaps = identify_coverage_gaps(surfaces)
    coverage_gaps = gaps

    # 2. Generate environment-specific tests
    if test_environment in ["inertia_dyno", "both"]:
        dyno_steps = generate_inertia_dyno_tests(gaps, mode_summary)
        all_steps.extend(dyno_steps)

    if test_environment in ["street", "both"]:
        street_steps = generate_street_tests(gaps, mode_summary)
        all_steps.extend(street_steps)

    # 3. Generate tests for hypotheses (minimal in v1 - only high-confidence)
    if cause_tree and cause_tree.hypotheses:
        # Only include top 2 hypotheses with confidence >= 0.7
        top_hyps = [h for h in cause_tree.hypotheses
                    if h.confidence >= 0.7][:2]
        if top_hyps:
            hyp_steps = _generate_hypothesis_tests(top_hyps)
            all_steps.extend(hyp_steps)

    # 4. Add general recommendations if data is very sparse
    if mode_summary:
        total_samples = sum(mode_summary.values())

        if total_samples < 500:
            all_steps.append(
                TestStep(
                    name="Increase Overall Data Volume",
                    goal="Improve statistical confidence with more samples",
                    test_type="general",
                    constraints="Log a complete session covering all operating conditions",
                    success_criteria="≥1000 total samples with good mode distribution",
                    priority=2,
                ))

    # Deduplicate similar steps
    seen_names = set()
    unique_steps = []
    for step in all_steps:
        if step.name not in seen_names:
            seen_names.add(step.name)
            unique_steps.append(step)

    # 5. Compute efficiency scores for all steps
    for step in unique_steps:
        gain, efficiency = score_test_efficiency(step, current_coverage)
        step.expected_coverage_gain = gain
        step.efficiency_score = efficiency

    # Sort by priority then efficiency
    unique_steps.sort(key=lambda s: (s.priority, -s.efficiency_score))

    # Build priority rationale
    high_pri_count = len([s for s in unique_steps if s.priority == 1])
    med_pri_count = len([s for s in unique_steps if s.priority == 2])

    rationale_parts = []
    if gaps:
        rationale_parts.append(f"{len(gaps)} coverage gaps identified")
    if high_pri_count > 0:
        rationale_parts.append(f"{high_pri_count} high-priority tests")
    if current_coverage < 70:
        rationale_parts.append(
            "Low overall coverage - prioritizing high-impact regions")

    priority_rationale = ("; ".join(rationale_parts) if rationale_parts else
                          "Standard coverage improvement plan")

    return NextTestPlan(
        steps=unique_steps,
        priority_rationale=priority_rationale,
        coverage_gaps=[g.description for g in gaps],
        coverage_gaps_detailed=gaps,
        total_estimated_pulls=len(
            [s for s in unique_steps if s.test_type == "wot_pull"]),
    )

    # Build rationale
    if not unique_steps:
        rationale = "Data coverage appears adequate. No specific tests recommended."
    else:
        high_priority_count = sum(1 for s in unique_steps if s.priority == 1)
        dyno_count = sum(1 for s in unique_steps if s.test_type == "wot_pull")
        street_count = sum(
            1 for s in unique_steps
            if s.test_type in ["transient_rolloff", "steady_state_sweep"])

        rationale = (
            f"{len(unique_steps)} test steps recommended. "
            f"{high_priority_count} high priority. "
            f"{len(gaps)} coverage gaps identified. "
            f"Dyno tests: {dyno_count}, Street tests: {street_count}.")

        if cause_tree and cause_tree.hypotheses:
            top_hyp = cause_tree.get_top_hypothesis()
            if top_hyp and top_hyp.confidence >= 0.7:
                rationale += f" Top hypothesis: {top_hyp.title}."

    # Estimate pulls
    total_pulls = sum(3 for s in unique_steps if s.test_type == "wot_pull")
    total_pulls += sum(
        1 for s in unique_steps
        if s.test_type in ["steady_state_sweep", "transient_rolloff"])

    return NextTestPlan(
        steps=unique_steps,
        priority_rationale=rationale,
        coverage_gaps=[g.description for g in coverage_gaps
                       ],  # Keep string list for backward compat
        coverage_gaps_detailed=coverage_gaps,
        total_estimated_pulls=total_pulls,
    )
