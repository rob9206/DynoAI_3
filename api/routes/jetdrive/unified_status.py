"""
Unified hardware status snapshot.

Aggregates the four pieces of state the operator UI cares about so the
React renderer can subscribe to a single source of truth:

- ``provider``      -- monitor/discovery state (provider id, name, host).
- ``capture``       -- live capture state (capturing, last_update_ts,
                       error / error_code, structured status block).
- ``channels``      -- the full Channel Health Board payload (per-canonical
                       row + summary counts + summary state).
- ``mapping``       -- top-line mapping confidence (ready_for_capture,
                       overall_confidence) when an existing mapping is
                       loaded for the active provider; ``null`` otherwise.
                       The detailed report stays at ``/mapping/confidence``.
- ``ingestion``     -- summary slice of the existing ingestion validator
                       (overall_health + healthy_count/total + drop_rate).

Detailed endpoints (``/mapping/confidence``, ``/hardware/health``,
``/hardware/channels/health``) remain available for diagnostic deep-dives.
Only the top-line state is unified here.
"""

from __future__ import annotations

import time
from typing import Any

from flask import jsonify

from ._shared import _live_data, _live_data_lock, _monitor_lock, _monitor_state
from .channel_health import build_channels_health_payload


def _build_capture_block() -> dict[str, Any]:
    """Project ``_live_data`` into the unified ``capture`` block."""
    with _live_data_lock:
        capturing = bool(_live_data.get("capturing"))
        last_update_ts = _live_data.get("last_update_ts")
        provider_id = _live_data.get("provider_id")
        provider_name = _live_data.get("provider_name")
        provider_host = _live_data.get("provider_host")
        error = _live_data.get("error")
        error_code = _live_data.get("error_code")

    age_seconds: float | None
    try:
        age_seconds = (
            float(time.time() - float(last_update_ts))
            if last_update_ts
            else None
        )
    except Exception:
        age_seconds = None

    return {
        "capturing": capturing,
        "last_update_ts": last_update_ts,
        "data_age_seconds": age_seconds,
        "provider_id": (
            f"0x{int(provider_id):04X}"
            if isinstance(provider_id, (int, float))
            else None
        ),
        "provider_name": provider_name,
        "provider_host": provider_host,
        "error": error,
        "error_code": error_code,
    }


def _build_provider_block() -> dict[str, Any]:
    """Project ``_monitor_state`` into the unified ``provider`` block."""
    with _monitor_lock:
        running = bool(_monitor_state.get("running"))
        last_check = _monitor_state.get("last_check")
        providers = list(_monitor_state.get("providers") or [])

    return {
        "monitor_running": running,
        "last_check": last_check,
        "connected": len(providers) > 0,
        "count": len(providers),
        "providers": providers,
    }


def _build_mapping_block() -> dict[str, Any] | None:
    """
    Top-line mapping for the *currently pinned* provider.

    Returns a dict with two sub-blocks:
    - ``saved``: persisted mapping (or null when no on-disk mapping exists).
    - ``transient_proposal``: unsaved auto-detect proposal from the
      in-memory cache (or null). Surfacing both lets the UI render an
      "Unsaved auto-detected mapping" banner alongside whatever is
      persisted.

    Avoids the heavy multicast discovery used by ``/mapping/confidence``
    so this endpoint stays fast enough to back a 1.5 s polling fallback.
    """
    with _live_data_lock:
        provider_id = _live_data.get("provider_id")

    if not isinstance(provider_id, (int, float)):
        return None

    saved_block: dict[str, Any] | None = None
    transient_block: dict[str, Any] | None = None
    selected_signature: str | None = None

    try:
        from api.services.jetdrive.jetdrive_mapping import (
            REQUIRED_CANONICAL,
            list_mappings,
        )

        mappings = list_mappings()
        selected = next(
            (m for m in mappings if int(m.provider_id) == int(provider_id)),
            None,
        )
        if selected is not None:
            selected_signature = selected.provider_signature
            mapped = set(selected.channels.keys())
            has_afr = any(
                name.startswith("afr_") or name.startswith("lambda_")
                for name in mapped
            )
            missing_required: list[str] = []
            if "rpm" not in mapped:
                missing_required.append("rpm")
            if not has_afr:
                missing_required.append("afr")

            saved_block = {
                "provider_signature": selected.provider_signature,
                "provider_id": (
                    f"0x{int(selected.provider_id):04X}"
                    if isinstance(selected.provider_id, (int, float))
                    else None
                ),
                "provider_name": selected.provider_name,
                "ready_for_capture": len(missing_required) == 0,
                "missing_required": missing_required,
                "mapped_count": len(mapped),
                "required_canonicals": list(REQUIRED_CANONICAL),
            }
    except Exception:
        saved_block = None

    # Transient proposal (auto-detect output not yet persisted).
    try:
        from api.services.jetdrive.mapping_transient_cache import (
            list_transient_mappings,
        )

        transient_entries = list_transient_mappings()
        # Match the proposal to the active provider by id; fall back to
        # signature when we know the saved one. Prefer id match for
        # robustness against stale signatures.
        for entry in transient_entries:
            if int(entry.provider_id) == int(provider_id):
                transient_block = entry.to_dict()
                break
        if transient_block is None and selected_signature is not None:
            for entry in transient_entries:
                if entry.provider_signature == selected_signature:
                    transient_block = entry.to_dict()
                    break
    except Exception:
        transient_block = None

    if saved_block is None and transient_block is None:
        return None

    return {
        "saved": saved_block,
        "transient_proposal": transient_block,
    }


def _build_ingestion_block() -> dict[str, Any]:
    """Summary projection of the existing ingestion validator."""
    try:
        from api.services.jetdrive.jetdrive_validation import get_validator
    except Exception:
        return {
            "overall_health": "unknown",
            "healthy_channels": 0,
            "total_channels": 0,
            "drop_rate_percent": 0.0,
        }

    try:
        report = get_validator().get_all_health()
    except Exception:
        return {
            "overall_health": "unknown",
            "healthy_channels": 0,
            "total_channels": 0,
            "drop_rate_percent": 0.0,
        }

    frame_stats = report.get("frame_stats") or {}
    return {
        "overall_health": report.get("overall_health", "unknown"),
        "health_reason": report.get("health_reason"),
        "healthy_channels": int(report.get("healthy_channels", 0)),
        "total_channels": int(report.get("total_channels", 0)),
        "drop_rate_percent": float(frame_stats.get("drop_rate_percent", 0.0)),
        "active_provider_id": (
            f"0x{int(report['active_provider_id']):04X}"
            if isinstance(report.get("active_provider_id"), (int, float))
            else None
        ),
    }


def build_unified_status_payload(*, now_ts: float | None = None) -> dict[str, Any]:
    """Single-source-of-truth payload consumed by ``useHardwareStatus``."""
    now = now_ts if now_ts is not None else time.time()
    return {
        "timestamp": now,
        "provider": _build_provider_block(),
        "capture": _build_capture_block(),
        "channels": build_channels_health_payload(now_ts=now),
        "mapping": _build_mapping_block(),
        "ingestion": _build_ingestion_block(),
    }


def register_unified_status_routes(blueprint) -> None:
    """Mount ``GET /hardware/status`` on the hardware blueprint."""

    @blueprint.route("/hardware/status", methods=["GET"])
    def get_unified_status():
        return jsonify(build_unified_status_payload())


__all__ = [
    "build_unified_status_payload",
    "register_unified_status_routes",
]
