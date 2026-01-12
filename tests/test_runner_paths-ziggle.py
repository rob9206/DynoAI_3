"""Test suite for run_experiment.py path validation and safety checks."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_outdir_created(tmp_path: Path):
    """Verify output directory is created on dry-run."""
    outdir = tmp_path / "x" / "y"
    csv = ROOT / "archive" / "FXDLS_Wheelie_Spark_Delta-1.csv"

    cmd = [
        sys.executable,
        str(ROOT / "experiments" / "run_experiment.py"),
        "--idea-id",
        "baseline",
        "--csv",
        str(csv),
        "--outdir",
        str(outdir),
        "--dry-run",
    ]

    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))

    assert r.returncode == 0, f"Command failed: {r.stderr}"
    assert outdir.exists(), f"Output directory not created: {outdir}"
    assert (outdir / "kernel_fingerprint.txt").exists(), "Fingerprint file missing"
    assert (outdir / "experiment_summary.json").exists(), "Summary file missing"


def test_traversal_rejected(tmp_path: Path):
    """Verify path traversal attempts are rejected."""
    csv = ROOT / "archive" / "FXDLS_Wheelie_Spark_Delta-1.csv"
    # Try to escape root with relative path
    outdir = ROOT.parent / "evil_outside_root"

    cmd = [
        sys.executable,
        str(ROOT / "experiments" / "run_experiment.py"),
        "--idea-id",
        "baseline",
        "--csv",
        str(csv),
        "--outdir",
        str(outdir),
        "--dry-run",
    ]

    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))

    assert r.returncode != 0, "Path traversal should have been rejected"
    assert "escapes repo root" in (r.stderr + r.stdout), (
        "Expected 'escapes repo root' error message"
    )


def test_invalid_idea_id():
    """Verify invalid idea-id is rejected."""
    csv = ROOT / "archive" / "FXDLS_Wheelie_Spark_Delta-1.csv"
    outdir = ROOT / "experiments" / "test_invalid"

    cmd = [
        sys.executable,
        str(ROOT / "experiments" / "run_experiment.py"),
        "--idea-id",
        "nonexistent_kernel",
        "--csv",
        str(csv),
        "--outdir",
        str(outdir),
        "--dry-run",
    ]

    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))

    assert r.returncode != 0, "Invalid idea-id should be rejected"
    assert "Unknown idea-id" in (r.stderr + r.stdout), (
        "Expected 'Unknown idea-id' error"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
