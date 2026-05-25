"""
JetDrive Channel Health Board.

Authoritative per-canonical-channel health for the Hardware Configuration
panel. Every status, value, and flag returned by ``/hardware/channels/health``
is computed server-side so the React frontend can stay a pure renderer
(see ``.cursor/rules/no-physics-in-frontend.mdc``).

Status semantics:

- ``OK``        -- channel is mapped, fresh, and within plausible bounds.
- ``STALE``     -- channel is mapped but the last sample is older than the
                   per-channel staleness threshold while capture is active.
- ``UNMAPPED``  -- canonical slot has no live entry from the active provider.
- ``INVALID``   -- value is implausible (NaN, infinite, out-of-range, or
                   a flagged condition such as ``lc2_pegged``).
- ``NO_SIGNAL`` -- capture is running but no samples have been received yet
                   for this channel (e.g. provider is up but the line is
                   silent).

Flags surfaced (all server-evaluated):

- ``lc2_pegged``        : AFR >= 22.38 (Innovate LC-2 ceiling).
- ``afr_implausible``   : AFR outside ``AFR_MIN_PLAUSIBLE`` ..
                           ``AFR_MAX_PLAUSIBLE`` from
                           :mod:`api.services.jetdrive.jetdrive_realtime_analysis`.
- ``rpm_zero_at_wot``   : RPM == 0 while TPS > WOT threshold (sensor faulted).
- ``not_finite``        : value is NaN or infinite.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from flask import jsonify

from ._shared import _live_data, _live_data_lock

# Staleness threshold for any individual canonical channel. The data layer
# considers the whole stream stale at >10s, but per-channel UI feedback uses
# a tighter threshold so an operator catches a single dropping channel.
CHANNEL_STALE_THRESHOLD_SEC = 2.5

# WOT threshold (TPS%) used for the ``rpm_zero_at_wot`` cross-channel flag.
WOT_TPS_THRESHOLD = 70.0

# LC-2 hardware ceiling (any reading at/above this is pegged/faulted).
LC2_AFR_CEILING = 22.38

# Flags that escalate a row's status to INVALID. Centralized so future flags
# don't silently degrade to "OK with annotations".
INVALIDATING_FLAGS = frozenset(
    {
        "not_finite",
        "lc2_pegged",
        "afr_implausible",
        "rpm_zero_at_wot",
        "value_out_of_range",
    }
)

# Rolling window for derived rate / peg counters surfaced to the operator.
# Kept short enough to be responsive but long enough to be statistically
# stable when the SSE health event fires at 2 Hz.
ROLLING_FLAG_WINDOW_SEC = 60.0


@dataclass(frozen=True)
class CanonicalSpec:
    """Authoritative description of a canonical channel slot.

    ``min_value`` / ``max_value`` define the static plausibility band used by
    the ``value_out_of_range`` flag. AFR-like channels deliberately leave
    these unset so the dynamic AFR plausibility band (driven by
    ``AFR_MIN_PLAUSIBLE`` / ``AFR_MAX_PLAUSIBLE``) remains the single source
    of truth for AFR validity.
    """

    canonical_name: str
    category: str
    units: str
    required: bool = False
    aliases: tuple[str, ...] = field(default_factory=tuple)
    afr_like: bool = False
    min_value: float | None = None
    max_value: float | None = None


# Minimum-required canonical channels that gate "all healthy" status.
# Optional rows are still surfaced to make missing channels visually obvious.
CANONICAL_CHANNEL_SPECS: tuple[CanonicalSpec, ...] = (
    CanonicalSpec(
        canonical_name="Engine RPM",
        category="dyno",
        units="rpm",
        required=True,
        aliases=("Digital RPM 1", "RPM"),
        min_value=0.0,
        max_value=10000.0,
    ),
    CanonicalSpec(
        canonical_name="AFR Front",
        category="afr",
        units=":1",
        required=True,
        aliases=("Air/Fuel Ratio 1", "AFR 1", "AFR"),
        afr_like=True,
    ),
    CanonicalSpec(
        canonical_name="AFR Rear",
        category="afr",
        units=":1",
        required=False,
        aliases=("Air/Fuel Ratio 2", "AFR 2"),
        afr_like=True,
    ),
    # Derived AFR canonicals (computed at ingest by derived_channels.py).
    # afr_like=True so the same plausibility band guards them.
    CanonicalSpec(
        canonical_name="AFR Mean",
        category="afr",
        units=":1",
        required=False,
        aliases=(),
        afr_like=True,
    ),
    CanonicalSpec(
        canonical_name="AFR Delta",
        category="afr",
        units=":1",
        required=False,
        aliases=(),
        afr_like=False,
        # Front-rear AFR delta is bounded; large values typically mean a
        # sensor mismatch or one bank flooded.
        min_value=-5.0,
        max_value=5.0,
    ),
    CanonicalSpec(
        canonical_name="MAP kPa",
        category="engine",
        units="kPa",
        required=False,
        aliases=("MAP", "Pressure"),
        min_value=0.0,
        max_value=115.0,
    ),
    CanonicalSpec(
        canonical_name="TPS",
        category="engine",
        units="%",
        required=False,
        aliases=(),
        min_value=0.0,
        max_value=100.0,
    ),
    CanonicalSpec(
        canonical_name="IAT",
        category="engine",
        units="°F",
        required=False,
        aliases=(),
        min_value=0.0,
        max_value=200.0,
    ),
    CanonicalSpec(
        canonical_name="ECT",
        category="engine",
        units="°F",
        required=False,
        aliases=(),
        min_value=100.0,
        max_value=280.0,
    ),
    CanonicalSpec(
        canonical_name="Knock",
        category="engine",
        units="deg",
        required=False,
        aliases=(),
    ),
    CanonicalSpec(
        canonical_name="Horsepower",
        category="dyno",
        units="HP",
        required=False,
        aliases=("Power",),
        min_value=0.0,
        max_value=600.0,
    ),
    CanonicalSpec(
        canonical_name="Torque",
        category="dyno",
        units="ft-lb",
        required=False,
        aliases=(),
        min_value=0.0,
        max_value=600.0,
    ),
)


def _afr_plausibility_bounds() -> tuple[float, float]:
    """Pull plausibility bounds from realtime analysis (single source of truth)."""
    try:
        from api.services.jetdrive.jetdrive_realtime_analysis import (
            AFR_MAX_PLAUSIBLE,
            AFR_MIN_PLAUSIBLE,
        )

        return float(AFR_MIN_PLAUSIBLE), float(AFR_MAX_PLAUSIBLE)
    except Exception:
        # Conservative fallback used only if realtime analysis fails to import.
        return 10.0, 18.0


def _resolve_entry(
    channels: dict[str, Any], spec: CanonicalSpec
) -> dict[str, Any] | None:
    """
    Pick the live entry that fills this canonical slot.

    The live capture loop already ranks/dedupes canonical sources. We trust
    its primary slot first and fall back to the explicit aliases only when
    the primary is missing (e.g. a rig publishes "AFR" but not "AFR Front").
    """
    primary = channels.get(spec.canonical_name)
    if isinstance(primary, dict):
        return primary
    for alias in spec.aliases:
        candidate = channels.get(alias)
        if isinstance(candidate, dict):
            return candidate
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_provider_id(value: Any) -> str | None:
    """Render a provider id consistently for the UI.

    Numeric provider ids are printed as ``0xPPPP``. Strings (used for
    server-derived sources, e.g. ``"computed:derived"``) are passed through
    so the operator can see the synthetic provenance directly.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value if value.strip() else None
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return None
    return f"0x{pid:04X}"


_FLAG_HISTORY: dict[tuple[str, str], deque[float]] = {}
_FLAG_HISTORY_LOCK = threading.Lock()


def _record_flag_event(canonical_name: str, flag: str, now_ts: float) -> None:
    """Record a flag occurrence into the rolling counter window."""
    key = (canonical_name, flag)
    with _FLAG_HISTORY_LOCK:
        bucket = _FLAG_HISTORY.get(key)
        if bucket is None:
            bucket = deque()
            _FLAG_HISTORY[key] = bucket
        bucket.append(now_ts)
        cutoff = now_ts - ROLLING_FLAG_WINDOW_SEC
        while bucket and bucket[0] < cutoff:
            bucket.popleft()


def _flag_count_window(canonical_name: str, flag: str, now_ts: float) -> int:
    key = (canonical_name, flag)
    with _FLAG_HISTORY_LOCK:
        bucket = _FLAG_HISTORY.get(key)
        if not bucket:
            return 0
        cutoff = now_ts - ROLLING_FLAG_WINDOW_SEC
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        return len(bucket)


def reset_flag_history() -> None:
    """Reset the rolling flag history (test seam)."""
    with _FLAG_HISTORY_LOCK:
        _FLAG_HISTORY.clear()


def _validator_metrics(provider_id: Any, channel_id: Any) -> dict[str, float] | None:
    """Pull validator metrics for a (provider_id, channel_id) pair.

    Returns None when the validator has no entry yet (e.g. capture just
    started or the canonical source is computed/derived). Pulling from the
    existing validator avoids duplicating a parallel counter system.
    """
    try:
        provider = int(provider_id)
    except (TypeError, ValueError):
        return None
    try:
        channel = int(channel_id)
    except (TypeError, ValueError):
        return None

    try:
        from api.services.jetdrive.jetdrive_validation import get_validator
    except Exception:
        return None

    try:
        metrics = get_validator().get_channel_health(provider, channel)
    except Exception:
        return None
    if metrics is None:
        return None
    return {
        "samples_per_second": float(getattr(metrics, "samples_per_second", 0.0) or 0.0),
        "total_samples": int(getattr(metrics, "total_samples", 0) or 0),
        "invalid_value_count": int(getattr(metrics, "invalid_value_count", 0) or 0),
    }


def _evaluate_row(
    spec: CanonicalSpec,
    entry: dict[str, Any] | None,
    channels: dict[str, Any],
    *,
    capturing: bool,
    now_ts: float,
    afr_bounds: tuple[float, float],
) -> dict[str, Any]:
    # Pre-loaded flags / reasons set at ingest by derived-channel pipelines
    # (e.g. ``cyl_imbalance`` on AFR Mean from derived_channels.py). The
    # board never invents these; it only forwards them so the renderer can
    # show a warning pill.
    flags: list[str] = []
    reasons: list[str] = []
    if isinstance(entry, dict):
        precomputed_flags = entry.get("flags")
        if isinstance(precomputed_flags, (list, tuple)):
            for raw_flag in precomputed_flags:
                if isinstance(raw_flag, str) and raw_flag and raw_flag not in flags:
                    flags.append(raw_flag)

    if entry is None:
        return {
            "canonical_name": spec.canonical_name,
            "category": spec.category,
            "required": spec.required,
            "expected_units": spec.units,
            "status": "UNMAPPED",
            "value": None,
            "units": None,
            "age_seconds": None,
            "source": None,
            "flags": [],
            "reasons": ["Canonical slot has no mapped source."]
            if not capturing
            else ["No source publishing this channel yet."],
            "samples_per_second": 0.0,
            "total_samples": 0,
            "lc2_peg_count_60s": 0,
            "value_out_of_range_count_60s": 0,
            "min_value": spec.min_value,
            "max_value": spec.max_value,
        }

    raw_value = entry.get("value")
    value = _to_float(raw_value) if raw_value is not None else None
    units = entry.get("units") if isinstance(entry.get("units"), str) else spec.units
    source_provider = _format_provider_id(entry.get("provider_id"))
    source_channel_id = entry.get("id")
    source_raw_name = entry.get("source_name") or entry.get("name")
    source = {
        "provider_id": source_provider,
        "channel_id": source_channel_id,
        "raw_name": source_raw_name,
    }

    age_seconds: float | None
    updated_at = _to_float(entry.get("updated_at_ts"))
    if updated_at is None:
        age_seconds = None
    else:
        age_seconds = max(0.0, now_ts - updated_at)

    # Validity flags (server-evaluated; never recompute on the client).
    if value is None or not math.isfinite(value):
        flags.append("not_finite")
        reasons.append("Value is not a finite number.")

    if spec.afr_like and value is not None and math.isfinite(value):
        afr_min, afr_max = afr_bounds
        if value >= LC2_AFR_CEILING:
            flags.append("lc2_pegged")
            reasons.append(
                f"AFR {value:.2f} is at or above LC-2 ceiling ({LC2_AFR_CEILING:.2f}); sensor pegged."
            )
        elif value < afr_min or value > afr_max:
            flags.append("afr_implausible")
            reasons.append(
                f"AFR {value:.2f} is outside plausible range ({afr_min:.1f}-{afr_max:.1f})."
            )

    # Static plausibility band (non-AFR canonicals). AFR-like channels rely
    # on the dynamic AFR plausibility above; we deliberately don't apply
    # spec.min/max twice for them.
    if (
        not spec.afr_like
        and value is not None
        and math.isfinite(value)
        and (spec.min_value is not None or spec.max_value is not None)
    ):
        below = spec.min_value is not None and value < spec.min_value
        above = spec.max_value is not None and value > spec.max_value
        if below or above:
            flags.append("value_out_of_range")
            bound_label = (
                f"{spec.min_value if spec.min_value is not None else '-inf'} "
                f"– {spec.max_value if spec.max_value is not None else '+inf'}"
            )
            reasons.append(
                f"{spec.canonical_name} value {value} is outside expected range {bound_label}."
            )

    # Cross-channel diagnostic: RPM zero while throttle is wide open.
    if (
        spec.canonical_name == "Engine RPM"
        and value is not None
        and value <= 0.0
    ):
        tps_entry = channels.get("TPS")
        if isinstance(tps_entry, dict):
            tps_value = _to_float(tps_entry.get("value"))
            if tps_value is not None and tps_value > WOT_TPS_THRESHOLD:
                flags.append("rpm_zero_at_wot")
                reasons.append(
                    f"RPM is 0 while TPS={tps_value:.0f}% (>{WOT_TPS_THRESHOLD:.0f}%); pickup likely faulted."
                )

    # Status precedence: invalid > stale > no_signal > ok. Any flag in
    # ``INVALIDATING_FLAGS`` forces INVALID so the operator sees the issue.
    if any(flag in INVALIDATING_FLAGS for flag in flags):
        status = "INVALID"
    elif (
        capturing
        and age_seconds is not None
        and age_seconds > CHANNEL_STALE_THRESHOLD_SEC
    ):
        status = "STALE"
        reasons.append(
            f"Last sample {age_seconds:.1f}s old (threshold {CHANNEL_STALE_THRESHOLD_SEC:.1f}s)."
        )
    elif value is None:
        status = "NO_SIGNAL"
        reasons.append("No numeric sample received yet for this channel.")
    else:
        status = "OK"

    # Record any LC-2 peg / value-out-of-range events for the rolling window.
    for tracked_flag in ("lc2_pegged", "value_out_of_range"):
        if tracked_flag in flags:
            _record_flag_event(spec.canonical_name, tracked_flag, now_ts)

    metrics = _validator_metrics(entry.get("provider_id"), entry.get("id"))
    samples_per_second = round(metrics["samples_per_second"], 2) if metrics else 0.0
    total_samples = metrics["total_samples"] if metrics else 0
    lc2_peg_count_60s = _flag_count_window(
        spec.canonical_name, "lc2_pegged", now_ts
    )
    value_out_of_range_count_60s = _flag_count_window(
        spec.canonical_name, "value_out_of_range", now_ts
    )

    return {
        "canonical_name": spec.canonical_name,
        "category": spec.category,
        "required": spec.required,
        "expected_units": spec.units,
        "status": status,
        "value": value,
        "units": units,
        "age_seconds": age_seconds,
        "source": source,
        "flags": flags,
        "reasons": reasons,
        "samples_per_second": samples_per_second,
        "total_samples": total_samples,
        "lc2_peg_count_60s": lc2_peg_count_60s,
        "value_out_of_range_count_60s": value_out_of_range_count_60s,
        "min_value": spec.min_value,
        "max_value": spec.max_value,
    }


def build_channels_health_payload(
    *,
    now_ts: float | None = None,
) -> dict[str, Any]:
    """
    Construct the channel health payload from the current ``_live_data``.

    Pure function (modulo the lock acquired to read shared state) so tests
    can drive it directly with controlled inputs.
    """
    now = now_ts if now_ts is not None else time.time()

    with _live_data_lock:
        channels: dict[str, Any] = dict(_live_data.get("channels", {}) or {})
        capturing = bool(_live_data.get("capturing"))
        provider_id = _live_data.get("provider_id")
        provider_name = _live_data.get("provider_name")
        provider_host = _live_data.get("provider_host")
        error = _live_data.get("error")
        error_code = _live_data.get("error_code")

    afr_bounds = _afr_plausibility_bounds()

    rows: list[dict[str, Any]] = []
    counts = {
        "OK": 0,
        "STALE": 0,
        "UNMAPPED": 0,
        "INVALID": 0,
        "NO_SIGNAL": 0,
    }
    for spec in CANONICAL_CHANNEL_SPECS:
        entry = _resolve_entry(channels, spec)
        row = _evaluate_row(
            spec,
            entry,
            channels,
            capturing=capturing,
            now_ts=now,
            afr_bounds=afr_bounds,
        )
        rows.append(row)
        counts[row["status"]] += 1

    required_rows = [r for r in rows if r["required"]]
    all_required_ok = bool(required_rows) and all(
        r["status"] == "OK" for r in required_rows
    )
    any_invalid = counts["INVALID"] > 0
    any_stale = counts["STALE"] > 0

    if not capturing and not any(r["source"] for r in rows):
        summary_state = "idle"
        summary_message = "Capture stopped; no channels are mapped."
    elif all_required_ok and not any_invalid and not any_stale:
        summary_state = "all_healthy"
        summary_message = "All required canonical channels are healthy."
    elif any_invalid:
        summary_state = "invalid"
        summary_message = "One or more channels are reporting invalid data."
    elif any_stale:
        summary_state = "stale"
        summary_message = "One or more channels are stale."
    elif counts["UNMAPPED"] > 0:
        summary_state = "unmapped"
        summary_message = "Required canonical channels are not yet mapped."
    else:
        summary_state = "warming_up"
        summary_message = "Capture started; waiting for samples."

    return {
        "capturing": capturing,
        "provider": {
            "provider_id": _format_provider_id(provider_id),
            "name": provider_name,
            "host": provider_host,
        },
        "all_required_ok": all_required_ok,
        "summary": {
            "state": summary_state,
            "message": summary_message,
            "counts": counts,
        },
        "afr_plausibility": {"min": afr_bounds[0], "max": afr_bounds[1]},
        "lc2_ceiling": LC2_AFR_CEILING,
        "stale_threshold_seconds": CHANNEL_STALE_THRESHOLD_SEC,
        "wot_tps_threshold": WOT_TPS_THRESHOLD,
        "channels": rows,
        "timestamp": now,
        "error": error,
        "error_code": error_code,
    }


def register_channel_health_routes(blueprint) -> None:
    """Attach the /hardware/channels/health route to the hardware blueprint."""

    @blueprint.route("/hardware/channels/health", methods=["GET"])
    def get_channels_health():
        return jsonify(build_channels_health_payload())


def canonical_specs_for_tests() -> Iterable[dict[str, Any]]:
    """Helper used by tests to enumerate canonical specs without imports."""
    return [asdict(spec) for spec in CANONICAL_CHANNEL_SPECS]


__all__ = [
    "CANONICAL_CHANNEL_SPECS",
    "CanonicalSpec",
    "CHANNEL_STALE_THRESHOLD_SEC",
    "LC2_AFR_CEILING",
    "WOT_TPS_THRESHOLD",
    "build_channels_health_payload",
    "register_channel_health_routes",
    "canonical_specs_for_tests",
]
