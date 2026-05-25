"""
Tests for the Item 3 + Item 5 channel-health extensions:

- ``value_out_of_range`` plausibility flag (per-channel min/max).
- Rolling LC-2 peg / out-of-range counters over the 60s window.
- Validator-fed ``samples_per_second`` / ``total_samples`` per row.

These mirror the seeding helpers from
``test_jetdrive_channel_health.py`` so the two suites stay aligned.
"""

from __future__ import annotations

import time
from typing import Any


def _entry(
    name: str,
    *,
    value: float | None = 1.0,
    units: str = "",
    category: str = "misc",
    provider_id: int = 0x1001,
    channel_id: int = 1,
    source_name: str = "raw",
    age_seconds: float = 0.0,
    now: float | None = None,
) -> dict[str, Any]:
    timestamp_ts = (now if now is not None else time.time()) - age_seconds
    return {
        "key": f"0x{provider_id:04X}:{channel_id}:{source_name}",
        "provider_id": provider_id,
        "id": channel_id,
        "name": name,
        "source_name": source_name,
        "value": value,
        "timestamp": int(timestamp_ts * 1000),
        "updated_at_ts": timestamp_ts,
        "category": category,
        "units": units,
    }


def _seed_live_data(*, channels, capturing=True, provider_id=0x1001):
    from api.routes.jetdrive._shared import _live_data, _live_data_lock

    snapshot = dict(_live_data)
    with _live_data_lock:
        _live_data.clear()
        _live_data.update(
            {
                "channels": channels,
                "capturing": capturing,
                "provider_id": provider_id,
                "provider_name": "Dyno RT",
                "provider_host": "192.168.1.55",
                "last_update_ts": time.time(),
            }
        )

    def _restore():
        with _live_data_lock:
            _live_data.clear()
            _live_data.update(snapshot)

    return _restore


def test_value_out_of_range_flag_is_emitted_for_rpm_above_limit(client):
    from api.routes.jetdrive.channel_health import reset_flag_history

    reset_flag_history()
    now = time.time()
    channels = {
        "Engine RPM": _entry(
            "Engine RPM",
            value=12000.0,  # above 10000 spec limit
            units="rpm",
            category="dyno",
            channel_id=39,
            now=now,
        ),
        "AFR Front": _entry(
            "AFR Front", value=13.2, units=":1", category="afr", now=now
        ),
    }
    _restore = _seed_live_data(channels=channels)
    try:
        body = client.get("/api/jetdrive/hardware/channels/health").get_json()
        rows = {row["canonical_name"]: row for row in body["channels"]}

        rpm = rows["Engine RPM"]
        assert rpm["status"] == "INVALID"
        assert "value_out_of_range" in rpm["flags"]
        assert rpm["min_value"] == 0.0
        assert rpm["max_value"] == 10000.0
        # Rolling counter incremented at least once on this poll.
        assert rpm["value_out_of_range_count_60s"] >= 1
    finally:
        _restore()


def test_value_out_of_range_for_map_below_zero(client):
    from api.routes.jetdrive.channel_health import reset_flag_history

    reset_flag_history()
    now = time.time()
    channels = {
        "Engine RPM": _entry("Engine RPM", value=3210.0, category="dyno", now=now),
        "AFR Front": _entry(
            "AFR Front", value=13.2, units=":1", category="afr", now=now
        ),
        "MAP kPa": _entry(
            "MAP kPa", value=-5.0, units="kPa", category="engine", now=now
        ),
    }
    _restore = _seed_live_data(channels=channels)
    try:
        body = client.get("/api/jetdrive/hardware/channels/health").get_json()
        rows = {row["canonical_name"]: row for row in body["channels"]}

        map_row = rows["MAP kPa"]
        assert map_row["status"] == "INVALID"
        assert "value_out_of_range" in map_row["flags"]
        assert map_row["min_value"] == 0.0
        assert map_row["max_value"] == 115.0
    finally:
        _restore()


def test_lc2_peg_count_60s_increments_on_each_poll_with_peg(client):
    from api.routes.jetdrive.channel_health import reset_flag_history

    reset_flag_history()
    now = time.time()
    channels = {
        "Engine RPM": _entry("Engine RPM", value=3210.0, category="dyno", now=now),
        "AFR Front": _entry(
            "AFR Front",
            value=22.39,  # pegged
            units=":1",
            category="afr",
            now=now,
        ),
    }
    _restore = _seed_live_data(channels=channels)
    try:
        body1 = client.get("/api/jetdrive/hardware/channels/health").get_json()
        rows = {row["canonical_name"]: row for row in body1["channels"]}
        assert rows["AFR Front"]["lc2_peg_count_60s"] == 1

        body2 = client.get("/api/jetdrive/hardware/channels/health").get_json()
        rows = {row["canonical_name"]: row for row in body2["channels"]}
        assert rows["AFR Front"]["lc2_peg_count_60s"] == 2
    finally:
        _restore()


def test_validator_samples_per_second_is_surfaced(client):
    """
    The validator's per-channel rate should appear on the health row when a
    matching (provider_id, channel_id) entry exists. Drive samples through
    the actual validator instance to avoid mocking a parallel system.
    """
    from api.routes.jetdrive.channel_health import reset_flag_history
    from api.services.jetdrive.jetdrive_client import JetDriveSample
    from api.services.jetdrive.jetdrive_validation import get_validator

    reset_flag_history()
    validator = get_validator()
    validator.reset()

    provider_id = 0x1001
    channel_id = 39
    base_ts = time.time() - 0.5
    # 6 samples spaced 100 ms apart -> ~10 Hz over a 0.5 s span.
    for i in range(6):
        validator.record_sample(
            JetDriveSample(
                provider_id=provider_id,
                channel_id=channel_id,
                channel_name="Engine RPM",
                timestamp_ms=int((base_ts + i * 0.1) * 1000),
                value=3000.0 + i,
            )
        )

    now = time.time()
    channels = {
        "Engine RPM": _entry(
            "Engine RPM",
            value=3210.0,
            units="rpm",
            category="dyno",
            provider_id=provider_id,
            channel_id=channel_id,
            now=now,
        ),
        "AFR Front": _entry(
            "AFR Front", value=13.2, units=":1", category="afr", now=now
        ),
    }
    _restore = _seed_live_data(channels=channels)
    try:
        body = client.get("/api/jetdrive/hardware/channels/health").get_json()
        rows = {row["canonical_name"]: row for row in body["channels"]}

        rpm = rows["Engine RPM"]
        assert rpm["total_samples"] == 6
        # Computed rate is non-zero — exact rate depends on wall-clock time
        # spacing recorded into the validator.
        assert rpm["samples_per_second"] > 0.0
    finally:
        validator.reset()
        _restore()
