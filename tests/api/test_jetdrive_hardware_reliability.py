from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _ProviderStub:
    provider_id: int
    name: str
    host: str
    channels: dict[int, object] = field(default_factory=dict)


def test_live_start_returns_503_when_no_providers(client, monkeypatch):
    from api.routes.jetdrive import hardware
    from api.routes.jetdrive._shared import _live_data, _live_data_lock

    monkeypatch.setattr(
        hardware,
        "_discover_providers_snapshot",
        lambda timeout=1.25: ([], None),
    )

    with _live_data_lock:
        previous = dict(_live_data)

    try:
        resp = client.post("/api/jetdrive/hardware/live/start")
        assert resp.status_code == 503
        body = resp.get_json()
        assert body["status"] == "no_providers"
        assert "retry_after_ms" in body

        with _live_data_lock:
            assert _live_data["capturing"] is False
            assert _live_data.get("error_code") == "no_providers"
    finally:
        with _live_data_lock:
            _live_data.clear()
            _live_data.update(previous)


def test_monitor_status_snapshots_when_monitor_not_running(client, monkeypatch):
    from api.routes.jetdrive import hardware
    from api.routes.jetdrive._shared import _monitor_lock, _monitor_state

    provider = _ProviderStub(
        provider_id=0x1001,
        name="Dyno RT",
        host="192.168.1.55",
        channels={10: object()},
    )
    monkeypatch.setattr(
        hardware,
        "_discover_providers_snapshot",
        lambda timeout=1.25: ([provider], None),
    )

    with _monitor_lock:
        previous = {
            "running": _monitor_state.get("running"),
            "last_check": _monitor_state.get("last_check"),
            "providers": list(_monitor_state.get("providers", [])),
            "history": list(_monitor_state.get("history", [])),
        }
        _monitor_state["running"] = False
        _monitor_state["last_check"] = None
        _monitor_state["providers"] = []
        _monitor_state["history"] = []

    try:
        resp = client.get("/api/jetdrive/hardware/monitor/status")
        assert resp.status_code == 200
        body = resp.get_json()

        assert body["running"] is False
        assert body["connected"] is True
        assert len(body["providers"]) == 1
        assert body["providers"][0]["provider_id"] == 0x1001
        assert body["providers"][0]["channel_count"] == 1
    finally:
        with _monitor_lock:
            _monitor_state["running"] = previous["running"]
            _monitor_state["last_check"] = previous["last_check"]
            _monitor_state["providers"] = previous["providers"]
            _monitor_state["history"] = previous["history"]


def test_live_start_rejects_unknown_requested_provider(client, monkeypatch):
    from api.routes.jetdrive import hardware
    from api.routes.jetdrive._shared import _live_data, _live_data_lock

    providers = [_ProviderStub(provider_id=0x1001, name="Dyno RT", host="192.168.1.55")]
    monkeypatch.setattr(
        hardware,
        "_discover_providers_snapshot",
        lambda timeout=1.25: (providers, None),
    )

    with _live_data_lock:
        previous = dict(_live_data)

    try:
        resp = client.post("/api/jetdrive/hardware/live/start?provider_id=0x1002")
        assert resp.status_code == 404
        body = resp.get_json()
        assert body["status"] == "provider_not_found"
        assert "available_provider_ids" in body
        with _live_data_lock:
            assert _live_data.get("error_code") == "provider_not_found"
            assert _live_data["capturing"] is False
    finally:
        with _live_data_lock:
            _live_data.clear()
            _live_data.update(previous)
