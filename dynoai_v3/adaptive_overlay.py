"""
DynoAI v3.0 — Bounded Adaptive Overlay
========================================

Runtime correction layer that allows calibrations to self-improve
within strictly defined physics bounds after the bike leaves the shop.

FIVE RULES (non-negotiable):
    1. Corrections are BOUNDED LINEAR only (gain + offset per cell)
    2. All corrections are LOGGED with full context
    3. MASTER KILL SWITCH reverts all corrections to zero instantly
    4. Corrections DECAY if not reinforced within 30 operating hours
    5. Physics constraints are LOOKUP TABLES the tuner can inspect

DOES NOT REPLACE:
    - Base calibration from dyno session (always preserved)
    - ve_operations.py clamp rules (still apply independently)
    - Any existing safety mechanisms

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

from .physics_constraints import PhysicsConstraints

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Correction event data
# ---------------------------------------------------------------------------
@dataclass
class CorrectionEvent:
    """A single logged correction."""
    timestamp: float
    rpm: float
    map_kpa: float
    iat_f: float
    ect_f: float
    parameter: str           # "fuel" or "timing"
    raw_correction: float    # Before bounding
    applied_correction: float  # After bounding
    trigger: str             # What caused the correction
    operating_hours: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "rpm": self.rpm,
            "map_kpa": self.map_kpa,
            "iat_f": self.iat_f,
            "ect_f": self.ect_f,
            "parameter": self.parameter,
            "raw_correction": round(self.raw_correction, 4),
            "applied_correction": round(self.applied_correction, 4),
            "trigger": self.trigger,
            "operating_hours": round(self.operating_hours, 2),
        }


@dataclass
class OverlayStatus:
    """Current state of the overlay system."""
    enabled: bool
    fuel_corrections_active: int     # Cells with non-zero fuel correction
    timing_corrections_active: int   # Cells with non-zero timing correction
    max_fuel_correction_pct: float
    max_timing_correction_deg: float
    total_correction_events: int
    operating_hours: float
    last_correction_time: Optional[float]

    def summary(self) -> str:
        if not self.enabled:
            return "Overlay DISABLED (kill switch active)"
        return (
            f"Overlay active: {self.fuel_corrections_active} fuel cells, "
            f"{self.timing_corrections_active} timing cells | "
            f"Max fuel: ±{self.max_fuel_correction_pct:.2f}% | "
            f"Max timing: ±{self.max_timing_correction_deg:.2f}° | "
            f"Events: {self.total_correction_events} | "
            f"Hours: {self.operating_hours:.1f}"
        )


# ---------------------------------------------------------------------------
# Proportional gain for feedback corrections
# ---------------------------------------------------------------------------
# AFR error of 1.0 (e.g., target 12.8, actual 13.8) → ~2% VE correction
K_FUEL_PROPORTIONAL = 2.0

# Knock detected → immediate retard (degrees per knock severity unit)
K_TIMING_KNOCK_RETARD = -3.0

# Learning rate: how fast corrections accumulate (0-1, lower = more conservative)
LEARNING_RATE = 0.3


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class BoundedOverlay:
    """
    Runtime correction layer with hard safety bounds.

    Corrections are linear, bounded, logged, and reversible.
    The overlay CANNOT make the calibration worse than the base map's
    safety envelope — it can only adjust within the bounds.

    Usage:
        overlay = BoundedOverlay(
            base_ve=base_ve_table,
            constraints=physics_constraints,
        )

        # During riding — compute a fuel correction
        correction = overlay.compute_fuel_correction(
            rpm=3500, map_kpa=95,
            current_afr=13.2, target_afr=12.8,
            ect_f=420, iat_f=95,
        )

        # Get the complete corrected VE table
        corrected_ve = overlay.get_corrected_table()

        # Emergency: revert everything
        overlay.kill_switch()

        # Export log for shop review
        log_df = overlay.export_correction_log()
    """

    def __init__(
        self,
        base_ve: NDArray[np.float64],
        rpm_bins: NDArray[np.float64],
        map_bins: NDArray[np.float64],
        constraints: PhysicsConstraints,
    ):
        self._base_ve = np.array(base_ve, dtype=np.float64, copy=True)  # READ-ONLY copy
        self._rpm_bins = np.array(rpm_bins, dtype=np.float64)
        self._map_bins = np.array(map_bins, dtype=np.float64)
        self.constraints = constraints
        n_rpm, n_map = len(rpm_bins), len(map_bins)

        # Correction grids — initialized to zero (no corrections)
        self._fuel_corrections = np.zeros((n_rpm, n_map), dtype=np.float64)
        self._timing_corrections = np.zeros((n_rpm, n_map), dtype=np.float64)

        # Correction age tracking — hours since last reinforcement per cell
        self._fuel_last_reinforced = np.full((n_rpm, n_map), -1.0)  # -1 = never
        self._timing_last_reinforced = np.full((n_rpm, n_map), -1.0)

        # State
        self.enabled = True
        self._correction_log: List[CorrectionEvent] = []
        self._operating_hours = 0.0
        self._kill_switch_active = False

        # Limits from constraints
        self._max_fuel_gain = constraints.maps.max_fuel_gain  # e.g., 0.05 = ±5%
        self._max_timing_offset = constraints.maps.max_timing_offset  # e.g., 2.0°
        self._decay_rate = constraints.maps.correction_decay_rate  # e.g., 0.10
        self._decay_threshold = constraints.maps.correction_decay_threshold_hrs  # e.g., 30

        logger.info(
            "BoundedOverlay initialized: %dx%d grid, "
            "max_fuel=±%.1f%%, max_timing=±%.1f°, "
            "decay_rate=%.0f%%/hr after %.0fhr",
            n_rpm, n_map,
            self._max_fuel_gain * 100,
            self._max_timing_offset,
            self._decay_rate * 100,
            self._decay_threshold,
        )

    # ------------------------------------------------------------------
    # Rule 3: MASTER KILL SWITCH
    # ------------------------------------------------------------------
    def kill_switch(self) -> None:
        """
        INSTANTLY revert all corrections to zero.

        The base calibration is always preserved. The overlay is disabled.
        This is the emergency exit.
        """
        self._fuel_corrections[:] = 0.0
        self._timing_corrections[:] = 0.0
        self._fuel_last_reinforced[:] = -1.0
        self._timing_last_reinforced[:] = -1.0
        self.enabled = False
        self._kill_switch_active = True

        self._log_event(
            rpm=0, map_kpa=0, iat_f=0, ect_f=0,
            parameter="SYSTEM",
            raw_correction=0.0, applied_correction=0.0,
            trigger="KILL_SWITCH_ACTIVATED",
        )
        logger.warning("KILL SWITCH ACTIVATED — all corrections zeroed, overlay disabled")

    def re_enable(self) -> None:
        """Re-enable the overlay after kill switch. Corrections start from zero."""
        self.enabled = True
        self._kill_switch_active = False
        self._log_event(
            rpm=0, map_kpa=0, iat_f=0, ect_f=0,
            parameter="SYSTEM",
            raw_correction=0.0, applied_correction=0.0,
            trigger="OVERLAY_RE_ENABLED",
        )
        logger.info("Overlay re-enabled. All corrections start from zero.")

    # ------------------------------------------------------------------
    # Public API: fuel correction
    # ------------------------------------------------------------------
    def compute_fuel_correction(
        self,
        rpm: float,
        map_kpa: float,
        current_afr: float,
        target_afr: float,
        ect_f: float,
        iat_f: float = 70.0,
    ) -> float:
        """
        Compute bounded fuel correction from closed-loop AFR feedback.

        Rule 1: Linear correction = K * error, bounded to ±max_fuel_gain
        Rule 5: Bounds are from physics constraint lookup tables

        Args:
            rpm: Current engine RPM
            map_kpa: Current manifold pressure (kPa)
            current_afr: Measured AFR from wideband O2
            target_afr: Target AFR from calibration
            ect_f: Engine/cylinder head temperature (°F)
            iat_f: Intake air temperature (°F)

        Returns:
            Applied fuel correction as a percentage (e.g., 2.5 = +2.5% fuel)
        """
        if not self.enabled:
            return 0.0

        # Calculate raw correction
        # If current > target (too lean), we need MORE fuel → positive correction
        # If current < target (too rich), we need LESS fuel → negative correction
        afr_error = current_afr - target_afr
        raw_correction = afr_error * K_FUEL_PROPORTIONAL

        # Bound correction (Rule 1)
        max_corr = self._max_fuel_gain * 100.0  # Convert to %
        bounded = float(np.clip(raw_correction, -max_corr, +max_corr))

        # Physics override: forced enrichment at high ECT (Rule 5)
        needs_enrich, enrich_amount = self.constraints.needs_enrichment_override(ect_f)
        if needs_enrich:
            bounded = max(bounded, enrich_amount)

        # Apply learning rate for gradual adaptation
        r_idx = self._nearest_idx(rpm, self._rpm_bins)
        m_idx = self._nearest_idx(map_kpa, self._map_bins)

        current = self._fuel_corrections[r_idx, m_idx]
        new_correction = current + LEARNING_RATE * (bounded - current)
        new_correction = float(np.clip(new_correction, -max_corr, +max_corr))

        self._fuel_corrections[r_idx, m_idx] = new_correction
        self._fuel_last_reinforced[r_idx, m_idx] = self._operating_hours

        # Log (Rule 2)
        self._log_event(
            rpm=rpm, map_kpa=map_kpa, iat_f=iat_f, ect_f=ect_f,
            parameter="fuel",
            raw_correction=raw_correction,
            applied_correction=new_correction,
            trigger=f"AFR feedback: target={target_afr:.1f}, actual={current_afr:.1f}",
        )

        return new_correction

    # ------------------------------------------------------------------
    # Public API: timing correction
    # ------------------------------------------------------------------
    def compute_timing_correction(
        self,
        rpm: float,
        map_kpa: float,
        knock_detected: bool,
        knock_severity: float = 0.0,
        ect_f: float = 200.0,
        iat_f: float = 70.0,
    ) -> float:
        """
        Compute bounded timing correction.

        Timing corrections are RETARD ONLY when knock is detected.
        The overlay never advances timing beyond the base map.

        Args:
            rpm: Current engine RPM
            map_kpa: Current manifold pressure
            knock_detected: Whether knock was detected this cycle
            knock_severity: 0.0–1.0 severity rating
            ect_f: Engine temperature
            iat_f: Intake air temperature

        Returns:
            Timing correction in degrees (negative = retard)
        """
        if not self.enabled:
            return 0.0

        r_idx = self._nearest_idx(rpm, self._rpm_bins)
        m_idx = self._nearest_idx(map_kpa, self._map_bins)

        if knock_detected:
            # Immediate retard proportional to severity
            raw_retard = K_TIMING_KNOCK_RETARD * max(knock_severity, 0.3)
            max_retard = -self._max_timing_offset  # Negative = retard
            bounded = max(raw_retard, max_retard)  # More negative = more retard

            current = self._timing_corrections[r_idx, m_idx]
            new_correction = min(current, bounded)  # Only retard more, never advance
            new_correction = float(np.clip(
                new_correction, -self._max_timing_offset, 0.0
            ))

            self._timing_corrections[r_idx, m_idx] = new_correction
            self._timing_last_reinforced[r_idx, m_idx] = self._operating_hours

            self._log_event(
                rpm=rpm, map_kpa=map_kpa, iat_f=iat_f, ect_f=ect_f,
                parameter="timing",
                raw_correction=raw_retard,
                applied_correction=new_correction,
                trigger=f"KNOCK detected (severity={knock_severity:.2f})",
            )
            return new_correction

        # No knock — allow slow recovery toward base timing
        current = self._timing_corrections[r_idx, m_idx]
        if current < 0:
            # Recover at 10% per evaluation toward zero
            recovered = current * 0.9
            if abs(recovered) < 0.1:
                recovered = 0.0
            self._timing_corrections[r_idx, m_idx] = recovered

        return float(self._timing_corrections[r_idx, m_idx])

    # ------------------------------------------------------------------
    # Public API: get corrected tables
    # ------------------------------------------------------------------
    def get_corrected_ve_table(self) -> NDArray[np.float64]:
        """
        Return the base VE table with fuel corrections applied.

        corrected = base * (1 + fuel_correction/100)
        """
        if not self.enabled:
            return self._base_ve.copy()
        return self._base_ve * (1.0 + self._fuel_corrections / 100.0)

    def get_fuel_corrections(self) -> NDArray[np.float64]:
        """Return raw fuel correction grid (% values)."""
        return self._fuel_corrections.copy()

    def get_timing_corrections(self) -> NDArray[np.float64]:
        """Return raw timing correction grid (degrees, negative = retard)."""
        return self._timing_corrections.copy()

    # ------------------------------------------------------------------
    # Rule 4: Correction decay
    # ------------------------------------------------------------------
    def apply_decay(self, current_hours: float) -> int:
        """
        Decay corrections that haven't been reinforced recently.

        Rule 4: If a correction hasn't been reinforced in
        decay_threshold hours, it decays toward zero at decay_rate
        per hour.

        Call this periodically (e.g., every 10 minutes of operation).

        Returns:
            Number of cells that had corrections decayed
        """
        if not self.enabled:
            return 0

        self._operating_hours = current_hours
        decayed_count = 0

        # Decay fuel corrections
        for r in range(self._fuel_corrections.shape[0]):
            for m in range(self._fuel_corrections.shape[1]):
                last = self._fuel_last_reinforced[r, m]
                if last < 0 or abs(self._fuel_corrections[r, m]) < 0.01:
                    continue
                hours_since = current_hours - last
                if hours_since > self._decay_threshold:
                    excess_hours = hours_since - self._decay_threshold
                    decay_factor = max(0.0, 1.0 - self._decay_rate * excess_hours)
                    old = self._fuel_corrections[r, m]
                    self._fuel_corrections[r, m] *= decay_factor
                    if abs(self._fuel_corrections[r, m]) < 0.01:
                        self._fuel_corrections[r, m] = 0.0
                    if old != self._fuel_corrections[r, m]:
                        decayed_count += 1

        # Decay timing corrections (same logic)
        for r in range(self._timing_corrections.shape[0]):
            for m in range(self._timing_corrections.shape[1]):
                last = self._timing_last_reinforced[r, m]
                if last < 0 or abs(self._timing_corrections[r, m]) < 0.01:
                    continue
                hours_since = current_hours - last
                if hours_since > self._decay_threshold:
                    excess_hours = hours_since - self._decay_threshold
                    decay_factor = max(0.0, 1.0 - self._decay_rate * excess_hours)
                    old = self._timing_corrections[r, m]
                    self._timing_corrections[r, m] *= decay_factor
                    if abs(self._timing_corrections[r, m]) < 0.01:
                        self._timing_corrections[r, m] = 0.0
                    if old != self._timing_corrections[r, m]:
                        decayed_count += 1

        if decayed_count > 0:
            logger.info(
                "Decay applied at %.1f hours: %d cells decayed",
                current_hours, decayed_count,
            )
        return decayed_count

    # ------------------------------------------------------------------
    # Rule 2: Logging & export
    # ------------------------------------------------------------------
    def export_correction_log(self) -> List[Dict[str, Any]]:
        """Export full correction history as list of dicts (for CSV/DataFrame)."""
        return [e.to_dict() for e in self._correction_log]

    def save_correction_log(self, path: Path) -> None:
        """Save correction log to JSON file."""
        with open(path, "w") as f:
            json.dump(self.export_correction_log(), f, indent=2)
        logger.info("Correction log saved to %s (%d events)", path, len(self._correction_log))

    def get_status(self) -> OverlayStatus:
        """Get current overlay status for UI display."""
        fuel_active = int(np.sum(np.abs(self._fuel_corrections) > 0.01))
        timing_active = int(np.sum(np.abs(self._timing_corrections) > 0.01))

        return OverlayStatus(
            enabled=self.enabled,
            fuel_corrections_active=fuel_active,
            timing_corrections_active=timing_active,
            max_fuel_correction_pct=float(np.max(np.abs(self._fuel_corrections))),
            max_timing_correction_deg=float(np.max(np.abs(self._timing_corrections))),
            total_correction_events=len(self._correction_log),
            operating_hours=self._operating_hours,
            last_correction_time=(
                self._correction_log[-1].timestamp if self._correction_log else None
            ),
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def save_state(self, path: Path) -> None:
        """Save overlay state for persistence across sessions."""
        state = {
            "enabled": self.enabled,
            "kill_switch_active": self._kill_switch_active,
            "operating_hours": self._operating_hours,
            "fuel_corrections": self._fuel_corrections.tolist(),
            "timing_corrections": self._timing_corrections.tolist(),
            "fuel_last_reinforced": self._fuel_last_reinforced.tolist(),
            "timing_last_reinforced": self._timing_last_reinforced.tolist(),
        }
        with open(path, "w") as f:
            json.dump(state, f, indent=2)

    def load_state(self, path: Path) -> None:
        """Load overlay state from a previous session."""
        with open(path, "r") as f:
            state = json.load(f)
        self.enabled = state["enabled"]
        self._kill_switch_active = state["kill_switch_active"]
        self._operating_hours = state["operating_hours"]
        self._fuel_corrections = np.array(state["fuel_corrections"])
        self._timing_corrections = np.array(state["timing_corrections"])
        self._fuel_last_reinforced = np.array(state["fuel_last_reinforced"])
        self._timing_last_reinforced = np.array(state["timing_last_reinforced"])

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _log_event(self, **kwargs) -> None:
        """Record a correction event."""
        event = CorrectionEvent(
            timestamp=time.time(),
            operating_hours=self._operating_hours,
            **kwargs,
        )
        self._correction_log.append(event)

    @staticmethod
    def _nearest_idx(value: float, bins: NDArray[np.float64]) -> int:
        return int(np.argmin(np.abs(bins - value)))
