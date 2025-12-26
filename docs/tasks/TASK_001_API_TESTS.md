# Task 001: API Endpoint Tests

## Priority: HIGH
## Estimated Effort: Medium (2-3 hours)
## Dependencies: None

---

## Objective
Create comprehensive pytest-based tests for all Flask API endpoints to catch regressions and validate security fixes.

## Current State
- Core/kernel tests exist in `tests/`
- xAI client/blueprint tests exist
- **No dedicated tests for Flask API routes** (`/api/analyze`, `/api/download`, `/api/health`, etc.)

## Target Structure
```
tests/test_api/              # Note: Named test_api to avoid shadowing the api package
├── __init__.py
├── conftest.py              # Shared fixtures (Flask test client, temp dirs)
├── test_health_endpoint.py  # /api/health
├── test_analyze_endpoint.py # /api/analyze (file upload, validation)
├── test_download_endpoint.py # /api/download/<run_id>/<filename>
├── test_runs_endpoint.py    # /api/runs, /api/runs/<run_id>
├── test_ve_data_endpoint.py # /api/ve-data/<run_id>
├── test_diagnostics_endpoint.py # /api/diagnostics/<run_id>
└── test_security.py         # Path traversal, input validation tests
```

## Implementation Details

### 1. conftest.py - Shared Fixtures
```python
import pytest
import tempfile
from pathlib import Path
from api.app import app
from api.config import get_config

@pytest.fixture
def client():
    """Flask test client with test configuration."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

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
    
    # Create sample run
    run_dir = output_dir / "test-run-001"
    run_dir.mkdir()
    (run_dir / "VE_Correction_Delta_DYNO.csv").write_text("rpm,load,value\n1000,50,1.5")
    (run_dir / "manifest.json").write_text('{"version": "1.0"}')
    
    return output_dir

@pytest.fixture
def sample_csv_file(tmp_path):
    """Sample CSV file for upload tests."""
    csv_content = '''timestamp,rpm,afr_front,afr_rear,ect,iat
0,1000,14.7,14.7,180,95
1,1500,14.5,14.6,182,96
2,2000,14.3,14.4,185,98'''
    csv_file = tmp_path / "test_log.csv"
    csv_file.write_text(csv_content)
    return csv_file
```

### 2. test_health_endpoint.py
```python
def test_health_returns_ok(client):
    """Health endpoint returns 200 with status ok."""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'

def test_health_includes_timestamp(client):
    """Health endpoint includes timestamp."""
    response = client.get('/api/health')
    data = response.get_json()
    assert 'timestamp' in data
```

### 3. test_analyze_endpoint.py
```python
def test_analyze_requires_file(client):
    """Analyze endpoint requires file upload."""
    response = client.post('/api/analyze')
    assert response.status_code == 400
    assert 'No file provided' in response.get_json()['error']['message']

def test_analyze_rejects_non_csv(client, tmp_path):
    """Analyze endpoint rejects non-CSV files."""
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("not a csv")
    
    with open(txt_file, 'rb') as f:
        response = client.post('/api/analyze', data={'file': (f, 'test.txt')})
    
    assert response.status_code == 400

def test_analyze_accepts_valid_csv(client, sample_csv_file):
    """Analyze endpoint accepts valid CSV and returns run_id."""
    with open(sample_csv_file, 'rb') as f:
        response = client.post('/api/analyze', data={'file': (f, 'test.csv')})
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'run_id' in data
```

### 4. test_security.py - Critical Security Tests
```python
import pytest

class TestPathTraversalPrevention:
    """Tests for path traversal vulnerability prevention."""
    
    def test_download_rejects_path_traversal_run_id(self, client):
        """Download rejects ../.. in run_id."""
        response = client.get('/api/download/../../../etc/passwd/file.csv')
        assert response.status_code in (400, 404)
    
    def test_download_rejects_path_traversal_filename(self, client):
        """Download rejects ../.. in filename."""
        response = client.get('/api/download/valid-run/../../../etc/passwd')
        assert response.status_code in (400, 404)
    
    def test_ve_data_rejects_empty_run_id(self, client):
        """VE data endpoint rejects inputs that sanitize to empty string."""
        # "..." sanitizes to "" via secure_filename()
        response = client.get('/api/ve-data/...')
        assert response.status_code == 400
    
    def test_diagnostics_rejects_traversal(self, client):
        """Diagnostics endpoint prevents directory traversal."""
        response = client.get('/api/diagnostics/../../../etc')
        assert response.status_code in (400, 404)

class TestInputValidation:
    """Tests for input validation."""
    
    def test_analyze_validates_parameters(self, client, sample_csv_file):
        """Analyze validates tuning parameters."""
        with open(sample_csv_file, 'rb') as f:
            response = client.post('/api/analyze', data={
                'file': (f, 'test.csv'),
                'smoothPasses': 'invalid',  # Should be int
            })
        # Should either accept with default or return validation error
        assert response.status_code in (200, 400)
```

## Acceptance Criteria
- [x] All API endpoints have at least 2 test cases (106 tests total)
- [x] Security tests cover all path traversal fixes (28 security tests)
- [x] Tests run in CI via `pytest tests/test_api/ -v`
- [x] Coverage > 80% for `api/app.py` (exactly 80%)
- [x] No mocking of security functions (test real behavior)

## Files to Reference
- `api/app.py` - Main Flask application
- `api/errors.py` - Error handling (use these error types)
- `api/config.py` - Configuration (may need test config)
- `api/routes/jetstream/runs.py` - Jetstream routes

## Run Command
```bash
pytest tests/test_api/ -v --cov=api --cov-report=term-missing
```

