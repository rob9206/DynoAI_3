#!/usr/bin/env python
"""Quick script to generate dense dyno test data."""
import csv
import math
import random
from pathlib import Path

rows, fs_hz = 12000, 20
rpm_min, rpm_max = 1500, 5500
map_min, map_max = 35, 95
rnd = random.Random(42)
dt, t = 1.0/fs_hz, 0.0
rpm_center, rpm_amp = (rpm_min+rpm_max)/2, (rpm_max-rpm_min)/2
map_center, map_amp = (map_min+map_max)/2, (map_max-map_min)/2
sweep_period = (rows/fs_hz)/6
rpm_period, map_period = sweep_period*0.8, sweep_period*1.2

output = Path("dense_dyno_test.csv")
with open(output, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['rpm','map_kpa','torque','ve_f','ve_r','spark_f','spark_r',
                'afr_cmd_f','afr_cmd_r','afr_meas_f','afr_meas_r','iat','knock','vbatt','tps'])
    for _ in range(rows):
        t += dt
        rpm = rpm_center + rpm_amp*math.sin(2*math.pi*t/rpm_period) + 150*math.sin(2*math.pi*t/(rpm_period/4.3))
        rpm = max(rpm_min, min(rpm_max, rpm))
        mapk = map_center + map_amp*math.sin(2*math.pi*t/map_period) + map_amp*0.3*math.sin(2*math.pi*t/(map_period/3))
        mapk = max(map_min, min(map_max, mapk))
        afr_t = 13.0 - 0.3*(mapk-map_min)/(map_max-map_min)
        afr_f = afr_t + 0.15*math.sin(2*math.pi*(t-0.2)/11.3) + rnd.gauss(0, 0.08)
        afr_r = afr_t + 0.20*math.sin(2*math.pi*(t-0.25)/12.1) + rnd.gauss(0, 0.10)
        rpm_fac = 1.0 - abs(rpm-3500)/2500
        torque = 60 + 50*rpm_fac*(mapk-map_min)/(map_max-map_min) + rnd.gauss(0, 2.5)
        iat = 85 + (t/(rows/fs_hz))*35 + 5*math.sin(2*math.pi*t/60) + rnd.gauss(0, 1.5)
        knock = 1 if mapk>88 and rpm>4200 and rnd.random()<0.02*((mapk-88)/10)*((rpm-4200)/1000) else 0
        ve_f, ve_r = 58+40*rpm_fac, 56+40*rpm_fac
        spark_f = 20 + 15*(rpm-rpm_min)/(rpm_max-rpm_min) - knock*2
        w.writerow([round(rpm,2), round(mapk,2), round(torque,2), round(ve_f,1), round(ve_r,1), 
                    round(spark_f,1), round(spark_f-2,1), round(afr_t,2), round(afr_t,2), 
                    round(afr_f,2), round(afr_r,2), round(iat,1), knock, 
                    round(13.8+rnd.gauss(0,0.05),2), 
                    round(max(0,min(100,10+85*(mapk-map_min)/(map_max-map_min)+rnd.gauss(0,2))),1)])

print(f"Generated {output} with {rows} rows")
print(f"  RPM: {rpm_min}-{rpm_max}")
print(f"  MAP: {map_min}-{map_max} kPa")
print(f"  Duration: {rows/fs_hz/60:.1f} minutes @ {fs_hz}Hz")

