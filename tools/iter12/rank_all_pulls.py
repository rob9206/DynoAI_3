"""Rank every WinPEP-equipped pull by peak corrected HP.

Walks the watch folder, picks files with (DWRT CPU) Power and Engine RPM,
computes the WOT peak HP / TQ per file, and prints a sorted leaderboard.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FOLDER = Path(r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus")

COL_RPM_DWRT = "(DWRT CPU) Engine RPM"  # already in kRPM
COL_RPM_ECU = "(Harley - ECU Type 14 SW Level 141) Engine Speed"
COL_TPS = "(Harley - ECU Type 14 SW Level 141) Throttle Position"
COL_MAP = "(Harley - ECU Type 14 SW Level 141) Manifold Absolute Pressure"
COL_HP = "(DWRT CPU) Power"
COL_HP_UNC = "(DWRT CPU) Power (uncorrected)"
COL_TQ = "(DWRT CPU) Torque"
COL_SPEED = "(DWRT CPU) Speed"
COL_LC2 = "(DWRT CPU) LC2 Volts Petrol AFR2"
COL_KF = "(Harley - ECU Type 14 SW Level 141) Knock Retard Front"
COL_KR = "(Harley - ECU Type 14 SW Level 141) Knock Retard Rear"

ITER_TAGS = [
    (["_18", "_19", "6th gear load then wot.txt", "6th gear load then wot_"], "iter_2 baseline / Dynojet stage"),
    (["_20", "_21", "_22", "_23", "_24"], "iter_3"),
    (["_25", "_26", "_27", "_28"], "iter_6 (DRAGGING BRAKE)"),
    (["_31", "_32", "_33"], "iter_6 (clean)"),
    (["_35", "_36", "_37"], "iter_7 (+1 deg spark)"),
    (["_38", "_39", "_40"], "iter_8 (+2 deg + smoothing)"),
    (["_41", "_42", "_43", "_44"], "iter_8 cruise (loaded)"),
    (["_46", "_47", "_48"], "iter_9 cruise (loaded)"),
    (["_49", "_50", "_51"], "iter_11 4th pre-retorque"),
    (["5TH GEAR"], "iter_11 5th pre-retorque"),
    (["4th gear 11 probe adjuste"], "iter_11 4th POST-retorque"),
    (["5th gear 11 probe adjusted"], "iter_11 5th POST-retorque"),
    (["52.txt"], "per-cyl REAR (probe loose)"),
    (["_55", "_56", "_57"], "per-cyl FRONT"),
]


def tag_file(name: str) -> str:
    for keys, label in ITER_TAGS:
        for k in keys:
            if k in name:
                return label
    return "?"


def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def analyze(path: Path) -> dict | None:
    try:
        df = pd.read_csv(path, encoding="utf-8", encoding_errors="replace", low_memory=False)
    except Exception as exc:
        return {"file": path.name, "error": str(exc)}
    df.columns = [str(c).strip() for c in df.columns]
    if COL_HP not in df.columns:
        return None

    out = pd.DataFrame()
    out["rpm"] = _to_num(df[COL_RPM_DWRT]) if COL_RPM_DWRT in df.columns else pd.Series([float("nan")] * len(df))
    out["rpm_ecu"] = _to_num(df[COL_RPM_ECU]) * 1000.0 if COL_RPM_ECU in df.columns else pd.Series([float("nan")] * len(df))
    out["rpm"] = out["rpm"].fillna(out["rpm_ecu"] / 1000.0) * 1000.0  # use kRPM->RPM
    out["tps"] = _to_num(df[COL_TPS]) if COL_TPS in df.columns else float("nan")
    out["map"] = _to_num(df[COL_MAP]) if COL_MAP in df.columns else float("nan")
    out["hp"] = _to_num(df[COL_HP])
    out["hp_uncorr"] = _to_num(df[COL_HP_UNC]) if COL_HP_UNC in df.columns else pd.Series([float("nan")] * len(df))
    out["tq"] = _to_num(df[COL_TQ]) if COL_TQ in df.columns else float("nan")
    out["speed"] = _to_num(df[COL_SPEED]) if COL_SPEED in df.columns else float("nan")
    out["lc2"] = _to_num(df[COL_LC2]) if COL_LC2 in df.columns else float("nan")
    out["kf"] = _to_num(df[COL_KF]) if COL_KF in df.columns else 0.0
    out["kr"] = _to_num(df[COL_KR]) if COL_KR in df.columns else 0.0

    out = out.dropna(subset=["rpm", "hp"])
    if len(out) < 5:
        return None

    wot = out[(out["tps"] >= 80.0) & (out["map"] >= 85.0)]
    if wot.empty:
        wot = out[out["hp"] >= out["hp"].max() * 0.6]

    if wot.empty:
        return None

    peak_hp = float(wot["hp"].max())
    peak_hp_rpm = float(wot.loc[wot["hp"].idxmax(), "rpm"])
    peak_tq = float(wot["tq"].max()) if wot["tq"].notna().any() else float("nan")
    peak_tq_rpm = float(wot.loc[wot["tq"].idxmax(), "rpm"]) if wot["tq"].notna().any() else float("nan")
    peak_speed = float(wot["speed"].max()) if wot["speed"].notna().any() else float("nan")
    valid_lc2 = wot[wot["lc2"].between(10, 18)]
    avg_lc2 = float(valid_lc2["lc2"].mean()) if not valid_lc2.empty else float("nan")
    knock_max = float(max(out["kf"].max(), out["kr"].max()))

    return {
        "file": path.name,
        "tag": tag_file(path.name),
        "peak_hp": peak_hp,
        "peak_hp_rpm": peak_hp_rpm,
        "peak_tq": peak_tq,
        "peak_tq_rpm": peak_tq_rpm,
        "peak_mph": peak_speed,
        "wot_lc2": avg_lc2,
        "knock_max": knock_max,
    }


def main() -> int:
    rows = []
    for p in sorted(FOLDER.glob("*.txt")):
        r = analyze(p)
        if r and "peak_hp" in r:
            rows.append(r)
    if not rows:
        print("No files with (DWRT CPU) Power channel found.")
        return 0

    df = pd.DataFrame(rows).sort_values("peak_hp", ascending=False).reset_index(drop=True)
    print("\n=== LEADERBOARD by peak corrected HP (WOT only, TPS>=80, MAP>=85) ===\n")
    print(
        f"  {'rank':>4}  {'peak_HP':>7}  {'@RPM':>5}  {'peak_TQ':>7}  {'@RPM':>5}  "
        f"{'mph':>5}  {'AFR':>5}  {'kn':>4}  {'tag':30}  file"
    )
    for i, row in df.iterrows():
        afr = f"{row['wot_lc2']:.2f}" if pd.notna(row["wot_lc2"]) else "  -  "
        ptq = f"{row['peak_tq']:.1f}" if pd.notna(row["peak_tq"]) else "  -  "
        ptq_rpm = f"{row['peak_tq_rpm']:.0f}" if pd.notna(row["peak_tq_rpm"]) else "  -  "
        mph = f"{row['peak_mph']:.0f}" if pd.notna(row["peak_mph"]) else "  -  "
        print(
            f"  {i+1:>4}  {row['peak_hp']:>7.2f}  {row['peak_hp_rpm']:>5.0f}  "
            f"{ptq:>7}  {ptq_rpm:>5}  {mph:>5}  {afr:>5}  {row['knock_max']:>4.1f}  "
            f"{row['tag']:30}  {row['file']}"
        )

    print("\n=== Per-iteration peak (best file in each iter) ===")
    grp = df.loc[df.groupby("tag")["peak_hp"].idxmax()].sort_values("peak_hp", ascending=False)
    for _, row in grp.iterrows():
        print(
            f"  {row['peak_hp']:>6.2f} hp  /  {row['peak_tq']:>5.1f} ftlb  "
            f"AFR={row['wot_lc2']:>5.2f}  kn={row['knock_max']:>3.1f}  "
            f"{row['tag']:32}  {row['file']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
