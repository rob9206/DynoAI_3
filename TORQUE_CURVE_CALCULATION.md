# Engine Torque & Power Curve Calculation

## Overview
The simulator creates realistic torque and horsepower curves for engine profiles using a multi-stage process that combines mathematical curve fitting with physics-based corrections.

---

## Stage 1: Base Torque Curve Generation
**Location:** `_precompute_curves()` (lines 626-707)

### Input Parameters (from EngineProfile)
- `max_tq` - Peak torque (e.g., 122 ft-lb for M8-114)
- `tq_peak_rpm` - RPM where peak torque occurs (e.g., 3200 RPM)
- `max_hp` - Peak horsepower (e.g., 110 HP for M8-114)
- `hp_peak_rpm` - RPM where peak HP occurs (e.g., 5000 RPM)
- `idle_rpm` - Idle speed (e.g., 900 RPM)
- `redline_rpm` - Maximum safe RPM (e.g., 5800 RPM)

### Algorithm

#### Step 1: Calculate Required Torque at HP Peak
```
tq_at_hp_peak = max_hp × 5252 / hp_peak_rpm

Example for M8-114:
tq_at_hp_peak = 110 × 5252 / 5000 = 115.5 ft-lb
```

This ensures the HP curve peaks at the correct RPM with the correct value.

#### Step 2: Create Anchor Points
Four key points define the curve shape:

```
Point 1 (Idle):     idle_rpm,    tq_idle (35% of max_tq)
Point 2 (TQ Peak):  tq_peak_rpm, max_tq
Point 3 (HP Peak):  hp_peak_rpm, tq_at_hp_peak
Point 4 (Redline):  redline_rpm, tq_redline (78% of tq_at_hp_peak)

Example for M8-114:
Point 1:  900 RPM,   42.7 ft-lb  (35% of 122)
Point 2: 3200 RPM,  122.0 ft-lb  (peak torque)
Point 3: 5000 RPM,  115.5 ft-lb  (torque at HP peak)
Point 4: 5800 RPM,   90.1 ft-lb  (78% of 115.5)
```

#### Step 3: Interpolate Between Points
Linear interpolation creates 1000 points between idle and redline:
```python
torque = np.interp(rpm_points, anchor_rpm, anchor_tq)
```

#### Step 4: Smooth the Curve
Apply 9-point moving average to remove sharp corners:
```python
window = 9
kernel = np.ones(window) / window
torque = np.convolve(torque, kernel, mode="same")
```

#### Step 5: Enforce Exact Peaks
Global scaling ensures exact peak torque:
```python
torque *= max_tq / actual_peak_tq
```

Smoothstep adjustment ensures correct torque at HP peak:
```python
# Gradually blend correction from tq_peak to hp_peak
x = (rpm - tq_peak_rpm) / (hp_peak_rpm - tq_peak_rpm)
w = x² × (3 - 2x)  # smoothstep function
torque *= 1.0 + (correction_factor - 1.0) × w
```

#### Step 6: Calculate HP Curve
```
HP = Torque × RPM / 5252
```

### Result
Smooth, realistic torque and HP curves stored for runtime interpolation.

---

## Stage 2: Real-Time Torque Calculation
**Location:** `_calculate_effective_torque()` (lines 970-1037)

During simulation, the base torque is modified by physics corrections:

```
Effective_Torque = Base_Torque 
                  × VE
                  × (1 - Pumping_Loss)
                  × Thermal_Factor
                  × Air_Density_Factor
                  × Mechanical_Efficiency
                  × Knock_Factor
```

### Correction Factors

#### 1. Volumetric Efficiency (VE)
**Location:** `_get_volumetric_efficiency()` (lines 713-798)

Represents how well cylinders fill with air/fuel mixture.

**At WOT (TPS > 80%):**
- Ramps up from idle: 88% → 100%
- Plateaus at tq_peak_rpm: 100% (peak VE)
- Holds through hp_peak_rpm: 100%
- Tapers at redline: 100% → 86%

**At Part Throttle:**
- Gaussian shape centered at tq_peak_rpm
- Reduced by throttle position: VE × (TPS / 100)
- Additional penalties at low RPM (poor scavenging) and high RPM (flow restrictions)

**Example:**
```
At 3200 RPM, 100% TPS: VE = 1.0 (peak)
At 3200 RPM, 50% TPS:  VE = 0.5 (half)
At 900 RPM, 100% TPS:  VE = 0.88 (ramp-up)
```

#### 2. Pumping Losses
**Location:** `_get_pumping_losses()` (lines 800-836)

Power consumed moving air through restricted throttle.

**Vacuum Loss (dominant at low throttle):**
```
vacuum_loss = (100 - TPS) / 100 × 0.40
+ extra 0.15 penalty if TPS < 5%

Example:
Closed throttle (0%): 0.40 + 0.15 = 0.55 (55% loss)
Half throttle (50%):  0.25 (25% loss)
WOT (100%):          0.00 (no vacuum loss)
```

**RPM Friction Loss:**
```
friction_loss = (RPM / redline_rpm) × 0.15

Example at 5800 RPM (redline):
friction_loss = 1.0 × 0.15 = 0.15 (15% loss)
```

**Total:** `min(1.0, vacuum_loss + friction_loss)`

#### 3. Thermal Correction
**Location:** `_get_thermal_correction()` (lines 838-858)

Power varies with engine temperature.

**Optimal:** 180°F (no correction)
**Cold:** 1% loss per 10°F below optimal
**Hot:** 1.5% loss per 10°F above optimal

```
Example:
140°F: 1.0 - (40/10 × 0.01) = 0.96 (4% loss)
180°F: 1.0 (optimal)
220°F: 1.0 - (40/10 × 0.015) = 0.94 (6% loss)
```

#### 4. Air Density Correction
**Location:** `_get_air_density_correction()` (lines 860-913)

Uses SAE J1349 method for air density.

**Standard Conditions:** 59°F, 29.92 inHg, 0% humidity

**Correction Factor:**
```
density_ratio = (pressure / std_pressure) 
               × (std_temp / current_temp)
               × humidity_correction

Example:
75°F, 29.92 inHg, 50% humidity:
density_ratio ≈ 0.97 (3% loss from temperature)

90°F, 28.5 inHg, 80% humidity:
density_ratio ≈ 0.89 (11% loss from heat/humidity/altitude)
```

#### 5. Mechanical Efficiency
**From Profile:** Accounts for friction, parasitic losses

- V-twins: 0.85-0.87 (85-87%)
- Sportbikes: 0.90 (90%, less friction)

#### 6. Knock Factor
**Location:** `_check_knock_conditions()` (lines 915-967)

If knock detected (lean AFR, high IAT, high temp):
```
knock_factor = 1.0 - (timing_retard_deg × 0.01)
             = 1.0 - (4 × 0.01)
             = 0.96 (4% loss from timing retard)
```

---

## Stage 3: Physics Simulation
**Location:** `_update_physics()` (lines 1083-1161)

### Forward Simulation (Engine drives drum)
```
1. Get effective_torque from Stage 2
2. Scale for unit conversion: torque_scaled = torque × scale_factor (50.0)
3. Calculate angular acceleration: α = torque_scaled / total_inertia
4. Update angular velocity: ω_new = ω_old + α × dt
5. Apply drag: ω_new = ω_new × (1 - drag_factor)
6. Convert to RPM: rpm = ω × 60 / (2π)
```

### Reverse Measurement (Dyno measures from drum)
```
1. Measure actual angular acceleration: α_net = (ω_new - ω_old) / dt
2. Infer torque from drum: dyno_torque = (I_total × α_net) / scale_factor
3. Calculate HP: dyno_hp = dyno_torque × rpm / 5252
```

This simulates how a real inertia dyno works!

---

## Example: M8-114 at 5000 RPM, WOT

### Base Curve
```
Base torque: 115.5 ft-lb (from curve)
```

### Corrections (typical conditions)
```
VE:               1.00  (peak VE range)
Pumping Loss:     0.03  (minimal at WOT + high RPM friction)
Thermal:          1.00  (optimal temp)
Air Density:      0.97  (warm day)
Mechanical Eff:   0.87  (V-twin friction)
Knock:            1.00  (no knock)
```

### Effective Torque
```
effective_torque = 115.5 × 1.0 × 0.97 × 1.0 × 0.97 × 0.87 × 1.0
                 = 94.7 ft-lb
```

### Physics Simulation (assuming moderate acceleration)
```
torque_scaled = 94.7 × 50.0 = 4735
α = 4735 / 7.6 = 623 rad/s²

After dt (0.02s):
ω increases by 12.46 rad/s
RPM increases by ~120 RPM per tick
```

### Dyno Measurement
```
Measured α_net ≈ 623 rad/s² (from drum acceleration)
dyno_torque = (7.6 × 623) / 50.0 = 94.7 ft-lb ✓
dyno_hp = 94.7 × 5000 / 5252 = 90.1 HP

Note: Slightly less than profile max (110 HP) due to:
- Air density loss: 3%
- Mechanical efficiency: 13%
- Pumping losses: 3%
Total reduction: ~19% → 110 × 0.81 = 89 HP ✓
```

---

## Key Tuning Parameters

### For Curve Shape
- Engine profile specs (max_tq, max_hp, peak RPMs)
- These define the ideal "perfect conditions" curve

### For Realistic Behavior
- `dyno_inertia` - Controls acceleration rate (currently 6.75 for M8)
- `torque_to_angular_accel_scale` - Unit conversion factor (50.0)
- `mechanical_efficiency` - Friction losses (0.85-0.90)
- `volumetric_efficiency_peak` - Max cylinder filling (0.85-0.95)

### For Environmental Effects
- `ambient_temp_f` - Air temperature (default 75°F)
- `barometric_pressure_inhg` - Atmospheric pressure (default 29.92)
- `humidity_pct` - Relative humidity (default 50%)

---

## Summary

The simulator creates realistic dyno behavior by:

1. **Generating smooth torque curves** from profile specs
2. **Applying physics corrections** for VE, losses, environment
3. **Simulating rotational dynamics** with realistic inertia
4. **Measuring power from drum acceleration** like a real inertia dyno

This produces curves that match real-world dyno results, including environmental effects, tuning errors, and transient behavior!
