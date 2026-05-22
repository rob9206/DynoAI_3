"""Real WOT HP/torque/AFR comparison across iter_3 / iter_6 / iter_8 / iter_11.

Uses (DWRT CPU) Power/Torque/Speed channels which ARE in the PV csv files.
Filters to true WOT (TPS>=80, MAP>=85), valid LC2, and reports peak HP / TQ
plus per-RPM-bin AFR and inj duty.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FOLDER = Path(r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus")

GROUPS = {
    "iter_6 (4th, post-brake fix)":           ["PV_Logfile_5.csv_31.txt", "PV_Logfile_5.csv_32.txt", "PV_Logfile_5.csv_33.txt"],
    "iter_7 (4th, +1 deg)":                   ["PV_Logfile_5.csv_35.txt", "PV_Logfile_5.csv_36.txt", "PV_Logfile_5.csv_37.txt"],
    "iter_8 (4th, +2 deg + smoothing)":       ["PV_Logfile_5.csv_38.txt", "PV_Logfile_5.csv_39.txt", "PV_Logfile_5.csv_40.txt"],
    "iter_11 (4th, pre-retorque)":            ["PV_Logfile_5.csv_49.txt", "PV_Logfile_5.csv_50.txt", "PV_Logfile_5.csv_51.txt"],
    "iter_11 (5th, pre-retorque)":            ["5TH GEAR.txt", "5TH GEAR_0.txt"],
    "iter_11 (4th, POST-retorque + sniffer)": [
        "4th gear 11 probe adjuste.txt",
        "4th gear 11 probe adjuste2.txt",
        "4th gear 11 probe adjuste3.txt",
        "4th gear 11 probe adjuste4.txt",
        "4th gear 11 probe adjuste5.txt",
    ],
}

COL_TIME = "Time"
COL_RPM_ECU = "(Harley - ECU Type 14 SW Level 141) Engine Speed"
COL_RPM_DWRT = "(DWRT CPU) Engine RPM"
COL_TPS = "(Harley - ECU Type 14 SW Level 141) Throttle Position"
COL_MAP = "(Harley - ECU Type 14 SW Level 141) Manifold Absolute Pressure"
COL_LC2 = "(DWRT CPU) LC2 Volts Petrol AFR2"
COL_INJF = "(Harley - ECU Type 14 SW Level 141) Injector Time Front"
COL_INJR = "(Harley - ECU Type 14 SW Level 141) Injector Time Rear"
COL_KF = "(Harley - ECU Type 14 SW Level 141) Knock Retard Front"
COL_KR = "(Harley - ECU Type 14 SW Level 141) Knock Retard Rear"
COL_HP = "(DWRT CPU) Power"
COL_HP_UNC = "(DWRT CPU) Power (uncorrected)"
COL_TQ = "(DWRT CPU) Torque"
COL_SPEED = "(DWRT CPU) Speed"
COL_CF = "(DWRT CPU) Correction Factor"
COL_IAT = "(Harley - ECU Type 14 SW Level 141) Intake Air Temperature"
COL_CHT = "(Harley - ECU Type 14 SW Level 141) Engine Temperature"

RPM_BINS = [3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]
LC2_LO, LC2_HI = 10.0, 18.0


def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def load(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p, encoding="utf-8", encoding_errors="replace", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    n = len(df)
    nan = pd.Series([float("nan")] * n)
    out = pd.DataFrame()
    out["t"]    = _to_num(df.get(COL_TIME, nan))
    rpm_ecu     = _to_num(df.get(COL_RPM_ECU, nan)) * 1000.0
    rpm_dwrt    = _to_num(df.get(COL_RPM_DWRT, nan)) * 1000.0
    out["rpm"]  = rpm_ecu
    if rpm_dwrt.notna().sum() > rpm_ecu.notna().sum() * 0.5:
        out["rpm"] = rpm_dwrt
    out["tps"]  = _to_num(df.get(COL_TPS, nan))
    out["map"]  = _to_num(df.get(COL_MAP, nan))
    out["lc2"]  = _to_num(df.get(COL_LC2, nan))
    out["injf"] = _to_num(df.get(COL_INJF, nan))
    out["injr"] = _to_num(df.get(COL_INJR, nan))
    out["kf"]   = _to_num(df.get(COL_KF, nan))
    out["kr"]   = _to_num(df.get(COL_KR, nan))
    out["hp"]   = _to_num(df.get(COL_HP, nan))
    out["hpu"]  = _to_num(df.get(COL_HP_UNC, nan))
    out["tq"]   = _to_num(df.get(COL_TQ, nan))
    out["mph"]  = _to_num(df.get(COL_SPEED, nan))
    out["cf"]   = _to_num(df.get(COL_CF, nan))
    out["iat"]  = _to_num(df.get(COL_IAT, nan))
    out["cht"]  = _to_num(df.get(COL_CHT, nan))
    out["src"]  = p.name
    return out


def _bin(value: float) -> int | None:
    for i in range(len(RPM_BINS) - 1):
        if RPM_BINS[i] <= value < RPM_BINS[i + 1]:
            return RPM_BINS[i]
    if value >= RPM_BINS[-1]:
        return RPM_BINS[-1]
    return None


def per_pull_peaks(df: pd.DataFrame) -> list[dict]:
    out: list[dict] = []
    for src, sub in df.groupby("src"):
        wot = (sub["tps"] >= 80.0) & (sub["map"] >= 85.0) & sub["rpm"].between(3000, 6500)
        wot_sub = sub[wot & sub["hp"].notna()]
        if wot_sub.empty:
            continue
        peak_idx = wot_sub["hp"].idxmax()
        peak_row = wot_sub.loc[peak_idx]
        peak_tq_idx = wot_sub["tq"].idxmax()
        tq_row = wot_sub.loc[peak_tq_idx]
        out.append({
            "src": src,
            "peak_hp": float(peak_row["hp"]),
            "peak_hp_rpm": float(peak_row["rpm"]),
            "peak_hp_mph": float(peak_row["mph"]) if not pd.isna(peak_row["mph"]) else float("nan"),
            "peak_hp_uncorr": float(peak_row["hpu"]) if not pd.isna(peak_row["hpu"]) else float("nan"),
            "peak_tq": float(tq_row["tq"]),
            "peak_tq_rpm": float(tq_row["rpm"]),
            "cf": float(wot_sub["cf"].mean()) if wot_sub["cf"].notna().any() else float("nan"),
            "iat_avg": float(wot_sub["iat"].mean()) if wot_sub["iat"].notna().any() else float("nan"),
            "cht_avg": float(wot_sub["cht"].mean()) if wot_sub["cht"].notna().any() else float("nan"),
            "knock_max": max(
                float(wot_sub["kf"].max()) if wot_sub["kf"].notna().any() else 0.0,
                float(wot_sub["kr"].max()) if wot_sub["kr"].notna().any() else 0.0,
            ),
        })
    return out


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

    peaks = per_pull_peaks(df)
    print("  per-pull peaks:")
    print(f"  {'source':<28} {'HP':>6} @ {'rpm':>5} ({'mph':>4})  {'TQ':>5}@{'rpm':>5}  {'CF':>5}  {'IAT':>5}  {'CHT':>5}  {'kn':>4}")
    for r in peaks:
        print(
            f"  {r['src']:<28} {r['peak_hp']:>6.2f} @ {r['peak_hp_rpm']:>5.0f} ({r['peak_hp_mph']:>4.1f})  "
            f"{r['peak_tq']:>5.2f}@{r['peak_tq_rpm']:>5.0f}  "
            f"{r['cf']:>5.3f}  {r['iat_avg']:>5.1f}  {r['cht_avg']:>5.1f}  {r['knock_max']:>4.1f}"
        )

    if peaks:
        avg_hp = sum(r["peak_hp"] for r in peaks) / len(peaks)
        max_hp = max(r["peak_hp"] for r in peaks)
        avg_tq = sum(r["peak_tq"] for r in peaks) / len(peaks)
        max_tq = max(r["peak_tq"] for r in peaks)
        print(f"  group avg/max:  HP avg={avg_hp:.2f}  max={max_hp:.2f}    "
              f"TQ avg={avg_tq:.2f}  max={max_tq:.2f}")

    wot = (df["tps"] >= 80.0) & (df["map"] >= 85.0) & df["rpm"].between(3000, 6500)
    valid = wot & df["lc2"].between(LC2_LO, LC2_HI)
    df = df.copy()
    df["rpm_bin"] = df["rpm"].apply(_bin)
    df["duty_f"] = df["injf"] * df["rpm"] / 1200.0

    grid = (
        df[valid]
        .groupby("rpm_bin")
        .agg(
            n=("lc2", "count"),
            lc2_avg=("lc2", "mean"),
            hp_avg=("hp", "mean"),
            duty_f_max=("duty_f", "max"),
        )
    )
    print("  per-RPM (valid LC2 WOT only):")
    print(f"  {'rpm':>5}  {'n':>3}  {'LC2':>5}  {'HP avg':>6}  {'dutyF%':>7}")
    for rpm_bin, row in grid.iterrows():
        print(
            f"  {int(rpm_bin):>5}  {int(row['n']):>3}  "
            f"{row['lc2_avg']:>5.2f}  {row['hp_avg']:>6.2f}  {row['duty_f_max']:>7.0f}"
        )


def main() -> int:
    for g, files in GROUPS.items():
        analyze(g, files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
