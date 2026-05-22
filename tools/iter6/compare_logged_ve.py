"""Compare logged VE values and adaptive fuel factor between iter_3 and iter_6 pulls."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

FOLDER = Path(r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus")

ITER3_FILES = ["6th gear load then wot_4.txt", "6th gear load then wot_7.txt"]
ITER6_FILES = ["PV_Logfile_5.csv_27.txt", "PV_Logfile_5.csv_28.txt"]

RPM = "(Harley - ECU Type 14 SW Level 141) Engine Speed"
MAP_C = "(Harley - ECU Type 14 SW Level 141) Manifold Absolute Pressure"
TPS = "(Harley - ECU Type 14 SW Level 141) Throttle Position"
VEF = "(Harley - ECU Type 14 SW Level 141) VE Front"
VER = "(Harley - ECU Type 14 SW Level 141) VE Rear"
VEFN = "(Harley - ECU Type 14 SW Level 141) VE New Front"
VERN = "(Harley - ECU Type 14 SW Level 141) VE New Rear"
AFFF = "(Harley - ECU Type 14 SW Level 141) Front Adaptive Fuel Factor"
AFFR = "(Harley - ECU Type 14 SW Level 141) Rear Adaptive Fuel Factor"
DAFR = "(Harley - ECU Type 14 SW Level 141) Desired Air/Fuel"
HP = "(DWRT CPU) Power"

BINS = [(3500, 4000), (4000, 4500), (4500, 5000), (5000, 5500), (5500, 6000)]


def report_file(p: Path) -> None:
    df = pd.read_csv(p, encoding="utf-8", encoding_errors="replace", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    def get(col: str) -> pd.Series:
        return pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series([float("nan")] * len(df))

    rpm = get(RPM) * 1000
    mapk = get(MAP_C)
    tps = get(TPS)
    vef = get(VEF)
    ver = get(VER)
    vefn = get(VEFN)
    vern = get(VERN)
    afff = get(AFFF)
    affr = get(AFFR)
    dafr = get(DAFR)
    hp = get(HP)

    print(f"\n  {p.name}")
    print(
        f"    {'rpm bin':<11s} {'n':>3s} {'rpm':>5s} {'map':>5s} "
        f"{'VEf':>5s} {'VEr':>5s} {'VEnewF':>6s} {'VEnewR':>6s} "
        f"{'AFFf':>6s} {'AFFr':>6s} {'desAFR':>6s} {'hp':>5s}"
    )
    for lo, hi in BINS:
        m = (rpm >= lo) & (rpm < hi) & (mapk >= 85) & (tps >= 80)
        if not m.any():
            continue
        def avg(s: pd.Series) -> float:
            v = s[m]
            return float(v.mean()) if v.notna().any() else math.nan
        print(
            f"    {lo}-{hi:<6d} {int(m.sum()):>3d} {avg(rpm):>5.0f} {avg(mapk):>5.1f} "
            f"{avg(vef):>5.1f} {avg(ver):>5.1f} {avg(vefn):>6.1f} {avg(vern):>6.1f} "
            f"{avg(afff):>6.3f} {avg(affr):>6.3f} {avg(dafr):>6.2f} {avg(hp):>5.1f}"
        )


def main() -> int:
    print("=== iter_3 baseline (yesterday, 91-92 hp) ===")
    for fn in ITER3_FILES:
        p = FOLDER / fn
        if p.exists():
            report_file(p)
    print("\n=== iter_6 today (these pulls) ===")
    for fn in ITER6_FILES:
        p = FOLDER / fn
        if p.exists():
            report_file(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
