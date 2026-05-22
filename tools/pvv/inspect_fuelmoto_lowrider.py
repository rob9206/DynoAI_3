"""Quick inspect of a Fuel Moto PVV tune for a 2017 Dyna Low Rider 110."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"c:\Dev\DynoAI_3")
sys.path.insert(0, str(ROOT))

from api.services.powercore_integration import parse_pvv_tune, tune_table_to_dataframe

PVV = r"c:\Users\dawso\Downloads\fuelmoto110lowrider.pvv"

tune = parse_pvv_tune(PVV)

print(f"Source: {tune.source_path}")
print(f"Tables:  {len(tune.tables)}")
print(f"Scalars: {len(tune.scalars)}")
print(f"Flags:   {len(tune.flags)}")

print("\n=== ALL TABLES (name | shape | row_units | col_units) ===")
for name, t in sorted(tune.tables.items()):
    print(f"  {name:55s} | {t.values.shape!s:10s} | rows={t.row_units!r:25s} cols={t.col_units!r}")

print("\n=== SCALARS ===")
for k, v in sorted(tune.scalars.items()):
    print(f"  {k:55s} = {v}")

print("\n=== FLAGS ===")
for k, v in sorted(tune.flags.items()):
    print(f"  {k:55s} = {v}")
