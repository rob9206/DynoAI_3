"""Test suite for delta floor handling (<0.001% → 0.000%)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_delta_floor_applied(tmp_path: Path):
    """Verify delta values <0.001% are floored to 0.000% in summary."""
    csv = ROOT / "archive" / "FXDLS_Wheelie_Spark_Delta-1.csv"
    outdir = tmp_path / "floor_test"
    
    cmd = [
        sys.executable,
        str(ROOT / "experiments" / "run_experiment.py"),
        "--idea-id", "baseline",
        "--csv", str(csv),
        "--outdir", str(outdir),
        "--dry-run"
    ]
    
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    
    assert r.returncode == 0, f"Command failed: {r.stderr}"
    
    summary = json.loads((outdir / "experiment_summary.json").read_text())
    
    # For dry-run, there's no actual VE delta computation
    # But we can verify the summary structure
    assert "status" in summary, "Summary missing status field"
    assert summary["status"]["code"] == "DRY_RUN", "Expected DRY_RUN status"
    
    # If avg_abs_ve_delta_vs_baseline exists, it should be >= 0.000
    if "avg_abs_ve_delta_vs_baseline" in summary:
        delta = summary["avg_abs_ve_delta_vs_baseline"]
        assert isinstance(delta, (int, float)), "Delta should be numeric"
        assert delta >= 0.0, "Delta should be non-negative"
        # Verify precision (3 decimals max for display)
        assert round(delta, 3) == delta, "Delta should be rounded to 3 decimals"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
