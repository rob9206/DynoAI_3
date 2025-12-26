#!/usr/bin/env python3
"""
Baseline Dataset Generator for DynoAI Kernel Testing

Generates frozen baseline datasets for continuous kernel testing:
- Dense baseline: High coverage, realistic AFR errors
- Sparse baseline: Low coverage, minimal data points

These serve as reference for all future kernel comparisons.
"""

import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dynoai.core.io_contracts import sanitize_csv_cell

PY = sys.executable
TOOL = ROOT / "ai_tuner_toolkit_dyno_v1_2.py"

def make_dense_baseline_csv(path: Path, rows: int = 12000, fs_hz: int = 20) -> None:
    """
    Generate dense baseline dataset with high coverage across all bins.

    Features:
    - 12,000 rows (10 minutes at 20Hz)
    - Comprehensive RPM/MAP coverage (1500-5500 RPM, 35-95 kPa)
    - Realistic AFR errors (±8-9%) for significant corrections
    - Good knock distribution for testing
    """
    import csv
    rnd = random.Random(42)  # Fixed seed for reproducibility
    dt = 1.0 / fs_hz
    t = 0.0

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        headers = ["rpm","map_kpa","torque","ve_f","ve_r","spark_f","spark_r",
                   "afr_cmd_f","afr_cmd_r","afr_meas_f","afr_meas_r","iat","knock","vbatt","tps"]
        w.writerow([sanitize_csv_cell(h) for h in headers])

        for _ in range(rows):
            t += dt

            # Comprehensive RPM sweep: 1500-5500 RPM
            rpm = 2500 + 1500 * math.sin(2*math.pi*t/30) + 500 * math.sin(2*math.pi*t/7)
            rpm = max(1500, min(5500, rpm))

            # Full MAP range: 35-95 kPa
            mapk = 65 + 30 * math.sin(2*math.pi*t/25) + 15 * math.sin(2*math.pi*t/11)
            mapk = max(35, min(95, mapk))

            afr = 13.0
            # Large AFR errors for significant corrections
            afr_error_pct_f = rnd.gauss(0, 0.08) + 0.03 * math.sin(2*math.pi*(t-0.18)/9)
            afr_error_pct_r = rnd.gauss(0, 0.09) + 0.035 * math.sin(2*math.pi*(t-0.20)/9.5)

            afr_meas_f = afr * (1 + afr_error_pct_f)
            afr_meas_r = afr * (1 + afr_error_pct_r)

            torque = 80 + 10*math.sin(2*math.pi*t/8) + rnd.gauss(0, 5)
            torque = max(30, min(150, torque))

            iat = 105 + 6*math.sin(2*math.pi*t/45) + rnd.gauss(0, 3)
            iat = max(70, min(160, iat))

            # Distributed knock events
            knock = 1 if (int(t*fs_hz) % 800 == 0 and mapk > 85 and rpm > 3500) else 0

            vbatt = 13.9 + rnd.gauss(0, 0.02)
            tps = 20 + 5*math.sin(2*math.pi*t/6) + rnd.gauss(0, 2)

            row_data = [
                round(rpm,2), round(mapk,2), round(torque,2),
                120,121,24,22, afr, afr, round(afr_meas_f,2), round(afr_meas_r,2),
                round(iat,1), knock, round(vbatt,2), round(tps,1)
            ]
            row_data_str = [str(sanitize_csv_cell(c)) for c in row_data]
            w.writerow(row_data_str)

def make_sparse_baseline_csv(path: Path, rows: int = 3000, fs_hz: int = 20) -> None:
    """
    Generate sparse baseline dataset with low coverage.

    Features:
    - 3,000 rows (2.5 minutes at 20Hz)
    - Limited RPM/MAP coverage (focus on mid-range)
    - Same AFR error characteristics as dense
    - Minimal knock events
    """
    import csv
    rnd = random.Random(123)  # Different seed for variety
    dt = 1.0 / fs_hz
    t = 0.0

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        headers = ["rpm","map_kpa","torque","ve_f","ve_r","spark_f","spark_r",
                   "afr_cmd_f","afr_cmd_r","afr_meas_f","afr_meas_r","iat","knock","vbatt","tps"]
        w.writerow([sanitize_csv_cell(h) for h in headers])

        for _ in range(rows):
            t += dt

            # Limited RPM range: 2500-4000 RPM (sparse coverage)
            rpm = 3000 + 500 * math.sin(2*math.pi*t/20) + rnd.gauss(0, 100)
            rpm = max(2500, min(4000, rpm))

            # Limited MAP range: 60-85 kPa (sparse coverage)
            mapk = 72.5 + 12.5 * math.sin(2*math.pi*t/18) + rnd.gauss(0, 3)
            mapk = max(60, min(85, mapk))

            afr = 13.0
            # Same AFR error characteristics as dense
            afr_error_pct_f = rnd.gauss(0, 0.08) + 0.03 * math.sin(2*math.pi*(t-0.18)/9)
            afr_error_pct_r = rnd.gauss(0, 0.09) + 0.035 * math.sin(2*math.pi*(t-0.20)/9.5)

            afr_meas_f = afr * (1 + afr_error_pct_f)
            afr_meas_r = afr * (1 + afr_error_pct_r)

            torque = 80 + 10*math.sin(2*math.pi*t/8) + rnd.gauss(0, 5)
            torque = max(30, min(150, torque))

            iat = 105 + 6*math.sin(2*math.pi*t/45) + rnd.gauss(0, 3)
            iat = max(70, min(160, iat))

            # Rare knock events
            knock = 1 if (int(t*fs_hz) % 2000 == 0 and mapk > 80 and rpm > 3800) else 0

            vbatt = 13.9 + rnd.gauss(0, 0.02)
            tps = 20 + 5*math.sin(2*math.pi*t/6) + rnd.gauss(0, 2)

            row_data = [
                round(rpm,2), round(mapk,2), round(torque,2),
                120,121,24,22, afr, afr, round(afr_meas_f,2), round(afr_meas_r,2),
                round(iat,1), knock, round(vbatt,2), round(tps,1)
            ]
            row_data_str = [str(sanitize_csv_cell(c)) for c in row_data]
            w.writerow(row_data_str)

def run_toolkit(csv_path: Path, outdir: Path) -> dict:
    """Run the DynoAI toolkit and return manifest data."""
    args = [
        PY, str(TOOL),
        "--csv", str(csv_path),
        "--outdir", str(outdir),
        "--smooth_passes", "2",
        "--clamp", "15",
        "--rear_bias", "2.5",
        "--rear_rule_deg", "2.0",
        "--hot_extra", "-1.0"
    ]

    start_time = time.time()
    proc = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True)
    runtime = time.time() - start_time

    if proc.returncode != 0:
        raise RuntimeError(f"Toolkit failed: {proc.stderr}")

    manifest_path = outdir / "manifest.json"
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    return {
        "manifest": manifest,
        "runtime": runtime,
        "stdout": proc.stdout,
        "stderr": proc.stderr
    }

def calculate_baseline_metrics(manifest: dict, runtime: float) -> dict:
    """Calculate baseline metrics for comparison."""
    stats = manifest.get("stats", {})

    # VE Energy: sum of absolute VE correction percentages
    ve_energy = 0.0
    corrections_path = None
    for output in manifest.get("outputs", []):
        if output["name"] == "VE_Correction_Delta_DYNO.csv":
            corrections_path = Path(manifest["input"]["path"]).parent / output["path"]
            break

    if corrections_path and corrections_path.exists():
        # Read corrections and calculate energy
        with open(corrections_path, 'r', newline='', encoding='utf-8') as f:
            import csv
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                for val in row[1:]:  # Skip RPM column
                    if val.strip():
                        try:
                            ve_energy += abs(float(val))
                        except ValueError:
                            pass

    return {
        "runtime_seconds": runtime,
        "rows_read": stats.get("rows_read", 0),
        "bins_total": stats.get("bins_total", 0),
        "bins_covered": stats.get("bins_covered", 0),
        "coverage_percent": (stats.get("bins_covered", 0) / max(1, stats.get("bins_total", 0))) * 100,
        "ve_energy": ve_energy,
        "front_accepted": stats.get("front_accepted", 0),
        "rear_accepted": stats.get("rear_accepted", 0)
    }

def main():
    """Generate baseline datasets and establish reference metrics."""
    print("[*] DynoAI Kernel Testing - Baseline Setup")
    print("=" * 50)

    # Create directories
    dense_dir = ROOT / "experiments" / "outputs" / "dense_baseline"
    sparse_dir = ROOT / "experiments" / "outputs" / "sparse_baseline"

    dense_dir.mkdir(parents=True, exist_ok=True)
    sparse_dir.mkdir(parents=True, exist_ok=True)

    # Generate dense baseline
    print("\n[*] Generating dense baseline dataset...")
    dense_csv = dense_dir / "dense_baseline.csv"
    make_dense_baseline_csv(dense_csv, rows=12000)

    print("[>] Running toolkit on dense baseline...")
    dense_results = run_toolkit(dense_csv, dense_dir)
    dense_metrics = calculate_baseline_metrics(dense_results["manifest"], dense_results["runtime"])

    # Generate sparse baseline
    print("\n[*] Generating sparse baseline dataset...")
    sparse_csv = sparse_dir / "sparse_baseline.csv"
    make_sparse_baseline_csv(sparse_csv, rows=3000)

    print("[>] Running toolkit on sparse baseline...")
    sparse_results = run_toolkit(sparse_csv, sparse_dir)
    sparse_metrics = calculate_baseline_metrics(sparse_results["manifest"], sparse_results["runtime"])

    # Save baseline metrics
    baseline_data = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": "2025-11-10",
        "dense": dense_metrics,
        "sparse": sparse_metrics
    }

    baseline_path = ROOT / "experiments" / "baseline_metrics.json"
    with open(baseline_path, 'w', encoding='utf-8') as f:
        json.dump(baseline_data, f, indent=2)

    print("\nBaseline setup complete!")
    print(f"Dense baseline: {dense_dir}")
    print(f"Sparse baseline: {sparse_dir}")
    print(f"Metrics saved: {baseline_path}")

    print("\nDense Baseline Metrics:")
    for key, value in dense_metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.3f}")
        else:
            print(f"  {key}: {value}")

    print("\nSparse Baseline Metrics:")
    for key, value in sparse_metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.3f}")
        else:
            print(f"  {key}: {value}")

if __name__ == "__main__":
    main()