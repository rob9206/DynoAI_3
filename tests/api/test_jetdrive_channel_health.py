"""Tests for the /hardware/channels/health Channel Health Board endpoint."""

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


def _seed_live_data(
    monkeypatch_lock,
    *,
    channels: dict[str, Any],
    capturing: bool = True,
    provider_id: int | None = 0x1001,
    provider_name: str = "Dyno RT",
    provider_host: str = "192.168.1.55",
):
    from api.routes.jetdrive._shared import _live_data, _live_data_lock

    snapshot = dict(_live_data)
    with _live_data_lock:
        _live_data.clear()
        _live_data.update(
            {
                "channels": channels,
                "capturing": capturing,
                "provider_id": provider_id,
                "provider_name": provider_name,
                "provider_host": provider_host,
                "last_update_ts": time.time(),
            }
        )

    def _restore():
        with _live_data_lock:
            _live_data.clear()
            _live_data.update(snapshot)

    return _restore


def test_unmapped_when_no_channels_present(client):
    _restore = _seed_live_data(None, channels={}, capturing=False, provider_id=None)
    try:
        resp = client.get("/api/jetdrive/hardware/channels/health")
        assert resp.status_code == 200
        body = resp.get_json()

        # Every canonical row exists and is UNMAPPED with no source.
        assert len(body["channels"]) >= 5
        for row in body["channels"]:
            assert row["status"] == "UNMAPPED"
            assert row["source"] is None

        assert body["all_required_ok"] is False
        assert body["summary"]["state"] in {"idle", "unmapped"}
        assert body["summary"]["counts"]["UNMAPPED"] == len(body["channels"])
    finally:
        _restore()


def test_ok_status_for_required_channels(client):
    now = time.time()
    channels = {
        "Engine RPM": _entry(
            "Engine RPM",
            value=3210.0,
            units="rpm",
            category="dyno",
            channel_id=39,
            source_name="(DWRT CPU) Engine RPM",
            now=now,
        ),
        "AFR Front": _entry(
            "AFR Front",
            value=13.2,
            units=":1",
            category="afr",
            channel_id=20,
            source_name="LC2 Volts Petrol AFR1",
            now=now,
        ),
    }
    _restore = _seed_live_data(None, channels=channels, capturing=True)
    try:
        resp = client.get("/api/jetdrive/hardware/channels/health")
        body = resp.get_json()

        rows = {row["canonical_name"]: row for row in body["channels"]}

        assert rows["Engine RPM"]["status"] == "OK"
        assert rows["Engine RPM"]["value"] == 3210.0
        assert rows["Engine RPM"]["source"]["provider_id"] == "0x1001"
        assert rows["Engine RPM"]["source"]["channel_id"] == 39

        assert rows["AFR Front"]["status"] == "OK"
        assert rows["AFR Front"]["value"] == 13.2
        assert rows["AFR Rear"]["status"] == "UNMAPPED"

        # Required = RPM + AFR Front. Both are OK, so summary is healthy.
        assert body["all_required_ok"] is True
        assert body["summary"]["state"] == "all_healthy"
    finally:
        _restore()


def test_stale_status_when_age_exceeds_threshold(client):
    now = time.time()
    channels = {
        "Engine RPM": _entry(
            "Engine RPM",
            value=3210.0,
            units="rpm",
            category="dyno",
            age_seconds=5.0,  # > 2.5s threshold
            now=now,
        ),
        "AFR Front": _entry(
            "AFR Front",
            value=13.2,
            units=":1",
            category="afr",
            now=now,
        ),
    }
    _restore = _seed_live_data(None, channels=channels, capturing=True)
    try:
        body = client.get("/api/jetdrive/hardware/channels/health").get_json()
        rows = {row["canonical_name"]: row for row in body["channels"]}

        assert rows["Engine RPM"]["status"] == "STALE"
        assert rows["AFR Front"]["status"] == "OK"

        assert body["all_required_ok"] is False
        assert body["summary"]["state"] == "stale"
        assert body["summary"]["counts"]["STALE"] >= 1
    finally:
        _restore()


def test_lc2_pegged_marks_invalid_with_flag(client):
    """LC-2 voltage at the rail (>=22.38 AFR) must be flagged as INVALID."""
    now = time.time()
    channels = {
        "Engine RPM": _entry("Engine RPM", value=3210.0, category="dyno", now=now),
        "AFR Front": _entry(
            "AFR Front",
            value=22.39,  # ceiling
            units=":1",
            category="afr",
            now=now,
        ),
    }
    _restore = _seed_live_data(None, channels=channels, capturing=True)
    try:
        body = client.get("/api/jetdrive/hardware/channels/health").get_json()
        rows = {row["canonical_name"]: row for row in body["channels"]}

        assert rows["AFR Front"]["status"] == "INVALID"
        assert "lc2_pegged" in rows["AFR Front"]["flags"]
        assert body["summary"]["state"] == "invalid"
        assert body["all_required_ok"] is False
    finally:
        _restore()


def test_afr_implausible_flag_outside_band(client):
    """AFR <10 or >18 should be flagged ``afr_implausible`` and INVALID."""
    now = time.time()
    channels = {
        "Engine RPM": _entry("Engine RPM", value=3210.0, category="dyno", now=now),
        "AFR Front": _entry(
            "AFR Front",
            value=5.0,  # below plausible
            units=":1",
            category="afr",
            now=now,
        ),
    }
    _restore = _seed_live_data(None, channels=channels, capturing=True)
    try:
        body = client.get("/api/jetdrive/hardware/channels/health").get_json()
        rows = {row["canonical_name"]: row for row in body["channels"]}

        assert rows["AFR Front"]["status"] == "INVALID"
        assert "afr_implausible" in rows["AFR Front"]["flags"]
    finally:
        _restore()


def test_rpm_zero_at_wot_flag(client):
    """RPM=0 with TPS>WOT should produce ``rpm_zero_at_wot`` and INVALID."""
    now = time.time()
    channels = {
        "Engine RPM": _entry("Engine RPM", value=0.0, category="dyno", now=now),
        "TPS": _entry("TPS", value=85.0, category="engine", units="%", now=now),
        "AFR Front": _entry(
            "AFR Front", value=13.2, units=":1", category="afr", now=now
        ),
    }
    _restore = _seed_live_data(None, channels=channels, capturing=True)
    try:
        body = client.get("/api/jetdrive/hardware/channels/health").get_json()
        rows = {row["canonical_name"]: row for row in body["channels"]}

        assert rows["Engine RPM"]["status"] == "INVALID"
        assert "rpm_zero_at_wot" in rows["Engine RPM"]["flags"]
    finally:
        _restore()


def test_no_signal_when_capturing_but_value_missing(client):
    """Capture is on, source slot exists, but no numeric sample yet."""
    now = time.time()
    channels = {
        "Engine RPM": _entry(
            "Engine RPM",
            value=None,
            category="dyno",
            now=now,
        ),
        "AFR Front": _entry(
            "AFR Front",
            value=13.2,
            units=":1",
            category="afr",
            now=now,
        ),
    }
    _restore = _seed_live_data(None, channels=channels, capturing=True)
    try:
        body = client.get("/api/jetdrive/hardware/channels/health").get_json()
        rows = {row["canonical_name"]: row for row in body["channels"]}

        # Missing numeric value triggers not_finite -> INVALID per design.
        assert rows["Engine RPM"]["status"] == "INVALID"
        assert "not_finite" in rows["Engine RPM"]["flags"]
    finally:
        _restore()


def test_provider_metadata_serialized_as_hex(client):
    now = time.time()
    channels = {
        "Engine RPM": _entry(
            "Engine RPM",
            value=3210.0,
            category="dyno",
            provider_id=0xFEED,
            now=now,
        ),
        "AFR Front": _entry(
            "AFR Front",
            value=13.2,
            category="afr",
            provider_id=0xFEED,
            now=now,
        ),
    }
    _restore = _seed_live_data(
        None, channels=channels, capturing=True, provider_id=0xFEED
    )
    try:
        body = client.get("/api/jetdrive/hardware/channels/health").get_json()
        assert body["provider"]["provider_id"] == "0xFEED"
        rpm_row = next(r for r in body["channels"] if r["canonical_name"] == "Engine RPM")
        assert rpm_row["source"]["provider_id"] == "0xFEED"
    finally:
        _restore()
