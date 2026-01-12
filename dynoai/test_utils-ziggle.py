"""
Shared test utilities for generating synthetic dyno data.

This module provides functions for creating realistic synthetic WinPEP-style
CSV files for testing purposes. The synthetic data simulates dyno runs with
various conditions including AFR variations, knock events, temperature changes,
and realistic engine operating parameters.
"""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path
from typing import Any, Dict, List

from io_contracts import sanitize_csv_cell


def make_synthetic_csv(path: Path, rows: int = 4000, fs_hz: int = 20) -> None:
    """
    Generate a synthetic WinPEP-style CSV file for testing.

    This function creates realistic dyno test data with configurable number of rows
    and sampling frequency. The generated data includes:
    - Sinusoidal RPM/MAP variations
    - AFR command and measurement with realistic errors
    - Torque, IAT, knock, battery voltage, and TPS readings
    - Proper CSV sanitization for security

    Args:
        path: Output path for the CSV file
        rows: Number of data rows to generate (default: 4000)
        fs_hz: Sampling frequency in Hz (default: 20)

    Example:
        >>> from pathlib import Path
        >>> make_synthetic_csv(Path("test_data.csv"), rows=1000)
    """
    rnd = random.Random(42)  # Fixed seed for reproducibility
    dt = 1.0 / fs_hz
    t = 0.0

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
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
        w.writerow([sanitize_csv_cell(h) for h in headers])

        for _ in range(rows):
            t += dt

            # Sinusoidal RPM variation: 2800 ± 800 RPM
            rpm = 2800 + 800 * math.sin(2 * math.pi * t / 12)

            # Sinusoidal MAP variation: 80 ± 12 kPa
            mapk = 80 + 12 * math.sin(2 * math.pi * t / 7)

            # Base AFR command
            afr = 13.0

            # Generate AFR measurement errors with gaussian noise and sinusoidal pattern
            # Large errors ensure bin averages exceed 1% threshold for meaningful corrections
            afr_error_pct_f = rnd.gauss(0, 0.08) + 0.03 * math.sin(
                2 * math.pi * (t - 0.18) / 9
            )
            afr_error_pct_r = rnd.gauss(0, 0.09) + 0.035 * math.sin(
                2 * math.pi * (t - 0.20) / 9.5
            )

            afr_meas_f = afr * (1 + afr_error_pct_f)
            afr_meas_r = afr * (1 + afr_error_pct_r)

            # Sinusoidal torque variation: 80 ± 10 ft-lb
            torque = 80 + 10 * math.sin(2 * math.pi * t / 8)

            # Sinusoidal IAT variation: 105 ± 6°F
            iat = 105 + 6 * math.sin(2 * math.pi * t / 45)

            # Periodic knock events at high load/RPM conditions
            knock = 1 if (int(t * fs_hz) % 500 == 0 and mapk > 90 and rpm > 3200) else 0

            # Battery voltage with gaussian noise: 13.9 ± 0.02V
            vbatt = 13.9 + rnd.gauss(0, 0.02)

            # Sinusoidal TPS variation: 20 ± 5%
            tps = 20 + 5 * math.sin(2 * math.pi * t / 6)

            # Build data row with proper rounding
            row_data: list[float | int | str] = [
                round(rpm, 2),
                round(mapk, 2),
                round(torque, 2),
                120,
                121,  # Fixed VE values (front, rear)
                24,
                22,  # Fixed spark advance (front, rear)
                afr,
                afr,  # AFR command (front, rear)
                round(afr_meas_f, 2),
                round(afr_meas_r, 2),  # Measured AFR
                round(iat, 1),
                knock,
                round(vbatt, 2),
                round(tps, 1),
            ]

            # Sanitize and convert to strings for CSV safety
            row_data_str: List[str] = [str(sanitize_csv_cell(c)) for c in row_data]
            w.writerow(row_data_str)


def make_realistic_dyno_csv(
    path: Path, duration_minutes: int = 12, fs_hz: int = 20
) -> None:
    """
    Generate realistic dyno test data with large AFR variations and complex conditions.

    This function creates more complex test data compared to make_synthetic_csv,
    with multiple test phases, variable operating conditions, and realistic
    engine behavior patterns.

    Features:
    - Large AFR errors (±2.0 AFR) to generate significant VE corrections
    - Complex RPM/MAP sweeps including WOT and high load conditions
    - Lean and rich operating periods
    - Realistic knock patterns based on timing and conditions
    - Variable VE values that respond to conditions
    - Temperature extremes (cold start to heat soak)
    - Transients and step changes

    Args:
        path: Output path for the CSV file
        duration_minutes: Duration of the simulated dyno run in minutes (default: 12)
        fs_hz: Sampling frequency in Hz (default: 20)

    Example:
        >>> from pathlib import Path
        >>> make_realistic_dyno_csv(Path("complex_test.csv"), duration_minutes=15)
    """
    rnd = random.Random(42)  # Fixed seed for reproducibility

    total_samples = duration_minutes * 60 * fs_hz
    dt = 1.0 / fs_hz
    t = 0.0

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
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
        w.writerow([sanitize_csv_cell(h) for h in headers])

        # Phase definitions for complex dyno run
        phases: List[Dict[str, Any]] = [
            {
                "name": "warmup",
                "duration": 2 * 60,
                "rpm_base": 2000,
                "rpm_var": 500,
                "map_base": 60,
                "map_var": 10,
            },
            {
                "name": "sweep_low",
                "duration": 3 * 60,
                "rpm_base": 2500,
                "rpm_var": 800,
                "map_base": 70,
                "map_var": 15,
            },
            {
                "name": "high_load",
                "duration": 2 * 60,
                "rpm_base": 3500,
                "rpm_var": 600,
                "map_base": 95,
                "map_var": 5,
            },
            {
                "name": "lean_test",
                "duration": 1.5 * 60,
                "rpm_base": 3000,
                "rpm_var": 400,
                "map_base": 80,
                "map_var": 8,
            },
            {
                "name": "wot_sweep",
                "duration": 2 * 60,
                "rpm_base": 4000,
                "rpm_var": 1000,
                "map_base": 100,
                "map_var": 2,
            },
            {
                "name": "cooldown",
                "duration": 1.5 * 60,
                "rpm_base": 1800,
                "rpm_var": 300,
                "map_base": 50,
                "map_var": 6,
            },
        ]

        phase_start = 0.0
        current_phase = 0

        for sample_idx in range(total_samples):
            # Update phase
            if t >= phase_start + phases[current_phase]["duration"]:
                phase_start = t
                current_phase = min(current_phase + 1, len(phases) - 1)

            phase = phases[current_phase]
            phase_progress = (t - phase_start) / phase["duration"]

            # Complex RPM/MAP patterns with transients
            if phase["name"] == "warmup":
                rpm = (
                    phase["rpm_base"]
                    + phase["rpm_var"] * math.sin(2 * math.pi * t / 15)
                    + 200 * (1 - phase_progress)
                )
                mapk = phase["map_base"] + phase["map_var"] * math.sin(
                    2 * math.pi * t / 12
                )
            elif phase["name"] == "sweep_low":
                rpm = phase["rpm_base"] + phase["rpm_var"] * math.sin(
                    2 * math.pi * t / 8
                )
                mapk = phase["map_base"] + phase["map_var"] * math.sin(
                    2 * math.pi * t / 6
                )
            elif phase["name"] == "high_load":
                rpm = phase["rpm_base"] + phase["rpm_var"] * math.sin(
                    2 * math.pi * t / 5
                )
                mapk = min(
                    105,
                    phase["map_base"]
                    + phase["map_var"] * math.sin(2 * math.pi * t / 4),
                )
            elif phase["name"] == "lean_test":
                rpm = phase["rpm_base"] + phase["rpm_var"] * math.sin(
                    2 * math.pi * t / 10
                )
                mapk = phase["map_base"] + phase["map_var"] * math.sin(
                    2 * math.pi * t / 8
                )
            elif phase["name"] == "wot_sweep":
                rpm = phase["rpm_base"] + phase["rpm_var"] * math.sin(
                    2 * math.pi * t / 6
                )
                mapk = min(105, 98 + 4 * math.sin(2 * math.pi * t / 3))
            else:  # cooldown
                rpm = phase["rpm_base"] + phase["rpm_var"] * math.sin(
                    2 * math.pi * t / 20
                ) * (1 - phase_progress)
                mapk = phase["map_base"] + phase["map_var"] * math.sin(
                    2 * math.pi * t / 15
                ) * (1 - phase_progress)

            # Add noise and transients
            rpm += rnd.gauss(0, 25)
            mapk += rnd.gauss(0, 1.5)
            rpm = max(800, min(6500, rpm))
            mapk = max(25, min(110, mapk))

            # AFR command with lean/rich periods
            base_afr = 13.2
            if phase["name"] == "lean_test":
                base_afr = 14.2 + 0.5 * math.sin(2 * math.pi * t / 7)  # Lean condition
            elif phase["name"] == "high_load":
                base_afr = 12.8 + 0.3 * math.sin(2 * math.pi * t / 5)  # Rich condition
            elif sample_idx % 1200 < 300:  # Occasional rich periods
                base_afr = 12.5

            afr_cmd = base_afr

            # Large AFR measurement errors (±2.0 AFR) for significant corrections
            afr_error_f = rnd.gauss(0, 0.8) + 0.5 * math.sin(2 * math.pi * t / 11)
            afr_error_r = rnd.gauss(0, 0.9) + 0.6 * math.sin(2 * math.pi * t / 12)

            # Make errors larger in certain conditions
            if mapk > 90:
                afr_error_f *= 1.5
                afr_error_r *= 1.5
            if rpm > 4000:
                afr_error_f *= 1.2
                afr_error_r *= 1.2

            afr_meas_f = afr_cmd + afr_error_f
            afr_meas_r = afr_cmd + afr_error_r

            # Realistic AFR bounds
            afr_meas_f = max(9.0, min(18.0, afr_meas_f))
            afr_meas_r = max(9.0, min(18.0, afr_meas_r))

            # Torque based on conditions
            base_torque = 60 + (rpm - 2000) * 0.03 + (mapk - 50) * 0.8
            torque_noise = rnd.gauss(0, 3)
            torque = max(20, min(180, base_torque + torque_noise))

            # Variable VE based on conditions (not fixed like old generator)
            ve_base = 110 + (rpm - 3000) * 0.005 + (mapk - 70) * 0.1
            ve_f = ve_base + rnd.gauss(0, 2)
            ve_r = ve_base + rnd.gauss(0, 2.5)  # Rear slightly different
            ve_f = max(85, min(140, ve_f))
            ve_r = max(85, min(140, ve_r))

            # Spark advance based on conditions
            spark_base = 28 - (rpm - 3000) * 0.002 - (mapk - 70) * 0.01
            spark_f = spark_base + rnd.gauss(0, 0.5)
            spark_r = spark_base - 2.0 + rnd.gauss(0, 0.5)  # Rear retarded
            spark_f = max(8, min(45, spark_f))
            spark_r = max(8, min(45, spark_r))

            # Temperature with extremes
            if t < 60:  # Cold start
                iat = 65 + 20 * math.sin(2 * math.pi * t / 30) + rnd.gauss(0, 2)
            elif t > duration_minutes * 60 - 120:  # Heat soak
                iat = 185 + 15 * math.sin(2 * math.pi * t / 45) + rnd.gauss(0, 3)
            else:  # Normal operation
                iat = (
                    110
                    + 25 * math.sin(2 * math.pi * t / 180)
                    + 10 * (t / (duration_minutes * 60))
                    + rnd.gauss(0, 4)
                )
            iat = max(40, min(220, iat))

            # Realistic knock patterns
            timing_margin_f = spark_f - (28 - (rpm - 3000) * 0.003 - (mapk - 70) * 0.02)
            knock_prob_f = max(
                0, min(0.15, (1.5 - timing_margin_f) * 0.1 + (iat - 150) * 0.002)
            )
            knock_f = 1 if rnd.random() < knock_prob_f else 0

            # Battery voltage with realistic variation
            vbatt = 13.8 + 0.3 * math.sin(2 * math.pi * t / 300) + rnd.gauss(0, 0.05)
            vbatt = max(12.5, min(14.8, vbatt))

            # TPS based on MAP and transients
            tps_base = 15 + (mapk - 40) * 0.4
            tps = tps_base + rnd.gauss(0, 2) + 5 * math.sin(2 * math.pi * t / 13)
            tps = max(0, min(95, tps))

            row_data: list[float | int | str] = [
                round(rpm, 2),
                round(mapk, 2),
                round(torque, 2),
                round(ve_f, 1),
                round(ve_r, 1),
                round(spark_f, 1),
                round(spark_r, 1),
                round(afr_cmd, 2),
                round(afr_cmd, 2),
                round(afr_meas_f, 2),
                round(afr_meas_r, 2),
                round(iat, 1),
                knock_f,
                round(vbatt, 2),
                round(tps, 1),
            ]

            # Sanitize and coerce to strings
            row_data_str: List[str] = [str(sanitize_csv_cell(c)) for c in row_data]
            w.writerow(row_data_str)

            t += dt
