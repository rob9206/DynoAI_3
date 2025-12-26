#!/usr/bin/env python3
"""
Experiment: K2 Coverage-Adaptive Clamp Kernel

Tests the K2 kernel against baseline datasets to measure:
- VE Energy (sum of absolute corrections)
- Stability (RMS difference vs shuffled input)
- Runtime performance
- Comparison with K1 gradient-limiting kernel
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

import k2_coverage_adaptive_v1 as k2

from experiments.utils import calculate_metrics, load_baseline_data

# Add paths
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "experiments" / "protos"))

# Import kernels

# Import experiment utilities
sys.path.insert(0, str(ROOT))


def run_k2_experiment(dataset_name: str, dataset_path: str) -> Dict[str, Any]:
    """Run K2 kernel experiment on a dataset."""

    print(f"Running K2 experiment on {dataset_name}...")

    # Load baseline data
    baseline_data = load_baseline_data(dataset_path)
    input_grid = baseline_data["grid"]

    # Record start time
    start_time = time.time()

    # Apply K2 kernel
    result_grid = k2.kernel_smooth(input_grid, passes=2)

    # Record end time
    end_time = time.time()
    runtime_ms = (end_time - start_time) * 1000

    # Calculate metrics
    metrics = calculate_metrics(input_grid, result_grid, runtime_ms)

    # Add kernel-specific metadata
    metrics.update(
        {
            "kernel": "k2_coverage_adaptive_v1",
            "kernel_description": "Coverage-adaptive clamp kernel with confidence-based limits",
            "parameters": {
                "passes": 2,
                "low_confidence_threshold": 1.0,
                "high_confidence_threshold": 3.0,
            },
            "dataset": dataset_name,
            "dataset_path": dataset_path,
        }
    )

    print(f"Runtime: {runtime_ms:.1f}ms")
    print(f"VE Energy: {metrics['ve_energy']:.3f}")
    print(f"Stability: {metrics['stability']:.6f}")
    return metrics


def compare_kernels(
    k1_results: Dict[str, Any], k2_results: Dict[str, Any]
) -> Dict[str, Any]:
    """Compare K1 and K2 kernel results."""

    comparison = {
        "kernels_compared": ["k1_gradient_limit_v1", "k2_coverage_adaptive_v1"],
        "datasets": [],
        "metrics_comparison": {},
    }

    # Compare each dataset
    datasets = set(k1_results.keys()) & set(k2_results.keys())
    for dataset in datasets:
        if dataset in ["experiment_info"]:  # Skip metadata
            continue

        k1_data = k1_results[dataset]
        k2_data = k2_results[dataset]

        comparison["datasets"].append(dataset)
        comparison["metrics_comparison"][dataset] = {
            "ve_energy": {
                "k1": k1_data["ve_energy"],
                "k2": k2_data["ve_energy"],
                "k2_vs_k1_ratio": (
                    k2_data["ve_energy"] / k1_data["ve_energy"]
                    if k1_data["ve_energy"] != 0
                    else float("inf")
                ),
            },
            "stability": {
                "k1": k1_data["stability"],
                "k2": k2_data["stability"],
                "k2_vs_k1_ratio": (
                    k2_data["stability"] / k1_data["stability"]
                    if k1_data["stability"] != 0
                    else float("inf")
                ),
            },
            "runtime_ms": {
                "k1": k1_data["runtime_ms"],
                "k2": k2_data["runtime_ms"],
                "k2_vs_k1_ratio": (
                    k2_data["runtime_ms"] / k1_data["runtime_ms"]
                    if k1_data["runtime_ms"] != 0
                    else float("inf")
                ),
            },
        }

    return comparison


def main():
    """Main experiment execution."""

    print("=== K2 Coverage-Adaptive Clamp Kernel Experiment ===\n")

    # Define datasets to test
    datasets = {
        "dense": "experiments/baselines/dense_baseline.json",
        "sparse": "experiments/baselines/sparse_baseline.json",
    }

    # Run K2 experiments
    k2_results = {}
    for name, path in datasets.items():
        try:
            k2_results[name] = run_k2_experiment(name, path)
        except Exception as e:
            print(f"Failed to run K2 on {name}: {e}")
            continue

    # Load K1 results for comparison
    k1_results_path = ROOT / "experiments" / "results" / "k1_experiment_results.json"
    k1_results = {}
    if k1_results_path.exists():
        try:
            with open(k1_results_path, "r") as f:
                k1_results = json.load(f)
            print("Loaded K1 results for comparison")
        except Exception as e:
            print(f"Could not load K1 results: {e}")
    else:
        print("K1 results not found - comparison will be skipped")

    # Add experiment metadata
    k2_results["experiment_info"] = {
        "experiment_name": "k2_coverage_adaptive_experiment",
        "description": "Testing K2 coverage-adaptive clamp kernel against baseline datasets",
        "timestamp": time.time(),
        "kernels_tested": ["k2_coverage_adaptive_v1"],
        "datasets_tested": list(datasets.keys()),
    }

    # Generate comparison if K1 results available
    if k1_results:
        comparison = compare_kernels(k1_results, k2_results)
        k2_results["comparison_with_k1"] = comparison
        print("\n=== K1 vs K2 Comparison ===")
        for dataset in comparison["datasets"]:
            comp = comparison["metrics_comparison"][dataset]
            print(f"\n{dataset.upper()} Dataset:")
            print(
                f"VE Energy - K1: {comp['ve_energy']['k1']:.3f}, K2: {comp['ve_energy']['k2']:.3f}, K2/K1: {comp['ve_energy']['k2_vs_k1_ratio']:.3f}"
            )
            print(
                f"Stability - K1: {comp['stability']['k1']:.6f}, K2: {comp['stability']['k2']:.6f}, K2/K1: {comp['stability']['k2_vs_k1_ratio']:.3f}"
            )
            print(
                f"Runtime - K1: {comp['runtime_ms']['k1']:.1f}ms, K2: {comp['runtime_ms']['k2']:.1f}ms, K2/K1: {comp['runtime_ms']['k2_vs_k1_ratio']:.3f}"
            )
    # Save results
    results_dir = ROOT / "experiments" / "results"
    results_dir.mkdir(exist_ok=True)

    results_file = results_dir / "k2_experiment_results.json"
    with open(results_file, "w") as f:
        json.dump(k2_results, f, indent=2, default=str)

    print(f"\nResults saved to: {results_file}")

    # Summary
    successful_datasets = [name for name in datasets if name in k2_results]
    print(
        f"\nExperiment completed successfully on {len(successful_datasets)}/{len(datasets)} datasets"
    )


if __name__ == "__main__":
    main()
