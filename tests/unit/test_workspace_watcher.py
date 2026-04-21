"""Smoke test for the hot-folder watcher."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

from api.services.ingest import watcher as watcher_module
from api.services.ingest.watcher import WorkspaceWatcher, get_watcher
from api.services.tuning_workspace import TuningWorkspace, reset_workspace

try:
    from watchdog.observers import Observer  # noqa: F401

    _HAS_WATCHDOG = True
except Exception:
    _HAS_WATCHDOG = False


pytestmark = pytest.mark.skipif(
    not _HAS_WATCHDOG, reason="watchdog not installed"
)


def test_hot_folder_routes_pvv_and_wp8(tmp_path: Path):
    reset_workspace()
    ws_root = tmp_path / "ws"
    watch_root = tmp_path / "watched"
    watch_root.mkdir()

    ws = TuningWorkspace(root=ws_root)
    vehicle = ws.create_vehicle(name="Racile 2006 Dyna", watch_folder=str(watch_root))
    session = ws.create_session(vehicle_id=vehicle.id)

    watcher = WorkspaceWatcher(workspace=ws, debounce_seconds=0.05)
    assert watcher.start()

    try:
        pvv = (
            b'<?xml version="1.0"?><PVV>'
            b'<Item name="tbl_ve_tps_based_front_cyl">'
            b'<Cell value="1.0"/></Item></PVV>'
        )
        wp8 = b"\xfe\xce\xfa\xce" + b"\x00" * 64

        (watch_root / "tune.pvv").write_bytes(pvv)
        (watch_root / "run.wp8").write_bytes(wp8)

        deadline = time.time() + 5.0
        while time.time() < deadline:
            routed = [e for e in watcher.recent_events() if e["ok"]]
            slots = {e["slot"] for e in routed}
            if {"base_tune", "pulls"}.issubset(slots):
                break
            time.sleep(0.1)
        else:
            pytest.fail(
                f"watcher did not route files in time: events={watcher.recent_events()}"
            )

        assert ws.get_base_tune_path(vehicle.id, session.id) is not None
        pulls = ws.list_pulls(vehicle.id, session.id, session.active_iteration_id)
        assert any(p.name == "run.wp8" for p in pulls)
    finally:
        watcher.stop()
        reset_workspace()


def test_get_watcher_singleton():
    w1 = get_watcher()
    w2 = get_watcher()
    assert w1 is w2
    watcher_module.reset_watcher()
