"""
In-memory transient mapping cache.

After ``POST /mapping/auto-detect`` succeeds, the proposed mapping lives
here until the operator either persists it via ``PUT /mapping/<sig>`` or
the TTL expires. The Hardware Configuration UI surfaces the transient
proposal via the unified status endpoint so the operator never loses sight
of an unsaved auto-detected mapping.

Single source of truth: this module owns the cache. The frontend never
fabricates transient state.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

# Default TTL (seconds). 10 minutes is long enough for an operator to scan
# the proposal and click Save without losing it on refresh, short enough
# that stale proposals don't linger forever.
TRANSIENT_TTL_SECONDS = 10 * 60


@dataclass
class TransientMapping:
    """A pending mapping proposal that hasn't been persisted yet."""

    provider_signature: str
    provider_id: int
    provider_name: str
    host: str
    proposed_at: float
    expires_at: float
    source: str  # "auto_detect" | "template" | etc.
    mapping: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_signature": self.provider_signature,
            "provider_id": (
                f"0x{int(self.provider_id):04X}"
                if isinstance(self.provider_id, (int, float))
                else None
            ),
            "provider_id_int": int(self.provider_id),
            "provider_name": self.provider_name,
            "host": self.host,
            "proposed_at": self.proposed_at,
            "expires_at": self.expires_at,
            "source": self.source,
            "mapping": self.mapping,
            "ttl_remaining_seconds": max(0.0, self.expires_at - time.time()),
        }


_transient_cache: dict[str, TransientMapping] = {}
_transient_lock = threading.Lock()


def store_transient_mapping(
    *,
    provider_signature: str,
    provider_id: int,
    provider_name: str,
    host: str,
    mapping: dict[str, Any],
    source: str = "auto_detect",
    ttl_seconds: float = TRANSIENT_TTL_SECONDS,
    now_ts: float | None = None,
) -> TransientMapping:
    """Cache a mapping proposal. Replaces any prior proposal for the same signature."""
    now = now_ts if now_ts is not None else time.time()
    entry = TransientMapping(
        provider_signature=provider_signature,
        provider_id=int(provider_id),
        provider_name=str(provider_name),
        host=str(host),
        proposed_at=now,
        expires_at=now + float(ttl_seconds),
        source=str(source),
        mapping=dict(mapping),
    )
    with _transient_lock:
        _transient_cache[provider_signature] = entry
    return entry


def get_transient_mapping(
    provider_signature: str, *, now_ts: float | None = None
) -> Optional[TransientMapping]:
    """Return the live transient proposal, evicting expired entries lazily."""
    now = now_ts if now_ts is not None else time.time()
    with _transient_lock:
        entry = _transient_cache.get(provider_signature)
        if entry is None:
            return None
        if entry.expires_at <= now:
            _transient_cache.pop(provider_signature, None)
            return None
        return entry


def clear_transient_mapping(provider_signature: str) -> bool:
    """Drop the proposal for ``provider_signature``. Returns True if removed."""
    with _transient_lock:
        return _transient_cache.pop(provider_signature, None) is not None


def list_transient_mappings(*, now_ts: float | None = None) -> list[TransientMapping]:
    """Return all live transient proposals (expired entries pruned)."""
    now = now_ts if now_ts is not None else time.time()
    expired: list[str] = []
    live: list[TransientMapping] = []
    with _transient_lock:
        for sig, entry in _transient_cache.items():
            if entry.expires_at <= now:
                expired.append(sig)
            else:
                live.append(entry)
        for sig in expired:
            _transient_cache.pop(sig, None)
    return live


def reset_transient_cache() -> None:
    """Test seam: drop all proposals."""
    with _transient_lock:
        _transient_cache.clear()


__all__ = [
    "TRANSIENT_TTL_SECONDS",
    "TransientMapping",
    "clear_transient_mapping",
    "get_transient_mapping",
    "list_transient_mappings",
    "reset_transient_cache",
    "store_transient_mapping",
]
