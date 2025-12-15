"""
Virtual Tuning Session - Closed-loop multi-iteration tuning orchestrator.

This module orchestrates complete tuning sessions:
1. Start with intentionally wrong VE tables
2. Run dyno pull
3. Analyze AFR errors
4. Calculate VE corrections
5. Apply corrections to Virtual ECU
6. Repeat until converged

This is the complete closed-loop tuning simulation!
"""

from __future__ import annotations

import concurrent.futures
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from api.services.autotune_workflow import AutoTuneWorkflow
from api.services.dyno_simulator import (
    DynoSimulator,
    EngineProfile,
    SimulatorConfig,
)
from api.services.virtual_ecu import (
    VirtualECU,
    create_afr_target_table,
    create_baseline_ve_table,
    create_intentionally_wrong_ve_table,
)

logger = logging.getLogger(__name__)


class TuningStatus(Enum):
    """Status of tuning session."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    CONVERGED = "converged"
    FAILED = "failed"
    STOPPED = "stopped"
    MAX_ITERATIONS = "max_iterations"


@dataclass
class IterationResult:
    """Results from one tuning iteration."""

    iteration: int
    timestamp: float

    # AFR metrics
    max_afr_error: float
    mean_afr_error: float
    rms_afr_error: float

    # VE correction metrics
    max_ve_correction_pct: float
    mean_ve_correction_pct: float
    cells_corrected: int
    cells_converged: int

    # Pull data
    pull_data_points: int
    peak_hp: float
    peak_tq: float

    # Convergence
    converged: bool

    # VE tables (for tracking evolution)
    ve_table_front: np.ndarray | None = None
    ve_table_rear: np.ndarray | None = None

    # Correction table (for applying corrections)
    correction_table: np.ndarray | None = None


@dataclass
class TuningSessionConfig:
    """Configuration for a tuning session."""

    # Engine configuration
    engine_profile: EngineProfile

    # Initial VE scenario
    base_ve_scenario: str = "lean"  # "perfect", "lean", "rich", "custom"
    base_ve_error_pct: float = -10.0  # For custom scenario
    base_ve_error_std: float = 5.0

    # Convergence criteria
    max_iterations: int = 10
    convergence_threshold_afr: float = 0.3  # AFR points
    convergence_cell_pct: float = 90.0  # % of cells must be converged

    # Safety limits
    max_correction_per_iteration_pct: float = 15.0
    max_total_correction_pct: float = 50.0

    # Timeout protection
    iteration_timeout_sec: float = 60.0  # Max time per iteration

    # Oscillation detection
    oscillation_detection_enabled: bool = True
    oscillation_threshold: float = 0.1  # If error increases by this much, flag it

    # Environmental
    barometric_pressure_inhg: float = 29.92
    ambient_temp_f: float = 75.0


@dataclass
class TuningSession:
    """A complete virtual tuning session."""

    session_id: str
    config: TuningSessionConfig
    status: TuningStatus = TuningStatus.INITIALIZING

    # Iteration tracking
    current_iteration: int = 0
    iterations: list[IterationResult] = field(default_factory=list)

    # Sub-iteration progress (0-100)
    progress_pct: float = 0.0
    progress_message: str = ""

    # Current VE tables
    current_ve_front: np.ndarray | None = None
    current_ve_rear: np.ndarray | None = None

    # Baseline (correct) VE for comparison
    baseline_ve: np.ndarray | None = None

    # Timing
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None

    # Error tracking
    error_message: str | None = None

    # Thread safety for progress updates
    _progress_lock: Any = field(
        default_factory=lambda: __import__("threading").Lock(),
        init=False,
        repr=False,
    )

    def update_progress(self, pct: float, message: str = "") -> None:
        """Thread-safe progress update."""
        with self._progress_lock:
            self.progress_pct = pct
            self.progress_message = message

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "current_iteration": self.current_iteration,
            "max_iterations": self.config.max_iterations,
            "converged": self.status == TuningStatus.CONVERGED,
            "progress_pct": self.progress_pct,
            "progress_message": self.progress_message,
            "iterations": [
                {
                    "iteration": it.iteration,
                    "timestamp": it.timestamp,
                    "max_afr_error": round(it.max_afr_error, 3),
                    "mean_afr_error": round(it.mean_afr_error, 3),
                    "rms_afr_error": round(it.rms_afr_error, 3),
                    "max_ve_correction_pct": round(it.max_ve_correction_pct, 2),
                    "mean_ve_correction_pct": round(it.mean_ve_correction_pct, 2),
                    "cells_corrected": it.cells_corrected,
                    "cells_converged": it.cells_converged,
                    "converged": it.converged,
                    "peak_hp": round(it.peak_hp, 1),
                    "peak_tq": round(it.peak_tq, 1),
                }
                for it in self.iterations
            ],
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_sec": (self.end_time or time.time()) - self.start_time,
            "error_message": self.error_message,
        }


class VirtualTuningOrchestrator:
    """
    Orchestrates closed-loop virtual tuning sessions.

    This is the main class for running complete multi-iteration tuning
    simulations. It manages the entire workflow:

    1. Initialize with wrong VE tables
    2. Run dyno pull with Virtual ECU
    3. Analyze AFR errors using AutoTuneWorkflow
    4. Calculate VE corrections
    5. Apply corrections to ECU tables
    6. Check convergence
    7. Repeat until converged or max iterations

    Example:
        config = TuningSessionConfig(
            engine_profile=EngineProfile.m8_114(),
            base_ve_scenario="lean",
            max_iterations=10,
            convergence_threshold_afr=0.3,
        )

        orchestrator = VirtualTuningOrchestrator()
        session = orchestrator.create_session(config)

        # Run tuning (blocks until complete)
        orchestrator.run_session(session)

        # Check results
        if session.status == TuningStatus.CONVERGED:
            print(f"Converged in {session.current_iteration} iterations!")
    """

    def __init__(self):
        """Initialize the orchestrator."""
        self.sessions: dict[str, TuningSession] = {}

    def create_session(self, config: TuningSessionConfig) -> TuningSession:
        """
        Create a new tuning session.

        Args:
            config: Session configuration

        Returns:
            TuningSession object
        """
        session_id = f"tune_{int(time.time())}_{np.random.randint(1000, 9999)}"

        session = TuningSession(
            session_id=session_id,
            config=config,
            status=TuningStatus.INITIALIZING,
        )

        # Create baseline (correct) VE table for comparison
        session.baseline_ve = create_baseline_ve_table(
            peak_ve=0.85,
            peak_rpm=4000,
        )

        # Create initial (wrong) VE tables based on scenario
        if config.base_ve_scenario == "perfect":
            session.current_ve_front = session.baseline_ve.copy()
            session.current_ve_rear = session.baseline_ve.copy()
        elif config.base_ve_scenario == "lean":
            session.current_ve_front = create_intentionally_wrong_ve_table(
                session.baseline_ve,
                error_pct_mean=-10.0,
                error_pct_std=5.0,
                seed=42,
            )
            session.current_ve_rear = session.current_ve_front.copy()
        elif config.base_ve_scenario == "rich":
            session.current_ve_front = create_intentionally_wrong_ve_table(
                session.baseline_ve,
                error_pct_mean=10.0,
                error_pct_std=5.0,
                seed=42,
            )
            session.current_ve_rear = session.current_ve_front.copy()
        elif config.base_ve_scenario == "custom":
            session.current_ve_front = create_intentionally_wrong_ve_table(
                session.baseline_ve,
                error_pct_mean=config.base_ve_error_pct,
                error_pct_std=config.base_ve_error_std,
                seed=42,
            )
            session.current_ve_rear = session.current_ve_front.copy()
        else:
            raise ValueError(f"Unknown scenario: {config.base_ve_scenario}")

        self.sessions[session_id] = session
        logger.info(f"Created tuning session: {session_id}")

        return session

    def run_session(self, session: TuningSession) -> TuningSession:
        """
        Run a complete tuning session until convergence or max iterations.

        This is a blocking call that runs the entire tuning loop.

        Args:
            session: TuningSession to run

        Returns:
            Updated TuningSession with results
        """
        logger.info(f"Starting tuning session: {session.session_id}")
        session.status = TuningStatus.RUNNING

        try:
            for iteration in range(1, session.config.max_iterations + 1):
                # Allow external stop requests (best-effort; current iteration may still finish)
                if session.status == TuningStatus.STOPPED:
                    session.end_time = time.time()
                    logger.info(f"Session stopped: {session.session_id}")
                    break

                logger.info("=" * 60)
                logger.info(f"Iteration {iteration}/{session.config.max_iterations}")
                logger.info("=" * 60)

                # Run one iteration with timeout protection
                try:
                    with concurrent.futures.ThreadPoolExecutor(
                        max_workers=1
                    ) as executor:
                        future = executor.submit(
                            self._run_iteration, session, iteration
                        )
                        try:
                            iteration_result = future.result(
                                timeout=session.config.iteration_timeout_sec
                            )
                        except concurrent.futures.TimeoutError:
                            logger.error(
                                f"⚠️ Iteration {iteration} exceeded timeout ({session.config.iteration_timeout_sec}s)"
                            )
                            session.status = TuningStatus.FAILED
                            session.error_message = f"Iteration {iteration} timeout after {session.config.iteration_timeout_sec}s"
                            session.end_time = time.time()
                            break
                except Exception as iter_error:
                    logger.error(
                        f"Iteration {iteration} failed: {iter_error}", exc_info=True
                    )
                    session.status = TuningStatus.FAILED
                    session.error_message = (
                        f"Iteration {iteration} failed: {str(iter_error)}"
                    )
                    session.end_time = time.time()
                    break

                session.iterations.append(iteration_result)
                session.current_iteration = iteration

                # Check convergence
                if iteration_result.converged:
                    session.status = TuningStatus.CONVERGED
                    session.end_time = time.time()
                    logger.info(f"✅ Converged in {iteration} iterations!")
                    break

                # Check for oscillation
                if (
                    session.config.oscillation_detection_enabled
                    and iteration > 1
                    and self._detect_oscillation(session)
                ):
                    session.status = TuningStatus.FAILED
                    session.error_message = (
                        "Oscillation detected - corrections are not converging"
                    )
                    session.end_time = time.time()
                    logger.warning("⚠️ Oscillation detected, stopping")
                    break

                # Apply corrections for next iteration
                self._apply_corrections(session, iteration_result)

            # Max iterations reached without convergence
            if session.status == TuningStatus.RUNNING:
                session.status = TuningStatus.MAX_ITERATIONS
                session.end_time = time.time()
                logger.info(f"Reached max iterations ({session.config.max_iterations})")

        except Exception as e:
            session.status = TuningStatus.FAILED
            session.error_message = str(e)
            session.end_time = time.time()
            logger.error(f"Tuning session failed: {e}", exc_info=True)

        return session

    def _run_iteration(self, session: TuningSession, iteration: int) -> IterationResult:
        """
        Run one iteration of the tuning loop.

        Steps:
        1. Create Virtual ECU with current VE tables
        2. Run dyno pull
        3. Analyze AFR errors
        4. Calculate VE corrections
        5. Return metrics

        Args:
            session: Current tuning session
            iteration: Iteration number

        Returns:
            IterationResult with metrics
        """
        iteration_start = time.time()

        # Progress: 0% - Iteration started
        session.update_progress(0.0, f"Starting iteration {iteration}...")

        # Create AFR target table
        afr_table = create_afr_target_table(cruise_afr=14.0, wot_afr=12.5)

        # Create Virtual ECU with current VE tables
        if session.current_ve_front is None or session.current_ve_rear is None:
            raise ValueError("VE tables not initialized in session")

        logger.info("  Creating Virtual ECU with current VE tables...")
        ecu = VirtualECU(
            ve_table_front=session.current_ve_front,
            ve_table_rear=session.current_ve_rear,
            afr_target_table=afr_table,
            barometric_pressure_inhg=session.config.barometric_pressure_inhg,
            ambient_temp_f=session.config.ambient_temp_f,
        )
        logger.info("  ✓ Virtual ECU created with VE tables")

        # Progress: 20% - Virtual ECU created
        session.update_progress(20.0, "Virtual ECU created")

        # Create simulator with Virtual ECU
        sim_config = SimulatorConfig(
            profile=session.config.engine_profile,
            enable_thermal_effects=True,
            auto_pull=False,
        )

        simulator = DynoSimulator(config=sim_config, virtual_ecu=ecu)
        simulator.start()

        # Wait for idle
        time.sleep(0.5)

        logger.info(f"  Simulator state after start: {simulator.get_state().value}")

        # Trigger pull
        # Progress: 40% - Dyno pull started
        session.update_progress(40.0, "Running dyno pull...")
        logger.info("  🚀 Starting dyno pull simulation...")
        simulator.trigger_pull()

        # Verify pull started
        time.sleep(0.2)
        logger.info(f"  Simulator state after trigger: {simulator.get_state().value}")

        # Wait for completion (with timeout)
        max_wait = 30  # 30 second timeout
        wait_count = 0
        while simulator.get_state().value != "idle":
            time.sleep(0.1)
            wait_count += 1
            if wait_count > max_wait * 10:  # 10 checks per second
                logger.error(
                    f"Timeout waiting for pull to complete (state: {simulator.get_state().value})"
                )
                simulator.stop()
                raise TimeoutError("Pull did not complete within 30 seconds")

        # Get pull data
        pull_data = simulator.get_pull_data()
        logger.info(f"  ✓ Dyno pull complete, {len(pull_data)} data points captured")
        simulator.stop()

        # Progress: 70% - Dyno pull completed
        session.update_progress(70.0, f"Dyno pull complete ({len(pull_data)} points)")

        if not pull_data or len(pull_data) == 0:
            raise ValueError("No pull data collected - pull may not have completed")

        df = pd.DataFrame(pull_data)

        # Calculate AFR errors
        logger.info("  📊 Analyzing AFR errors...")
        df["AFR Error F"] = df["AFR Meas F"] - df["AFR Target"]
        df["AFR Error R"] = df["AFR Meas R"] - df["AFR Target"]

        # Metrics
        max_afr_error = float(
            max(df["AFR Error F"].abs().max(), df["AFR Error R"].abs().max())
        )
        mean_afr_error = float(
            (df["AFR Error F"].abs().mean() + df["AFR Error R"].abs().mean()) / 2
        )
        rms_afr_error = float(
            np.sqrt((df["AFR Error F"] ** 2).mean() + (df["AFR Error R"] ** 2).mean())
            / np.sqrt(2)
        )
        logger.info(f"  ✓ AFR analysis complete, max error: {max_afr_error:.3f}")

        # Progress: 85% - AFR analysis completed
        session.update_progress(85.0, "AFR analysis complete")

        # Calculate VE corrections using AutoTuneWorkflow
        logger.info("  🔧 Calculating VE corrections...")
        workflow = AutoTuneWorkflow()
        workflow_session = workflow.create_session()
        workflow.import_dataframe(workflow_session, df)
        workflow.analyze_afr(workflow_session)
        corrections = workflow.calculate_corrections(workflow_session)

        if corrections is None:
            raise ValueError("Failed to calculate corrections")

        # Correction metrics
        correction_array = corrections.correction_table
        correction_pcts = (correction_array - 1.0) * 100

        # Only count cells with significant corrections
        significant_mask = np.abs(correction_pcts) > 0.5
        max_ve_correction = (
            np.abs(correction_pcts[significant_mask]).max()
            if significant_mask.any()
            else 0.0
        )
        mean_ve_correction = (
            np.abs(correction_pcts[significant_mask]).mean()
            if significant_mask.any()
            else 0.0
        )
        cells_corrected = int(significant_mask.sum())

        # Progress: 100% - VE corrections calculated
        session.update_progress(100.0, "VE corrections calculated")

        # Convergence check
        converged_mask = (
            np.abs(correction_pcts) < session.config.convergence_threshold_afr * 7
        )  # ~7% VE per AFR point
        cells_converged = int(converged_mask.sum())
        total_cells = correction_array.size
        convergence_pct = (cells_converged / total_cells) * 100

        converged = (
            max_afr_error < session.config.convergence_threshold_afr
            and convergence_pct >= session.config.convergence_cell_pct
        )

        # Peak performance
        peak_hp = float(df["Horsepower"].max())
        peak_tq = float(df["Torque"].max())

        iteration_duration = time.time() - iteration_start
        logger.info(
            f"  ✓ Iteration {iteration} complete in {iteration_duration:.1f}s - "
            f"Max AFR error: {max_afr_error:.3f}, "
            f"Mean: {mean_afr_error:.3f}, "
            f"Max VE correction: {max_ve_correction:.2f}%, "
            f"Converged: {converged}"
        )

        return IterationResult(
            iteration=iteration,
            timestamp=time.time(),
            max_afr_error=max_afr_error,
            mean_afr_error=mean_afr_error,
            rms_afr_error=rms_afr_error,
            max_ve_correction_pct=max_ve_correction,
            mean_ve_correction_pct=mean_ve_correction,
            cells_corrected=cells_corrected,
            cells_converged=cells_converged,
            pull_data_points=len(df),
            peak_hp=peak_hp,
            peak_tq=peak_tq,
            converged=converged,
            ve_table_front=(
                session.current_ve_front.copy()
                if session.current_ve_front is not None
                else None
            ),
            ve_table_rear=(
                session.current_ve_rear.copy()
                if session.current_ve_rear is not None
                else None
            ),
            correction_table=correction_array.copy(),
        )

    def _apply_corrections(
        self, session: TuningSession, iteration_result: IterationResult
    ) -> None:
        """
        Apply VE corrections to session's current VE tables.

        Uses the correction table from the iteration result to apply
        cell-by-cell corrections to the VE tables.

        Args:
            session: Current tuning session
            iteration_result: Results with correction data
        """
        if iteration_result.correction_table is None:
            logger.warning("No correction table available, skipping corrections")
            return

        if session.current_ve_front is None or session.current_ve_rear is None:
            logger.error("VE tables not initialized in session")
            return

        correction_table = iteration_result.correction_table

        # Verify dimensions match
        if correction_table.shape != session.current_ve_front.shape:
            logger.error(
                f"Correction table shape {correction_table.shape} doesn't match "
                f"VE table shape {session.current_ve_front.shape}"
            )
            return

        # Apply safety clamps to correction table
        max_correction = 1.0 + (session.config.max_correction_per_iteration_pct / 100.0)
        min_correction = 1.0 - (session.config.max_correction_per_iteration_pct / 100.0)
        clamped_corrections = np.clip(correction_table, min_correction, max_correction)

        # Apply cell-by-cell corrections: VE_new = VE_old * correction_multiplier
        # At this point we know both are not None from the check above
        ve_front = session.current_ve_front
        ve_rear = session.current_ve_rear
        assert ve_front is not None
        assert ve_rear is not None

        ve_front = ve_front * clamped_corrections
        ve_rear = ve_rear * clamped_corrections

        # Clamp VE tables to reasonable range
        ve_front = np.clip(ve_front, 0.3, 1.5)
        ve_rear = np.clip(ve_rear, 0.3, 1.5)

        session.current_ve_front = ve_front
        session.current_ve_rear = ve_rear

        # Log correction statistics
        correction_pcts = (clamped_corrections - 1.0) * 100
        max_corr_pct = np.abs(correction_pcts).max()
        mean_corr_pct = (
            np.abs(correction_pcts[correction_pcts != 0]).mean()
            if np.any(correction_pcts != 0)
            else 0.0
        )
        logger.info(
            f"  Applied cell-by-cell corrections: max={max_corr_pct:.2f}%, "
            f"mean={mean_corr_pct:.2f}%"
        )

    def _detect_oscillation(self, session: TuningSession) -> bool:
        """
        Detect if corrections are oscillating (not converging).

        Args:
            session: Current tuning session

        Returns:
            True if oscillation detected
        """
        if len(session.iterations) < 3:
            return False

        # Check if error is increasing
        last_error = session.iterations[-1].max_afr_error
        prev_error = session.iterations[-2].max_afr_error

        if last_error > prev_error + session.config.oscillation_threshold:
            logger.warning(
                f"Oscillation detected: error increased from {prev_error:.3f} to {last_error:.3f}"
            )
            return True

        return False

    def get_session(self, session_id: str) -> TuningSession | None:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def stop_session(self, session_id: str) -> bool:
        """
        Stop a running session.

        Args:
            session_id: Session to stop

        Returns:
            True if stopped successfully
        """
        session = self.sessions.get(session_id)
        if session and session.status == TuningStatus.RUNNING:
            session.status = TuningStatus.STOPPED
            session.end_time = time.time()
            logger.info(f"Stopped session: {session_id}")
            return True
        return False


# Global orchestrator instance
_orchestrator: VirtualTuningOrchestrator | None = None


def get_orchestrator() -> VirtualTuningOrchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = VirtualTuningOrchestrator()
    return _orchestrator
