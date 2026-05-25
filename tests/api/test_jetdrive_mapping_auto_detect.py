"""Structured-error contract tests for ``POST /mapping/auto-detect``."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _ProviderStub:
    provider_id: int
    name: str
    host: str
    port: int = 22344
    channels: dict[int, object] = field(default_factory=dict)


def test_auto_detect_returns_503_when_no_providers(client, monkeypatch):
    """When discovery yields zero providers, return the structured 503 contract."""
    from api.routes.jetdrive import mapping as mapping_routes

    async def _empty_discover(_config, timeout=0.0):
        return []

    monkeypatch.setattr(
        "api.services.jetdrive.jetdrive_client.discover_providers",
        _empty_discover,
    )
    # Some routes import it via the jetdrive_client module attribute used inside
    # the function body; make sure both paths return [].
    if hasattr(mapping_routes, "discover_providers"):
        monkeypatch.setattr(mapping_routes, "discover_providers", _empty_discover)

    resp = client.post(
        "/api/jetdrive/mapping/auto-detect",
        json={},
    )
    assert resp.status_code == 503

    body = resp.get_json()
    assert body["status"] == "no_providers"
    assert body["error_code"] == "no_providers"
    assert "retryable" in body and body["retryable"] is True
    assert isinstance(body.get("retry_after_ms"), int)
    assert body["retry_after_ms"] >= 1000
    assert body["message"]  # non-empty


def test_auto_detect_returns_404_when_requested_provider_missing(client, monkeypatch):
    from api.routes.jetdrive import mapping as mapping_routes

    providers = [_ProviderStub(provider_id=0x1001, name="Dyno RT", host="192.168.1.55")]

    async def _discover(_config, timeout=0.0):
        return providers

    monkeypatch.setattr(
        "api.services.jetdrive.jetdrive_client.discover_providers",
        _discover,
    )
    if hasattr(mapping_routes, "discover_providers"):
        monkeypatch.setattr(mapping_routes, "discover_providers", _discover)

    # Ask for a provider that does not exist.
    resp = client.post(
        "/api/jetdrive/mapping/auto-detect",
        json={"provider_id": 0x9999},
    )
    assert resp.status_code == 404

    body = resp.get_json()
    assert body["status"] == "provider_not_found"
    assert body["error_code"] == "provider_not_found"
    assert "available_provider_ids" in body
    assert body["available_provider_ids"] == ["0x1001"]
