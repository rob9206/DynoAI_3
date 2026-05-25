"""Capture restart should clear rolling channel-health flag history.

Background:
``channel_health._FLAG_HISTORY`` accumulates LC-2 peg / out-of-range events
in a rolling 60-second window. An operator who quickly stops/starts capture
should see zeroed rolling counters for the new session, not stale ones from
the previous run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import time


@dataclass
class _ProviderStub:
    provider_id: int
    name: str
    host: str
    port: int = 22344
    channels: dict[int, object] = field(default_factory=dict)


def _seed_peg_history():
    from api.routes.jetdrive.channel_health import (
        _flag_count_window,
        _record_flag_event,
    )

    now = time.time()
    _record_flag_event("AFR Front", "lc2_pegged", now)
    _record_flag_event("AFR Front", "lc2_pegged", now)
    _record_flag_event("Engine RPM", "value_out_of_range", now)
    # Sanity check before the test.
    assert _flag_count_window("AFR Front", "lc2_pegged", now) == 2
    assert _flag_count_window("Engine RPM", "value_out_of_range", now) == 1


def test_reset_flag_history_clears_all_canonicals():
    from api.routes.jetdrive.channel_health import (
        _flag_count_window,
        reset_flag_history,
    )

    _seed_peg_history()
    reset_flag_history()
    now = time.time()
    assert _flag_count_window("AFR Front", "lc2_pegged", now) == 0
    assert _flag_count_window("Engine RPM", "value_out_of_range", now) == 0


def test_live_start_route_clears_history(client, monkeypatch):
    """``POST /hardware/live/start`` must clear the rolling counters."""
    from api.routes.jetdrive import hardware as hardware_routes
    from api.routes.jetdrive._shared import _live_data, _live_data_lock
    from api.routes.jetdrive.channel_health import (
        _flag_count_window,
        _record_flag_event,
    )

    # Seed peg history from a prior session.
    now = time.time()
    _record_flag_event("AFR Front", "lc2_pegged", now)
    _record_flag_event("AFR Front", "lc2_pegged", now)
    assert _flag_count_window("AFR Front", "lc2_pegged", now) == 2

    # Mock discovery so the route doesn't actually launch a UDP capture
    # thread; we only need the cleanup path.
    providers = [_ProviderStub(provider_id=0x1001, name="Dyno RT", host="127.0.0.1")]
    monkeypatch.setattr(
        hardware_routes,
        "_discover_providers_snapshot",
        lambda timeout=1.25: (providers, None),
    )

    snapshot = dict(_live_data)
    with _live_data_lock:
        # Force capturing=False so the route enters the start path.
        _live_data["capturing"] = False

    try:
        resp = client.post("/api/jetdrive/hardware/live/start")
        # Either ``started`` or ``already_capturing`` is acceptable; the only
        # thing under test is that history is wiped.
        assert resp.status_code in (200, 503)

        now2 = time.time()
        assert _flag_count_window("AFR Front", "lc2_pegged", now2) == 0
    finally:
        with _live_data_lock:
            _live_data.clear()
            _live_data.update(snapshot)


def test_reset_flag_history_does_not_clear_unrelated_module_state():
    """Sanity check: reset only touches its own deque dict, nothing else."""
    from api.routes.jetdrive import channel_health
    from api.routes.jetdrive.channel_health import (
        CANONICAL_CHANNEL_SPECS,
        reset_flag_history,
    )

    snapshot_specs = tuple(CANONICAL_CHANNEL_SPECS)
    snapshot_invalidating = frozenset(channel_health.INVALIDATING_FLAGS)

    reset_flag_history()

    assert tuple(CANONICAL_CHANNEL_SPECS) == snapshot_specs
    assert frozenset(channel_health.INVALIDATING_FLAGS) == snapshot_invalidating
