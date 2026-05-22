"""Inspect rear-cyl probe log: find when probe came loose vs solidly seated.

Symptoms of a loose probe in a true-dual exhaust:
  - LC2 lean spikes >18 (sudden atmosphere bleed)
  - High noise / oscillation
  - Drift toward the OTHER cylinder's pipe or collector mix
  - Sustained "reasonable" AFR for one cyl, then transition

We segment the timeline into stable windows and report each window's
AFR statistics under WOT and cruise filters separately.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iter9.analyze_cruise_logs import (  # noqa: E402
    COL_LC2,
    COL_MAP,
    COL_RPM_ECU,
    COL_TIME,
    COL_TPS,
)

FILE = Path(
    r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus\52.txt"
)


def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def main() -> int:
    if not FILE.exists():
        print(f"missing: {FILE}")
        return 1

    df = pd.read_csv(FILE, encoding="utf-8", encoding_errors="replace", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    df["t"] = _to_num(df.get(COL_TIME))
    df["rpm"] = _to_num(df.get(COL_RPM_ECU)) * 1000.0
    df["tps"] = _to_num(df.get(COL_TPS))
    df["map"] = _to_num(df.get(COL_MAP))
    df["lc2"] = _to_num(df.get(COL_LC2))
    df = df[df["t"].notna() & df["lc2"].notna()].copy()
    df = df.sort_values("t").reset_index(drop=True)

    duration = float(df["t"].max() - df["t"].min())
    print(f"File: {FILE.name}")
    print(f"  rows={len(df)}  duration={duration:.1f} s")
    print(
        f"  LC2 overall: min={df['lc2'].min():.2f}  max={df['lc2'].max():.2f}  "
        f"mean={df['lc2'].mean():.2f}  median={df['lc2'].median():.2f}"
    )
    print(
        f"  LC2 valid range (10-22) count: {int(df['lc2'].between(10, 22).sum())}"
        f"  saturated (>=22.3) count: {int((df['lc2'] >= 22.3).sum())}"
    )

    bin_s = 30.0
    df["t_bin"] = (df["t"] // bin_s).astype(int)
    print("\nPer 30-second window: LC2 stats and load conditions")
    print(
        f"  {'t0..t1':<14} {'n':>4} {'LC2_med':>8} {'LC2_p10':>8} "
        f"{'LC2_p90':>8} {'sat>22':>7} {'WOT_n':>5} {'cruise_n':>8}"
    )
    for tb, sub in df.groupby("t_bin"):
        if len(sub) < 5:
            continue
        wot = (sub["tps"] >= 80.0) & (sub["map"] >= 85.0)
        cruise = (sub["tps"] <= 35.0) & sub["map"].between(30, 70)
        sat = (sub["lc2"] >= 22.3).sum()
        t0 = sub["t"].min()
        t1 = sub["t"].max()
        valid = sub[sub["lc2"].between(10, 22)]
        if len(valid) >= 3:
            med = valid["lc2"].median()
            p10 = valid["lc2"].quantile(0.10)
            p90 = valid["lc2"].quantile(0.90)
        else:
            med = p10 = p90 = float("nan")
        print(
            f"  {t0:>5.1f}..{t1:>5.1f}  {len(sub):>4}  {med:>8.2f} {p10:>8.2f} "
            f"{p90:>8.2f}  {int(sat):>7d}  {int(wot.sum()):>5d}  "
            f"{int(cruise.sum()):>8d}"
        )

    print("\nWOT-only segments (TPS>=80 & MAP>=85):")
    wot_df = df[(df["tps"] >= 80.0) & (df["map"] >= 85.0) & df["lc2"].between(10, 22)].copy()
    if not wot_df.empty:
        print(
            f"  total samples: {len(wot_df)}  LC2 mean: {wot_df['lc2'].mean():.2f}  "
            f"std: {wot_df['lc2'].std():.2f}  min: {wot_df['lc2'].min():.2f}  "
            f"max: {wot_df['lc2'].max():.2f}"
        )
        wot_df["t_bin"] = (wot_df["t"] // bin_s).astype(int)
        print("  by 30s window:")
        print("    t0..t1     n   LC2med  rpm_lo  rpm_hi")
        for tb, sub in wot_df.groupby("t_bin"):
            if len(sub) < 3:
                continue
            print(
                f"    {sub['t'].min():>5.1f}..{sub['t'].max():>5.1f}  "
                f"{len(sub):>3}  {sub['lc2'].median():>5.2f}  "
                f"{sub['rpm'].min():>5.0f}  {sub['rpm'].max():>5.0f}"
            )

    print("\nCruise-only segments (TPS<=35 & MAP 30-70):")
    cr = df[(df["tps"] <= 35) & df["map"].between(30, 70) & df["lc2"].between(10, 22)].copy()
    if not cr.empty:
        print(
            f"  total samples: {len(cr)}  LC2 mean: {cr['lc2'].mean():.2f}  "
            f"std: {cr['lc2'].std():.2f}  min: {cr['lc2'].min():.2f}  "
            f"max: {cr['lc2'].max():.2f}"
        )
        cr["t_bin"] = (cr["t"] // bin_s).astype(int)
        print("  by 30s window:")
        print("    t0..t1     n   LC2med  rpm_med  map_med  tps_med")
        for tb, sub in cr.groupby("t_bin"):
            if len(sub) < 3:
                continue
            print(
                f"    {sub['t'].min():>5.1f}..{sub['t'].max():>5.1f}  "
                f"{len(sub):>3}  {sub['lc2'].median():>5.2f}  "
                f"{sub['rpm'].median():>5.0f}    "
                f"{sub['map'].median():>5.1f}    "
                f"{sub['tps'].median():>5.1f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
