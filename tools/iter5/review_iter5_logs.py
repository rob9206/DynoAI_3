"""Detailed review of post-flash 4th-gear pulls (PV_Logfile_5.csv_NN.txt)."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

FOLDER = Path(r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus")
DEFAULT_INDICES = [20, 21, 22, 23, 24]

COLS = {
    "time": "Time",
    "hp": "(DWRT CPU) Power",
    "tq": "(DWRT CPU) Torque",
    "rpm": "(Harley - ECU Type 14 SW Level 141) Engine Speed",
    "drpm": "(DWRT CPU) Engine RPM",
    "map": "(Harley - ECU Type 14 SW Level 141) Manifold Absolute Pressure",
    "tps": "(Harley - ECU Type 14 SW Level 141) Throttle Position",
    "lc2": "(DWRT CPU) LC2 Volts Petrol AFR2",
    "gear": "(DWRT CPU) Gear Ratio",
    "speed": "(DWRT CPU) Speed",
    "injf": "(Harley - ECU Type 14 SW Level 141) Injector Time Front",
    "injr": "(Harley - ECU Type 14 SW Level 141) Injector Time Rear",
    "kf": "(Harley - ECU Type 14 SW Level 141) Front Spark Knock Retard",
    "kr": "(Harley - ECU Type 14 SW Level 141) Rear Spark Knock Retard",
    "cht": "(Harley - ECU Type 14 SW Level 141) Engine Temperature",
    "iat": "(Harley - ECU Type 14 SW Level 141) Intake Air Temperature",
}


def safe_max(s: pd.Series) -> float:
    return float(s.max()) if s.notna().any() else math.nan


def safe_min(s: pd.Series) -> float:
    return float(s.min()) if s.notna().any() else math.nan


def safe_mean(s: pd.Series) -> float:
    return float(s.mean()) if s.notna().any() else math.nan


def review(p: Path) -> None:
    df = pd.read_csv(p, encoding="utf-8", encoding_errors="replace", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    for c in COLS.values():
        if c not in df.columns:
            df[c] = float("nan")
    g = lambda k: pd.to_numeric(df[COLS[k]], errors="coerce")
    t = g("time")
    hp = g("hp")
    tq = g("tq")
    rpm = g("rpm") * 1000.0
    mapk = g("map")
    tps = g("tps")
    lc2 = g("lc2")
    gear = g("gear")
    speed = g("speed")
    injf = g("injf")
    injr = g("injr")
    kf = g("kf")
    kr = g("kr")
    cht = g("cht")
    iat = g("iat")

    wot = (rpm >= 1200) & (rpm <= 7000) & (mapk >= 85) & (tps >= 80)
    dutyf = injf * rpm / 1200.0
    dutyr = injr * rpm / 1200.0

    print("\n=== %s rows=%d wot_rows=%d ===" % (p.name, len(df), int(wot.sum())))
    print(
        "  duration=%.2fs  rpm %.0f-%.0f  speed %.1f-%.1f  gear avg=%.1f"
        % (
            float(t.max() - t.min()),
            safe_min(rpm),
            safe_max(rpm),
            safe_min(speed),
            safe_max(speed),
            float(gear[wot].mean()) if wot.any() and gear[wot].notna().any() else math.nan,
        )
    )
    print(
        "  cht max=%.0fF  iat max=%.0fF  knock max F=%.1f R=%.1f"
        % (safe_max(cht), safe_max(iat), safe_max(kf), safe_max(kr))
    )

    if wot.any() and hp[wot].notna().any():
        i = hp[wot].idxmax()
        print(
            "  PEAK WOT HP=%.2f TQ=%.2f @ rpm=%.0f map=%.1f tps=%.0f lc2=%.2f speed=%.1f"
            % (
                float(hp.loc[i]),
                float(tq.loc[i]) if tq.notna().any() else math.nan,
                float(rpm.loc[i]),
                float(mapk.loc[i]),
                float(tps.loc[i]),
                float(lc2.loc[i]),
                float(speed.loc[i]) if speed.notna().any() else math.nan,
            )
        )
    band = lc2[wot & (rpm >= 3000) & (rpm <= 5500) & (lc2 > 5) & (lc2 < 22.38)]
    print(
        "  WOT LC2 3000-5500 avg=%.2f  pegged%%=%.1f"
        % (
            float(band.mean()) if len(band) else math.nan,
            float((lc2 >= 22.38).mean() * 100),
        )
    )
    print(
        "  WOT inj duty max F=%.1f%% R=%.1f%%   wot duration=%.2fs"
        % (
            float(dutyf[wot].max()) if wot.any() and dutyf[wot].notna().any() else math.nan,
            float(dutyr[wot].max()) if wot.any() and dutyr[wot].notna().any() else math.nan,
            float(t[wot].max() - t[wot].min())
            if wot.any() and t[wot].notna().any()
            else math.nan,
        )
    )
    rpm_dot = rpm.diff() / t.diff()
    if wot.any() and rpm_dot[wot].notna().any():
        print(
            "  RPM rate at WOT: median=%.0f max=%.0f rpm/s"
            % (float(rpm_dot[wot].median()), float(rpm_dot[wot].max()))
        )

    bins = [(2000, 3000), (3000, 4000), (4000, 5000), (5000, 5500), (5500, 6000), (6000, 6500)]
    print("  WOT LC2 / HP by RPM bin:")
    for lo, hi in bins:
        m = wot & (rpm >= lo) & (rpm < hi)
        if not m.any():
            continue
        clean = lc2[m & (lc2 > 5) & (lc2 < 22.38)]
        print(
            "    %d-%d  n=%d  hp_avg=%.1f  hp_max=%.1f  lc2_avg=%.2f  duty_R_max=%.1f%%"
            % (
                lo,
                hi,
                int(m.sum()),
                float(hp[m].mean()) if hp[m].notna().any() else math.nan,
                float(hp[m].max()) if hp[m].notna().any() else math.nan,
                float(clean.mean()) if len(clean) else math.nan,
                float(dutyr[m].max()) if dutyr[m].notna().any() else math.nan,
            )
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--indices",
        type=int,
        nargs="+",
        default=DEFAULT_INDICES,
        help="Pull file numeric indices to review (e.g. --indices 25 26 27 28)",
    )
    args = ap.parse_args()
    for i in args.indices:
        p = FOLDER / f"PV_Logfile_5.csv_{i}.txt"
        if not p.exists():
            print(f"MISSING: {p.name}")
            continue
        review(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
