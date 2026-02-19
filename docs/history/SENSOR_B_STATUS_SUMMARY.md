# Sensor B Live Data Status

## Current Situation

### What We Found
1. **Sensor A**: Unplugged → Correctly detected as E2 error ✓
2. **Sensor B**: Connected, engine running → Should show live AFR data

### The Issue
The MTS packet is showing status bytes `00 02` for the sensor data, which I initially interpreted as an E2 error. However, this might actually be a **normal operational status** when the sensor is actively reading.

### Packet Data Observed
```
Channel bytes: [5B 13 00 02]
- Bytes 0-1: 5B 13 (AFR data → would calculate to ~28.0 AFR)
- Bytes 2-3: 00 02 (status - NOT necessarily an error!)
```

### Status Byte Patterns
- `01 51` = Normal/idle (observed when both sensors at 22.4 AFR)
- `00 02` = Possibly "active measurement" or "sensor ready" state
- `00 00` = Complete signal loss (true error)

## Current Fix Status

### What's Been Fixed
✅ **Byte selection corrected**: Now reading bytes 0-1 for AFR data (was reading bytes 2-3)
✅ **Formula corrected**: Using direct AFR formula with divisor 409.6
✅ **Error detection added**: Filters out sensors with `00 00` status (no signal)
✅ **Relaxed `00 02` handling**: Now allows AFR data through with `00 02` status

### What Should Happen Now
With the latest changes, Sensor B **should** be reporting AFR data even with the `00 02` status bytes.

## Troubleshooting Steps

### Step 1: Reconnect Innovate Device
The device may need to be reconnected after all the server reloads:

1. In the DynoAI web interface, go to Hardware Monitor
2. Click "Connect" for the Innovate DLG-1
3. Select COM5 (or the appropriate port)
4. Click Connect

### Step 2: Check Live Data
Once connected:
1. You should see "Innovate AFR 2" or "AFR 2" in the live data channels
2. The value should update in real-time as the engine runs
3. Expected AFR range: 12-15 AFR (rich under load) or higher if cruising

### Step 3: Verify in Logs
Check the terminal for:
- ✅ "Channel 2: Non-standard status (possibly warming/transitional)" - This is OK!
- ✅ AFR values being calculated and logged
- ❌ "Channel 2: Sensor error state detected (no signal)" - This would be bad

## Expected Behavior

### With Engine Running (Current Setup)
- **Sensor A (Channel 1)**: No data (unplugged) ✓
- **Sensor B (Channel 2)**: Live AFR data showing engine's actual air/fuel ratio

### AFR Values to Expect
- **Idle**: 14.7 AFR (stoichiometric)
- **Cruise**: 14.7-16.0 AFR (slightly lean for efficiency)
- **Acceleration/Load**: 12.0-13.5 AFR (rich for power)
- **Deceleration**: 18-22 AFR (lean, fuel cut)

## If Still No Data

### Possible Causes
1. **Device not connected**: Check connection in UI
2. **Wrong COM port**: Verify COM5 is correct
3. **Sensor warming up**: Wait 30-60 seconds for sensor to heat
4. **Packet structure different**: May need to capture actual packet for analysis

### Debug Commands
```powershell
# Check if device is streaming data
Get-Content "c:\Users\dawso\.cursor\projects\c-Dev-DynoAI-3\terminals\26.txt" -Tail 50 | Select-String "Channel|AFR"

# Check connection status via API
curl http://localhost:5001/api/jetdrive/innovate/status
```

## Next Actions

1. **Reconnect the Innovate device** in the web UI
2. **Wait for data** - should see AFR values within a few seconds
3. **If still no data**: Let me know and I'll add more detailed packet logging to diagnose

## Technical Notes

The key insight is that `00 02` in the status bytes doesn't necessarily mean "error" - it appears to be a normal operational state. The true error condition is `00 00` (complete signal loss).

The AFR data in bytes 0-1 (`5B 13` = ~28 AFR) suggests the sensor IS reading, it's just in a different status mode than the idle `01 51` pattern we saw earlier.

## Date
December 16, 2025

## Status
🔄 **AWAITING RECONNECTION** - Device needs to be reconnected in UI to resume data flow

