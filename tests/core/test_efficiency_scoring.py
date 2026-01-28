"""
Tests for Efficiency Scoring (Phase 7)

Validates test plan efficiency scoring algorithm.
"""

import pytest

from dynoai.core.next_test_planner import (
    TestStep,
    score_test_efficiency,
)


class TestEfficiencyScoring:
    """Tests for score_test_efficiency function."""

    def test_basic_scoring(self):
        """Test basic efficiency calculation."""
        step = TestStep(
            name="High-MAP Midrange Pull",
            goal="Fill high-load torque peak region",
            rpm_range=(2500, 4500),
            map_range=(80, 100),
            test_type="wot_pull",
            priority=1,
        )

        gain, efficiency = score_test_efficiency(step, current_coverage=50.0)

        assert isinstance(gain, float)
        assert isinstance(efficiency, float)
        assert gain >= 0
        assert gain <= 50  # Can't exceed remaining coverage
        assert 0 <= efficiency <= 1

    def test_wot_pull_multiplier(self):
        """Test WOT pull gets efficiency multiplier."""
        step_wot = TestStep(
            name="WOT Pull",
            goal="Sweep RPM range",
            rpm_range=(2000, 6000),
            map_range=(90, 100),
            test_type="wot_pull",
            priority=1,
        )

        step_steady = TestStep(
            name="Steady State",
            goal="Hold RPM/MAP",
            rpm_range=(2000, 6000),
            map_range=(90, 100),
            test_type="steady_state_sweep",
            priority=1,
        )

        gain_wot, eff_wot = score_test_efficiency(step_wot,
                                                  current_coverage=50.0)
        gain_steady, eff_steady = score_test_efficiency(step_steady,
                                                        current_coverage=50.0)

        # WOT should have higher gain due to multiplier
        assert gain_wot > gain_steady

    def test_priority_boost(self):
        """Test high priority boosts efficiency score."""
        step_high_pri = TestStep(
            name="Test 1",
            goal="High priority test",
            rpm_range=(2000, 4000),
            map_range=(80, 100),
            test_type="wot_pull",
            priority=1,
        )

        step_low_pri = TestStep(
            name="Test 2",
            goal="Low priority test",
            rpm_range=(2000, 4000),
            map_range=(80, 100),
            test_type="wot_pull",
            priority=3,
        )

        gain_high, eff_high = score_test_efficiency(step_high_pri,
                                                    current_coverage=50.0)
        gain_low, eff_low = score_test_efficiency(step_low_pri,
                                                  current_coverage=50.0)

        # High priority should have higher efficiency
        assert eff_high >= eff_low

    def test_coverage_gain_bounded(self):
        """Test coverage gain can't exceed remaining coverage."""
        step = TestStep(
            name="Large Test",
            goal="Cover many cells",
            rpm_range=(1000, 7000),
            map_range=(20, 100),
            test_type="wot_pull",
            priority=1,
        )

        # Already at 95% coverage
        gain, _ = score_test_efficiency(step, current_coverage=95.0)

        # Gain should be at most 5%
        assert gain <= 5.0

    def test_small_region_low_gain(self):
        """Test small regions have lower expected gain."""
        step_large = TestStep(
            name="Large Region",
            goal="Cover large area",
            rpm_range=(2000, 6000),
            map_range=(40, 100),
            test_type="wot_pull",
            priority=1,
        )

        step_small = TestStep(
            name="Small Region",
            goal="Cover small area",
            rpm_range=(3000, 3500),
            map_range=(85, 95),
            test_type="idle_hold",
            priority=1,
        )

        gain_large, _ = score_test_efficiency(step_large,
                                              current_coverage=50.0)
        gain_small, _ = score_test_efficiency(step_small,
                                              current_coverage=50.0)

        assert gain_large > gain_small

    def test_no_rpm_map_range(self):
        """Test handling of steps without explicit ranges."""
        step = TestStep(
            name="General Test",
            goal="General improvement",
            test_type="general",
            priority=2,
        )

        gain, efficiency = score_test_efficiency(step, current_coverage=50.0)

        # Should still return valid values
        assert gain >= 0
        assert 0 <= efficiency <= 1

    def test_test_type_multipliers(self):
        """Test different test types have appropriate multipliers."""
        base_rpm = (2000, 4000)
        base_map = (80, 100)

        types_to_test = [
            ("wot_pull", 1.5),
            ("steady_state_sweep", 1.2),
            ("transient_rolloff", 1.0),
            ("idle_hold", 0.5),
        ]

        results = []

        for test_type, expected_mult in types_to_test:
            step = TestStep(
                name=f"{test_type} Test",
                goal="Test",
                rpm_range=base_rpm,
                map_range=base_map,
                test_type=test_type,
                priority=2,
            )

            gain, _ = score_test_efficiency(step, current_coverage=50.0)
            results.append((test_type, gain))

        # WOT pull should have highest gain
        wot_gain = [g for t, g in results if t == "wot_pull"][0]
        idle_gain = [g for t, g in results if t == "idle_hold"][0]

        assert wot_gain > idle_gain

    def test_efficiency_normalized(self):
        """Test efficiency score is properly normalized to 0-1."""
        steps = [
            TestStep(
                name=f"Test {i}",
                goal="Test",
                rpm_range=(1000 + i * 1000, 2000 + i * 1000),
                map_range=(20 + i * 10, 30 + i * 10),
                test_type="wot_pull",
                priority=1,
            ) for i in range(5)
        ]

        for step in steps:
            _, efficiency = score_test_efficiency(step, current_coverage=50.0)
            assert 0 <= efficiency <= 1, (
                f"Efficiency {efficiency} out of bounds for {step.name}")

    def test_high_coverage_diminishing_returns(self):
        """Test that expected gains decrease as coverage increases."""
        step = TestStep(
            name="Test",
            goal="Test",
            rpm_range=(2000, 4000),
            map_range=(80, 100),
            test_type="wot_pull",
            priority=1,
        )

        gain_low, _ = score_test_efficiency(step, current_coverage=20.0)
        gain_med, _ = score_test_efficiency(step, current_coverage=50.0)
        gain_high, _ = score_test_efficiency(step, current_coverage=90.0)

        # Gains should be bounded by remaining coverage
        assert gain_low <= 80  # Max 80% remaining
        assert gain_med <= 50  # Max 50% remaining
        assert gain_high <= 10  # Max 10% remaining


class TestEfficiencyIntegration:
    """Integration tests with generate_test_plan."""

    def test_plan_includes_efficiency_scores(self):
        """Test that generated plans include efficiency scores."""
        from dynoai.core.next_test_planner import generate_test_plan
        from dynoai.core.surface_builder import Surface2D, SurfaceAxis, SurfaceStats

        # Create minimal surface with low coverage
        surface = Surface2D(
            surface_id="spark_f",
            title="Front Spark",
            description="Test",
            rpm_axis=SurfaceAxis(name="RPM",
                                 unit="rpm",
                                 bins=[1000, 2000, 3000, 4000]),
            map_axis=SurfaceAxis(name="MAP",
                                 unit="kPa",
                                 bins=[20, 40, 60, 80, 100]),
            values=[[25] * 5 for _ in range(4)],
            hit_count=[[2, 1, 0, 0, 0] for _ in range(4)],  # Low coverage
            stats=SurfaceStats(
                min=20.0,
                max=30.0,
                mean=25.0,
                non_nan_cells=8,
                total_cells=20,
            ),
        )

        plan = generate_test_plan(
            surfaces={"spark_f": surface},
            cumulative_coverage=40.0,
        )

        # Check that steps have efficiency fields
        assert len(plan.steps) > 0

        for step in plan.steps:
            assert hasattr(step, "expected_coverage_gain")
            assert hasattr(step, "efficiency_score")
            assert step.expected_coverage_gain >= 0
            assert 0 <= step.efficiency_score <= 1

    def test_steps_sorted_by_efficiency(self):
        """Test that steps are sorted by priority then efficiency."""
        from dynoai.core.next_test_planner import generate_test_plan
        from dynoai.core.surface_builder import Surface2D, SurfaceAxis, SurfaceStats

        surface = Surface2D(
            surface_id="spark_f",
            title="Front Spark",
            description="Test",
            rpm_axis=SurfaceAxis(name="RPM",
                                 unit="rpm",
                                 bins=[1000, 2000, 3000, 4000]),
            map_axis=SurfaceAxis(name="MAP",
                                 unit="kPa",
                                 bins=[20, 40, 60, 80, 100]),
            values=[[25] * 5 for _ in range(4)],
            hit_count=[[1, 0, 0, 0, 0] for _ in range(4)],
            stats=SurfaceStats(
                min=20.0,
                max=30.0,
                mean=25.0,
                non_nan_cells=4,
                total_cells=20,
            ),
        )

        plan = generate_test_plan(
            surfaces={"spark_f": surface},
            cumulative_coverage=20.0,
        )

        # Check sorting: priority ascending, then efficiency descending
        prev_priority = 0
        prev_efficiency = 1.0

        for step in plan.steps:
            if step.priority == prev_priority:
                # Within same priority, efficiency should be descending
                assert step.efficiency_score <= prev_efficiency
            elif step.priority > prev_priority:
                # Priority increased, reset efficiency comparison
                prev_efficiency = 1.0

            prev_priority = step.priority
            prev_efficiency = step.efficiency_score
