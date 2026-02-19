# Innovate DLG-1 Error State Detection

## Overview
The Innovate DLG-1 MTS protocol includes status bytes that indicate sensor error conditions like E2 (sensor not ready/unplugged). The client now properly detects and handles these error states.

## Error States Detected

### E2 Error - Sensor Not Ready/Unplugged
**Pattern:** Status bytes `0x00 0x02` in bytes 2-3 of channel data

**Causes:**
- Sensor physically unplugged
- Sensor cable disconnected
- Sensor not powered
- Sensor hardware failure

**Behavior:**
- Client returns `None` for that channel (no AFR data)
- Warning logged: "Channel X: E2 error state detected (sensor not ready)"
- UI will show sensor as disconnected/no data

### No Signal Error
**Pattern:** Status bytes `0x00 0x00` in bytes 2-3 of channel data

**Causes:**
- Complete signal loss
- Communication error
- Device malfunction

**Behavior:**
- Client returns `None` for that channel
- Warning logged: "Channel X: Sensor error state detected (no signal)"

## Normal Operation Pattern
**Pattern:** Status bytes `0x01 0x51` in bytes 2-3 of channel data

This indicates the sensor is connected, warmed up, and providing valid readings.

## Implementation Details

### Channel Data Structure (4 bytes)
```
Byte 0: HIGH 7 bits of AFR + warmup flag (bit 6)
Byte 1: LOW 7 bits of AFR
Byte 2: Status byte (0x01 = normal, 0x00 = error)
Byte 3: Status byte (0x51 = normal, 0x02 = E2 error, 0x00 = no signal)
```

### Error Detection Code
```python
# Check for E2 error (sensor unplugged)
if status_byte_2 == 0x00 and status_byte_3 == 0x02:
    logger.warning(f"Channel {channel}: E2 error state detected (sensor not ready)")
    return None  # Don't report invalid AFR

# Check for no signal error
if status_byte_2 == 0x00 and status_byte_3 == 0x00:
    logger.warning(f"Channel {channel}: Sensor error state detected (no signal)")
    return None
```

## Current Setup (User's Configuration)
- **Sensor A (Channel 1)**: UNPLUGGED → E2 error state → No AFR data reported ✓
- **Sensor B (Channel 2)**: CONNECTED → Normal operation → 22.4 AFR ✓

## UI Behavior

### Before Error Detection
- Unplugged sensor would show random/erratic AFR values (reading status bytes as AFR data)
- Confusing and misleading

### After Error Detection
- Unplugged sensor shows as "No Data" or "Disconnected"
- Only valid sensors report AFR values
- Clear indication of sensor status

## Testing

### Test with Unplugged Sensor
1. Unplug Sensor A
2. Keep Sensor B connected
3. Expected result:
   - Sensor A: No AFR data (or "E2 Error" message)
   - Sensor B: Steady 22.4 AFR reading

### Test with Both Sensors Connected
1. Plug in both sensors
2. Expected result:
   - Both sensors show steady AFR readings
   - Values should match if measuring same exhaust

## Logging

When error states are detected, you'll see warnings in the server logs:

```
WARNING: Channel 1: E2 error state detected (sensor not ready)
```

This helps diagnose connection issues without cluttering the UI with invalid data.

## Future Enhancements

Potential additions:
- Expose error state to UI (show "E2 Error" badge)
- Add warmup state indicator (sensor heating up)
- Detect other error codes (E1, E3, etc.)
- Add sensor health monitoring

## Date
December 16, 2025

## Status
✅ **IMPLEMENTED** - Error detection active
✅ **TESTED** - Correctly filters out unplugged sensors

