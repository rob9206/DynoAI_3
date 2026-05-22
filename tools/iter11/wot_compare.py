"""WOT-only AFR / knock / injector saturation across iter_8, iter_9, iter_11 pulls.

PV ECU-only logs (no dyno HP channel) -- so this validates that WOT changed only
where we wanted (or, ideally, didn't change at all since iter_11 only modified
cruise VE cells). It does NOT produce HP numbers; for that you need DWRT logs.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FOLDER = Path(r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus")

GROUPS = {
    "iter_8 (4th)": ["PV_Logfile_5.csv_38.txt", "PV_Logfile_5.csv_39.txt", "PV_Logfile_5.csv_40.txt"],
    "iter_11 (4th)": ["PV_Logfile_5.csv_49.txt", "PV_Logfile_5.csv_50.txt", "PV_Logfile_5.csv_51.txt"],
    "iter_11 (5th)": ["5TH GEAR.txt", "5TH GEAR_0.txt"],
}

COL_TIME = "Time"
COL_RPM = "(Harley - ECU Type 14 SW Level 141) Engine Speed"
COL_TPS = "(Harley - ECU Type 14 SW Level 141) Throttle Position"
COL_MAP = "(Harley - ECU Type 14 SW Level 141) Manifold Absolute Pressure"
COL_LC2 = "(DWRT CPU) LC2 Volts Petrol AFR2"
COL_INJF = "(Harley - ECU Type 14 SW Level 141) Injector Time Front"
COL_INJR = "(Harley - ECU Type 14 SW Level 141) Injector Time Rear"
COL_KF = "(Harley - ECU Type 14 SW Level 141) Knock Retard Front"
COL_KR = "(Harley - ECU Type 14 SW Level 141) Knock Retard Rear"

RPM_BINS = [3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]
LC2_LO, LC2_HI = 10.0, 18.0


def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def load(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p, encoding="utf-8", encoding_errors="replace", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    out = pd.DataFrame()
    out["t"] = _to_num(df.get(COL_TIME, pd.Series([float("nan")] * len(df))))
    out["rpm"] = _to_num(df.get(COL_RPM, pd.Series([float("nan")] * len(df)))) * 1000.0
    out["tps"] = _to_num(df.get(COL_TPS, pd.Series([float("nan")] * len(df))))
    out["map"] = _to_num(df.get(COL_MAP, pd.Series([float("nan")] * len(df))))
    out["lc2"] = _to_num(df.get(COL_LC2, pd.Series([float("nan")] * len(df))))
    out["injf"] = _to_num(df.get(COL_INJF, pd.Series([float("nan")] * len(df))))
    out["injr"] = _to_num(df.get(COL_INJR, pd.Series([float("nan")] * len(df))))
    out["kf"] = _to_num(df.get(COL_KF, pd.Series([float("nan")] * len(df))))
    out["kr"] = _to_num(df.get(COL_KR, pd.Series([float("nan")] * len(df))))
    out["src"] = p.name
    return out


def _bin(value: float) -> int | None:
    for i in range(len(RPM_BINS) - 1):
        if RPM_BINS[i] <= value < RPM_BINS[i + 1]:
            return RPM_BINS[i]
    if value >= RPM_BINS[-1]:
        return RPM_BINS[-1]
    return None


def analyze(group: str, files: list[str]) -> None:
    print(f"\n=== {group} ===")
    rows: list[pd.DataFrame] = []
    for f in files:
        p = FOLDER / f
        if not p.exists():
            print(f"  MISSING: {f}")
            continue
        rows.append(load(p))
    if not rows:
        return
    df = pd.concat(rows, ignore_index=True)

    wot = (df["tps"] >= 80.0) & (df["map"] >= 85.0) & df["rpm"].between(3000, 6500)
    valid_lc2 = wot & df["lc2"].between(LC2_LO, LC2_HI)
    print(
        f"  total rows: {len(df)}  WOT samples: {int(wot.sum())}  "
        f"valid LC2 WOT: {int(valid_lc2.sum())}"
    )
    print(
        f"  knock max: front={float(df.loc[wot, 'kf'].max() if wot.any() else 0):.1f}  "
        f"rear={float(df.loc[wot, 'kr'].max() if wot.any() else 0):.1f}"
    )

    df = df.copy()
    df["rpm_bin"] = df["rpm"].apply(_bin)
    df["duty_f"] = df["injf"] * df["rpm"] / 1200.0
    df["duty_r"] = df["injr"] * df["rpm"] / 1200.0

    grid = (
        df[valid_lc2]
        .groupby("rpm_bin")
        .agg(
            n=("lc2", "count"),
            lc2_avg=("lc2", "mean"),
            lc2_min=("lc2", "min"),
            lc2_max=("lc2", "max"),
            duty_f_max=("duty_f", "max"),
            duty_r_max=("duty_r", "max"),
            injf_max=("injf", "max"),
            injr_max=("injr", "max"),
        )
    )
    print(
        "  rpm_bin  n   LC2 avg  LC2 range     dutyF%  dutyR%  injF ms  injR ms"
    )
    for rpm_bin, row in grid.iterrows():
        print(
            f"  {int(rpm_bin):>5}    {int(row['n']):>3}  "
            f"{row['lc2_avg']:>6.2f}   {row['lc2_min']:.2f}-{row['lc2_max']:.2f}  "
            f"{row['duty_f_max']:>6.0f}  {row['duty_r_max']:>6.0f}  "
            f"{row['injf_max']:>6.2f}   {row['injr_max']:>6.2f}"
        )


def main() -> int:
    for g, files in GROUPS.items():
        analyze(g, files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
