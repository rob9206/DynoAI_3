"""Check if Engine Displacement parameter was logged at runtime."""

import pandas as pd
from pathlib import Path

FOLDER = Path(r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus")

p = FOLDER / "PV_Logfile_5.csv_27.txt"
df = pd.read_csv(p, encoding="utf-8", encoding_errors="replace", low_memory=False, nrows=1)
cols = [str(c).strip() for c in df.columns]

interest = [
    c for c in cols
    if any(
        k in c.lower()
        for k in (
            "displ", "ve ", "afr", "stoich", "fuel", "trim",
            "compensat", "barometric", "baro", "vol",
        )
    )
]
for c in interest:
    print(c)
