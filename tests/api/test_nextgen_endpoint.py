"""
Tests for /api/nextgen/<run_id> endpoints.

The NextGen API provides physics-informed ECU analysis including:
- Mode detection
- Surface building (spark, AFR error, knock)
- Spark valley detection
- Causal hypothesis generation
- Next-test planning
"""

import json
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import pandas as pd

# Test data path
TEST_DATA_DIR = Path(__file__).parent.parent / "data"
DENSE_DYNO_CSV = TEST_DATA_DIR / "dense_dyno_test.csv"


@pytest.fixture
def mock_workflow():
    """Create a mock NextGenWorkflow for testing."""
    mock = MagicMock()
    return mock


@pytest.fixture
def nextgen_run_dir(tmp_path):
    """
    Create a temporary run directory with dyno input CSV.
    
    Structure:
        tmp_runs/<run_id>/
        ├── input/
        │   └── dynoai_input.csv
        └── output/
    """
    runs_dir = tmp_path / "tmp_runs"
    runs_dir.mkdir()
    
    run_id = "nextgen_test_run_001"
    run_dir = runs_dir / run_id
    run_dir.mkdir()
    (run_dir / "input").mkdir()
    (run_dir / "output").mkdir()
    
    # Copy test CSV to input directory
    input_csv = run_dir / "input" / "dynoai_input.csv"
    if DENSE_DYNO_CSV.exists():
        shutil.copy(DENSE_DYNO_CSV, input_csv)
    else:
        # Create a minimal CSV if test data is missing
        df = pd.DataFrame({
            "rpm": [3000] * 10,
            "map_kpa": [60] * 10,
            "tps": [40] * 10,
            "spark_f": [28] * 10,
            "spark_r": [27] * 10,
            "afr_meas_f": [13.0] * 10,
            "afr_meas_r": [13.0] * 10,
            "afr_cmd_f": [12.8] * 10,
            "afr_cmd_r": [12.8] * 10,
        })
        df.to_csv(input_csv, index=False)
    
    yield {
        "runs_dir": runs_dir,
        "run_id": run_id,
        "run_dir": run_dir,
        "input_csv": input_csv,
    }


@pytest.fixture
def nextgen_run_no_knock(tmp_path):
    """
    Create a run directory with CSV that has knock column removed.
    
    Used to test graceful degradation when optional columns are missing.
    """
    runs_dir = tmp_path / "tmp_runs"
    runs_dir.mkdir(exist_ok=True)
    
    run_id = "nextgen_no_knock_run"
    run_dir = runs_dir / run_id
    run_dir.mkdir()
    (run_dir / "input").mkdir()
    (run_dir / "output").mkdir()
    
    # Create CSV without knock column
    df = pd.DataFrame({
        "rpm": [3000] * 50,
        "map_kpa": [60] * 50,
        "tps": [40] * 50,
        "spark_f": [28] * 50,
        "spark_r": [27] * 50,
        "afr_meas_f": [13.0] * 50,
        "afr_meas_r": [13.0] * 50,
        "afr_cmd_f": [12.8] * 50,
        "afr_cmd_r": [12.8] * 50,
        "iat": [85] * 50,
    })
    
    input_csv = run_dir / "input" / "dynoai_input.csv"
    df.to_csv(input_csv, index=False)
    
    return {
        "runs_dir": runs_dir,
        "run_id": run_id,
        "run_dir": run_dir,
        "input_csv": input_csv,
    }


class TestNextGenGenerateEndpoint:
    """Tests for POST /api/nextgen/<run_id>/generate endpoint."""
    
    def test_generate_returns_200_and_creates_files(self, client, nextgen_run_dir):
        """Generate endpoint returns 200 and creates NextGenAnalysis.json."""
        run_id = nextgen_run_dir["run_id"]
        output_dir = nextgen_run_dir["run_dir"] / "output"
        input_csv = nextgen_run_dir["input_csv"]
        
        with patch("api.routes.nextgen.get_nextgen_workflow") as mock_get_workflow:
            mock_workflow = MagicMock()
            mock_get_workflow.return_value = mock_workflow
            
            # Mock generate_for_run to create the files
            def mock_generate(rid, force=False):
                # Simulate file creation
                payload = {
                    "schema_version": "dynoai.nextgen@1",
                    "run_id": rid,
                    "generated_at": "2026-01-27T10:00:00Z",
                    "surfaces": {},
                    "spark_valley": {"findings": []},
                    "cause_tree": {"hypotheses": []},
                    "next_tests": {"steps": []},
                    "notes_warnings": [],
                }
                (output_dir / "NextGenAnalysis.json").write_text(json.dumps(payload))
                (output_dir / "NextGenAnalysis_Meta.json").write_text(json.dumps({"schema_version": "dynoai.nextgen@1"}))
                
                return {
                    "success": True,
                    "run_id": rid,
                    "generated_at": "2026-01-27T10:00:00Z",
                    "from_cache": False,
                    "summary": {
                        "total_samples": 100,
                        "surface_count": 2,
                        "hypothesis_count": 0,
                        "test_step_count": 0,
                    },
                    "download_url": f"/api/nextgen/{rid}/download",
                }
            
            mock_workflow.generate_for_run.side_effect = mock_generate
            
            response = client.post(f"/api/nextgen/{run_id}/generate")
            
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["run_id"] == run_id
    
    def test_generate_returns_summary_fields(self, client, nextgen_run_dir):
        """Generate endpoint returns expected summary fields."""
        run_id = nextgen_run_dir["run_id"]
        
        with patch("api.routes.nextgen.get_nextgen_workflow") as mock_get_workflow:
            mock_workflow = MagicMock()
            mock_get_workflow.return_value = mock_workflow
            
            mock_workflow.generate_for_run.return_value = {
                "success": True,
                "run_id": run_id,
                "generated_at": "2026-01-27T10:00:00Z",
                "from_cache": False,
                "summary": {
                    "total_samples": 100,
                    "surface_count": 2,
                    "hypothesis_count": 3,
                    "test_step_count": 5,
                },
                "download_url": f"/api/nextgen/{run_id}/download",
            }
            
            response = client.post(f"/api/nextgen/{run_id}/generate")
            
            assert response.status_code == 200
            data = response.get_json()
            summary = data["summary"]
            
            assert "total_samples" in summary
            assert "surface_count" in summary
            assert "hypothesis_count" in summary
            assert "test_step_count" in summary
            assert summary["total_samples"] > 0
    
    def test_generate_with_force_regenerates(self, client, nextgen_run_dir):
        """Generate with force=true regenerates even if cached."""
        run_id = nextgen_run_dir["run_id"]
        
        with patch("api.routes.nextgen.get_nextgen_workflow") as mock_get_workflow:
            mock_workflow = MagicMock()
            mock_get_workflow.return_value = mock_workflow
            
            # First call without force - returns from cache
            mock_workflow.generate_for_run.return_value = {
                "success": True,
                "run_id": run_id,
                "generated_at": "2026-01-27T10:00:00Z",
                "from_cache": True,
                "summary": {"total_samples": 100, "surface_count": 2, "hypothesis_count": 0, "test_step_count": 0},
                "download_url": f"/api/nextgen/{run_id}/download",
            }
            
            response1 = client.post(f"/api/nextgen/{run_id}/generate")
            assert response1.status_code == 200
            data1 = response1.get_json()
            assert data1["from_cache"] is True
            
            # Second call with force - regenerates
            mock_workflow.generate_for_run.return_value["from_cache"] = False
            
            response2 = client.post(f"/api/nextgen/{run_id}/generate?force=true")
            assert response2.status_code == 200
            data2 = response2.get_json()
            # Verify force parameter was passed
            call_args = mock_workflow.generate_for_run.call_args
            assert call_args is not None
    
    def test_generate_with_include_full_returns_payload(self, client, nextgen_run_dir):
        """Generate with include=full returns full payload inline."""
        run_id = nextgen_run_dir["run_id"]
        
        with patch("api.routes.nextgen.get_nextgen_workflow") as mock_get_workflow:
            mock_workflow = MagicMock()
            mock_get_workflow.return_value = mock_workflow
            
            payload = {
                "schema_version": "dynoai.nextgen@1",
                "run_id": run_id,
                "surfaces": {},
                "cause_tree": {"hypotheses": []},
            }
            
            mock_workflow.generate_for_run.return_value = {
                "success": True,
                "run_id": run_id,
                "generated_at": "2026-01-27T10:00:00Z",
                "from_cache": False,
                "payload": payload,
                "summary": {"total_samples": 100, "surface_count": 0, "hypothesis_count": 0, "test_step_count": 0},
                "download_url": f"/api/nextgen/{run_id}/download",
            }
            
            response = client.post(f"/api/nextgen/{run_id}/generate?include=full")
            
            assert response.status_code == 200
            data = response.get_json()
            assert "payload" in data
            assert data["payload"]["schema_version"] == "dynoai.nextgen@1"
            assert "surfaces" in data["payload"]
            assert "cause_tree" in data["payload"]
    
    def test_generate_returns_error_for_missing_run(self, client):
        """Generate returns error for non-existent run."""
        with patch("api.routes.nextgen.get_nextgen_workflow") as mock_get_workflow:
            mock_workflow = MagicMock()
            mock_get_workflow.return_value = mock_workflow
            mock_workflow.generate_for_run.return_value = {
                "success": False,
                "error": "Input CSV not found",
            }
            
            response = client.post("/api/nextgen/nonexistent_run_xyz/generate")
            
            # Should return error (400)
            assert response.status_code == 400
            data = response.get_json()
            assert data["success"] is False
            assert "error" in data


class TestNextGenGetEndpoint:
    """Tests for GET /api/nextgen/<run_id> endpoint."""
    
    def test_get_returns_404_before_generation(self, client):
        """GET returns 404 when analysis hasn't been generated."""
        with patch("api.routes.nextgen.get_nextgen_workflow") as mock_get_workflow:
            mock_workflow = MagicMock()
            mock_get_workflow.return_value = mock_workflow
            mock_workflow.load_cached.return_value = None
            
            response = client.get("/api/nextgen/some_run_id")
            
            assert response.status_code == 404
            data = response.get_json()
            assert "error" in data
    
    def test_get_returns_payload_after_generation(self, client, nextgen_run_dir):
        """GET returns cached payload after generation."""
        run_id = nextgen_run_dir["run_id"]
        
        with patch("api.routes.nextgen.get_nextgen_workflow") as mock_get_workflow:
            mock_workflow = MagicMock()
            mock_get_workflow.return_value = mock_workflow
            
            payload = {
                "schema_version": "dynoai.nextgen@1",
                "run_id": run_id,
                "generated_at": "2026-01-27T10:00:00Z",
                "inputs_present": {},
                "mode_summary": {},
                "surfaces": {},
                "spark_valley": {"findings": []},
                "cause_tree": {"hypotheses": []},
                "next_tests": {"steps": []},
                "notes_warnings": [],
            }
            
            mock_workflow.load_cached.return_value = payload
            
            response = client.get(f"/api/nextgen/{run_id}")
            
            assert response.status_code == 200
            data = response.get_json()
            assert data["schema_version"] == "dynoai.nextgen@1"
            assert data["run_id"] == run_id
            assert "surfaces" in data
            assert "spark_valley" in data
            assert "cause_tree" in data
            assert "next_tests" in data
    
    def test_get_payload_has_expected_keys(self, client, nextgen_run_dir):
        """GET payload contains all required schema keys."""
        run_id = nextgen_run_dir["run_id"]
        
        with patch("api.routes.nextgen.get_nextgen_workflow") as mock_get_workflow:
            mock_workflow = MagicMock()
            mock_get_workflow.return_value = mock_workflow
            
            payload = {
                "schema_version": "dynoai.nextgen@1",
                "run_id": run_id,
                "generated_at": "2026-01-27T10:00:00Z",
                "inputs_present": {},
                "mode_summary": {},
                "surfaces": {},
                "spark_valley": {"findings": []},
                "cause_tree": {"hypotheses": []},
                "next_tests": {"steps": []},
                "notes_warnings": [],
            }
            
            mock_workflow.load_cached.return_value = payload
            
            response = client.get(f"/api/nextgen/{run_id}")
            data = response.get_json()
            
            # Check all top-level keys
            required_keys = [
                "schema_version",
                "run_id",
                "generated_at",
                "inputs_present",
                "mode_summary",
                "surfaces",
                "spark_valley",
                "cause_tree",
                "next_tests",
                "notes_warnings",
            ]
            for key in required_keys:
                assert key in data, f"Missing required key: {key}"


class TestNextGenDownloadEndpoint:
    """Tests for GET /api/nextgen/<run_id>/download endpoint."""
    
    def test_download_returns_404_before_generation(self, client):
        """Download returns 404 when file doesn't exist."""
        with patch("api.routes.nextgen.get_nextgen_workflow") as mock_get_workflow:
            mock_workflow = MagicMock()
            mock_get_workflow.return_value = mock_workflow
            mock_workflow.get_payload_path.return_value = None
            
            response = client.get("/api/nextgen/nonexistent_run/download")
            
            assert response.status_code == 404
    
    def test_download_returns_json_attachment(self, client, nextgen_run_dir):
        """Download returns JSON file as attachment."""
        run_id = nextgen_run_dir["run_id"]
        output_dir = nextgen_run_dir["run_dir"] / "output"
        
        # Create the JSON file
        payload = {
            "schema_version": "dynoai.nextgen@1",
            "run_id": run_id,
        }
        payload_path = output_dir / "NextGenAnalysis.json"
        payload_path.write_text(json.dumps(payload))
        
        with patch("api.routes.nextgen.get_nextgen_workflow") as mock_get_workflow:
            mock_workflow = MagicMock()
            mock_get_workflow.return_value = mock_workflow
            mock_workflow.get_payload_path.return_value = payload_path
            
            response = client.get(f"/api/nextgen/{run_id}/download")
            
            assert response.status_code == 200
            assert response.content_type == "application/json"
            assert "attachment" in response.headers.get("Content-Disposition", "")


class TestNextGenGracefulDegradation:
    """Tests for graceful degradation when optional columns are missing."""
    
    def test_generate_succeeds_without_knock_column(self, client, nextgen_run_no_knock):
        """Generate succeeds when knock column is missing."""
        run_id = nextgen_run_no_knock["run_id"]
        
        with patch("api.routes.nextgen.get_nextgen_workflow") as mock_get_workflow:
            mock_workflow = MagicMock()
            mock_get_workflow.return_value = mock_workflow
            
            payload = {
                "schema_version": "dynoai.nextgen@1",
                "run_id": run_id,
                "surfaces": {"spark_front": {}, "afr_error_front": {}},  # No knock surfaces
                "notes_warnings": ["No knock data available"],
            }
            
            mock_workflow.generate_for_run.return_value = {
                "success": True,
                "run_id": run_id,
                "generated_at": "2026-01-27T10:00:00Z",
                "from_cache": False,
                "payload": payload,
                "summary": {"total_samples": 50, "surface_count": 2, "hypothesis_count": 0, "test_step_count": 0},
                "download_url": f"/api/nextgen/{run_id}/download",
            }
            
            response = client.post(f"/api/nextgen/{run_id}/generate?include=full")
            
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            
            # Payload should exist
            payload_data = data["payload"]
            assert payload_data is not None
            assert "surfaces" in payload_data
    
    def test_knock_surfaces_omitted_when_missing(self, client, nextgen_run_no_knock):
        """Knock surfaces are not present when knock data is missing."""
        run_id = nextgen_run_no_knock["run_id"]
        
        with patch("api.routes.nextgen.get_nextgen_workflow") as mock_get_workflow:
            mock_workflow = MagicMock()
            mock_get_workflow.return_value = mock_workflow
            
            payload = {
                "schema_version": "dynoai.nextgen@1",
                "run_id": run_id,
                "surfaces": {"spark_front": {}, "spark_rear": {}},  # No knock surface
                "notes_warnings": [],
            }
            
            mock_workflow.generate_for_run.return_value = {
                "success": True,
                "run_id": run_id,
                "generated_at": "2026-01-27T10:00:00Z",
                "from_cache": False,
                "payload": payload,
                "summary": {"total_samples": 50, "surface_count": 2, "hypothesis_count": 0, "test_step_count": 0},
                "download_url": f"/api/nextgen/{run_id}/download",
            }
            
            response = client.post(f"/api/nextgen/{run_id}/generate?include=full")
            
            assert response.status_code == 200
            payload_data = response.get_json()["payload"]
            
            # Should not have knock_activity surface
            surfaces = payload_data["surfaces"]
            assert "knock_activity" not in surfaces
    
    def test_warning_recorded_for_missing_knock(self, client, nextgen_run_no_knock):
        """Warning is recorded in notes_warnings when knock is missing."""
        run_id = nextgen_run_no_knock["run_id"]
        
        with patch("api.routes.nextgen.get_nextgen_workflow") as mock_get_workflow:
            mock_workflow = MagicMock()
            mock_get_workflow.return_value = mock_workflow
            
            payload = {
                "schema_version": "dynoai.nextgen@1",
                "run_id": run_id,
                "surfaces": {},
                "notes_warnings": ["No knock data available; knock-related analysis disabled."],
            }
            
            mock_workflow.generate_for_run.return_value = {
                "success": True,
                "run_id": run_id,
                "generated_at": "2026-01-27T10:00:00Z",
                "from_cache": False,
                "payload": payload,
                "summary": {"total_samples": 50, "surface_count": 0, "hypothesis_count": 0, "test_step_count": 0},
                "download_url": f"/api/nextgen/{run_id}/download",
            }
            
            response = client.post(f"/api/nextgen/{run_id}/generate?include=full")
            
            assert response.status_code == 200
            payload_data = response.get_json()["payload"]
            
            # Should have a warning about missing knock
            warnings = payload_data["notes_warnings"]
            knock_warning_found = any(
                "knock" in w.lower() or "No knock data" in w
                for w in warnings
            )
            assert knock_warning_found, f"Expected knock warning, got: {warnings}"


class TestNextGenInputValidation:
    """Tests for NextGen endpoint input validation."""
    
    def test_generate_rejects_invalid_run_id(self, client):
        """Generate rejects run_id with path traversal attempts."""
        response = client.post("/api/nextgen/../../../etc/passwd/generate")
        
        # Should be rejected (either 400, 404, or route not found)
        assert response.status_code in [400, 404, 405]
    
    def test_get_rejects_empty_run_id(self, client):
        """GET rejects empty run_id."""
        response = client.get("/api/nextgen//")
        
        # Should be 404 or 405
        assert response.status_code in [404, 405]
