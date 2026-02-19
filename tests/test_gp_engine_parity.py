"""Parity tests for NumPy MaternGP against sklearn with fixed parameters."""

from __future__ import annotations

import time

import numpy as np
import pytest

from dynoai.core.gp_engine import MaternGP

GRID_SHAPES = {
    "11x5": (np.linspace(0, 1, 11), np.linspace(0, 1, 5)),
    "16x16": (np.linspace(0, 1, 16), np.linspace(0, 1, 16)),
}

LENGTH_SCALES = np.array([0.3, 0.3])
SIGNAL_VAR = 1.0
NOISE_VAR = 0.15
JITTER = 1e-8


def _make_training_data(n: int, seed: int = 42):
    rng = np.random.RandomState(seed)
    X = rng.rand(n, 2)
    y = 85.0 + 10.0 * np.sin(np.pi * X[:, 0]) + 15.0 * X[:, 1] + rng.randn(n) * 0.5
    return X, y


def _grid_points(rpm_norm: np.ndarray, map_norm: np.ndarray) -> np.ndarray:
    rr, mm = np.meshgrid(rpm_norm, map_norm, indexing="ij")
    return np.column_stack([rr.ravel(), mm.ravel()])


def _sklearn_fixed_predict(X_train, y_train, X_pred):
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import Matern, WhiteKernel

    kernel = Matern(nu=2.5, length_scale=LENGTH_SCALES.tolist()) + WhiteKernel(
        noise_level=NOISE_VAR
    )
    gp = GaussianProcessRegressor(
        kernel=kernel,
        optimizer=None,
        n_restarts_optimizer=0,
        alpha=JITTER,
        normalize_y=True,
    )
    gp.fit(X_train, y_train)
    return gp.predict(X_pred, return_std=True)


def _numpy_predict(X_train, y_train, X_pred):
    gp = MaternGP(
        length_scales=LENGTH_SCALES,
        signal_var=SIGNAL_VAR,
        noise_var=NOISE_VAR,
        jitter=JITTER,
        normalize_y=True,
    )
    gp.fit(X_train, y_train)
    return gp.predict(X_pred, return_std=True)


class TestMathParity:
    pytestmark = pytest.mark.validation

    @pytest.mark.parametrize("n_train", [10, 50, 120])
    @pytest.mark.parametrize("grid_name", ["11x5", "16x16"])
    def test_mean_parity(self, n_train, grid_name):
        X, y = _make_training_data(n_train)
        X_pred = _grid_points(*GRID_SHAPES[grid_name])

        mean_sk, _ = _sklearn_fixed_predict(X, y, X_pred)
        mean_np, _ = _numpy_predict(X, y, X_pred)

        assert float(np.max(np.abs(mean_sk - mean_np))) < 1e-6

    @pytest.mark.parametrize("n_train", [10, 50, 120])
    @pytest.mark.parametrize("grid_name", ["11x5", "16x16"])
    def test_std_parity_observation_level(self, n_train, grid_name):
        X, y = _make_training_data(n_train)
        X_pred = _grid_points(*GRID_SHAPES[grid_name])

        _, std_sk = _sklearn_fixed_predict(X, y, X_pred)
        _, std_np = _numpy_predict(X, y, X_pred)

        y_std = float(np.std(y))
        if y_std < 1e-12:
            y_std = 1.0
        std_np_obs = np.sqrt(std_np**2 + NOISE_VAR * y_std**2)
        assert float(np.max(np.abs(std_sk - std_np_obs))) < 1e-4


class TestDeterminismAndLatency:
    pytestmark = pytest.mark.validation

    def test_bit_identical(self):
        X, y = _make_training_data(80)
        X_pred = _grid_points(*GRID_SHAPES["16x16"])
        outs = []
        for _ in range(3):
            gp = MaternGP(length_scales=LENGTH_SCALES, signal_var=SIGNAL_VAR, noise_var=NOISE_VAR)
            gp.fit(X, y)
            outs.append(gp.predict(X_pred))
        for i in range(1, 3):
            assert float(np.max(np.abs(outs[0][0] - outs[i][0]))) == 0.0
            assert float(np.max(np.abs(outs[0][1] - outs[i][1]))) == 0.0

    @pytest.mark.parametrize("n_train", [30, 80, 150])
    @pytest.mark.parametrize("grid_name", ["11x5", "16x16"])
    def test_latency_contract(self, n_train, grid_name):
        X, y = _make_training_data(n_train)
        X_pred = _grid_points(*GRID_SHAPES[grid_name])
        gp = MaternGP(length_scales=LENGTH_SCALES, signal_var=SIGNAL_VAR, noise_var=NOISE_VAR)

        t0 = time.perf_counter()
        gp.fit(X, y)
        fit_ms = (time.perf_counter() - t0) * 1000

        timings = []
        for _ in range(10):
            t1 = time.perf_counter()
            gp.predict(X_pred)
            timings.append((time.perf_counter() - t1) * 1000)
        pred_ms = float(np.median(timings))

        assert fit_ms < 10.0
        assert pred_ms < 3.0


class TestEdgeCases:
    pytestmark = pytest.mark.validation

    def test_single_observation(self):
        gp = MaternGP()
        gp.fit(np.array([[0.5, 0.5]]), np.array([90.0]))
        mean, std = gp.predict(np.array([[0.5, 0.5], [0.0, 0.0]]))
        assert mean.shape == (2,)
        assert std.shape == (2,)
        assert np.all(std >= 0)

    def test_predict_before_fit_raises(self):
        with pytest.raises(RuntimeError):
            MaternGP().predict(np.array([[0.5, 0.5]]))
