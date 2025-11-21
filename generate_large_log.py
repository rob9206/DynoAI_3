import csv
import math
import random
from pathlib import Path


def make_synthetic_csv(path: Path, rows: int = 250000, fs_hz: int = 20) -> None:
    """
    Generates a large synthetic WinPEP-style CSV file for testing.
    """
    print(f"Generating {rows} rows of synthetic data to {path}...")
    rnd = random.Random(42)
    dt = 1.0 / fs_hz
    t = 0.0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # Minimal WinPEP-like header (simplified for tests)
        w.writerow(
            [
                "Engine RPM",
                "MAP kPa",
                "Torque",
                "AFR Target F",
                "AFR Target R",
                "VE F",
                "VE R",
                "AFR Cmd F",
                "AFR Cmd R",
                "AFR Meas F",
                "AFR Meas R",
                "IAT F",
                "Knock",
                "VBatt",
                "TPS",
            ]
        )

        rpm = 2000.0
        mapk = 30.0

        for i in range(rows):
            # Simple ramp/oscillation model
            rpm += rnd.gauss(10.0, 3.0)
            rpm = max(800.0, min(rpm, 6500.0))

            mapk += rnd.gauss(0.5, 0.3)
            mapk = max(20.0, min(mapk, 100.0))

            ve_f = 24 + 2 * math.sin(2 * math.pi * t / 10)
            ve_r = 22 + 2 * math.sin(2 * math.pi * t / 11)

            afr_target_f = 13.0 if mapk < 60 else 12.5
            afr_target_r = 13.0 if mapk < 60 else 12.5

            afr_cmd_f = afr_target_f + rnd.gauss(0, 0.05)
            afr_cmd_r = afr_target_r + rnd.gauss(0, 0.05)

            afr_meas_f = afr_cmd_f + rnd.gauss(0, 0.1)
            afr_meas_r = afr_cmd_r + rnd.gauss(0, 0.1)

            afr = 14.7  # placeholder closed-loop reference

            torque = 80 + 10 * math.sin(2 * math.pi * t / 8)
            iat = 105 + 6 * math.sin(2 * math.pi * t / 45)
            knock = 1 if (int(t * fs_hz) % 500 == 0 and mapk > 90 and rpm > 3200) else 0
            vbatt = 13.9 + rnd.gauss(0, 0.02)
            tps = 20 + 5 * math.sin(2 * math.pi * t / 6)
            w.writerow(
                [
                    round(rpm, 2),
                    round(mapk, 2),
                    round(torque, 2),
                    120,
                    121,
                    24,
                    22,
                    afr,
                    afr,
                    round(afr_meas_f, 2),
                    round(afr_meas_r, 2),
                    round(iat, 1),
                    knock,
                    round(vbatt, 2),
                    round(tps, 1),
                ]
            )
            t += dt
    print("Done.")


if __name__ == "__main__":
    output_path = Path("large_test_log.csv")
    make_synthetic_csv(output_path)
    print(f"Successfully created large log file: {output_path.resolve()}")
