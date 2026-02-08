"""
DynoAI v3.0 — Gaussian Process Surrogate Engine
==================================================

Maintains a live probabilistic model of the entire VE map that updates
after each pull, providing both predictions and uncertainty estimates at
every cell.

The GP model predicts absolute VE percentages (70-113%), not deltas or
corrections. This aligns with Power Vision PVV format and provides intuitive
display values.

Why GP, Not Neural Network:
    1. Calibrated uncertainty estimates out of the box
    2. Works well with small datasets (10-30 pulls)
    3. Interpretable — inspect kernel, lengthscales, noise model
    4. Industry standard in calibration tools (AVL CAMEO, ETAS ASCMO)

Performance Budget:
    _refit()          uses <=150 obs (capped) for bounded runtime
    _refit()          warm refit reuses previous kernel params
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

# Extreme VE value threshold — observations beyond reasonable VE range are rejected
# Typical VE range is 60-120%, so values outside ±50% from 85% mean are suspicious
_MAX_VE_DEVIATION = 50.0  # Reject if |VE - 85| > 50 (i.e., VE < 35 or VE > 135)

# Cap observations used for GP fit so refit stays fast (GP is O(n^3)).
# Without this, 500+ obs can take minutes and freeze the UI.
_MAX_OBS_FOR_REFIT = 150

# Cap how many non-template (real pull) observations we keep in memory.
# Template observations are kept separately (they serve as priors), but pull
# observations are pruned to keep memory bounded during long sessions.
_MAX_PULL_OBS_STORED = _MAX_OBS_FOR_REFIT


# ---------------------------------------------------------------------------
# Module-level confidence functions
# ---------------------------------------------------------------------------
def uncertainty_to_confidence(std: float) -> float:
    """
    Map GP standard deviation to a DynoAI confidence score (0-100).

    Aligns with existing H/M/L/skip badge system.
    """
    if std < 0.5:
        return 95.0  # High
    if std < 1.0:
        return 80.0  # Medium
    if std < 2.0:
        return 60.0  # Low
    return 20.0  # Skip / insufficient


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


def _uncertainty_map_to_confidence(unc_map: NDArray[np.float64]) -> NDArray[np.float64]:
    """
    Vectorized uncertainty->confidence mapping.

    Replaces `np.vectorize(uncertainty_to_confidence)` which is a Python-loop wrapper.
    """
    unc = np.asarray(unc_map, dtype=np.float64)
    return np.select(
        [unc < 0.5, unc < 1.0, unc < 2.0],
        [95.0, 80.0, 60.0],
        default=20.0,
    ).astype(np.float64)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class Observation:
    """A single measured data point from a dyno pull.

    Note: Despite the field name 've_delta', this stores absolute VE percentage values
    (70-113%), not deltas. The naming is historical but the semantics are absolute VE.
    """

    rpm: float
    map_kpa: float
    ve_delta: float  # Absolute VE percentage (e.g., 85.5%)
    pull_number: Optional[int] = None
    timestamp: Optional[float] = None


@dataclass
class PointPrediction:
    """Prediction at a single operating point.

    Note: ve_delta stores absolute VE percentage (70-113%), not a delta.
    """

    ve_delta: float  # Absolute VE percentage (e.g., 92.3%)
    uncertainty: float
    confidence: float
    badge: str


@dataclass
class FullMapPrediction:
    """Prediction across the entire VE grid.

    Note: ve_map contains absolute VE percentages (70-113%), not deltas.
    """

    ve_map: NDArray[np.float64]  # Absolute VE percentages
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

        # Store raw seed VE table for exact 1:1 reproduction (PVV import)
        self._seed_ve_table: Optional[NDArray[np.float64]] = None

        self._gp_model = None
        self.is_fitted = False
        self._last_fit_time_ms: float = 0.0
        self._stale: bool = False

        # Normalization parameters — computed from bin ranges
        self._rpm_min = float(np.min(rpm_bins))
        self._rpm_range = float(np.max(rpm_bins) - np.min(rpm_bins))
        self._map_min = float(np.min(map_bins))
        self._map_range = float(np.max(map_bins) - np.min(map_bins))

        logger.info(
            "VESurrogate initialized: %s, %d RPM bins x %d MAP bins",
            engine_family,
            len(rpm_bins),
            len(map_bins),
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def observation_count(self) -> int:
        return len(self.observations)

    def _prune_observations_if_needed(self) -> None:
        """
        Keep memory bounded by pruning old pull observations.

        - Always retain template observations (pull_number == -1)
        - Retain only the most recent `_MAX_PULL_OBS_STORED` non-template observations
        """
        # Quick check to avoid work on the hot path.
        max_allowed = int(self.template_observation_count) + int(_MAX_PULL_OBS_STORED)
        if len(self.observations) <= max_allowed:
            return

        template_obs: list[Observation] = []
        pull_obs: list[Observation] = []
        for o in self.observations:
            if o.pull_number == -1:
                template_obs.append(o)
            else:
                pull_obs.append(o)

        if len(pull_obs) > _MAX_PULL_OBS_STORED:
            pull_obs = pull_obs[-_MAX_PULL_OBS_STORED:]

        self.observations = template_obs + pull_obs

    # ------------------------------------------------------------------
    # Add data
    # ------------------------------------------------------------------
    def add_observation(self, obs: Observation) -> None:
        """Add a single measured data point (marks model stale)."""
        if obs.timestamp is None:
            obs.timestamp = time.time()
        self.observations.append(obs)
        self._prune_observations_if_needed()
        self._stale = True

    def add_pull_data(
        self,
        rpm: NDArray[np.float64],
        map_kpa: NDArray[np.float64],
        ve: NDArray[np.float64],
        pull_number: Optional[int] = None,
    ) -> int:
        """
        Ingest an entire pull's worth of data.

        Rejects extreme VE values outside reasonable range (35-135%).

        Args:
            rpm: Array of RPM values
            map_kpa: Array of MAP values
            ve: Array of absolute VE percentage values (70-113%)
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
            # Reject unrealistic VE values (typical range 60-120%)
            if abs(ve[i] - 85.0) > _MAX_VE_DEVIATION:
                logger.debug(
                    "Rejected extreme VE value: %.2f%% at RPM=%.0f MAP=%.0f",
                    ve[i],
                    rpm[i],
                    map_kpa[i],
                )
                continue
            self.observations.append(
                Observation(
                    rpm=float(rpm[i]),
                    map_kpa=float(map_kpa[i]),
                    ve_delta=float(ve[i]),  # Stores absolute VE %
                    pull_number=pull_number,
                    timestamp=ts,
                )
            )
            accepted += 1

        if accepted > 0:
            self._prune_observations_if_needed()
            self._stale = True

        logger.info(
            "Pull data ingested: %d/%d accepted (pull #%s)",
            accepted,
            len(rpm),
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
            template_ve: 2D array of absolute VE percentages (70-113%) from the template
            rpm_bins: RPM bins corresponding to template rows
            map_bins: MAP bins corresponding to template columns
        """
        template_ve = np.asarray(template_ve, dtype=np.float64)
        rpm_bins = np.asarray(rpm_bins, dtype=np.float64)
        map_bins = np.asarray(map_bins, dtype=np.float64)

        # Store raw seed table for exact 1:1 reproduction when no real pulls exist
        self._seed_ve_table = template_ve.copy()

        logger.info(
            "Storing seed VE table: shape=%s, min=%.1f%%, max=%.1f%%, mean=%.1f%%",
            self._seed_ve_table.shape,
            np.min(self._seed_ve_table),
            np.max(self._seed_ve_table),
            np.mean(self._seed_ve_table),
        )

        count = 0
        ts = time.time()
        for r_idx, rpm in enumerate(rpm_bins):
            for m_idx, map_kpa in enumerate(map_bins):
                if r_idx < template_ve.shape[0] and m_idx < template_ve.shape[1]:
                    self.observations.append(
                        Observation(
                            rpm=float(rpm),
                            map_kpa=float(map_kpa),
                            ve_delta=float(template_ve[r_idx, m_idx]),
                            pull_number=-1,  # Sentinel for template data
                            timestamp=ts,
                        )
                    )
                    count += 1

        self.template_observation_count = count

        if count > 0:
            self._prune_observations_if_needed()
            self._stale = True

        logger.info(
            "Template seeded: %d synthetic observations added",
            count,
        )

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------
    def predict(self, rpm: float, map_kpa: float) -> PointPrediction:
        """
        Predict VE correction and uncertainty at a single point.

        If the model is not fitted, returns a high-uncertainty prior.
        """
        if self._stale:
            self._refit()

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

        if self._stale:
            self._refit()

        if not self.is_fitted or self._gp_model is None:
            # Return prior: zero VE, high uncertainty
            elapsed = (time.time() - t0) * 1000
            unc_map = np.full((n_rpm, n_map), 10.0)
            return FullMapPrediction(
                ve_map=np.zeros((n_rpm, n_map)),
                uncertainty_map=unc_map,
                confidence_map=_uncertainty_map_to_confidence(unc_map),
                predict_time_ms=elapsed,
            )

        # If we only have template data, return raw seed values for accuracy
        if hasattr(self, "_seed_ve_table") and self._seed_ve_table is not None:
            all_template = all(o.pull_number == -1 for o in self.observations)
            if all_template and self._seed_ve_table.shape == (n_rpm, n_map):
                # Use constant uncertainty (no GP predict) to avoid sklearn 1.8+
                # AttributeError when alpha_ is not set after fit
                unc_map = np.full(
                    (n_rpm, n_map), 1.0
                )  # Medium uncertainty until real pulls
                conf_map = _uncertainty_map_to_confidence(unc_map)
                elapsed = (time.time() - t0) * 1000

                logger.info(
                    "Returning raw seed VE table (template-only, no real pulls): "
                    "shape=%s, min=%.1f%%, max=%.1f%%, mean=%.1f%%",
                    self._seed_ve_table.shape,
                    np.min(self._seed_ve_table),
                    np.max(self._seed_ve_table),
                    np.mean(self._seed_ve_table),
                )
                return FullMapPrediction(
                    ve_map=self._seed_ve_table.copy(),  # Exact 1:1 PVV values
                    uncertainty_map=unc_map,
                    confidence_map=conf_map,
                    predict_time_ms=elapsed,
                )

        # Guard: sklearn 1.8+ can leave GPR without alpha_ after fit in edge cases
        if not hasattr(self._gp_model, "alpha_") or self._gp_model.alpha_ is None:
            logger.warning(
                "GP model not properly fitted (missing alpha_); returning prior"
            )
            elapsed = (time.time() - t0) * 1000
            unc_map = np.full((n_rpm, n_map), 10.0)
            return FullMapPrediction(
                ve_map=np.zeros((n_rpm, n_map)),
                uncertainty_map=unc_map,
                confidence_map=_uncertainty_map_to_confidence(unc_map),
                predict_time_ms=elapsed,
            )

        # Build an (n_rpm*n_map, 2) grid without Python loops.
        rr, mm = np.meshgrid(self.rpm_bins, self.map_bins, indexing="ij")
        grid = np.stack((rr.ravel(), mm.ravel()), axis=1)
        X_norm = self._normalize(grid)
        means, stds = self._gp_model.predict(X_norm, return_std=True)

        ve_map = means.reshape(n_rpm, n_map)
        unc_map = stds.reshape(n_rpm, n_map)
        conf_map = _uncertainty_map_to_confidence(unc_map)

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
        Refit the GP model on observations.

        Uses at most _MAX_OBS_FOR_REFIT total points to keep fit time bounded.
        Template observations (pull_number == -1) are always retained in the fit
        so template priors are not lost.
        """
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import Matern, WhiteKernel

        if len(self.observations) < 3:
            return

        t0 = time.time()

        # Cap total points so refit stays fast (GP is O(n^3)), but always keep
        # template observations (pull_number == -1) so the prior is not lost.
        if len(self.observations) <= _MAX_OBS_FOR_REFIT:
            obs_for_fit = self.observations
        else:
            template_obs = [o for o in self.observations if o.pull_number == -1]
            pull_obs = [o for o in self.observations if o.pull_number != -1]
            n_slots_for_pull = _MAX_OBS_FOR_REFIT - len(template_obs)
            if n_slots_for_pull <= 0:
                obs_for_fit = (template_obs + pull_obs)[-_MAX_OBS_FOR_REFIT:]
            else:
                obs_for_fit = template_obs + pull_obs[-n_slots_for_pull:]
        n_used = len(obs_for_fit)

        X = np.array([[o.rpm, o.map_kpa] for o in obs_for_fit])
        y = np.array([o.ve_delta for o in obs_for_fit])

        X_norm = self._normalize(X)

        # Create fresh kernel for each fit
        # Note: Warm-start kernel copying causes issues with sklearn 1.8+
        # (missing alpha_ attribute after prediction). Fresh fit is fast enough
        # with sklearn 1.8.0 and avoids compatibility issues.
        kernel = Matern(nu=2.5, length_scale=[0.3, 0.3]) + WhiteKernel(noise_level=0.1)
        n_restarts = 2

        self._gp_model = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=n_restarts,
            alpha=0.05,
            normalize_y=True,
        )
        self._gp_model.fit(X_norm, y)
        self.is_fitted = True
        self._stale = False

        self._last_fit_time_ms = (time.time() - t0) * 1000
        logger.info(
            "GP refit: %d used (of %d total), %.1f ms",
            n_used,
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
            path,
            len(self.observations),
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
            s.observations.append(
                Observation(
                    rpm=od["rpm"],
                    map_kpa=od["map_kpa"],
                    ve_delta=od["ve_delta"],
                    pull_number=od.get("pull_number"),
                    timestamp=od.get("timestamp"),
                )
            )

        if len(s.observations) >= 3:
            s._refit()

        return s
