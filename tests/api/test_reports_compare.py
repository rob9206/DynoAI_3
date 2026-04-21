"""Tests for /api/reports/compare and comparison loading helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from api.services.report_generator import _load_comparison_run


@pytest.fixture
def comparison_runs(tmp_path: Path) -> Path:
    """Create two synthetic run directories with run.csv files."""
    runs_dir = tmp_path / "runs"
    run_a = runs_dir / "run_a"
    run_b = runs_dir / "run_b"
    run_a.mkdir(parents=True, exist_ok=True)
    run_b.mkdir(parents=True, exist_ok=True)

    run_a_csv = """Engine RPM,Horsepower,Torque,AFR Meas F,AFR Meas R
1000,20,100,13.5,13.6
2000,40,120,13.2,13.3
3000,65,130,13.0,13.1
4000,72,128,12.9,13.0
5000,68,119,12.8,12.9
"""
    run_b_csv = """Engine RPM,Horsepower,Torque,AFR Meas F,AFR Meas R
1000,22,102,13.4,13.5
2000,46,126,13.1,13.2
3000,70,135,12.9,13.0
4000,79,133,12.8,12.9
5000,75,125,12.7,12.8
"""
    (run_a / "run.csv").write_text(run_a_csv, encoding="utf-8")
    (run_b / "run.csv").write_text(run_b_csv, encoding="utf-8")
    return runs_dir


def test_compare_report_peaks_match_source_csv(comparison_runs: Path):
    peaks_a, curve_a, afr_a, _ = _load_comparison_run("run_a", comparison_runs)
    peaks_b, curve_b, afr_b, _ = _load_comparison_run("run_b", comparison_runs)

    assert peaks_a["peak_hp"] == pytest.approx(72.0)
    assert peaks_a["peak_hp_rpm"] == pytest.approx(4000.0)
    assert peaks_b["peak_hp"] == pytest.approx(79.0)
    assert peaks_b["peak_tq"] == pytest.approx(135.0)
    assert len(curve_a) == len(curve_b) == 11
    assert len(afr_a) == len(afr_b) == 11


def test_compare_runs_returns_pdf_metadata(client, monkeypatch, comparison_runs: Path):
    monkeypatch.setattr("api.routes.reports.get_runs_dir", lambda: comparison_runs)
    response = client.post(
        "/api/reports/compare",
        json={"run_a_id": "run_a", "run_b_id": "run_b", "customer_name": "Test"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["size_bytes"] > 0
    assert "download_url" in payload
    assert payload["summary"]["deltas"]["peak_hp_gain"] == pytest.approx(7.0)
    assert Path(payload["report_path"]).exists()


def test_compare_runs_download_true_returns_pdf(client, monkeypatch, comparison_runs: Path):
    monkeypatch.setattr("api.routes.reports.get_runs_dir", lambda: comparison_runs)
    response = client.post(
        "/api/reports/compare?download=true",
        json={"run_a_id": "run_a", "run_b_id": "run_b"},
    )
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert len(response.data) > 1000


def test_compare_runs_missing_run_returns_404(client, monkeypatch, comparison_runs: Path):
    monkeypatch.setattr("api.routes.reports.get_runs_dir", lambda: comparison_runs)
    response = client.post(
        "/api/reports/compare",
        json={"run_a_id": "run_a", "run_b_id": "run_missing"},
    )
    assert response.status_code == 404
    assert "Run not found" in response.get_json()["error"]


def test_compare_runs_same_id_returns_400(client, monkeypatch, comparison_runs: Path):
    monkeypatch.setattr("api.routes.reports.get_runs_dir", lambda: comparison_runs)
    response = client.post(
        "/api/reports/compare",
        json={"run_a_id": "run_a", "run_b_id": "run_a"},
    )
    assert response.status_code == 400
    assert "must be different" in response.get_json()["error"]
