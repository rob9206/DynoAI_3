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

import csv
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from api.config import get_config
from api.errors import ValidationError
from dynoai.core.ve_math import calculate_ve_correction, correction_to_percentage
from dynoai.core.afr_targets import get_target_afr_for_map

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory session store (thread-safe)
# ---------------------------------------------------------------------------
_sessions: Dict[str, Any] = {}  # session_id → TuningSession
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
    d: Dict[str, Any] = {
        "rpm": rec.rpm,
        "map_kpa": rec.map_kpa,
        "gear": rec.gear,
        "pull_number": rec.pull_number,
        "pull_type": (
            rec.pull_type.value
            if hasattr(rec.pull_type, "value")
            else str(rec.pull_type)
        ),
        "reason": rec.reason,
        "expected_info_gain": rec.expected_info_gain,
        "remaining_uncertainty": rec.remaining_uncertainty,
        "throttle_pct": rec.throttle_pct,
        "alternatives": [_rec_to_dict(a) for a in (rec.alternatives or [])],
    }
    # pull_mode was added in v3.1 — include if present
    if hasattr(rec, "pull_mode"):
        d["pull_mode"] = (
            rec.pull_mode.value
            if hasattr(rec.pull_mode, "value")
            else str(rec.pull_mode)
        )
    return d


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


def _validate_bins(label: str, bins: List[float]) -> np.ndarray:
    if not isinstance(bins, list) or len(bins) == 0:
        raise ValidationError(f"{label} must be a non-empty list")
    return np.array(bins, dtype=np.float64)


def _ensure_bins_match(
    label: str,
    session_bins: np.ndarray,
    provided_bins: np.ndarray,
    *,
    atol: float = 1e-3,
) -> None:
    if session_bins.shape != provided_bins.shape:
        raise ValidationError(f"{label} bins do not match the session grid")
    if not np.allclose(session_bins, provided_bins, atol=atol):
        raise ValidationError(f"{label} bins do not match the session grid")


def _iso_utc_now() -> str:
    """Return an RFC3339-ish UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _format_float(value: float, precision: int = 6) -> str:
    """Format float for CSV/JSON while avoiding noisy trailing zeros."""
    formatted = f"{float(value):.{precision}f}"
    # Only strip trailing zeros after decimal point, not all trailing zeros
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def _normalize_multiplier_grid(
    corrections: np.ndarray,
    fmt: str = "multiplier",
) -> np.ndarray:
    """
    Normalize correction values to multiplier grid (1.0 = no change).
    """
    if fmt == "multiplier":
        return np.asarray(corrections, dtype=np.float64)
    # percentage (+5 means +5%) -> multiplier (1.05)
    return 1.0 + (np.asarray(corrections, dtype=np.float64) / 100.0)


def _multiplier_to_percent_grid(multiplier_grid: np.ndarray) -> np.ndarray:
    """
    Convert multiplier grid to VEApply-compatible percent delta grid.
    Example: 1.05 -> +5.0, 0.93 -> -7.0
    """
    arr = np.asarray(multiplier_grid, dtype=np.float64)
    return (arr - 1.0) * 100.0


def _cache_latest_corrections(
    session: Any,
    correction_grid: np.ndarray,
    rpm_bins: np.ndarray,
    map_bins: np.ndarray,
    *,
    source: str,
    pull_number: Optional[int] = None,
) -> None:
    """Store latest correction surface on session for materialization/export."""
    setattr(
        session,
        "_latest_corrections",
        {
            "correction_grid": np.asarray(correction_grid, dtype=np.float64).copy(),
            "rpm_bins": np.asarray(rpm_bins, dtype=np.float64).copy(),
            "map_bins": np.asarray(map_bins, dtype=np.float64).copy(),
            "source": source,
            "pull_number": pull_number,
            "updated_at": _iso_utc_now(),
        },
    )


def _materialize_latest_run(session_id: str, session: Any) -> Dict[str, Any]:
    """
    Persist the latest cached correction grid into a run folder compatible with /api/apply.
    """
    latest = getattr(session, "_latest_corrections", None)
    if not isinstance(latest, dict):
        raise ValidationError(
            "No cached v3 corrections found for this session. Run Analyze/Update first."
        )

    correction_grid = latest.get("correction_grid")
    rpm_bins = latest.get("rpm_bins")
    map_bins = latest.get("map_bins")
    if correction_grid is None or rpm_bins is None or map_bins is None:
        raise ValidationError(
            "Cached v3 corrections are incomplete; run Analyze/Update again."
        )

    correction_array = np.asarray(correction_grid, dtype=np.float64)
    percent_delta_array = _multiplier_to_percent_grid(correction_array)
    rpm_array = np.asarray(rpm_bins, dtype=np.float64)
    map_array = np.asarray(map_bins, dtype=np.float64)
    if correction_array.ndim != 2:
        raise ValidationError("Cached correction grid must be 2D.")
    if correction_array.shape != (len(rpm_array), len(map_array)):
        raise ValidationError(
            "Cached correction grid dimensions do not match cached RPM/MAP bins."
        )

    config = get_config()
    timestamp = datetime.now(timezone.utc)
    ts_compact = timestamp.strftime("%Y%m%d_%H%M%S")
    run_id = f"v3_{session_id[:8]}_{ts_compact}"

    run_dir = config.storage.runs_folder / run_id
    suffix = 1
    while run_dir.exists():
        run_id = f"v3_{session_id[:8]}_{ts_compact}_{suffix}"
        run_dir = config.storage.runs_folder / run_id
        suffix += 1
    run_dir.mkdir(parents=True, exist_ok=False)

    ve_2d_path = run_dir / "VE_Corrections_2D.csv"
    ve_delta_path = run_dir / "VE_Correction_Delta_DYNO.csv"

    map_headers = [_format_float(v, 3) for v in map_array.tolist()]
    rpm_headers = [_format_float(v, 0) for v in rpm_array.tolist()]

    # JetDrive-style table.
    with open(ve_2d_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["RPM\\MAP", *map_headers])
        for row_idx, rpm in enumerate(rpm_headers):
            row_values = [
                _format_float(v, 6) for v in percent_delta_array[row_idx].tolist()
            ]
            writer.writerow([rpm, *row_values])

    # Legacy apply-compatible table (preferred by /api/apply if present).
    with open(ve_delta_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["RPM", *map_headers])
        for row_idx, rpm in enumerate(rpm_headers):
            row_values = [
                _format_float(v, 6) for v in percent_delta_array[row_idx].tolist()
            ]
            writer.writerow([rpm, *row_values])

    materialized_at = _iso_utc_now()
    manifest = {
        "source": "v3_materialized",
        "session_id": session_id,
        "materialized_at": materialized_at,
        "generated_files": [ve_2d_path.name, ve_delta_path.name],
        "grid": {
            "rows": int(correction_array.shape[0]),
            "cols": int(correction_array.shape[1]),
            "rpm_bins": rpm_array.tolist(),
            "map_bins": map_array.tolist(),
            "correction_units": "percent_delta",
        },
        "latest_corrections_meta": {
            "updated_at": latest.get("updated_at"),
            "source": latest.get("source"),
            "pull_number": latest.get("pull_number"),
        },
    }
    with open(run_dir / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    return {
        "success": True,
        "run_id": run_id,
        "session_id": session_id,
        "materialized_at": materialized_at,
    }


# ---------------------------------------------------------------------------
# Public API (called by routes)
# ---------------------------------------------------------------------------


def _import_ve_table_to_delta(table: List[List[float]]) -> Optional[np.ndarray]:
    """
    Convert imported VE table to absolute VE percentages.

    Power Vision PVV stores absolute VE as percentages (70-113%). Templates may store
    correction factors (~0.5-1.5). This function normalizes both to absolute VE %.

    Note: Despite the function name, this now returns absolute VE values, not deltas.
    The GP model predicts absolute VE percentages directly.

    Returns:
        Absolute VE array (70-113%), or None if table is all zeros (invalid import)
    """
    arr = np.asarray(table, dtype=np.float64)

    # Debug logging
    logger.info(
        "Import VE conversion: shape=%s, min=%.2f, max=%.2f, mean=%.2f, sample(top-left 3x3)=%s",
        arr.shape,
        np.min(arr),
        np.max(arr),
        np.mean(arr),
        arr[:3, :3].tolist() if arr.size > 0 else "empty",
    )

    # Skip all-zero table (failed parse)
    if np.all(arr == 0):
        logger.warning("Imported VE table is all zeros; skipping seed")
        return None

    # If values are large (> 2), treat as absolute VE percentages (70-113%)
    if np.max(np.abs(arr)) > 2.0:
        logger.info(
            "Treating as absolute VE %% (values > 2): min=%.2f, max=%.2f, mean=%.2f",
            np.min(arr),
            np.max(arr),
            np.mean(arr),
        )
        return arr  # Return absolute VE values directly

    # If values are small (<= 2), treat as correction factors (0.7-1.13) → convert to %
    absolute_ve = arr * 100.0  # correction factor → absolute VE %
    logger.info(
        "Converted correction factor to absolute VE %%: min=%.2f, max=%.2f, mean=%.2f",
        np.min(absolute_ve),
        np.max(absolute_ve),
        np.mean(absolute_ve),
    )
    return absolute_ve


def create_session(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new TuningSession, initialize it, and return status."""
    from dynoai_v3.session_orchestrator import TuningSession
    from dynoai_v3.template_library import HardwareConfig

    config = HardwareConfig.from_dict(config_dict)

    # Explicit bin extraction (in case from_dict filtering drops them)
    if config.rpm_bins is None and "rpm_bins" in config_dict:
        config.rpm_bins = config_dict["rpm_bins"]
    if config.map_bins is None and "map_bins" in config_dict:
        config.map_bins = config_dict["map_bins"]

    # Diagnostic logging to confirm PVV bins are flowing through
    logger.info(
        "Session config: engine=%s, rpm_bins=%s, map_bins=%s, has_import=%s",
        config.engine_family,
        f"{len(config.rpm_bins)} bins" if config.rpm_bins else "None",
        f"{len(config.map_bins)} bins" if config.map_bins else "None",
        bool(config_dict.get("initial_ve_table")),
    )

    session = TuningSession(config, templates_dir=_TEMPLATES_DIR)

    # Check if user provided an import; if so, skip template seeding
    has_import = bool(config_dict.get("initial_ve_table"))
    init = session.initialize(skip_template_seed=has_import)

    # Seed GP from imported tune if provided (so Uncertainty Map shows it, not zeros)
    initial_ve = config_dict.get("initial_ve_table")
    if initial_ve and session.surrogate is not None:
        try:
            delta = _import_ve_table_to_delta(initial_ve)
            if delta is not None:
                # Validate shape matches session grid
                expected_shape = (
                    len(session.surrogate.rpm_bins),
                    len(session.surrogate.map_bins),
                )
                actual_shape = delta.shape
                if actual_shape != expected_shape:
                    logger.warning(
                        "initial_ve_table shape %s does not match session grid %s; "
                        "will use overlapping region only",
                        actual_shape,
                        expected_shape,
                    )

                session.surrogate.seed_from_template(
                    delta,
                    session.surrogate.rpm_bins,
                    session.surrogate.map_bins,
                )
                logger.info("GP seeded from imported tune (%d cells)", int(delta.size))
        except Exception as e:
            logger.warning("Could not seed from initial_ve_table: %s", e)

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


def import_base_ve(
    session_id: str,
    ve_table: List[List[float]],
    rpm_bins: List[float],
    map_bins: List[float],
) -> Dict[str, Any]:
    """Seed the GP surrogate with an imported base VE table."""
    from dynoai_v3.session_orchestrator import SessionState

    session = _get_session(session_id)
    if session.surrogate is None:
        raise ValidationError("Session not initialized")
    if session.state != SessionState.READY:
        raise ValidationError("Base VE import is only allowed before the first pull")

    if not isinstance(ve_table, list) or len(ve_table) == 0:
        raise ValidationError("ve_table must be a non-empty 2D array")

    rpm_bins_arr = _validate_bins("rpm_bins", rpm_bins)
    map_bins_arr = _validate_bins("map_bins", map_bins)
    _ensure_bins_match("RPM", session.surrogate.rpm_bins, rpm_bins_arr)
    _ensure_bins_match("MAP", session.surrogate.map_bins, map_bins_arr)

    ve_array = np.array(ve_table, dtype=np.float64)
    if ve_array.ndim != 2:
        raise ValidationError("ve_table must be a 2D array")

    # Replace any template observations with the imported base VE table.
    session.surrogate.observations = []
    session.surrogate.template_observation_count = 0
    session.surrogate.is_fitted = False
    session.surrogate._gp_model = None

    session.surrogate.seed_from_template(
        ve_array,
        rpm_bins_arr,
        map_bins_arr,
    )

    return {
        "status": "seeded",
        "observations_added": session.surrogate.template_observation_count,
    }


def ingest_pull(
    session_id: str,
    rpm: List[float],
    map_kpa: List[float],
    ve: Optional[List[float]] = None,
    afr: Optional[List[float]] = None,
    target_afr: Optional[List[float]] = None,
    base_ve: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Ingest pull data and return result.
    
    Accepts either pre-calculated Absolute VE OR raw AFR data.
    If AFR is provided, base_ve is highly recommended to calculate precise Absolute VE.
    If base_ve is missing, it will assume the surrogate's current prediction or a default
    (which may be inaccurate, so providing base_ve is preferred).
    """
    session = _get_session(session_id)
    
    # helper: validate and convert to numpy
    rpm_arr = np.array(rpm, dtype=np.float64)
    map_arr = np.array(map_kpa, dtype=np.float64)
    
    # 1. Determine Absolute VE
    if ve is not None:
        # Trust provided Absolute VE (legacy/frontend-calculated)
        ve_arr = np.array(ve, dtype=np.float64)
    
    elif afr is not None:
        # Calculate from AFR using Core Math
        afr_arr = np.array(afr, dtype=np.float64)
        count = len(afr_arr)
        
        # Determine targets
        if target_afr is not None:
            target_arr = np.array(target_afr, dtype=np.float64)
        else:
            # Lookup targets based on MAP
            target_arr = np.zeros(count, dtype=np.float64)
            for i in range(count):
                target_arr[i] = get_target_afr_for_map(float(map_arr[i]))
                
        # Determine Base VE (defaults to 100.0 if missing - simplistic but prevents crash)
        if base_ve is not None:
            base_ve_arr = np.array(base_ve, dtype=np.float64)
        else:
            logger.warning("Ingesting AFR without base_ve; assuming Base VE = 80.0 for calculation.")
            base_ve_arr = np.full(count, 80.0, dtype=np.float64)

        # Calculate Absolute VE using rigorous math
        # Correction = Measured / Target
        # AbsoluteVE = BaseVE * Correction
        ve_absolute_list = []
        for i in range(count):
            measured = float(afr_arr[i])
            target = float(target_arr[i])
            base = float(base_ve_arr[i])
            
            # Use Core Math for calculation
            correction = calculate_ve_correction(measured, target)
            
            # Calculate New Absolute VE
            new_ve = base * correction
            ve_absolute_list.append(new_ve)
            
        ve_arr = np.array(ve_absolute_list, dtype=np.float64)
        
        logger.info(
            "Calculated %d Absolute VE values from AFR (mean: %.2f%%)", 
            count, np.mean(ve_arr)
        )
        
    else:
        raise ValidationError("Either 've' or 'afr' data is required")

    result = session.ingest_pull(
        rpm_arr,
        map_arr,
        ve_arr,
    )
    return {
        "pull_number": result.pull_number,
        "observations_added": result.observations_added,
        "convergence": (
            _convergence_to_dict(result.convergence) if result.convergence else None
        ),
        "next_suggestion": (
            _rec_to_dict(result.next_suggestion) if result.next_suggestion else None
        ),
    }


def import_corrections(
    session_id: str,
    corrections: List[List[float]],
    rpm_bins: List[float],
    map_bins: List[float],
    fmt: str,
) -> Dict[str, Any]:
    """Import correction grid into the session as synthetic observations."""
    from dynoai_v3.session_orchestrator import SessionState

    session = _get_session(session_id)
    if session.surrogate is None:
        raise ValidationError("Session not initialized")
    if session.state == SessionState.COMPLETE:
        raise ValidationError("Corrections cannot be imported after completion")

    if fmt not in ("multiplier", "percentage"):
        raise ValidationError("format must be 'multiplier' or 'percentage'")
    if not isinstance(corrections, list) or len(corrections) == 0:
        raise ValidationError("corrections must be a non-empty 2D array")

    rpm_bins_arr = _validate_bins("rpm_bins", rpm_bins)
    map_bins_arr = _validate_bins("map_bins", map_bins)
    _ensure_bins_match("RPM", session.surrogate.rpm_bins, rpm_bins_arr)
    _ensure_bins_match("MAP", session.surrogate.map_bins, map_bins_arr)

    corr_array = np.array(corrections, dtype=np.float64)
    if corr_array.ndim != 2:
        raise ValidationError("corrections must be a 2D array")

    # Cache imported grid for potential materialization/apply bridge.
    multiplier_grid = _normalize_multiplier_grid(corr_array, fmt=fmt)
    _cache_latest_corrections(
        session,
        multiplier_grid,
        rpm_bins_arr,
        map_bins_arr,
        source="import_corrections",
    )

    rpm_values: List[float] = []
    map_values: List[float] = []
    ve_deltas: List[float] = []

    for r_idx, rpm in enumerate(rpm_bins_arr):
        for m_idx, map_kpa in enumerate(map_bins_arr):
            if r_idx >= corr_array.shape[0] or m_idx >= corr_array.shape[1]:
                continue
            raw = float(corr_array[r_idx, m_idx])
            if fmt == "multiplier":
                delta_pct = (raw - 1.0) * 100.0
            else:
                delta_pct = raw

            if abs(delta_pct) < 1e-6:
                continue

            rpm_values.append(float(rpm))
            map_values.append(float(map_kpa))
            ve_deltas.append(delta_pct)

    if len(ve_deltas) == 0:
        return {
            "status": "imported",
            "observations_added": 0,
            "convergence": (
                _convergence_to_dict(session._convergence)
                if session._convergence
                else None
            ),
        }

    result = session.ingest_pull(
        np.array(rpm_values, dtype=np.float64),
        np.array(map_values, dtype=np.float64),
        np.array(ve_deltas, dtype=np.float64),
    )

    return {
        "status": "imported",
        "observations_added": result.observations_added,
        "convergence": (
            _convergence_to_dict(result.convergence) if result.convergence else None
        ),
        "next_suggestion": (
            _rec_to_dict(result.next_suggestion) if result.next_suggestion else None
        ),
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

    # Best-effort cleanup of any per-session simulation assets.
    # (simulate_pull_realistic keeps a simulator running for performance.)
    try:
        cache = getattr(session, "_realistic_sim_cache", None)
        sim = cache.get("simulator") if isinstance(cache, dict) else None
        if sim is not None:
            sim.stop()
    except Exception:
        pass

    return {
        "template_id": result.template_id,
        "total_pulls": result.total_pulls,
        "session_id": result.session_id,
        "session_duration_s": result.session_duration_s,
    }


def materialize_run(session_id: str) -> Dict[str, Any]:
    """Persist latest v3 correction surface to a run artifact folder."""
    session = _get_session(session_id)
    return _materialize_latest_run(session_id, session)


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
        SimState,
        SimulatorConfig,
    )
    from api.services.simulation.virtual_ecu import (
        VirtualECU,
        create_afr_target_table,
        create_baseline_ve_table,
        create_intentionally_wrong_ve_table,
    )

    session = _get_session(session_id)

    # ---- 0. Resolve target from advisor if not specified ----
    # Also capture pull_mode so we can route acceleration vs steady-state.
    _pull_mode_value = "acceleration"  # default
    if rpm is None or map_kpa is None:
        if session.advisor is None:
            raise RuntimeError("Session not initialized")
        rec = session.advisor.suggest_next_pull()
        rpm = rpm or rec.rpm
        map_kpa = map_kpa or rec.map_kpa
        if hasattr(rec, "pull_mode"):
            _pull_mode_value = (
                rec.pull_mode.value
                if hasattr(rec.pull_mode, "value")
                else str(rec.pull_mode)
            )

    # ---- 1. Get session's authoritative grid ----
    rpm_bins = session.surrogate.rpm_bins.tolist()
    map_bins = session.surrogate.map_bins.tolist()

    # Map engine family → EngineProfile
    _PROFILE_MAP = {
        "m8_107": EngineProfile.m8_114,
        "m8_114": EngineProfile.m8_114,
        "m8_117": EngineProfile.m8_114,
        "m8_131": EngineProfile.m8_131,
        "tc_88": EngineProfile.twin_cam_88,
        "tc_96": EngineProfile.twin_cam_96,
        "tc_103": EngineProfile.twin_cam_103,
        "tc_110": EngineProfile.twin_cam_110,
        "evo_1200": EngineProfile.twin_cam_103,
        "revmax_975": EngineProfile.revmax_975,
        "revmax_1250": EngineProfile.revmax_1250,
    }
    profile_fn = _PROFILE_MAP.get(session.config.engine_family, EngineProfile.m8_114)
    profile = profile_fn()

    # ---- 2/3. Build/reuse per-session simulation assets ----
    # For performance, keep the simulator (thread + physics) running across pulls.
    # This endpoint is for development/demo; we prefer responsiveness over perfect
    # reproducibility on every call.
    rpm_bins_int = tuple(int(r) for r in rpm_bins)
    map_bins_int = tuple(int(m) for m in map_bins)
    displacement_ci = float(session.config.displacement_ci or 114)
    cache_key = (
        session.config.engine_family,
        rpm_bins_int,
        map_bins_int,
        displacement_ci,
    )

    cache = getattr(session, "_realistic_sim_cache", None)
    if not isinstance(cache, dict) or cache.get("key") != cache_key:
        # Tear down any old simulator
        try:
            old_sim = cache.get("simulator") if isinstance(cache, dict) else None
            if old_sim is not None:
                old_sim.stop()
        except Exception:
            pass

        baseline_ve = create_baseline_ve_table(
            list(rpm_bins_int), list(map_bins_int), peak_ve=0.85
        )
        # Seed once per session so VirtualECU interpolators can be reused.
        seed = abs(hash(getattr(session, "session_id", session_id))) % (2**31 - 1)
        wrong_ve = create_intentionally_wrong_ve_table(
            baseline_ve,
            error_pct_mean=-8.0,
            error_pct_std=4.0,
            seed=int(seed),
        )
        afr_targets = create_afr_target_table(list(rpm_bins_int), list(map_bins_int))

        ecu = VirtualECU(
            ve_table_front=wrong_ve,
            ve_table_rear=wrong_ve,
            afr_target_table=afr_targets,
            rpm_bins=list(rpm_bins_int),
            map_bins=list(map_bins_int),
            displacement_ci=displacement_ci,
        )

        sim_config = SimulatorConfig(
            profile=profile,
            enable_thermal_effects=True,
            auto_pull=False,
            time_scale=5.0,  # 5x speed for faster sim
        )
        simulator = DynoSimulator(config=sim_config, virtual_ecu=ecu)
        simulator.start()
        _time.sleep(0.3)

        workflow = AutoTuneWorkflow(
            rpm_axis=[float(r) for r in rpm_bins],
            map_axis=[float(m) for m in map_bins],
        )

        cache = {
            "key": cache_key,
            "ecu": ecu,
            "simulator": simulator,
            "workflow": workflow,
            "wrong_ve": wrong_ve,  # Store for VE conversion later
            "lock": threading.Lock(),
        }
        setattr(session, "_realistic_sim_cache", cache)
    else:
        simulator = cache["simulator"]
        workflow = cache["workflow"]
        # Ensure simulator is running
        try:
            if simulator.get_state() == SimState.STOPPED:
                simulator.start()
                _time.sleep(0.3)
        except Exception:
            pass

    # ---- 3. Run DynoSimulator physics pull ----
    # Guard against concurrent simulate calls on the same session.
    # Route to acceleration (WOT sweep) or steady-state (eddy brake RPM hold)
    # based on the advisor's pull_mode for this recommendation.
    lock = cache.get("lock") if isinstance(cache, dict) else None
    if lock is None:
        lock = threading.Lock()
    with lock:
        if _pull_mode_value == "steady_state":
            # Cruise / part-throttle: use eddy brake RPM hold for clean data.
            # Steady-state won't hit redline, so we collect data for a fixed
            # duration then close throttle to trigger the decel transition.
            throttle_for_map = min(100.0, max(0.0, (map_kpa - 25) / 0.75))
            logger.info(
                "Steady-state pull: RPM=%.0f, MAP=%.0f, throttle=%.0f%%",
                rpm,
                map_kpa,
                throttle_for_map,
            )
            simulator.trigger_steady_state(
                throttle_pct=throttle_for_map,
                target_rpm=rpm,
            )
            # Let the engine stabilise at the target RPM (3-5s real time)
            _time.sleep(0.8)  # 0.8s real × 5x time_scale = ~4s sim time

            # Close throttle to trigger PULL→DECEL transition
            simulator.physics.tps_target = 0.0
            _time.sleep(0.2)

            # Wait for decel → cooldown → idle (max 10s)
            for _ in range(100):
                if simulator.get_state() == SimState.IDLE:
                    break
                _time.sleep(0.1)
        else:
            # Preserve the operator-selected simulator throttle instead of forcing WOT.
            # This keeps manual Trigger Pull behavior consistent with the UI slider.
            current_tps_target = float(getattr(simulator.physics, "tps_target", 100.0))
            throttle_pct = max(0.0, min(100.0, current_tps_target))
            simulator.trigger_pull(throttle_pct=throttle_pct)
            _time.sleep(0.2)

            # Wait for pull completion (max 15s real time)
            for _ in range(150):
                if simulator.get_state() == SimState.IDLE:
                    break
                _time.sleep(0.1)

        pull_data = simulator.get_pull_data()

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

    try:
        ws = workflow.create_session()
        workflow.import_dataframe(ws, df)
        afr_result = workflow.analyze_afr(ws)
        corrections = workflow.calculate_corrections(ws)

        if corrections is None:
            logger.warning("AutoTuneWorkflow produced no corrections, using quick mode")
            return simulate_pull(session_id, rpm=rpm, map_kpa=map_kpa)

        # Validate corrections table shape
        expected_shape = (len(rpm_bins), len(map_bins))
        if corrections.correction_table.shape != expected_shape:
            logger.error(
                "Correction table shape %s != expected %s; falling back to quick mode",
                corrections.correction_table.shape,
                expected_shape,
            )
            return simulate_pull(session_id, rpm=rpm, map_kpa=map_kpa)

        logger.info(
            "AutoTuneWorkflow complete: correction range [%.3f, %.3f]",
            np.min(corrections.correction_table),
            np.max(corrections.correction_table),
        )
    except Exception as e:
        logger.error(
            "AutoTuneWorkflow failed: %s; falling back to quick mode", e, exc_info=True
        )
        return simulate_pull(session_id, rpm=rpm, map_kpa=map_kpa)

    # ---- 5. Convert grid corrections → per-observation VE deltas ----
    rpm_arr = df["Engine RPM"].values.astype(np.float64)
    map_arr = df["MAP kPa"].values.astype(np.float64)

    rpm_bins_arr = np.asarray(rpm_bins, dtype=np.float64)
    map_bins_arr = np.asarray(map_bins, dtype=np.float64)

    def _nearest_bin_indices(values: np.ndarray, bins: np.ndarray) -> np.ndarray:
        # bins must be sorted ascending
        n = int(bins.shape[0])
        idx_right = np.searchsorted(bins, values, side="left")
        idx_right = np.clip(idx_right, 0, n - 1)
        idx_left = np.clip(idx_right - 1, 0, n - 1)

        left_dist = np.abs(values - bins[idx_left])
        right_dist = np.abs(bins[idx_right] - values)
        choose_left = left_dist <= right_dist
        return np.where(choose_left, idx_left, idx_right).astype(np.int64)

    r_idx = _nearest_bin_indices(rpm_arr, rpm_bins_arr)
    m_idx = _nearest_bin_indices(map_arr, map_bins_arr)

    # Get baseline VE from the "wrong" ECU table (the one being corrected)
    # wrong_ve is stored as fractions (0.7-1.1), corrections are multipliers (~0.95-1.05)
    # GP model expects absolute VE percentages (70-113%)
    # Strategy: Convert wrong_ve to %, then apply correction multiplier
    wrong_ve_baseline = cache.get("wrong_ve") if cache else None
    if wrong_ve_baseline is not None:
        # Validate shapes before indexing
        if wrong_ve_baseline.shape != corrections.correction_table.shape:
            logger.error(
                "Shape mismatch: wrong_ve %s != correction_table %s; using fallback",
                wrong_ve_baseline.shape,
                corrections.correction_table.shape,
            )
            wrong_ve_baseline = None  # Fall through to fallback
        else:
            # Convert wrong_ve fractions to percentages, then apply correction multiplier
            wrong_ve_pct = wrong_ve_baseline[r_idx, m_idx] * 100.0  # 0.85 → 85%
            ve_values = (
                wrong_ve_pct * corrections.correction_table[r_idx, m_idx]
            )  # 85% * 1.05 = 89.25%
            logger.debug(
                "VE conversion: wrong_ve range [%.2f, %.2f], corrected range [%.2f, %.2f]",
                wrong_ve_pct.min(),
                wrong_ve_pct.max(),
                ve_values.min(),
                ve_values.max(),
            )

    if wrong_ve_baseline is None:
        # Fallback: assume wrong_ve was around 85% and corrections fix it
        logger.warning("No baseline VE available, using estimated absolute values")
        base_ve_pct = 85.0
        ve_values = base_ve_pct * corrections.correction_table[r_idx, m_idx]

    # ---- 6. Ingest into v3 session ----
    # Use the new Math Integration path!
    # Instead of calculating VE here, we pass raw AFR + Target + Base VE.
    # formatting: extracting numpy arrays from dataframe/tables
    
    afr_meas = df["AFR Meas F"].values.astype(np.float64)
    afr_target = df["AFR Target"].values.astype(np.float64)
    
    # We need Base VE for every point. Look it up from wrong_ve_baseline.
    base_ve_values = []
    if wrong_ve_baseline is not None:
         # Convert from fraction to percent 
         base_ve_values = wrong_ve_baseline[r_idx, m_idx] * 100.0
    else:
         # Fallback
         base_ve_values = np.full(len(afr_meas), 85.0, dtype=np.float64)
         
    logger.info(
        "Ingesting %d simulated points via AFR/BaseVE path. Mean Base VE: %.1f%%",
        len(afr_meas),
        np.mean(base_ve_values) if len(base_ve_values) > 0 else 0.0
    )
    
    # DEBUG: Print sample of data
    if len(afr_meas) > 0:
        logger.debug(f"DEBUG SAMPLE: AFR={afr_meas[:3]}, Target={afr_target[:3]}, BaseVE={base_ve_values[:3]}")
    else:
        logger.warning("DEBUG: afr_meas is EMPTY! Simulator produced no valid AFR data.")

    # Call the PUBLIC service ingest_pull (not session.ingest_pull directly) 
    # so it triggers the calculation logic we just added.
    # Note: simulate_pull_realistic is inside v3_session_service, so we recurse 
    # to the top-level ingest_pull function defined in this module.
    result_dict = ingest_pull(
        session_id=session_id,
        rpm=rpm_arr.tolist(),
        map_kpa=map_arr.tolist(),
        afr=afr_meas.tolist(),
        target_afr=afr_target.tolist(),
        base_ve=base_ve_values.tolist()
    )
    
    # Unpack the dict result to match local variables expected below
    observations_added = result_dict["observations_added"]
    pull_number = result_dict["pull_number"]

    # We still want to cache the "grid corrections" from AutoTuneWorkflow for visualization if available,
    # even though we didn't use them for the actual VE calculation (we trusted ingest_pull).
    _cache_latest_corrections(
        session,
        corrections.correction_table,
        np.asarray(rpm_bins, dtype=np.float64),
        np.asarray(map_bins, dtype=np.float64),
        source="simulate_pull_realistic",
        pull_number=pull_number,
    )

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
        rpm,
        map_kpa,
        len(df),
        corrections.zones_adjusted,
    )

    return {
        "pull_number": pull_number,
        "observations_added": observations_added,
        "target_rpm": float(rpm),
        "target_map_kpa": float(map_kpa),
        "convergence": result_dict.get("convergence"),
        "next_suggestion": result_dict.get("next_suggestion"),
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
    Point generation strategy varies by pull_mode:
      - acceleration: simulates an RPM sweep at roughly constant MAP,
        covering many RPM bins in a single pull (25 points).
      - steady_state: clusters points near the target RPM/MAP zone
        for focused uncertainty reduction (15 points).

    Args:
        session_id: Session ID
        rpm: Target RPM (optional, defaults to next advisor suggestion)
        map_kpa: Target MAP (optional, defaults to next advisor suggestion)
        n_points: Number of data points to generate (ignored — overridden
                  by pull_mode heuristics)

    Returns:
        PullResult dict
    """
    session = _get_session(session_id)

    # Resolve target and pull_mode from advisor recommendation
    _pull_mode_value = "acceleration"
    if rpm is None or map_kpa is None:
        if session.advisor is None:
            raise RuntimeError("Session not initialized")
        rec = session.advisor.suggest_next_pull()
        rpm = rpm or rec.rpm
        map_kpa = map_kpa or rec.map_kpa
        if hasattr(rec, "pull_mode"):
            _pull_mode_value = (
                rec.pull_mode.value
                if hasattr(rec.pull_mode, "value")
                else str(rec.pull_mode)
            )

    # Seed RNG deterministically from target + observation count
    rng = np.random.RandomState(
        int(rpm + map_kpa + len(session.surrogate.observations))
    )

    if _pull_mode_value == "acceleration":
        # --- Acceleration sweep: spread across the RPM range at target MAP ---
        n_pts = 25
        rpm_lo = max(750.0, rpm - 2000)
        rpm_hi = min(6500.0, rpm + 2000)
        rpm_arr = np.linspace(rpm_lo, rpm_hi, n_pts) + rng.randn(n_pts) * 50
        map_arr = map_kpa + rng.randn(n_pts) * 3  # tight MAP spread (WOT ≈ const)
    else:
        # --- Steady-state: cluster at the target RPM/MAP zone ---
        n_pts = 15
        rpm_arr = rpm + rng.randn(n_pts) * 80  # tight RPM cluster
        map_arr = map_kpa + rng.randn(n_pts) * 4  # tight MAP cluster

    # --- Generate Synthetic AFR Data ---
    # Instead of guessing VE directly, we'll generate Base VE + AFR Error
    # giving us a "measured AFR" that implies the VE correction.
    
    # 1. Base VE (The "wrong" map we are correcting)
    base_ve_arr = np.full(n_pts, 85.0) # Simplified base map
    
    # Add some shape to base VE based on RPM/MAP so it's not flat
    ve_shape = (rpm_arr - 2000) / 4000 * 10 + (map_arr - 30) / 70 * 20
    base_ve_arr += ve_shape
    
    # 2. Target AFR (Rich at high load, Lean at cruise)
    # Simple logic: 13.0 at 100kPa, 14.7 at 30kPa
    target_afr_arr = 14.7 - (map_arr - 30) / 70 * 1.7
    
    # 3. Measured AFR
    # Apply a random "error" to the target.
    # e.g. Error = 1.05 means running 5% lean (AFR = Target * 1.05)
    # which implies Actual VE is HIGHER than Base VE (needs fuel added)
    # Wait: correction = Measured / Target. 
    # If Measured > Target (Lean), Correction > 1.0, VE increases. Correct.
    
    noise = rng.randn(n_pts) * 0.05 # +/- 5% random noise
    true_correction = 1.0 + noise 
    
    # Drift: simulate a systematic lean spot
    drift = 0.05 * np.sin(rpm_arr / 1000)
    true_correction += drift
    
    measured_afr_arr = target_afr_arr * true_correction
    
    # Ingest using the new Math Path
    result_dict = ingest_pull(
        session_id=session_id,
        rpm=rpm_arr.tolist(),
        map_kpa=map_arr.tolist(),
        afr=measured_afr_arr.tolist(),
        target_afr=target_afr_arr.tolist(),
        base_ve=base_ve_arr.tolist()
    )

    logger.info(
        "Quick-sim pull (%s) at RPM=%.0f MAP=%.0f: %d points generated via AFR path",
        _pull_mode_value,
        rpm,
        map_kpa,
        n_pts,
    )

    return {
        "pull_number": result_dict["pull_number"],
        "observations_added": result_dict["observations_added"],
        "target_rpm": float(rpm),
        "target_map_kpa": float(map_kpa),
        "convergence": result_dict.get("convergence"),
        "next_suggestion": result_dict.get("next_suggestion"),
        "mode": "quick",
        "afr_metrics": {
            "max_afr_error": float(np.max(np.abs(measured_afr_arr - target_afr_arr))),
            "mean_afr_error": float(np.mean(np.abs(measured_afr_arr - target_afr_arr))),
            "data_points": n_pts
        }
    }
