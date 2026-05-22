"""Quick inspector: classify recent pulls (gear, WOT vs cruise, peak HP)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iter9.analyze_cruise_logs import (  # noqa: E402
    FOLDER,
    COL_TIME,
    COL_RPM_ECU,
    COL_TPS,
    COL_MAP,
    COL_LC2,
    COL_INJF,
    COL_INJR,
)

COL_RPM_DWRT = "(DWRT CPU) Engine Speed"
COL_HP = "(DWRT CPU) Engine Power"
COL_VS = "(DWRT CPU) Vehicle Speed"
COL_KNOCK_F = "(Harley - ECU Type 14 SW Level 141) Knock Retard Front"
COL_KNOCK_R = "(Harley - ECU Type 14 SW Level 141) Knock Retard Rear"


def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def inspect(path: Path) -> None:
    df = pd.read_csv(path, encoding="utf-8", encoding_errors="replace", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    has_dwrt_rpm = COL_RPM_DWRT in df.columns
    rpm = _to_num(df[COL_RPM_ECU]) * 1000.0 if COL_RPM_ECU in df.columns else pd.Series([float("nan")])
    if has_dwrt_rpm:
        rpm_dw = _to_num(df[COL_RPM_DWRT])
        if rpm_dw.notna().sum() > rpm.notna().sum() * 0.5:
            rpm = rpm_dw
    tps = _to_num(df[COL_TPS]) if COL_TPS in df.columns else pd.Series([float("nan")])
    map_ = _to_num(df[COL_MAP]) if COL_MAP in df.columns else pd.Series([float("nan")])
    lc2 = _to_num(df[COL_LC2]) if COL_LC2 in df.columns else pd.Series([float("nan")])
    t = _to_num(df[COL_TIME]) if COL_TIME in df.columns else pd.Series([float("nan")])
    hp = _to_num(df[COL_HP]) if COL_HP in df.columns else pd.Series([float("nan")])
    vs = _to_num(df[COL_VS]) if COL_VS in df.columns else pd.Series([float("nan")])
    knock_f = _to_num(df[COL_KNOCK_F]) if COL_KNOCK_F in df.columns else pd.Series([float("nan")])
    knock_r = _to_num(df[COL_KNOCK_R]) if COL_KNOCK_R in df.columns else pd.Series([float("nan")])
    injf = _to_num(df[COL_INJF]) if COL_INJF in df.columns else pd.Series([float("nan")])

    duration = float(t.max() - t.min()) if t.notna().any() else float("nan")

    wot_mask = (tps >= 80.0) & (map_ >= 85.0)
    wot_n = int(wot_mask.sum())

    rpm_per_sec = float("nan")
    if rpm.notna().sum() > 5 and t.notna().sum() > 5:
        wot_idx = wot_mask[wot_mask].index
        if len(wot_idx) >= 5:
            r0 = rpm.loc[wot_idx[0]]
            r1 = rpm.loc[wot_idx[-1]]
            t0 = t.loc[wot_idx[0]]
            t1 = t.loc[wot_idx[-1]]
            if t1 - t0 > 0.5:
                rpm_per_sec = (r1 - r0) / (t1 - t0)

    mph_per_krpm = float("nan")
    if vs.notna().sum() > 10 and rpm.notna().sum() > 10:
        m = (rpm > 2500) & (vs > 25) & wot_mask
        if m.sum() > 5:
            mph_per_krpm = float((vs[m] / (rpm[m] / 1000.0)).median())

    peak_hp = float(hp.where(wot_mask).max()) if hp.notna().any() else float("nan")
    peak_hp_rpm = (
        float(rpm[hp.where(wot_mask).idxmax()]) if hp.notna().any() and wot_mask.any() else float("nan")
    )
    knock_max_f = float(knock_f.max()) if knock_f.notna().any() else 0.0
    knock_max_r = float(knock_r.max()) if knock_r.notna().any() else 0.0
    injf_max = float(injf.max()) if injf.notna().any() else float("nan")

    rpm_lo = float(rpm.where(wot_mask).min()) if wot_mask.any() else float("nan")
    rpm_hi = float(rpm.where(wot_mask).max()) if wot_mask.any() else float("nan")

    if not pd.isna(mph_per_krpm):
        if mph_per_krpm > 28:
            gear_guess = "6th"
        elif mph_per_krpm > 22:
            gear_guess = "5th"
        elif mph_per_krpm > 17:
            gear_guess = "4th"
        elif mph_per_krpm > 13:
            gear_guess = "3rd"
        else:
            gear_guess = f"{mph_per_krpm:.1f} mph/krpm"
    elif not pd.isna(rpm_per_sec):
        if rpm_per_sec < 350:
            gear_guess = "5th/6th (slow rpm rate)"
        elif rpm_per_sec < 600:
            gear_guess = "4th"
        elif rpm_per_sec < 1100:
            gear_guess = "3rd"
        else:
            gear_guess = f"{rpm_per_sec:.0f} rpm/s"
    else:
        gear_guess = "unknown"

    print(f"\n=== {path.name} ===")
    print(f"  rows={len(df)}  duration={duration:.1f}s  wot_samples={wot_n}")
    print(f"  RPM source: {'DWRT' if has_dwrt_rpm else 'ECU'}")
    print(f"  WOT RPM range: {rpm_lo:.0f} -> {rpm_hi:.0f}")
    print(f"  WOT RPM rate:  {rpm_per_sec:.0f} rpm/s")
    print(f"  MPH per kRPM:  {mph_per_krpm:.1f}")
    print(f"  Gear guess:    {gear_guess}")
    print(f"  Peak HP (WOT): {peak_hp:.1f} hp at {peak_hp_rpm:.0f} rpm")
    print(f"  Knock max:     front={knock_max_f:.1f} deg  rear={knock_max_r:.1f} deg")
    print(f"  InjF max:      {injf_max:.2f} ms")
    if wot_n > 0:
        lc2_wot = lc2[wot_mask]
        print(
            f"  LC2 WOT:       mean={float(lc2_wot.mean()):.2f}  "
            f"min={float(lc2_wot.min()):.2f}  max={float(lc2_wot.max()):.2f}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--indices", type=int, nargs="+")
    ap.add_argument("--names", type=str, nargs="*", default=[])
    args = ap.parse_args()

    paths: list[Path] = []
    for i in args.indices or []:
        p = FOLDER / f"PV_Logfile_5.csv_{i}.txt"
        if p.exists():
            paths.append(p)
    for n in args.names:
        p = FOLDER / n
        if p.exists():
            paths.append(p)

    if not paths:
        print("no files")
        return 1
    for p in paths:
        inspect(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
