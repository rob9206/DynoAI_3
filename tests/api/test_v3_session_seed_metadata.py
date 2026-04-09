"""Contract tests for v3 session seed metadata fields."""

from __future__ import annotations


def test_create_session_returns_seed_metadata(client, auth_headers):
    response = client.post(
        "/api/v3/session",
        headers=auth_headers,
        json={
            "engine_family": "m8_114",
            "displacement_ci": 114,
            "cam_spec": "stock",
            "exhaust_type": "stock",
            "air_cleaner": "stock",
        },
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload is not None
    assert "seed_source" in payload
    assert payload["seed_source"] in {
        "user_import",
        "calibration_library",
        "template",
        "default",
    }
    assert "calibration_seed" in payload
    assert "seed_warning" in payload
