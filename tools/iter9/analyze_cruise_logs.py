"""Cruise / part-throttle AFR analysis from DynoWare RT logs.

Selects steady-state samples (low |dRPM|, |dTPS|, |dMAP| over a rolling window),
bins them in an RPM x MAP grid, and reports LC2 vs cruise AFR target per cell.

Cruise AFR target curve (industry standard for HD V-twin, no on-bike O2):
  30 kPa: 14.7   40: 14.5   50: 14.0   60: 13.5   70: 13.0
  80 kPa: 12.8   90: 12.5  100: 12.2

Use:
    python tools/iter9/analyze_cruise_logs.py --indices 41 42 43 44

Loaded/braked sections are fine -- they just shift which RPM x MAP cells we hit.
The steady-state filter excludes transients and WOT pulls so power runs in the
same file don't pollute the cruise data.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

FOLDER = Path(r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus")

CRUISE_AFR_TARGET = {
    30: 14.7,
    40: 14.5,
    50: 14.0,
    60: 13.5,
    70: 13.0,
    80: 12.8,
    90: 12.5,
    100: 12.2,
}

RPM_BINS = [1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000]
MAP_BINS = [30, 40, 50, 60, 70, 80, 90, 100]

ROLL_WINDOW = 8
RPM_STD_LIMIT = 80
TPS_STD_LIMIT = 1.5
MAP_STD_LIMIT = 2.5
MAX_TPS_FOR_CRUISE = 60.0
LC2_VALID_LO = 5.0
LC2_VALID_HI = 22.38

COL_TIME = "Time"
COL_RPM_ECU = "(Harley - ECU Type 14 SW Level 141) Engine Speed"
COL_TPS = "(Harley - ECU Type 14 SW Level 141) Throttle Position"
COL_MAP = "(Harley - ECU Type 14 SW Level 141) Manifold Absolute Pressure"
COL_LC2 = "(DWRT CPU) LC2 Volts Petrol AFR2"
COL_INJF = "(Harley - ECU Type 14 SW Level 141) Injector Time Front"
COL_INJR = "(Harley - ECU Type 14 SW Level 141) Injector Time Rear"
COL_CHT = "(Harley - ECU Type 14 SW Level 141) Engine Temperature"
COL_IAT = "(Harley - ECU Type 14 SW Level 141) Intake Air Temperature"


def _bin_index(value: float, edges: list[int]) -> int | None:
    if pd.isna(value):
        return None
    for i in range(len(edges) - 1):
        if edges[i] - 0 <= value < edges[i + 1]:
            return i
    if value >= edges[-1]:
        return len(edges) - 1
    return None


def _bin_label(value: float, edges: list[int]) -> int | None:
    idx = _bin_index(value, edges)
    if idx is None:
        return None
    return edges[idx]


def _afr_target_for_map(map_kpa: float) -> float:
    keys = sorted(CRUISE_AFR_TARGET.keys())
    if map_kpa <= keys[0]:
        return CRUISE_AFR_TARGET[keys[0]]
    if map_kpa >= keys[-1]:
        return CRUISE_AFR_TARGET[keys[-1]]
    for i in range(len(keys) - 1):
        lo = keys[i]
        hi = keys[i + 1]
        if lo <= map_kpa <= hi:
            t_lo = CRUISE_AFR_TARGET[lo]
            t_hi = CRUISE_AFR_TARGET[hi]
            frac = (map_kpa - lo) / (hi - lo)
            return t_lo + frac * (t_hi - t_lo)
    return CRUISE_AFR_TARGET[keys[-1]]


def load_log(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8", encoding_errors="replace", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    for col in (
        COL_TIME, COL_RPM_ECU, COL_TPS, COL_MAP, COL_LC2,
        COL_INJF, COL_INJR, COL_CHT, COL_IAT,
    ):
        if col not in df.columns:
            df[col] = float("nan")
    df["_t"] = pd.to_numeric(df[COL_TIME], errors="coerce")
    df["_rpm"] = pd.to_numeric(df[COL_RPM_ECU], errors="coerce") * 1000.0
    df["_tps"] = pd.to_numeric(df[COL_TPS], errors="coerce")
    df["_map"] = pd.to_numeric(df[COL_MAP], errors="coerce")
    df["_lc2"] = pd.to_numeric(df[COL_LC2], errors="coerce")
    df["_injf"] = pd.to_numeric(df[COL_INJF], errors="coerce")
    df["_injr"] = pd.to_numeric(df[COL_INJR], errors="coerce")
    df["_cht"] = pd.to_numeric(df[COL_CHT], errors="coerce")
    df["_iat"] = pd.to_numeric(df[COL_IAT], errors="coerce")
    df["_source"] = path.name
    return df


def steady_state_mask(df: pd.DataFrame) -> pd.Series:
    rpm_std = df["_rpm"].rolling(window=ROLL_WINDOW, center=True, min_periods=ROLL_WINDOW).std()
    tps_std = df["_tps"].rolling(window=ROLL_WINDOW, center=True, min_periods=ROLL_WINDOW).std()
    map_std = df["_map"].rolling(window=ROLL_WINDOW, center=True, min_periods=ROLL_WINDOW).std()
    valid_lc2 = (df["_lc2"] > LC2_VALID_LO) & (df["_lc2"] < LC2_VALID_HI)
    cruise_tps = df["_tps"] <= MAX_TPS_FOR_CRUISE
    return (
        (rpm_std <= RPM_STD_LIMIT)
        & (tps_std <= TPS_STD_LIMIT)
        & (map_std <= MAP_STD_LIMIT)
        & valid_lc2
        & cruise_tps
        & df["_rpm"].between(RPM_BINS[0], RPM_BINS[-1] + 500)
        & df["_map"].between(MAP_BINS[0], MAP_BINS[-1] + 10)
    )


def analyze(indices: list[int]) -> int:
    files = []
    for i in indices:
        p = FOLDER / f"PV_Logfile_5.csv_{i}.txt"
        if not p.exists():
            print(f"MISSING: {p.name}")
            continue
        files.append(p)
    if not files:
        print("no input files")
        return 1

    rows: list[pd.DataFrame] = []
    for p in files:
        df = load_log(p)
        m = steady_state_mask(df)
        sub = df[m].copy()
        sub["_rpm_bin"] = sub["_rpm"].apply(lambda x: _bin_label(x, RPM_BINS))
        sub["_map_bin"] = sub["_map"].apply(lambda x: _bin_label(x, MAP_BINS))
        sub = sub.dropna(subset=["_rpm_bin", "_map_bin"])
        sub["_target"] = sub["_map"].apply(_afr_target_for_map)
        sub["_afr_err"] = sub["_lc2"] - sub["_target"]
        sub["_correction"] = sub["_lc2"] / sub["_target"]
        print(
            f"{p.name}: rows={len(df)}  total_t={(df['_t'].max() - df['_t'].min()):.1f}s  "
            f"steady_samples={len(sub)}"
        )
        rows.append(sub)

    if not rows:
        return 1
    all_data = pd.concat(rows, ignore_index=True)
    print(f"\nTOTAL steady-state cruise samples: {len(all_data)}")
    print(f"RPM range covered: {all_data['_rpm'].min():.0f} - {all_data['_rpm'].max():.0f}")
    print(f"MAP range covered: {all_data['_map'].min():.1f} - {all_data['_map'].max():.1f}")
    print(f"TPS range covered: {all_data['_tps'].min():.1f} - {all_data['_tps'].max():.1f}")

    grid = all_data.groupby(["_rpm_bin", "_map_bin"]).agg(
        n=("_lc2", "count"),
        lc2_avg=("_lc2", "mean"),
        target_avg=("_target", "mean"),
        afr_err_avg=("_afr_err", "mean"),
        corr_avg=("_correction", "mean"),
        tps_avg=("_tps", "mean"),
        injr_avg=("_injr", "mean"),
        cht_avg=("_cht", "mean"),
    ).reset_index()
    grid = grid[grid["n"] >= 3]

    print("\n=== Cruise AFR map (mean LC2 / target / error) by RPM x MAP cell ===")
    pivot_lc2 = grid.pivot(index="_rpm_bin", columns="_map_bin", values="lc2_avg")
    pivot_err = grid.pivot(index="_rpm_bin", columns="_map_bin", values="afr_err_avg")
    pivot_n = grid.pivot(index="_rpm_bin", columns="_map_bin", values="n")
    target_row = "         | " + " | ".join(f"{m:>5d}" for m in MAP_BINS)
    print(f"\nLC2 (measured AFR):")
    print("  rpm    | " + " | ".join(f"{m:>5d}" for m in MAP_BINS))
    for r in RPM_BINS:
        cells: list[str] = []
        for m in MAP_BINS:
            v = pivot_lc2.loc[r, m] if (r in pivot_lc2.index and m in pivot_lc2.columns) else math.nan
            cells.append(f"{v:>5.2f}" if not pd.isna(v) else "  -  ")
        print(f"  {r:>5d}  | " + " | ".join(cells))

    print(f"\nAFR error (LC2 - target, NEGATIVE = rich, POSITIVE = lean):")
    print("  rpm    | " + " | ".join(f"{m:>5d}" for m in MAP_BINS))
    for r in RPM_BINS:
        cells = []
        for m in MAP_BINS:
            v = pivot_err.loc[r, m] if (r in pivot_err.index and m in pivot_err.columns) else math.nan
            cells.append(f"{v:>+5.2f}" if not pd.isna(v) else "  -  ")
        print(f"  {r:>5d}  | " + " | ".join(cells))

    print(f"\nSample count per cell:")
    print("  rpm    | " + " | ".join(f"{m:>5d}" for m in MAP_BINS))
    for r in RPM_BINS:
        cells = []
        for m in MAP_BINS:
            v = pivot_n.loc[r, m] if (r in pivot_n.index and m in pivot_n.columns) else math.nan
            cells.append(f"{int(v):>5d}" if not pd.isna(v) else "  -  ")
        print(f"  {r:>5d}  | " + " | ".join(cells))

    print(f"\nCruise AFR target curve used:")
    print("  " + " ".join(f"{k}:{v}" for k, v in CRUISE_AFR_TARGET.items()))

    biggest = grid.reindex(grid["afr_err_avg"].abs().sort_values(ascending=False).index)
    print(f"\nTop 15 cells with biggest AFR error (where to consider VE correction):")
    print("  RPM   MAP   n   LC2avg   target   err     corr    tps_avg")
    for _, row in biggest.head(15).iterrows():
        print(
            f"  {int(row['_rpm_bin']):>4}  {int(row['_map_bin']):>4}  "
            f"{int(row['n']):>3}   {row['lc2_avg']:>6.2f}   {row['target_avg']:>6.2f}   "
            f"{row['afr_err_avg']:>+5.2f}   {row['corr_avg']:>5.3f}   {row['tps_avg']:>4.1f}"
        )

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--indices", type=int, nargs="+", required=True)
    args = ap.parse_args()
    return analyze(args.indices)


if __name__ == "__main__":
    raise SystemExit(main())
