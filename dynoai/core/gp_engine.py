"""
DynoAI — Pure NumPy Gaussian Process Engine
=============================================

Matérn ν=5/2 kernel with ARD length scales.  No sklearn, no scipy.
Deterministic for fixed inputs under pinned BLAS threads.

Design constraints (from holdout harness contract):
    - n_train ≤ 150, n_pred up to 256+ (arbitrary grid)
    - First fit < 10ms for 150×150 Cholesky
    - Cached predict < 2ms for 256×150 prediction
    - Bit-identical across repeated calls (no randomness)
    - Frozen hyperparameters (no optimizer)

Semantics:
    - Target y is absolute VE % (not residual over physics prior)
    - X normalization handled by caller (gp_surrogate.py)
    - y is internally centered + scaled (replicating sklearn normalize_y=True)
    - Returned std is for latent function f (not observation y)

Author: Thunderhorse Tuning / DynoAI
Version: 1.0.0 (NumPy backend, parity target with sklearn)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Frozen hyperparameter defaults
# ---------------------------------------------------------------------------
# These are seed values matching the sklearn kernel's initial config.
# They must be validated via holdout harness before production use.
DEFAULT_LENGTH_SCALES = np.array([0.3, 0.3], dtype=np.float64)
DEFAULT_SIGNAL_VAR = 1.0     # No ConstantKernel in current sklearn config
DEFAULT_NOISE_VAR = 0.15     # WhiteKernel(0.1) + alpha(0.05) combined
DEFAULT_JITTER = 1e-8        # Numerical stability only


# ---------------------------------------------------------------------------
# Kernel math
# ---------------------------------------------------------------------------
def _scaled_sqdist(A: NDArray, B: NDArray) -> NDArray:
    """
    Squared Euclidean distance matrix between rows of A and B.

    Args:
        A: (n, d) array, already scaled by length_scales
        B: (m, d) array, already scaled by length_scales

    Returns:
        (n, m) matrix of squared distances, clamped ≥ 0
    """
    # Stable computation: ||a-b||² = ||a||² + ||b||² - 2 a·b
    A_sq = np.sum(A * A, axis=1)[:, None]  # (n, 1)
    B_sq = np.sum(B * B, axis=1)[None, :]  # (1, m)
    D2 = A_sq + B_sq - 2.0 * (A @ B.T)
    np.maximum(D2, 0.0, out=D2)
    return D2


def _matern52(r: NDArray, signal_var: float = 1.0) -> NDArray:
    """
    Matérn ν=5/2 kernel evaluated at distance r.

    k(r) = signal_var * (1 + √5·r + 5/3·r²) · exp(-√5·r)

    Args:
        r: (n, m) non-negative distance matrix
        signal_var: kernel amplitude (k(0) = signal_var)

    Returns:
        (n, m) kernel matrix
    """
    s5 = np.sqrt(5.0)
    return signal_var * (1.0 + s5 * r + (5.0 / 3.0) * r * r) * np.exp(-s5 * r)


# ---------------------------------------------------------------------------
# Cache structure
# ---------------------------------------------------------------------------
@dataclass
class _FitCache:
    """Cached Cholesky factorization and solve results from fit()."""

    X_train_scaled: NDArray          # (n, d) — pre-divided by length_scales
    y_mean: float                    # center of y normalization
    y_std: float                     # scale of y normalization
    L: NDArray                       # (n, n) — lower Cholesky of K + noise*I
    alpha: NDArray                   # (n,) or (n, 1) — K^{-1} y_norm
    signal_var: float
    noise_var: float
    jitter: float
    length_scales: NDArray


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class MaternGP:
    """
    Gaussian Process regressor with Matérn 5/2 kernel.

    Pure NumPy.  Frozen hyperparameters.  Deterministic.

    Usage::

        gp = MaternGP(length_scales=[0.3, 0.3], signal_var=1.0, noise_var=0.15)
        gp.fit(X_train, y_train)
        mean, std = gp.predict(X_pred)

    The returned ``std`` is the **latent function** posterior standard deviation.
    For observation-level uncertainty: ``std_y = sqrt(std**2 + noise_var)``.
    """

    def __init__(
        self,
        length_scales: Optional[NDArray] = None,
        signal_var: float = DEFAULT_SIGNAL_VAR,
        noise_var: float = DEFAULT_NOISE_VAR,
        jitter: float = DEFAULT_JITTER,
        normalize_y: bool = True,
    ):
        """
        Args:
            length_scales: ARD length scales, shape (d,). Default [0.3, 0.3].
            signal_var: Kernel amplitude. k(x,x) = signal_var at zero distance.
            noise_var: Observation noise variance added to training diagonal.
            jitter: Tiny numerical stabilizer added to diagonal (independent of noise).
            normalize_y: If True, center+scale y by mean/std before fitting,
                         and un-transform on prediction (replicates sklearn behavior).
        """
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

    # ------------------------------------------------------------------
    # fit
    # ------------------------------------------------------------------
    def fit(self, X_train: NDArray, y_train: NDArray) -> None:
        """
        Fit the GP on training data.  Caches Cholesky factorization.

        Args:
            X_train: (n, d) training inputs, already X-normalized by caller.
            y_train: (n,) training targets (absolute VE %).

        Raises:
            np.linalg.LinAlgError: If Cholesky fails (shouldn't with jitter).
        """
        X = np.asarray(X_train, dtype=np.float64)
        y = np.asarray(y_train, dtype=np.float64).ravel()
        n = X.shape[0]

        if n == 0:
            self._cache = None
            return

        # -- y normalization (center + scale) --
        if self.normalize_y:
            y_mean = float(np.mean(y))
            y_std = float(np.std(y)) if n > 1 else 1.0
            if y_std < 1e-12:
                y_std = 1.0  # Avoid division by zero for constant y
            y_norm = (y - y_mean) / y_std
        else:
            y_mean = 0.0
            y_std = 1.0
            y_norm = y.copy()

        # -- Pre-scale X by length scales (done once) --
        ls = self.length_scales
        X_scaled = X / ls  # (n, d)

        # -- Kernel matrix K(X, X) --
        D2 = _scaled_sqdist(X_scaled, X_scaled)
        r = np.sqrt(D2)
        K = _matern52(r, self.signal_var)

        # -- Add noise + jitter to diagonal --
        diag_add = self.noise_var + self.jitter
        K[np.diag_indices(n)] += diag_add

        # -- Cholesky factorization --
        L = np.linalg.cholesky(K)  # (n, n) lower triangular

        # -- Solve for alpha: K^{-1} y_norm via two triangular solves --
        # L v = y_norm  →  v = L^{-1} y_norm
        # L^T alpha = v  →  alpha = K^{-1} y_norm
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

        logger.debug(
            "MaternGP fit: n=%d, y_mean=%.2f, y_std=%.4f, diag_add=%.2e",
            n, y_mean, y_std, diag_add,
        )

    # ------------------------------------------------------------------
    # predict
    # ------------------------------------------------------------------
    def predict(
        self,
        X_pred: NDArray,
        return_std: bool = True,
    ) -> Tuple[NDArray, Optional[NDArray]]:
        """
        Predict at new locations.

        Args:
            X_pred: (m, d) prediction inputs, X-normalized by caller.
            return_std: If True, also return posterior std of latent f.

        Returns:
            mean: (m,) posterior mean in original y scale.
            std:  (m,) posterior std of latent function f (or None).
                  For observation-level: std_y = sqrt(std**2 + noise_var).
        """
        if self._cache is None:
            raise RuntimeError("MaternGP.predict() called before fit()")

        c = self._cache
        X_pred = np.asarray(X_pred, dtype=np.float64)

        # -- Scale prediction inputs --
        X_pred_scaled = X_pred / c.length_scales  # (m, d)

        # -- Cross-covariance K(X*, X_train) --
        D2_star = _scaled_sqdist(X_pred_scaled, c.X_train_scaled)
        r_star = np.sqrt(D2_star)
        K_star = _matern52(r_star, c.signal_var)  # (m, n)

        # -- Posterior mean (normalized space) --
        mean_norm = K_star @ c.alpha  # (m,)

        # -- Un-normalize --
        mean = mean_norm * c.y_std + c.y_mean

        if not return_std:
            return mean, None

        # -- Posterior variance of f --
        # w = L^{-1} K_star^T  →  shape (n, m)
        w = np.linalg.solve(c.L, K_star.T)

        # k(x*,x*) diagonal = signal_var (Matérn at r=0)
        k_ss = c.signal_var

        # var_f = k_ss - sum(w^2, axis=0)
        var_f = k_ss - np.sum(w * w, axis=0)  # (m,)
        np.maximum(var_f, 0.0, out=var_f)

        # Scale std back to original y space
        std = np.sqrt(var_f) * c.y_std

        return mean, std

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------
    def invalidate(self) -> None:
        """Clear cached factorization. Call when training data changes."""
        self._cache = None

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    def get_hyperparameters(self) -> dict:
        """Return current frozen hyperparameters for logging/auditing."""
        return {
            "length_scales": self.length_scales.tolist(),
            "signal_var": self.signal_var,
            "noise_var": self.noise_var,
            "jitter": self.jitter,
            "normalize_y": self.normalize_y,
        }


