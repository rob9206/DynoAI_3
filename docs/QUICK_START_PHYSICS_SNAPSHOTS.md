# Quick Start: Physics Snapshots

## Overview

Physics snapshots provide detailed insights into the simulator's internal calculations. Use them for research, debugging, or validating physics models.

## Basic Usage

### 1. Enable Snapshot Collection

```python
from api.services.dyno_simulator import DynoSimulator

sim = DynoSimulator()
sim.start()

# Enable before triggering a pull
sim.enable_snapshot_collection(True)
```

### 2. Trigger a Pull

```python
sim.trigger_pull()

# Wait for completion
import time
while sim.state in ["pull", "decel", "cooldown"]:
    time.sleep(0.1)
```

### 3. Get Snapshots

```python
snapshots = sim.get_physics_snapshots()
print(f"Collected {len(snapshots)} snapshots")
```

## What's in a Snapshot?

Each snapshot contains 20+ data points:

```python
snapshot = snapshots[0]

# Basic dynamics
snapshot.rpm                    # Engine RPM
snapshot.angular_velocity       # rad/s
snapshot.angular_acceleration   # rad/s²

# Throttle
snapshot.tps_actual            # Actual throttle position
snapshot.tps_target            # Target throttle position

# Torque breakdown
snapshot.torque_base           # Base from engine curve
snapshot.torque_effective      # After all corrections
snapshot.horsepower            # Calculated HP

# Correction factors (0.0 to 1.0)
snapshot.volumetric_efficiency
snapshot.pumping_loss
snapshot.thermal_factor
snapshot.air_density_factor
snapshot.mechanical_efficiency

# Temperatures
snapshot.engine_temp_f
snapshot.iat_f
snapshot.ambient_temp_f

# Environmental
snapshot.barometric_pressure_inhg
snapshot.humidity_pct

# Knock detection
snapshot.knock_detected        # True/False
snapshot.knock_risk_score      # 0.0 to 1.0

# Timestamp
snapshot.timestamp             # Unix timestamp
```

## Examples

### Example 1: Find Peak Torque

```python
snapshots = sim.get_physics_snapshots()

# Find peak
peak = max(snapshots, key=lambda s: s.torque_effective)

print(f"Peak torque: {peak.torque_effective:.1f} ft-lb at {peak.rpm:.0f} RPM")
print(f"Correction factors:")
print(f"  VE: {peak.volumetric_efficiency:.3f}")
print(f"  Thermal: {peak.thermal_factor:.3f}")
print(f"  Air Density: {peak.air_density_factor:.3f}")
```

### Example 2: Analyze Knock Risk

```python
# Find high-risk points
high_risk = [s for s in snapshots if s.knock_risk_score > 0.5]

if high_risk:
    print(f"⚠️ {len(high_risk)} high knock risk points:")
    for snap in high_risk:
        print(f"  RPM {snap.rpm:.0f}: Risk={snap.knock_risk_score:.3f}, "
              f"IAT={snap.iat_f:.0f}°F")
```

### Example 3: Correction Factor Analysis

```python
# Analyze what factors dominate power loss
for snap in snapshots[::10]:  # Every 10th sample
    total_correction = (
        snap.volumetric_efficiency *
        (1.0 - snap.pumping_loss) *
        snap.thermal_factor *
        snap.air_density_factor *
        snap.mechanical_efficiency
    )
    
    efficiency_pct = total_correction * 100
    
    print(f"RPM {snap.rpm:4.0f}: {efficiency_pct:.1f}% "
          f"(VE={snap.volumetric_efficiency:.2f}, "
          f"Air={snap.air_density_factor:.3f})")
```

### Example 4: Export to CSV

```python
import csv

snapshots = sim.get_physics_snapshots()

with open('physics_analysis.csv', 'w', newline='') as f:
    # Get field names from first snapshot
    fieldnames = snapshots[0].to_dict().keys()
    
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    
    for snap in snapshots:
        writer.writerow(snap.to_dict())

print("Exported to physics_analysis.csv")
```

### Example 5: Plot Correction Factors

```python
import matplotlib.pyplot as plt

snapshots = sim.get_physics_snapshots()

rpms = [s.rpm for s in snapshots]
ve = [s.volumetric_efficiency for s in snapshots]
air = [s.air_density_factor for s in snapshots]
thermal = [s.thermal_factor for s in snapshots]

plt.figure(figsize=(10, 6))
plt.plot(rpms, ve, label='Volumetric Efficiency')
plt.plot(rpms, air, label='Air Density')
plt.plot(rpms, thermal, label='Thermal Factor')
plt.xlabel('RPM')
plt.ylabel('Correction Factor')
plt.title('Physics Correction Factors vs RPM')
plt.legend()
plt.grid(True)
plt.savefig('corrections.png')
```

## Performance Considerations

### Memory Usage

- **Per snapshot:** ~20 bytes
- **500 snapshots per pull:** ~10 KB
- **Impact:** Negligible for modern systems

### CPU Overhead

- **Disabled:** 0% overhead (default)
- **Enabled:** <1% overhead

### When to Use

✅ **Use snapshots when:**
- Researching physics models
- Debugging unexpected behavior
- Validating against real dyno data
- Understanding correction factor interactions
- Developing tuning strategies

❌ **Don't use snapshots when:**
- Running production pulls (unless needed)
- Memory is constrained (<100 MB available)
- You only need standard pull data

## Disabling Snapshots

```python
# Disable after collection
sim.enable_snapshot_collection(False)

# Snapshots are automatically cleared on next pull
sim.trigger_pull()
```

## Advanced: Snapshot Filtering

```python
# Get only high-RPM snapshots
high_rpm = [s for s in snapshots if s.rpm > 4000]

# Get only knock events
knock_events = [s for s in snapshots if s.knock_detected]

# Get specific RPM range
mid_range = [s for s in snapshots if 3000 <= s.rpm <= 4000]
```

## Tips

1. **Always enable before pull** - Snapshots only collected during PULL state
2. **Disable when not needed** - Save memory and CPU
3. **Export immediately** - Data cleared on next pull
4. **Sample rate is 50Hz** - 500 snapshots typical for 10-second pull
5. **Use every Nth snapshot** - Reduce data volume with `snapshots[::N]`

## Troubleshooting

**Q: No snapshots collected?**
A: Make sure to enable before triggering pull:
```python
sim.enable_snapshot_collection(True)  # Before trigger
sim.trigger_pull()
```

**Q: Snapshots empty after second pull?**
A: Snapshots cleared at start of each pull. Export data before next pull.

**Q: How to compare multiple pulls?**
A: Export each to separate CSV files:
```python
# Pull 1
sim.trigger_pull()
# ... wait ...
export_snapshots(sim.get_physics_snapshots(), 'pull1.csv')

# Pull 2
sim.trigger_pull()
# ... wait ...
export_snapshots(sim.get_physics_snapshots(), 'pull2.csv')
```

---

**See Also:**
- `docs/PHYSICS_BASED_SIMULATOR.md` - Complete physics documentation
- `docs/SIMULATOR_ENHANCEMENTS_V2.md` - Feature details
- `tests/test_physics_simulator.py::TestEnhancements` - Code examples

