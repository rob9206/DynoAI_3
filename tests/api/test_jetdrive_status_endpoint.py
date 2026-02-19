import json


def test_jetdrive_status_ok_without_runs_dir(client, tmp_path, monkeypatch):
    """
    Regression: /api/jetdrive/status must not 500 even if the project root has no runs/ folder.
    """
    monkeypatch.setenv("DYNOAI_PROJECT_ROOT", str(tmp_path))

    resp = client.get("/api/jetdrive/status")
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["available"] is True
    assert "runs_count" in data
    assert "runs" in data
    assert data["runs_count"] == 0
    assert data["runs"] == []


def test_jetdrive_status_lists_runs_from_manifest(client, tmp_path, monkeypatch):
    monkeypatch.setenv("DYNOAI_PROJECT_ROOT", str(tmp_path))

    run_dir = tmp_path / "runs" / "run_20251225_000001"
    run_dir.mkdir(parents=True)

    manifest = {
        "timestamp": "2025-12-25T00:00:01Z",
        "analysis": {
            "overall_status": "ok",
            "peak_hp": 123.4,
            "peak_tq": 98.7,
        },
        "inputs": {"mode": "simulate"},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    resp = client.get("/api/jetdrive/status")
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["runs_count"] == 1
    assert isinstance(data["runs"], list) and len(data["runs"]) == 1
    run = data["runs"][0]
    assert run["run_id"] == "run_20251225_000001"
    assert run["timestamp"] == "2025-12-25T00:00:01Z"
    assert run["peak_hp"] == 123.4
    assert run["peak_tq"] == 98.7
    assert run["status"] == "ok"


