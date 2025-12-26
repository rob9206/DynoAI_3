import time

import pytest


@pytest.mark.integration
def test_simulator_live_flow(client, monkeypatch):
    """
    Simulator-backed E2E: start simulator, start live, observe telemetry, stop.
    """
    # Ensure simulator fallback is allowed in CI environments
    monkeypatch.setenv("DYNOAI_SIMULATOR_FALLBACK", "1")

    # Start simulator
    resp = client.post("/api/jetdrive/simulator/start", json={"profile": "m8_114"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("success") is True

    # Start live capture
    resp = client.post("/api/jetdrive/hardware/start")
    assert resp.status_code == 200

    # Poll for live data
    got_sample = False
    for _ in range(10):
        resp = client.get("/api/jetdrive/hardware/live/data")
        assert resp.status_code == 200
        payload = resp.get_json()
        if payload.get("capturing") and (payload.get("channels") or {}):
            got_sample = True
            break
        time.sleep(0.5)

    assert got_sample, "Expected some live channel data while capturing"

    # Stop live capture
    resp = client.post("/api/jetdrive/hardware/stop")
    assert resp.status_code == 200

    # Stop simulator
    resp = client.post("/api/jetdrive/simulator/stop")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("success") is True


