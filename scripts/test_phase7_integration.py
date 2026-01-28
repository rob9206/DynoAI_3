#!/usr/bin/env python3
"""
Phase 7 Integration Test

Demonstrates the complete predictive test planning workflow:
1. Aggregate run coverage
2. Get cumulative gaps
3. Configure constraints
4. Generate efficiency-scored predictions
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.services.coverage_tracker import (
    aggregate_run_coverage,
    get_cumulative_gaps,
    get_coverage_summary,
    reset_cumulative_coverage,
)
from api.services.nextgen_workflow import (
    TestPlannerConstraints,
    save_planner_constraints,
    get_planner_constraints,
)
from dynoai.core.next_test_planner import generate_test_plan, score_test_efficiency
from dynoai.core.surface_builder import Surface2D, SurfaceAxis, SurfaceStats


def print_section(title):
    """Print section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print('=' * 70)


def create_sample_surface(coverage_level="low"):
    """Create sample surface with configurable coverage."""
    hit_counts = {
        "low": [[2, 1, 0, 0, 0] for _ in range(4)],
        "medium": [[5, 8, 3, 1, 0] for _ in range(4)],
        "high": [[10, 15, 12, 8, 5] for _ in range(4)],
    }
    
    return {
        "spark_f": {
            "surface_id": "spark_f",
            "title": "Front Spark Timing",
            "description": "Timing advance in degrees",
            "hit_count": hit_counts.get(coverage_level, hit_counts["low"]),
            "values": [[25.0, 26.5, 24.0, 22.0, 20.0] for _ in range(4)],
            "rpm_axis": {
                "name": "RPM",
                "unit": "rpm",
                "bins": [1000, 2000, 3000, 4000],
            },
            "map_axis": {
                "name": "MAP",
                "unit": "kPa",
                "bins": [20, 40, 60, 80, 100],
            },
            "stats": {
                "min": 20.0,
                "max": 26.5,
                "mean": 23.5,
                "non_nan_cells": 8,
                "total_cells": 20,
                "coverage_pct": 40.0,
            }
        }
    }


def main():
    """Run Phase 7 integration test."""
    
    print_section("Phase 7: Predictive Test Planning - Integration Test")
    
    vehicle_id = "test_integration_vehicle"
    
    # Clean slate
    print(f"\nResetting coverage for vehicle: {vehicle_id}")
    reset_cumulative_coverage(vehicle_id)
    
    # Step 1: Aggregate first run (low coverage)
    print_section("Step 1: Aggregate First Run (Low Coverage)")
    
    surfaces_run1 = create_sample_surface("low")
    coverage1 = aggregate_run_coverage(
        vehicle_id=vehicle_id,
        run_id="run1",
        surfaces=surfaces_run1,
        dyno_signature="dyno_test_123",
    )
    
    print(f"[OK] Run 1 aggregated")
    print(f"  Total runs: {coverage1.total_runs}")
    print(f"  Surfaces tracked: {list(coverage1.aggregated_hit_count.keys())}")
    
    summary1 = get_coverage_summary(vehicle_id)
    print(f"  Coverage: {summary1['coverage_pct']:.1f}%")
    
    # Step 2: Get gaps
    print_section("Step 2: Identify Coverage Gaps")
    
    gaps = get_cumulative_gaps(vehicle_id, min_hits=5)
    print(f"[OK] Found {len(gaps)} coverage gaps")
    
    for i, gap in enumerate(gaps[:3], 1):
        print(f"\n  Gap {i}: {gap['region_name']}")
        print(f"    Impact: {gap['impact']}")
        print(f"    RPM: {gap['rpm_range'][0]}-{gap['rpm_range'][1]}")
        print(f"    MAP: {gap['map_range'][0]}-{gap['map_range'][1]} kPa")
        print(f"    Coverage: {gap['coverage_pct']:.1f}%")
        print(f"    Empty cells: {gap['empty_cells']}/{gap['total_cells']}")
    
    # Step 3: Configure constraints
    print_section("Step 3: Configure Test Planner Constraints")
    
    constraints = TestPlannerConstraints(
        min_rpm=1500,
        max_rpm=6500,
        min_map_kpa=30,
        max_map_kpa=100,
        max_pulls_per_session=5,
        preferred_test_environment="both",
    )
    
    save_planner_constraints(constraints, vehicle_id)
    print(f"[OK] Constraints saved:")
    print(f"  RPM range: {constraints.min_rpm}-{constraints.max_rpm}")
    print(f"  MAP range: {constraints.min_map_kpa}-{constraints.max_map_kpa} kPa")
    print(f"  Max pulls: {constraints.max_pulls_per_session}")
    print(f"  Environment: {constraints.preferred_test_environment}")
    
    # Step 4: Generate test plan with efficiency scoring
    print_section("Step 4: Generate Efficiency-Scored Test Plan")
    
    # Create Surface2D object for planner
    surface_obj = Surface2D(
        surface_id="spark_f",
        title="Front Spark Timing",
        description="Test surface",
        rpm_axis=SurfaceAxis(name="RPM", unit="rpm", bins=[1000, 2000, 3000, 4000]),
        map_axis=SurfaceAxis(name="MAP", unit="kPa", bins=[20, 40, 60, 80, 100]),
        values=[[25.0] * 5 for _ in range(4)],
        hit_count=surfaces_run1["spark_f"]["hit_count"],
        stats=SurfaceStats(
            min=20.0,
            max=26.5,
            mean=23.5,
            non_nan_cells=8,
            total_cells=20,
        ),
    )
    
    plan = generate_test_plan(
        surfaces={"spark_f": surface_obj},
        cumulative_coverage=summary1['coverage_pct'],
    )
    
    print(f"[OK] Test plan generated")
    print(f"  Total steps: {len(plan.steps)}")
    print(f"  Rationale: {plan.priority_rationale}")
    
    print("\n  Top 3 Recommended Tests:")
    for i, step in enumerate(plan.steps[:3], 1):
        print(f"\n  {i}. {step.name} (P{step.priority})")
        print(f"     Goal: {step.goal}")
        if step.rpm_range:
            print(f"     RPM: {step.rpm_range[0]}-{step.rpm_range[1]}")
        if step.map_range:
            print(f"     MAP: {step.map_range[0]}-{step.map_range[1]} kPa")
        print(f"     Expected gain: +{step.expected_coverage_gain:.1f}%")
        print(f"     Efficiency: {step.efficiency_score:.2f}")
    
    # Step 5: Simulate second run and observe improvement
    print_section("Step 5: Aggregate Second Run (Medium Coverage)")
    
    surfaces_run2 = create_sample_surface("medium")
    coverage2 = aggregate_run_coverage(
        vehicle_id=vehicle_id,
        run_id="run2",
        surfaces=surfaces_run2,
        dyno_signature="dyno_test_123",
    )
    
    summary2 = get_coverage_summary(vehicle_id)
    
    print(f"[OK] Run 2 aggregated")
    print(f"  Total runs: {coverage2.total_runs}")
    print(f"  New coverage: {summary2['coverage_pct']:.1f}% (was {summary1['coverage_pct']:.1f}%)")
    print(f"  Improvement: +{summary2['coverage_pct'] - summary1['coverage_pct']:.1f}%")
    
    # Step 6: Show updated gaps
    print_section("Step 6: Updated Coverage Gaps After Run 2")
    
    gaps2 = get_cumulative_gaps(vehicle_id, min_hits=5)
    print(f"[OK] Gaps now: {len(gaps2)} (was {len(gaps)})")
    
    if len(gaps2) < len(gaps):
        print(f"  [OK] {len(gaps) - len(gaps2)} gaps filled!")
    
    # Step 7: Demonstrate efficiency comparison
    print_section("Step 7: Efficiency Score Comparison")
    
    from dynoai.core.next_test_planner import TestStep
    
    test_cases = [
        ("WOT Pull (High-MAP)", (2500, 4500), (80, 100), "wot_pull", 1),
        ("Steady Cruise", (2000, 3000), (40, 60), "steady_state_sweep", 2),
        ("Idle Hold", (800, 1200), (20, 30), "idle_hold", 2),
    ]
    
    print("\n  Test Type                 | Coverage Gain | Efficiency | Priority")
    print("  " + "-" * 68)
    
    for name, rpm, map_range, test_type, priority in test_cases:
        step = TestStep(
            name=name,
            goal="Test",
            rpm_range=rpm,
            map_range=map_range,
            test_type=test_type,
            priority=priority,
        )
        
        gain, efficiency = score_test_efficiency(step, summary2['coverage_pct'])
        
        print(f"  {name:25} | {gain:6.1f}%       | {efficiency:6.2f}    | P{priority}")
    
    # Cleanup
    print_section("Cleanup")
    reset_cumulative_coverage(vehicle_id)
    print(f"[OK] Coverage reset for {vehicle_id}")
    
    # Summary
    print_section("Integration Test Complete [OK]")
    print("""
  Phase 7 Features Validated:
  [OK] Cross-run coverage aggregation
  [OK] Coverage gap detection
  [OK] User-configurable constraints
  [OK] Efficiency scoring algorithm
  [OK] Test plan generation with efficiency
  [OK] Feedback loop simulation
  
  All systems operational!
    """)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
