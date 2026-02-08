"""
DynoAI v3.0 — Physics Constraints
====================================

Engine-family-specific safety boundaries stored as conventional lookup
tables.  These are the hard limits that no adaptive system can exceed.
They encode the collective tuning knowledge of Thunderhorse into data
structures that are inspectable, editable, and auditable.

Key principle:
    These constraint files are the most valuable IP in the system.
    They represent hundreds of hours of dyno experience encoded as data.

Author: Thunderhorse Tuning / DynoAI
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known engine families
# ---------------------------------------------------------------------------
KNOWN_FAMILIES: List[str] = [
    "m8_107",
    "m8_114",
    "m8_117",
    "m8_131",
    "tc_88",
    "tc_96",
    "tc_103",
    "tc_110",
    "revmax_975",
    "revmax_1250",
    "evo_1200",
]


# ---------------------------------------------------------------------------
# Safety violation dataclasses
# ---------------------------------------------------------------------------
@dataclass
class Violation:
    """A single safety violation."""

    parameter: str  # e.g. "afr", "timing", "rpm"
    reason: str  # Human-readable explanation
    value: float  # The offending value
    limit: float  # The boundary that was exceeded


@dataclass
class SafetyVerdict:
    """Result of a safety check on a single operating point."""

    safe: bool
    violations: List[Violation] = field(default_factory=list)

    @property
    def violation_count(self) -> int:
        return len(self.violations)


@dataclass
class ClampEvent:
    """Record of a clamped cell during table validation."""

    rpm_idx: int
    map_idx: int
    original_value: float
    clamped_value: float
    limit: float


# ---------------------------------------------------------------------------
# Constraint maps — all per-family limits in one dataclass
# ---------------------------------------------------------------------------
@dataclass
class ConstraintMaps:
    """All per-family safety limits in one inspectable structure."""

    engine_family: str
    cooling_type: str  # "air", "oil", "liquid"

    # Grid definition
    rpm_bins: List[float] = field(default_factory=list)
    map_bins: List[float] = field(default_factory=list)

    # Timing limits
    max_spark_advance_deg: float = 28.0  # Max base advance (BTDC)
    knock_retard_limit_deg: float = -8.0  # Max retard from base

    # AFR limits
    min_afr_wot: float = 12.2  # Minimum AFR at WOT
    max_afr_wot: float = 13.2  # Maximum AFR at WOT
    decel_min_afr: float = 13.0  # Minimum AFR during decel

    # Thermal limits
    ect_enrichment_trigger_f: float = 475.0  # ECT that triggers enrichment
    ect_enrichment_amount_pct: float = 5.0  # Enrichment percentage
    max_egt_f: float = 1450.0  # Maximum EGT

    # Correction limits
    max_ve_correction_pct: float = 7.0  # Standard VE clamp (±%)
    max_fuel_gain: float = 0.05  # Adaptive overlay max (±5%)
    max_timing_offset: float = 2.0  # Adaptive timing max (±degrees)

    # Decay parameters
    correction_decay_rate: float = 0.10  # 10% per hour past threshold
    correction_decay_threshold_hrs: float = 30.0

    # Operating envelope
    max_test_rpm: float = 6000.0  # Max RPM for testing

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ConstraintMaps":
        return cls(**d)


# ---------------------------------------------------------------------------
# Default constraint maps per engine family
# ---------------------------------------------------------------------------
def _default_m8_air_cooled(family: str) -> ConstraintMaps:
    """Defaults for M8 air-cooled engines (107, 114, 117)."""
    displacement_map = {"m8_107": 107, "m8_114": 114, "m8_117": 117}
    return ConstraintMaps(
        engine_family=family,
        cooling_type="air",
        rpm_bins=[1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500],
        map_bins=[30, 40, 50, 60, 70, 80, 90, 100, 105],
        max_spark_advance_deg=28.0,
        knock_retard_limit_deg=-8.0,
        min_afr_wot=12.2,
        max_afr_wot=13.2,
        decel_min_afr=13.0,
        ect_enrichment_trigger_f=475.0,
        ect_enrichment_amount_pct=5.0,
        max_egt_f=1450.0,
        max_ve_correction_pct=7.0,
        max_fuel_gain=0.05,
        max_timing_offset=2.0,
        correction_decay_rate=0.10,
        correction_decay_threshold_hrs=30.0,
        max_test_rpm=6000.0,
    )


def _default_m8_oil_cooled(family: str) -> ConstraintMaps:
    """Defaults for M8 131 oil-cooled engine."""
    return ConstraintMaps(
        engine_family=family,
        cooling_type="oil",
        rpm_bins=[1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500],
        map_bins=[30, 40, 50, 60, 70, 80, 90, 100, 105],
        max_spark_advance_deg=30.0,
        knock_retard_limit_deg=-8.0,
        min_afr_wot=12.4,
        max_afr_wot=13.2,
        decel_min_afr=13.0,
        ect_enrichment_trigger_f=450.0,
        ect_enrichment_amount_pct=5.0,
        max_egt_f=1450.0,
        max_ve_correction_pct=7.0,
        max_fuel_gain=0.05,
        max_timing_offset=2.0,
        correction_decay_rate=0.10,
        correction_decay_threshold_hrs=30.0,
        max_test_rpm=6000.0,
    )


def _default_revmax_liquid(family: str) -> ConstraintMaps:
    """Defaults for RevMax 1250 liquid-cooled (Sportster S / Pan America)."""
    return ConstraintMaps(
        engine_family=family,
        cooling_type="liquid",
        rpm_bins=[1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000],
        map_bins=[30, 40, 50, 60, 70, 80, 90, 100, 105],
        max_spark_advance_deg=36.0,
        knock_retard_limit_deg=-6.0,
        min_afr_wot=12.4,
        max_afr_wot=13.5,
        decel_min_afr=13.5,
        ect_enrichment_trigger_f=230.0,
        ect_enrichment_amount_pct=5.0,
        max_egt_f=1550.0,
        max_ve_correction_pct=7.0,
        max_fuel_gain=0.05,
        max_timing_offset=2.0,
        correction_decay_rate=0.10,
        correction_decay_threshold_hrs=30.0,
        max_test_rpm=9000.0,
    )


def _default_revmax_975(family: str) -> ConstraintMaps:
    """Defaults for RevMax 975T liquid-cooled (Nightster)."""
    return ConstraintMaps(
        engine_family=family,
        cooling_type="liquid",
        rpm_bins=[1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000],
        map_bins=[30, 40, 50, 60, 70, 80, 90, 100, 105],
        max_spark_advance_deg=36.0,
        knock_retard_limit_deg=-6.0,
        min_afr_wot=12.4,
        max_afr_wot=13.4,
        decel_min_afr=13.5,
        ect_enrichment_trigger_f=230.0,
        ect_enrichment_amount_pct=5.0,
        max_egt_f=1550.0,
        max_ve_correction_pct=7.0,
        max_fuel_gain=0.05,
        max_timing_offset=2.0,
        correction_decay_rate=0.10,
        correction_decay_threshold_hrs=30.0,
        max_test_rpm=8500.0,
    )


def _default_evo(family: str) -> ConstraintMaps:
    """Defaults for Evo 1200 air-cooled engine."""
    return ConstraintMaps(
        engine_family=family,
        cooling_type="air",
        rpm_bins=[1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500],
        map_bins=[30, 40, 50, 60, 70, 80, 90, 100, 105],
        max_spark_advance_deg=26.0,
        knock_retard_limit_deg=-8.0,
        min_afr_wot=12.0,
        max_afr_wot=13.0,
        decel_min_afr=13.0,
        ect_enrichment_trigger_f=470.0,
        ect_enrichment_amount_pct=5.0,
        max_egt_f=1400.0,
        max_ve_correction_pct=7.0,
        max_fuel_gain=0.05,
        max_timing_offset=2.0,
        correction_decay_rate=0.10,
        correction_decay_threshold_hrs=30.0,
        max_test_rpm=5500.0,
    )


def _default_twin_cam(family: str) -> ConstraintMaps:
    """Defaults for Twin Cam air-cooled engines (88, 96, 103, 110)."""
    return ConstraintMaps(
        engine_family=family,
        cooling_type="air",
        rpm_bins=[1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500],
        map_bins=[30, 40, 50, 60, 70, 80, 90, 100, 105],
        max_spark_advance_deg=26.0,
        knock_retard_limit_deg=-8.0,
        min_afr_wot=12.0,
        max_afr_wot=13.0,
        decel_min_afr=13.0,
        ect_enrichment_trigger_f=470.0,
        ect_enrichment_amount_pct=5.0,
        max_egt_f=1400.0,
        max_ve_correction_pct=7.0,
        max_fuel_gain=0.05,
        max_timing_offset=2.0,
        correction_decay_rate=0.10,
        correction_decay_threshold_hrs=30.0,
        max_test_rpm=5500.0,
    )


_DEFAULT_BUILDERS = {
    "m8_107": _default_m8_air_cooled,
    "m8_114": _default_m8_air_cooled,
    "m8_117": _default_m8_air_cooled,
    "m8_131": _default_m8_oil_cooled,
    "tc_88": _default_twin_cam,
    "tc_96": _default_twin_cam,
    "tc_103": _default_twin_cam,
    "tc_110": _default_twin_cam,
    "revmax_975": _default_revmax_975,
    "revmax_1250": _default_revmax_liquid,
    "evo_1200": _default_evo,
}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class PhysicsConstraints:
    """
    Engine-family-specific safety boundaries.

    All limits stored as lookup tables (JSON), not code.
    Tuner can inspect and modify via UI or JSON editor.

    Usage:
        pc = PhysicsConstraints("m8_114")
        verdict = pc.check_point(rpm=3500, map_kpa=80, timing=22.0, afr=12.8)
        safe, reason = pc.is_safe_to_test(3500, 90)
    """

    def __init__(
        self,
        engine_family: str,
        constraints_dir: Optional[Path] = None,
    ):
        if engine_family not in KNOWN_FAMILIES:
            raise ValueError(
                f"Unknown engine family: '{engine_family}'. "
                f"Known families: {KNOWN_FAMILIES}"
            )

        self._family = engine_family

        # Try to load from JSON first, fall back to built-in defaults
        loaded = False
        if constraints_dir is not None:
            json_path = constraints_dir / f"{engine_family}_limits.json"
            if json_path.exists():
                self.maps = self._load_from_json(json_path)
                loaded = True

        if not loaded:
            builder = _DEFAULT_BUILDERS[engine_family]
            self.maps = builder(engine_family)

        logger.info(
            "PhysicsConstraints loaded for %s (%s-cooled): "
            "max_test_rpm=%d, min_afr_wot=%.1f, ect_trigger=%.0f°F",
            engine_family,
            self.maps.cooling_type,
            self.maps.max_test_rpm,
            self.maps.min_afr_wot,
            self.maps.ect_enrichment_trigger_f,
        )

    # ------------------------------------------------------------------
    # Point safety check
    # ------------------------------------------------------------------
    def check_point(
        self,
        rpm: float,
        map_kpa: float,
        timing: Optional[float] = None,
        afr: Optional[float] = None,
    ) -> SafetyVerdict:
        """
        Check whether an operating point is within safety bounds.

        Args:
            rpm: Engine RPM
            map_kpa: Manifold absolute pressure (kPa)
            timing: Spark advance (degrees BTDC), optional
            afr: Air-fuel ratio, optional

        Returns:
            SafetyVerdict with .safe and .violations[]
        """
        violations: List[Violation] = []

        # RPM check
        if rpm > self.maps.max_test_rpm:
            violations.append(
                Violation(
                    parameter="rpm",
                    reason=f"RPM {rpm:.0f} exceeds max test RPM {self.maps.max_test_rpm:.0f}",
                    value=rpm,
                    limit=self.maps.max_test_rpm,
                )
            )

        # Timing check
        if timing is not None:
            max_allowed = self.maps.max_spark_advance_deg
            if timing > max_allowed:
                violations.append(
                    Violation(
                        parameter="timing",
                        reason=(
                            f"Timing {timing:.1f}° exceeds max spark advance "
                            f"{max_allowed:.1f}°"
                        ),
                        value=timing,
                        limit=max_allowed,
                    )
                )

        # AFR check (varies by load)
        if afr is not None:
            is_wot = map_kpa >= 90
            if is_wot:
                if afr > self.maps.max_afr_wot:
                    violations.append(
                        Violation(
                            parameter="afr",
                            reason=(
                                f"LEAN at WOT: AFR {afr:.1f} exceeds max "
                                f"{self.maps.max_afr_wot:.1f}"
                            ),
                            value=afr,
                            limit=self.maps.max_afr_wot,
                        )
                    )
                if afr < self.maps.min_afr_wot:
                    violations.append(
                        Violation(
                            parameter="afr",
                            reason=(
                                f"RICH at WOT: AFR {afr:.1f} below min "
                                f"{self.maps.min_afr_wot:.1f}"
                            ),
                            value=afr,
                            limit=self.maps.min_afr_wot,
                        )
                    )

        return SafetyVerdict(
            safe=len(violations) == 0,
            violations=violations,
        )

    # ------------------------------------------------------------------
    # Pre-pull safety gate
    # ------------------------------------------------------------------
    def is_safe_to_test(
        self,
        rpm: float,
        map_kpa: float,
    ) -> Tuple[bool, str]:
        """
        Quick pre-pull safety check for the Pull Advisor.

        Returns:
            (safe: bool, reason: str) — reason is "OK" if safe
        """
        if rpm > self.maps.max_test_rpm:
            return (
                False,
                f"RPM {rpm:.0f} exceeds max test RPM {self.maps.max_test_rpm:.0f}",
            )

        if map_kpa > 110:
            return False, f"MAP {map_kpa:.0f} kPa exceeds safe test range"

        return True, "OK"

    # ------------------------------------------------------------------
    # VE table clamping
    # ------------------------------------------------------------------
    def clamp_ve_table(
        self,
        table: "np.ndarray",
        is_adaptive: bool = False,
    ) -> Tuple["np.ndarray", List[ClampEvent]]:
        """
        Apply hard VE correction limits to a table.

        Args:
            table: VE correction table (% values)
            is_adaptive: If True, use tighter adaptive limits (±5%)
                         instead of standard limits (±7%)

        Returns:
            (clamped_table, list_of_clamp_events)
        """
        limit = (
            self.maps.max_fuel_gain * 100.0
            if is_adaptive
            else self.maps.max_ve_correction_pct
        )

        clamped = np.clip(table, -limit, +limit)
        events: List[ClampEvent] = []

        # Record which cells were clamped
        diff = table - clamped
        clamped_mask = np.abs(diff) > 0.001
        rows, cols = np.where(clamped_mask)
        for r, c in zip(rows, cols):
            events.append(
                ClampEvent(
                    rpm_idx=int(r),
                    map_idx=int(c),
                    original_value=float(table[r, c]),
                    clamped_value=float(clamped[r, c]),
                    limit=limit,
                )
            )

        if events:
            logger.info(
                "Clamped %d cells to ±%.1f%% (%s mode)",
                len(events),
                limit,
                "adaptive" if is_adaptive else "standard",
            )

        return clamped, events

    # ------------------------------------------------------------------
    # ECT enrichment override (used by adaptive_overlay)
    # ------------------------------------------------------------------
    def needs_enrichment_override(
        self,
        ect_f: float,
    ) -> Tuple[bool, float]:
        """
        Check if ECT requires forced enrichment.

        Args:
            ect_f: Engine/cylinder head temperature in °F

        Returns:
            (needs_enrichment: bool, enrichment_amount: float as %)
        """
        if ect_f > self.maps.ect_enrichment_trigger_f:
            return True, self.maps.ect_enrichment_amount_pct
        return False, 0.0

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def export_to_json(self, path: Path) -> Path:
        """
        Export constraint maps to a JSON file.

        Args:
            path: Destination file path

        Returns:
            The path written to
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(self.maps.to_dict(), f, indent=2)

        logger.info("Exported constraints for %s to %s", self._family, path)
        return path

    @staticmethod
    def _load_from_json(path: Path) -> ConstraintMaps:
        """Load constraint maps from a JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        return ConstraintMaps.from_dict(data)
