#!/usr/bin/env python
"""Compute avg_abs_delta between two VE correction grids for experiment comparison."""
from __future__ import annotations

import csv
import sys
from pathlib import Path


def load_ve_grid(csv_path: Path) -> tuple[list[int], list[int], list[list[float | None]]]:
    """Load VE correction grid from CSV."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        kpa_bins = [int(h.strip("'")) for h in header[1:]]
        
        rpm_bins: list[int] = []
        grid: list[list[float | None]] = []
        
        for row in reader:
            rpm_bins.append(int(row[0].strip("'")))
            ve_row: list[float | None] = []
            for cell in row[1:]:
                cell = cell.strip().strip("'")
                if cell == "":
                    ve_row.append(None)
                else:
                    try:
                        ve_row.append(float(cell))
                    except ValueError:
                        ve_row.append(None)
            grid.append(ve_row)
    
    return rpm_bins, kpa_bins, grid


def compute_avg_abs_delta(
    baseline_path: Path, test_path: Path
) -> tuple[float | None, int, int]:
    """
    Compute average absolute delta between two grids.
    
    Returns:
        (avg_abs_delta, overlapping_cells, total_cells)
    """
    try:
        b_rpm, b_kpa, b_grid = load_ve_grid(baseline_path)
        t_rpm, t_kpa, t_grid = load_ve_grid(test_path)
    except Exception as e:
        print(f"Error loading grids: {e}", file=sys.stderr)
        return None, 0, 0
    
    if b_rpm != t_rpm or b_kpa != t_kpa:
        print("Grid dimension mismatch!", file=sys.stderr)
        return None, 0, 0
    
    total_sum = 0.0
    count = 0
    total_cells = len(b_rpm) * len(b_kpa)
    
    for ri in range(len(b_rpm)):
        for ki in range(len(b_kpa)):
            b_val = b_grid[ri][ki]
            t_val = t_grid[ri][ki]
            if b_val is not None and t_val is not None:
                total_sum += abs(t_val - b_val)
                count += 1
    
    avg = (total_sum / count) if count > 0 else None
    return avg, count, total_cells


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python compare_ve_grids.py baseline.csv test.csv")
        sys.exit(1)
    
    baseline = Path(sys.argv[1])
    test = Path(sys.argv[2])
    
    avg_delta, overlapping, total = compute_avg_abs_delta(baseline, test)
    
    if avg_delta is not None:
        print(f"avg_abs_delta: {avg_delta:.4f}%")
        print(f"overlapping cells: {overlapping}/{total} ({100*overlapping/total:.1f}%)")
    else:
        print("Could not compute delta (no overlapping data)")
        sys.exit(1)
