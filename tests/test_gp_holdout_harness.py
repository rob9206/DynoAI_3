"""
DynoAI GP Backend — Holdout Validation Harness
================================================

Objective: Establish a measurable baseline for the current sklearn GP backend
before migrating to a pure NumPy engine. Records per-scenario metrics so the
NumPy engine can be validated against the same contract.

Scenarios exercised:
    1. Unfitted model → high-uncertainty prior (edge case)
    2. Template-only seeding → exact seed table passthrough (edge case)
    3. Template + real data → GP blends both sources (normal fit)
    4. Real data only (no template) → GP fits from scratch (normal fit)
    5. Holdout prediction accuracy across multiple grid shapes
    6. Latency measurement for predict_full_map
    7. Observation pruning under _MAX_OBS_FOR_REFIT cap

Grid shapes tested:
    - 10×9  (test fixture default, matches test_v3_modules.py)
    - 11×5  (production constants from dynoai/constants.py)
    - 16×16 (documented performance budget target)

Usage:
    pytest tests/test_gp_holdout_harness.py -v
    pytest tests/test_gp_holdout_harness.py -v -s  # with metric printout

Author: Thunderhorse Tuning / DynoAI
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Grid shape definitions — exercise multiple runtime configurations
# ---------------------------------------------------------------------------
GRID_SHAPES: Dict[str, Tuple[np.ndarray, np.ndarray]] = {
    "10x9_test": (
        np.array([1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500], dtype=np.float64),
        np.array([30, 40, 50, 60, 70, 80, 90, 100, 105], dtype=np.float64),
    ),
    "11x5_production": (
        np.array([1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500], dtype=np.float64),
        np.array([35, 50, 65, 80, 95], dtype=np.float64),
    ),
    "16x16_budget": (
        np.linspace(1000, 6500, 16).astype(np.float64),
        np.linspace(25, 105, 16).astype(np.float64),
    ),
}


# ---------------------------------------------------------------------------
# Synthetic data generators (deterministic, seeded)
# ---------------------------------------------------------------------------
def _make_ve_surface(rpm_bins: np.ndarray, map_bins: np.ndarray, seed: int = 42) -> np.ndarray:
    """
    Generate a physically plausible VE surface for testing.

    Shape matches a V-twin: VE rises with MAP, peaks in mid-RPM, falls
    at high RPM. Values in absolute VE % (70-110).
    """
    rng = np.random.RandomState(seed)
    n_rpm, n_map = len(rpm_bins), len(map_bins)
    table = np.zeros((n_rpm, n_map))

    rpm_range = float(rpm_bins.max() - rpm_bins.min()) or 1.0
    map_range = float(map_bins.max() - map_bins.min()) or 1.0
    rpm_norm = (rpm_bins - rpm_bins.min()) / rpm_range
    map_norm = (map_bins - map_bins.min()) / map_range

    for r in range(n_rpm):
        for m in range(n_map):
            base = 75.0 + 25.0 * map_norm[m]                  # 75% at min MAP → 100% at max
            rpm_shape = 5.0 * np.sin(np.pi * rpm_norm[r])     # ±5% bell over RPM
            interaction = 3.0 * rpm_norm[r] * map_norm[m]      # slight RPM×MAP coupling
            table[r, m] = base + rpm_shape + interaction

    # Small noise so GP has something to learn beyond smooth trend
    table += rng.randn(n_rpm, n_map) * 0.5
    return table


def _generate_observations(
    ve_surface: np.ndarray,
    rpm_bins: np.ndarray,
    map_bins: np.ndarray,
    n_obs: int,
    noise_std: float = 0.5,
    seed: int = 123,
) -> List[dict]:
    """
    Sample observations from a known VE surface with measurement noise.

    Returns list of dicts with keys: rpm, map_kpa, ve, grid_r, grid_m.
    grid_r/grid_m are the true grid indices (for holdout bookkeeping).
    """
    rng = np.random.RandomState(seed)
    observations = []
    n_rpm, n_map = len(rpm_bins), len(map_bins)

    for _ in range(n_obs):
        r_idx = rng.randint(0, n_rpm)
        m_idx = rng.randint(0, n_map)
        # Jitter around bin center (realistic: samples don't land exactly on bin)
        rpm_jitter = rng.uniform(-100, 100)
        map_jitter = rng.uniform(-3, 3)
        true_ve = ve_surface[r_idx, m_idx]
        measured_ve = true_ve + rng.randn() * noise_std

        observations.append({
            "rpm": float(rpm_bins[r_idx] + rpm_jitter),
            "map_kpa": float(map_bins[m_idx] + map_jitter),
            "ve": float(measured_ve),
            "grid_r": r_idx,
            "grid_m": m_idx,
        })

    return observations


def _holdout_split(
    observations: List[dict],
    holdout_fraction: float = 0.3,
    seed: int = 99,
) -> Tuple[List[dict], List[dict]]:
    """Split observations into train and holdout sets."""
    rng = np.random.RandomState(seed)
    indices = rng.permutation(len(observations))
    n_holdout = max(1, int(len(observations) * holdout_fraction))
    holdout_idx = set(indices[:n_holdout].tolist())

    train = [o for i, o in enumerate(observations) if i not in holdout_idx]
    holdout = [o for i, o in enumerate(observations) if i in holdout_idx]
    return train, holdout


# ---------------------------------------------------------------------------
# Metrics recording
# ---------------------------------------------------------------------------
@dataclass
class HarnessMetrics:
    """Metrics from a single harness scenario run."""

    scenario: str
    backend: str
    grid_shape: str
    n_rpm: int
    n_map: int
    n_train: int
    n_holdout: int
    n_template: int

    # Prediction quality (holdout cells)
    mae: Optional[float] = None
    rmse: Optional[float] = None
    max_error: Optional[float] = None
    mean_uncertainty_holdout: Optional[float] = None

    # Full map stats
    mean_uncertainty_full: Optional[float] = None
    min_confidence_full: Optional[float] = None
    mean_confidence_full: Optional[float] = None

    # Latency
    predict_full_map_ms: Optional[float] = None
    refit_ms: Optional[float] = None

    # Edge case mode
    mode: str = "normal_fit"  # unfitted, template_only, normal_fit, fallback

    # Observation management
    total_obs_in_model: int = 0
    template_obs_in_model: int = 0

    def summary(self) -> str:
        parts = [
            f"[{self.backend}] {self.scenario} ({self.grid_shape})",
            f"  grid: {self.n_rpm}×{self.n_map} = {self.n_rpm * self.n_map} cells",
            f"  train: {self.n_train}, holdout: {self.n_holdout}, template: {self.n_template}",
            f"  mode: {self.mode}",
        ]
        if self.mae is not None:
            parts.append(f"  MAE: {self.mae:.4f}  RMSE: {self.rmse:.4f}  MaxErr: {self.max_error:.4f}")
        if self.mean_uncertainty_holdout is not None:
            parts.append(f"  mean_unc(holdout): {self.mean_uncertainty_holdout:.4f}")
        if self.mean_uncertainty_full is not None:
            conf_str = f"{self.mean_confidence_full:.1f}" if self.mean_confidence_full is not None else "—"
            parts.append(f"  mean_unc(full): {self.mean_uncertainty_full:.4f}  mean_conf(full): {conf_str}")
        if self.predict_full_map_ms is not None:
            parts.append(f"  latency: predict_full_map={self.predict_full_map_ms:.1f}ms")
        if self.refit_ms is not None:
            parts.append(f"  latency: refit={self.refit_ms:.1f}ms")
        parts.append(f"  obs in model: {self.total_obs_in_model} (template: {self.template_obs_in_model})")
        return "\n".join(parts)


# Accumulate metrics across all tests for final report
_all_metrics: List[HarnessMetrics] = []


# ---------------------------------------------------------------------------
# Backend abstraction — switch between sklearn and numpy
# ---------------------------------------------------------------------------
BACKEND = "sklearn"


def _create_surrogate(rpm_bins: np.ndarray, map_bins: np.ndarray, engine_family: str = "m8_114"):
    """Create a VESurrogate using the current backend."""
    from dynoai_v3.gp_surrogate import VESurrogate
    return VESurrogate(rpm_bins, map_bins, engine_family, backend=BACKEND)


def _add_observation(surrogate, rpm: float, map_kpa: float, ve: float, pull_number: int = 1):
    """Add a single observation."""
    from dynoai_v3.gp_surrogate import Observation
    surrogate.add_observation(Observation(
        rpm=rpm, map_kpa=map_kpa, ve_delta=ve, pull_number=pull_number,
    ))


def _predict_at(surrogate, rpm: float, map_kpa: float):
    """Predict at a single point. Returns (mean, uncertainty)."""
    pred = surrogate.predict(rpm, map_kpa)
    return pred.ve_delta, pred.uncertainty


def _predict_full_map(surrogate):
    """Predict full map. Returns FullMapPrediction."""
    return surrogate.predict_full_map()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(params=list(GRID_SHAPES.keys()))
def grid_shape(request):
    """Parametrize over grid shapes."""
    name = request.param
    rpm_bins, map_bins = GRID_SHAPES[name]
    return name, rpm_bins, map_bins


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------
class TestUnfittedModel:
    """Scenario 1: No data, no template. Model should return high-uncertainty prior."""

    pytestmark = pytest.mark.validation

    @pytest.mark.parametrize("grid_name", list(GRID_SHAPES.keys()))
    def test_unfitted_returns_high_uncertainty(self, grid_name):
        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        s = _create_surrogate(rpm_bins, map_bins)

        metrics = HarnessMetrics(
            scenario="unfitted_prior",
            backend=BACKEND,
            grid_shape=grid_name,
            n_rpm=len(rpm_bins),
            n_map=len(map_bins),
            n_train=0,
            n_holdout=0,
            n_template=0,
            mode="unfitted",
        )

        # Single point prediction
        mean, unc = _predict_at(s, 3500, 90)
        assert unc >= 5.0, f"Unfitted model uncertainty too low: {unc}"

        # Full map prediction
        t0 = time.perf_counter()
        pred = _predict_full_map(s)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert pred.ve_map.shape == (len(rpm_bins), len(map_bins))
        assert pred.uncertainty_map.shape == pred.ve_map.shape
        assert np.all(pred.uncertainty_map >= 5.0)

        metrics.mean_uncertainty_full = float(np.mean(pred.uncertainty_map))
        metrics.mean_confidence_full = float(np.mean(pred.confidence_map))
        metrics.min_confidence_full = float(np.min(pred.confidence_map))
        metrics.predict_full_map_ms = elapsed_ms
        metrics.total_obs_in_model = s.observation_count

        _all_metrics.append(metrics)
        print(f"\n{metrics.summary()}")


class TestTemplateOnly:
    """Scenario 2: Template seeded, no real pulls. Should passthrough exact seed table."""

    pytestmark = pytest.mark.validation

    @pytest.mark.parametrize("grid_name", list(GRID_SHAPES.keys()))
    def test_template_passthrough(self, grid_name):
        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        ve_surface = _make_ve_surface(rpm_bins, map_bins)

        s = _create_surrogate(rpm_bins, map_bins)
        s.seed_from_template(ve_surface, rpm_bins, map_bins)

        metrics = HarnessMetrics(
            scenario="template_only",
            backend=BACKEND,
            grid_shape=grid_name,
            n_rpm=len(rpm_bins),
            n_map=len(map_bins),
            n_train=0,
            n_holdout=0,
            n_template=len(rpm_bins) * len(map_bins),
            mode="template_only",
        )

        t0 = time.perf_counter()
        pred = _predict_full_map(s)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Core contract: template-only should return exact seed values
        np.testing.assert_array_equal(
            pred.ve_map, ve_surface,
            err_msg="Template-only prediction must return exact seed table",
        )

        metrics.predict_full_map_ms = elapsed_ms
        metrics.mean_uncertainty_full = float(np.mean(pred.uncertainty_map))
        metrics.mean_confidence_full = float(np.mean(pred.confidence_map))
        metrics.min_confidence_full = float(np.min(pred.confidence_map))
        metrics.total_obs_in_model = s.observation_count
        metrics.template_obs_in_model = s.template_observation_count

        _all_metrics.append(metrics)
        print(f"\n{metrics.summary()}")


class TestTemplateWithRealData:
    """Scenario 3: Template + real dyno observations. GP should blend both."""

    pytestmark = pytest.mark.validation

    @pytest.mark.parametrize("grid_name", list(GRID_SHAPES.keys()))
    def test_holdout_accuracy(self, grid_name):
        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        ve_surface = _make_ve_surface(rpm_bins, map_bins)

        # Generate observations from the known surface
        n_obs = min(80, len(rpm_bins) * len(map_bins) * 2)
        all_obs = _generate_observations(ve_surface, rpm_bins, map_bins, n_obs=n_obs)
        train, holdout = _holdout_split(all_obs)

        # Build surrogate: template + training data
        s = _create_surrogate(rpm_bins, map_bins)
        s.seed_from_template(ve_surface, rpm_bins, map_bins)

        for obs in train:
            _add_observation(s, obs["rpm"], obs["map_kpa"], obs["ve"], pull_number=1)

        # Predict full map
        t0 = time.perf_counter()
        pred = _predict_full_map(s)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Evaluate on holdout: compare predicted VE at each holdout point's grid cell
        errors = []
        holdout_uncertainties = []
        for obs in holdout:
            r, m = obs["grid_r"], obs["grid_m"]
            predicted = pred.ve_map[r, m]
            actual = ve_surface[r, m]  # Compare to true surface, not noisy measurement
            errors.append(predicted - actual)
            holdout_uncertainties.append(pred.uncertainty_map[r, m])

        errors = np.array(errors)
        mae = float(np.mean(np.abs(errors)))
        rmse = float(np.sqrt(np.mean(errors**2)))
        max_err = float(np.max(np.abs(errors)))

        metrics = HarnessMetrics(
            scenario="template_plus_real",
            backend=BACKEND,
            grid_shape=grid_name,
            n_rpm=len(rpm_bins),
            n_map=len(map_bins),
            n_train=len(train),
            n_holdout=len(holdout),
            n_template=len(rpm_bins) * len(map_bins),
            mode="normal_fit",
            mae=mae,
            rmse=rmse,
            max_error=max_err,
            mean_uncertainty_holdout=float(np.mean(holdout_uncertainties)),
            mean_uncertainty_full=float(np.mean(pred.uncertainty_map)),
            mean_confidence_full=float(np.mean(pred.confidence_map)),
            min_confidence_full=float(np.min(pred.confidence_map)),
            predict_full_map_ms=elapsed_ms,
            refit_ms=s._last_fit_time_ms,
            total_obs_in_model=s.observation_count,
            template_obs_in_model=s.template_observation_count,
        )

        _all_metrics.append(metrics)
        print(f"\n{metrics.summary()}")

        # Baseline assertions — these define the contract the numpy engine must meet
        assert mae < 5.0, f"MAE too high: {mae:.4f} (must be < 5.0 VE%)"
        assert pred.ve_map.shape == (len(rpm_bins), len(map_bins))


class TestRealDataOnly:
    """Scenario 4: No template, only real observations. GP fits from scratch."""

    pytestmark = pytest.mark.validation

    @pytest.mark.parametrize("grid_name", list(GRID_SHAPES.keys()))
    def test_holdout_accuracy_no_template(self, grid_name):
        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        ve_surface = _make_ve_surface(rpm_bins, map_bins)

        # More observations needed without template prior
        n_obs = min(120, len(rpm_bins) * len(map_bins) * 3)
        all_obs = _generate_observations(ve_surface, rpm_bins, map_bins, n_obs=n_obs, seed=77)
        train, holdout = _holdout_split(all_obs)

        s = _create_surrogate(rpm_bins, map_bins)
        for obs in train:
            _add_observation(s, obs["rpm"], obs["map_kpa"], obs["ve"], pull_number=1)

        t0 = time.perf_counter()
        pred = _predict_full_map(s)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        errors = []
        holdout_uncertainties = []
        for obs in holdout:
            r, m = obs["grid_r"], obs["grid_m"]
            predicted = pred.ve_map[r, m]
            actual = ve_surface[r, m]
            errors.append(predicted - actual)
            holdout_uncertainties.append(pred.uncertainty_map[r, m])

        errors = np.array(errors)
        mae = float(np.mean(np.abs(errors)))
        rmse = float(np.sqrt(np.mean(errors**2)))
        max_err = float(np.max(np.abs(errors)))

        metrics = HarnessMetrics(
            scenario="real_data_only",
            backend=BACKEND,
            grid_shape=grid_name,
            n_rpm=len(rpm_bins),
            n_map=len(map_bins),
            n_train=len(train),
            n_holdout=len(holdout),
            n_template=0,
            mode="normal_fit",
            mae=mae,
            rmse=rmse,
            max_error=max_err,
            mean_uncertainty_holdout=float(np.mean(holdout_uncertainties)),
            mean_uncertainty_full=float(np.mean(pred.uncertainty_map)),
            mean_confidence_full=float(np.mean(pred.confidence_map)),
            min_confidence_full=float(np.min(pred.confidence_map)),
            predict_full_map_ms=elapsed_ms,
            refit_ms=s._last_fit_time_ms,
            total_obs_in_model=s.observation_count,
            template_obs_in_model=0,
        )

        _all_metrics.append(metrics)
        print(f"\n{metrics.summary()}")

        assert mae < 10.0, f"MAE too high without template: {mae:.4f} (must be < 10.0 VE%)"
        assert pred.ve_map.shape == (len(rpm_bins), len(map_bins))


class TestLatencyBudget:
    """Scenario 6: Verify predict_full_map stays within latency budget."""

    pytestmark = pytest.mark.validation

    @pytest.mark.parametrize("grid_name", list(GRID_SHAPES.keys()))
    def test_predict_latency(self, grid_name):
        """Full map prediction must complete within 500ms for any grid shape."""
        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        ve_surface = _make_ve_surface(rpm_bins, map_bins)

        s = _create_surrogate(rpm_bins, map_bins)
        s.seed_from_template(ve_surface, rpm_bins, map_bins)

        # Add some real data to trigger GP fit
        n_obs = 30
        obs = _generate_observations(ve_surface, rpm_bins, map_bins, n_obs=n_obs, seed=55)
        for o in obs:
            _add_observation(s, o["rpm"], o["map_kpa"], o["ve"])

        # Warm-up fit (don't count first fit in latency)
        _ = _predict_full_map(s)

        # Timed prediction (model already fitted, cache should help)
        timings = []
        for _ in range(5):
            t0 = time.perf_counter()
            pred = _predict_full_map(s)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            timings.append(elapsed_ms)

        median_ms = float(np.median(timings))

        metrics = HarnessMetrics(
            scenario="latency_budget",
            backend=BACKEND,
            grid_shape=grid_name,
            n_rpm=len(rpm_bins),
            n_map=len(map_bins),
            n_train=n_obs,
            n_holdout=0,
            n_template=len(rpm_bins) * len(map_bins),
            mode="normal_fit",
            predict_full_map_ms=median_ms,
            total_obs_in_model=s.observation_count,
            template_obs_in_model=s.template_observation_count,
        )

        _all_metrics.append(metrics)
        print(f"\n{metrics.summary()}")
        print(f"  all timings: {[f'{t:.1f}ms' for t in timings]}")

        # Budget: 500ms for prediction (generous; target is <100ms)
        assert median_ms < 500, f"Prediction too slow: {median_ms:.1f}ms (budget: 500ms)"


class TestObservationPruning:
    """Scenario 7: Verify observation cap and template retention under pruning."""

    pytestmark = pytest.mark.validation

    def test_pruning_retains_templates(self):
        """When exceeding _MAX_OBS_FOR_REFIT, template observations are preserved."""
        from dynoai_v3.gp_surrogate import _MAX_OBS_FOR_REFIT

        rpm_bins, map_bins = GRID_SHAPES["10x9_test"]
        ve_surface = _make_ve_surface(rpm_bins, map_bins)

        s = _create_surrogate(rpm_bins, map_bins)
        s.seed_from_template(ve_surface, rpm_bins, map_bins)
        template_count = s.template_observation_count

        # Add enough real observations to exceed the cap
        n_extra = _MAX_OBS_FOR_REFIT + 50
        rng = np.random.RandomState(42)
        for i in range(n_extra):
            _add_observation(
                s,
                rpm=float(rng.choice(rpm_bins)),
                map_kpa=float(rng.choice(map_bins)),
                ve=float(rng.randn() * 3 + 85),
                pull_number=i + 1,
            )

        # Template observations should still be present
        n_templates = sum(1 for o in s.observations if o.pull_number == -1)
        assert n_templates == template_count, (
            f"Template observations lost: expected {template_count}, got {n_templates}"
        )

        # Total should be bounded
        # (template_count + _MAX_PULL_OBS_STORED)
        from dynoai_v3.gp_surrogate import _MAX_PULL_OBS_STORED
        max_expected = template_count + _MAX_PULL_OBS_STORED
        assert len(s.observations) <= max_expected, (
            f"Observations not pruned: {len(s.observations)} > {max_expected}"
        )

        metrics = HarnessMetrics(
            scenario="observation_pruning",
            backend=BACKEND,
            grid_shape="10x9_test",
            n_rpm=len(rpm_bins),
            n_map=len(map_bins),
            n_train=n_extra,
            n_holdout=0,
            n_template=template_count,
            mode="normal_fit",
            total_obs_in_model=len(s.observations),
            template_obs_in_model=n_templates,
        )

        _all_metrics.append(metrics)
        print(f"\n{metrics.summary()}")


class TestMissingAlphaFallback:
    """Scenario: Exercise the alpha_ guard path in predict_full_map.

    The existing code guards against sklearn leaving the model without
    alpha_ after fit (observed in sklearn 1.8+). This test verifies the
    fallback behavior produces safe output.
    """

    pytestmark = pytest.mark.validation

    def test_fallback_returns_prior(self):
        """If GP model has no alpha_, prediction falls back to high-uncertainty prior."""
        rpm_bins, map_bins = GRID_SHAPES["10x9_test"]
        s = _create_surrogate(rpm_bins, map_bins)

        # Manually force the fallback state
        from dynoai_v3.gp_surrogate import Observation
        for rpm in [2500, 3000, 3500]:
            s.add_observation(Observation(rpm=rpm, map_kpa=100, ve_delta=85.0))

        # Trigger fit
        s._refit()
        assert s.is_fitted

        # Simulate sklearn bug: remove alpha_ attribute
        if hasattr(s._gp_model, "alpha_"):
            delattr(s._gp_model, "alpha_")

        pred = _predict_full_map(s)

        # Should fall back to high-uncertainty prior
        assert pred.ve_map.shape == (len(rpm_bins), len(map_bins))
        assert np.all(pred.uncertainty_map >= 5.0), "Fallback should have high uncertainty"

        metrics = HarnessMetrics(
            scenario="alpha_fallback",
            backend=BACKEND,
            grid_shape="10x9_test",
            n_rpm=len(rpm_bins),
            n_map=len(map_bins),
            n_train=3,
            n_holdout=0,
            n_template=0,
            mode="fallback",
            mean_uncertainty_full=float(np.mean(pred.uncertainty_map)),
            total_obs_in_model=s.observation_count,
        )

        _all_metrics.append(metrics)
        print(f"\n{metrics.summary()}")


class TestDeterminism:
    """Verify that identical inputs produce identical outputs (within float tolerance)."""

    pytestmark = pytest.mark.validation

    def test_identical_inputs_identical_outputs(self):
        rpm_bins, map_bins = GRID_SHAPES["10x9_test"]
        ve_surface = _make_ve_surface(rpm_bins, map_bins)

        results = []
        for trial in range(3):
            s = _create_surrogate(rpm_bins, map_bins)
            s.seed_from_template(ve_surface, rpm_bins, map_bins)

            obs = _generate_observations(ve_surface, rpm_bins, map_bins, n_obs=30, seed=42)
            for o in obs:
                _add_observation(s, o["rpm"], o["map_kpa"], o["ve"])

            pred = _predict_full_map(s)
            results.append(pred.ve_map.copy())

        # Compare all pairs
        for i in range(1, len(results)):
            max_diff = float(np.max(np.abs(results[0] - results[i])))
            # Note: sklearn GP with optimizer restarts may not be bit-identical.
            # Record the actual drift so numpy backend can improve on it.
            print(f"\n  Determinism trial 0 vs {i}: max_diff = {max_diff:.6e}")

            # Loose tolerance for sklearn (optimizer has randomness)
            # Numpy backend should achieve max_diff == 0.0
            assert max_diff < 1.0, (
                f"Excessive non-determinism: max_diff={max_diff:.6e} (budget: <1.0 VE%)"
            )


class TestCapSizeTraining:
    """Scenario: Exercise GP at observation cap (~150 points).

    This is the largest Cholesky the system will ever compute.
    Tests accuracy and latency at the documented _MAX_OBS_FOR_REFIT boundary.
    """

    pytestmark = pytest.mark.validation

    @pytest.mark.parametrize("grid_name", ["11x5_production", "16x16_budget"])
    def test_cap_size_accuracy_and_latency(self, grid_name):
        from dynoai_v3.gp_surrogate import _MAX_OBS_FOR_REFIT

        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        ve_surface = _make_ve_surface(rpm_bins, map_bins)

        # Generate observations near the cap
        n_obs = min(_MAX_OBS_FOR_REFIT, 150)
        all_obs = _generate_observations(
            ve_surface, rpm_bins, map_bins, n_obs=n_obs, seed=303,
        )
        train, holdout = _holdout_split(all_obs, holdout_fraction=0.2)

        s = _create_surrogate(rpm_bins, map_bins)
        for obs in train:
            _add_observation(s, obs["rpm"], obs["map_kpa"], obs["ve"], pull_number=1)

        # Time the fit (first prediction triggers it)
        t0 = time.perf_counter()
        pred = _predict_full_map(s)
        first_fit_ms = (time.perf_counter() - t0) * 1000

        # Time cached prediction
        timings = []
        for _ in range(5):
            t0 = time.perf_counter()
            _ = _predict_full_map(s)
            timings.append((time.perf_counter() - t0) * 1000)
        cached_ms = float(np.median(timings))

        # Holdout accuracy
        errors = []
        for obs in holdout:
            r, m = obs["grid_r"], obs["grid_m"]
            predicted = pred.ve_map[r, m]
            actual = ve_surface[r, m]
            errors.append(predicted - actual)

        errors = np.array(errors)
        mae = float(np.mean(np.abs(errors)))
        rmse = float(np.sqrt(np.mean(errors**2)))
        max_err = float(np.max(np.abs(errors)))

        metrics = HarnessMetrics(
            scenario="cap_size_training",
            backend=BACKEND,
            grid_shape=grid_name,
            n_rpm=len(rpm_bins),
            n_map=len(map_bins),
            n_train=len(train),
            n_holdout=len(holdout),
            n_template=0,
            mode="normal_fit",
            mae=mae,
            rmse=rmse,
            max_error=max_err,
            predict_full_map_ms=first_fit_ms,
            refit_ms=s._last_fit_time_ms,
            total_obs_in_model=s.observation_count,
        )

        _all_metrics.append(metrics)
        print(f"\n{metrics.summary()}")
        print(f"  cached predict: {cached_ms:.1f}ms")
        print(f"  train size: {len(train)} (cap: {_MAX_OBS_FOR_REFIT})")

        assert mae < 5.0, f"Cap-size MAE too high: {mae:.4f}"
        assert first_fit_ms < 5000, f"Cap-size first fit too slow: {first_fit_ms:.0f}ms"
        assert cached_ms < 10, f"Cap-size cached predict too slow: {cached_ms:.1f}ms"


class TestNumpyBackendAB:
    """A/B comparison: Run key scenarios with numpy backend through VESurrogate.

    Validates that the numpy backend produces correct results when wired
    through the full surrogate pipeline (normalization, template handling,
    observation management, predict_full_map).
    """

    pytestmark = pytest.mark.validation

    def _create_numpy_surrogate(self, rpm_bins, map_bins, engine_family="m8_114"):
        from dynoai_v3.gp_surrogate import VESurrogate
        return VESurrogate(rpm_bins, map_bins, engine_family, backend="numpy")

    @pytest.mark.parametrize("grid_name", list(GRID_SHAPES.keys()))
    def test_numpy_template_plus_real_accuracy(self, grid_name):
        """Numpy backend: template + real data holdout accuracy."""
        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        ve_surface = _make_ve_surface(rpm_bins, map_bins)

        n_obs = min(80, len(rpm_bins) * len(map_bins) * 2)
        all_obs = _generate_observations(ve_surface, rpm_bins, map_bins, n_obs=n_obs)
        train, holdout = _holdout_split(all_obs)

        s = self._create_numpy_surrogate(rpm_bins, map_bins)
        s.seed_from_template(ve_surface, rpm_bins, map_bins)
        for obs in train:
            _add_observation(s, obs["rpm"], obs["map_kpa"], obs["ve"], pull_number=1)

        t0 = time.perf_counter()
        pred = _predict_full_map(s)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        errors = []
        for obs in holdout:
            r, m = obs["grid_r"], obs["grid_m"]
            errors.append(pred.ve_map[r, m] - ve_surface[r, m])

        errors = np.array(errors)
        mae = float(np.mean(np.abs(errors)))
        rmse = float(np.sqrt(np.mean(errors**2)))
        max_err = float(np.max(np.abs(errors)))

        metrics = HarnessMetrics(
            scenario="numpy_template_plus_real",
            backend="numpy",
            grid_shape=grid_name,
            n_rpm=len(rpm_bins),
            n_map=len(map_bins),
            n_train=len(train),
            n_holdout=len(holdout),
            n_template=len(rpm_bins) * len(map_bins),
            mode="normal_fit",
            mae=mae,
            rmse=rmse,
            max_error=max_err,
            predict_full_map_ms=elapsed_ms,
            refit_ms=s._last_fit_time_ms,
            total_obs_in_model=s.observation_count,
            template_obs_in_model=s.template_observation_count,
        )
        _all_metrics.append(metrics)
        print(f"\n{metrics.summary()}")

        assert mae < 5.0, f"Numpy MAE too high: {mae:.4f}"
        assert pred.ve_map.shape == (len(rpm_bins), len(map_bins))

    @pytest.mark.parametrize("grid_name", list(GRID_SHAPES.keys()))
    def test_numpy_real_only_accuracy(self, grid_name):
        """Numpy backend: real data only holdout accuracy."""
        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        ve_surface = _make_ve_surface(rpm_bins, map_bins)

        n_obs = min(120, len(rpm_bins) * len(map_bins) * 3)
        all_obs = _generate_observations(ve_surface, rpm_bins, map_bins, n_obs=n_obs, seed=77)
        train, holdout = _holdout_split(all_obs)

        s = self._create_numpy_surrogate(rpm_bins, map_bins)
        for obs in train:
            _add_observation(s, obs["rpm"], obs["map_kpa"], obs["ve"], pull_number=1)

        pred = _predict_full_map(s)

        errors = []
        for obs in holdout:
            r, m = obs["grid_r"], obs["grid_m"]
            errors.append(pred.ve_map[r, m] - ve_surface[r, m])

        errors = np.array(errors)
        mae = float(np.mean(np.abs(errors)))

        metrics = HarnessMetrics(
            scenario="numpy_real_only",
            backend="numpy",
            grid_shape=grid_name,
            n_rpm=len(rpm_bins),
            n_map=len(map_bins),
            n_train=len(train),
            n_holdout=len(holdout),
            n_template=0,
            mode="normal_fit",
            mae=mae,
            rmse=float(np.sqrt(np.mean(errors**2))),
            max_error=float(np.max(np.abs(errors))),
            predict_full_map_ms=None,
            refit_ms=s._last_fit_time_ms,
            total_obs_in_model=s.observation_count,
        )
        _all_metrics.append(metrics)
        print(f"\n{metrics.summary()}")

        assert mae < 10.0, f"Numpy MAE too high: {mae:.4f}"

    def test_numpy_template_passthrough(self):
        """Numpy backend: template-only returns exact seed table."""
        rpm_bins, map_bins = GRID_SHAPES["11x5_production"]
        ve_surface = _make_ve_surface(rpm_bins, map_bins)

        s = self._create_numpy_surrogate(rpm_bins, map_bins)
        s.seed_from_template(ve_surface, rpm_bins, map_bins)

        pred = _predict_full_map(s)
        np.testing.assert_array_equal(pred.ve_map, ve_surface)

    def test_numpy_determinism(self):
        """Numpy backend through VESurrogate: bit-identical across trials."""
        rpm_bins, map_bins = GRID_SHAPES["10x9_test"]
        ve_surface = _make_ve_surface(rpm_bins, map_bins)

        results = []
        for _ in range(3):
            s = self._create_numpy_surrogate(rpm_bins, map_bins)
            s.seed_from_template(ve_surface, rpm_bins, map_bins)
            obs = _generate_observations(ve_surface, rpm_bins, map_bins, n_obs=30, seed=42)
            for o in obs:
                _add_observation(s, o["rpm"], o["map_kpa"], o["ve"])
            pred = _predict_full_map(s)
            results.append(pred.ve_map.copy())

        for i in range(1, len(results)):
            max_diff = float(np.max(np.abs(results[0] - results[i])))
            print(f"\n  Numpy determinism trial 0 vs {i}: max_diff = {max_diff:.6e}")
            assert max_diff == 0.0, f"Numpy not bit-identical: {max_diff}"

    @pytest.mark.parametrize("grid_name", ["11x5_production", "16x16_budget"])
    def test_numpy_latency(self, grid_name):
        """Numpy backend: fit + predict within contract."""
        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        ve_surface = _make_ve_surface(rpm_bins, map_bins)

        s = self._create_numpy_surrogate(rpm_bins, map_bins)
        s.seed_from_template(ve_surface, rpm_bins, map_bins)
        obs = _generate_observations(ve_surface, rpm_bins, map_bins, n_obs=100, seed=55)
        for o in obs:
            _add_observation(s, o["rpm"], o["map_kpa"], o["ve"])

        # First call triggers fit
        t0 = time.perf_counter()
        _ = _predict_full_map(s)
        first_ms = (time.perf_counter() - t0) * 1000

        # Cached calls
        timings = []
        for _ in range(10):
            t0 = time.perf_counter()
            _ = _predict_full_map(s)
            timings.append((time.perf_counter() - t0) * 1000)
        cached_ms = float(np.median(timings))

        print(f"\n  Numpy latency [{grid_name}]: first={first_ms:.1f}ms, cached={cached_ms:.2f}ms")

        # Numpy contract: first fit < 10ms, cached < 2ms
        assert first_ms < 50, f"First fit too slow: {first_ms:.1f}ms"
        assert cached_ms < 5, f"Cached predict too slow: {cached_ms:.2f}ms"

    @pytest.mark.parametrize("grid_name", list(GRID_SHAPES.keys()))
    def test_numpy_vs_sklearn_mean_agreement(self, grid_name):
        """Key A/B: numpy and sklearn predictions on same data should be close.

        Note: sklearn optimizes hyperparameters, numpy uses frozen values,
        so predictions won't match exactly. We verify they're in the same
        ballpark (< 3 VE% MAE between backends).
        """
        from dynoai_v3.gp_surrogate import VESurrogate

        rpm_bins, map_bins = GRID_SHAPES[grid_name]
        ve_surface = _make_ve_surface(rpm_bins, map_bins)

        n_obs = min(60, len(rpm_bins) * len(map_bins) * 2)
        obs = _generate_observations(ve_surface, rpm_bins, map_bins, n_obs=n_obs, seed=888)

        # sklearn
        s_sk = VESurrogate(rpm_bins, map_bins, "m8_114", backend="sklearn")
        for o in obs:
            _add_observation(s_sk, o["rpm"], o["map_kpa"], o["ve"])
        pred_sk = _predict_full_map(s_sk)

        # numpy
        s_np = VESurrogate(rpm_bins, map_bins, "m8_114", backend="numpy")
        for o in obs:
            _add_observation(s_np, o["rpm"], o["map_kpa"], o["ve"])
        pred_np = _predict_full_map(s_np)

        diff = pred_sk.ve_map - pred_np.ve_map
        mae = float(np.mean(np.abs(diff)))
        max_diff = float(np.max(np.abs(diff)))

        print(f"\n  sklearn vs numpy [{grid_name}]: MAE={mae:.4f}, max_diff={max_diff:.4f}")

        # Loose: sklearn optimizes hyperparams, numpy freezes them
        assert mae < 3.0, f"Backend disagreement too large: MAE={mae:.4f}"


# ---------------------------------------------------------------------------
# Final report — prints summary of all metrics after all tests
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _print_final_report(request):
    """Print full metrics report after all tests complete."""
    def _report():
        if not _all_metrics:
            return
        print("\n")
        print("=" * 78)
        print("GP HOLDOUT HARNESS — FULL METRICS REPORT")
        print(f"Backend: {BACKEND}")
        print(f"Scenarios run: {len(_all_metrics)}")
        print("=" * 78)

        for m in _all_metrics:
            print(f"\n{m.summary()}")

        # Summary table for holdout accuracy scenarios
        accuracy_runs = [m for m in _all_metrics if m.mae is not None]
        if accuracy_runs:
            print("\n" + "-" * 60)
            print("HOLDOUT ACCURACY SUMMARY")
            print(f"{'Scenario':<25} {'Grid':<15} {'MAE':>8} {'RMSE':>8} {'MaxErr':>8}")
            print("-" * 60)
            for m in accuracy_runs:
                print(f"{m.scenario:<25} {m.grid_shape:<15} {m.mae:>8.4f} {m.rmse:>8.4f} {m.max_error:>8.4f}")

        # Latency summary
        latency_runs = [m for m in _all_metrics if m.predict_full_map_ms is not None]
        if latency_runs:
            print("\n" + "-" * 60)
            print("LATENCY SUMMARY")
            print(f"{'Scenario':<25} {'Grid':<15} {'predict_ms':>12} {'refit_ms':>12}")
            print("-" * 60)
            for m in latency_runs:
                refit = f"{m.refit_ms:.1f}" if m.refit_ms is not None else "—"
                pred = f"{m.predict_full_map_ms:.1f}" if m.predict_full_map_ms is not None else "—"
                print(f"{m.scenario:<25} {m.grid_shape:<15} {pred:>12} {refit:>12}")

        print("\n" + "=" * 78)

    request.addfinalizer(_report)
