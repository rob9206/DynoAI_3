"""Tests for the in-memory transient mapping cache."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from unittest.mock import patch

import pytest


@dataclass
class _ChannelInfoStub:
    chan_id: int
    name: str
    unit: int = 0
    vendor: int = 0


@dataclass
class _ProviderStub:
    provider_id: int
    name: str
    host: str
    port: int = 22344
    channels: dict[int, _ChannelInfoStub] = field(default_factory=dict)


def _stub_provider(channels: dict[int, _ChannelInfoStub] | None = None) -> _ProviderStub:
    return _ProviderStub(
        provider_id=0x1001,
        name="Dyno RT",
        host="192.168.1.55",
        channels=channels or {
            39: _ChannelInfoStub(chan_id=39, name="Engine RPM", unit=8),
            20: _ChannelInfoStub(chan_id=20, name="LC2 Volts Petrol AFR1", unit=14),
        },
    )


@pytest.fixture(autouse=True)
def _reset_transient():
    from api.services.jetdrive.mapping_transient_cache import reset_transient_cache

    reset_transient_cache()
    yield
    reset_transient_cache()


def test_store_then_get_returns_entry():
    from api.services.jetdrive.mapping_transient_cache import (
        get_transient_mapping,
        store_transient_mapping,
    )

    entry = store_transient_mapping(
        provider_signature="sig-1",
        provider_id=0x1001,
        provider_name="Dyno RT",
        host="192.168.1.55",
        mapping={"version": "1.0", "channels": {"rpm": {"source_id": 39}}},
    )
    found = get_transient_mapping("sig-1")
    assert found is entry
    assert found.source == "auto_detect"
    assert found.expires_at > entry.proposed_at


def test_get_returns_none_when_expired():
    from api.services.jetdrive.mapping_transient_cache import (
        get_transient_mapping,
        store_transient_mapping,
    )

    store_transient_mapping(
        provider_signature="sig-2",
        provider_id=0x1001,
        provider_name="Dyno RT",
        host="192.168.1.55",
        mapping={},
        ttl_seconds=1.0,
    )
    # Look up "10s in the future" so the TTL has elapsed.
    found = get_transient_mapping("sig-2", now_ts=time.time() + 10.0)
    assert found is None


def test_clear_removes_entry():
    from api.services.jetdrive.mapping_transient_cache import (
        clear_transient_mapping,
        get_transient_mapping,
        store_transient_mapping,
    )

    store_transient_mapping(
        provider_signature="sig-3",
        provider_id=0x1001,
        provider_name="Dyno RT",
        host="192.168.1.55",
        mapping={},
    )
    assert clear_transient_mapping("sig-3") is True
    assert get_transient_mapping("sig-3") is None
    # Idempotent.
    assert clear_transient_mapping("sig-3") is False


def test_auto_detect_route_populates_transient(client, monkeypatch, tmp_path):
    """``POST /mapping/auto-detect`` must store the proposal in the cache."""
    from api.routes.jetdrive import mapping as mapping_routes
    from api.services.jetdrive import jetdrive_mapping
    from api.services.jetdrive.mapping_transient_cache import get_transient_mapping

    provider = _stub_provider()

    async def _discover(_config, timeout=0.0):
        return [provider]

    monkeypatch.setattr(
        "api.services.jetdrive.jetdrive_client.discover_providers", _discover
    )
    if hasattr(mapping_routes, "discover_providers"):
        monkeypatch.setattr(mapping_routes, "discover_providers", _discover)

    # Point on-disk mapping dir at a temp path for hermetic tests.
    monkeypatch.setattr(jetdrive_mapping, "MAPPING_DIR", tmp_path / "mappings")

    resp = client.post("/api/jetdrive/mapping/auto-detect", json={})
    assert resp.status_code == 200
    body = resp.get_json()
    assert "transient_proposal" in body
    sig = body["mapping"]["provider_signature"]
    assert sig
    cached = get_transient_mapping(sig)
    assert cached is not None
    assert cached.source == "auto_detect"
    assert cached.provider_id == 0x1001


def test_save_route_clears_transient(client, monkeypatch, tmp_path):
    """``PUT /mapping/<sig>`` must clear the transient entry on success."""
    from api.routes.jetdrive import mapping as mapping_routes
    from api.services.jetdrive import jetdrive_mapping
    from api.services.jetdrive.mapping_transient_cache import (
        get_transient_mapping,
        store_transient_mapping,
    )

    monkeypatch.setattr(jetdrive_mapping, "MAPPING_DIR", tmp_path / "mappings")
    # Save mapping never actually opens a network socket; only fs.
    sig = "sig-save-test"
    store_transient_mapping(
        provider_signature=sig,
        provider_id=0x1001,
        provider_name="Dyno RT",
        host="192.168.1.55",
        mapping={"version": "1.0", "channels": {}},
    )
    assert get_transient_mapping(sig) is not None

    resp = client.put(
        f"/api/jetdrive/mapping/{sig}",
        json={
            "version": "1.0",
            "provider_id": 0x1001,
            "provider_name": "Dyno RT",
            "host": "192.168.1.55",
            "channels": {
                "rpm": {"source_id": 39, "source_name": "Engine RPM", "transform": "identity"},
            },
        },
    )
    assert resp.status_code == 200
    assert get_transient_mapping(sig) is None


def test_unified_status_surfaces_transient_block_separate_from_saved(
    client, monkeypatch
):
    """The unified status must expose ``saved`` and ``transient_proposal`` separately."""
    from api.routes.jetdrive._shared import _live_data, _live_data_lock
    from api.services.jetdrive.mapping_transient_cache import store_transient_mapping

    snapshot = dict(_live_data)
    with _live_data_lock:
        _live_data.clear()
        _live_data.update(
            {
                "channels": {},
                "capturing": False,
                "provider_id": 0x1001,
                "provider_name": "Dyno RT",
                "provider_host": "192.168.1.55",
                "last_update_ts": time.time(),
            }
        )

    store_transient_mapping(
        provider_signature="sig-status-test",
        provider_id=0x1001,
        provider_name="Dyno RT",
        host="192.168.1.55",
        mapping={"channels": {"rpm": {"source_id": 39}}},
    )

    try:
        resp = client.get("/api/jetdrive/hardware/status")
        body = resp.get_json()
        assert resp.status_code == 200
        mapping_block = body["mapping"]
        assert mapping_block is not None
        assert "saved" in mapping_block and "transient_proposal" in mapping_block
        # No saved mapping exists for this provider in the test env.
        assert mapping_block["saved"] is None
        transient = mapping_block["transient_proposal"]
        assert transient is not None
        assert transient["provider_id"] == "0x1001"
        assert transient["source"] == "auto_detect"
        assert transient["ttl_remaining_seconds"] > 0
    finally:
        with _live_data_lock:
            _live_data.clear()
            _live_data.update(snapshot)
