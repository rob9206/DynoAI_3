# Testing Guide

This repo contains both unittest-based and pytest-style tests.

- Unittest suite (no network calls):
  - tests/test_xai_client.py
  - tests/test_xai_blueprint.py

- Pytest-dependent tests: additional files may import `pytest`. Installing pytest removes import errors during unittest discovery.

## Quick commands (Windows PowerShell)

```powershell
# Activate venv
 .\.venv\Scripts\Activate.ps1

# Install deps
 pip install -r requirements.txt

# Run only xAI tests (fast, mocked)
 python -m unittest -v tests/test_xai_client.py tests/test_xai_blueprint.py

# Or discover all tests (pytest is installed to avoid import errors)
 python -m unittest discover -s tests -p "test_*.py" -v
```

## Notes
- Network calls are mocked in the xAI tests; `XAI_API_KEY` isn’t required for test runs.
- For full pytest execution in the future, we can add a `pytest.ini` and run `pytest -q`.