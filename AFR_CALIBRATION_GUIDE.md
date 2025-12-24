# AFR Sensor Calibration Guide

## Overview

This guide explains how to calibrate your Innovate DLG-1 AFR sensors for accurate readings in DynoAI.

## Why Calibrate?

AFR sensors can drift over time due to:
- Sensor age and wear
- Contamination from fuel additives or oil
- Manufacturing tolerances between sensors
- Environmental factors

**Free air calibration** ensures your sensors read the correct AFR value when exposed to atmospheric air (20.9 AFR).

## Quick Start

### 1. Prepare for Calibration

```bash
# Prerequisites
- Sensors removed from exhaust (free air)
- Engine running or bench power supply connected
- Sensors warmed up for 30-60 seconds
- COM port identified (e.g., COM5)
```

### 2. Run Calibration Tool

```bash
python scripts/calibrate_afr.py COM5
```

### 3. Follow On-Screen Instructions

The tool will:
1. Collect 30 samples from each sensor
2. Calculate average AFR readings
3. Compare to expected free air AFR (20.9)
4. Recommend calibration offsets
5. Optionally update `config/afr_calibration.json`

## Expected Values

| Condition | AFR Range | Status |
|-----------|-----------|--------|
| **Free Air (Calibration)** | 20.5 - 21.3 | ✓ Good - No calibration needed |
| **Free Air (Close)** | 19.9 - 22.9 | ~ Acceptable - Minor calibration recommended |
| **Free Air (Off)** | < 19.9 or > 22.9 | ✗ Bad - Calibration required |

## Calibration File Structure

`config/afr_calibration.json`:

```json
{
  "base_divisor": 409.6,
  "channels": {
    "1": {
      "name": "Sensor A / Channel 1",
      "enabled": true,
      "offset_afr": 0.0,
      "multiplier": 1.0,
      "last_free_air_reading": null,
      "calibration_date": null
    },
    "2": {
      "name": "Sensor B / Channel 2",
      "enabled": true,
      "offset_afr": 0.0,
      "multiplier": 1.0,
      "last_free_air_reading": null,
      "calibration_date": null
    }
  }
}
```

### Calibration Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `offset_afr` | AFR offset added to raw reading | `-0.6` (subtract 0.6 from reading) |
| `multiplier` | Multiplier applied after offset | `1.01` (1% increase) |
| `enabled` | Enable/disable channel | `true` / `false` |

## Manual Calibration

If you prefer to manually set offsets:

### Calculate Offset

```
Offset = Expected AFR - Measured AFR
Offset = 20.9 - Measured AFR
```

**Examples:**
- Sensor reads **21.5** in free air → Offset = `20.9 - 21.5 = -0.6`
- Sensor reads **20.3** in free air → Offset = `20.9 - 20.3 = +0.6`

### Apply Offset

Edit `config/afr_calibration.json`:

```json
{
  "channels": {
    "1": {
      "offset_afr": -0.6  // Sensor was reading 0.6 too high
    },
    "2": {
      "offset_afr": 0.6   // Sensor was reading 0.6 too low
    }
  }
}
```

### Restart DynoAI

Changes take effect when the application restarts.

## Verification

After applying calibration, verify with the monitoring tool:

```bash
python scripts/calibration_monitor.py COM5
```

**Expected Results (in free air):**
- Both sensors should read **20.5 - 21.3 AFR**
- Readings should be stable (±0.2 AFR)

## Troubleshooting

### Sensor Reads Too High (e.g., 22.0 AFR)

**Solution:** Use **negative** offset

```json
"offset_afr": -1.1  // 22.0 - 20.9 = 1.1, so offset = -1.1
```

### Sensor Reads Too Low (e.g., 19.5 AFR)

**Solution:** Use **positive** offset

```json
"offset_afr": 1.4  // 20.9 - 19.5 = 1.4
```

### Readings Are Erratic (jumping around)

**Possible causes:**
- Sensor not fully warmed up (wait longer)
- Poor connections or cable damage
- Sensor contamination (clean or replace)
- Electrical interference

### No Readings

**Check:**
1. COM port is correct
2. DLG-1 is powered on
3. USB cable is connected
4. No other programs using the port (close LM Programmer)

### One Sensor Works, Other Doesn't

**Check:**
1. Both sensors are powered
2. Both sensors are warmed up
3. Channel is enabled in calibration file:
   ```json
   "enabled": true
   ```

## Advanced: Multiplier Calibration

For sensors with **non-linear drift** across AFR range:

1. Calibrate offset at free air (20.9 AFR)
2. Test at stoichiometric (14.7 AFR on running engine)
3. If error persists, adjust multiplier:

```json
"multiplier": 1.02  // 2% increase across all readings
```

**Example:**
- Free air correct after offset
- But reads 14.4 instead of 14.7 at stoich
- Multiplier = 14.7 / 14.4 = 1.0208
- Set `"multiplier": 1.02`

## Calibration Schedule

### When to Calibrate

- **New sensors:** Before first use
- **Routine:** Every 3-6 months
- **After contamination:** If sensor exposed to oil, coolant, or rich fuel
- **Inconsistent readings:** When data doesn't match expected AFR

### Best Practices

1. ✅ Calibrate sensors together (both channels at once)
2. ✅ Use clean, ambient air (not near exhaust or fuel vapors)
3. ✅ Allow full warmup time (30-60 seconds minimum)
4. ✅ Verify calibration after applying offsets
5. ❌ Don't calibrate in exhaust (use free air only)
6. ❌ Don't calibrate cold sensors

## Technical Details

### How Calibration Works

1. **Raw Reading:** Sensor sends digital signal via MTS protocol
2. **Base Conversion:** `AFR_raw = raw_value / 409.6`
3. **Apply Offset:** `AFR_offset = AFR_raw + offset_afr`
4. **Apply Multiplier:** `AFR_final = AFR_offset × multiplier`
5. **Display:** Final calibrated value shown in DynoAI

### Why 20.9 AFR?

Atmospheric air contains approximately **20.9% oxygen by volume**. When an AFR sensor measures air (not exhaust), it should read the stoichiometric AFR for burning pure oxygen in that air mixture, which equals approximately **20.9 AFR** for gasoline.

This is the industry-standard reference for wideband O2 sensor calibration.

## Files

| File | Purpose |
|------|---------|
| `config/afr_calibration.json` | Calibration data storage |
| `scripts/calibrate_afr.py` | Interactive calibration tool |
| `scripts/calibration_monitor.py` | Real-time AFR monitoring |
| `api/services/innovate_client.py` | Sensor driver with calibration support |

## Support

For issues or questions:
1. Check this guide's troubleshooting section
2. Review `SENSOR_B_FIXED_FINAL.md` for sensor configuration
3. Check DynoAI logs for error messages
4. Verify hardware connections

## References

- Innovate DLG-1 Manual
- Wideband O2 Sensor Theory
- Free Air Calibration Standards



