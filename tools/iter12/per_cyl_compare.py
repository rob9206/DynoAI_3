"""Per-cylinder AFR comparison: rear (52.txt) vs front (_55/_56/_57).

Filters out probe-loose windows (LC2 saturated or > 17 sustained for cruise/WOT).
Compares front-cyl AFR vs rear-cyl AFR at matched RPM/MAP bins for both
WOT and cruise operating regimes.
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

FOLDER = Path(r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus")

REAR_FILES = ["52.txt"]
FRONT_FILES = [
    "PV_Logfile_5.csv_55.txt",
    "PV_Logfile_5.csv_56.txt",
    "PV_Logfile_5.csv_57.txt",
]

LC2_VALID_HI = 17.5  # anything above this in our operating zones is probe leak
LC2_VALID_LO = 10.0

RPM_BINS = [3000, 3500, 4000, 4500, 5000, 5500, 6000]
MAP_BINS = [30, 40, 50, 60, 70, 80, 90, 100]


def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _bin(value: float, edges: list[int]) -> int | None:
    for i in range(len(edges) - 1):
        if edges[i] <= value < edges[i + 1]:
            return edges[i]
    if value >= edges[-1]:
        return edges[-1]
    return None


def load_with_quality(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8", encoding_errors="replace", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    out = pd.DataFrame()
    out["t"] = _to_num(df.get(COL_TIME))
    out["rpm"] = _to_num(df.get(COL_RPM_ECU)) * 1000.0
    out["tps"] = _to_num(df.get(COL_TPS))
    out["map"] = _to_num(df.get(COL_MAP))
    out["lc2"] = _to_num(df.get(COL_LC2))
    out["src"] = path.name
    return out


def file_quality_report(path: Path) -> pd.DataFrame:
    df = load_with_quality(path)
    df = df[df["t"].notna() & df["lc2"].notna()].sort_values("t").reset_index(drop=True)
    duration = float(df["t"].max() - df["t"].min())
    sat = int((df["lc2"] >= 22.3).sum())
    leak = int(df["lc2"].between(17.5, 22.3).sum())
    valid = int(df["lc2"].between(LC2_VALID_LO, LC2_VALID_HI).sum())
    print(f"  {path.name}: duration={duration:.1f}s  rows={len(df)}  "
          f"valid_lc2={valid}  leak(17.5-22.3)={leak}  saturated(>=22.3)={sat}")
    return df


def per_cell_grid(df: pd.DataFrame, label: str) -> pd.DataFrame:
    df = df.copy()
    valid = df["lc2"].between(LC2_VALID_LO, LC2_VALID_HI)
    wot = (df["tps"] >= 80.0) & (df["map"] >= 85.0)
    cruise = (df["tps"] <= 35.0) & df["map"].between(30, 70)
    df["regime"] = pd.Series(["other"] * len(df))
    df.loc[valid & wot, "regime"] = "WOT"
    df.loc[valid & cruise, "regime"] = "cruise"
    df = df[df["regime"].isin(["WOT", "cruise"])].copy()
    df["rpm_bin"] = df["rpm"].apply(lambda v: _bin(v, RPM_BINS))
    df["map_bin"] = df["map"].apply(lambda v: _bin(v, MAP_BINS))
    df = df.dropna(subset=["rpm_bin", "map_bin"])
    df["cyl"] = label
    return df


def main() -> int:
    print("Quality check (probe seating):")
    print("REAR (52.txt):")
    rear_dfs = [file_quality_report(FOLDER / f) for f in REAR_FILES]
    print("\nFRONT (_55, _56, _57):")
    front_dfs = [file_quality_report(FOLDER / f) for f in FRONT_FILES]

    rear_all = pd.concat(rear_dfs, ignore_index=True)
    front_all = pd.concat(front_dfs, ignore_index=True)

    rear_grid = per_cell_grid(rear_all, "rear")
    front_grid = per_cell_grid(front_all, "front")

    print("\n=== WOT (TPS>=80, MAP>=85) per RPM bin ===")
    print(f"  {'rpm':>5}  {'F_n':>4} {'F_LC2':>6} {'F_std':>5}   "
          f"{'R_n':>4} {'R_LC2':>6} {'R_std':>5}   {'F-R':>5}")
    for r in RPM_BINS:
        f_sub = front_grid[(front_grid["regime"] == "WOT") & (front_grid["rpm_bin"] == r)]
        r_sub = rear_grid[(rear_grid["regime"] == "WOT") & (rear_grid["rpm_bin"] == r)]
        if f_sub.empty and r_sub.empty:
            continue
        fa = f_sub["lc2"].mean() if not f_sub.empty else float("nan")
        fs = f_sub["lc2"].std() if len(f_sub) > 1 else float("nan")
        ra = r_sub["lc2"].mean() if not r_sub.empty else float("nan")
        rs = r_sub["lc2"].std() if len(r_sub) > 1 else float("nan")
        delta = fa - ra if not (pd.isna(fa) or pd.isna(ra)) else float("nan")
        print(
            f"  {r:>5}  {len(f_sub):>4d} {fa:>6.2f} {fs:>5.2f}   "
            f"{len(r_sub):>4d} {ra:>6.2f} {rs:>5.2f}   {delta:>+5.2f}"
        )

    print("\n=== Cruise (TPS<=35, MAP 30-70) per RPMxMAP bin ===")
    print(f"  {'rpm':>5}  {'map':>4}  {'F_n':>4} {'F_LC2':>6}   "
          f"{'R_n':>4} {'R_LC2':>6}   {'F-R':>5}")
    for r in RPM_BINS:
        for m in MAP_BINS:
            f_sub = front_grid[
                (front_grid["regime"] == "cruise")
                & (front_grid["rpm_bin"] == r)
                & (front_grid["map_bin"] == m)
            ]
            r_sub = rear_grid[
                (rear_grid["regime"] == "cruise")
                & (rear_grid["rpm_bin"] == r)
                & (rear_grid["map_bin"] == m)
            ]
            if len(f_sub) < 3 and len(r_sub) < 3:
                continue
            fa = f_sub["lc2"].mean() if len(f_sub) >= 3 else float("nan")
            ra = r_sub["lc2"].mean() if len(r_sub) >= 3 else float("nan")
            delta = fa - ra if not (pd.isna(fa) or pd.isna(ra)) else float("nan")
            fa_s = f"{fa:.2f}" if not pd.isna(fa) else "  -  "
            ra_s = f"{ra:.2f}" if not pd.isna(ra) else "  -  "
            ds  = f"{delta:+.2f}" if not pd.isna(delta) else "  -  "
            print(
                f"  {r:>5}  {m:>4}  {len(f_sub):>4d} {fa_s:>6}   "
                f"{len(r_sub):>4d} {ra_s:>6}   {ds:>5}"
            )

    print("\n=== Overall summaries ===")
    for label, grid in [("FRONT", front_grid), ("REAR", rear_grid)]:
        wot = grid[grid["regime"] == "WOT"]
        cr = grid[grid["regime"] == "cruise"]
        print(
            f"  {label}: WOT n={len(wot)} LC2={wot['lc2'].mean():.2f}+/-"
            f"{wot['lc2'].std():.2f}  Cruise n={len(cr)} "
            f"LC2={cr['lc2'].mean():.2f}+/-{cr['lc2'].std():.2f}"
        )

    print("\nInterpretation:")
    print("  F-R column = front AFR - rear AFR  (negative = front richer than rear)")
    print("  +/- 0.3 AFR  -> balanced (within sensor noise)")
    print("  +/- 0.5 AFR  -> mild imbalance, not actionable")
    print("  > 1.0 AFR    -> real imbalance, target the leaner cylinder's VE for trim/raise")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
