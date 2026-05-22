"""READ-ONLY audit script: extract AFR2, pulse width, knock retard, MAP, duty cycle estimates from seanbike running logs.
This is a one-off diagnostic; do not commit results as canonical state.
"""
from __future__ import annotations
import csv
import statistics
from pathlib import Path

PATHS = [
    r"C:\CommmandCenter\Customer_Files\seanbike\runnning_9.txt",
    r"C:\CommmandCenter\Customer_Files\seanbike\runnning_10.txt",
    r"C:\CommmandCenter\Customer_Files\seanbike\runnning_11.txt",
    r"C:\CommmandCenter\Customer_Files\seanbike\runnning_12.txt",
    r"C:\CommmandCenter\Customer_Files\seanbike\runnning_13.txt",
]

ECU = "(Harley - ECU Type 20 SW Level 357)"

RPM_C = f"{ECU} Engine Speed"
TPS_C = f"{ECU} Throttle Position"
MAP_C = f"{ECU} Manifold Absolute Pressure"
AFR_C = "(DWRT CPU) LC2 Volts Petrol AFR2"
DES_LAM_C = f"{ECU} Desired Lambda"
IPF_C = f"{ECU} Injector Time Front"
IPR_C = f"{ECU} Injector Time Rear"
KNKF_C = f"{ECU} Front Spark Knock Retard"
KNKR_C = f"{ECU} Rear Spark Knock Retard"
VEF_C = f"{ECU} VE Front"
VER_C = f"{ECU} VE Rear"
ECT_C = f"{ECU} Engine Temperature"
BATTV_C = f"{ECU} Battery Voltage"


def pct(vals, q):
    if not vals:
        return float("nan")
    s = sorted(vals)
    i = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[i]


def fmt(x, n=2):
    try:
        return f"{x:.{n}f}"
    except Exception:
        return "NA"


for pth in PATHS:
    p = Path(pth)
    if not p.exists():
        print("MISSING", pth)
        continue
    with p.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        header = [h.strip() for h in next(reader)]
        idx = {h: i for i, h in enumerate(header)}

        all_rpm = []
        all_tps = []
        all_ipf = []
        all_ipr = []
        all_afr = []
        all_map = []
        ect = []
        batt = []
        lr_afr = []
        lr_ipf = []
        lr_ipr = []
        lr_knkF = []
        lr_knkR = []
        lr_rpm = []
        lr_map = []
        lr_veF = []
        lr_veR = []
        lr_des_lam = []

        def fv(row, c):
            try:
                return float(row[idx[c]].strip() or "nan")
            except Exception:
                return float("nan")

        for row in reader:
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))
            rpm = fv(row, RPM_C)
            tps = fv(row, TPS_C)
            mapv = fv(row, MAP_C)
            afr = fv(row, AFR_C)
            des = fv(row, DES_LAM_C)
            ipf = fv(row, IPF_C)
            ipr = fv(row, IPR_C)
            kf = fv(row, KNKF_C)
            kr = fv(row, KNKR_C)
            vef = fv(row, VEF_C)
            ver = fv(row, VER_C)
            ec = fv(row, ECT_C)
            bv = fv(row, BATTV_C)
            if rpm == rpm:
                all_rpm.append(rpm)
            if tps == tps:
                all_tps.append(tps)
            if ipf == ipf:
                all_ipf.append(ipf)
            if ipr == ipr:
                all_ipr.append(ipr)
            if afr == afr:
                all_afr.append(afr)
            if mapv == mapv:
                all_map.append(mapv)
            if ec == ec:
                ect.append(ec)
            if bv == bv:
                batt.append(bv)
            if rpm == rpm and tps == tps and rpm >= 3.0 and tps >= 50:
                if afr == afr:
                    lr_afr.append(afr)
                if ipf == ipf:
                    lr_ipf.append(ipf)
                if ipr == ipr:
                    lr_ipr.append(ipr)
                if kf == kf:
                    lr_knkF.append(kf)
                if kr == kr:
                    lr_knkR.append(kr)
                if vef == vef:
                    lr_veF.append(vef)
                if ver == ver:
                    lr_veR.append(ver)
                if mapv == mapv:
                    lr_map.append(mapv)
                lr_rpm.append(rpm)
                if des == des:
                    lr_des_lam.append(des)

    print()
    print("=== " + p.name + " ===")
    print(f"  rows: rpm n={len(all_rpm)} ipf n={len(all_ipf)} afr n={len(all_afr)}")
    if ect:
        print(f"  ECT med: {fmt(statistics.median(ect),1)} F")
    if batt:
        print(f"  BattV med: {fmt(statistics.median(batt),2)} V")
    if all_rpm:
        print(f"  RPM max full: {fmt(max(all_rpm),0)}  TPS max: {fmt(max(all_tps),0)}  MAP max: {fmt(max(all_map),1)}")
    if all_ipf:
        print(f"  IPF (ms) full p95: {fmt(pct(all_ipf,0.95))}  max: {fmt(max(all_ipf))}")
    if all_ipr:
        print(f"  IPR (ms) full p95: {fmt(pct(all_ipr,0.95))}  max: {fmt(max(all_ipr))}")
    print(f"  LOADED (rpm>=3000 & tps>=50) samples: {len(lr_afr)}")
    if lr_afr:
        print(f"    AFR2 p50={fmt(statistics.median(lr_afr))} p10={fmt(pct(lr_afr,0.10))} p90={fmt(pct(lr_afr,0.90))} max={fmt(max(lr_afr))}")
    if lr_des_lam:
        med = statistics.median(lr_des_lam)
        print(f"    Desired Lambda p50={fmt(med,3)} -> commanded AFR p50 {fmt(med*14.7)}")
    if lr_ipf:
        print(f"    Front IPT(ms) p50={fmt(statistics.median(lr_ipf))} p95={fmt(pct(lr_ipf,0.95))} max={fmt(max(lr_ipf))}")
    if lr_ipr:
        print(f"    Rear  IPT(ms) p50={fmt(statistics.median(lr_ipr))} p95={fmt(pct(lr_ipr,0.95))} max={fmt(max(lr_ipr))}")
    if lr_rpm:
        # rpm reported in k-RPM in these logs
        rpm_p95_k = pct(lr_rpm, 0.95)
        rpm_max_k = max(lr_rpm)
        rpm_p95 = rpm_p95_k * 1000.0
        rpm_max = rpm_max_k * 1000.0
        cyc_p95 = 120000.0 / rpm_p95 if rpm_p95 > 0 else 0
        cyc_max = 120000.0 / rpm_max if rpm_max > 0 else 0
        print(f"    RPM in load (RPM) p50={fmt(statistics.median(lr_rpm)*1000,0)} p95={fmt(rpm_p95,0)} max={fmt(rpm_max,0)}")
        print(f"    Cycle time (4-stroke per cyl) @ p95rpm: {fmt(cyc_p95)} ms ; @ maxrpm: {fmt(cyc_max)} ms")
        if lr_ipf:
            dc_front_p95 = pct(lr_ipf, 0.95) / cyc_p95 * 100 if cyc_p95 > 0 else 0
            dc_front_max = max(lr_ipf) / cyc_max * 100 if cyc_max > 0 else 0
            print(f"    DUTY Front p95: {fmt(dc_front_p95,1)}%  max: {fmt(dc_front_max,1)}%")
        if lr_ipr:
            dc_rear_p95 = pct(lr_ipr, 0.95) / cyc_p95 * 100 if cyc_p95 > 0 else 0
            dc_rear_max = max(lr_ipr) / cyc_max * 100 if cyc_max > 0 else 0
            print(f"    DUTY Rear  p95: {fmt(dc_rear_p95,1)}%  max: {fmt(dc_rear_max,1)}%")
    if lr_knkF:
        print(f"    Knock Retard Front max: {fmt(max(lr_knkF))}  p95: {fmt(pct(lr_knkF,0.95))}")
    if lr_knkR:
        print(f"    Knock Retard Rear  max: {fmt(max(lr_knkR))}  p95: {fmt(pct(lr_knkR,0.95))}")
    if lr_veF:
        print(f"    Commanded VE Front in load p50={fmt(statistics.median(lr_veF),1)} max={fmt(max(lr_veF),1)}")
    if lr_veR:
        print(f"    Commanded VE Rear  in load p50={fmt(statistics.median(lr_veR),1)} max={fmt(max(lr_veR),1)}")
    if lr_map:
        print(f"    MAP (kPa) in load p50={fmt(statistics.median(lr_map),1)} max={fmt(max(lr_map),1)}")
