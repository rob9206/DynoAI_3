"""End-to-end dispatch readiness flow for FATBOY v3 sessions."""

from __future__ import annotations

import io

import pytest
from werkzeug.datastructures import MultiDict


@pytest.fixture(autouse=True)
def _isolated_workspace(tmp_path, monkeypatch):
    """Point workspace singleton at an isolated tmp directory per test."""
    from api.services import tuning_workspace as ws_mod

    monkeypatch.setenv("DYNOAI_WORKSPACE_ROOT", str(tmp_path / "vehicles"))
    ws_mod.reset_workspace()
    yield
    ws_mod.reset_workspace()


def test_dispatch_readiness_fatboy_transitions_to_ready(client):
    vid = "fatboy_cvo"
    create_vehicle = client.post(
        "/api/workspace/vehicles",
        json={
            "id": vid,
            "name": "2006 CVO Fat Boy",
            "year": 2006,
            "make": "harley",
            "model": "flstfse2",
            "displacement_ci": 103.0,
        },
    )
    assert create_vehicle.status_code == 201

    create_session = client.post(f"/api/workspace/vehicles/{vid}/sessions", json={})
    assert create_session.status_code == 201
    sid = create_session.get_json()["id"]

    v3_payload = {
        "schema_version": "dynoai.session.v3",
        "session_id": sid,
        "status": "blocked_pending_verify",
        "vehicle": {
            "year": 2006,
            "make": "harley",
            "model": "flstfse2 cvo fatboy",
            "vin": "1HD1PNF156Y953325",
        },
        "build_spec": {
            "displacement_ci": 103.0,
            "injectors": {"flow_rate_g_s": 3.91, "status": "verify_pending"},
        },
        "verify_blockers": [
            {
                "field": "build_spec.displacement_ci",
                "blocking": True,
                "resolved": False,
                "owner": "planner",
            },
            {
                "field": "build_spec.injectors.flow_rate_g_s",
                "blocking": True,
                "resolved": False,
                "owner": "planner",
            },
            {
                "field": "vehicle.vin",
                "blocking": True,
                "resolved": False,
                "owner": "planner",
            },
        ],
        "session_blockers": [],
        "template": {"dispatch_after": ["dispatch_ready"]},
        "kernel_sentinel": {"halt_on_breach": True, "lambda_targets": {"wot": 0.88}},
    }
    upsert_v3 = client.post(
        f"/api/workspace/vehicles/{vid}/sessions/{sid}/v3",
        json=v3_payload,
    )
    assert upsert_v3.status_code == 200

    readiness_before = client.get(
        f"/api/workspace/vehicles/{vid}/sessions/{sid}/dispatch_readiness"
    )
    assert readiness_before.status_code == 200
    readiness_before_body = readiness_before.get_json()
    assert readiness_before_body["ready"] is False
    assert readiness_before_body["gates"]["workspace_ready"] is False
    assert readiness_before_body["gates"]["verify_blockers_resolved"] is False
    assert readiness_before_body["gates"]["p0_plausibility_ok"] is False

    # Meet workspace-ready gate: one base tune and one AFR pull.
    pvv_bytes = (
        b'<?xml version="1.0"?><PVV>'
        b'<Item name="tbl_ve_tps_based_front_cyl"><Cell value="1.0"/></Item></PVV>'
    )
    dyno_txt = (
        b"Time\tmph\tft-lbs\thp\tLC1 Volts Petrol AFR\tLC2 Volts Petrol AFR2\n"
        b"0.5\t30.0\t12.0\t10.0\t13.5\t13.4\n"
        b"1.0\t40.0\t18.0\t22.0\t13.2\t13.1\n"
        b"1.5\t55.0\t30.0\t35.0\t12.9\t12.8\n"
        b"2.0\t70.0\t42.0\t48.0\t12.7\t12.6\n"
    )
    upload = client.post(
        f"/api/workspace/vehicles/{vid}/sessions/{sid}/upload",
        data=MultiDict(
            [
                ("files", (io.BytesIO(pvv_bytes), "stock.pvv")),
                ("files", (io.BytesIO(dyno_txt), "pull.txt")),
            ]
        ),
        content_type="multipart/form-data",
    )
    assert upload.status_code == 200

    # Resolve all verify blockers.
    for field_name in [
        "build_spec.displacement_ci",
        "build_spec.injectors.flow_rate_g_s",
        "vehicle.vin",
    ]:
        resolve = client.post(
            f"/api/workspace/vehicles/{vid}/sessions/{sid}/v3/resolve_blocker",
            json={
                "field": field_name,
                "resolved_by": "test",
                "evidence": "fixture-confirmed",
            },
        )
        assert resolve.status_code == 200

    # Run P0 plausibility.
    p0 = client.post(
        f"/api/workspace/vehicles/{vid}/sessions/{sid}/p0_plausibility",
        json={
            "known_displacement_ci": 103.0,
            "peak_tq_ftlb": 105.0,
            "peak_tq_rpm": 3200.0,
        },
    )
    assert p0.status_code == 200
    assert p0.get_json()["p0_plausibility"]["status"] == "pass"

    # Meet status gate (dispatch_after includes dispatch_ready).
    patch = client.patch(
        f"/api/workspace/vehicles/{vid}/sessions/{sid}",
        json={"status": "dispatch_ready"},
    )
    assert patch.status_code == 200

    readiness_after = client.get(
        f"/api/workspace/vehicles/{vid}/sessions/{sid}/dispatch_readiness"
    )
    assert readiness_after.status_code == 200
    readiness_after_body = readiness_after.get_json()
    assert readiness_after_body["ready"] is True
    assert readiness_after_body["gates"]["workspace_ready"] is True
    assert readiness_after_body["gates"]["verify_blockers_resolved"] is True
    assert readiness_after_body["gates"]["session_blockers_clear"] is True
    assert readiness_after_body["gates"]["status_gate_ok"] is True
    assert readiness_after_body["gates"]["kernel_halt_on_breach"] is True
    assert readiness_after_body["gates"]["p0_plausibility_ok"] is True
