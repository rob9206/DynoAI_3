#!/usr/bin/env python3
"""
DLG-1 Accuracy & Data Quality Test

Analyzes the data stream to verify:
- Sample rate (should be ~12 Hz per channel)
- Both channels receiving data
- Data consistency and stability
- Packet loss detection
- Lambda resolution being utilized

Usage:
    python dlg1_accuracy_test.py [COM_PORT] [DURATION_SECONDS]

Example:
    python dlg1_accuracy_test.py COM5 30
"""

import io
import os
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List

from api.services.innovate_client import (
    InnovateClient,
    InnovateDeviceType,
    InnovateSample,
)

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class ChannelStats:
    """Statistics for a single channel."""

    samples: List[InnovateSample] = field(default_factory=list)
    afr_values: List[float] = field(default_factory=list)
    lambda_values: List[float] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    inter_sample_times: List[float] = field(default_factory=list)


def analyze_channel(stats: ChannelStats, channel: int) -> Dict:
    """Analyze data quality for a channel."""
    if not stats.samples:
        return {"error": "No samples received"}

    results = {
        "channel": channel,
        "total_samples": len(stats.samples),
    }

    # Time analysis
    if len(stats.timestamps) > 1:
        duration = stats.timestamps[-1] - stats.timestamps[0]
        results["duration_sec"] = round(duration, 2)
        results["sample_rate_hz"] = (
            round(len(stats.samples) / duration, 2) if duration > 0 else 0
        )

        # Inter-sample timing
        for i in range(1, len(stats.timestamps)):
            stats.inter_sample_times.append(
                stats.timestamps[i] - stats.timestamps[i - 1]
            )

        if stats.inter_sample_times:
            results["avg_sample_interval_ms"] = round(
                statistics.mean(stats.inter_sample_times) * 1000, 2
            )
            results["min_sample_interval_ms"] = round(
                min(stats.inter_sample_times) * 1000, 2
            )
            results["max_sample_interval_ms"] = round(
                max(stats.inter_sample_times) * 1000, 2
            )
            results["sample_interval_stdev_ms"] = (
                round(statistics.stdev(stats.inter_sample_times) * 1000, 2)
                if len(stats.inter_sample_times) > 1
                else 0
            )

            # Detect potential packet loss (gaps > 150ms when expecting ~83ms)
            gaps = [t for t in stats.inter_sample_times if t > 0.15]
            results["potential_gaps"] = len(gaps)

    # AFR analysis
    if stats.afr_values:
        results["afr_min"] = round(min(stats.afr_values), 2)
        results["afr_max"] = round(max(stats.afr_values), 2)
        results["afr_mean"] = round(statistics.mean(stats.afr_values), 2)
        results["afr_stdev"] = (
            round(statistics.stdev(stats.afr_values), 3)
            if len(stats.afr_values) > 1
            else 0
        )

        # Count unique AFR values (shows resolution being used)
        results["unique_afr_values"] = len(set(stats.afr_values))

    # Lambda analysis
    if stats.lambda_values:
        results["lambda_min"] = round(min(stats.lambda_values), 4)
        results["lambda_max"] = round(max(stats.lambda_values), 4)
        results["lambda_mean"] = round(statistics.mean(stats.lambda_values), 4)

        # Count unique lambda values
        results["unique_lambda_values"] = len(set(stats.lambda_values))

    return results


def print_results(results: Dict, channel_name: str):
    """Print formatted results for a channel."""
    print(f"\n{'-' * 50}")
    print(f"  CHANNEL {channel_name}")
    print(f"{'-' * 50}")

    if "error" in results:
        print(f"  [X] {results['error']}")
        return

    # Sample rate
    rate = results.get("sample_rate_hz", 0)
    rate_status = "[OK]" if 10 <= rate <= 15 else "[!!]" if rate > 0 else "[X]"
    print(f"  {rate_status} Sample Rate: {rate} Hz (target: ~12 Hz)")
    print(f"       Total Samples: {results.get('total_samples', 0)}")
    print(f"       Duration: {results.get('duration_sec', 0)} sec")

    # Timing consistency
    avg_interval = results.get("avg_sample_interval_ms", 0)
    stdev = results.get("sample_interval_stdev_ms", 0)
    timing_status = "[OK]" if stdev < 20 else "[!!]"
    print(f"\n  {timing_status} Timing Consistency:")
    print(f"       Avg Interval: {avg_interval} ms (target: ~83 ms)")
    print(
        f"       Min/Max: {results.get('min_sample_interval_ms', 0)} / {results.get('max_sample_interval_ms', 0)} ms"
    )
    print(f"       Std Dev: {stdev} ms")

    # Packet loss
    gaps = results.get("potential_gaps", 0)
    gap_status = "[OK]" if gaps == 0 else "[!!]"
    print(f"\n  {gap_status} Potential Packet Loss: {gaps} gaps detected")

    # AFR values
    print(f"\n  [*] AFR Statistics:")
    print(f"       Range: {results.get('afr_min', 0)} - {results.get('afr_max', 0)}")
    print(f"       Mean: {results.get('afr_mean', 0)}")
    print(f"       Std Dev: {results.get('afr_stdev', 0)} (lower = more stable)")
    print(f"       Unique Values: {results.get('unique_afr_values', 0)}")

    # Lambda resolution
    unique_lambda = results.get("unique_lambda_values", 0)
    resolution_status = "[OK]" if unique_lambda > 1 else "[!!]"
    print(f"\n  {resolution_status} Lambda Resolution:")
    print(
        f"       Range: {results.get('lambda_min', 0)} - {results.get('lambda_max', 0)}"
    )
    print(f"       Unique Values: {unique_lambda} (more = better resolution)")


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0

    print(f"""
{"=" * 60}
     DLG-1 ACCURACY & DATA QUALITY TEST
{"=" * 60}

Port: {port}
Test Duration: {duration} seconds

This test will analyze:
  - Sample rate (should be ~12 Hz per channel)
  - Timing consistency
  - Packet loss detection
  - Data resolution
  - Sensor stability

Starting in 3 seconds...
""")

    time.sleep(3)

    # Data collection
    channel_stats = {1: ChannelStats(), 2: ChannelStats()}
    packet_count = 0

    def on_sample(sample: InnovateSample):
        nonlocal packet_count
        packet_count += 1

        ch = sample.channel
        if ch in channel_stats:
            channel_stats[ch].samples.append(sample)
            channel_stats[ch].afr_values.append(sample.afr)
            channel_stats[ch].lambda_values.append(sample.lambda_value)
            channel_stats[ch].timestamps.append(sample.timestamp)

        # Progress indicator
        if packet_count % 20 == 0:
            print(f"\r  Collecting... {packet_count} samples", end="", flush=True)

    try:
        client = InnovateClient(port=port, device_type=InnovateDeviceType.DLG1)

        print("Connecting to DLG-1...")
        if not client.connect():
            print("[X] Failed to connect!")
            return 1

        print("[OK] Connected! Collecting data...\n")

        # Start streaming
        client.start_streaming(callback=on_sample, channels=[1, 2])

        # Wait for test duration
        time.sleep(duration)

        # Stop
        client.stop_streaming()
        client.disconnect()

        print(f"\r  Collection complete: {packet_count} total samples")

        # Analyze results
        print(f"\n{'=' * 60}")
        print("     ANALYSIS RESULTS")
        print(f"{'=' * 60}")

        ch1_results = analyze_channel(channel_stats[1], 1)
        ch2_results = analyze_channel(channel_stats[2], 2)

        print_results(ch1_results, "1 (Sensor A)")
        print_results(ch2_results, "2 (Sensor B)")

        # Overall assessment
        print(f"\n{'=' * 60}")
        print("     OVERALL ASSESSMENT")
        print(f"{'=' * 60}")

        issues = []

        # Check sample rates
        ch1_rate = ch1_results.get("sample_rate_hz", 0)
        ch2_rate = ch2_results.get("sample_rate_hz", 0)

        if ch1_rate < 10:
            issues.append("Channel 1 sample rate too low")
        if ch2_rate < 10:
            issues.append("Channel 2 sample rate too low")
        if ch2_rate == 0 and ch1_rate > 0:
            issues.append("Channel 2 not receiving data")

        # Check gaps
        if ch1_results.get("potential_gaps", 0) > 5:
            issues.append("Significant packet loss on Channel 1")
        if ch2_results.get("potential_gaps", 0) > 5:
            issues.append("Significant packet loss on Channel 2")

        # Check stability
        if ch1_results.get("afr_stdev", 0) > 0.5:
            issues.append("Channel 1 readings unstable (high variance)")
        if ch2_results.get("afr_stdev", 0) > 0.5:
            issues.append("Channel 2 readings unstable (high variance)")

        if not issues:
            print("\n  [OK] ALL CHECKS PASSED - Maximum accuracy achieved!")
            print("\n  Your DLG-1 is operating optimally:")
            print(
                f"       - Sample rate: ~{(ch1_rate + ch2_rate) / 2:.1f} Hz per channel"
            )
            print(f"       - Both channels active")
            print(f"       - Minimal packet loss")
            print(f"       - Stable readings")
        else:
            print("\n  [!!] ISSUES DETECTED:")
            for issue in issues:
                print(f"       - {issue}")
            print("\n  Recommendations:")
            if any("sample rate" in i.lower() for i in issues):
                print("       - Check USB connection")
                print("       - Close other applications using serial ports")
            if any("channel 2" in i.lower() for i in issues):
                print("       - Check sensor B connection")
                print("       - Verify sensor B is enabled in LM Programmer")
            if any("unstable" in i.lower() for i in issues):
                print("       - Calibrate sensors using LM Programmer")
                print("       - Check for electrical interference")

        # Calibration reminder
        ch1_afr = ch1_results.get("afr_mean", 0)
        ch2_afr = ch2_results.get("afr_mean", 0)

        print(f"\n{'-' * 60}")
        print("  CALIBRATION STATUS")
        print(f"{'-' * 60}")

        for ch, afr, name in [(1, ch1_afr, "A"), (2, ch2_afr, "B")]:
            if 21.0 <= afr <= 23.0:
                print(
                    f"  [OK] Sensor {name}: {afr:.1f} AFR - Calibrated (reading free air)"
                )
            elif 20.0 <= afr <= 24.0:
                print(
                    f"  [!!] Sensor {name}: {afr:.1f} AFR - Close, may need fine calibration"
                )
            elif afr > 0:
                print(
                    f"  [i] Sensor {name}: {afr:.1f} AFR - Not in free air (or needs calibration)"
                )
            else:
                print(f"  [X] Sensor {name}: No data")

        print(f"\n{'=' * 60}")

        return 0

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return 1
    except Exception as e:
        print(f"[X] Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    if sys.platform == "win32":
        os.system("")  # Enable ANSI colors
    sys.exit(main())
