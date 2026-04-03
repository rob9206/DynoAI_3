"""
Generate baseline VE tables for a 2017 FXDLS Low Rider S (110" Twin Cam)
with high-flow intake and Bassani 2-1 Road Rage exhaust.

The 110" Screamin' Eagle Twin Cam (CVO motor) has:
  - 1801cc / 110 cubic inches
  - Higher compression than stock TC103 (~10.5:1 vs 9.6:1)
  - Twin-cooled heads (oil + air)
  - Broader torque curve than TC103

Mod effects on VE:
  - High-flow intake: +3-5% VE in mid-to-high MAP (better breathing)
  - 2-1 exhaust (Bassani Road Rage): +2-4% VE in mid-range (torque pipe),
    slight loss at very low RPM due to less backpressure,
    good scavenging effect in 2500-4500 RPM range

Output: CSV files for front and rear cylinder VE tables + AFR targets
"""
import csv
import os
import math
import json

# PVV ECU standard bins (17 MAP columns x 21 RPM rows for Twin Cam)
MAP_BINS = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 85, 95, 105]
RPM_BINS = [
    750, 1000, 1250, 1500, 1750, 2000, 2250, 2500, 2750, 3000,
    3250, 3500, 3750, 4000, 4250, 4500, 4750, 5000, 5250, 5500, 5750
]

# AFR targets for TC110 with free-flowing intake/exhaust
# Slightly richer than bone-stock TC due to less restriction = more airflow = more fuel needed
AFR_TARGETS = {
    10: 14.6,   # Decel overrun
    15: 14.6,   # Decel
    20: 14.6,   # Decel / light coast
    25: 14.6,   # Idle / very light load
    30: 14.6,   # Idle / light cruise
    35: 14.5,   # Light cruise
    40: 14.4,   # Cruise
    45: 14.2,   # Cruise
    50: 14.0,   # Moderate cruise
    55: 13.6,   # Transition to acceleration
    60: 13.4,   # Light acceleration
    65: 13.2,   # Moderate acceleration
    70: 13.0,   # Acceleration
    75: 12.8,   # Heavy acceleration
    85: 12.5,   # WOT - rich for power + cooling
    95: 12.3,   # WOT peak power
    105: 12.1,  # WOT / overrun safety
}


def base_ve(rpm: float, map_kpa: float) -> float:
    """
    Calculate baseline VE for TC110 with high-flow intake + 2-1 exhaust.
    
    Physics-based model:
    - VE increases with MAP (more pressure = more air)
    - VE has a peak in the mid-RPM range (volumetric resonance)
    - At very low RPM: poor intake velocity, low VE
    - At very high RPM: insufficient time to fill cylinder, VE drops
    - 110" motors have good low-end breathing due to displacement
    """
    # Normalize inputs
    rpm_norm = (rpm - 750) / (5750 - 750)     # 0..1
    map_norm = (map_kpa - 10) / (105 - 10)    # 0..1
    
    # Base VE from MAP (linear relationship with diminishing returns at high MAP)
    ve_from_map = 45 + 55 * (1 - math.exp(-2.5 * map_norm))
    
    # RPM volumetric efficiency curve for TC110
    # Peak VE around 3000-3500 RPM (torque peak of the 110")
    # The 2-1 exhaust enhances mid-range scavenging
    rpm_peak = 3250  # shifted slightly up from stock by 2-1 exhaust
    rpm_width = 2000  # broader than stock due to better flowing heads
    rpm_factor = math.exp(-0.5 * ((rpm - rpm_peak) / rpm_width) ** 2)
    
    # Low RPM penalty (poor intake velocity below 1250 RPM)
    if rpm < 1250:
        low_rpm_penalty = 0.85 + 0.15 * ((rpm - 750) / 500)
    else:
        low_rpm_penalty = 1.0
    
    # High RPM falloff (TC110 is not a high-revver, VE drops above 5000)
    if rpm > 5000:
        high_rpm_penalty = 1.0 - 0.12 * ((rpm - 5000) / 750)
    else:
        high_rpm_penalty = 1.0
    
    # Combine: base VE shaped by RPM efficiency.
    # Calibrated to reproduce TC110-style enriched mid-range cells (~110-125%).
    ve = ve_from_map * (0.92 + 0.42 * rpm_factor) * low_rpm_penalty * high_rpm_penalty
    
    # High-flow intake bonus: stronger impact at higher MAP.
    intake_bonus = 4.5 * map_norm ** 0.7
    
    # 2-1 exhaust scavenging bonus: strongest at 2500-4500 RPM, mid-high MAP.
    exhaust_rpm_factor = math.exp(-0.5 * ((rpm - 3500) / 1500) ** 2)
    exhaust_bonus = 5.5 * exhaust_rpm_factor * map_norm ** 0.5
    
    # 2-1 exhaust low-RPM backpressure loss (slight)
    if rpm < 1500 and map_kpa < 40:
        exhaust_loss = -1.5 * (1 - rpm / 1500) * (1 - map_kpa / 40)
    else:
        exhaust_loss = 0
    
    ve = ve + intake_bonus + exhaust_bonus + exhaust_loss
    
    # Clamp to realistic tune limits (modded TC110 can exceed 120%).
    ve = max(15.0, min(130.0, ve))
    
    return round(ve, 1)


def rear_cylinder_offset(rpm: float, map_kpa: float) -> float:
    """
    Rear cylinder VE offset for V-twin.
    
    The rear cylinder on a Harley V-twin typically runs 1-3% different:
    - Hotter (less cooling, tucked behind front)
    - Slightly different intake runner length
    - On TC110 twin-cooled, the difference is smaller than older air-cooled TCs
    - At high RPM/load the rear runs hotter = slightly lower VE (heat expansion)
    - At idle/cruise the difference is minimal
    """
    rpm_norm = (rpm - 750) / (5750 - 750)
    map_norm = (map_kpa - 10) / (105 - 10)
    
    # Rear runs ~1-2% lower VE at high load due to heat
    heat_offset = -1.5 * rpm_norm * map_norm
    
    # Slight intake runner advantage at certain RPMs (constructive interference)
    runner_offset = 0.8 * math.exp(-0.5 * ((rpm - 2750) / 800) ** 2) * map_norm
    
    return round(heat_offset + runner_offset, 1)


def generate_tables():
    """Generate front VE, rear VE, and AFR target tables."""
    
    ve_front = []
    ve_rear = []
    
    for rpm in RPM_BINS:
        front_row = []
        rear_row = []
        for map_kpa in MAP_BINS:
            fve = base_ve(rpm, map_kpa)
            rve = round(fve + rear_cylinder_offset(rpm, map_kpa), 1)
            rve = max(15.0, min(130.0, rve))
            front_row.append(fve)
            rear_row.append(rve)
        ve_front.append(front_row)
        ve_rear.append(rear_row)
    
    return ve_front, ve_rear


def write_csv(filepath, table, rpm_bins, map_bins, title):
    """Write a VE or AFR table as CSV."""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([title])
        writer.writerow(['RPM \\ MAP (kPa)'] + [str(m) for m in map_bins])
        for i, rpm in enumerate(rpm_bins):
            writer.writerow([str(rpm)] + [str(v) for v in table[i]])


def write_afr_csv(filepath, afr_targets):
    """Write AFR target table as CSV."""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['AFR Targets - 2017 FXDLS TC110 (High-Flow Intake + Bassani 2-1)'])
        writer.writerow(['MAP (kPa)', 'Target AFR'])
        for map_kpa in sorted(afr_targets.keys()):
            writer.writerow([str(map_kpa), str(afr_targets[map_kpa])])


def print_table(name, table, rpm_bins, map_bins):
    """Pretty-print a table to console."""
    print(f"\n{'=' * 80}")
    print(f"  {name}")
    print(f"  2017 FXDLS Low Rider S | TC110 (1801cc/110ci)")
    print(f"  Mods: High-Flow Intake + Bassani 2-1 Road Rage Exhaust")
    print(f"{'=' * 80}")
    
    # Header
    header = f"{'RPM':>5} |"
    for m in map_bins:
        header += f" {m:5}"
    print(header)
    print("-" * len(header))
    
    for i, rpm in enumerate(rpm_bins):
        row = f"{rpm:5} |"
        for val in table[i]:
            row += f" {val:5.1f}"
        print(row)
    print()


def main():
    ve_front, ve_rear = generate_tables()
    
    # Print tables to console
    print_table("FRONT CYLINDER VE TABLE (%)", ve_front, RPM_BINS, MAP_BINS)
    print_table("REAR CYLINDER VE TABLE (%)", ve_rear, RPM_BINS, MAP_BINS)
    
    # Print AFR targets
    print(f"\n{'=' * 40}")
    print(f"  AFR TARGETS")
    print(f"{'=' * 40}")
    print(f"{'MAP (kPa)':>10} | {'Target AFR':>10}")
    print("-" * 25)
    for m in sorted(AFR_TARGETS.keys()):
        print(f"{m:>10} | {AFR_TARGETS[m]:>10.1f}")
    
    # Write CSV files
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'output', 'fxdls_baseline')
    os.makedirs(output_dir, exist_ok=True)
    
    write_csv(
        os.path.join(output_dir, 'VE_Front_Baseline_FXDLS.csv'),
        ve_front, RPM_BINS, MAP_BINS,
        'Front Cylinder VE (%) - 2017 FXDLS TC110 + High-Flow Intake + Bassani 2-1'
    )
    write_csv(
        os.path.join(output_dir, 'VE_Rear_Baseline_FXDLS.csv'),
        ve_rear, RPM_BINS, MAP_BINS,
        'Rear Cylinder VE (%) - 2017 FXDLS TC110 + High-Flow Intake + Bassani 2-1'
    )
    write_afr_csv(
        os.path.join(output_dir, 'AFR_Targets_FXDLS.csv'),
        AFR_TARGETS
    )
    
    # Also write a JSON summary for import into DynoAI
    summary = {
        'bike': {
            'year': 2017,
            'model': 'FXDLS Low Rider S',
            'engine': 'Twin Cam 110 (Screamin Eagle)',
            'displacement_ci': 110,
            'displacement_cc': 1801,
        },
        'mods': [
            'High-flow air cleaner',
            'Bassani 2-1 Road Rage exhaust',
        ],
        'calibration_source': '16D110002401',
        'grid': {
            'rpm_bins': RPM_BINS,
            'map_bins': MAP_BINS,
        },
        'afr_targets': AFR_TARGETS,
        've_front': ve_front,
        've_rear': ve_rear,
        'notes': (
            'Baseline VE tables generated for TC110 with breathing mods. '
            'High-flow intake adds ~3% VE at high MAP. '
            'Bassani 2-1 adds ~3-4% mid-range scavenging (2500-4500 RPM). '
            'Rear cylinder runs ~1-2% lower VE at high load due to heat soak. '
            'These are STARTING POINT tables - use DynoAI auto-tune to refine '
            'with actual dyno data.'
        ),
    }
    
    with open(os.path.join(output_dir, 'baseline_config.json'), 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nFiles written to: {os.path.abspath(output_dir)}")
    print(f"  - VE_Front_Baseline_FXDLS.csv")
    print(f"  - VE_Rear_Baseline_FXDLS.csv")
    print(f"  - AFR_Targets_FXDLS.csv")
    print(f"  - baseline_config.json")


if __name__ == '__main__':
    main()
