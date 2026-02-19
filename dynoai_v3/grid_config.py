"""
DynoAI v3.0 — Unified Grid Configuration
============================================

Single source of truth for RPM/MAP bin definitions within a tuning session.

Grid sources (priority order):
    1. PVV import — the user's actual tune file defines the grid
    2. Setup wizard — user configured custom RPM/MAP ranges
    3. Engine family preset — hardcoded defaults from PhysicsConstraints

All downstream consumers (GP surrogate, AutoTuneWorkflow, VirtualECU)
receive their grid from this config so they always agree.

Author: Thunderhorse Tuning / DynoAI
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GridConfig:
    """
    Authoritative RPM/MAP bin definition for a tuning session.

    Attributes:
        rpm_bins: Sorted list of RPM bin centres.
        map_bins: Sorted list of MAP bin centres (kPa).
        source:   How the grid was determined ("pvv", "wizard", "preset").
    """

    rpm_bins: List[float] = field(default_factory=list)
    map_bins: List[float] = field(default_factory=list)
    source: str = "preset"

    # ---- Constructors -----------------------------------------------------

    @classmethod
    def from_pvv(
        cls,
        rpm_axis: List[float],
        map_axis: List[float],
    ) -> "GridConfig":
        """Build a GridConfig from a PVV file's embedded axes."""
        return cls(
            rpm_bins=sorted(float(r) for r in rpm_axis),
            map_bins=sorted(float(m) for m in map_axis),
            source="pvv",
        )

    @classmethod
    def from_wizard(
        cls,
        rpm_min: float,
        rpm_max: float,
        map_min: float,
        map_max: float,
        rpm_step: float = 500.0,
        map_step: float = 10.0,
    ) -> "GridConfig":
        """
        Build a GridConfig from the Setup Wizard's RPM/MAP range inputs.

        Generates evenly-spaced bins within the user-specified ranges.
        """
        import numpy as np

        rpm_bins = np.arange(rpm_min, rpm_max + rpm_step / 2, rpm_step).tolist()
        map_bins = np.arange(map_min, map_max + map_step / 2, map_step).tolist()

        return cls(
            rpm_bins=[float(r) for r in rpm_bins],
            map_bins=[float(m) for m in map_bins],
            source="wizard",
        )

    @classmethod
    def from_preset(cls, engine_family: str) -> "GridConfig":
        """
        Build a GridConfig from the hardcoded PhysicsConstraints defaults.

        This is the fallback when no PVV or wizard config is available.
        """
        from .physics_constraints import PhysicsConstraints

        pc = PhysicsConstraints(engine_family)
        return cls(
            rpm_bins=[float(r) for r in pc.maps.rpm_bins],
            map_bins=[float(m) for m in pc.maps.map_bins],
            source="preset",
        )

    @classmethod
    def resolve(
        cls,
        engine_family: str,
        pvv_rpm_bins: Optional[List[float]] = None,
        pvv_map_bins: Optional[List[float]] = None,
        wizard_rpm_bins: Optional[List[float]] = None,
        wizard_map_bins: Optional[List[float]] = None,
    ) -> "GridConfig":
        """
        Resolve the authoritative grid from all available sources.

        Priority:
            1. PVV axes (if both rpm and map provided)
            2. Wizard custom bins (if both provided)
            3. Engine family preset (fallback)
        """
        # Check PVV bins (must have both and be non-empty)
        has_pvv = (
            pvv_rpm_bins is not None 
            and pvv_map_bins is not None 
            and len(pvv_rpm_bins) > 0 
            and len(pvv_map_bins) > 0
        )
        
        if has_pvv:
            gc = cls.from_pvv(pvv_rpm_bins, pvv_map_bins)
            logger.info(
                "Grid resolved from PVV: %d RPM x %d MAP bins",
                len(gc.rpm_bins), len(gc.map_bins),
            )
            return gc

        # Check wizard bins
        has_wizard = (
            wizard_rpm_bins is not None
            and wizard_map_bins is not None
            and len(wizard_rpm_bins) > 0
            and len(wizard_map_bins) > 0
        )
        
        if has_wizard:
            gc = cls(
                rpm_bins=sorted(float(r) for r in wizard_rpm_bins),
                map_bins=sorted(float(m) for m in wizard_map_bins),
                source="wizard",
            )
            logger.info(
                "Grid resolved from wizard: %d RPM x %d MAP bins",
                len(gc.rpm_bins), len(gc.map_bins),
            )
            return gc

        # Fallback to preset with diagnostic logging
        logger.warning(
            "Grid falling back to preset: pvv_rpm=%s, pvv_map=%s, wizard_rpm=%s, wizard_map=%s",
            f"{len(pvv_rpm_bins)} bins" if pvv_rpm_bins else "None/empty",
            f"{len(pvv_map_bins)} bins" if pvv_map_bins else "None/empty",
            f"{len(wizard_rpm_bins)} bins" if wizard_rpm_bins else "None/empty",
            f"{len(wizard_map_bins)} bins" if wizard_map_bins else "None/empty",
        )
        gc = cls.from_preset(engine_family)
        logger.info(
            "Grid resolved from preset (%s): %d RPM x %d MAP bins",
            engine_family, len(gc.rpm_bins), len(gc.map_bins),
        )
        return gc

    # ---- Properties -------------------------------------------------------

    @property
    def shape(self) -> tuple:
        """(n_rpm, n_map)"""
        return (len(self.rpm_bins), len(self.map_bins))

    def to_dict(self) -> dict:
        return {
            "rpm_bins": self.rpm_bins,
            "map_bins": self.map_bins,
            "source": self.source,
        }
