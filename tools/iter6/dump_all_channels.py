"""Dump every column header from a pull file so we can hunt fuel/air corrections."""

import pandas as pd
from pathlib import Path

p = Path(
    r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus\PV_Logfile_5.csv_27.txt"
)

df = pd.read_csv(p, encoding="utf-8", encoding_errors="replace", low_memory=False, nrows=1)
cols = [str(c).strip() for c in df.columns]
for c in cols:
    print(c)
