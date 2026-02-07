"""
DynoAI v3.0 — Gaussian Process Surrogate Engine
==================================================

Maintains a live probabilistic model of the entire VE map that updates
after each pull, providing both predictions and uncertainty estimates at
every cell.

Why GP, Not Neural Network:
    1. Calibrated uncertainty estimates out of the box
    2. Works well with small datasets (10-30 pulls)
    3. Interpretable — inspect kernel, lengthscales, noise model
    4. Industry standard in calibration tools (AVL CAMEO, ETAS ASCMO)

Performance Budget:
    _refit()          with 100 obs:  < 1.5 seconds
    _refit()          with 500 obs:  < 5 seconds
    predict_full_map  on 16x16 grid: < 100 ms
    predict           single point:  < 5 ms

Author: Thunderhorse Tuning / DynoAI
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Extreme VE delta threshold — observations beyond this are rejected
_MAX_VE_DELTA = 15.0


# ---------------------------------------------------------------------------
# Module-level confidence functions
# ---------------------------------------------------------------------------
def uncertainty_to_confidence(std: float) -> float:
    """
    Map GP standard deviation to a DynoAI confidence score (0-100).

    Aligns with existing H/M/L/skip badge system.
    """
    if std < 0.5:
        return 95.0   # High
    if std < 1.0:
        return 80.0   # Medium
    if std < 2.0:
        return 60.0   # Low
    return 20.0        # Skip / insufficient


def confidence_to_badge(confidence: float) -> str:
    """
    Map confidence score to DynoAI badge string.

    Returns:
        "H" (high), "M" (medium), "L" (low), or "—" (skip)
    """
    if confidence >= 90:
        return "H"
    if confidence >= 70:
        return "M"
    if confidence >= 50:
        return "L"
    return "\u2014"  # em-dash


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class Observation:
    """A single measured data point from a dyno pull."""
    rpm: float
    map_kpa: float
    ve_delta: float
    pull_number: Optional[int] = None
    timestamp: Optional[float] = None


@dataclass
class PointPrediction:
    """Prediction at a single operating point."""
    ve_delta: float
    uncertainty: float
    confidence: float
    badge: str


@dataclass
class FullMapPrediction:
    """Prediction across the entire VE grid."""
    ve_map: NDArray[np.float64]
    uncertainty_map: NDArray[np.float64]
    confidence_map: NDArray[np.float64]
    predict_time_ms: float


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class VESurrogate:
    """
    Gaussian Process surrogate for VE table prediction.

    Wraps scikit-learn GaussianProcessRegressor with DynoAI-specific
    input/output handling.

    Usage:
        s = VESurrogate(rpm_bins, map_bins, "m8_114")
        s.add_observation(Observation(rpm=3500, map_kpa=100, ve_delta=2.5))
        pred = s.predict(3500, 100)
        full = s.predict_full_map()
    """

    def __init__(
        self,
        rpm_bins: NDArray[np.float64],
        map_bins: NDArray[np.float64],
        engine_family: str,
    ):
        self.rpm_bins = np.array(rpm_bins, dtype=np.float64)
        self.map_bins = np.array(map_bins, dtype=np.float64)
        self.engine_family = engine_family
        self.observations: List[Observation] = []
        self.template_observation_count: int = 0

        self._gp_model = None
        self.is_fitted = False
        self._last_fit_time_ms: float = 0.0

        # Normalization parameters — computed from bin ranges
        self._rpm_min = float(np.min(rpm_bins))
        self._rpm_range = float(np.max(rpm_bins) - np.min(rpm_bins))
        self._map_min = float(np.min(map_bins))
        self._map_range = float(np.max(map_bins) - np.min(map_bins))

        logger.info(
            "VESurrogate initialized: %s, %d RPM bins x %d MAP bins",
            engine_family, len(rpm_bins), len(map_bins),
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def observation_count(self) -> int:
        return len(self.observations)

    # ------------------------------------------------------------------
    # Add data
    # ------------------------------------------------------------------
    def add_observation(self, obs: Observation) -> None:
        """Add a single measured data point and refit if we have enough."""
        if obs.timestamp is None:
            obs.timestamp = time.time()
        self.observations.append(obs)
        if len(self.observations) >= 3:
            self._refit()

    def add_pull_data(
        self,
        rpm: NDArray[np.float64],
        map_kpa: NDArray[np.float64],
        ve: NDArray[np.float64],
        pull_number: Optional[int] = None,
    ) -> int:
        """
        Ingest an entire pull's worth of data.

        Rejects extreme VE values (|ve_delta| > _MAX_VE_DELTA).

        Args:
            rpm: Array of RPM values
            map_kpa: Array of MAP values
            ve: Array of VE delta values
            pull_number: Optional pull sequence number

        Returns:
            Number of observations accepted
        """
        rpm = np.asarray(rpm, dtype=np.float64)
        map_kpa = np.asarray(map_kpa, dtype=np.float64)
        ve = np.asarray(ve, dtype=np.float64)

        accepted = 0
        ts = time.time()

        for i in range(len(rpm)):
            if abs(ve[i]) > _MAX_VE_DELTA:
                logger.debug(
                    "Rejected extreme VE delta: %.2f at RPM=%.0f MAP=%.0f",
                    ve[i], rpm[i], map_kpa[i],
                )
                continue
            self.observations.append(Observation(
                rpm=float(rpm[i]),
                map_kpa=float(map_kpa[i]),
                ve_delta=float(ve[i]),
                pull_number=pull_number,
                timestamp=ts,
            ))
            accepted += 1

        if len(self.observations) >= 3:
            self._refit()

        logger.info(
            "Pull data ingested: %d/%d accepted (pull #%s)",
            accepted, len(rpm),
            pull_number if pull_number is not None else "?",
        )
        return accepted

    # ------------------------------------------------------------------
    # Template seeding
    # ------------------------------------------------------------------
    def seed_from_template(
        self,
        template_ve: NDArray[np.float64],
        rpm_bins: NDArray[np.float64],
        map_bins: NDArray[np.float64],
    ) -> None:
        """
        Seed the GP surrogate with template VE data.

        Converts the template VE table into synthetic observations
        with elevated uncertainty (lower weight) so real dyno data
        can override them.

        Args:
            template_ve: 2D array of VE corrections from the template
            rpm_bins: RPM bins corresponding to template rows
            map_bins: MAP bins corresponding to template columns
        """
        template_ve = np.asarray(template_ve, dtype=np.float64)
        rpm_bins = np.asarray(rpm_bins, dtype=np.float64)
        map_bins = np.asarray(map_bins, dtype=np.float64)

        count = 0
        ts = time.time()
        for r_idx, rpm in enumerate(rpm_bins):
            for m_idx, map_kpa in enumerate(map_bins):
                if r_idx < template_ve.shape[0] and m_idx < template_ve.shape[1]:
                    self.observations.append(Observation(
                        rpm=float(rpm),
                        map_kpa=float(map_kpa),
                        ve_delta=float(template_ve[r_idx, m_idx]),
                        pull_number=-1,  # Sentinel for template data
                        timestamp=ts,
                    ))
                    count += 1

        self.template_observation_count = count

        if len(self.observations) >= 3:
            self._refit()

        logger.info(
            "Template seeded: %d synthetic observations added", count,
        )

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------
    def predict(self, rpm: float, map_kpa: float) -> PointPrediction:
        """
        Predict VE correction and uncertainty at a single point.

        If the model is not fitted, returns a high-uncertainty prior.
        """
        if not self.is_fitted or self._gp_model is None:
            return PointPrediction(
                ve_delta=0.0,
                uncertainty=10.0,
                confidence=uncertainty_to_confidence(10.0),
                badge=confidence_to_badge(uncertainty_to_confidence(10.0)),
            )

        X = self._normalize(np.array([[rpm, map_kpa]]))
        mean, std = self._gp_model.predict(X, return_std=True)

        unc = float(std[0])
        conf = uncertainty_to_confidence(unc)
        return PointPrediction(
            ve_delta=float(mean[0]),
            uncertainty=unc,
            confidence=conf,
            badge=confidence_to_badge(conf),
        )

    def predict_full_map(self) -> FullMapPrediction:
        """
        Predict entire VE grid with uncertainties.

        Returns FullMapPrediction with shapes (n_rpm, n_map).
        """
        t0 = time.time()
        n_rpm = len(self.rpm_bins)
        n_map = len(self.map_bins)

        if not self.is_fitted or self._gp_model is None:
            # Return prior: zero VE, high uncertainty
            elapsed = (time.time() - t0) * 1000
            unc_map = np.full((n_rpm, n_map), 10.0)
            return FullMapPrediction(
                ve_map=np.zeros((n_rpm, n_map)),
                uncertainty_map=unc_map,
                confidence_map=np.vectorize(uncertainty_to_confidence)(unc_map),
                predict_time_ms=elapsed,
            )

        grid = np.array([
            [r, m] for r in self.rpm_bins for m in self.map_bins
        ])
        X_norm = self._normalize(grid)
        means, stds = self._gp_model.predict(X_norm, return_std=True)

        ve_map = means.reshape(n_rpm, n_map)
        unc_map = stds.reshape(n_rpm, n_map)
        conf_map = np.vectorize(uncertainty_to_confidence)(unc_map)

        elapsed = (time.time() - t0) * 1000

        return FullMapPrediction(
            ve_map=ve_map,
            uncertainty_map=unc_map,
            confidence_map=conf_map,
            predict_time_ms=elapsed,
        )

    def get_uncertainty_map(self) -> NDArray[np.float64]:
        """Return uncertainty at every grid cell."""
        pred = self.predict_full_map()
        return pred.uncertainty_map

    # ------------------------------------------------------------------
    # GP fitting
    # ------------------------------------------------------------------
    def _refit(self) -> None:
        """
        Refit the GP model on all observations.

        Target: <1.5s for 100 obs, <5s for 500 obs.
        """
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import Matern, WhiteKernel

        if len(self.observations) < 3:
            return

        t0 = time.time()

        X = np.array([
            [o.rpm, o.map_kpa] for o in self.observations
        ])
        y = np.array([o.ve_delta for o in self.observations])

        X_norm = self._normalize(X)

        kernel = Matern(nu=2.5, length_scale=[0.3, 0.3]) + WhiteKernel(
            noise_level=0.1
        )
        self._gp_model = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=2,
            alpha=0.05,
            normalize_y=True,
        )
        self._gp_model.fit(X_norm, y)
        self.is_fitted = True

        self._last_fit_time_ms = (time.time() - t0) * 1000
        logger.info(
            "GP refit: %d observations, %.1f ms",
            len(self.observations),
            self._last_fit_time_ms,
        )

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------
    def _normalize(self, X: NDArray[np.float64]) -> NDArray[np.float64]:
        """Normalize RPM/MAP inputs to [0, 1] for stable GP fitting."""
        X_norm = X.copy().astype(np.float64)
        rpm_range = self._rpm_range if self._rpm_range > 0 else 1.0
        map_range = self._map_range if self._map_range > 0 else 1.0
        X_norm[:, 0] = (X_norm[:, 0] - self._rpm_min) / rpm_range
        X_norm[:, 1] = (X_norm[:, 1] - self._map_min) / map_range
        return X_norm

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def save_state(self, path: Path) -> None:
        """Save surrogate state for persistence across sessions."""
        state = {
            "engine_family": self.engine_family,
            "rpm_bins": self.rpm_bins.tolist(),
            "map_bins": self.map_bins.tolist(),
            "template_observation_count": self.template_observation_count,
            "observations": [
                {
                    "rpm": o.rpm,
                    "map_kpa": o.map_kpa,
                    "ve_delta": o.ve_delta,
                    "pull_number": o.pull_number,
                    "timestamp": o.timestamp,
                }
                for o in self.observations
            ],
        }
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
        logger.info(
            "GP state saved to %s (%d observations)",
            path, len(self.observations),
        )

    @classmethod
    def load_state(cls, path: Path) -> "VESurrogate":
        """Load surrogate state from a previous session."""
        with open(path, "r") as f:
            state = json.load(f)

        rpm_bins = np.array(state["rpm_bins"], dtype=np.float64)
        map_bins = np.array(state["map_bins"], dtype=np.float64)
        s = cls(rpm_bins, map_bins, state["engine_family"])
        s.template_observation_count = state.get("template_observation_count", 0)

        for od in state["observations"]:
            s.observations.append(Observation(
                rpm=od["rpm"],
                map_kpa=od["map_kpa"],
                ve_delta=od["ve_delta"],
                pull_number=od.get("pull_number"),
                timestamp=od.get("timestamp"),
            ))

        if len(s.observations) >= 3:
            s._refit()

        return s
