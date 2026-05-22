"""Look for PowerVision Auto-Tune signals in iter_3 vs iter_6 pulls."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

FOLDER = Path(r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus")

PAIRS = [
    ("iter_3 wot_4", "6th gear load then wot_4.txt"),
    ("iter_3 wot_7", "6th gear load then wot_7.txt"),
    ("iter_6 _27", "PV_Logfile_5.csv_27.txt"),
    ("iter_6 _28", "PV_Logfile_5.csv_28.txt"),
]

CHANNELS = [
    "(PV) AT Lambda 1",
    "(PV) AT Lambda 2",
    "(PV) Desired Lambda",
    "(PV) WBO2 AFR Front",
    "(PV) WBO2 AFR Rear",
    "(Harley - ECU Type 14 SW Level 141) WBO2 AFR Front",
    "(Harley - ECU Type 14 SW Level 141) WBO2 AFR Rear",
    "(PV) Warm-up Fuel AFR (Lambda)",
    "(PV) Warm-up Fuel AFR (Ratio)",
    "(DWRT CPU) Correction Factor",
]


def main() -> int:
    for label, fn in PAIRS:
        p = FOLDER / fn
        if not p.exists():
            print(f"\n{label} :: MISSING {fn}")
            continue
        df = pd.read_csv(p, encoding="utf-8", encoding_errors="replace", low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        print(f"\n{label}  ({fn})")
        for c in CHANNELS:
            if c not in df.columns:
                print(f"  {c}  MISSING")
                continue
            s = pd.to_numeric(df[c], errors="coerce")
            if not s.notna().any():
                print(f"  {c}  all NaN")
                continue
            print(
                f"  {c}  min={float(s.min()):.3f}  mean={float(s.mean()):.3f}  max={float(s.max()):.3f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
