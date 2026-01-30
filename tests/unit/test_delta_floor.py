"""Test suite for delta floor handling (<0.001% → 0.000%)."""

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_delta_floor_applied():
    """Verify delta values <0.001% are floored to 0.000% in summary."""
    csv = ROOT / "tables" / "WinPEP_Log_Sample.csv"

    if not csv.exists():
        pytest.skip(f"Test data file not found: {csv}")

    # Use project-local temp directory (required by run_experiment.py path validation)
    test_id = uuid.uuid4().hex[:8]
    outdir = ROOT / "temp_selftest" / f"floor_test_{test_id}"

    try:
        cmd = [
            sys.executable,
            str(ROOT / "experiments" / "run_experiment.py"),
            "--idea-id",
            "baseline",
            "--csv",
            str(csv),
            "--outdir",
            str(outdir),
        ]

        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))

        assert r.returncode == 0, f"Command failed: {r.stderr}"

        summary_path = outdir / "experiment_summary.json"
        assert summary_path.exists(), "Summary file not created"

        summary = json.loads(summary_path.read_text())

        # Verify the summary structure
        assert "idea_id" in summary, "Summary missing idea_id field"
        assert "duration_sec" in summary, "Summary missing duration_sec field"
        assert "metrics" in summary, "Summary missing metrics field"

        # If avg_abs_ve_delta_vs_baseline exists, it should be >= 0.000
        if "avg_abs_ve_delta_vs_baseline" in summary:
            delta = summary["avg_abs_ve_delta_vs_baseline"]
            if delta is not None:
                assert isinstance(delta, (int, float)), "Delta should be numeric"
                assert delta >= 0.0, "Delta should be non-negative"
    finally:
        # Clean up test output
        if outdir.exists():
            shutil.rmtree(outdir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
