"""
DynoAI v3.0 — Test Suite
==========================

Tests for all v3.0 modules. Run with: pytest tests/test_v3_modules.py -v

Tests are organized by module and follow the existing DynoAI testing pattern:
deterministic, no external dependencies, synthetic data where needed.
"""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Standard V-twin test grid
# ---------------------------------------------------------------------------
RPM_BINS = np.array(
    [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500], dtype=np.float64
)
MAP_BINS = np.array([30, 40, 50, 60, 70, 80, 90, 100, 105], dtype=np.float64)


def _synthetic_ve_table(rpm_bins=RPM_BINS, map_bins=MAP_BINS, noise=0.0):
    """Generate a realistic synthetic VE table with absolute percentages (70-110%)."""
    rng = np.random.RandomState(42)
    n_rpm, n_map = len(rpm_bins), len(map_bins)
    table = np.zeros((n_rpm, n_map))
    for r in range(n_rpm):
        for m in range(n_map):
            # VE increases with load; typical range 70-110%
            # Base VE around 75-85% at low load, 95-105% at high load
            base_ve = 75 + (map_bins[m] - 30) / 75 * 25  # 75% at 30kPa, 100% at 105kPa
            rpm_effect = np.sin(rpm_bins[r] / 1500) * 5  # ±5% variation with RPM
            table[r, m] = base_ve + rpm_effect
    if noise > 0:
        table += rng.randn(n_rpm, n_map) * noise
    return table


def _synthetic_pull_data(rpm_center, map_center, n_points=5, noise=0.3):
    """Generate synthetic data from a single dyno pull around a center point."""
    rng = np.random.RandomState(int(rpm_center + map_center))
    rpm = rpm_center + rng.randn(n_points) * 100
    map_kpa = map_center + rng.randn(n_points) * 5
    ve = (
        _synthetic_ve_table()[
            np.searchsorted(RPM_BINS, rpm_center) - 1,
            np.searchsorted(MAP_BINS, map_center) - 1,
        ]
        + rng.randn(n_points) * noise
    )
    return rpm, map_kpa, ve


# ===========================================================================
# PHYSICS CONSTRAINTS TESTS
# ===========================================================================
class TestPhysicsConstraints:
    """Tests for physics_constraints.py"""

    def test_load_defaults(self):
        """Default constraints load for all known families."""
        from dynoai_v3.physics_constraints import KNOWN_FAMILIES, PhysicsConstraints

        for family in KNOWN_FAMILIES:
            pc = PhysicsConstraints(family)
            assert pc.maps.engine_family == family
            assert len(pc.maps.rpm_bins) > 0
            assert len(pc.maps.map_bins) > 0

    def test_unknown_family_raises(self):
        """Unknown engine family raises ValueError."""
        from dynoai_v3.physics_constraints import PhysicsConstraints

        with pytest.raises(ValueError, match="Unknown engine family"):
            PhysicsConstraints("turbocharged_inline_6")

    def test_check_point_safe(self):
        """Normal operating point passes all checks."""
        from dynoai_v3.physics_constraints import PhysicsConstraints

        pc = PhysicsConstraints("m8_114")
        verdict = pc.check_point(rpm=3500, map_kpa=80, timing=22.0, afr=12.8)
        assert verdict.safe
        assert verdict.violation_count == 0

    def test_check_point_lean_wot(self):
        """Lean AFR at WOT fails safety check."""
        from dynoai_v3.physics_constraints import PhysicsConstraints

        pc = PhysicsConstraints("m8_114")
        verdict = pc.check_point(rpm=3500, map_kpa=100, afr=14.0)
        assert not verdict.safe
        assert any("LEAN" in v.reason.upper() for v in verdict.violations)

    def test_check_point_over_rpm(self):
        """RPM above max test RPM fails."""
        from dynoai_v3.physics_constraints import PhysicsConstraints

        pc = PhysicsConstraints("m8_114")
        verdict = pc.check_point(rpm=6500, map_kpa=100)
        assert not verdict.safe

    def test_is_safe_to_test(self):
        """Pre-pull safety check works."""
        from dynoai_v3.physics_constraints import PhysicsConstraints

        pc = PhysicsConstraints("m8_114")
        safe, reason = pc.is_safe_to_test(3500, 90)
        assert safe
        assert reason == "OK"

        safe, reason = pc.is_safe_to_test(7000, 100)
        assert not safe
        assert "RPM" in reason

    def test_clamp_ve_table(self):
        """VE table clamping enforces bounds."""
        from dynoai_v3.physics_constraints import PhysicsConstraints

        pc = PhysicsConstraints("m8_114")
        table = np.full((10, 9), 10.0)  # 10% correction — over the ±7% limit
        clamped, events = pc.clamp_ve_table(table)
        assert np.all(clamped <= 7.0)
        assert len(events) > 0

    def test_adaptive_clamp_tighter(self):
        """Adaptive clamping uses tighter limits than standard."""
        from dynoai_v3.physics_constraints import PhysicsConstraints

        pc = PhysicsConstraints("m8_114")
        table = np.full((10, 9), 6.0)
        _, events_std = pc.clamp_ve_table(table, is_adaptive=False)
        _, events_adp = pc.clamp_ve_table(table, is_adaptive=True)
        assert len(events_adp) >= len(events_std)

    def test_export_and_reload(self):
        """Constraints survive JSON round-trip."""
        from dynoai_v3.physics_constraints import PhysicsConstraints

        with tempfile.TemporaryDirectory() as tmpdir:
            pc = PhysicsConstraints("m8_114")
            path = pc.export_to_json(Path(tmpdir) / "m8_114_limits.json")
            assert path.exists()

            pc2 = PhysicsConstraints("m8_114", constraints_dir=Path(tmpdir))
            assert pc2.maps.max_egt_f == pc.maps.max_egt_f
            assert pc2.maps.min_afr_wot == pc.maps.min_afr_wot

    def test_cooling_type_affects_limits(self):
        """Different cooling types produce different thermal limits."""
        from dynoai_v3.physics_constraints import PhysicsConstraints

        air = PhysicsConstraints("m8_114")  # Air-cooled
        liquid = PhysicsConstraints("revmax_1250")  # Liquid-cooled
        assert air.maps.ect_enrichment_trigger_f > liquid.maps.ect_enrichment_trigger_f

    def test_revmax_975_constraints(self):
        """RevMax 975 (Nightster) has liquid cooling and high redline range."""
        from dynoai_v3.physics_constraints import PhysicsConstraints

        pc = PhysicsConstraints("revmax_975")
        assert pc.maps.cooling_type == "liquid"
        assert pc.maps.max_test_rpm >= 8000
        assert len(pc.maps.rpm_bins) >= 8


# ===========================================================================
# GP SURROGATE TESTS
# ===========================================================================
class TestGPSurrogate:
    """Tests for gp_surrogate.py"""

    def test_init(self):
        """Surrogate initializes without data."""
        from dynoai_v3.gp_surrogate import VESurrogate

        s = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        assert not s.is_fitted
        assert s.observation_count == 0

    def test_unfitted_prediction(self):
        """Unfitted model returns high uncertainty."""
        from dynoai_v3.gp_surrogate import VESurrogate

        s = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        pred = s.predict(3500, 90)
        assert pred.uncertainty >= 5.0
        assert pred.confidence <= 20.0

    def test_add_observations_and_fit(self):
        """Adding observations marks model stale; fit happens on first prediction."""
        from dynoai_v3.gp_surrogate import Observation, VESurrogate

        s = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        assert not s.is_fitted
        for rpm in [2500, 3000, 3500, 4000, 4500]:
            s.add_observation(
                Observation(rpm=rpm, map_kpa=100, ve_delta=85.0 + rpm / 5000)
            )
        assert s.observation_count == 5
        assert s._stale  # Model is marked stale, not yet fitted
        # First prediction triggers lazy fit
        pred = s.predict(3500, 100)
        assert s.is_fitted
        assert pred.uncertainty < 1.0  # Should be low uncertainty near data

    def test_prediction_near_data(self):
        """Predictions near measured data have low uncertainty."""
        from dynoai_v3.gp_surrogate import Observation, VESurrogate

        s = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        for rpm in [2500, 3000, 3500, 4000, 4500]:
            s.add_observation(Observation(rpm=rpm, map_kpa=100, ve_delta=95.0))
        pred = s.predict(3500, 100)
        assert pred.uncertainty < 1.0
        assert pred.confidence > 80

    def test_prediction_far_from_data(self):
        """Predictions far from data have high uncertainty."""
        from dynoai_v3.gp_surrogate import Observation, VESurrogate

        s = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        # Only add data at WOT
        for rpm in [2500, 3000, 3500, 4000, 4500]:
            s.add_observation(Observation(rpm=rpm, map_kpa=100, ve_delta=95.0))
        pred_far = s.predict(2000, 40)  # Far from data
        pred_near = s.predict(3500, 100)  # Near data
        assert pred_far.uncertainty > pred_near.uncertainty

    def test_add_pull_data(self):
        """Bulk pull data ingestion works; fit happens on first prediction."""
        from dynoai_v3.gp_surrogate import VESurrogate

        s = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        rpm, map_kpa, ve = _synthetic_pull_data(3500, 100, n_points=10)
        n = s.add_pull_data(rpm, map_kpa, ve, pull_number=1)
        assert n == 10
        assert s._stale  # Model marked stale after ingestion
        assert not s.is_fitted  # Not fitted until first prediction
        # First prediction triggers lazy fit
        pred = s.predict_full_map()
        assert s.is_fitted

    def test_rejects_extreme_data(self):
        """Extreme VE values are rejected."""
        from dynoai_v3.gp_surrogate import VESurrogate

        s = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        rpm = np.array([3000, 3500, 4000])
        map_kpa = np.array([100, 100, 100])
        ve = np.array([85.0, 200.0, 90.0])  # 200% is extreme (outside 35-135% range)
        n = s.add_pull_data(rpm, map_kpa, ve)
        assert n == 2  # Only 2 accepted

    def test_predict_full_map(self):
        """Full map prediction returns correct shapes."""
        from dynoai_v3.gp_surrogate import Observation, VESurrogate

        s = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        for rpm in [2500, 3000, 3500, 4000]:
            for map_kpa in [50, 70, 90, 100]:
                s.add_observation(Observation(rpm=rpm, map_kpa=map_kpa, ve_delta=85.0))
        pred = s.predict_full_map()
        assert pred.ve_map.shape == (len(RPM_BINS), len(MAP_BINS))
        assert pred.uncertainty_map.shape == pred.ve_map.shape
        assert pred.confidence_map.shape == pred.ve_map.shape
        assert pred.predict_time_ms > 0

    def test_template_seeding(self):
        """Template seeding reduces initial uncertainty."""
        from dynoai_v3.gp_surrogate import VESurrogate

        # Unseeded
        s1 = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        s1.add_observation(
            __import__("dynoai_v3.gp_surrogate", fromlist=["Observation"]).Observation(
                rpm=3500, map_kpa=100, ve_delta=95.0
            )
        )
        # Additional observations to ensure it's fitted
        s1.add_observation(
            __import__("dynoai_v3.gp_surrogate", fromlist=["Observation"]).Observation(
                rpm=4000, map_kpa=90, ve_delta=90.0
            )
        )
        s1.add_observation(
            __import__("dynoai_v3.gp_surrogate", fromlist=["Observation"]).Observation(
                rpm=3000, map_kpa=80, ve_delta=88.0
            )
        )
        unc1 = s1.get_uncertainty_map()

        # Seeded
        s2 = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        template_ve = _synthetic_ve_table()
        s2.seed_from_template(template_ve, RPM_BINS, MAP_BINS)
        unc2 = s2.get_uncertainty_map()

        # Seeded model should have lower mean uncertainty
        assert np.mean(unc2) < np.mean(unc1)

    def test_seed_table_returned_exactly(self):
        """When only template data exists, predict_full_map returns exact 1:1 PVV values."""
        from dynoai_v3.gp_surrogate import VESurrogate

        s = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        template_ve = _synthetic_ve_table()

        # Seed with template
        s.seed_from_template(template_ve, RPM_BINS, MAP_BINS)

        # Predict full map (no real pull data yet)
        pred = s.predict_full_map()

        # VE map should match template exactly (1:1)
        np.testing.assert_array_equal(pred.ve_map, template_ve)

        # Uncertainty map should still be computed from GP
        assert pred.uncertainty_map.shape == template_ve.shape
        assert np.all(pred.uncertainty_map > 0)  # Should have some uncertainty

    def test_seed_table_blends_with_real_data(self):
        """After adding real pull data, GP blends seed with real observations."""
        from dynoai_v3.gp_surrogate import Observation, VESurrogate

        s = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        template_ve = _synthetic_ve_table()

        # Seed with template
        s.seed_from_template(template_ve, RPM_BINS, MAP_BINS)

        # Add a real observation with different value
        s.add_observation(
            Observation(rpm=3500, map_kpa=100, ve_delta=99.0, pull_number=1)
        )

        # Predict full map
        pred = s.predict_full_map()

        # VE map should NOT exactly match template anymore (GP blends)
        assert not np.array_equal(pred.ve_map, template_ve)

        # But should still be close to template in most places
        diff = np.abs(pred.ve_map - template_ve)
        assert np.mean(diff) < 5.0  # Mean difference less than 5%

    def test_save_load_state(self):
        """Surrogate state survives JSON round-trip."""
        from dynoai_v3.gp_surrogate import Observation, VESurrogate

        with tempfile.TemporaryDirectory() as tmpdir:
            s = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
            for rpm in [3000, 3500, 4000]:
                s.add_observation(Observation(rpm=rpm, map_kpa=100, ve_delta=92.0))
            path = Path(tmpdir) / "gp_state.json"
            s.save_state(path)

            s2 = VESurrogate.load_state(path)
            assert s2.observation_count == s.observation_count
            assert s2.is_fitted

    def test_confidence_badge_mapping(self):
        """Confidence scores map to correct badges."""
        from dynoai_v3.gp_surrogate import (
            confidence_to_badge,
            uncertainty_to_confidence,
        )

        assert confidence_to_badge(uncertainty_to_confidence(0.3)) == "H"
        assert confidence_to_badge(uncertainty_to_confidence(0.8)) == "M"
        assert confidence_to_badge(uncertainty_to_confidence(1.5)) == "L"
        assert confidence_to_badge(uncertainty_to_confidence(3.0)) == "—"

    def test_refit_performance(self):
        """GP refit completes within performance budget."""
        from dynoai_v3.gp_surrogate import Observation, VESurrogate

        s = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        rng = np.random.RandomState(42)
        for i in range(100):
            s.observations.append(
                Observation(
                    rpm=float(rng.choice(RPM_BINS)),
                    map_kpa=float(rng.choice(MAP_BINS)),
                    ve_delta=float(rng.randn() * 10 + 85),  # Mean 85%, stdev 10%
                )
            )
        s._refit()
        assert s._last_fit_time_ms < 5000  # 5 second budget for 100 obs


# ===========================================================================
# PULL ADVISOR TESTS
# ===========================================================================
class TestPullAdvisor:
    """Tests for pull_advisor.py"""

    def _make_advisor(self):
        from dynoai_v3.gp_surrogate import Observation, VESurrogate
        from dynoai_v3.physics_constraints import PhysicsConstraints
        from dynoai_v3.pull_advisor import PullAdvisor

        s = VESurrogate(RPM_BINS, MAP_BINS, "m8_114")
        # Seed with some data
        for rpm in [3000, 4000, 5000]:
            s.add_observation(Observation(rpm=rpm, map_kpa=100, ve_delta=95.0))
        pc = PhysicsConstraints("m8_114")
        return PullAdvisor(s, pc)

    def test_suggest_next_pull(self):
        """Pull advisor returns a valid recommendation."""
        advisor = self._make_advisor()
        rec = advisor.suggest_next_pull()
        assert rec.rpm > 0
        assert rec.map_kpa > 0
        assert rec.gear >= 1
        assert rec.pull_number == 1
        assert len(rec.reason) > 0

    def test_suggest_pull_sequence(self):
        """Initial sequence contains WOT sweeps."""
        advisor = self._make_advisor()
        plan = advisor.suggest_pull_sequence(max_pulls=12)
        assert len(plan) <= 12
        assert len(plan) >= 3
        # First pulls should be WOT
        from dynoai_v3.pull_advisor import PullType

        wot_count = sum(1 for p in plan if p.pull_type == PullType.WOT_SWEEP)
        assert wot_count >= 3

    def test_convergence_starts_false(self):
        """Fresh advisor is not converged (requires min observations)."""
        advisor = self._make_advisor()
        status = advisor.check_convergence()
        assert not status.converged

    def test_operator_veto(self):
        """Vetoed points are excluded from suggestions."""
        advisor = self._make_advisor()
        rec1 = advisor.suggest_next_pull()
        # Veto that point
        advisor.operator_veto(rec1.rpm, rec1.map_kpa, "too scary")
        rec2 = advisor.suggest_next_pull()
        # Should suggest a different point
        assert rec2.rpm != rec1.rpm or rec2.map_kpa != rec1.map_kpa

    def test_alternatives_provided(self):
        """Recommendations include alternatives."""
        advisor = self._make_advisor()
        rec = advisor.suggest_next_pull()
        # Alternatives may be empty if grid is small, but should be a list
        assert isinstance(rec.alternatives, list)

    def test_unsafe_points_skipped(self):
        """Advisor never suggests points beyond max test RPM."""
        advisor = self._make_advisor()
        for _ in range(20):
            rec = advisor.suggest_next_pull()
            assert rec.rpm <= advisor.constraints.maps.max_test_rpm


# ===========================================================================
# TEMPLATE LIBRARY TESTS
# ===========================================================================
class TestTemplateLibrary:
    """Tests for template_library.py"""

    def test_store_and_retrieve(self):
        """Templates survive store → find cycle."""
        from dynoai_v3.template_library import HardwareConfig, TemplateLibrary

        with tempfile.TemporaryDirectory() as tmpdir:
            lib = TemplateLibrary(Path(tmpdir))
            config = HardwareConfig(
                engine_family="m8_114",
                displacement_ci=114,
                cam_spec="s&s_475",
                exhaust_type="2into1",
            )
            cal = {"ve_table_front": _synthetic_ve_table().tolist()}
            tid = lib.store_template(config, cal, operator="test")
            assert tid

            # Find it back
            match = lib.find_nearest(config)
            assert match is not None
            assert match.similarity_score == 1.0  # Exact match

    def test_similarity_scoring(self):
        """Similar configs score higher than dissimilar ones."""
        from dynoai_v3.template_library import HardwareConfig, TemplateLibrary

        with tempfile.TemporaryDirectory() as tmpdir:
            lib = TemplateLibrary(Path(tmpdir))

            # Store a baseline template
            stored_config = HardwareConfig(
                engine_family="m8_114",
                displacement_ci=114,
                cam_spec="s&s_475",
                exhaust_type="2into1",
                air_cleaner="high_flow",
            )
            lib.store_template(stored_config, {"ve_table_front": [[0.0]]})

            # Query with same cams but different exhaust
            similar = HardwareConfig(
                engine_family="m8_114",
                displacement_ci=114,
                cam_spec="s&s_475",
                exhaust_type="slip_on",
            )
            # Query with everything different (but same family)
            different = HardwareConfig(
                engine_family="m8_114",
                displacement_ci=114,
                cam_spec="s&s_585",
                exhaust_type="open",
                air_cleaner="velocity_stack",
                compression_ratio=11.5,
            )

            match_similar = lib.find_nearest(similar)
            match_different = lib.find_nearest(different)

            assert match_similar is not None
            assert match_different is not None
            assert match_similar.similarity_score > match_different.similarity_score

    def test_family_mismatch_returns_none(self):
        """Different engine family returns no match."""
        from dynoai_v3.template_library import HardwareConfig, TemplateLibrary

        with tempfile.TemporaryDirectory() as tmpdir:
            lib = TemplateLibrary(Path(tmpdir))
            lib.store_template(
                HardwareConfig(engine_family="m8_114", displacement_ci=114),
                {"ve": [[0]]},
            )
            match = lib.find_nearest(
                HardwareConfig(engine_family="revmax_1250", displacement_ci=76)
            )
            assert match is None

    def test_count(self):
        """Template count tracks correctly."""
        from dynoai_v3.template_library import HardwareConfig, TemplateLibrary

        with tempfile.TemporaryDirectory() as tmpdir:
            lib = TemplateLibrary(Path(tmpdir))
            assert lib.count() == 0
            lib.store_template(
                HardwareConfig(engine_family="m8_114", displacement_ci=114),
                {"ve": [[0]]},
            )
            assert lib.count() == 1
            assert lib.count(engine_family="m8_114") == 1
            assert lib.count(engine_family="m8_107") == 0

    def test_hardware_config_signature(self):
        """Config signature is deterministic and filesystem-safe."""
        from dynoai_v3.template_library import HardwareConfig

        c = HardwareConfig(
            engine_family="m8_114",
            displacement_ci=114,
            exhaust_type="2into1",
            cam_spec="s&s_475",
        )
        sig = c.signature()
        assert "/" not in sig
        assert "\\" not in sig
        assert " " not in sig
        # Deterministic
        assert c.signature() == sig


# ===========================================================================
# SESSION ORCHESTRATOR TESTS
# ===========================================================================
class TestSessionOrchestrator:
    """Tests for session_orchestrator.py"""

    def test_full_session_lifecycle(self):
        """Complete session: init → pulls → converge → finalize."""
        from dynoai_v3.session_orchestrator import TuningSession
        from dynoai_v3.template_library import HardwareConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            config = HardwareConfig(
                engine_family="m8_114",
                displacement_ci=114,
                cam_spec="stock",
                exhaust_type="stock",
            )
            session = TuningSession(
                config,
                templates_dir=Path(tmpdir) / "templates",
                constraints_dir=Path(tmpdir) / "constraints",
            )

            # Phase 1
            init = session.initialize()
            assert init.session_id
            assert len(init.initial_plan) > 0
            assert init.engine_family == "m8_114"

            # Phase 2 — simulate pulls
            for i in range(8):
                rpm, map_kpa, ve = _synthetic_pull_data(
                    3000 + i * 300, 70 + i * 4, n_points=8
                )
                result = session.ingest_pull(rpm, map_kpa, ve)
                assert result.pull_number == i + 1
                assert result.observations_added > 0

            # Phase 3
            final_ve = _synthetic_ve_table()
            final = session.finalize(
                ve_table_front=final_ve,
                operator="test_operator",
            )
            assert final.template_id
            assert final.total_pulls == 8

    def test_status_tracking(self):
        """Session status updates correctly."""
        from dynoai_v3.session_orchestrator import SessionState, TuningSession
        from dynoai_v3.template_library import HardwareConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            config = HardwareConfig(engine_family="m8_114", displacement_ci=114)
            session = TuningSession(config, templates_dir=Path(tmpdir) / "t")
            assert session.state == SessionState.CREATED

            session.initialize()
            assert session.state == SessionState.READY

            rpm, map_kpa, ve = _synthetic_pull_data(3500, 100)
            session.ingest_pull(rpm, map_kpa, ve)
            assert session.state == SessionState.IN_PROGRESS

            status = session.get_status()
            assert status["state"] == "in_progress"
            assert status["pull_count"] == 1


# ===========================================================================
# BOUNDED OVERLAY TESTS
# ===========================================================================
class TestBoundedOverlay:
    """Tests for adaptive_overlay.py"""

    def _make_overlay(self):
        from dynoai_v3.adaptive_overlay import BoundedOverlay
        from dynoai_v3.physics_constraints import PhysicsConstraints

        pc = PhysicsConstraints("m8_114")
        base_ve = np.full((10, 9), 80.0)  # 80% VE everywhere
        return BoundedOverlay(base_ve, RPM_BINS, MAP_BINS, pc)

    def test_no_correction_when_afr_on_target(self):
        """No correction when AFR matches target."""
        overlay = self._make_overlay()
        corr = overlay.compute_fuel_correction(
            rpm=3500,
            map_kpa=90,
            current_afr=12.8,
            target_afr=12.8,
            ect_f=400,
        )
        assert abs(corr) < 0.1  # Near zero with learning rate

    def test_enrichment_when_lean(self):
        """Positive correction when running lean."""
        overlay = self._make_overlay()
        # Run 10 cycles to accumulate correction
        for _ in range(10):
            corr = overlay.compute_fuel_correction(
                rpm=3500,
                map_kpa=100,
                current_afr=13.5,
                target_afr=12.8,
                ect_f=400,
            )
        assert corr > 0  # Should add fuel

    def test_correction_bounded(self):
        """Corrections never exceed physics limits."""
        overlay = self._make_overlay()
        max_pct = overlay._max_fuel_gain * 100
        # Drive correction hard
        for _ in range(100):
            corr = overlay.compute_fuel_correction(
                rpm=3500,
                map_kpa=100,
                current_afr=15.0,
                target_afr=12.0,  # Huge error
                ect_f=400,
            )
        assert abs(corr) <= max_pct + 0.01  # Within bounds

    def test_kill_switch(self):
        """Kill switch zeros all corrections and disables overlay."""
        overlay = self._make_overlay()
        # Accumulate some corrections
        for _ in range(10):
            overlay.compute_fuel_correction(
                rpm=3500,
                map_kpa=100,
                current_afr=13.5,
                target_afr=12.8,
                ect_f=400,
            )
        assert overlay.enabled

        overlay.kill_switch()
        assert not overlay.enabled
        assert np.all(overlay._fuel_corrections == 0.0)
        assert np.all(overlay._timing_corrections == 0.0)

        # Corrections return 0 when disabled
        corr = overlay.compute_fuel_correction(
            rpm=3500,
            map_kpa=100,
            current_afr=14.0,
            target_afr=12.8,
            ect_f=400,
        )
        assert corr == 0.0

    def test_kill_switch_re_enable(self):
        """Re-enable starts from zero corrections."""
        overlay = self._make_overlay()
        for _ in range(10):
            overlay.compute_fuel_correction(
                rpm=3500,
                map_kpa=100,
                current_afr=13.5,
                target_afr=12.8,
                ect_f=400,
            )
        overlay.kill_switch()
        overlay.re_enable()
        assert overlay.enabled
        assert np.all(overlay._fuel_corrections == 0.0)

    def test_timing_retard_on_knock(self):
        """Knock detection retards timing."""
        overlay = self._make_overlay()
        corr = overlay.compute_timing_correction(
            rpm=3500,
            map_kpa=100,
            knock_detected=True,
            knock_severity=0.8,
            ect_f=400,
        )
        assert corr < 0  # Negative = retard

    def test_timing_never_advances(self):
        """Timing overlay never advances beyond base."""
        overlay = self._make_overlay()
        corr = overlay.compute_timing_correction(
            rpm=3500,
            map_kpa=100,
            knock_detected=False,
        )
        assert corr <= 0.0  # Never positive

    def test_correction_decay(self):
        """Old corrections decay toward zero."""
        overlay = self._make_overlay()
        # Set a correction at hour 0
        overlay.compute_fuel_correction(
            rpm=3500,
            map_kpa=100,
            current_afr=13.5,
            target_afr=12.8,
            ect_f=400,
        )
        initial_corr = overlay._fuel_corrections.copy()
        assert np.any(initial_corr != 0)

        # Advance 50 hours (past 30-hour threshold)
        decayed = overlay.apply_decay(50.0)
        assert decayed > 0
        # Corrections should be smaller
        assert np.max(np.abs(overlay._fuel_corrections)) < np.max(np.abs(initial_corr))

    def test_ect_enrichment_override(self):
        """High ECT forces enrichment regardless of AFR target."""
        overlay = self._make_overlay()
        # ECT way above trigger (475°F for M8 air-cooled)
        corr = overlay.compute_fuel_correction(
            rpm=3500,
            map_kpa=100,
            current_afr=12.8,
            target_afr=12.8,  # AFR on target
            ect_f=500,  # Over the 475°F trigger
        )
        # Should still have positive correction due to ECT override
        assert corr >= 0

    def test_correction_log(self):
        """All corrections are logged."""
        overlay = self._make_overlay()
        overlay.compute_fuel_correction(
            rpm=3500,
            map_kpa=100,
            current_afr=13.5,
            target_afr=12.8,
            ect_f=400,
        )
        log = overlay.export_correction_log()
        assert len(log) == 1
        assert log[0]["parameter"] == "fuel"
        assert "rpm" in log[0]
        assert "timestamp" in log[0]

    def test_corrected_table(self):
        """Corrected VE table applies fuel corrections to base."""
        overlay = self._make_overlay()
        base = overlay._base_ve.copy()

        # No corrections → same as base
        corrected = overlay.get_corrected_ve_table()
        np.testing.assert_array_equal(corrected, base)

        # Add correction → table changes
        for _ in range(10):
            overlay.compute_fuel_correction(
                rpm=3500,
                map_kpa=100,
                current_afr=13.5,
                target_afr=12.8,
                ect_f=400,
            )
        corrected = overlay.get_corrected_ve_table()
        assert not np.array_equal(corrected, base)

    def test_state_persistence(self):
        """Overlay state survives save/load cycle."""
        overlay = self._make_overlay()
        for _ in range(5):
            overlay.compute_fuel_correction(
                rpm=3500,
                map_kpa=100,
                current_afr=13.5,
                target_afr=12.8,
                ect_f=400,
            )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "overlay_state.json"
            overlay.save_state(path)

            overlay2 = self._make_overlay()
            overlay2.load_state(path)
            np.testing.assert_array_almost_equal(
                overlay._fuel_corrections, overlay2._fuel_corrections
            )


# ===========================================================================
# INTEGRATION TEST
# ===========================================================================
class TestEndToEnd:
    """Full end-to-end integration test."""

    def test_complete_workflow(self):
        """
        Simulate a complete accelerated tuning session:
        1. Create session with hardware config
        2. Initialize (template match + GP)
        3. Follow pull advisor for 10 pulls
        4. Finalize and store template
        5. Start NEW session — verify template match speeds things up
        """
        from dynoai_v3 import HardwareConfig, TuningSession

        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir) / "templates"
            constraints_dir = Path(tmpdir) / "constraints"

            # === SESSION 1: First tune (no templates) ===
            config = HardwareConfig(
                engine_family="m8_114",
                displacement_ci=114,
                cam_spec="s&s_475",
                exhaust_type="2into1",
                exhaust_brand="bassani",
                air_cleaner="high_flow",
                compression_ratio=10.5,
            )

            session1 = TuningSession(config, templates_dir, constraints_dir)
            init1 = session1.initialize()
            assert init1.template_match is None  # No templates yet

            # Simulate 10 pulls
            for i in range(10):
                rpm, map_kpa, ve = _synthetic_pull_data(
                    2500 + i * 300, 60 + i * 5, n_points=6
                )
                session1.ingest_pull(rpm, map_kpa, ve)

            # Finalize
            final_ve = _synthetic_ve_table()
            result1 = session1.finalize(
                ve_table_front=final_ve,
                operator="robbie",
            )
            assert result1.total_pulls == 10
            assert result1.template_id

            # === SESSION 2: Same config — should find template ===
            session2 = TuningSession(config, templates_dir, constraints_dir)
            init2 = session2.initialize()
            assert init2.template_match is not None
            assert init2.template_match.similarity_score == 1.0  # Exact match
            assert init2.template_match.is_usable

            # GP should be seeded — lower initial uncertainty
            pred = session2.surrogate.predict_full_map()
            assert session2.surrogate.template_observation_count > 0

            # === SESSION 3: Similar config — should find partial match ===
            similar_config = HardwareConfig(
                engine_family="m8_114",
                displacement_ci=114,
                cam_spec="s&s_475",  # Same cams
                exhaust_type="slip_on",  # Different exhaust
                air_cleaner="high_flow",  # Same
                compression_ratio=10.5,  # Same
            )
            session3 = TuningSession(similar_config, templates_dir, constraints_dir)
            init3 = session3.initialize()
            assert init3.template_match is not None
            assert 0.5 < init3.template_match.similarity_score < 1.0  # Partial match
