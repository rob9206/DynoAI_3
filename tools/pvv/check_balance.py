"""Check cylinder balance of the current VE tables."""
import sys
from pathlib import Path
import numpy as np

ROOT = Path(r"c:\Dev\DynoAI_3")
sys.path.insert(0, str(ROOT))
from api.services.powercore_integration import parse_pvv_tune

t = parse_pvv_tune(r"c:\Users\dawso\Downloads\fuelmoto110lowrider_o2off_wheelieA_smooth_ve1.pvv")

ve_f = t.tables["VE (MAP based/Front Cyl)"].values
ve_r = t.tables["VE (MAP based/Rear Cyl)"].values

# Calculate bias: (Rear / Front - 1) * 100
bias = (ve_r / ve_f - 1) * 100
max_bias = np.max(bias)
min_bias = np.min(bias)
avg_bias = np.mean(bias)

print(f"VE MAP Bias (Rear vs Front):")
print(f"  Average Bias: {avg_bias:.2f}%")
print(f"  Max Bias (Rear rich): {max_bias:.2f}%")
print(f"  Min Bias (Rear lean): {min_bias:.2f}%")

# Same for TPS
ve_f_tps = t.tables["VE (TPS based/Front Cyl)"].values
ve_r_tps = t.tables["VE (TPS based/Rear Cyl)"].values
bias_tps = (ve_r_tps / ve_f_tps - 1) * 100
print(f"\nVE TPS Bias (Rear vs Front):")
print(f"  Average Bias: {np.mean(bias_tps):.2f}%")
print(f"  Max Bias (Rear rich): {np.max(bias_tps):.2f}%")
print(f"  Min Bias (Rear lean): {np.min(bias_tps):.2f}%")
