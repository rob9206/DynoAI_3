"""Tests for the unified hardware status endpoint + SSE health event."""

from __future__ import annotations

import json
import time

import pytest


def _seed_live(channels=None, *, capturing=True, provider_id=0x1001):
    from api.routes.jetdrive._shared import _live_data, _live_data_lock

    snapshot = dict(_live_data)
    with _live_data_lock:
        _live_data.clear()
        _live_data.update(
            {
                "channels": dict(channels or {}),
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


def _seed_monitor(*, providers):
    from api.routes.jetdrive._shared import _monitor_lock, _monitor_state

    snapshot = {
        "running": _monitor_state.get("running"),
        "last_check": _monitor_state.get("last_check"),
        "providers": list(_monitor_state.get("providers") or []),
        "history": list(_monitor_state.get("history") or []),
    }
    with _monitor_lock:
        _monitor_state["running"] = False
        _monitor_state["last_check"] = "2026-05-25T00:00:00"
        _monitor_state["providers"] = list(providers)
        _monitor_state["history"] = []

    def _restore():
        with _monitor_lock:
            _monitor_state.update(snapshot)

    return _restore


def test_unified_status_returns_aggregated_blocks(client):
    now = time.time()
    channels = {
        "Engine RPM": {
            "key": "0x1001:39:Engine RPM",
            "provider_id": 0x1001,
            "id": 39,
            "name": "Engine RPM",
            "value": 3210.0,
            "timestamp": int(now * 1000),
            "updated_at_ts": now,
            "category": "dyno",
            "units": "rpm",
            "source_name": "(DWRT CPU) Engine RPM",
        },
        "AFR Front": {
            "key": "0x1001:20:AFR Front",
            "provider_id": 0x1001,
            "id": 20,
            "name": "AFR Front",
            "value": 13.2,
            "timestamp": int(now * 1000),
            "updated_at_ts": now,
            "category": "afr",
            "units": ":1",
            "source_name": "LC2 Volts Petrol AFR1",
        },
    }
    restore_live = _seed_live(channels)
    restore_monitor = _seed_monitor(
        providers=[{"provider_id": 0x1001, "name": "Dyno RT", "host": "192.168.1.55", "channel_count": 12}]
    )
    try:
        resp = client.get("/api/jetdrive/hardware/status")
        assert resp.status_code == 200
        body = resp.get_json()

        # All four aggregated blocks present.
        assert set(body.keys()) >= {
            "timestamp",
            "provider",
            "capture",
            "channels",
            "mapping",
            "ingestion",
        }

        # Provider block reflects the seeded monitor snapshot.
        assert body["provider"]["connected"] is True
        assert body["provider"]["count"] == 1

        # Capture block reflects current live state.
        assert body["capture"]["capturing"] is True
        assert body["capture"]["provider_id"] == "0x1001"
        assert body["capture"]["data_age_seconds"] is not None

        # Channels block matches the channel-health payload contract.
        ch = body["channels"]
        assert "summary" in ch and "channels" in ch and "all_required_ok" in ch
        canonicals = {row["canonical_name"] for row in ch["channels"]}
        assert "Engine RPM" in canonicals
        assert "AFR Front" in canonicals

        # Ingestion block always present.
        assert "overall_health" in body["ingestion"]
    finally:
        restore_monitor()
        restore_live()


def test_unified_status_returns_200_with_no_providers(client):
    """The endpoint must always return 200 (no retry storms)."""
    restore_live = _seed_live(capturing=False, provider_id=None)
    restore_monitor = _seed_monitor(providers=[])
    try:
        resp = client.get("/api/jetdrive/hardware/status")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["provider"]["connected"] is False
        assert body["channels"]["summary"]["state"] in {"idle", "unmapped"}
        # Mapping block is null when no provider is pinned.
        assert body["mapping"] is None
    finally:
        restore_monitor()
        restore_live()


def test_sse_stream_emits_health_event(client):
    """The SSE stream should emit at least one ``event: health`` block."""
    restore_live = _seed_live(capturing=False, provider_id=None)
    restore_monitor = _seed_monitor(providers=[])
    try:
        resp = client.get("/api/jetdrive/hardware/live/stream", buffered=False)
        assert resp.status_code == 200

        chunks: list[str] = []
        deadline = time.time() + 4.0
        try:
            for raw in resp.response:
                if not raw:
                    continue
                chunks.append(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
                if any("event: health" in chunk for chunk in chunks):
                    break
                if time.time() > deadline:
                    pytest.fail("Timed out waiting for SSE health event")
        finally:
            try:
                resp.close()
            except Exception:
                pass

        joined = "".join(chunks)
        assert "event: health" in joined

        # Find the JSON payload that follows ``event: health``.
        idx = joined.index("event: health")
        tail = joined[idx:]
        data_idx = tail.index("data: ")
        end_idx = tail.index("\n\n", data_idx)
        body_str = tail[data_idx + len("data: "):end_idx].strip()
        body = json.loads(body_str)

        # The health event payload matches the unified status shape.
        assert "channels" in body
        assert "provider" in body
        assert "capture" in body
    finally:
        restore_monitor()
        restore_live()
