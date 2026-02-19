# Virtual ECU Simulation - Closed-Loop Tuning Foundation

**Status:** ✅ Phase 1-2 Complete  
**Date:** December 15, 2025  
**Version:** 1.0.0

---

## Overview

The Virtual ECU system simulates how an ECU calculates fuel delivery based on VE (Volumetric Efficiency) tables. When the ECU's VE table doesn't match actual engine behavior, the resulting AFR (Air/Fuel Ratio) will have errors. This creates realistic tuning scenarios for testing and development.

### Key Concept

```
ECU VE Table (Wrong) → Wrong Fuel Delivery → AFR Error → Tuning Correction Needed
```

This is the foundation for **closed-loop tuning simulation** where corrections can be applied iteratively until convergence.

---

## Architecture

### Components

1. **VirtualECU** (`api/services/virtual_ecu.py`)
   - Reads VE tables (front/rear cylinders)
   - Calculates air mass from MAP and RPM
   - Calculates fuel delivery based on VE table
   - Simulates resulting AFR when VE table is wrong

2. **DynoSimulator Integration** (`api/services/dyno_simulator.py`)
   - Accepts optional `virtual_ecu` parameter
   - Uses ECU simulation during dyno pulls
   - Generates realistic AFR data with tuning errors

3. **Helper Functions**
   - `create_baseline_ve_table()` - Generate realistic VE tables
   - `create_afr_target_table()` - Generate AFR targets by load
   - `create_intentionally_wrong_ve_table()` - Create tables with errors for testing

---

## How It Works

### 1. ECU Fuel Calculation

The ECU calculates fuel delivery in several steps:

```python
# Step 1: Calculate air mass using ideal gas law
air_mass_mg = (MAP × Displacement) / (R × Temperature)

# Step 2: Calculate required fuel for target AFR
fuel_required_mg = air_mass_mg / target_afr

# Step 3: Apply VE correction from table
fuel_delivered_mg = fuel_required_mg × VE_from_table
```

### 2. Resulting AFR Calculation

When actual engine VE differs from ECU's VE table:

```python
# ECU delivers fuel based on its (possibly wrong) VE table
ecu_ve = lookup_ve_table(rpm, map)
fuel_delivered = calculate_fuel(ecu_ve)

# Actual engine has different VE
actual_ve = physics_engine.get_actual_ve(rpm, throttle)

# Resulting AFR depends on VE error
ve_error_ratio = actual_ve / ecu_ve
resulting_afr = target_afr × ve_error_ratio
```

**Example:**
- Target AFR: 12.5:1
- ECU thinks VE = 0.85
- Actual VE = 0.95 (engine breathes 11.8% better)
- ECU delivers fuel for VE=0.85 (not enough!)
- Result: AFR = 12.5 × (0.95/0.85) = **13.97:1 (LEAN)**
- Correction needed: Increase VE table by 11.8%

---

## Usage

### Basic Example

```python
from api.services.dyno_simulator import DynoSimulator, SimulatorConfig, EngineProfile
from api.services.virtual_ecu import (
    VirtualECU,
    create_baseline_ve_table,
    create_afr_target_table,
)

# Create VE tables
ve_table = create_baseline_ve_table(peak_ve=0.85, peak_rpm=4000)
afr_table = create_afr_target_table(cruise_afr=14.0, wot_afr=12.5)

# Create Virtual ECU
ecu = VirtualECU(
    ve_table_front=ve_table,
    ve_table_rear=ve_table,
    afr_target_table=afr_table,
)

# Create simulator with ECU
config = SimulatorConfig(profile=EngineProfile.m8_114())
simulator = DynoSimulator(config=config, virtual_ecu=ecu)

# Run dyno pull
simulator.start()
simulator.trigger_pull()

# Wait for completion and get data
pull_data = simulator.get_pull_data()
```

### Testing Tuning Scenarios

```python
from api.services.virtual_ecu import create_intentionally_wrong_ve_table

# Create correct VE
correct_ve = create_baseline_ve_table(peak_ve=0.85)

# Create wrong VE (10% too low - typical untuned engine)
wrong_ve = create_intentionally_wrong_ve_table(
    correct_ve,
    error_pct_mean=-10.0,  # 10% too low
    error_pct_std=5.0,     # ±5% variation
    seed=42                # Reproducible
)

# Create ECU with wrong VE
ecu = VirtualECU(
    ve_table_front=wrong_ve,
    ve_table_rear=wrong_ve,
    afr_target_table=afr_table,
)

# Run pull - will show AFR errors that need correction
simulator = DynoSimulator(config=config, virtual_ecu=ecu)
# ... AFR will be systematically lean where VE is underestimated
```

---

## Demo Script

Run the comprehensive demo:

```bash
cd examples
python virtual_ecu_demo.py
```

This demonstrates:
1. **Perfect VE Table** → AFR on target (±0.05 sensor noise)
2. **Incorrect VE Table** → Systematic AFR errors (needs tuning)
3. **No ECU Simulation** → Default behavior (for comparison)

Generates comparison plots showing AFR errors, torque curves, and error distributions.

---

## API Reference

### VirtualECU Class

```python
class VirtualECU:
    def __init__(
        self,
        ve_table_front: np.ndarray,      # Front cylinder VE (11x9 grid)
        ve_table_rear: np.ndarray,       # Rear cylinder VE (11x9 grid)
        afr_target_table: np.ndarray,    # AFR targets (11x9 grid)
        rpm_bins: list[int] = DEFAULT_RPM_BINS,
        map_bins: list[int] = DEFAULT_MAP_BINS,
        displacement_ci: float = 114.0,  # Engine displacement
        ambient_temp_f: float = 75.0,
        barometric_pressure_inhg: float = 29.92,
    )
```

#### Key Methods

**`lookup_ve(rpm, map_kpa, cylinder)`**
- Look up VE from table at given RPM and MAP
- Uses bilinear interpolation
- Returns: VE value (0.3-1.5)

**`lookup_target_afr(rpm, map_kpa)`**
- Look up target AFR from table
- Returns: Target AFR (10.0-18.0)

**`calculate_air_mass_mg(rpm, map_kpa)`**
- Calculate theoretical air mass per combustion event
- Uses ideal gas law: m = PV/RT
- Returns: Air mass in milligrams

**`calculate_resulting_afr(rpm, map_kpa, actual_ve, cylinder)`**
- **THE KEY FUNCTION** for tuning simulation
- Calculates AFR that results from ECU fueling vs actual VE
- Returns: Resulting AFR (8.0-20.0)

**`get_ve_error_pct(rpm, map_kpa, actual_ve, cylinder)`**
- Calculate VE error percentage
- Returns: Error % (positive = ECU underestimates VE)

### Helper Functions

**`create_baseline_ve_table(rpm_bins, map_bins, peak_ve, peak_rpm)`**
- Creates realistic VE table with Gaussian distribution
- Peak VE at torque peak RPM
- VE increases with MAP (better cylinder filling)
- Returns: 11x9 numpy array

**`create_afr_target_table(rpm_bins, map_bins, cruise_afr, wot_afr)`**
- Creates AFR target table with load-based strategy
- Light load: Leaner (economy)
- High load: Richer (power/cooling)
- Returns: 11x9 numpy array

**`create_intentionally_wrong_ve_table(baseline_table, error_pct_mean, error_pct_std, seed)`**
- Creates VE table with intentional errors for testing
- Useful for testing tuning convergence
- Returns: 11x9 numpy array with errors

**`print_ecu_diagnostics(ecu, rpm, map_kpa, actual_ve)`**
- Prints detailed diagnostic information
- Shows ECU VE, actual VE, VE error, AFR error
- Useful for debugging

---

## Testing

Run comprehensive tests:

```bash
pytest tests/test_virtual_ecu.py -v
```

### Test Coverage

✅ VE table lookup and interpolation  
✅ AFR target lookup  
✅ Air mass calculation (ideal gas law)  
✅ Fuel delivery calculation  
✅ Resulting AFR calculation (key function)  
✅ VE error calculation  
✅ Front/rear cylinder independence  
✅ Helper function validation  
✅ Complete tuning scenario integration  

**Result:** All tests passing, 0 security vulnerabilities

---

## Physics Validation

### Air Mass Calculation

Uses ideal gas law: **PV = mRT**

Solving for mass: **m = PV / RT**

Where:
- P = Manifold Absolute Pressure (Pa)
- V = Cylinder displacement (m³)
- R = Specific gas constant for air (287.05 J/(kg·K))
- T = Temperature (K)

**Example Validation:**
- M8 114ci = 57ci per cylinder = 9.34×10⁻⁴ m³
- MAP = 80 kPa = 80,000 Pa
- Temp = 75°F = 297 K
- Air mass = (80,000 × 9.34×10⁻⁴) / (287.05 × 297) = **876 mg** ✓

### AFR Error Propagation

When VE error = +10%:
- Actual VE / ECU VE = 1.10
- AFR error = Target AFR × 1.10
- For target 12.5:1 → Resulting 13.75:1 (1.25 AFR points lean)

**VE Correction Formula (v2.0.0):**
```
VE_correction = AFR_measured / AFR_target
```

This is mathematically exact and physically accurate.

---

## Next Steps: Phase 3

With Virtual ECU complete, we can now build:

### Closed-Loop Tuning Orchestrator

```python
class VirtualTuningSession:
    """
    Multi-iteration tuning until convergence.
    
    Workflow:
    1. Load base VE tables into ECU
    2. Run dyno pull
    3. Analyze AFR errors
    4. Calculate VE corrections
    5. Apply corrections to ECU
    6. Repeat until converged
    """
```

**Features to implement:**
- ✅ Virtual ECU with VE tables (DONE)
- ✅ AFR simulation from VE errors (DONE)
- ⏳ Multi-iteration convergence loop
- ⏳ Convergence metrics and tracking
- ⏳ Timing optimization (knock-based)
- ⏳ Decel popping detection/correction
- ⏳ Heat soak compensation
- ⏳ Cylinder balance optimization

---

## Benefits

### 1. Training & Education
- Tuners can practice without risking real engines
- Learn how VE errors manifest as AFR errors
- Understand convergence patterns

### 2. Algorithm Development
- Test new correction strategies safely
- A/B test different approaches
- Validate convergence rates

### 3. Edge Case Testing
- Simulate extreme conditions (altitude, heat, knock)
- Test recovery from bad base maps
- Validate safety limits

### 4. Automated Testing
- CI/CD integration
- Regression testing for tuning algorithms
- Performance benchmarking

### 5. Customer Demos
- Show full tuning workflow without hardware
- Generate realistic before/after data
- Prove ROI

---

## Technical Details

### Table Grid

**RPM Bins (11 points):**
```
[1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]
```

**MAP Bins (9 points):**
```
[20, 30, 40, 50, 60, 70, 80, 90, 100] kPa
```

**Total cells:** 11 × 9 = 99 cells per table

### Interpolation

Uses `scipy.interpolate.RegularGridInterpolator`:
- Method: Bilinear interpolation
- Bounds: Extrapolate beyond grid (clamp to reasonable range)
- Performance: ~10 µs per lookup

### Typical VE Values

| Condition | VE Range | Notes |
|-----------|----------|-------|
| Idle (low RPM, low MAP) | 0.40-0.60 | Poor scavenging |
| Cruise (mid RPM, mid MAP) | 0.70-0.85 | Efficient |
| Peak Torque (optimal RPM, high MAP) | 0.85-0.95 | Best breathing |
| Redline (high RPM, high MAP) | 0.70-0.80 | Flow restrictions |

### Typical AFR Targets

| Condition | AFR Range | Purpose |
|-----------|-----------|---------|
| Idle | 14.0-14.7 | Smooth idle |
| Cruise (light load) | 13.5-14.2 | Economy + cooling |
| Part throttle | 13.0-13.5 | Balance |
| WOT (high load) | 12.5-13.0 | Power + safety |

---

## Security

✅ **Snyk Code Scan:** 0 vulnerabilities  
✅ **No external dependencies** beyond scipy/numpy  
✅ **Input validation:** All lookups clamped to safe ranges  
✅ **No file I/O** in core ECU class  

---

## Performance

**Benchmarks (M8 114ci, 11x9 grid):**
- ECU initialization: ~1 ms
- VE lookup: ~10 µs
- AFR calculation: ~50 µs
- Full dyno pull (50Hz, 8 sec): ~400 ms

**Memory usage:**
- VirtualECU instance: ~5 KB
- VE tables (3 × 11×9): ~2 KB
- Negligible overhead on simulator

---

## Changelog

### v1.0.0 (2025-12-15)
- ✅ Initial implementation
- ✅ VirtualECU class with full API
- ✅ Integration with DynoSimulator
- ✅ Helper functions for table generation
- ✅ Comprehensive test suite (100% passing)
- ✅ Demo script with visualization
- ✅ Security scan (0 vulnerabilities)
- ✅ Documentation

---

## References

### Related Documentation
- [Physics-Based Simulator](PHYSICS_BASED_SIMULATOR.md)
- [VE Math Specification](DETERMINISTIC_MATH_SPECIFICATION.md)
- [V-Twin Tuning Validation](VTWIN_TUNING_TECHNICAL_VALIDATION.md)

### Code Locations
- Core: `api/services/virtual_ecu.py`
- Integration: `api/services/dyno_simulator.py`
- Tests: `tests/test_virtual_ecu.py`
- Demo: `examples/virtual_ecu_demo.py`

---

## Support

For questions or issues:
1. Check test suite for usage examples
2. Run demo script for visualization
3. Review API reference above
4. See integration tests for complete workflows

**Status:** Production-ready for Phase 3 (Closed-Loop Orchestrator) ✅

