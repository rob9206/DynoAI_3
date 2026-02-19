"""
DynoAI v3.0 — Next-Pull Advisor
==================================

Bayesian active learning for dyno test planning.  Instead of the
operator guessing which pull to do next, the system examines the GP
uncertainty map and recommends the single most informative operating
point.

Importance Weighting:
    - WOT cells (MAP > 90 kPa):   3x weight (power-critical)
    - Cruise cells (MAP 40-70):    2x weight (most time spent)
    - All other cells:             1x weight

Author: Thunderhorse Tuning / DynoAI
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from .gp_surrogate import VESurrogate
from .physics_constraints import PhysicsConstraints

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pull types
# ---------------------------------------------------------------------------
class PullType(Enum):
    """Classification of pull types."""
    WOT_SWEEP = "wot_sweep"
    PART_THROTTLE = "part_throttle"
    CRUISE = "cruise"
    TARGETED = "targeted"


class PullMode(Enum):
    """How the dyno should execute this pull."""
    ACCELERATION = "acceleration"   # WOT or partial-throttle accel sweep
    STEADY_STATE = "steady_state"   # RPM hold via eddy brake + throttle targeting MAP


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class PullRecommendation:
    """A single pull recommendation from the advisor."""
    rpm: float
    map_kpa: float
    gear: int = 3
    pull_number: int = 1
    pull_type: PullType = PullType.TARGETED
    pull_mode: PullMode = PullMode.ACCELERATION
    reason: str = ""
    expected_info_gain: float = 0.0
    remaining_uncertainty: float = 0.0
    throttle_pct: float = 0.0
    alternatives: List["PullRecommendation"] = field(default_factory=list)


@dataclass
class ConvergenceStatus:
    """Convergence status of the current session."""
    converged: bool
    max_uncertainty: float = 0.0
    mean_uncertainty: float = 0.0
    cells_above_threshold: int = 0
    total_cells: int = 0
    estimated_pulls_remaining: int = 0


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class PullAdvisor:
    """
    Bayesian active learning for dyno test planning.

    Selects the next pull that maximally reduces overall uncertainty,
    respecting physics constraints and operator vetoes.

    Usage:
        advisor = PullAdvisor(surrogate, constraints)
        rec = advisor.suggest_next_pull()
        plan = advisor.suggest_pull_sequence(max_pulls=12)
        status = advisor.check_convergence()
    """

    def __init__(
        self,
        surrogate: VESurrogate,
        constraints: PhysicsConstraints,
    ):
        self.surrogate = surrogate
        self.constraints = constraints
        self.pull_history: List[PullRecommendation] = []
        self._vetoed_points: List[Tuple[float, float, str]] = []

    # ------------------------------------------------------------------
    # Next pull suggestion
    # ------------------------------------------------------------------
    def suggest_next_pull(self) -> PullRecommendation:
        """
        Return the recommended next operating point.

        Uses maximum importance-weighted uncertainty acquisition function.
        Respects physics constraints and operator vetoes.
        """
        unc_map = self.surrogate.get_uncertainty_map()
        weights = self._importance_weights()
        weighted = unc_map * weights

        # Mask out vetoed points and unsafe points
        masked = self._apply_masks(weighted)

        # Find the best candidate
        idx = np.unravel_index(np.argmax(masked), masked.shape)
        rpm = float(self.surrogate.rpm_bins[idx[0]])
        map_kpa = float(self.surrogate.map_bins[idx[1]])

        # Determine pull type
        pull_type = self._classify_pull(rpm, map_kpa)

        # Find alternatives (top 3 excluding the best)
        alternatives = self._find_alternatives(masked, top_n=3)

        pull_number = len(self.pull_history) + 1

        rec = PullRecommendation(
            rpm=rpm,
            map_kpa=map_kpa,
            gear=self._recommend_gear(rpm),
            pull_number=pull_number,
            pull_type=pull_type,
            pull_mode=self._pull_mode_for_type(pull_type),
            reason=self._build_reason(rpm, map_kpa, unc_map, idx),
            expected_info_gain=float(masked[idx]),
            remaining_uncertainty=float(np.mean(unc_map)),
            throttle_pct=self._map_to_throttle(map_kpa),
            alternatives=alternatives,
        )

        return rec

    # ------------------------------------------------------------------
    # Pull sequence (non-adaptive initial plan)
    # ------------------------------------------------------------------
    def suggest_pull_sequence(self, max_pulls: int = 15) -> List[PullRecommendation]:
        """
        Pre-plan a full test sequence (greedy, non-adaptive).

        Starts with WOT sweeps (most critical for power), then fills
        remaining slots with highest-uncertainty part-throttle cells.

        Args:
            max_pulls: Maximum number of pulls in the plan

        Returns:
            Ordered list of PullRecommendation
        """
        sequence: List[PullRecommendation] = []

        # Phase 1: WOT sweep across safe RPM range
        wot_rpms = [
            r for r in self.surrogate.rpm_bins
            if r <= self.constraints.maps.max_test_rpm
        ]
        # Select a representative subset if too many
        if len(wot_rpms) > 7:
            step = max(1, len(wot_rpms) // 7)
            wot_rpms = wot_rpms[::step]

        for rpm in wot_rpms:
            if len(sequence) >= max_pulls:
                break
            sequence.append(PullRecommendation(
                rpm=float(rpm),
                map_kpa=100.0,
                gear=self._recommend_gear(float(rpm)),
                pull_number=len(sequence) + 1,
                pull_type=PullType.WOT_SWEEP,
                pull_mode=PullMode.ACCELERATION,
                reason=f"WOT sweep at {rpm:.0f} RPM",
                throttle_pct=100.0,
            ))

        # Phase 2: Fill remaining with highest-uncertainty cells
        remaining = max_pulls - len(sequence)
        if remaining > 0:
            unc_map = self.surrogate.get_uncertainty_map()
            weights = self._importance_weights()
            weighted = unc_map * weights

            # Zero out WOT row cells we already covered
            for rec in sequence:
                r_idx = self._nearest_idx(rec.rpm, self.surrogate.rpm_bins)
                m_idx = self._nearest_idx(rec.map_kpa, self.surrogate.map_bins)
                weighted[r_idx, m_idx] = 0.0

            for _ in range(remaining):
                if np.max(weighted) <= 0:
                    break
                idx = np.unravel_index(np.argmax(weighted), weighted.shape)
                rpm = float(self.surrogate.rpm_bins[idx[0]])
                map_kpa = float(self.surrogate.map_bins[idx[1]])

                # Check safety
                safe, _ = self.constraints.is_safe_to_test(rpm, map_kpa)
                if not safe:
                    weighted[idx] = 0.0
                    continue

                pull_type = self._classify_pull(rpm, map_kpa)
                sequence.append(PullRecommendation(
                    rpm=rpm,
                    map_kpa=map_kpa,
                    gear=self._recommend_gear(rpm),
                    pull_number=len(sequence) + 1,
                    pull_type=pull_type,
                    pull_mode=self._pull_mode_for_type(pull_type),
                    reason=f"High uncertainty at {rpm:.0f}/{map_kpa:.0f}",
                    throttle_pct=self._map_to_throttle(map_kpa),
                ))
                weighted[idx] = 0.0

        return sequence

    # ------------------------------------------------------------------
    # Convergence check
    # ------------------------------------------------------------------
    def check_convergence(self, threshold: float = 1.0) -> ConvergenceStatus:
        """
        Has the map converged?

        Args:
            threshold: Uncertainty threshold for convergence

        Returns:
            ConvergenceStatus with detailed metrics
        """
        unc_map = self.surrogate.get_uncertainty_map()
        weights = self._importance_weights()
        weighted = unc_map * weights

        max_unc = float(np.max(weighted))
        mean_unc = float(np.mean(unc_map))
        above = int(np.sum(weighted > threshold))
        total = unc_map.size

        # Estimate remaining pulls: ~1 pull per 3 cells above threshold
        est_remaining = max(0, (above + 2) // 3)

        # Require both low uncertainty and enough pulls before declaring converged
        min_observations = 6
        converged = (
            max_unc < threshold
            and len(self.surrogate.observations) >= min_observations
        )

        return ConvergenceStatus(
            converged=converged,
            max_uncertainty=max_unc,
            mean_uncertainty=mean_unc,
            cells_above_threshold=above,
            total_cells=total,
            estimated_pulls_remaining=est_remaining,
        )

    # ------------------------------------------------------------------
    # Operator veto
    # ------------------------------------------------------------------
    def operator_veto(self, rpm: float, map_kpa: float, reason: str = "") -> None:
        """
        Operator overrides a suggested point as unsafe or impractical.

        The vetoed point will be excluded from future suggestions.
        """
        self._vetoed_points.append((rpm, map_kpa, reason))
        logger.info(
            "Operator vetoed point: RPM=%.0f MAP=%.0f (%s)",
            rpm, map_kpa, reason or "no reason",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _importance_weights(self) -> NDArray[np.float64]:
        """Weight grid cells by calibration importance."""
        n_rpm = len(self.surrogate.rpm_bins)
        n_map = len(self.surrogate.map_bins)
        weights = np.ones((n_rpm, n_map))

        map_bins = np.array(self.surrogate.map_bins)
        rpm_bins = np.array(self.surrogate.rpm_bins)

        # WOT (MAP > 90 kPa): 3x weight
        wot_mask = map_bins > 90
        weights[:, wot_mask] *= 3.0

        # Cruise (MAP 40-70, RPM 2000-3500): 2x weight
        cruise_rpm = (rpm_bins >= 2000) & (rpm_bins <= 3500)
        cruise_map = (map_bins >= 40) & (map_bins <= 70)
        weights[np.ix_(cruise_rpm, cruise_map)] *= 2.0

        return weights

    def _apply_masks(self, weighted: NDArray[np.float64]) -> NDArray[np.float64]:
        """Mask out vetoed and unsafe points."""
        masked = weighted.copy()

        # Mask vetoed points
        for rpm, map_kpa, _ in self._vetoed_points:
            r_idx = self._nearest_idx(rpm, self.surrogate.rpm_bins)
            m_idx = self._nearest_idx(map_kpa, self.surrogate.map_bins)
            masked[r_idx, m_idx] = 0.0

        # Mask unsafe RPMs
        for i, rpm in enumerate(self.surrogate.rpm_bins):
            if rpm > self.constraints.maps.max_test_rpm:
                masked[i, :] = 0.0

        return masked

    def _find_alternatives(
        self,
        masked: NDArray[np.float64],
        top_n: int = 3,
    ) -> List[PullRecommendation]:
        """Find top-N alternative points (excluding the best)."""
        flat = masked.flatten()
        # Get indices of top values
        top_indices = np.argsort(flat)[::-1][1: top_n + 1]

        alts: List[PullRecommendation] = []
        for flat_idx in top_indices:
            if flat[flat_idx] <= 0:
                break
            idx = np.unravel_index(flat_idx, masked.shape)
            rpm = float(self.surrogate.rpm_bins[idx[0]])
            map_kpa = float(self.surrogate.map_bins[idx[1]])
            pt = self._classify_pull(rpm, map_kpa)
            alts.append(PullRecommendation(
                rpm=rpm,
                map_kpa=map_kpa,
                gear=self._recommend_gear(rpm),
                pull_type=pt,
                pull_mode=self._pull_mode_for_type(pt),
                reason=f"Alternative at {rpm:.0f}/{map_kpa:.0f}",
                throttle_pct=self._map_to_throttle(map_kpa),
            ))

        return alts

    def _classify_pull(self, rpm: float, map_kpa: float) -> PullType:
        """Classify a pull based on its operating point."""
        if map_kpa >= 90:
            return PullType.WOT_SWEEP
        if 40 <= map_kpa <= 70 and 2000 <= rpm <= 3500:
            return PullType.CRUISE
        return PullType.PART_THROTTLE

    @staticmethod
    def _pull_mode_for_type(pull_type: PullType) -> PullMode:
        """Derive execution mode from pull classification.

        WOT sweeps and generic targeted pulls use acceleration (inertia).
        Cruise and part-throttle zones benefit from steady-state mapping
        via eddy-brake RPM hold so the GP gets clean, non-transient data.
        """
        if pull_type in (PullType.CRUISE, PullType.PART_THROTTLE):
            return PullMode.STEADY_STATE
        return PullMode.ACCELERATION

    @staticmethod
    def _recommend_gear(rpm: float) -> int:
        """Recommend a gear based on target RPM."""
        if rpm < 2000:
            return 2
        if rpm < 3000:
            return 3
        if rpm < 4500:
            return 4
        return 5

    @staticmethod
    def _map_to_throttle(map_kpa: float) -> float:
        """Approximate throttle % from MAP."""
        return min(100.0, max(0.0, (map_kpa - 25) / 0.75))

    @staticmethod
    def _nearest_idx(value: float, bins: NDArray[np.float64]) -> int:
        return int(np.argmin(np.abs(bins - value)))

    def _build_reason(
        self,
        rpm: float,
        map_kpa: float,
        unc_map: NDArray[np.float64],
        idx: tuple,
    ) -> str:
        """Build a human-readable reason for the recommendation."""
        zone = self._classify_pull(rpm, map_kpa).value.replace("_", " ")
        unc = float(unc_map[idx])
        return (
            f"Highest uncertainty ({unc:.2f}) in {zone} zone "
            f"at {rpm:.0f} RPM / {map_kpa:.0f} kPa"
        )
