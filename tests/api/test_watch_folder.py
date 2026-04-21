"""Tests for the Power Core watch-folder service and routes."""

from __future__ import annotations

import os

import pytest

from api.services.parsers.file_index import reset_file_index
from api.services.watch_folder import maybe_start_watcher
from api.services.watch_folder.broadcaster import WatchFolderBroadcaster
from api.services.watch_folder.config import load_watch_folders
from api.services.watch_folder.service import WatcherService

os.environ["DYNOAI_WATCH_FOLDER_ENABLED"] = "0"


def test_load_watch_folders_merges_default_env_and_yaml(tmp_path, monkeypatch):
    default_dir = tmp_path / "default"
    env_dir = tmp_path / "env"
    yaml_dir = tmp_path / "yaml"
    for folder in (default_dir, env_dir, yaml_dir):
        folder.mkdir(parents=True)

    config_path = tmp_path / "watch_folder.yaml"
    config_path.write_text(f"folders:\n  - {yaml_dir}\n", encoding="utf-8")

    monkeypatch.setattr(
        "api.services.watch_folder.config.find_powercore_data_dirs",
        lambda: [default_dir],
    )
    monkeypatch.setenv("DYNOAI_WATCH_FOLDERS", str(env_dir))

    loaded = load_watch_folders(config_path=config_path)
    loaded_set = {str(p) for p in loaded}
    assert str(default_dir.resolve()) in loaded_set
    assert str(env_dir.resolve()) in loaded_set
    assert str(yaml_dir.resolve()) in loaded_set


def test_broadcaster_recent_bound_and_subscriber_cleanup():
    broadcaster = WatchFolderBroadcaster(max_recent=3)

    for idx in range(5):
        broadcaster.broadcast({"idx": idx})

    recent = broadcaster.recent(limit=10)
    assert len(recent) == 3
    assert recent[0]["idx"] == 4
    assert recent[-1]["idx"] == 2

    stream = broadcaster.subscribe()
    _ = next(stream)  # connected event
    assert broadcaster.status()["subscriber_count"] == 1

    stream.close()
    assert broadcaster.status()["subscriber_count"] == 0


def test_handle_path_placeholder_skip_emits_no_event(tmp_path, monkeypatch):
    csv_file = tmp_path / "incoming.csv"
    csv_file.write_text("timestamp,rpm\n0,1000\n", encoding="utf-8")

    broadcaster = WatchFolderBroadcaster(max_recent=10)
    service = WatcherService(broadcaster=broadcaster)

    monkeypatch.setattr(service, "_is_placeholder_stub", lambda _path: True)
    monkeypatch.setattr(service, "_is_stable", lambda _path: True)

    payload = service.handle_path(csv_file)
    assert payload is None
    assert broadcaster.status()["event_count"] == 0


def test_handle_path_dedup_and_parse_failure(tmp_path, monkeypatch):
    reset_file_index()
    csv_file = tmp_path / "incoming.csv"
    csv_file.write_text("timestamp,rpm\n0,1000\n", encoding="utf-8")

    broadcaster = WatchFolderBroadcaster(max_recent=10)
    service = WatcherService(broadcaster=broadcaster)

    monkeypatch.setattr(service, "_is_placeholder_stub", lambda _path: False)
    monkeypatch.setattr(service, "_is_stable", lambda _path: True)
    monkeypatch.setattr(
        "api.services.watch_folder.service.parse_powervision_log",
        lambda _path: (_ for _ in ()).throw(ValueError("bad csv")),
    )

    payload = service.handle_path(csv_file)
    assert payload is not None
    assert payload["parse_ok"] is False
    assert "parse_failed" in payload["parse_detail"]
    assert broadcaster.status()["event_count"] == 1

    # Immediate second pass should dedupe.
    assert service.handle_path(csv_file) is None
    assert broadcaster.status()["event_count"] == 1
    reset_file_index()


def test_handle_path_empty_csv_parse_is_failure(tmp_path, monkeypatch):
    reset_file_index()
    csv_file = tmp_path / "emptyish.csv"
    csv_file.write_text("header_only\n", encoding="utf-8")

    class _Parsed:
        def __init__(self):
            self.signals = {}
            self.data = []

    broadcaster = WatchFolderBroadcaster(max_recent=10)
    service = WatcherService(broadcaster=broadcaster)

    monkeypatch.setattr(service, "_is_placeholder_stub", lambda _path: False)
    monkeypatch.setattr(service, "_is_stable", lambda _path: True)
    monkeypatch.setattr(
        "api.services.watch_folder.service.parse_powervision_log",
        lambda _path: _Parsed(),
    )

    payload = service.handle_path(csv_file)
    assert payload is not None
    assert payload["parse_ok"] is False
    assert "empty_or_incomplete_log" in payload["parse_detail"]
    reset_file_index()


def test_rescan_requires_configured_folder(tmp_path):
    service = WatcherService()
    configured = tmp_path / "configured"
    configured.mkdir()
    service._folders = [configured.resolve()]  # test setup

    with pytest.raises(ValueError, match="not configured"):
        service.rescan(tmp_path / "other", limit=5)


def test_maybe_start_watcher_guards(monkeypatch):
    class _App:
        debug = True

    monkeypatch.setenv("DYNOAI_WATCH_FOLDER_ENABLED", "0")
    assert maybe_start_watcher(_App()) is False

    monkeypatch.setenv("DYNOAI_WATCH_FOLDER_ENABLED", "1")
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    assert maybe_start_watcher(_App()) is False


def test_watch_routes_status_and_rescan_validation(client):
    status_resp = client.get("/api/powercore/watch/status")
    assert status_resp.status_code == 200
    status_data = status_resp.get_json()
    assert "running" in status_data
    assert "subscriber_count" in status_data

    rescan_resp = client.post("/api/powercore/watch/rescan", json={})
    assert rescan_resp.status_code == 400
    assert "Missing required field: folder" in rescan_resp.get_json()["error"]
