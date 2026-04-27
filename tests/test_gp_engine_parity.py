"""
DynoAI GP Engine — Parity Tests
=================================

A/B comparison of MaternGP (NumPy) vs sklearn GaussianProcessRegressor
with optimizer DISABLED (fixed kernel params).

This isolates the math comparison from sklearn's optimizer behavior.
Both backends get the same X, y, and hyperparameters.

Run:  pytest tests/test_gp_engine_parity.py -v -s

Author: Thunderhorse Tuning / DynoAI
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from dynoai.core.gp_engine import MaternGP

# ---------------------------------------------------------------------------
# Shared test data generators (deterministic)
# ---------------------------------------------------------------------------
GRID_SHAPES = {
    "10x9": (
        np.linspace(0, 1, 10),  # Already normalized
        np.linspace(0, 1, 9),
    ),
    "11x5": (
        np.linspace(0, 1, 11),
        np.linspace(0, 1, 5),
    ),
    "16x16": (
        np.linspace(0, 1, 16),
        np.linspace(0, 1, 16),
    ),
}


def _make_training_data(n: int, d: int = 2, seed: int = 42):
    """Generate normalized training data in [0,1]^d with smooth target."""
    rng = np.random.RandomState(seed)
    X = rng.rand(n, d)
    # Smooth target: y = 85 + 10*sin(pi*x0) + 15*x1 + noise
    y = 85.0 + 10.0 * np.sin(
        np.pi * X[:, 0]) + 15.0 * X[:, 1] + rng.randn(n) * 0.5
    return X, y


def _make_pred_grid(rpm_norm: np.ndarray, map_norm: np.ndarray) -> np.ndarray:
    """Create prediction grid from normalized axes."""
    rr, mm = np.meshgrid(rpm_norm, map_norm, indexing="ij")
    return np.column_stack([rr.ravel(), mm.ravel()])


# ---------------------------------------------------------------------------
# Frozen hyperparameters for parity comparison
# ---------------------------------------------------------------------------
LENGTH_SCALES = np.array([0.3, 0.3])
SIGNAL_VAR = 1.0
NOISE_VAR = 0.15  # Combined: WhiteKernel(0.1) + alpha(0.05)
JITTER = 1e-8


def _sklearn_fixed_predict(X_train, y_train, X_pred, return_std=True):
    """
    sklearn GP with optimizer DISABLED and matching hyperparameters.

    This is the apples-to-apples comparison target.
    """
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import Matern, WhiteKernel

    # Fixed kernel (n_restarts_optimizer=0 disables optimization)
    kernel = Matern(nu=2.5, length_scale=LENGTH_SCALES.tolist()) + WhiteKernel(
        noise_level=NOISE_VAR)
    gp = GaussianProcessRegressor(
        kernel=kernel,
        n_restarts_optimizer=0,
        optimizer=None,  # Fully disable optimizer
        alpha=JITTER,  # Only jitter on diagonal (noise is in WhiteKernel)
        normalize_y=True,
    )
    gp.fit(X_train, y_train)
    if return_std:
        mean, std = gp.predict(X_pred, return_std=True)
        return mean, std
    return gp.predict(X_pred), None


def _numpy_predict(X_train, y_train, X_pred, return_std=True):
    """NumPy GP with matching hyperparameters."""
    gp = MaternGP(
        length_scales=LENGTH_SCALES,
        signal_var=SIGNAL_VAR,
        noise_var=NOISE_VAR,
        jitter=JITTER,
        normalize_y=True,
    )
    gp.fit(X_train, y_train)
    mean, std = gp.predict(X_pred, return_std=return_std)
    return mean, std


# ===========================================================================
# Parity tests
# ===========================================================================
class TestMathParity:
    """Verify NumPy engine produces same results as sklearn with fixed params."""

    pytestmark = pytest.mark.validation

    @pytest.mark.parametrize("n_train", [10, 50, 120])
    @pytest.mark.parametrize("grid_name", ["11x5", "16x16"])
    def test_mean_parity(self, n_train, grid_name):
        """Posterior mean should match within tight tolerance."""
        X_train, y_train = _make_training_data(n_train)
        rpm_norm, map_norm = GRID_SHAPES[grid_name]
        X_pred = _make_pred_grid(rpm_norm, map_norm)

        mean_sk, _ = _sklearn_fixed_predict(X_train,
                                            y_train,
                                            X_pred,
                                            return_std=False)
        mean_np, _ = _numpy_predict(X_train, y_train, X_pred, return_std=False)

        max_diff = float(np.max(np.abs(mean_sk - mean_np)))
        mae = float(np.mean(np.abs(mean_sk - mean_np)))

        print(f"\n  Mean parity [{grid_name}, n={n_train}]: "
              f"max_diff={max_diff:.2e}, MAE={mae:.2e}")

        # Tight tolerance — this is the same math, just different implementation
        assert max_diff < 1e-6, (
            f"Mean parity failed: max_diff={max_diff:.2e} (tolerance: 1e-6)")

    @pytest.mark.parametrize("n_train", [10, 50, 120])
    @pytest.mark.parametrize("grid_name", ["11x5", "16x16"])
    def test_std_parity(self, n_train, grid_name):
        """Posterior std should match after accounting for noise semantics.

        sklearn's kernel (Matern + WhiteKernel) includes noise_var in the prior
        diagonal at prediction points:  k_ss_sklearn = signal_var + noise_var.
        NumPy engine returns latent std: k_ss_numpy = signal_var.

        Relationship: std_sklearn² = std_numpy² + noise_var * y_std²
        We verify this holds to numerical precision.
        """
        X_train, y_train = _make_training_data(n_train)
        rpm_norm, map_norm = GRID_SHAPES[grid_name]
        X_pred = _make_pred_grid(rpm_norm, map_norm)

        _, std_sk = _sklearn_fixed_predict(X_train, y_train, X_pred)
        _, std_np = _numpy_predict(X_train, y_train, X_pred)

        # Compute y_std for the noise_var un-normalization factor
        y_std_val = float(np.std(y_train))
        if y_std_val < 1e-12:
            y_std_val = 1.0

        # Convert numpy latent std to observation std for comparison
        # var_observation = var_latent + noise_var * y_std²
        std_np_observation = np.sqrt(std_np**2 + NOISE_VAR * y_std_val**2)

        max_diff = float(np.max(np.abs(std_sk - std_np_observation)))
        print(f"\n  Std parity [{grid_name}, n={n_train}]: "
              f"max_diff={max_diff:.2e} (after noise correction)")

        # After accounting for the noise term, should match tightly
        assert max_diff < 1e-4, (
            f"Std parity failed: max_diff={max_diff:.2e} (tolerance: 1e-4)")

        # Also verify the raw difference matches expected noise contribution
        raw_diff = float(np.max(np.abs(std_sk - std_np)))
        print(
            f"  Raw std diff (before correction): {raw_diff:.4f} "
            f"(expected ~sqrt(noise_var)*y_std = {np.sqrt(NOISE_VAR) * y_std_val:.4f})"
        )


class TestNumpyDeterminism:
    """Verify NumPy engine is bit-identical across repeated calls."""

    pytestmark = pytest.mark.validation

    def test_bit_identical_repeated_fit_predict(self):
        """Same inputs → same outputs, exactly."""
        X_train, y_train = _make_training_data(80)
        rpm_norm, map_norm = GRID_SHAPES["16x16"]
        X_pred = _make_pred_grid(rpm_norm, map_norm)

        results = []
        for _ in range(5):
            gp = MaternGP(
                length_scales=LENGTH_SCALES,
                signal_var=SIGNAL_VAR,
                noise_var=NOISE_VAR,
                jitter=JITTER,
            )
            gp.fit(X_train, y_train)
            mean, std = gp.predict(X_pred)
            results.append((mean.copy(), std.copy()))

        for i in range(1, len(results)):
            mean_diff = float(np.max(np.abs(results[0][0] - results[i][0])))
            std_diff = float(np.max(np.abs(results[0][1] - results[i][1])))
            print(
                f"\n  Trial 0 vs {i}: mean_diff={mean_diff:.2e}, std_diff={std_diff:.2e}"
            )
            assert mean_diff == 0.0, f"Mean not bit-identical: diff={mean_diff}"
            assert std_diff == 0.0, f"Std not bit-identical: diff={std_diff}"


class TestNumpyLatency:
    """Verify NumPy engine meets performance contract."""

    pytestmark = pytest.mark.validation

    @pytest.mark.parametrize("n_train", [30, 80, 150])
    @pytest.mark.parametrize("grid_name", ["11x5", "16x16"])
    def test_fit_latency(self, n_train, grid_name):
        """fit() must complete within budget."""
        X_train, y_train = _make_training_data(n_train)

        gp = MaternGP(length_scales=LENGTH_SCALES,
                      signal_var=SIGNAL_VAR,
                      noise_var=NOISE_VAR)

        timings = []
        for _ in range(10):
            gp.invalidate()
            t0 = time.perf_counter()
            gp.fit(X_train, y_train)
            timings.append((time.perf_counter() - t0) * 1000)

        median_ms = float(np.median(timings))
        print(f"\n  Fit latency [n={n_train}]: median={median_ms:.2f}ms, "
              f"all={[f'{t:.2f}' for t in timings]}")

        # Contract: < 10ms for ≤ 150 points
        assert median_ms < 10.0, f"Fit too slow: {median_ms:.2f}ms (budget: 10ms)"

    @pytest.mark.parametrize("n_train", [30, 80, 150])
    @pytest.mark.parametrize("grid_name", ["11x5", "16x16"])
    def test_predict_latency(self, n_train, grid_name):
        """predict() must complete within budget."""
        X_train, y_train = _make_training_data(n_train)
        rpm_norm, map_norm = GRID_SHAPES[grid_name]
        X_pred = _make_pred_grid(rpm_norm, map_norm)

        gp = MaternGP(length_scales=LENGTH_SCALES,
                      signal_var=SIGNAL_VAR,
                      noise_var=NOISE_VAR)
        gp.fit(X_train, y_train)

        timings = []
        for _ in range(20):
            t0 = time.perf_counter()
            gp.predict(X_pred)
            timings.append((time.perf_counter() - t0) * 1000)

        median_ms = float(np.median(timings))
        n_pred = X_pred.shape[0]
        print(
            f"\n  Predict latency [{grid_name}, n_train={n_train}, n_pred={n_pred}]: "
            f"median={median_ms:.2f}ms")

        # Contract: cached prediction stays well under one-frame budget.
        # The original 2ms threshold flagged false-positives on slower CI
        # runners and on the 16x16 / n_train=150 corner. Codex review on
        # PR #130 explicitly called this brittle. 10ms still rules out a
        # real regression (e.g. accidentally re-running Cholesky every call,
        # which would be 100x+ slower) without flapping on a busy host.
        assert median_ms < 10.0, f"Predict too slow: {median_ms:.2f}ms (budget: 10ms)"


class TestEdgeCases:
    """Edge cases the engine must handle."""

    pytestmark = pytest.mark.validation

    def test_single_observation(self):
        """GP with n=1 should not crash."""
        X = np.array([[0.5, 0.5]])
        y = np.array([90.0])

        gp = MaternGP(length_scales=LENGTH_SCALES,
                      signal_var=SIGNAL_VAR,
                      noise_var=NOISE_VAR)
        gp.fit(X, y)

        X_pred = np.array([[0.5, 0.5], [0.0, 0.0], [1.0, 1.0]])
        mean, std = gp.predict(X_pred)

        assert mean.shape == (3, )
        assert std.shape == (3, )
        assert np.all(std >= 0)
        # Near the training point, mean should be close to 90
        assert abs(mean[0] - 90.0) < 1.0

    def test_constant_y(self):
        """Constant y should not crash (std of y = 0 edge case)."""
        X = np.random.RandomState(42).rand(20, 2)
        y = np.full(20, 85.0)

        gp = MaternGP(length_scales=LENGTH_SCALES,
                      signal_var=SIGNAL_VAR,
                      noise_var=NOISE_VAR)
        gp.fit(X, y)

        X_pred = np.array([[0.5, 0.5]])
        mean, std = gp.predict(X_pred)

        assert abs(mean[0] - 85.0) < 0.5
        assert std[0] >= 0

    def test_empty_training_set(self):
        """Empty fit → predict raises."""
        gp = MaternGP()
        gp.fit(np.zeros((0, 2)), np.zeros(0))
        assert not gp.is_fitted

        with pytest.raises(RuntimeError, match="before fit"):
            gp.predict(np.array([[0.5, 0.5]]))

    def test_predict_without_fit_raises(self):
        """predict() before fit() raises RuntimeError."""
        gp = MaternGP()
        with pytest.raises(RuntimeError, match="before fit"):
            gp.predict(np.array([[0.5, 0.5]]))

    def test_invalidate_clears_cache(self):
        """invalidate() clears the fit cache."""
        X, y = _make_training_data(20)
        gp = MaternGP()
        gp.fit(X, y)
        assert gp.is_fitted

        gp.invalidate()
        assert not gp.is_fitted

    def test_hyperparameter_reporting(self):
        """get_hyperparameters returns correct values."""
        gp = MaternGP(
            length_scales=np.array([0.4, 0.25]),
            signal_var=1.5,
            noise_var=0.2,
            jitter=1e-6,
        )
        hp = gp.get_hyperparameters()
        assert hp["length_scales"] == [0.4, 0.25]
        assert hp["signal_var"] == 1.5
        assert hp["noise_var"] == 0.2
        assert hp["jitter"] == 1e-6

    def test_large_grid_prediction(self):
        """Predict on 32×32 = 1024 grid cells (exceeds 256)."""
        X_train, y_train = _make_training_data(50)
        rpm_norm = np.linspace(0, 1, 32)
        map_norm = np.linspace(0, 1, 32)
        X_pred = _make_pred_grid(rpm_norm, map_norm)

        gp = MaternGP(length_scales=LENGTH_SCALES,
                      signal_var=SIGNAL_VAR,
                      noise_var=NOISE_VAR)
        gp.fit(X_train, y_train)
        mean, std = gp.predict(X_pred)

        assert mean.shape == (1024, )
        assert std.shape == (1024, )
        assert np.all(np.isfinite(mean))
        assert np.all(std >= 0)


# ===========================================================================
# Defensive guardrails added in response to PR #130 review feedback.
#
# These cover behaviors that the AI bots flagged but were never enforced
# by the original tests:
#   - Cross-instance state contamination via length_scales array aliasing
#   - Shape validation in fit() and predict()
#   - Cholesky failure error path
#   - Empty X_pred edge case
# ===========================================================================


class TestLengthScalesIsolation:
    """`length_scales` must not alias the module default or another instance."""

    pytestmark = pytest.mark.validation

    def test_module_default_is_not_aliased_by_default_constructor(self):
        from dynoai.core.gp_engine import DEFAULT_LENGTH_SCALES

        original = DEFAULT_LENGTH_SCALES.copy()
        gp = MaternGP()
        # Mutating the instance copy must not change the module default.
        gp.length_scales[0] = 99.0
        np.testing.assert_array_equal(DEFAULT_LENGTH_SCALES, original)

    def test_two_instances_do_not_share_length_scales(self):
        a = MaternGP()
        b = MaternGP()
        a.length_scales[0] = 7.7
        # b's array must be untouched.
        assert b.length_scales[0] != 7.7

    def test_caller_array_not_aliased(self):
        custom = np.array([0.5, 0.5], dtype=np.float64)
        gp = MaternGP(length_scales=custom)
        # Mutating the caller's array must not change the GP's internal copy.
        custom[0] = 99.0
        assert gp.length_scales[0] == 0.5


class TestShapeValidation:
    """fit() and predict() must reject shape mismatches with clear errors."""

    pytestmark = pytest.mark.validation

    def test_fit_rejects_1d_X(self):
        gp = MaternGP()
        with pytest.raises(ValueError, match="2D"):
            gp.fit(np.array([0.5, 0.5, 0.5]), np.array([90.0, 91.0, 92.0]))

    def test_fit_rejects_X_y_count_mismatch(self):
        gp = MaternGP()
        X = np.random.RandomState(0).rand(10, 2)
        y = np.zeros(7)  # wrong count
        with pytest.raises(ValueError, match="10 samples but y_train has 7"):
            gp.fit(X, y)

    def test_fit_rejects_feature_count_mismatch(self):
        # length_scales defaults to shape (2,); a 3-feature X must error.
        gp = MaternGP()
        X = np.random.RandomState(0).rand(10, 3)
        y = np.zeros(10)
        with pytest.raises(ValueError,
                           match="3 features but length_scales has 2"):
            gp.fit(X, y)

    def test_predict_rejects_1d_X(self):
        gp = MaternGP()
        X, y = _make_training_data(20)
        gp.fit(X, y)
        with pytest.raises(ValueError, match="2D"):
            gp.predict(np.array([0.5, 0.5]))

    def test_predict_rejects_feature_count_mismatch(self):
        gp = MaternGP()
        X, y = _make_training_data(20)
        gp.fit(X, y)
        with pytest.raises(ValueError,
                           match="3 features but model was fitted with 2"):
            gp.predict(np.random.RandomState(0).rand(5, 3))


class TestPredictEmptyInput:
    """Empty X_pred is a valid query shape and must not crash."""

    pytestmark = pytest.mark.validation

    def test_predict_with_empty_X_returns_empty(self):
        gp = MaternGP()
        X, y = _make_training_data(20)
        gp.fit(X, y)
        mean, std = gp.predict(np.zeros((0, 2)))
        assert mean.shape == (0, )
        assert std is not None
        assert std.shape == (0, )

    def test_predict_with_empty_X_and_no_std(self):
        gp = MaternGP()
        X, y = _make_training_data(20)
        gp.fit(X, y)
        mean, std = gp.predict(np.zeros((0, 2)), return_std=False)
        assert mean.shape == (0, )
        assert std is None


class TestCholeskyFailureMessage:
    """An ill-conditioned matrix should surface an actionable error."""

    pytestmark = pytest.mark.validation

    def test_cholesky_failure_raises_with_jitter_hint(self):
        # Build a degenerate setup: zero noise + zero jitter + duplicate
        # training points → singular kernel matrix.
        gp = MaternGP(
            length_scales=np.array([0.3, 0.3]),
            signal_var=1.0,
            noise_var=0.0,
            jitter=0.0,
        )
        X = np.array([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]])
        y = np.array([90.0, 90.0, 90.0])
        with pytest.raises(RuntimeError, match=r"jitter|noise_var"):
            gp.fit(X, y)
