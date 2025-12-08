"""
Shared pytest fixtures for API endpoint tests.

Provides Flask test client, temporary directories, and sample data fixtures.
"""

import json
import os
import sys
from pathlib import Path

# Ensure the project root is in the path for imports BEFORE any other imports
PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Set test environment variables BEFORE importing app
os.environ["DYNOAI_DEBUG"] = "false"
os.environ["JETSTREAM_STUB_MODE"] = "true"
os.environ["JETSTREAM_ENABLED"] = "false"

import pytest


@pytest.fixture
def app():
    """Create Flask app instance for testing."""
    from api.app import app as flask_app

    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False

    yield flask_app


@pytest.fixture
def client(app):
    """Flask test client with test configuration."""
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def temp_upload_dir(tmp_path):
    """Temporary upload directory."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    return upload_dir


@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary output directory with sample run data."""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    run_dir = output_dir / "test-run-001"
    run_dir.mkdir()

    ve_content = """RPM,20,40,60,80,100
1000,+1.5,+2.0,+1.8,+1.2,+0.5
2000,+2.0,+2.5,+2.2,+1.5,+0.8
3000,+1.8,+2.2,+2.0,+1.3,+0.6
4000,+1.2,+1.5,+1.3,+0.8,+0.3"""
    (run_dir / "VE_Correction_Delta_DYNO.csv").write_text(ve_content)

    manifest = {
        "version": "1.0",
        "timing": {"start": "2025-12-05T10:00:00Z"},
        "input": {"path": "test_log.csv"},
        "stats": {"rows_read": 100, "front_accepted": 50, "rear_accepted": 40},
        "outputs": [
            {"name": "VE_Correction_Delta_DYNO.csv", "path": "VE_Correction_Delta_DYNO.csv"}
        ],
        "config": {"args": {"smooth_passes": 2}},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))

    (run_dir / "Diagnostics_Report.txt").write_text(
        "Diagnostics Report\n==================\nAll systems nominal."
    )
    (run_dir / "Anomaly_Hypotheses.json").write_text(
        json.dumps({"anomalies": [], "hypotheses": []})
    )

    return output_dir


@pytest.fixture
def sample_csv_file(tmp_path):
    """Sample CSV file for upload tests."""
    csv_content = """timestamp,rpm,afr_front,afr_rear,ect,iat
0,1000,14.7,14.7,180,95
1,1500,14.5,14.6,182,96
2,2000,14.3,14.4,185,98
3,2500,14.2,14.3,187,99
4,3000,14.1,14.2,190,100"""
    csv_file = tmp_path / "test_log.csv"
    csv_file.write_text(csv_content)
    return csv_file


@pytest.fixture
def invalid_file(tmp_path):
    """Invalid file for rejection tests."""
    exe_file = tmp_path / "malicious.exe"
    exe_file.write_bytes(b"\x00\x01\x02\x03")
    return exe_file


@pytest.fixture
def sample_txt_file(tmp_path):
    """Sample TXT file (allowed extension) for upload tests."""
    txt_content = """timestamp,rpm,afr_front,afr_rear,ect,iat
0,1000,14.7,14.7,180,95
1,1500,14.5,14.6,182,96"""
    txt_file = tmp_path / "test_log.txt"
    txt_file.write_text(txt_content)
    return txt_file


@pytest.fixture
def mock_output_folder(tmp_path):
    """
    Mock the output folder configuration to use a temporary directory.
    Creates test run data in the temporary folder.
    """
    from api.config import get_config

    config = get_config()

    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    run_id = "test-run-abc123"
    run_dir = output_dir / run_id
    run_dir.mkdir()

    ve_content = """RPM,20,40,60,80,100
1000,+1.5,+2.0,+1.8,+1.2,+0.5
2000,+2.0,+2.5,+2.2,+1.5,+0.8
3000,+1.8,+2.2,+2.0,+1.3,+0.6
4000,+1.2,+1.5,+1.3,+0.8,+0.3"""
    (run_dir / "VE_Correction_Delta_DYNO.csv").write_text(ve_content)

    manifest = {
        "version": "1.0",
        "timing": {"start": "2025-12-05T10:00:00Z"},
        "input": {"path": "test_log.csv"},
        "stats": {"rows_read": 100, "front_accepted": 50, "rear_accepted": 40},
        "outputs": [
            {"name": "VE_Correction_Delta_DYNO.csv", "path": "VE_Correction_Delta_DYNO.csv"}
        ],
        "config": {"args": {"smooth_passes": 2}},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))

    (run_dir / "Diagnostics_Report.txt").write_text(
        "Diagnostics Report\n==================\nAll systems nominal."
    )
    (run_dir / "Anomaly_Hypotheses.json").write_text(
        json.dumps({"anomalies": [], "hypotheses": []})
    )

    coverage_content = """RPM,20,40,60,80,100
1000,5,10,8,3,1
2000,8,15,12,6,2
3000,6,12,10,4,1
4000,3,6,5,2,0"""
    (run_dir / "Coverage_Front.csv").write_text(coverage_content)
    (run_dir / "Coverage_Rear.csv").write_text(coverage_content)

    original_output_folder = config.storage.output_folder
    config.storage.output_folder = output_dir

    yield {"output_dir": output_dir, "run_id": run_id, "run_dir": run_dir}

    config.storage.output_folder = original_output_folder
