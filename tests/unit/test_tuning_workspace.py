"""Tests for api.services.tuning_workspace."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from api.services.tuning_workspace import (
    TuningWorkspace,
    WorkspaceError,
    reset_workspace,
    slugify,
)


@pytest.fixture()
def ws() -> TuningWorkspace:
    reset_workspace()
    tmp = tempfile.mkdtemp(prefix="wsp_test_")
    workspace = TuningWorkspace(root=tmp)
    try:
        yield workspace
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        reset_workspace()


def test_slugify():
    assert slugify("Racile 2006 Dyna 88ci") == "racile_2006_dyna_88ci"
    assert slugify("  Strange!!! name ") == "strange_name"
    assert slugify("") == "untitled"


def test_create_and_get_vehicle(ws: TuningWorkspace):
    vehicle = ws.create_vehicle(name="Racile 2006 Dyna 88ci", year=2006)
    assert vehicle.id == "racile_2006_dyna_88ci"
    assert vehicle.year == 2006
    assert (ws.root / vehicle.id / "profile.json").exists()

    fetched = ws.get_vehicle(vehicle.id)
    assert fetched.name == vehicle.name


def test_duplicate_vehicle_rejected(ws: TuningWorkspace):
    ws.create_vehicle(name="Racile 2006 Dyna")
    with pytest.raises(WorkspaceError):
        ws.create_vehicle(name="Racile 2006 Dyna")


def test_list_vehicles_sorted(ws: TuningWorkspace):
    ws.create_vehicle(name="Bravo")
    ws.create_vehicle(name="Alpha")
    names = [v.id for v in ws.list_vehicles()]
    assert names == ["alpha", "bravo"]


def test_update_vehicle_signature(ws: TuningWorkspace):
    vehicle = ws.create_vehicle(name="Racile 2006 Dyna")
    updated = ws.update_vehicle(vehicle.id, ecu_signature="abc123")
    assert updated.ecu_signature == "abc123"


def test_create_session_bootstraps_iter0(ws: TuningWorkspace):
    vehicle = ws.create_vehicle(name="Racile 2006 Dyna")
    session = ws.create_session(vehicle_id=vehicle.id)
    assert session.active_iteration_id == "iter_0"
    iter0 = ws.get_iteration(vehicle.id, session.id, "iter_0")
    assert iter0.index == 0


def test_pull_routing(ws: TuningWorkspace):
    vehicle = ws.create_vehicle(name="Racile 2006 Dyna")
    session = ws.create_session(vehicle_id=vehicle.id)
    pvv = b'<?xml version="1.0"?><PVV/>'
    ws.set_base_tune(vehicle.id, session.id, pvv)

    wp8 = b"\xfe\xce\xfa\xce" + b"\x00" * 50
    ws.add_pull(vehicle.id, session.id, "iter_0", "run.wp8", wp8)

    pulls = ws.list_pulls(vehicle.id, session.id, "iter_0")
    assert len(pulls) == 1
    assert pulls[0].name == "run.wp8"


def test_create_iteration_advances_active(ws: TuningWorkspace):
    vehicle = ws.create_vehicle(name="Racile 2006 Dyna")
    session = ws.create_session(vehicle_id=vehicle.id)
    iter1 = ws.create_iteration(vehicle.id, session.id, patch_filename="foo.pvv")
    assert iter1.id == "iter_1"
    refreshed = ws.get_session(vehicle.id, session.id)
    assert refreshed.active_iteration_id == "iter_1"
    assert ws.get_active_iteration(vehicle.id, session.id).id == "iter_1"


def test_unique_path_avoids_overwrite(ws: TuningWorkspace):
    vehicle = ws.create_vehicle(name="Racile 2006 Dyna")
    session = ws.create_session(vehicle_id=vehicle.id)
    ws.add_pull(vehicle.id, session.id, "iter_0", "pull.txt", b"a")
    ws.add_pull(vehicle.id, session.id, "iter_0", "pull.txt", b"b")
    names = {p.name for p in ws.list_pulls(vehicle.id, session.id, "iter_0")}
    assert names == {"pull.txt", "pull-1.txt"}


def test_status_progression(ws: TuningWorkspace):
    vehicle = ws.create_vehicle(name="Racile 2006 Dyna")
    session = ws.create_session(vehicle_id=vehicle.id)

    s = ws.compute_status(vehicle.id, session.id)
    assert s.ready_to_analyze is False
    assert s.has_base_tune is False
    assert s.pull_count == 0

    ws.set_base_tune(vehicle.id, session.id, b'<?xml version="1.0"?><PVV/>')
    ws.add_pull(vehicle.id, session.id, "iter_0", "pull.txt", b"ok")
    s = ws.compute_status(vehicle.id, session.id)
    assert s.has_base_tune is True
    assert s.pull_count == 1
    assert s.has_afr_data is True
    assert s.ready_to_analyze is True


def test_find_vehicle_by_ecu_signature(ws: TuningWorkspace):
    vehicle = ws.create_vehicle(name="Racile 2006 Dyna")
    ws.update_vehicle(vehicle.id, ecu_signature="deadbeef")
    assert ws.find_vehicle_by_ecu_signature("deadbeef").id == vehicle.id
    assert ws.find_vehicle_by_ecu_signature("nope") is None
