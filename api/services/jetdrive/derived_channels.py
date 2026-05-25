"""
Server-side derived canonical channels.

Currently emits ``AFR Mean`` and ``AFR Delta`` from canonicalized
``AFR Front`` / ``AFR Rear`` samples. This is the only place where front+
rear AFR fusion math lives. Per ``.cursor/rules/no-physics-in-frontend.mdc``
the React renderer must consume these as ordinary channels.

Rules (hard, embedded in tests):

- Each input sample is rejected if the AFR value is at or above
  ``LC2_AFR_CEILING`` (``22.38``, the LC-2 hardware ceiling) — these are
  pegged sensors and including them would skew the mean / delta.
- Front and rear must be co-temporal: the absolute timestamp delta must
  be ``<= AFR_PAIR_WINDOW_MS`` (``50 ms``). Otherwise we wait for the next
  matching pair instead of fabricating a mean from disjoint samples.
- A confidence label is attached to each derived sample so the operator
  knows whether the pair was tight (``high``) or skirted the ceiling /
  used a slightly older partner (``low``). We never emit when the pair
  is invalid.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable, Optional

from api.services.jetdrive.wideband_rescale import canonicalize_wideband_sample

# Same ceiling as the live capture loop / channel health board uses.
LC2_AFR_CEILING = 22.38

# Maximum allowable timestamp gap between Front/Rear samples (ms).
# 50 ms matches the JetDrive ingest aggregation window so we never derive
# from samples that span more than one window.
AFR_PAIR_WINDOW_MS = 50

DERIVED_PROVIDER_ID = "computed:derived"
DERIVED_AFR_MEAN_NAME = "AFR Mean"
DERIVED_AFR_DELTA_NAME = "AFR Delta"

# ---------------------------------------------------------------------------
# Cylinder imbalance enrichment
# ---------------------------------------------------------------------------
#
# Front-rear AFR delta is bulk on most rigs (venturi/tailpipe sniffers, see
# AGENTS.md), so an instantaneous |delta| spike isn't actionable on its own.
# Instead we emit a ``cyl_imbalance`` flag on ``AFR Mean`` only when an
# absolute delta above ``CYL_IMBALANCE_AFR_THRESHOLD`` is sustained across
# the rolling pair window.

CYL_IMBALANCE_AFR_THRESHOLD = 1.0  # AFR points
CYL_IMBALANCE_WINDOW_MS = 1500  # ~1.5 s of accepted pairs
# Require at least N samples in window AND at least this fraction above the
# threshold before flagging imbalance. Cheap protection against transients.
CYL_IMBALANCE_MIN_SAMPLES = 6
CYL_IMBALANCE_MIN_FRACTION = 0.7


@dataclass
class _AfrSample:
    value: float
    timestamp_ms: int


@dataclass
class DerivedChannelEntry:
    """Result of a derived computation, ready to be merged into ``_live_data``."""

    canonical_name: str
    value: float
    timestamp_ms: int
    confidence: str  # "high" or "low"
    units: str = ":1"
    category: str = "afr"
    source_name: str = ""
    provider_id: str = DERIVED_PROVIDER_ID
    flags: tuple[str, ...] = ()

    def to_live_entry(self, *, updated_at_ts: float) -> dict[str, object]:
        return {
            "key": f"computed:{self.canonical_name}:derived",
            "provider_id": self.provider_id,
            "id": None,
            "name": self.canonical_name,
            "source_name": self.source_name,
            "value": float(self.value),
            "timestamp": int(self.timestamp_ms),
            "updated_at_ts": float(updated_at_ts),
            "category": self.category,
            "units": self.units,
            "computed": True,
            "confidence": self.confidence,
            "flags": list(self.flags),
        }


@dataclass
class AfrDerivationState:
    """Holds the most recent valid Front / Rear samples used for derivation.

    The state is per capture session; ``_live_capture_loop`` owns one and
    resets it on (re)connect.
    """

    last_front: Optional[_AfrSample] = None
    last_rear: Optional[_AfrSample] = None
    # Rolling buffer of (timestamp_ms, abs_delta) for recently-emitted pairs.
    # Drives the ``cyl_imbalance`` enrichment without needing a global
    # counter. Bounded by time, not entries, so we trim on every record().
    _delta_history: deque[tuple[int, float]] = field(default_factory=deque, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def reset(self) -> None:
        with self._lock:
            self.last_front = None
            self.last_rear = None
            self._delta_history.clear()

    def _is_imbalanced(self, *, now_ms: int) -> bool:
        """Return True when |delta| has been sustained above threshold.

        Pure read of ``_delta_history``; caller must hold the lock.
        """
        cutoff = now_ms - CYL_IMBALANCE_WINDOW_MS
        # Trim entries that have aged out.
        while self._delta_history and self._delta_history[0][0] < cutoff:
            self._delta_history.popleft()
        n = len(self._delta_history)
        if n < CYL_IMBALANCE_MIN_SAMPLES:
            return False
        n_above = sum(
            1
            for _ts, abs_delta in self._delta_history
            if abs_delta > CYL_IMBALANCE_AFR_THRESHOLD
        )
        return (n_above / n) >= CYL_IMBALANCE_MIN_FRACTION

    def record(
        self,
        canonical_name: str,
        value: float,
        timestamp_ms: int,
    ) -> list[DerivedChannelEntry]:
        """Record one canonical AFR sample and return any derived emissions."""
        if canonical_name not in ("AFR Front", "AFR Rear"):
            return []

        # Reject pegged samples outright; they corrupt the mean and the
        # imbalance window. We also do NOT push the rejected sample into
        # ``_delta_history`` so a transient peg can't trigger imbalance.
        if not _is_valid_afr(value):
            return []

        with self._lock:
            if canonical_name == "AFR Front":
                self.last_front = _AfrSample(value=float(value), timestamp_ms=int(timestamp_ms))
                partner = self.last_rear
            else:
                self.last_rear = _AfrSample(value=float(value), timestamp_ms=int(timestamp_ms))
                partner = self.last_front

            front = self.last_front
            rear = self.last_rear

            if front is None or rear is None or partner is None:
                return []

            gap_ms = abs(front.timestamp_ms - rear.timestamp_ms)
            if gap_ms > AFR_PAIR_WINDOW_MS:
                # Pair too far apart; skip emitting and don't extend the
                # imbalance window with a stale partner.
                return []

            confidence = _classify_confidence(front.value, rear.value, gap_ms)
            mean_value = (front.value + rear.value) / 2.0
            delta_value = front.value - rear.value
            emit_ts_ms = max(front.timestamp_ms, rear.timestamp_ms)

            # Push the accepted pair's |delta| onto the history before
            # evaluating imbalance so the new sample is included.
            self._delta_history.append((emit_ts_ms, abs(delta_value)))
            cyl_imbalance = self._is_imbalanced(now_ms=emit_ts_ms)

        mean_flags: tuple[str, ...] = ("cyl_imbalance",) if cyl_imbalance else ()

        return [
            DerivedChannelEntry(
                canonical_name=DERIVED_AFR_MEAN_NAME,
                value=mean_value,
                timestamp_ms=emit_ts_ms,
                confidence=confidence,
                source_name="derived:afr_mean(AFR Front, AFR Rear)",
                flags=mean_flags,
            ),
            DerivedChannelEntry(
                canonical_name=DERIVED_AFR_DELTA_NAME,
                value=delta_value,
                timestamp_ms=emit_ts_ms,
                confidence=confidence,
                source_name="derived:afr_delta(AFR Front - AFR Rear)",
            ),
        ]


def _is_valid_afr(value: float) -> bool:
    """Reject pegged / non-finite AFR samples before they enter the average."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    if v != v:  # NaN
        return False
    if v in (float("inf"), float("-inf")):
        return False
    if v >= LC2_AFR_CEILING:
        return False
    if v <= 0.0:
        return False
    return True


def _classify_confidence(front: float, rear: float, gap_ms: int) -> str:
    """Confidence label policy.

    ``high`` -- both within plausible band and gap < 25 ms.
    ``low``  -- otherwise (still within window or we wouldn't have emitted).
    """
    if gap_ms <= AFR_PAIR_WINDOW_MS // 2:
        # Tight pair; both already passed the ceiling check.
        return "high"
    return "low"


def is_canonical_afr_input(canonical_name: str) -> bool:
    """Convenience check used by the live capture loop integration."""
    return canonical_name in ("AFR Front", "AFR Rear")


def maybe_derive_from_raw_sample(
    state: AfrDerivationState,
    channel_name: str,
    raw_value: float,
    timestamp_ms: int,
) -> list[DerivedChannelEntry]:
    """Wideband-canonicalize ``channel_name`` and feed the derivation state.

    Used by tests so they can drive the same code path the ingest loop drives
    without hand-rolling the canonical name resolution.
    """
    canonicalized = canonicalize_wideband_sample(channel_name, raw_value)
    if canonicalized is None:
        return []
    return state.record(
        canonicalized.canonical_name,
        canonicalized.afr,
        timestamp_ms,
    )


def derived_canonical_names() -> Iterable[str]:
    return (DERIVED_AFR_MEAN_NAME, DERIVED_AFR_DELTA_NAME)


__all__ = [
    "AFR_PAIR_WINDOW_MS",
    "AfrDerivationState",
    "DERIVED_AFR_DELTA_NAME",
    "DERIVED_AFR_MEAN_NAME",
    "DERIVED_PROVIDER_ID",
    "DerivedChannelEntry",
    "LC2_AFR_CEILING",
    "derived_canonical_names",
    "is_canonical_afr_input",
    "maybe_derive_from_raw_sample",
]
