"""Test suite for kernel fingerprint generation."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_fingerprint_contents(tmp_path: Path):
    """Verify fingerprint file contains correct module/function/params."""
    csv = ROOT / "archive" / "FXDLS_Wheelie_Spark_Delta-1.csv"
    outdir = tmp_path / "fp_test"
    
    cmd = [
        sys.executable,
        str(ROOT / "experiments" / "run_experiment.py"),
        "--idea-id", "k2_coverage_adaptive_v1",
        "--csv", str(csv),
        "--outdir", str(outdir),
        "--dry-run"
    ]
    
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    
    assert r.returncode == 0, f"Command failed: {r.stderr}"
    
    fp = (outdir / "kernel_fingerprint.txt").read_text()
    assert "module=" in fp, "Fingerprint missing module field"
    assert "function=" in fp, "Fingerprint missing function field"
    assert "params=" in fp, "Fingerprint missing params field"
    assert "k2_coverage_adaptive_v1" in fp, "Fingerprint missing kernel name"
    assert "kernel_smooth" in fp, "Fingerprint missing function name"


def test_fingerprint_all_kernels(tmp_path: Path):
    """Verify fingerprints can be generated for all registered kernels."""
    csv = ROOT / "archive" / "FXDLS_Wheelie_Spark_Delta-1.csv"
    kernels = ["baseline", "k1", "k2", "k3", "kernel_weighted_v1", "kernel_knock_aware_v1"]
    
    for kernel_id in kernels:
        outdir = tmp_path / f"fp_{kernel_id}"
        
        cmd = [
            sys.executable,
            str(ROOT / "experiments" / "run_experiment.py"),
            "--idea-id", kernel_id,
            "--csv", str(csv),
            "--outdir", str(outdir),
            "--dry-run"
        ]
        
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
        
        assert r.returncode == 0, f"Failed for kernel '{kernel_id}': {r.stderr}"
        assert (outdir / "kernel_fingerprint.txt").exists(), f"No fingerprint for '{kernel_id}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
