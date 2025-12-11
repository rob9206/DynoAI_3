#!/usr/bin/env python3
"""
Analyze captured JetDrive dyno data and generate tuning recommendations.
"""

import csv
from pathlib import Path

import numpy as np
import pandas as pd


def analyze_run(csv_path: Path) -> dict:
    """Analyze a dyno run and return tuning recommendations."""
    df = pd.read_csv(csv_path)

    print("=" * 60)
    print("DYNO DATA ANALYSIS")
    print("=" * 60)
    print(f"Source: {csv_path}")
    print(f"Rows: {len(df)}")
    print()

    # Basic stats
    print("Channel Statistics:")
    print("-" * 40)
    for col in ["RPM", "Torque", "Horsepower", "AFR"]:
        if col in df.columns:
            print(
                f"  {col:12s}: min={df[col].min():7.1f}  "
                f"max={df[col].max():7.1f}  mean={df[col].mean():7.1f}"
            )

    print()
    print("Peak Performance:")
    print("-" * 40)
    peak_hp_idx = df["Horsepower"].idxmax()
    peak_tq_idx = df["Torque"].idxmax()
    peak_hp = df.loc[peak_hp_idx, "Horsepower"]
    peak_hp_rpm = df.loc[peak_hp_idx, "RPM"]
    peak_tq = df.loc[peak_tq_idx, "Torque"]
    peak_tq_rpm = df.loc[peak_tq_idx, "RPM"]
    print(f"  Peak HP:  {peak_hp:.1f} @ {peak_hp_rpm:.0f} RPM")
    print(f"  Peak TQ:  {peak_tq:.1f} ft-lb @ {peak_tq_rpm:.0f} RPM")

    # AFR Analysis by zone
    print()
    print("AFR Analysis (vs target):")
    print("-" * 40)

    # Classify into zones
    df["Zone"] = pd.cut(
        df["RPM"],
        bins=[0, 2000, 3500, 5000, 7000],
        labels=["Idle", "Cruise", "Mid", "WOT"],
    )

    # Target AFR by zone (typical V-twin targets)
    target_map = {"Idle": 14.7, "Cruise": 14.0, "Mid": 13.0, "WOT": 12.5}
    df["AFR_Target"] = df["Zone"].map(target_map).astype(float)
    df["AFR_Error_Pct"] = ((df["AFR"] - df["AFR_Target"]) / df["AFR_Target"]) * 100

    zone_analysis = {}
    for zone in ["Idle", "Cruise", "Mid", "WOT"]:
        zone_data = df[df["Zone"] == zone]
        if len(zone_data) > 0:
            mean_err = zone_data["AFR_Error_Pct"].mean()
            status = "LEAN" if mean_err > 2 else "RICH" if mean_err < -2 else "OK"
            print(f"  {zone:6s}: AFR error = {mean_err:+5.1f}%  [{status}]")
            zone_analysis[zone] = {"error_pct": mean_err, "status": status}

    # Generate VE correction suggestions
    print()
    print("VE Correction Recommendations:")
    print("-" * 40)

    corrections = {}
    for zone in ["Idle", "Cruise", "Mid", "WOT"]:
        zone_data = df[df["Zone"] == zone]
        if len(zone_data) > 0:
            mean_err = zone_data["AFR_Error_Pct"].mean()
            # If lean (+error), need MORE fuel → INCREASE VE
            # If rich (-error), need LESS fuel → DECREASE VE
            correction = 1 + (mean_err / 100)
            correction = np.clip(correction, 0.90, 1.10)  # ±10% max
            action = (
                "increase"
                if correction > 1.01
                else "decrease"
                if correction < 0.99
                else "keep"
            )
            print(
                f"  {zone:6s}: VE x {correction:.3f}  "
                f"({action} VE by {abs(correction - 1) * 100:.1f}%)"
            )
            corrections[zone] = correction

    # Save corrections to CSV
    output_dir = csv_path.parent
    corrections_path = output_dir / "ve_corrections.csv"

    with open(corrections_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Zone", "RPM_Min", "RPM_Max", "VE_Multiplier", "Action"])
        zone_rpm = {
            "Idle": (0, 2000),
            "Cruise": (2000, 3500),
            "Mid": (3500, 5000),
            "WOT": (5000, 7000),
        }
        for zone, mult in corrections.items():
            rpm_min, rpm_max = zone_rpm[zone]
            action = (
                "increase" if mult > 1.01 else "decrease" if mult < 0.99 else "keep"
            )
            writer.writerow([zone, rpm_min, rpm_max, f"{mult:.4f}", action])

    print()
    print(f"Corrections saved: {corrections_path}")

    # Generate paste-ready VE delta table
    ve_delta_path = output_dir / "VE_Delta_PasteReady.txt"
    with open(ve_delta_path, "w") as f:
        f.write("# VE Correction Delta Table (paste into WinPEP/TuneLab)\n")
        f.write("# Format: RPM zone | Correction multiplier\n")
        f.write("#" + "=" * 50 + "\n")
        for zone, mult in corrections.items():
            rpm_min, rpm_max = zone_rpm[zone]
            delta_pct = (mult - 1) * 100
            f.write(f"{rpm_min:5d}-{rpm_max:5d} RPM: {delta_pct:+5.1f}%\n")

    print(f"Paste-ready saved: {ve_delta_path}")

    print()
    print("=" * 60)
    print("TUNING SUMMARY")
    print("=" * 60)

    # Overall assessment
    lean_zones = sum(1 for z in zone_analysis.values() if z["status"] == "LEAN")
    rich_zones = sum(1 for z in zone_analysis.values() if z["status"] == "RICH")
    ok_zones = sum(1 for z in zone_analysis.values() if z["status"] == "OK")

    if lean_zones > rich_zones:
        print("Overall: Running LEAN - increase fuel/VE")
    elif rich_zones > lean_zones:
        print("Overall: Running RICH - decrease fuel/VE")
    else:
        print("Overall: Mixture looks balanced")

    print(f"  Lean zones: {lean_zones}")
    print(f"  Rich zones: {rich_zones}")
    print(f"  OK zones:   {ok_zones}")

    print()
    print("Next steps:")
    print("  1. Review ve_corrections.csv for zone-by-zone adjustments")
    print("  2. Copy VE_Delta_PasteReady.txt values into your tune")
    print("  3. Re-run dyno pull to verify corrections")
    print("=" * 60)

    return {
        "peak_hp": peak_hp,
        "peak_hp_rpm": peak_hp_rpm,
        "peak_tq": peak_tq,
        "peak_tq_rpm": peak_tq_rpm,
        "corrections": corrections,
        "zone_analysis": zone_analysis,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
    else:
        csv_path = Path("runs/jetdrive_test/run.csv")

    if not csv_path.exists():
        print(f"Error: {csv_path} not found")
        sys.exit(1)

    analyze_run(csv_path)
