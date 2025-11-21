#!/usr/bin/env python
"""Generate dense synthetic dyno data for experiments with comprehensive coverage.

This creates a realistic multi-pass dyno session with:
- Full RPM range coverage (1500-5500 RPM)
- Full MAP range coverage (35-95 kPa)
- Multiple sweeps through the power band
- Realistic AFR variations, knock events, and thermal drift
- 10,000-15,000 data points for dense grid coverage
"""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path

from io_contracts import sanitize_csv_cell


def generate_dense_dyno_csv(
    output_path: Path,
    rows: int = 12000,
    fs_hz: int = 20,
    rpm_range: tuple[float, float] = (1500, 5500),
    map_range: tuple[float, float] = (35, 95),
    num_sweeps: int = 6,
) -> None:
    """
    Generate dense synthetic dyno data with comprehensive coverage.

    Args:
        output_path: Path to write CSV
        rows: Total number of data points (default: 12000 = 10 minutes @ 20 Hz)
        fs_hz: Sample rate in Hz
        rpm_range: (min_rpm, max_rpm) tuple
        map_range: (min_kpa, max_kpa) tuple
        num_sweeps: Number of full RPM sweeps (each with varying load)
    """
    rnd = random.Random(42)  # Deterministic for reproducibility
    dt = 1.0 / fs_hz
    t = 0.0

    # Calculate sweep parameters
    rpm_min, rpm_max = rpm_range
    rpm_center = (rpm_min + rpm_max) / 2
    rpm_amplitude = (rpm_max - rpm_min) / 2

    map_min, map_max = map_range
    map_center = (map_min + map_max) / 2
    map_amplitude = (map_max - map_min) / 2

    # Sweep periods (seconds) - varying lengths for diverse coverage
    sweep_period = (rows / fs_hz) / num_sweeps
    rpm_period = sweep_period * 0.8  # RPM sweeps slightly faster
    map_period = sweep_period * 1.2  # MAP changes more slowly

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Write header
        headers = [
            "rpm",
            "map_kpa",
            "torque",
            "ve_f",
            "ve_r",
            "spark_f",
            "spark_r",
            "afr_cmd_f",
            "afr_cmd_r",
            "afr_meas_f",
            "afr_meas_r",
            "iat",
            "knock",
            "vbatt",
            "tps",
        ]
        writer.writerow([sanitize_csv_cell(h) for h in headers])

        for _ in range(rows):
            t += dt

            # Multi-frequency RPM sweeps covering full range
            rpm_base = rpm_center + rpm_amplitude * math.sin(
                2 * math.pi * t / rpm_period
            )
            # Add secondary oscillation for more complete coverage
            rpm_wobble = 150 * math.sin(2 * math.pi * t / (rpm_period / 4.3))
            rpm = rpm_base + rpm_wobble
            rpm = max(rpm_min, min(rpm_max, rpm))  # Clamp to range

            # MAP/load variation - slower changes, multiple load points
            map_base = map_center + map_amplitude * math.sin(
                2 * math.pi * t / map_period
            )
            # Add third harmonic for intermediate load points
            map_harmonic = (
                map_amplitude * 0.3 * math.sin(2 * math.pi * t / (map_period / 3))
            )
            mapk = map_base + map_harmonic
            mapk = max(map_min, min(map_max, mapk))  # Clamp to range

            # AFR target varies slightly with load (richer at high load)
            afr_target_f = 13.0 - 0.3 * (mapk - map_min) / (map_max - map_min)
            afr_target_r = afr_target_f  # Same target for both cylinders

            # Measured AFR with realistic error patterns
            # Front cylinder: tighter control
            afr_error_f = 0.15 * math.sin(2 * math.pi * (t - 0.2) / 11.3) + rnd.gauss(
                0, 0.08
            )
            afr_meas_f = afr_target_f + afr_error_f

            # Rear cylinder: slightly more variation (common V-twin characteristic)
            afr_error_r = 0.20 * math.sin(2 * math.pi * (t - 0.25) / 12.1) + rnd.gauss(
                0, 0.10
            )
            afr_meas_r = afr_target_r + afr_error_r

            # Torque correlates with RPM and MAP
            rpm_factor = 1.0 - abs(rpm - 3500) / 2500  # Peak torque around 3500 RPM
            map_factor = (mapk - map_min) / (map_max - map_min)
            torque_base = 60 + 50 * rpm_factor * map_factor
            torque = torque_base + rnd.gauss(0, 2.5)

            # IAT rises gradually during session (thermal soak)
            iat_base = 85 + (t / (rows / fs_hz)) * 35  # 85°F -> 120°F over session
            iat_oscillation = 5 * math.sin(2 * math.pi * t / 60)  # Cooling cycles
            iat = iat_base + iat_oscillation + rnd.gauss(0, 1.5)

            # Knock events at high load + high RPM
            knock_threshold_map = 88
            knock_threshold_rpm = 4200
            knock_prob = 0.0
            if mapk > knock_threshold_map and rpm > knock_threshold_rpm:
                knock_prob = (
                    0.02
                    * ((mapk - knock_threshold_map) / 10)
                    * ((rpm - knock_threshold_rpm) / 1000)
                )
            knock = 1 if rnd.random() < knock_prob else 0

            # VE estimates (realistic values for Harley V-twin)
            ve_f = 58.0 + 40 * rpm_factor  # 58-98% range
            ve_r = ve_f - 2.0  # Rear slightly lower (thermal)

            # Spark advance varies with RPM and load
            spark_base = 20 + 15 * (rpm - rpm_min) / (rpm_max - rpm_min)
            spark_f = spark_base - knock * 2.0  # Retard on knock
            spark_r = spark_f - 2.0  # Rear safety margin

            # Battery voltage
            vbatt = 13.8 + rnd.gauss(0, 0.05)

            # TPS correlates with MAP
            tps = 10 + 85 * (mapk - map_min) / (map_max - map_min) + rnd.gauss(0, 2)
            tps = max(0, min(100, tps))

            # Build row
            row_data: list[float | int] = [
                round(rpm, 2),
                round(mapk, 2),
                round(torque, 2),
                round(ve_f, 1),
                round(ve_r, 1),
                round(spark_f, 1),
                round(spark_r, 1),
                round(afr_target_f, 2),
                round(afr_target_r, 2),
                round(afr_meas_f, 2),
                round(afr_meas_r, 2),
                round(iat, 1),
                knock,
                round(vbatt, 2),
                round(tps, 1),
            ]

            # Sanitize for CSV safety
            row_str = [str(sanitize_csv_cell(val)) for val in row_data]
            writer.writerow(row_str)

    print(f"[OK] Generated {rows} rows of dense dyno data:")
    print(f"     RPM range: {rpm_min}-{rpm_max}")
    print(f"     MAP range: {map_min}-{map_max} kPa")
    print(
        f"     Duration: {rows / fs_hz:.1f} seconds ({rows / fs_hz / 60:.1f} minutes)"
    )
    print(f"     Output: {output_path}")


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Default output path
    output = Path("dense_dyno_test.csv")

    # Parse optional command-line argument
    if len(sys.argv) > 1:
        output = Path(sys.argv[1])

    generate_dense_dyno_csv(
        output_path=output,
        rows=12000,
        fs_hz=20,
        rpm_range=(1500, 5500),
        map_range=(35, 95),
        num_sweeps=6,
    )
