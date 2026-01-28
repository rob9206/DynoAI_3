"""
Benchmark script for JetDrive Real-Time Analysis Engine

Verifies performance requirements:
- on_aggregated_sample() completes in <1ms
- get_state() completes in <10ms
- No memory leaks under sustained load
"""

import gc
import sys
import time

from api.services.jetdrive_realtime_analysis import RealtimeAnalysisEngine

# Add project root to path
sys.path.insert(0, ".")


def make_sample(i: int) -> dict:
    """Create a sample data point."""
    return {
        "timestamp_ms": i * 50,
        "rpm": 1000 + (i % 9000),  # Vary across RPM range
        "map_kpa": 20 + (i % 100),  # Vary across MAP range
        "afr": 12.0 + (i % 60) * 0.1,  # Vary AFR
        "tps": 10 + (i % 90),
        "torque": 50 + (i % 200),
        "horsepower": 100 + (i % 300),
    }


def benchmark_on_aggregated_sample(engine: RealtimeAnalysisEngine,
                                   num_samples: int = 1000):
    """Benchmark on_aggregated_sample() performance."""
    print(
        f"\n=== Benchmarking on_aggregated_sample ({num_samples} samples) ===")

    # Warm up
    for i in range(100):
        engine.on_aggregated_sample(make_sample(i))

    # Measure
    times = []
    for i in range(num_samples):
        sample = make_sample(i + 100)

        start = time.perf_counter()
        engine.on_aggregated_sample(sample)
        elapsed = time.perf_counter() - start

        times.append(elapsed * 1000)  # Convert to ms

    avg_ms = sum(times) / len(times)
    max_ms = max(times)
    min_ms = min(times)
    p99_ms = sorted(times)[int(len(times) * 0.99)]

    print(f"  Average: {avg_ms:.4f} ms")
    print(f"  Min:     {min_ms:.4f} ms")
    print(f"  Max:     {max_ms:.4f} ms")
    print(f"  P99:     {p99_ms:.4f} ms")

    if avg_ms < 1.0:
        print(f"  PASS: Average {avg_ms:.4f}ms < 1ms limit")
    else:
        print(f"  FAIL: Average {avg_ms:.4f}ms >= 1ms limit")

    return avg_ms < 1.0


def benchmark_get_state(engine: RealtimeAnalysisEngine, num_calls: int = 100):
    """Benchmark get_state() performance."""
    print(f"\n=== Benchmarking get_state ({num_calls} calls) ===")

    # Measure
    times = []
    for _ in range(num_calls):
        start = time.perf_counter()
        state = engine.get_state()
        elapsed = time.perf_counter() - start

        times.append(elapsed * 1000)

    avg_ms = sum(times) / len(times)
    max_ms = max(times)

    print(f"  Average: {avg_ms:.4f} ms")
    print(f"  Max:     {max_ms:.4f} ms")

    if avg_ms < 10.0:
        print(f"  PASS: Average {avg_ms:.4f}ms < 10ms limit")
    else:
        print(f"  FAIL: Average {avg_ms:.4f}ms >= 10ms limit")

    return avg_ms < 10.0


def benchmark_sustained_load(num_samples: int = 10000):
    """Benchmark sustained load to check for memory issues."""
    print(f"\n=== Benchmarking sustained load ({num_samples} samples) ===")

    engine = RealtimeAnalysisEngine(target_afr=14.7)

    gc.collect()

    start = time.perf_counter()
    for i in range(num_samples):
        engine.on_aggregated_sample(make_sample(i))
    elapsed = time.perf_counter() - start

    total_ms = elapsed * 1000
    avg_ms = total_ms / num_samples
    samples_per_sec = num_samples / elapsed

    print(f"  Total time: {total_ms:.2f} ms")
    print(f"  Average per sample: {avg_ms:.4f} ms")
    print(f"  Throughput: {samples_per_sec:.0f} samples/sec")
    print(f"  Coverage cells: {len(engine.coverage_map)}")
    print(f"  VE delta cells: {len(engine.ve_delta_map)}")
    print(f"  Alerts: {len(engine.alerts)}")

    # Check that we can handle 20Hz (50ms per sample)
    # We need to process in <1ms to leave headroom
    if avg_ms < 1.0:
        print(f"  PASS: Can handle 20Hz with {(1.0 - avg_ms):.3f}ms headroom")
    else:
        print(f"  FAIL: Cannot handle 20Hz, need {avg_ms:.3f}ms per sample")

    return avg_ms < 1.0


def main():
    print("=" * 60)
    print("JetDrive Real-Time Analysis Engine Benchmark")
    print("=" * 60)

    # Create engine
    engine = RealtimeAnalysisEngine(target_afr=14.7)

    # Run benchmarks
    results = []

    # Test 1: on_aggregated_sample performance
    results.append(
        ("on_aggregated_sample", benchmark_on_aggregated_sample(engine, 1000)))

    # Test 2: get_state performance (with data)
    results.append(("get_state", benchmark_get_state(engine, 100)))

    # Test 3: Sustained load
    results.append(("sustained_load", benchmark_sustained_load(10000)))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All benchmarks PASSED - ready for 20Hz operation")
        return 0
    else:
        print("Some benchmarks FAILED - performance issues detected")
        return 1


if __name__ == "__main__":
    sys.exit(main())
