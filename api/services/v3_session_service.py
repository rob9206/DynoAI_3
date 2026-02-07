"""
DynoAI v3.0 Session Service
==============================

Stateful service managing TuningSession instances.  All dynoai_v3 module
interactions are funnelled through this single service so that routes stay
thin and business logic is testable in isolation.

Thread-safety: a global ``_sessions`` dict is protected by a ``Lock``.
Templates are stored under ``data/v3_templates/`` by default.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory session store (thread-safe)
# ---------------------------------------------------------------------------
_sessions: Dict[str, Any] = {}          # session_id → TuningSession
_sessions_lock = threading.Lock()

_TEMPLATES_DIR = Path("data/v3_templates")
_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def _get_session(session_id: str):
    """Retrieve a session or raise KeyError."""
    with _sessions_lock:
        if session_id not in _sessions:
            raise KeyError(f"Session {session_id} not found")
        return _sessions[session_id]


# ---------------------------------------------------------------------------
# Helpers: convert dataclass → dict safely
# ---------------------------------------------------------------------------
def _rec_to_dict(rec) -> Dict[str, Any]:
    """Convert a PullRecommendation to a plain dict."""
    return {
        "rpm": rec.rpm,
        "map_kpa": rec.map_kpa,
        "gear": rec.gear,
        "pull_number": rec.pull_number,
        "pull_type": rec.pull_type.value if hasattr(rec.pull_type, "value") else str(rec.pull_type),
        "reason": rec.reason,
        "expected_info_gain": rec.expected_info_gain,
        "remaining_uncertainty": rec.remaining_uncertainty,
        "throttle_pct": rec.throttle_pct,
        "alternatives": [_rec_to_dict(a) for a in (rec.alternatives or [])],
    }


def _convergence_to_dict(cs) -> Dict[str, Any]:
    return {
        "converged": cs.converged,
        "max_uncertainty": cs.max_uncertainty,
        "mean_uncertainty": cs.mean_uncertainty,
        "cells_above_threshold": cs.cells_above_threshold,
        "total_cells": cs.total_cells,
        "estimated_pulls_remaining": cs.estimated_pulls_remaining,
    }


def _template_match_to_dict(tm) -> Optional[Dict[str, Any]]:
    if tm is None:
        return None
    return {
        "template_id": tm.template_id,
        "similarity_score": tm.similarity_score,
        "is_usable": tm.is_usable,
        "engine_family": tm.config.engine_family,
    }


# ---------------------------------------------------------------------------
# Public API (called by routes)
# ---------------------------------------------------------------------------

def create_session(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new TuningSession, initialize it, and return status."""
    from dynoai_v3.template_library import HardwareConfig
    from dynoai_v3.session_orchestrator import TuningSession

    config = HardwareConfig.from_dict(config_dict)
    session = TuningSession(config, templates_dir=_TEMPLATES_DIR)
    init = session.initialize()

    with _sessions_lock:
        _sessions[session.session_id] = session

    logger.info("V3 session created: %s (%s)", session.session_id, config.engine_family)

    return {
        "session_id": init.session_id,
        "engine_family": init.engine_family,
        "estimated_pulls": init.estimated_pulls,
        "template_match": _template_match_to_dict(init.template_match),
        "initial_plan": [_rec_to_dict(r) for r in init.initial_plan],
    }


def get_session(session_id: str) -> Dict[str, Any]:
    """Get current session status."""
    session = _get_session(session_id)
    return session.get_status()


def list_sessions() -> List[Dict[str, Any]]:
    """List all active sessions."""
    with _sessions_lock:
        return [s.get_status() for s in _sessions.values()]


def ingest_pull(
    session_id: str,
    rpm: List[float],
    map_kpa: List[float],
    ve: List[float],
) -> Dict[str, Any]:
    """Ingest pull data and return result."""
    session = _get_session(session_id)
    result = session.ingest_pull(
        np.array(rpm, dtype=np.float64),
        np.array(map_kpa, dtype=np.float64),
        np.array(ve, dtype=np.float64),
    )
    return {
        "pull_number": result.pull_number,
        "observations_added": result.observations_added,
        "convergence": _convergence_to_dict(result.convergence) if result.convergence else None,
        "next_suggestion": _rec_to_dict(result.next_suggestion) if result.next_suggestion else None,
    }


def finalize_session(
    session_id: str,
    ve_table_front: List[List[float]],
    operator: str = "unknown",
) -> Dict[str, Any]:
    """Finalize session, store template, return result."""
    session = _get_session(session_id)
    result = session.finalize(
        ve_table_front=np.array(ve_table_front, dtype=np.float64),
        operator=operator,
    )
    return {
        "template_id": result.template_id,
        "total_pulls": result.total_pulls,
        "session_id": result.session_id,
        "session_duration_s": result.session_duration_s,
    }


def suggest_next_pull(session_id: str) -> Dict[str, Any]:
    """Get the advisor's next pull recommendation."""
    session = _get_session(session_id)
    if session.advisor is None:
        raise RuntimeError("Session not initialized")
    rec = session.advisor.suggest_next_pull()
    return _rec_to_dict(rec)


def check_convergence(session_id: str) -> Dict[str, Any]:
    """Get convergence status."""
    session = _get_session(session_id)
    if session.advisor is None:
        raise RuntimeError("Session not initialized")
    cs = session.advisor.check_convergence()
    return _convergence_to_dict(cs)


def operator_veto(
    session_id: str,
    rpm: float,
    map_kpa: float,
    reason: str = "",
) -> Dict[str, Any]:
    """Veto a suggested operating point."""
    session = _get_session(session_id)
    if session.advisor is None:
        raise RuntimeError("Session not initialized")
    session.advisor.operator_veto(rpm, map_kpa, reason)
    return {"status": "vetoed", "rpm": rpm, "map_kpa": map_kpa}


def get_uncertainty_map(session_id: str) -> Dict[str, Any]:
    """Get the GP uncertainty map as a 2D list."""
    session = _get_session(session_id)
    if session.surrogate is None:
        raise RuntimeError("Session not initialized")
    pred = session.surrogate.predict_full_map()
    return {
        "ve_map": pred.ve_map.tolist(),
        "uncertainty_map": pred.uncertainty_map.tolist(),
        "confidence_map": pred.confidence_map.tolist(),
        "predict_time_ms": pred.predict_time_ms,
        "rpm_bins": session.surrogate.rpm_bins.tolist(),
        "map_bins": session.surrogate.map_bins.tolist(),
    }


def get_overlay_status(session_id: str) -> Dict[str, Any]:
    """Get bounded overlay status (if active)."""
    # Overlay is only created after finalize in a real workflow,
    # so we return a stub for now showing constraints info.
    session = _get_session(session_id)
    return {
        "enabled": False,
        "fuel_corrections_active": 0,
        "timing_corrections_active": 0,
        "max_fuel_correction_pct": session.constraints.maps.max_fuel_gain * 100,
        "max_timing_correction_deg": session.constraints.maps.max_timing_offset,
        "engine_family": session.config.engine_family,
        "ect_enrichment_trigger_f": session.constraints.maps.ect_enrichment_trigger_f,
    }


def kill_switch(session_id: str) -> Dict[str, Any]:
    """Activate the overlay kill switch (placeholder until overlay is live)."""
    _ = _get_session(session_id)
    return {"status": "kill_switch_acknowledged", "session_id": session_id}


def list_templates(engine_family: Optional[str] = None) -> Dict[str, Any]:
    """List templates in the library."""
    from dynoai_v3.template_library import TemplateLibrary

    lib = TemplateLibrary(_TEMPLATES_DIR)
    total = lib.count()
    family_count = lib.count(engine_family=engine_family) if engine_family else total
    return {
        "total_templates": total,
        "family": engine_family,
        "family_count": family_count,
    }


def simulate_pull_realistic(
    session_id: str,
    rpm: Optional[float] = None,
    map_kpa: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Run a physics-based DynoSimulator pull, pipe through AutoTuneWorkflow,
    and ingest the resulting VE corrections into the v3 session.

    Pipeline:
        1. Advisor suggests target RPM/MAP (or use caller's)
        2. DynoSimulator runs a full physics pull with VirtualECU
        3. AutoTuneWorkflow bins the pull data on the SESSION's grid
        4. VE correction_table converted to per-observation deltas
        5. Ingested into the GP surrogate via session.ingest_pull()

    All three subsystems share the session's authoritative grid so no
    resampling is needed.
    """
    import time as _time

    import pandas as pd

    from api.services.autotune_workflow import AutoTuneWorkflow
    from api.services.simulation.dyno_simulator import (
        DynoSimulator,
        EngineProfile,
        SimulatorConfig,
        SimState,
    )
    from api.services.simulation.virtual_ecu import (
        VirtualECU,
        create_afr_target_table,
        create_baseline_ve_table,
        create_intentionally_wrong_ve_table,
    )
    from dynoai_v3.grid_utils import nearest_idx

    session = _get_session(session_id)

    # ---- 0. Resolve target from advisor if not specified ----
    if rpm is None or map_kpa is None:
        if session.advisor is None:
            raise RuntimeError("Session not initialized")
        rec = session.advisor.suggest_next_pull()
        rpm = rpm or rec.rpm
        map_kpa = map_kpa or rec.map_kpa

    # ---- 1. Get session's authoritative grid ----
    rpm_bins = session.surrogate.rpm_bins.tolist()
    map_bins = session.surrogate.map_bins.tolist()

    # Map engine family → EngineProfile
    _PROFILE_MAP = {
        "m8_107": EngineProfile.m8_114,
        "m8_114": EngineProfile.m8_114,
        "m8_117": EngineProfile.m8_114,
        "m8_131": EngineProfile.m8_131,
        "evo_1200": EngineProfile.twin_cam_103,
        "revmax_1250": EngineProfile.m8_131,
    }
    profile_fn = _PROFILE_MAP.get(session.config.engine_family, EngineProfile.m8_114)
    profile = profile_fn()

    # ---- 2. Build VirtualECU on session grid ----
    # Use an intentionally-wrong VE table so the sim produces AFR errors
    rpm_bins_int = [int(r) for r in rpm_bins]
    map_bins_int = [int(m) for m in map_bins]

    baseline_ve = create_baseline_ve_table(rpm_bins_int, map_bins_int, peak_ve=0.85)
    wrong_ve = create_intentionally_wrong_ve_table(
        baseline_ve, error_pct_mean=-8.0, error_pct_std=4.0,
        seed=int(rpm + map_kpa),
    )
    afr_targets = create_afr_target_table(rpm_bins_int, map_bins_int)

    ecu = VirtualECU(
        ve_table_front=wrong_ve,
        ve_table_rear=wrong_ve,
        afr_target_table=afr_targets,
        rpm_bins=rpm_bins_int,
        map_bins=map_bins_int,
        displacement_ci=float(session.config.displacement_ci or 114),
    )

    # ---- 3. Run DynoSimulator physics pull ----
    sim_config = SimulatorConfig(
        profile=profile,
        enable_thermal_effects=True,
        auto_pull=False,
        time_scale=5.0,  # 5x speed for faster sim
    )
    simulator = DynoSimulator(config=sim_config, virtual_ecu=ecu)
    simulator.start()
    _time.sleep(0.3)

    simulator.trigger_pull()
    _time.sleep(0.2)

    # Wait for pull completion (max 15s real time)
    max_wait = 150  # 15s at 10 checks/sec
    for _ in range(max_wait):
        if simulator.get_state() == SimState.IDLE:
            break
        _time.sleep(0.1)

    pull_data = simulator.get_pull_data()
    simulator.stop()

    if not pull_data or len(pull_data) < 5:
        # Fallback: if simulator didn't produce enough data, use quick mode
        logger.warning(
            "Simulator produced only %d points, falling back to quick mode",
            len(pull_data) if pull_data else 0,
        )
        return simulate_pull(session_id, rpm=rpm, map_kpa=map_kpa)

    logger.info("Simulator pull complete: %d data points", len(pull_data))

    # ---- 4. Pipe through AutoTuneWorkflow on SESSION grid ----
    df = pd.DataFrame(pull_data)

    workflow = AutoTuneWorkflow(
        rpm_axis=[float(r) for r in rpm_bins],
        map_axis=[float(m) for m in map_bins],
    )
    ws = workflow.create_session()
    workflow.import_dataframe(ws, df)
    afr_result = workflow.analyze_afr(ws)
    corrections = workflow.calculate_corrections(ws)

    if corrections is None:
        logger.warning("AutoTuneWorkflow produced no corrections, using quick mode")
        return simulate_pull(session_id, rpm=rpm, map_kpa=map_kpa)

    # ---- 5. Convert grid corrections → per-observation VE deltas ----
    rpm_arr = df["Engine RPM"].values.astype(np.float64)
    map_arr = df["MAP kPa"].values.astype(np.float64)
    ve_deltas = np.zeros(len(df), dtype=np.float64)

    for i in range(len(df)):
        r_idx = nearest_idx(rpm_arr[i], rpm_bins)
        m_idx = nearest_idx(map_arr[i], map_bins)
        ve_deltas[i] = (corrections.correction_table[r_idx, m_idx] - 1.0) * 100.0

    # ---- 6. Ingest into v3 session ----
    result = session.ingest_pull(rpm_arr, map_arr, ve_deltas)

    # AFR metrics for frontend display
    afr_metrics = None
    if afr_result is not None:
        afr_errors = df.get("AFR Meas F", pd.Series(dtype=float))
        afr_targets_col = df.get("AFR Target", pd.Series(dtype=float))
        if len(afr_errors) > 0 and len(afr_targets_col) > 0:
            errs = (afr_errors - afr_targets_col).abs()
            afr_metrics = {
                "max_afr_error": float(errs.max()) if len(errs) > 0 else 0.0,
                "mean_afr_error": float(errs.mean()) if len(errs) > 0 else 0.0,
                "data_points": len(df),
                "zones_corrected": corrections.zones_adjusted,
                "max_ve_correction_pct": corrections.max_correction_pct,
            }

    logger.info(
        "Realistic sim pull at RPM=%.0f MAP=%.0f: %d points, %d zones corrected",
        rpm, map_kpa, len(df), corrections.zones_adjusted,
    )

    return {
        "pull_number": result.pull_number,
        "observations_added": result.observations_added,
        "target_rpm": float(rpm),
        "target_map_kpa": float(map_kpa),
        "convergence": _convergence_to_dict(result.convergence) if result.convergence else None,
        "next_suggestion": _rec_to_dict(result.next_suggestion) if result.next_suggestion else None,
        "mode": "realistic",
        "afr_metrics": afr_metrics,
    }


def simulate_pull(
    session_id: str,
    rpm: Optional[float] = None,
    map_kpa: Optional[float] = None,
    n_points: int = 8,
) -> Dict[str, Any]:
    """
    Generate synthetic pull data and ingest it into the session.

    If rpm/map_kpa not provided, uses the advisor's next recommendation.
    Generates realistic scatter around the target point with VE deltas
    based on realistic noise patterns.

    Args:
        session_id: Session ID
        rpm: Target RPM (optional, defaults to next advisor suggestion)
        map_kpa: Target MAP (optional, defaults to next advisor suggestion)
        n_points: Number of data points to generate (default 8)

    Returns:
        PullResult dict
    """
    session = _get_session(session_id)

    # If no target specified, use advisor's next recommendation
    if rpm is None or map_kpa is None:
        if session.advisor is None:
            raise RuntimeError("Session not initialized")
        rec = session.advisor.suggest_next_pull()
        rpm = rpm or rec.rpm
        map_kpa = map_kpa or rec.map_kpa

    # Generate synthetic data with realistic scatter
    rng = np.random.RandomState(int(rpm + map_kpa + len(session.surrogate.observations)))

    # RPM scatter: +/- 100 RPM around target
    rpm_arr = rpm + rng.randn(n_points) * 100

    # MAP scatter: +/- 5 kPa around target
    map_arr = map_kpa + rng.randn(n_points) * 5

    # VE deltas: realistic base value + noise
    # Base value varies by load (higher MAP = more correction needed)
    base_ve = (map_kpa - 60) / 40 * 3.0  # -2.25 to +3.375 range
    rpm_effect = np.sin(rpm / 1500) * 1.5
    ve_base = base_ve + rpm_effect

    # Add noise
    ve_arr = ve_base + rng.randn(n_points) * 0.3

    # Ingest into session
    result = session.ingest_pull(rpm_arr, map_arr, ve_arr)

    logger.info(
        "Simulated pull at RPM=%.0f MAP=%.0f: %d points generated",
        rpm, map_kpa, n_points,
    )

    return {
        "pull_number": result.pull_number,
        "observations_added": result.observations_added,
        "target_rpm": float(rpm),
        "target_map_kpa": float(map_kpa),
        "convergence": _convergence_to_dict(result.convergence) if result.convergence else None,
        "next_suggestion": _rec_to_dict(result.next_suggestion) if result.next_suggestion else None,
        "mode": "quick",
        "afr_metrics": None,
    }
