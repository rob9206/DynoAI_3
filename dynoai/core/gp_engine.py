"""
DynoAI — Pure NumPy Gaussian Process Engine
=============================================

Matérn ν=5/2 kernel with ARD length scales. No sklearn, no scipy.
Deterministic for fixed inputs under pinned BLAS threads.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

DEFAULT_LENGTH_SCALES = np.array([0.3, 0.3], dtype=np.float64)
DEFAULT_SIGNAL_VAR = 1.0
DEFAULT_NOISE_VAR = 0.15
DEFAULT_JITTER = 1e-8


def _scaled_sqdist(A: NDArray[np.float64], B: NDArray[np.float64]) -> NDArray[np.float64]:
    """Squared Euclidean distance matrix between rows of A and B."""
    a2 = np.sum(A * A, axis=1)[:, None]
    b2 = np.sum(B * B, axis=1)[None, :]
    d2 = a2 + b2 - 2.0 * (A @ B.T)
    np.maximum(d2, 0.0, out=d2)
    return d2


def _matern52(r: NDArray[np.float64], signal_var: float = 1.0) -> NDArray[np.float64]:
    """Matérn ν=5/2 kernel value for distance matrix r."""
    s5 = np.sqrt(5.0)
    return signal_var * (1.0 + s5 * r + (5.0 / 3.0) * r * r) * np.exp(-s5 * r)


@dataclass
class _FitCache:
    """Cached Cholesky and normalization values from fit()."""

    X_train_scaled: NDArray[np.float64]
    y_mean: float
    y_std: float
    L: NDArray[np.float64]
    alpha: NDArray[np.float64]
    signal_var: float
    noise_var: float
    jitter: float
    length_scales: NDArray[np.float64]


class MaternGP:
    """Pure NumPy GP regressor with frozen Matérn 5/2 hyperparameters."""

    def __init__(
        self,
        length_scales: Optional[NDArray[np.float64]] = None,
        signal_var: float = DEFAULT_SIGNAL_VAR,
        noise_var: float = DEFAULT_NOISE_VAR,
        jitter: float = DEFAULT_JITTER,
        normalize_y: bool = True,
    ):
        self.length_scales = np.asarray(
            length_scales if length_scales is not None else DEFAULT_LENGTH_SCALES,
            dtype=np.float64,
        )
        self.signal_var = float(signal_var)
        self.noise_var = float(noise_var)
        self.jitter = float(jitter)
        self.normalize_y = normalize_y
        self._cache: Optional[_FitCache] = None

    @property
    def is_fitted(self) -> bool:
        return self._cache is not None

    def fit(self, X_train: NDArray[np.float64], y_train: NDArray[np.float64]) -> None:
        """Fit GP and cache Cholesky for fast repeated predict() calls."""
        X = np.asarray(X_train, dtype=np.float64)
        y = np.asarray(y_train, dtype=np.float64).ravel()
        n = X.shape[0]
        if n == 0:
            self._cache = None
            return

        if self.normalize_y:
            y_mean = float(np.mean(y))
            y_std = float(np.std(y))
            if y_std < 1e-12:
                y_std = 1.0
            y_norm = (y - y_mean) / y_std
        else:
            y_mean = 0.0
            y_std = 1.0
            y_norm = y.copy()

        ls = self.length_scales
        X_scaled = X / ls

        d2 = _scaled_sqdist(X_scaled, X_scaled)
        K = _matern52(np.sqrt(d2), self.signal_var)
        K[np.diag_indices(n)] += self.noise_var + self.jitter

        L = np.linalg.cholesky(K)
        v = np.linalg.solve(L, y_norm)
        alpha = np.linalg.solve(L.T, v)

        self._cache = _FitCache(
            X_train_scaled=X_scaled,
            y_mean=y_mean,
            y_std=y_std,
            L=L,
            alpha=alpha,
            signal_var=self.signal_var,
            noise_var=self.noise_var,
            jitter=self.jitter,
            length_scales=self.length_scales.copy(),
        )

        logger.debug("MaternGP fit n=%d y_mean=%.3f y_std=%.3f", n, y_mean, y_std)

    def predict(
        self,
        X_pred: NDArray[np.float64],
        return_std: bool = True,
    ) -> Tuple[NDArray[np.float64], Optional[NDArray[np.float64]]]:
        """Predict posterior mean and latent std at X_pred."""
        if self._cache is None:
            raise RuntimeError("MaternGP.predict() called before fit()")

        c = self._cache
        Xp = np.asarray(X_pred, dtype=np.float64)
        Xp_scaled = Xp / c.length_scales

        d2_star = _scaled_sqdist(Xp_scaled, c.X_train_scaled)
        K_star = _matern52(np.sqrt(d2_star), c.signal_var)

        mean_norm = K_star @ c.alpha
        mean = mean_norm * c.y_std + c.y_mean

        if not return_std:
            return mean, None

        w = np.linalg.solve(c.L, K_star.T)
        var_f = c.signal_var - np.sum(w * w, axis=0)
        np.maximum(var_f, 0.0, out=var_f)
        std = np.sqrt(var_f) * c.y_std
        return mean, std

    def invalidate(self) -> None:
        """Clear fit cache."""
        self._cache = None

    def get_hyperparameters(self) -> dict:
        """Return configured frozen hyperparameters."""
        return {
            "length_scales": self.length_scales.tolist(),
            "signal_var": self.signal_var,
            "noise_var": self.noise_var,
            "jitter": self.jitter,
            "normalize_y": self.normalize_y,
        }
