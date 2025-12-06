"""Test suite for run_experiment.py path validation and safety checks."""

import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_outdir_created():
    """Verify output directory is created with nested paths."""
    csv = ROOT / "tables" / "WinPEP_Log_Sample.csv"

    if not csv.exists():
        pytest.skip(f"Test data file not found: {csv}")

    # Use project-local temp directory with nested structure
    test_id = uuid.uuid4().hex[:8]
    outdir = ROOT / "temp_selftest" / f"nested_{test_id}" / "x" / "y"
    base_outdir = ROOT / "temp_selftest" / f"nested_{test_id}"

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
        assert outdir.exists(), f"Output directory not created: {outdir}"
        assert (outdir / "experiment_summary.json").exists(), "Summary file missing"
    finally:
        # Clean up test output
        if base_outdir.exists():
            shutil.rmtree(base_outdir, ignore_errors=True)


def test_traversal_rejected():
    """Verify path traversal attempts are rejected."""
    csv = ROOT / "tables" / "WinPEP_Log_Sample.csv"

    if not csv.exists():
        pytest.skip(f"Test data file not found: {csv}")

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
    ]

    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))

    assert r.returncode != 0, "Path traversal should have been rejected"
    # Error is wrapped by argparse as "invalid _resolve_under_root value"
    # The underlying ValueError contains "Path escapes repo root" but argparse shows function name
    combined_output = (r.stderr + r.stdout).lower()
    assert "_resolve_under_root" in combined_output or "escapes" in combined_output, (
        f"Expected path validation error message, got: {r.stderr}"
    )


def test_invalid_idea_id():
    """Verify invalid idea-id is rejected."""
    csv = ROOT / "tables" / "WinPEP_Log_Sample.csv"

    if not csv.exists():
        pytest.skip(f"Test data file not found: {csv}")

    test_id = uuid.uuid4().hex[:8]
    outdir = ROOT / "temp_selftest" / f"invalid_{test_id}"

    try:
        cmd = [
            sys.executable,
            str(ROOT / "experiments" / "run_experiment.py"),
            "--idea-id",
            "nonexistent_kernel",
            "--csv",
            str(csv),
            "--outdir",
            str(outdir),
        ]

        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))

        assert r.returncode != 0, "Invalid idea-id should be rejected"
        # Error message is "Unknown idea id 'nonexistent_kernel'. Known: ..."
        assert "unknown idea" in (r.stderr + r.stdout).lower(), (
            "Expected 'Unknown idea' error"
        )
    finally:
        # Clean up test output if it was created
        if outdir.exists():
            shutil.rmtree(outdir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
