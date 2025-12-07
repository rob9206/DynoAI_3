"""Test suite for kernel fingerprint generation."""

import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_fingerprint_contents():
    """Verify fingerprint file contains correct module/function/params."""
    csv = ROOT / "tables" / "WinPEP_Log_Sample.csv"

    if not csv.exists():
        pytest.skip(f"Test data file not found: {csv}")

    # Use project-local temp directory (required by run_experiment.py path validation)
    test_id = uuid.uuid4().hex[:8]
    outdir = ROOT / "temp_selftest" / f"fp_test_{test_id}"

    try:
        cmd = [
            sys.executable,
            str(ROOT / "experiments" / "run_experiment.py"),
            "--idea-id",
            "k2_coverage_adaptive_v1",
            "--csv",
            str(csv),
            "--outdir",
            str(outdir),
        ]

        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))

        assert r.returncode == 0, f"Command failed: {r.stderr}"

        fp_path = outdir / "kernel_fingerprint.txt"
        assert fp_path.exists(), "Fingerprint file not created"

        fp = fp_path.read_text()
        # Fingerprint format is: "module:function param1=val1, param2=val2"
        assert "k2_coverage_adaptive_v1" in fp, "Fingerprint missing kernel name"
        assert "kernel_smooth" in fp, "Fingerprint missing function name"
    finally:
        # Clean up test output
        if outdir.exists():
            shutil.rmtree(outdir, ignore_errors=True)


def test_fingerprint_all_kernels():
    """Verify fingerprints can be generated for all registered kernels."""
    csv = ROOT / "tables" / "WinPEP_Log_Sample.csv"

    if not csv.exists():
        pytest.skip(f"Test data file not found: {csv}")

    # Only test kernels that are actually registered in run_experiment.py IDEAS dict
    # Note: k3 (bilateral) has a different signature and is excluded from this test
    kernels = ["baseline", "k1", "k2"]

    test_id = uuid.uuid4().hex[:8]
    base_outdir = ROOT / "temp_selftest" / f"fp_all_{test_id}"

    try:
        for kernel_id in kernels:
            outdir = base_outdir / f"fp_{kernel_id}"

            cmd = [
                sys.executable,
                str(ROOT / "experiments" / "run_experiment.py"),
                "--idea-id",
                kernel_id,
                "--csv",
                str(csv),
                "--outdir",
                str(outdir),
            ]

            r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))

            assert r.returncode == 0, f"Failed for kernel '{kernel_id}': {r.stderr}"

            # baseline doesn't create a fingerprint (no kernel loaded)
            if kernel_id != "baseline":
                assert (outdir / "kernel_fingerprint.txt").exists(), (
                    f"No fingerprint for '{kernel_id}'"
                )
    finally:
        # Clean up test output
        if base_outdir.exists():
            shutil.rmtree(base_outdir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
