#!/usr/bin/env python3
"""
DynoAI Kernel Testing Metrics and Comparison System

Calculates advanced metrics for kernel evaluation:
- VE Energy: Sum of absolute VE correction percentages
- Stability: Delta between normal vs. shuffled input
- Runtime: Total processing time
- Coverage preservation
"""

import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import List

# Add parent directory to path for imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PY = sys.executable
TOOL = ROOT / "ai_tuner_toolkit_dyno_v1_2.py"

def load_baseline_metrics() -> dict:
    """Load baseline metrics for comparison."""
    baseline_path = ROOT / "experiments" / "baseline_metrics.json"
    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline metrics not found: {baseline_path}")

    with open(baseline_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_ve_energy(corrections_path: Path) -> float:
    """Calculate VE Energy: sum of absolute VE correction percentages."""
    if not corrections_path.exists():
        return 0.0

    energy = 0.0
    with open(corrections_path, 'r', newline='', encoding='utf-8') as f:
        import csv
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            for val in row[1:]:  # Skip RPM column
                val = val.strip()
                if val and val != ',':
                    # Remove single quotes that may surround values
                    val = val.strip("'\"")
                    try:
                        energy += abs(float(val))
                    except ValueError:
                        pass
    return energy

def calculate_stability(csv_path: Path, outdir: Path, kernel_args: List[str] = None) -> float:
    """
    Calculate stability: delta between normal vs. shuffled input.

    Shuffles the order of rows in the CSV to test if kernel produces
    consistent results regardless of input ordering.
    """
    # Read original CSV
    rows = []
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        import csv
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    if len(rows) < 10:
        return 0.0  # Not enough data for meaningful stability test

    # Create shuffled version
    shuffled_rows = rows.copy()
    random.Random(42).shuffle(shuffled_rows)  # Fixed seed for reproducibility

    # Write shuffled CSV
    shuffled_csv = outdir / "shuffled_input.csv"
    with open(shuffled_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(shuffled_rows)

    # Run toolkit on shuffled input
    shuffled_outdir = outdir / "shuffled_output"
    shuffled_outdir.mkdir(exist_ok=True)

    args = [
        PY, str(TOOL),
        "--csv", str(shuffled_csv),
        "--outdir", str(shuffled_outdir),
        "--smooth_passes", "2",
        "--clamp", "15",
        "--rear_bias", "2.5",
        "--rear_rule_deg", "2.0",
        "--hot_extra", "-1.0"
    ]

    if kernel_args:
        args.extend(kernel_args)

    proc = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"Warning: Shuffled run failed: {proc.stderr}")
        return float('inf')  # Indicate failure

    # Load shuffled results
    shuffled_manifest = json.load(open(shuffled_outdir / "manifest.json", 'r', encoding='utf-8'))

    # Find correction files
    normal_corrections = None
    shuffled_corrections = None

    for output in shuffled_manifest.get("outputs", []):
        if output["name"] == "VE_Correction_Delta_DYNO.csv":
            shuffled_corrections = shuffled_outdir / output["path"]
            break

    # Find normal corrections (from current run)
    normal_manifest_path = outdir / "manifest.json"
    if normal_manifest_path.exists():
        normal_manifest = json.load(open(normal_manifest_path, 'r', encoding='utf-8'))
        for output in normal_manifest.get("outputs", []):
            if output["name"] == "VE_Correction_Delta_DYNO.csv":
                normal_corrections = outdir / output["path"]
                break

    if not normal_corrections or not shuffled_corrections:
        return float('inf')

    # Calculate RMS difference between normal and shuffled corrections
    rms_diff = 0.0
    count = 0

    normal_data = {}
    shuffled_data = {}

    # Read normal corrections
    with open(normal_corrections, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) >= 2:
                try:
                    rpm = int(float(row[0]))
                    for i, val in enumerate(row[1:], 1):
                        if val.strip():
                            # Remove single quotes that may surround values
                            val = val.strip("'\"")
                            kpa = [35, 50, 65, 80, 95][i-1]  # Map column index to kPa
                            normal_data[(rpm, kpa)] = float(val)
                except (ValueError, IndexError):
                    continue

    # Read shuffled corrections
    with open(shuffled_corrections, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) >= 2:
                try:
                    rpm = int(float(row[0]))
                    for i, val in enumerate(row[1:], 1):
                        if val.strip():
                            # Remove single quotes that may surround values
                            val = val.strip("'\"")
                            kpa = [35, 50, 65, 80, 95][i-1]
                            shuffled_data[(rpm, kpa)] = float(val)
                except (ValueError, IndexError):
                    continue

    # Calculate RMS difference for common cells
    for key in set(normal_data.keys()) & set(shuffled_data.keys()):
        diff = normal_data[key] - shuffled_data[key]
        rms_diff += diff * diff
        count += 1

    return math.sqrt(rms_diff / max(1, count)) if count > 0 else float('inf')

def run_kernel_experiment(csv_path: Path, outdir: Path, kernel_name: str, dataset_type: str,
                         kernel_args: List[str] = None) -> dict:
    """Run a kernel experiment and calculate all metrics."""

    start_time = time.time()

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

    if kernel_args:
        args.extend(kernel_args)

    proc = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True)
    runtime = time.time() - start_time

    if proc.returncode != 0:
        raise RuntimeError(f"Kernel experiment failed: {proc.stderr}")

    # Load results
    manifest_path = outdir / "manifest.json"
    manifest = json.load(open(manifest_path, 'r', encoding='utf-8'))
    stats = manifest.get("stats", {})

    # Find corrections file
    corrections_path = None
    for output in manifest.get("outputs", []):
        if output["name"] == "VE_Correction_Delta_DYNO.csv":
            corrections_path = outdir / output["path"]
            break

    # Calculate metrics
    ve_energy = calculate_ve_energy(corrections_path) if corrections_path else 0.0
    stability = calculate_stability(csv_path, outdir, kernel_args)

    return {
        "kernel_name": kernel_name,
        "dataset": dataset_type,  # Add missing dataset field
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runtime_seconds": runtime,
        "rows_read": stats.get("rows_read", 0),
        "bins_total": stats.get("bins_total", 0),
        "bins_covered": stats.get("bins_covered", 0),
        "coverage_percent": (stats.get("bins_covered", 0) / max(1, stats.get("bins_total", 0))) * 100,
        "ve_energy": ve_energy,
        "stability_rms": stability,
        "front_accepted": stats.get("front_accepted", 0),
        "rear_accepted": stats.get("rear_accepted", 0),
        "success": proc.returncode == 0
    }

def compare_to_baseline(experiment_metrics: dict, baseline_metrics: dict,
                       dataset_type: str) -> dict:
    """Compare experiment metrics to baseline."""

    baseline = baseline_metrics.get(dataset_type, {})

    return {
        "runtime_delta": experiment_metrics["runtime_seconds"] - baseline.get("runtime_seconds", 0),
        "coverage_delta": experiment_metrics["coverage_percent"] - baseline.get("coverage_percent", 0),
        "ve_energy_delta": experiment_metrics["ve_energy"] - baseline.get("ve_energy", 0),
        "bins_covered_delta": experiment_metrics["bins_covered"] - baseline.get("bins_covered", 0)
    }

def save_experiment_summary(experiments: List[dict], output_path: Path):
    """Save experiment summary to JSON file."""

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": "2025-11-10",
        "experiments": experiments
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

def main():
    """Run kernel experiments and generate comparison report."""

    print("[*] DynoAI Kernel Testing - Metrics & Comparison")
    print("=" * 55)

    # Load baseline metrics
    try:
        baseline_metrics = load_baseline_metrics()
        print("[+] Loaded baseline metrics")
    except FileNotFoundError as e:
        print(f"[-] {e}")
        return 1

    # Define test datasets
    dense_csv = ROOT / "experiments" / "outputs" / "dense_baseline" / "dense_baseline.csv"
    sparse_csv = ROOT / "experiments" / "outputs" / "sparse_baseline" / "sparse_baseline.csv"

    if not dense_csv.exists() or not sparse_csv.exists():
        print("[-] Baseline datasets not found. Run baseline_generator.py first.")
        return 1

    # Define kernel experiments
    kernels = [
        {
            "name": "baseline_kernel",
            "args": [],  # Default two-stage kernel
            "description": "Current two-stage adaptive kernel (default)"
        }
    ]

    # Run experiments on both datasets
    experiments = []

    for kernel in kernels:
        print(f"\n[*] Testing kernel: {kernel['name']}")
        print(f"   {kernel['description']}")

        for dataset_type, csv_path in [("dense", dense_csv), ("sparse", sparse_csv)]:
            print(f"   -> {dataset_type} dataset...")

            # Create output directory
            outdir = ROOT / "experiments" / "outputs" / f"{kernel['name']}_{dataset_type}"
            outdir.mkdir(parents=True, exist_ok=True)

            try:
                # Run experiment
                metrics = run_kernel_experiment(csv_path, outdir, kernel["name"], dataset_type, kernel["args"])

                # Compare to baseline
                comparison = compare_to_baseline(metrics, baseline_metrics, dataset_type)
                metrics["baseline_comparison"] = comparison

                experiments.append(metrics)

                print(f"      Runtime: {metrics['runtime_seconds']:.3f}s")
                print(f"      Coverage: {metrics['coverage_percent']:.3f}%")
                print(f"      VE Energy: {metrics['ve_energy']:.3f}")
                print(f"      Stability: {metrics['stability_rms']:.3f}")

            except Exception as e:
                print(f"   [-] Failed: {e}")
                experiments.append({
                    "kernel_name": kernel["name"],
                    "dataset": dataset_type,
                    "error": str(e),
                    "success": False
                })

    # Save results
    summary_path = ROOT / "experiments" / "experiment_summary.json"
    save_experiment_summary(experiments, summary_path)

    print("\n[>] Results saved to:")
    print(f"   {summary_path}")

    # Print summary table
    print("\n[*] Summary Table:")
    print("-" * 80)
    print(f"{'Kernel':<15} {'Dataset':<10} {'Runtime':<10} {'Coverage':<10} {'VE Energy':<12} {'Stability':<12}")
    print("-" * 80)

    successful_experiments = [e for e in experiments if e.get("success", False)]
    for exp in successful_experiments:
        dataset = exp.get("dataset", "unknown")
        runtime = exp.get("runtime_seconds", 0)
        coverage = exp.get("coverage_percent", 0)
        energy = exp.get("ve_energy", 0)
        stability = exp.get("stability_rms", float('inf'))

        print(f"{exp.get('kernel_name', 'unknown'):<15} {dataset:<10} {runtime:<10.3f} {coverage:<10.3f} {energy:<12.3f} {stability:<12.3f}")

    return 0

if __name__ == "__main__":
    sys.exit(main())