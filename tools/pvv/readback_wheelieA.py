"""Read-back sanity for the final wheelie-A patched PVV."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"c:\Dev\DynoAI_3")
sys.path.insert(0, str(ROOT))
from api.services.powercore_integration import parse_pvv_tune, tune_table_to_dataframe

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
pd.set_option("display.float_format", lambda v: f"{v:6.2f}")

t = parse_pvv_tune(r"c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off_wheelieA.pvv")

print("=== O2 FLAGS (should all be False) ===")
for k in ["Closed Loop", "Adaptive Control", "Heated O2 Sensors"]:
    print(f"  {k:30s} = {t.flags.get(k)}")

print()
print("=== PE THRESHOLDS (should be 2.8 / 55 / 2.6 / 50) ===")
for k in ["PE Enable RPM", "PE Enable TPS", "PE Disable RPM", "PE Disable TPS"]:
    print(f"  {k:30s} = {t.scalars.get(k)}")

print()
print("=== ACCELERATION ENRICHMENT (90/118/147 F -> 1.15/1.00/0.80) ===")
print(tune_table_to_dataframe(t.tables["Acceleration Enrichment"]).to_string())

print()
print("=== THROTTLE BLADE CONTROL LOW GEAR (rows 0.7..2.5) ===")
print(tune_table_to_dataframe(t.tables["Throttle Blade Control Low Gear"]).iloc[0:8].to_string())

print()
print("=== UNTOUCHED CRITICAL ITEMS (must match Fuel Moto original) ===")
for k in [
    "Engine Displacement", "Injector Size", "RPM Limit Threshold",
    "Max Knock Retard", "Knock Event Spark Retard Adder",
]:
    print(f"  scalar {k:35s} = {t.scalars.get(k)}")
for k in ["Active Compression Release", "Target Tune", "Knock Control"]:
    print(f"  flag   {k:35s} = {t.flags.get(k)}")
for k in [
    "Air-Fuel Ratio",
    "VE (MAP based/Front Cyl)", "VE (MAP based/Rear Cyl)",
    "Spark Advance (Front Cyl)", "Spark Advance (Rear Cyl)",
    "PE Air-Fuel Ratio", "PE Spark",
]:
    print(f"  table  {k:35s} shape={t.tables[k].values.shape}")
print(f"  totals tables / scalars / flags     = {len(t.tables)} / {len(t.scalars)} / {len(t.flags)}")
