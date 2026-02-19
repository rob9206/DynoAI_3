"""
DynoAI v3.0 — Session Orchestrator
=====================================

Top-level entry point that ties all v3.0 modules together into a single
tuning session workflow.  Replaces the current manual flow of "run
pulls, then process" with a guided, adaptive session.

Lifecycle:
    CREATED → initialize() → READY → ingest_pull() → IN_PROGRESS → finalize() → COMPLETE

Author: Thunderhorse Tuning / DynoAI
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from numpy.typing import NDArray

from .gp_surrogate import VESurrogate, Observation
from .grid_config import GridConfig
from .physics_constraints import PhysicsConstraints
from .pull_advisor import PullAdvisor, PullRecommendation, ConvergenceStatus
from .template_library import HardwareConfig, TemplateLibrary, TemplateMatch

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session states
# ---------------------------------------------------------------------------
class SessionState(Enum):
    CREATED = "created"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------
@dataclass
class SessionInit:
    """Result of session initialization (Phase 1)."""
    session_id: str
    engine_family: str
    initial_plan: List[PullRecommendation]
    template_match: Optional[TemplateMatch] = None
    estimated_pulls: int = 0


@dataclass
class PullResult:
    """Result of ingesting a single pull (Phase 2)."""
    pull_number: int
    observations_added: int
    convergence: Optional[ConvergenceStatus] = None
    next_suggestion: Optional[PullRecommendation] = None


@dataclass
class FinalResult:
    """Result of session finalization (Phase 3)."""
    template_id: str
    total_pulls: int
    session_id: str = ""
    session_duration_s: float = 0.0


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class TuningSession:
    """
    Orchestrates a complete accelerated dyno tuning session.

    Usage:
        session = TuningSession(hardware_config, templates_dir)
        init = session.initialize()          # Phase 1

        for pull_data in pulls:
            result = session.ingest_pull(rpm, map_kpa, ve)  # Phase 2

        final = session.finalize(ve_table, operator="robbie")  # Phase 3
    """

    def __init__(
        self,
        config: HardwareConfig,
        templates_dir: Path,
        constraints_dir: Optional[Path] = None,
    ):
        self.config = config
        self._templates_dir = Path(templates_dir)
        self._constraints_dir = constraints_dir

        # Initialize physics constraints
        self.constraints = PhysicsConstraints(
            config.engine_family,
            constraints_dir=constraints_dir,
        )

        # State
        self.session_id = str(uuid.uuid4())[:12]
        self.state = SessionState.CREATED
        self._start_time = time.time()
        self._pull_count = 0

        # These are initialized during initialize()
        self.surrogate: Optional[VESurrogate] = None
        self.advisor: Optional[PullAdvisor] = None
        self._template_lib: Optional[TemplateLibrary] = None
        self._template_match: Optional[TemplateMatch] = None
        self._convergence: Optional[ConvergenceStatus] = None

        logger.info(
            "TuningSession created: %s (family=%s)",
            self.session_id, config.engine_family,
        )

    # ------------------------------------------------------------------
    # Phase 1: Initialize
    # ------------------------------------------------------------------
    def initialize(self, skip_template_seed: bool = False) -> SessionInit:
        """
        Phase 1: Find template, init GP surrogate, generate test plan.

        Args:
            skip_template_seed: If True, skip seeding from template library
                (used when user provides initial_ve_table import)

        Returns:
            SessionInit with template match info and initial pull plan
        """
        # 1. Initialize template library
        self._template_lib = TemplateLibrary(self._templates_dir)

        # 2. Find best template match
        self._template_match = self._template_lib.find_nearest(self.config)

        # 3. Resolve authoritative grid (PVV > wizard > preset)
        self.grid_config = GridConfig.resolve(
            engine_family=self.config.engine_family,
            pvv_rpm_bins=self.config.rpm_bins,
            pvv_map_bins=self.config.map_bins,
        )
        rpm_bins = np.array(self.grid_config.rpm_bins, dtype=np.float64)
        map_bins = np.array(self.grid_config.map_bins, dtype=np.float64)

        # Sync constraints so downstream safety checks use the same grid
        self.constraints.maps.rpm_bins = self.grid_config.rpm_bins
        self.constraints.maps.map_bins = self.grid_config.map_bins

        self.surrogate = VESurrogate(
            rpm_bins=rpm_bins,
            map_bins=map_bins,
            engine_family=self.config.engine_family,
        )

        # 4. If template found with good match, seed GP (unless user provided import)
        if (
            not skip_template_seed
            and self._template_match is not None
            and self._template_match.is_usable
        ):
            cal = self._template_match.calibration
            # Try to find a VE table in the calibration data
            ve_key = None
            for key in ["ve_table_front", "ve_table", "ve"]:
                if key in cal:
                    ve_key = key
                    break

            if ve_key is not None:
                template_ve = np.array(cal[ve_key], dtype=np.float64)
                self.surrogate.seed_from_template(
                    template_ve, rpm_bins, map_bins,
                )
                logger.info(
                    "GP seeded from template %s (similarity=%.2f)",
                    self._template_match.template_id,
                    self._template_match.similarity_score,
                )
        elif skip_template_seed and self._template_match is not None:
            logger.info(
                "Skipping template seed (user provided import); template %s available for reference",
                self._template_match.template_id,
            )

        # 5. Initialize Pull Advisor
        self.advisor = PullAdvisor(self.surrogate, self.constraints)

        # 6. Generate initial test plan
        initial_plan = self.advisor.suggest_pull_sequence()

        self.state = SessionState.READY

        return SessionInit(
            session_id=self.session_id,
            engine_family=self.config.engine_family,
            initial_plan=initial_plan,
            template_match=self._template_match,
            estimated_pulls=len(initial_plan),
        )

    # ------------------------------------------------------------------
    # Phase 2: Ingest pulls
    # ------------------------------------------------------------------
    def ingest_pull(
        self,
        rpm: NDArray[np.float64],
        map_kpa: NDArray[np.float64],
        ve: NDArray[np.float64],
    ) -> PullResult:
        """
        Process a completed pull through the GP surrogate.

        Args:
            rpm: Array of RPM values from the pull
            map_kpa: Array of MAP values from the pull
            ve: Array of VE delta values from the pull

        Returns:
            PullResult with pull number and convergence status
        """
        if self.surrogate is None:
            raise RuntimeError("Session not initialized — call initialize() first")

        self._pull_count += 1
        self.state = SessionState.IN_PROGRESS

        # Feed data to GP surrogate
        n_added = self.surrogate.add_pull_data(
            rpm, map_kpa, ve,
            pull_number=self._pull_count,
        )

        # Update convergence
        self._convergence = (
            self.advisor.check_convergence() if self.advisor else None
        )

        # Get next suggestion
        next_rec = (
            self.advisor.suggest_next_pull() if self.advisor else None
        )

        logger.info(
            "Pull #%d ingested: %d observations added",
            self._pull_count, n_added,
        )

        return PullResult(
            pull_number=self._pull_count,
            observations_added=n_added,
            convergence=self._convergence,
            next_suggestion=next_rec,
        )

    # ------------------------------------------------------------------
    # Phase 3: Finalize
    # ------------------------------------------------------------------
    def finalize(
        self,
        ve_table_front: NDArray[np.float64],
        operator: str = "unknown",
    ) -> FinalResult:
        """
        Phase 3: Store template and generate final output.

        Args:
            ve_table_front: Final VE correction table (front cylinder)
            operator: Operator name

        Returns:
            FinalResult with template ID and session stats
        """
        if self._template_lib is None:
            raise RuntimeError("Session not initialized — call initialize() first")

        # 1. Build calibration dict
        calibration = {
            "ve_table_front": np.asarray(ve_table_front).tolist(),
        }

        # 2. Store as new template
        template_id = self._template_lib.store_template(
            config=self.config,
            calibration=calibration,
            operator=operator,
        )

        self.state = SessionState.COMPLETE
        elapsed = time.time() - self._start_time

        logger.info(
            "Session %s finalized: %d pulls, template %s stored",
            self.session_id, self._pull_count, template_id,
        )

        return FinalResult(
            template_id=template_id,
            total_pulls=self._pull_count,
            session_id=self.session_id,
            session_duration_s=elapsed,
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    @property
    def converged(self) -> bool:
        """Whether the session has converged."""
        return (
            self._convergence is not None
            and self._convergence.converged
        )

    def get_status(self) -> Dict[str, Any]:
        """Get current session status for UI display."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "engine_family": self.config.engine_family,
            "pull_count": self._pull_count,
            "converged": self.converged,
            "elapsed_s": time.time() - self._start_time,
            "template_match": (
                self._template_match.template_id
                if self._template_match
                else None
            ),
        }
