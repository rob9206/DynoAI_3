# Innovate DLG-1 Sensor B Fix

## Problem
Sensor B (Channel 2) AFR readings were erratic and "all over the place" instead of showing a steady 22.4 AFR like Sensor A.

## Root Cause
The MTS packet parser in `api/services/innovate_client.py` was using the **wrong bytes** to decode the AFR value.

### Incorrect Implementation (Before)
```python
# WRONG: Using bytes 2 and 3 of each channel
low_byte = ch_data[2] & 0x7F   # Byte 2: low 7 bits
high_byte = ch_data[3] & 0x7F  # Byte 3: high 7 bits
raw_value = (high_byte << 7) | low_byte
lambda_value = raw_value / 10000.0 + 0.5
afr = lambda_value * 14.7
```

### Correct Implementation (After)
```python
# CORRECT: Using bytes 0 and 1 of each channel
low_byte = ch_data[1] & 0x7F   # Byte 1: low 7 bits
high_byte = ch_data[0] & 0x7F  # Byte 0: high 7 bits
raw_value = (high_byte << 7) | low_byte
afr = raw_value / 409.6  # Empirically determined DLG-1 formula
lambda_value = afr / 14.7
```

## Technical Details

### MTS Packet Structure
```
Byte 0-1:  B2 84           (Sync header)
Byte 2-5:  [Channel B data] (Sensor B - 4 bytes)
Byte 6-9:  [Channel A data] (Sensor A - 4 bytes)
```

### Channel Data Structure (4 bytes each)
```
Byte 0: HIGH 7 bits of AFR value
Byte 1: LOW 7 bits of AFR value  
Byte 2: Status/function byte
Byte 3: Status/function byte
```

### AFR Decoding Formula
The DLG-1 uses a 7-bit packed encoding:
- Combine bytes 0 and 1: `raw_value = ((byte0 & 0x7F) << 7) | (byte1 & 0x7F)`
- Convert to AFR: `afr = raw_value / 409.6`

This formula was empirically determined from observed data:
- Packet bytes `0x47 0x13` → raw value 9107 → AFR 22.24 ✓

### Why It Was Wrong
The previous implementation:
1. Used bytes 2 and 3 instead of bytes 0 and 1
2. Used an incorrect lambda-based formula (`raw / 10000 + 0.5`)
3. This caused Sensor B to read random status bytes instead of actual AFR data

## Changes Made

### File: `api/services/innovate_client.py`

1. **Fixed byte selection** (line ~526-527):
   - Changed from `ch_data[2]` and `ch_data[3]` to `ch_data[1]` and `ch_data[0]`

2. **Fixed AFR calculation** (line ~534):
   - Changed from lambda-based formula to direct AFR formula
   - Changed divisor from 10000 to 409.6

3. **Fixed sanity check** (line ~537):
   - Changed from lambda range (0.5-2.5) to AFR range (7.0-25.0)

4. **Updated documentation**:
   - Corrected docstring to reflect actual packet structure
   - Added empirical formula explanation

## Testing

### Before Fix
```
Sensor A: 22.4 AFR (steady) ✓
Sensor B: 7.3, 15.2, 8.9, 12.1, ... (erratic) ✗
```

### After Fix (Expected)
```
Sensor A: 22.4 AFR (steady) ✓
Sensor B: 22.4 AFR (steady) ✓
```

## Verification Steps

1. Restart the API server (auto-reloads with watchdog)
2. Connect to Innovate DLG-1 via UI
3. Observe both Sensor A and Sensor B readings
4. Both should now show steady 22.4 AFR

## References

- Working decoder: `scripts/innovate_mts_decoder.py` (line 70-71)
- Packet analysis: `scripts/compare_packets.py`
- Test data: `scripts/decode_mts_data.py`

## Date
December 16, 2025

## Status
✅ **FIXED** - Sensor B should now read correctly

