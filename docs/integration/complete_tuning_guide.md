# DynoAI Integration Guide: V-Twin Tuning Suite

This guide covers the full workflow for addressing the critical V-twin tuning challenges identified in the technical validation: **Decel Popping**, **Cylinder Imbalance**, **Heat Soak**, and **Knock Management**.

## 1. Workflow Overview

A professional tuning session with DynoAI follows this sequence:

1.  **Heat Management**: Remove "fake" data caused by sensor heat soak before tuning.
2.  **Cylinder Balancing**: Equalize Front/Rear VE tables.
3.  **Decel Management**: Patch the specific cells causing popping on deceleration.
4.  **Knock Optimization**: Finalize timing tables by removing retard and safely finding MBT.

---

## 2. Heat Soak Compensation
**Goal**: Prevent "lean-bias" errors from entering your tune during hot idle/traffic.

**When**: Run this *first* on any logs taken in hot conditions or traffic.

```python
from heat_management import detect_soak_events, generate_heat_correction_overlay, write_heat_overlay_csv

# 1. Detect & Generate
events = detect_soak_events(records, threshold_f=130.0)
overlay = generate_heat_correction_overlay(events)

# 2. Save Correction (Negative factors)
write_heat_overlay_csv(overlay, "outputs/heat_correction.csv")

# 3. Apply to VE (Strip out the heat error)
# use ve_operations.py apply ...
```

---

## 3. Cylinder Balancing
**Goal**: Quantify and correct the airflow imbalance between Front and Rear cylinders.

**When**: After every AutoTune session.

```bash
# 1. Check the gap
python ve_operations.py delta \
  --front "maps/front_ve.csv" \
  --rear "maps/rear_ve.csv"

# 2. Apply dual corrections (keep them in sync)
python ve_operations.py apply-dual \
  --front-base "maps/front_ve.csv" \
  --rear-base "maps/rear_ve.csv" \
  --front-factor "outputs/front_corrections.csv" \
  --rear-factor "outputs/rear_corrections.csv" \
  --front-output "maps/front_new.csv" \
  --rear-output "maps/rear_new.csv"
```

---

## 4. Decel Popping Elimination
**Goal**: Fix the "pop" between 1750-5500 RPM on closed throttle.

**When**: If customer complains of popping or "gurgling" on decel.

```python
from decel_management import process_decel_management

# 1. Analyze log for popping events
result = process_decel_management(
    records=records,
    output_dir="outputs/decel_fix",
    severity="medium"
)

# 2. Apply the generated overlay to BOTH cylinders
# use ve_operations.py apply-dual ...
```

---

## 5. Knock-Based Timing Optimization
**Goal**: Find Maximum Brake Torque (MBT) timing without damaging the engine.

**When**: Final step of the tune, after VE tables are dialed in.

### Python API
```python
from knock_optimization import process_knock_data, generate_timing_corrections, write_timing_grid_csv

# 1. Analyze Front Cylinder
knock_front = process_knock_data(records, cylinder='front')

# 2. Generate Corrections
# "Safe" mode = Retard on knock, no advance
# "Aggressive" mode = Retard on knock, Advance on clean data
timing_fix_f = generate_timing_corrections(knock_front, aggressiveness="safe")

# 3. Save
write_timing_grid_csv(timing_fix_f, "outputs/timing_fix_front.csv")

# Repeat for Rear cylinder...
```

### Application
Apply these timing corrections to your **Spark Advance Tables** (not VE tables).
*Note: `ve_operations.py` is for VE tables. Spark tables are structurally identical (RPM x kPa) but contain degrees, not efficiency %. You can use a similar CSV apply logic or a dedicated spark tool.*

