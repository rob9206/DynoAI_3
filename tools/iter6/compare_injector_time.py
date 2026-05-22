"""Compare injector pulse width and MAP at matched RPM/TPS between iter_3 and iter_6 pulls."""

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
LC2 = "(DWRT CPU) LC2 Volts Petrol AFR2"
INJF = "(Harley - ECU Type 14 SW Level 141) Injector Time Front"
INJR = "(Harley - ECU Type 14 SW Level 141) Injector Time Rear"
HP = "(DWRT CPU) Power"
ATMO_P = "(DWRT ATMO) Pressure"
ATMO_T = "(DWRT ATMO) Temperature 1"
IAT = "(Harley - ECU Type 14 SW Level 141) Intake Air Temperature"

BINS = [(3500, 4000), (4000, 4500), (4500, 5000), (5000, 5500), (5500, 6000)]


def load(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p, encoding="utf-8", encoding_errors="replace", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def stats(df: pd.DataFrame, lo: int, hi: int) -> dict[str, float]:
    rpm = pd.to_numeric(df[RPM], errors="coerce") * 1000
    mapk = pd.to_numeric(df[MAP_C], errors="coerce")
    tps = pd.to_numeric(df[TPS], errors="coerce")
    lc2 = pd.to_numeric(df[LC2], errors="coerce")
    injf = pd.to_numeric(df[INJF], errors="coerce")
    injr = pd.to_numeric(df[INJR], errors="coerce")
    hp = pd.to_numeric(df[HP], errors="coerce")
    iat = pd.to_numeric(df[IAT], errors="coerce") if IAT in df.columns else pd.Series(dtype=float)

    m = (rpm >= lo) & (rpm < hi) & (mapk >= 85) & (tps >= 80)
    if not m.any():
        return {}
    cleanv = lc2[m & (lc2 > 5) & (lc2 < 22.38)]
    return {
        "n": int(m.sum()),
        "rpm_avg": float(rpm[m].mean()),
        "map_avg": float(mapk[m].mean()),
        "tps_avg": float(tps[m].mean()),
        "lc2_avg": float(cleanv.mean()) if len(cleanv) else math.nan,
        "injf_ms_avg": float(injf[m].mean()),
        "injr_ms_avg": float(injr[m].mean()),
        "hp_avg": float(hp[m].mean()),
        "iat_avg": float(iat[m].mean()) if len(iat) and iat[m].notna().any() else math.nan,
    }


def atmo(df: pd.DataFrame) -> tuple[float, float]:
    p = pd.to_numeric(df[ATMO_P], errors="coerce") if ATMO_P in df.columns else pd.Series(dtype=float)
    t = pd.to_numeric(df[ATMO_T], errors="coerce") if ATMO_T in df.columns else pd.Series(dtype=float)
    return (
        float(p.mean()) if len(p) and p.notna().any() else math.nan,
        float(t.mean()) if len(t) and t.notna().any() else math.nan,
    )


def report(label: str, files: list[str]) -> None:
    print(f"\n=== {label} ===")
    for fn in files:
        p = FOLDER / fn
        if not p.exists():
            print(f"  MISSING: {fn}")
            continue
        df = load(p)
        ap, at = atmo(df)
        print(f"  {fn}  atmo P={ap:.2f} kPa T={at:.1f} F")
        print(f"    {'rpm bin':<11s} {'n':>4s} {'rpm':>6s} {'map':>5s} {'tps':>5s} {'lc2':>5s} {'injF':>6s} {'injR':>6s} {'hp':>6s} {'iat':>5s}")
        for lo, hi in BINS:
            s = stats(df, lo, hi)
            if not s:
                continue
            print(
                f"    {lo}-{hi:<6d} {s['n']:>4d} {s['rpm_avg']:>6.0f} "
                f"{s['map_avg']:>5.1f} {s['tps_avg']:>5.0f} "
                f"{s['lc2_avg']:>5.2f} {s['injf_ms_avg']:>6.2f} {s['injr_ms_avg']:>6.2f} "
                f"{s['hp_avg']:>6.1f} {s['iat_avg']:>5.0f}"
            )


def main() -> int:
    report("iter_3 baseline (yesterday, 91-92 hp)", ITER3_FILES)
    report("iter_6 today", ITER6_FILES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
