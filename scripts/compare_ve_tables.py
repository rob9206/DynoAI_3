"""Compare model-generated VE tables vs actual PVV extraction."""
import math

MAP_BINS = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 85, 95, 105]
RPM_BINS = [750,1000,1250,1500,1750,2000,2250,2500,2750,3000,3250,3500,3750,4000,4250,4500,4750,5000,5250,5500,5750]

def base_ve(rpm, map_kpa):
    rpm_norm = (rpm - 750) / (5750 - 750)
    map_norm = (map_kpa - 10) / (105 - 10)
    ve_from_map = 45 + 55 * (1 - math.exp(-2.5 * map_norm))
    rpm_factor = math.exp(-0.5 * ((rpm - 3250) / 2000) ** 2)
    low_rpm_penalty = (0.85 + 0.15 * ((rpm - 750) / 500)) if rpm < 1250 else 1.0
    high_rpm_penalty = (1.0 - 0.12 * ((rpm - 5000) / 750)) if rpm > 5000 else 1.0
    ve = ve_from_map * (0.75 + 0.30 * rpm_factor) * low_rpm_penalty * high_rpm_penalty
    intake_bonus = 3.0 * map_norm ** 0.7
    exhaust_rpm_factor = math.exp(-0.5 * ((rpm - 3500) / 1500) ** 2)
    exhaust_bonus = 3.5 * exhaust_rpm_factor * map_norm ** 0.5
    exhaust_loss = -1.5 * (1 - rpm / 1500) * (1 - map_kpa / 40) if (rpm < 1500 and map_kpa < 40) else 0
    ve = ve + intake_bonus + exhaust_bonus + exhaust_loss
    return round(max(15.0, min(115.0, ve)), 1)

gen_front = [[base_ve(rpm, m) for m in MAP_BINS] for rpm in RPM_BINS]

PVV_MAP_KPA = [10.5,15.2,20.0,25.1,29.8,35.2,40.0,45.0,50.1,54.9,60.3,65.0,70.1,74.8,85.0,94.8,104.3]
PVV_RPM = [750,1000,1125,1250,1500,1750,2000,2250,2500,2750,3000,3500,4000,4500,5000,5500,6000,6500,7000,7500,8000]
PVV_FRONT = [
    [70,70,80,80,80,80,80,80,80,80,80,80,80,80,80,80,82.5],
    [70.5,70.5,80,85.5,80,88.5,87.5,88.5,85.5,85,87.5,86,87.5,83,83,83,83],
    [72.5,72.5,80,82,83,83,82,83,83,82,84,82.5,85,84,86,83,85.5],
    [76,75.5,82.5,81,85.5,87,86.5,86,87.5,87,87.5,88.5,89.5,89.5,88,92.5,95],
    [81.5,80.5,85.5,82.5,88.5,90,91.5,94,96.5,97,98,98.5,98.5,98.5,98,105,108],
    [83,82,87.5,98,100,104.5,106.5,108.5,108.5,106.5,108,106.5,108,107.5,108,109.5,113],
    [78.5,78.5,95,102.5,105,110.5,112.5,108,107,107,104,103,102.5,101,97.5,94,96.5],
    [80.5,80.5,90.5,94,96,97,98,92,92.5,89,89.5,88.5,86.5,83.5,82,85,87.5],
    [83.5,84,93.5,95.5,94.5,93.5,93.5,92.5,90,88,87.5,86.5,86,85.5,86.5,92,95],
    [81,81,95,96,100,100,101,102,97,98,96,96,94,95.5,93.5,101.5,104.5],
    [75.5,75.5,85,95,98,102.5,108.5,110,110,110,107.5,106,103.5,102,101,113,116.5],
    [73,73,97.5,106,116.5,119.5,125.5,119.5,117.5,117.5,112,109.5,106.5,104.5,103.5,110.5,114],
    [71.5,72,74,81,104.5,114,122.5,123.5,118.5,116.5,109.5,107.5,103.5,100.5,101.5,111.5,115],
    [71,71.5,68,73,84.5,96.5,104,110,107.5,104.5,101.5,98,95.5,94,95.5,103.5,106.5],
    [71,71.5,68.5,76,84.5,90.5,98.5,106.5,102,100,98,94.5,93,91,91,96,98.5],
    [71,71,73,78,82.5,95.5,97,101,98.5,96.5,94,92.5,92.5,91.5,91,92.5,95.5],
    [71,71,71.5,78,82,89,92.5,96.5,92.5,91.5,88,86.5,86,84,82.5,86,88.5],
]

shared_rpms = [750,1000,1250,1500,1750,2000,2250,2500,2750,3000,3500,4000,4500,5000,5500]

print("FRONT CYLINDER VE: Generated (model) vs Actual (PVV)")
print("Positive = model higher than actual, Negative = model lower")
print("=" * 120)

hdr = f"{'RPM':>5} |"
for i in range(17):
    hdr += f"  {MAP_BINS[i]:>3}kPa"
print(hdr)
print("-" * 120)

diffs_all = []
for rpm in shared_rpms:
    gen_idx = RPM_BINS.index(rpm)
    pvv_idx = PVV_RPM.index(rpm)
    row = f"{rpm:>5} |"
    for c in range(17):
        g = gen_front[gen_idx][c]
        p = PVV_FRONT[pvv_idx][c]
        diff = g - p
        diffs_all.append((rpm, MAP_BINS[c], g, p, diff))
        sign = "+" if diff > 0 else ""
        row += f" {sign}{diff:>5.1f}"
    print(row)

print()
d_vals = [d[4] for d in diffs_all]
abs_vals = [abs(d[4]) for d in diffs_all]
print(f"Cells compared: {len(d_vals)}")
print(f"Mean difference (model - actual): {sum(d_vals)/len(d_vals):+.1f}%")
print(f"Mean absolute error: {sum(abs_vals)/len(abs_vals):.1f}%")
print(f"Max overestimate: {max(d_vals):+.1f}%")
print(f"Max underestimate: {min(d_vals):+.1f}%")
stddev = (sum((d - sum(d_vals)/len(d_vals))**2 for d in d_vals)/len(d_vals))**0.5
print(f"Std dev: {stddev:.1f}%")

# Worst cells
print()
print("TOP 10 LARGEST ERRORS:")
print("-" * 60)
sorted_by_err = sorted(diffs_all, key=lambda x: abs(x[4]), reverse=True)
for rpm, m, g, p, diff in sorted_by_err[:10]:
    print(f"  RPM {rpm:>5}, MAP {m:>3} kPa: model={g:>5.1f}, actual={p:>5.1f}, diff={diff:+.1f}%")

# Zone breakdown
print()
print("ZONE BREAKDOWN:")
print("-" * 65)
zones = {}
zone_defs = [
    ("Idle/Decel (MAP<30)", lambda r,m: m < 30),
    ("Cruise (MAP 30-70)", lambda r,m: 30 <= m <= 70),
    ("Part Throttle (MAP 70-95)", lambda r,m: 70 < m <= 95),
    ("WOT (MAP 95+)", lambda r,m: m > 95),
    ("Low RPM (<1500)", lambda r,m: r < 1500),
    ("Mid RPM (1500-3500)", lambda r,m: 1500 <= r <= 3500),
    ("High RPM (3500+)", lambda r,m: r > 3500),
]

for name, cond in zone_defs:
    vals = [d[4] for d in diffs_all if cond(d[0], d[1])]
    if vals:
        mean = sum(vals) / len(vals)
        mae = sum(abs(v) for v in vals) / len(vals)
        worst = max(vals, key=abs)
        print(f"  {name:<30s}: mean {mean:+5.1f}%  MAE {mae:4.1f}%  worst {worst:+5.1f}%  n={len(vals)}")

# AFR comparison
print()
print("=" * 80)
print("AFR TARGETS: Generated vs Actual")
print("=" * 80)
gen_afr = {10:14.6, 15:14.6, 20:14.6, 25:14.6, 30:14.6, 35:14.5, 40:14.4, 45:14.2, 50:14.0, 55:13.6, 60:13.4, 65:13.2, 70:13.0, 75:12.8, 85:12.5, 95:12.3, 105:12.1}
# Actual PVV AFR is a 2D table. Simplify: use the 2500 RPM row as representative cruise
# PVV AFR MAP bins (kPa): 20, 30.1, 34.9, 40, 50.1, 59.9, 70.1, 74.8, 79.9, 90.1, 99.9...
pvv_afr_maps = [20, 30, 35, 40, 50, 60, 70, 75, 80, 90, 100]
pvv_afr_2500 = [13.08, 14.37, 14.37, 14.37, 14.37, 14.37, 14.37, 14.39, 13.08, 12.88, 12.88]
pvv_afr_idle = [14.29, 14.29, 14.29, 14.29, 13.08, 13.08, 13.08, 13.08, 13.08, 12.88, 12.88]

print(f"{'MAP kPa':>8} | {'Generated':>10} | {'PVV @2500':>10} | {'PVV @Idle':>10} | {'Notes'}")
print("-" * 75)
for i, m in enumerate(pvv_afr_maps):
    gen_val = gen_afr.get(m, "-")
    pvv_cruise = pvv_afr_2500[i]
    pvv_idle_val = pvv_afr_idle[i]
    note = ""
    if isinstance(gen_val, float):
        diff = gen_val - pvv_cruise
        if abs(diff) > 0.5:
            note = f"<< {diff:+.2f} off cruise"
    print(f"{m:>8} | {gen_val:>10} | {pvv_cruise:>10} | {pvv_idle_val:>10} | {note}")
