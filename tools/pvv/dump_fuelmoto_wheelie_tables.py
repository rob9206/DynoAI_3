"""Dump the wheelie/throttle-relevant tables from the Fuel Moto PVV."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"c:\Dev\DynoAI_3")
sys.path.insert(0, str(ROOT))

from api.services.powercore_integration import parse_pvv_tune, tune_table_to_dataframe

PVV = r"c:\Users\dawso\Downloads\fuelmoto110lowrider.pvv"

tune = parse_pvv_tune(PVV)
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 60)
pd.set_option("display.float_format", lambda v: f"{v:7.2f}")

TARGETS = [
    "Drive By Wire Throttle Limit Vs Gear",
    "Gear Ratios",
    "Throttle Blade Control Low Gear",
    "Throttle Blade Control High Gear",
    "PE Air-Fuel Ratio",
    "PE Spark",
    "Air-Fuel Ratio",
    "Spark Advance (Front Cyl)",
    "Spark Advance (Rear Cyl)",
    "VE (MAP based/Front Cyl)",
    "VE (MAP based/Rear Cyl)",
    "VE (TPS based/Front Cyl)",
    "VE (TPS based/Rear Cyl)",
    "Acceleration Enrichment",
    "Map Default Table",
    "Adaptive Knock Retard",
    "MAP Load Normalization",
    "Charge Dilution Effect (Front Cyl)",
    "Charge Dilution Effect (Rear Cyl)",
    "Exit Fuel",
    "RPM Limit",
]


def show(name: str) -> None:
    t = tune.tables.get(name)
    if t is None:
        print(f"\n=== {name}: MISSING ===")
        return
    df = tune_table_to_dataframe(t)
    print(f"\n=== {name}  ({t.values.shape}) ===")
    print(f"  units={t.units!r}  row_units={t.row_units!r}  col_units={t.col_units!r}")
    print(df.to_string())


for n in TARGETS:
    show(n)

print("\n=== KEY SCALARS (wheelie/throttle-related) ===")
for k in [
    "Engine Displacement",
    "Injector Size",
    "RPM Limit Threshold",
    "PE Enable RPM", "PE Enable TPS", "PE Disable RPM", "PE Disable TPS",
    "Spark Advance",
    "Spark Delay Threshold",
    "Spark RPM Max",
    "Throttle Table Transition Gear",
    "Soft Throttle Enable", "Soft Throttle Disable",
    "Twistgrip Sensor Entry", "Twistgrip Sensor Exit",
    "Max Knock Retard",
    "Knock Event Spark Retard Adder",
    "Knock Spark Retard Removal Percentage",
    "Knock Spark Retard Removal Rate",
    "Wideband Offset", "Wideband Range",
    "MAP Entry", "MAP Exit",
    "Closed Loop MAP Enable", "Closed Loop MAP Disable",
    "Declutch RPM Entry", "Declutch RPM Exit",
]:
    v = tune.scalars.get(k)
    print(f"  {k:50s} = {v}")

print("\n=== KEY FLAGS ===")
for k in [
    "Target Tune", "Closed Loop", "Adaptive Control",
    "Volumetric Efficiency Table Selection",
    "Knock Control", "Active Compression Release",
    "Heated O2 Sensors", "Active Exhaust",
]:
    v = tune.flags.get(k)
    print(f"  {k:50s} = {v}")
