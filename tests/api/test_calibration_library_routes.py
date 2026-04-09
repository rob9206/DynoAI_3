"""API contract tests for /api/v3/calibration-library routes."""

from __future__ import annotations

from pathlib import Path

import pytest

from dynoai_v3.calibration_library import CalibrationLibrary
from dynoai_v3.template_library import HardwareConfig


def _seed_library(lib_dir: Path) -> str:
    library = CalibrationLibrary(lib_dir)
    cfg = HardwareConfig(
        engine_family="m8_114",
        displacement_ci=114,
        cam_spec="stock",
        exhaust_type="2into1",
        air_cleaner="high_flow",
    )
    return library.ingest_from_parsed(
        config=cfg,
        ve_front=[[82.0, 84.0], [86.0, 88.0]],
        ve_rear=[[81.5, 83.5], [85.5, 87.5]],
        afr_targets={40: 14.2, 70: 13.4},
        rpm_bins=[2000.0, 3000.0],
        map_bins=[40.0, 70.0],
        source_name="mastertune:C:/cal/m8_114_api_seed.mt8",
        source_path="C:/cal/m8_114_api_seed.mt8",
        operator="api-test",
        notes="seed for route tests",
    )


@pytest.fixture
def isolated_calibration_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from api.config import reload_config
    from api.services import calibration_library_service

    lib_dir = tmp_path / "calibration_library"
    monkeypatch.setenv("DYNOAI_CALIBRATION_LIBRARY_DIR", str(lib_dir))
    reload_config()
    calibration_library_service._library = None
    calibration_library_service._library_dir = None
    yield lib_dir
    calibration_library_service._library = None
    calibration_library_service._library_dir = None
    monkeypatch.delenv("DYNOAI_CALIBRATION_LIBRARY_DIR", raising=False)
    reload_config()


def test_list_calibration_library_returns_seeded_entries(
    client,
    auth_headers,
    isolated_calibration_library: Path,
):
    calibration_id = _seed_library(isolated_calibration_library)

    response = client.get("/api/v3/calibration-library", headers=auth_headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] >= 1
    entry = next(
        (item for item in payload["entries"] if item["calibration_id"] == calibration_id),
        None,
    )
    assert entry is not None
    assert entry["engine_family"] == "m8_114"
    assert str(entry.get("source_identity", "")).strip() != ""
    assert int(entry.get("afr_targets_count", 0)) == 2


def test_blend_calibration_library_accepts_min_similarity(
    client,
    auth_headers,
    isolated_calibration_library: Path,
):
    _seed_library(isolated_calibration_library)
    response = client.post(
        "/api/v3/calibration-library/blend",
        headers=auth_headers,
        json={
            "top_n": 5,
            "min_similarity": 0.5,
            "config": {
                "engine_family": "m8_114",
                "displacement_ci": 114,
                "cam_spec": "stock",
                "exhaust_type": "2into1",
                "air_cleaner": "high_flow",
            },
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["engine_family"] == "m8_114"
    assert payload["match_count"] >= 1
    assert float(payload["min_similarity"]) == pytest.approx(0.5)


def test_delete_calibration_then_get_returns_404(
    client,
    auth_headers,
    isolated_calibration_library: Path,
):
    calibration_id = _seed_library(isolated_calibration_library)
    delete_resp = client.delete(
        f"/api/v3/calibration-library/{calibration_id}",
        headers=auth_headers,
    )
    assert delete_resp.status_code == 200
    assert delete_resp.get_json()["deleted"] is True

    get_resp = client.get(
        f"/api/v3/calibration-library/{calibration_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 404
