"""Test suite for VE grid bin alignment checks."""

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Import the grid reading function directly for unit testing
sys.path.insert(0, str(ROOT / "experiments"))


def test_grid_mismatch_hard_fails(tmp_path: Path):
    """Verify mismatched RPM/kPa grids cause hard failure via _assert_bin_alignment."""
    # Use test data from tables directory
    src = ROOT / "tables" / "FXDLS_Wheelie_Spark_Delta.csv"
    
    # Skip if test data doesn't exist
    if not src.exists():
        pytest.skip(f"Test data file not found: {src}")
    
    # Copy and modify headers to create mismatched grid
    with src.open() as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    if len(rows) < 2 or len(rows[0]) < 2:
        pytest.skip("Test data file has insufficient data")
    
    # Create modified version with shifted kPa bin
    modified_rows = [row.copy() for row in rows]
    original_header = modified_rows[0][1]
    modified_rows[0][1] = str(int(original_header) + 2)  # Shift kPa bin
    
    # Write both versions to temp files
    original_csv = tmp_path / "original.csv"
    modified_csv = tmp_path / "modified.csv"
    
    with original_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    with modified_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(modified_rows)
    
    # Import the bin alignment checker
    from run_experiment import _read_grid_csv, _assert_bin_alignment
    
    # Read both grids
    rpm_a, kpa_a, grid_a = _read_grid_csv(original_csv)
    rpm_b, kpa_b, grid_b = _read_grid_csv(modified_csv)
    
    # Verify that mismatched grids cause AssertionError
    with pytest.raises(AssertionError, match="RPM/kPa grid mismatch"):
        _assert_bin_alignment(rpm_a, kpa_a, rpm_b, kpa_b)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
