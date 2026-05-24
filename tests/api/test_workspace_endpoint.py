"""Integration tests for the /api/workspace endpoints."""

from __future__ import annotations

import io

import pytest
from werkzeug.datastructures import MultiDict


@pytest.fixture(autouse=True)
def _isolated_workspace(tmp_path, monkeypatch):
    """Point the workspace singleton at an isolated tmp directory per test."""
    from api.services import tuning_workspace as ws_mod

    monkeypatch.setenv("DYNOAI_WORKSPACE_ROOT", str(tmp_path / "vehicles"))
    ws_mod.reset_workspace()
    yield
    ws_mod.reset_workspace()


class TestVehicleLifecycle:

    @staticmethod
    def test_list_vehicles_empty(client):
        resp = client.get("/api/workspace/vehicles")
        assert resp.status_code == 200
        assert resp.get_json() == []

    @staticmethod
    def test_create_vehicle(client):
        resp = client.post(
            "/api/workspace/vehicles",
            json={
                "name": "Racile 2006 Dyna 88ci",
                "year": 2006
            },
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["id"] == "racile_2006_dyna_88ci"
        assert body["year"] == 2006

    @staticmethod
    def test_duplicate_vehicle_rejected(client):
        client.post("/api/workspace/vehicles", json={"name": "Dyna"})
        resp = client.post("/api/workspace/vehicles", json={"name": "Dyna"})
        assert resp.status_code == 400

    @staticmethod
    def test_missing_name_rejected(client):
        resp = client.post("/api/workspace/vehicles", json={})
        assert resp.status_code == 400


class TestSessionLifecycle:

    @staticmethod
    def _make_vehicle(client):
        client.post("/api/workspace/vehicles", json={"name": "Dyna"})

    @staticmethod
    def test_create_session_and_status(client):
        TestSessionLifecycle._make_vehicle(client)
        resp = client.post("/api/workspace/vehicles/dyna/sessions",
                           json={"notes": "baseline"})
        assert resp.status_code == 201
        session = resp.get_json()
        assert session["active_iteration_id"] == "iter_0"

        sid = session["id"]
        status_resp = client.get(
            f"/api/workspace/vehicles/dyna/sessions/{sid}/status")
        assert status_resp.status_code == 200
        status = status_resp.get_json()
        assert status["ready_to_analyze"] is False
        assert status["has_base_tune"] is False


class TestUploadRouting:

    @staticmethod
    def _bootstrap(client):
        client.post(
            "/api/workspace/vehicles",
            json={
                "name": "Dyna",
                "year": 2006
            },
        )
        resp = client.post("/api/workspace/vehicles/dyna/sessions", json={})
        return resp.get_json()["id"]

    @staticmethod
    def test_upload_routes_pvv_to_base_tune(client):
        sid = TestUploadRouting._bootstrap(client)

        pvv_bytes = (b'<?xml version="1.0"?><PVV>'
                     b'<Item name="tbl_ve_tps_based_front_cyl">'
                     b'<Cell value="1.0"/></Item></PVV>')
        data = {
            "files": (io.BytesIO(pvv_bytes), "tune.pvv"),
        }
        resp = client.post(
            f"/api/workspace/vehicles/dyna/sessions/{sid}/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["routed"]) == 1
        assert body["routed"][0]["slot"] == "base_tune"
        assert body["routed"][0]["type"] == "pvv"
        assert body["status"]["has_base_tune"] is True

    @staticmethod
    def test_upload_routes_wp8_to_pulls(client):
        sid = TestUploadRouting._bootstrap(client)
        wp8_bytes = b"\xfe\xce\xfa\xce" + b"\x00" * 64

        data = {
            "files": (io.BytesIO(wp8_bytes), "run.wp8"),
        }
        resp = client.post(
            f"/api/workspace/vehicles/dyna/sessions/{sid}/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["routed"][0]["slot"] == "pulls"
        assert body["routed"][0]["type"] == "wp8"
        assert body["status"]["pull_count"] == 1

    @staticmethod
    def test_upload_multiple_files_mixed(client):
        sid = TestUploadRouting._bootstrap(client)
        pvv_bytes = (b'<?xml version="1.0"?><PVV>'
                     b'<Item name="tbl_ve_tps_based_front_cyl">'
                     b'<Cell value="1.0"/></Item></PVV>')
        wp8_bytes = b"\xfe\xce\xfa\xce" + b"\x00" * 32
        dyno_txt = (b"Time\tSpeed (mph)\tPower (hp)\tLC1 AFR\tLC2 AFR\n"
                    b"0.5\t30\t10\t13.5\t13.4\n"
                    b"1.0\t40\t22\t13.2\t13.1\n"
                    b"1.5\t55\t35\t12.9\t12.8\n")

        data = MultiDict([
            ("files", (io.BytesIO(pvv_bytes), "tune.pvv")),
            ("files", (io.BytesIO(wp8_bytes), "run.wp8")),
            ("files", (io.BytesIO(dyno_txt), "pull.txt")),
        ])
        resp = client.post(
            f"/api/workspace/vehicles/dyna/sessions/{sid}/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        slots = {r["slot"] for r in body["routed"]}
        assert slots == {"base_tune", "pulls"}
        assert body["status"]["pull_count"] == 2
        assert body["status"]["has_base_tune"] is True
        assert body["status"]["has_afr_data"] is True
        assert body["status"]["ready_to_analyze"] is True

    @staticmethod
    def test_upload_with_no_files_rejected(client):
        sid = TestUploadRouting._bootstrap(client)
        resp = client.post(
            f"/api/workspace/vehicles/dyna/sessions/{sid}/upload",
            data={},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400


# -----------------------------------------------------------------------------
# Persisted-result consistency: the on-disk autotune_<ts>.json must match the
# API response. The earlier ordering wrote first then mutated success/path,
# leaving stale values in the file.
# -----------------------------------------------------------------------------


class TestAnalyzeResultPersistenceConsistency:

    @staticmethod
    def _bootstrap_with_pulls(client):
        import json
        from pathlib import Path

        import pandas as pd

        from api.services.tuning_workspace import get_workspace

        client.post("/api/workspace/vehicles", json={"name": "Dyna"})
        resp = client.post("/api/workspace/vehicles/dyna/sessions", json={})
        sid = resp.get_json()["id"]

        ws = get_workspace()
        profile_path = ws.vehicle_profile("dyna")
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["tuning_guardrails"] = {
            "ve_table_ids": ["tbl_ve_tps_based_front_cyl", "tbl_ve_tps_based_rear_cyl"],
            "ve_cap_pct": 155.0,
            "ve_floor_pct": 70.0,
            "max_correction_pct_per_cell": 10.0,
        }
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

        repo_root = Path(__file__).resolve().parents[2]
        pvv_path = (
            repo_root
            / "vehicles"
            / "seanbike"
            / "sessions"
            / "dai_2026_0518_pcv_bake_verify"
            / "iterations"
            / "iter_0"
            / "patches"
            / "newnenww_emergency_rich_v5_stepup.pvv"
        )
        pvv = pvv_path.read_bytes()

        running9_path = (
            repo_root
            / "vehicles"
            / "seanbike"
            / "sessions"
            / "dai_2026_0518_pcv_bake_verify"
            / "iterations"
            / "iter_0"
            / "pulls"
            / "runnning_9.txt"
        )
        raw = pd.read_csv(running9_path)
        raw.columns = [str(c).strip() for c in raw.columns]

        normalized = pd.DataFrame(
            {
                "Engine RPM": pd.to_numeric(raw["(DWRT CPU) Engine RPM"], errors="coerce"),
                "Throttle Position": pd.to_numeric(raw["(PV) Throttle Position"], errors="coerce"),
                "AFR Meas": pd.to_numeric(raw["(DWRT CPU) LC1 Volts Petrol AFR"], errors="coerce"),
            }
        ).dropna(subset=["Engine RPM", "Throttle Position", "AFR Meas"])

        normalized = normalized[
            (normalized["Engine RPM"] > 0.5)
            & (normalized["Engine RPM"] <= 8.0)
            & (normalized["Throttle Position"] >= 0)
            & (normalized["Throttle Position"] <= 100)
            & (normalized["AFR Meas"] >= 7.0)
            & (normalized["AFR Meas"] <= 23.0)
        ].reset_index(drop=True)

        pull_csv = normalized.to_csv(index=False).encode("utf-8")

        data = MultiDict([
            ("files", (io.BytesIO(pvv), "tune.pvv")),
            ("files", (io.BytesIO(pull_csv), "pull.csv")),
        ])
        client.post(
            f"/api/workspace/vehicles/dyna/sessions/{sid}/upload",
            data=data,
            content_type="multipart/form-data",
        )
        return sid

    @staticmethod
    def test_persisted_json_matches_api_response(client, tmp_path):
        import json
        from pathlib import Path

        sid = TestAnalyzeResultPersistenceConsistency._bootstrap_with_pulls(
            client)

        resp = client.post(
            f"/api/workspace/vehicles/dyna/sessions/{sid}/analyze", json={})
        body = resp.get_json()
        assert body["analysis_json_path"], "API must surface the analysis path"
        assert "success" in body

        on_disk = Path(body["analysis_json_path"])
        assert on_disk.exists(
        ), "analysis JSON must be on disk at the reported path"

        persisted = json.loads(on_disk.read_text(encoding="utf-8"))
        assert persisted["success"] == body["success"], (
            "persisted success must match API response")
        assert persisted["analysis_json_path"] == body["analysis_json_path"], (
            "persisted analysis_json_path must self-reference its own file")
        assert persisted["correction_pvv_path"] == body["correction_pvv_path"]


class TestPeakHpUnitsAreNotConflated:
    """
    Dynojet TXT exports report `peak_hp_mph` (wheel speed at peak HP), not
    engine RPM. Earlier the analyzer fell back to mph as if it were RPM. The
    two are distinct fields now.
    """

    @staticmethod
    def test_peak_hp_mph_kept_separate_from_peak_hp_rpm(client):
        sid = TestAnalyzeResultPersistenceConsistency._bootstrap_with_pulls(
            client)
        resp = client.post(
            f"/api/workspace/vehicles/dyna/sessions/{sid}/analyze", json={})
        body = resp.get_json()
        assert "peak_hp_mph" in body, "peak_hp_mph field must exist on result"
        # This fixture now uses normalized CSV pulls with explicit RPM and TPS,
        # so wheel-speed-at-peak (mph) is absent while peak_hp_rpm is present.
        assert body["peak_hp_mph"] is None
        assert body["peak_hp_rpm"] is None or body["peak_hp_rpm"] != body["peak_hp_mph"]
