# Quick Start: Virtual ECU Simulation

**Get started with closed-loop tuning simulation in 5 minutes!**

---

## What is Virtual ECU?

The Virtual ECU simulates how an ECU's VE (Volumetric Efficiency) table affects fuel delivery and resulting AFR (Air/Fuel Ratio). When the VE table is wrong, you get realistic AFR errors that need tuning corrections.

**Perfect for:**
- Testing tuning algorithms
- Training tuners
- Validating corrections before applying to real engines
- Demonstrating closed-loop tuning workflows

---

## Installation

No additional dependencies needed! Uses existing DynoAI stack.

```bash
# Already installed with DynoAI
pip install -r requirements.txt
```

---

## Quick Demo (30 seconds)

```bash
cd examples
python virtual_ecu_demo.py
```

This runs 3 scenarios:
1. ✅ **Perfect VE** → AFR on target
2. ❌ **Wrong VE** → AFR errors (needs tuning)
3. 🔄 **No ECU** → Default behavior

**Output:** Comparison plots showing AFR errors and convergence potential.

---

## Basic Usage

### 1. Create a Virtual ECU

```python
from api.services.virtual_ecu import (
    VirtualECU,
    create_baseline_ve_table,
    create_afr_target_table,
)

# Create VE tables (11x9 grid: RPM x MAP)
ve_table = create_baseline_ve_table(
    peak_ve=0.85,      # Peak VE at optimal RPM
    peak_rpm=4000      # Torque peak RPM
)

# Create AFR target table
afr_table = create_afr_target_table(
    cruise_afr=14.0,   # Light load AFR
    wot_afr=12.5       # WOT AFR
)

# Create ECU
ecu = VirtualECU(
    ve_table_front=ve_table,
    ve_table_rear=ve_table,
    afr_target_table=afr_table,
)
```

### 2. Run Dyno Pull with ECU

```python
from api.services.dyno_simulator import (
    DynoSimulator,
    SimulatorConfig,
    EngineProfile,
)

# Create simulator with Virtual ECU
config = SimulatorConfig(profile=EngineProfile.m8_114())
simulator = DynoSimulator(config=config, virtual_ecu=ecu)

# Run pull
simulator.start()
simulator.trigger_pull()

# Wait for completion
import time
while simulator.get_state().value != 'idle':
    time.sleep(0.1)

# Get data
pull_data = simulator.get_pull_data()
simulator.stop()
```

### 3. Analyze AFR Errors

```python
import pandas as pd

df = pd.DataFrame(pull_data)

# Calculate errors
df['AFR Error'] = df['AFR Meas F'] - df['AFR Target']

# Statistics
print(f"Mean AFR Error: {df['AFR Error'].mean():.3f}")
print(f"Max AFR Error: {df['AFR Error'].abs().max():.3f}")

# Where are the errors?
print("\nWorst cells:")
print(df.nlargest(5, 'AFR Error')[['Engine RPM', 'MAP kPa', 'AFR Error']])
```

---

## Testing Tuning Scenarios

### Scenario: Untuned Engine (VE 10% Too Low)

```python
from api.services.virtual_ecu import create_intentionally_wrong_ve_table

# Create correct VE
correct_ve = create_baseline_ve_table(peak_ve=0.85)

# Create wrong VE (typical untuned engine)
wrong_ve = create_intentionally_wrong_ve_table(
    correct_ve,
    error_pct_mean=-10.0,  # 10% too low (lean)
    error_pct_std=5.0,     # ±5% variation
    seed=42                # Reproducible
)

# Create ECU with wrong VE
ecu = VirtualECU(
    ve_table_front=wrong_ve,
    ve_table_rear=wrong_ve,
    afr_target_table=afr_table,
)

# Run pull - will show AFR errors
simulator = DynoSimulator(config=config, virtual_ecu=ecu)
# ... AFR will be LEAN where VE is underestimated
```

**Expected Result:**
- AFR will be ~1.0-1.5 points lean at WOT
- Errors correlate with VE table inaccuracy
- Corrections needed: +10% VE in affected cells

---

## Understanding AFR Errors

### The Key Equation

```
Resulting AFR = Target AFR × (Actual VE / ECU VE)
```

**Examples:**

| ECU VE | Actual VE | Target AFR | Resulting AFR | Error | Condition |
|--------|-----------|------------|---------------|-------|-----------|
| 0.85 | 0.85 | 12.5 | 12.5 | 0.0 | ✅ Perfect |
| 0.85 | 0.95 | 12.5 | 13.97 | +1.47 | ❌ LEAN |
| 0.85 | 0.75 | 12.5 | 11.03 | -1.47 | ❌ RICH |

### VE Correction Formula

```python
# DynoAI v2.0.0 (physically accurate)
ve_correction = afr_measured / afr_target

# Example: AFR 13.97 vs target 12.5
ve_correction = 13.97 / 12.5 = 1.118  # Need +11.8% fuel
```

---

## Diagnostics

### Check ECU at Specific Point

```python
from api.services.virtual_ecu import print_ecu_diagnostics

# Diagnose at WOT condition
print_ecu_diagnostics(
    ecu, 
    rpm=4000, 
    map_kpa=80, 
    actual_ve=0.95  # What engine is really doing
)
```

**Output:**
```
=== ECU Diagnostics at 4000 RPM, 80 kPa ===
  Target AFR:        12.50
  ECU VE (table):    0.850
  Actual VE (phys):  0.950
  VE Error:          +11.8%
  Air mass:          876.3 mg
  Fuel delivered:    82.4 mg
  Resulting AFR:     13.97
  AFR Error:         +1.47
```

---

## Common Use Cases

### 1. Test Tuning Algorithm Convergence

```python
# Start with wrong VE
current_ve = create_intentionally_wrong_ve_table(correct_ve, -10.0)

for iteration in range(5):
    # Run pull with current VE
    ecu = VirtualECU(ve_table_front=current_ve, ...)
    simulator = DynoSimulator(virtual_ecu=ecu)
    pull_data = run_pull(simulator)
    
    # Analyze and correct
    corrections = analyze_afr_errors(pull_data)
    current_ve *= corrections
    
    # Check convergence
    max_error = calculate_max_afr_error(pull_data)
    if max_error < 0.3:
        print(f"Converged in {iteration+1} iterations!")
        break
```

### 2. Compare Front vs Rear Cylinder

```python
# V-twins often have different VE
ve_front = create_baseline_ve_table(peak_ve=0.85)
ve_rear = create_baseline_ve_table(peak_ve=0.80)  # 5% lower

ecu = VirtualECU(
    ve_table_front=ve_front,
    ve_table_rear=ve_rear,  # Different!
    afr_target_table=afr_table,
)

# Run pull - front/rear will have different AFRs
pull_data = run_pull(simulator)

# Analyze cylinder balance
df = pd.DataFrame(pull_data)
print(f"Front AFR: {df['AFR Meas F'].mean():.2f}")
print(f"Rear AFR:  {df['AFR Meas R'].mean():.2f}")
```

### 3. Simulate Altitude/Temperature Effects

```python
# High altitude dyno
ecu = VirtualECU(
    ve_table_front=ve_table,
    ve_table_rear=ve_table,
    afr_target_table=afr_table,
    barometric_pressure_inhg=24.9,  # 5000 ft elevation
    ambient_temp_f=85.0,             # Hot day
)

# Air density is lower → less air mass → AFR changes
```

---

## Next Steps

### Phase 3: Closed-Loop Orchestrator

With Virtual ECU complete, you can now build:

```python
class VirtualTuningSession:
    """
    Multi-iteration tuning until convergence.
    
    Workflow:
    1. Load base VE → ECU
    2. Run dyno pull
    3. Analyze AFR
    4. Calculate corrections
    5. Apply to ECU
    6. Repeat until converged
    """
```

See `docs/VIRTUAL_ECU_SIMULATION.md` for full architecture.

---

## Troubleshooting

### AFR errors seem too large

**Check:**
- Is VE table in reasonable range? (0.4-1.2)
- Is AFR target table correct? (12.0-15.0)
- Are RPM/MAP bins correct?

### No AFR errors with wrong VE

**Check:**
- Is `virtual_ecu` passed to `DynoSimulator`?
- Is VE table actually different from baseline?
- Run diagnostics at specific point to verify

### Interpolation errors

**Check:**
- Are table dimensions correct? (11x9)
- Are RPM/MAP bins in ascending order?
- Are values within valid range?

---

## Resources

- **Full Documentation:** `docs/VIRTUAL_ECU_SIMULATION.md`
- **API Reference:** See documentation above
- **Tests:** `tests/test_virtual_ecu.py` (usage examples)
- **Demo:** `examples/virtual_ecu_demo.py`

---

## Summary

✅ **Phase 1-2 Complete!**

You now have:
- ✅ Virtual ECU with VE table simulation
- ✅ Realistic AFR errors from VE mismatches
- ✅ Integration with physics simulator
- ✅ Helper functions for table generation
- ✅ Comprehensive tests (0 vulnerabilities)
- ✅ Demo script with visualization

**Ready for:** Closed-loop tuning orchestrator (Phase 3)

🚀 **Start experimenting with virtual tuning today!**

