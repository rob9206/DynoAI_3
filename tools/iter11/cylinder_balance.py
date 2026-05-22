"""Cylinder balance analyzer: front vs rear injector pulse-width and VE deltas.

We have a single LC2 in the collector, so we cannot measure per-cylinder AFR
directly. Instead we infer balance from:
  1. Injector pulse-width ratio (InjF vs InjR) at matched RPM/MAP/TPS bins.
     The ECU commands fuel from VE_table[cyl] * MAP * displacement / AFR_target.
     If front and rear VE tables are commanding noticeably different fuel for
     the same operating point, that's a systematic bias we can measure.
  2. Front-vs-rear VE table difference (cell-by-cell from the PVV).

Reports:
  - Per-pull mean InjF/InjR ratio at WOT and at cruise, and per-RPM-bin
  - VE-table cell-by-cell delta (Front - Rear, % of front)
  - Systematic bias and worst-case cell imbalance
  - Recommendation if systematic bias > 2%

Usage:
    python tools/iter11/cylinder_balance.py --pulls 38 39 40 49 50 51
    python tools/iter11/cylinder_balance.py --pulls 49 50 51 --pvv \\
        vehicles/.../iter_11/patch/iter_11_patched.pvv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import generate_iter2_patch as g2  # noqa: E402

FOLDER = Path(r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus")

COL_TIME = "Time"
COL_RPM_DWRT = "(DWRT CPU) Engine RPM"
COL_RPM_ECU = "(Harley - ECU Type 14 SW Level 141) Engine Speed"
COL_TPS = "(Harley - ECU Type 14 SW Level 141) Throttle Position"
COL_MAP = "(Harley - ECU Type 14 SW Level 141) Manifold Absolute Pressure"
COL_INJF = "(Harley - ECU Type 14 SW Level 141) Injector Time Front"
COL_INJR = "(Harley - ECU Type 14 SW Level 141) Injector Time Rear"

RPM_BINS = [3000, 3500, 4000, 4500, 5000, 5500, 6000]


def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _bin(value: float) -> int | None:
    for i in range(len(RPM_BINS) - 1):
        if RPM_BINS[i] <= value < RPM_BINS[i + 1]:
            return RPM_BINS[i]
    if value >= RPM_BINS[-1]:
        return RPM_BINS[-1]
    return None


def load(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p, encoding="utf-8", encoding_errors="replace", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    n = len(df)
    nan = pd.Series([float("nan")] * n)
    out = pd.DataFrame()
    out["t"] = _to_num(df.get(COL_TIME, nan))
    rpm_ecu = _to_num(df.get(COL_RPM_ECU, nan)) * 1000.0
    rpm_dwrt = _to_num(df.get(COL_RPM_DWRT, nan)) * 1000.0
    out["rpm"] = rpm_ecu
    if rpm_dwrt.notna().sum() > rpm_ecu.notna().sum() * 0.5:
        out["rpm"] = rpm_dwrt
    out["tps"] = _to_num(df.get(COL_TPS, nan))
    out["map"] = _to_num(df.get(COL_MAP, nan))
    out["injf"] = _to_num(df.get(COL_INJF, nan))
    out["injr"] = _to_num(df.get(COL_INJR, nan))
    out["src"] = p.name
    return out


def analyze_log_balance(paths: list[Path]) -> None:
    rows: list[pd.DataFrame] = []
    for p in paths:
        if not p.exists():
            print(f"  MISSING: {p.name}")
            continue
        rows.append(load(p))
    if not rows:
        return
    df = pd.concat(rows, ignore_index=True)

    # Both cylinders must have valid pulse-width samples
    valid = df["injf"].notna() & df["injr"].notna() & (df["injf"] > 1.0) & (df["injr"] > 1.0)
    df = df[valid].copy()
    df["ratio_rf"] = df["injr"] / df["injf"]
    df["pct_rf"] = (df["ratio_rf"] - 1.0) * 100.0

    df["rpm_bin"] = df["rpm"].apply(_bin)

    wot = (df["tps"] >= 80.0) & (df["map"] >= 85.0)
    cruise = (df["tps"] <= 35.0) & (df["map"].between(30, 70))

    print("\n=== Injector PWM balance (Rear / Front), all samples ===")
    if df["pct_rf"].notna().any():
        print(f"  count: {len(df)}  mean (R/F-1)%: {df['pct_rf'].mean():+.2f}  "
              f"std: {df['pct_rf'].std():.2f}  median: {df['pct_rf'].median():+.2f}")

    if wot.sum() > 0:
        sub = df[wot]
        print("\n=== WOT (TPS>=80, MAP>=85) ===")
        print(f"  count: {len(sub)}  mean (R/F-1)%: {sub['pct_rf'].mean():+.2f}  "
              f"std: {sub['pct_rf'].std():.2f}")
        grid = sub.groupby("rpm_bin").agg(
            n=("pct_rf", "count"),
            pct_mean=("pct_rf", "mean"),
            pct_std=("pct_rf", "std"),
            injf_mean=("injf", "mean"),
            injr_mean=("injr", "mean"),
        )
        print("  rpm  n  (R/F-1)%  std  injF ms  injR ms")
        for rpm_bin, row in grid.iterrows():
            print(f"  {int(rpm_bin):>4} {int(row['n']):>3}  "
                  f"{row['pct_mean']:>+6.2f}  {row['pct_std']:>4.2f}  "
                  f"{row['injf_mean']:>6.2f}   {row['injr_mean']:>6.2f}")

    if cruise.sum() > 0:
        sub = df[cruise]
        print("\n=== Cruise (TPS<=35, MAP 30-70) ===")
        print(f"  count: {len(sub)}  mean (R/F-1)%: {sub['pct_rf'].mean():+.2f}  "
              f"std: {sub['pct_rf'].std():.2f}")
        grid = sub.groupby("rpm_bin").agg(
            n=("pct_rf", "count"),
            pct_mean=("pct_rf", "mean"),
            pct_std=("pct_rf", "std"),
        )
        print("  rpm  n  (R/F-1)%  std")
        for rpm_bin, row in grid.iterrows():
            print(f"  {int(rpm_bin):>4} {int(row['n']):>3}  "
                  f"{row['pct_mean']:>+6.2f}  {row['pct_std']:>4.2f}")

    print("\nInterpretation:")
    print("  +%  = rear cyl commanded MORE fuel than front (rear VE > front VE for same air)")
    print("  -%  = front cyl commanded MORE fuel than rear")
    print("  | <2% systematic bias | -- normal HD V-twin asymmetry, leave alone")
    print("  | 2-5% systematic bias | -- consider 1-3% trim on the higher cylinder")
    print("  | >5% systematic bias | -- something is off (sensor, leak, hardware)")


def analyze_pvv_balance(pvv: Path) -> None:
    import xml.etree.ElementTree as ET

    print(f"\n=== VE table balance from {pvv.name} ===")
    root = ET.parse(str(pvv)).getroot()
    vf = g2.find_item_by_name(root, g2.VE_FRONT_TABLE)
    vr = g2.find_item_by_name(root, g2.VE_REAR_TABLE)
    if vf is None or vr is None:
        print("  VE tables missing")
        return
    rpm_axis, tps_axis, vf_grid = g2.read_table(vf)
    _, _, vr_grid = g2.read_table(vr)

    diffs: list[tuple[float, float, float, float, float]] = []
    for r in range(len(rpm_axis)):
        for c in range(len(tps_axis)):
            f = vf_grid[r][c]
            re = vr_grid[r][c]
            if abs(f) < 1e-9:
                continue
            pct = (re - f) / f * 100.0
            diffs.append((rpm_axis[r], tps_axis[c], f, re, pct))

    valid = [d for d in diffs if 0.5 <= d[0] <= 6.0 and 0 <= d[1] <= 100]
    if not valid:
        print("  no valid cells")
        return
    avg = sum(d[4] for d in valid) / len(valid)
    print(f"  cells in scope: {len(valid)}  mean (R-F)/F %: {avg:+.2f}")

    valid.sort(key=lambda d: -abs(d[4]))
    print("  Top 10 cells by absolute (R-F)/F %:")
    print(f"  {'rpm_k':>5} {'tps':>5} {'F':>6} {'R':>6} {'(R-F)%':>7}")
    for d in valid[:10]:
        print(f"  {d[0]:>5g} {d[1]:>5g} {d[2]:>6.2f} {d[3]:>6.2f} {d[4]:>+7.2f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pulls", type=int, nargs="*", default=[],
                    help="numeric indices of PV_Logfile_5.csv_N.txt files")
    ap.add_argument("--names", type=str, nargs="*", default=[],
                    help="exact filenames (e.g. '5TH GEAR.txt')")
    ap.add_argument("--pvv", type=Path, default=None,
                    help="PVV file to inspect VE table balance")
    args = ap.parse_args()

    paths: list[Path] = []
    for i in args.pulls:
        paths.append(FOLDER / f"PV_Logfile_5.csv_{i}.txt")
    for n in args.names:
        paths.append(FOLDER / n)
    if paths:
        analyze_log_balance(paths)
    if args.pvv is not None:
        analyze_pvv_balance(args.pvv)
    if not paths and args.pvv is None:
        print("no input -- pass --pulls and/or --pvv")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
