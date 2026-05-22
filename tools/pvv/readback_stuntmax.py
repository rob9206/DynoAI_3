"""Read-back sanity for the final stunt-max patched PVV.

Confirms:
- The 5 stunt-focused changes landed in the expected cells.
- All combustion-margin items and safety nets are still intact.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"c:\Dev\DynoAI_3")
sys.path.insert(0, str(ROOT))
from api.services.powercore_integration import parse_pvv_tune, tune_table_to_dataframe

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
pd.set_option("display.float_format", lambda v: f"{v:6.2f}")

PVV = r"c:\Users\dawso\Downloads\fuelmoto110lowrider_stuntmax.pvv"
t = parse_pvv_tune(PVV)

print("=== O2 FLAGS (must all be False -- O2 stays disabled) ===")
for k in ["Closed Loop", "Adaptive Control", "Heated O2 Sensors"]:
    print(f"  {k:35s} = {t.flags.get(k)}")

print()
print("=== EITMS scalars (Mode 2/3 Enable Temp should now be 600) ===")
for k in ["EITMS Mode 2 Enable Temp", "EITMS Mode 3 Enable Temp",
          "EITMS Mode 3 Enable Speed", "EITMS On Temperature"]:
    print(f"  {k:35s} = {t.scalars.get(k)}")

print()
print("=== Twistgrip deadband (Entry should be 1.4, Exit should be 1.75) ===")
for k in ["Twistgrip Sensor Entry", "Twistgrip Sensor Exit"]:
    print(f"  {k:35s} = {t.scalars.get(k)}")

print()
print("=== Rev limit (Threshold 6.0, table flat 6.5) ===")
print(f"  RPM Limit Threshold scalar = {t.scalars.get('RPM Limit Threshold')}")
print("  RPM Limit table:")
print(tune_table_to_dataframe(t.tables["RPM Limit"]).to_string())

print()
print("=== Decel Enleanment (147..320 F should be 0.55 then 0.50 x6) ===")
print(tune_table_to_dataframe(t.tables["Deceleration Enleanment"]).to_string())

print()
print("=== Closed Throttle Spark Front (row 1, cells 3 and 4 should be 28) ===")
print(tune_table_to_dataframe(t.tables["Closed Throttle Spark (Front Cyl)"]).to_string())

print()
print("=== Closed Throttle Spark Rear (row 1, cells 3 and 4 should be 28) ===")
print(tune_table_to_dataframe(t.tables["Closed Throttle Spark (Rear Cyl)"]).to_string())

print()
print("=== UNTOUCHED CRITICAL ITEMS (must match prior _final values) ===")
expect_scalars = {
    "Engine Displacement": 110.0,
    "Injector Size": 34.52,
    "Max Knock Retard": 6.0,
    "Knock Event Spark Retard Adder": 2.0,
    "Knock Spark Retard Removal Percentage": 14.844,
    "Knock Spark Retard Removal Rate": 0.51,
    "PE Enable RPM": 2.8,
    "PE Enable TPS": 55.0,
    "PE Disable RPM": 2.6,
    "PE Disable TPS": 50.0,
}
for k, want in expect_scalars.items():
    got = t.scalars.get(k)
    flag = "OK " if got == want else "MISMATCH"
    print(f"  [{flag}] scalar {k:40s} got={got}  want={want}")

expect_flags = {
    "Active Compression Release": True,
    "Target Tune": True,
    "Knock Control": True,
    "Closed Loop": False,
    "Adaptive Control": False,
    "Heated O2 Sensors": False,
}
for k, want in expect_flags.items():
    got = t.flags.get(k)
    flag = "OK " if got == want else "MISMATCH"
    print(f"  [{flag}] flag   {k:40s} got={got}  want={want}")

expect_shapes = {
    "VE (MAP based/Front Cyl)": (27, 17),
    "VE (MAP based/Rear Cyl)": (27, 17),
    "VE (TPS based/Front Cyl)": (27, 17),
    "VE (TPS based/Rear Cyl)": (27, 17),
    "Spark Advance (Front Cyl)": (21, 17),
    "Spark Advance (Rear Cyl)": (21, 17),
    "Air-Fuel Ratio": (17, 17),
    "PE Air-Fuel Ratio": (1, 17),
    "PE Spark": (1, 17),
}
for k, want in expect_shapes.items():
    got = t.tables[k].values.shape
    flag = "OK " if got == want else "MISMATCH"
    print(f"  [{flag}] table  {k:40s} shape={got}  want={want}")

# Spot-check spark advance to confirm we did not touch combustion margin
spark_f = t.tables["Spark Advance (Front Cyl)"]
import numpy as np
df_spark = tune_table_to_dataframe(spark_f)
# Pull the 3000 rpm @ 100 kPa cell (key WOT lift cell) -- should still be 18.0
val = df_spark.loc[3.0, 100.0] if 3.0 in df_spark.index and 100.0 in df_spark.columns else None
if isinstance(val, pd.Series):
    val = val.iloc[0]
print()
print(f"  spark@(3.0k, 100kPa) front = {val}  (must still be 18.0 -- combustion margin intact)")

print()
print(f"  totals tables / scalars / flags = {len(t.tables)} / {len(t.scalars)} / {len(t.flags)}")
