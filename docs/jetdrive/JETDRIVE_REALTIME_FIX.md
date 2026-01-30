# JetDrive Realtime Analysis Fix - NoneType Comparison Error

## Problem
The JetDrive realtime analysis was generating recurring errors:
```
Realtime analysis error (non-blocking): '>' not supported between instances of 'NoneType' and 'float'
```

This error was occurring repeatedly, causing the queue to fill up and drop items.

## Root Cause
The error was in the `_detect_alerts()` method in `api/services/jetdrive_realtime_analysis.py`.

Multiple issues were found:

### 1. **TPS (Throttle Position Sensor) Comparison** (Line 451)
```python
tps = data.get("tps", self._last_tps)
if tps > FROZEN_TPS_THRESHOLD:  # ❌ tps could be None
```

**Problem:** When `data.get("tps", self._last_tps)` returns `None` (which happens when TPS is explicitly `None` in the data, not just missing), the comparison `tps > FROZEN_TPS_THRESHOLD` fails because Python cannot compare `None` with a float.

### 2. **AFR (Air-Fuel Ratio) Comparison** (Line 464-474)
```python
if afr is not None:
    if afr < AFR_MIN_PLAUSIBLE:  # ❌ afr could be NaN
```

**Problem:** The code checked for `None` but not for `NaN` (Not a Number) values, which can also cause comparison issues.

### 3. **Staleness Comparison** (Line 487)
```python
if staleness > CHANNEL_STALE_THRESHOLD_SEC:  # ❌ staleness could be None
```

**Problem:** The `get_freshness()` method could return `None` values in edge cases.

## Solution

### Fixed `_detect_alerts()` Method

1. **Proper TPS handling with explicit None check:**
```python
tps = data.get("tps")

# Use fallback for None TPS values
if tps is None:
    tps = self._last_tps

# Frozen RPM detection with None check
if (
    self._last_rpm is not None and
    rpm is not None and
    abs(rpm - self._last_rpm) < 1.0 and
    tps is not None and  # ✅ Added explicit None check
    tps > FROZEN_TPS_THRESHOLD and
    current_time - self._last_rpm_time > FROZEN_RPM_THRESHOLD_SEC
):
    # ... alert logic
```

2. **Added NaN check for AFR:**
```python
if afr is not None and not math.isnan(afr):  # ✅ Check both None and NaN
    if afr < AFR_MIN_PLAUSIBLE:
        # ... alert logic
```

3. **Added None check for staleness:**
```python
if staleness is not None and staleness > CHANNEL_STALE_THRESHOLD_SEC:  # ✅ Check None
    # ... alert logic
```

4. **Added NaN check for TPS tracking:**
```python
# Track TPS for frozen RPM detection context
if tps is not None and not math.isnan(tps):  # ✅ Check both None and NaN
    self._last_tps = tps
```

## Changes Made

**File:** `api/services/jetdrive_realtime_analysis.py`

- **Lines 440-497:** Updated `_detect_alerts()` method with proper None/NaN checks
- **Lines 359-362:** Updated TPS tracking logic with NaN check

## Testing

After applying this fix:

1. **No more NoneType comparison errors** - The error messages should stop appearing
2. **Queue stability** - The queue should no longer fill up and drop items
3. **Proper alert detection** - Alerts will only trigger when valid data is present

## How to Apply

The fix has already been applied to the code. To activate it:

### If running in development mode:
```bash
# Simply restart the dev server (it will auto-reload)
# Or if not auto-reloading:
# Stop with Ctrl+C and restart
python start-dev.bat
```

### If running in Docker:
```bash
# Rebuild and restart the API container
docker-compose restart api
```

### If running the PowerShell script:
```powershell
# Stop and restart
.\start-jetdrive.ps1
```

## Verification

After restarting, you should see:

✅ **No more "Realtime analysis error" messages**
✅ **No more "Queue full, dropped oldest item" messages**
✅ **Clean HTTP 200 responses** for JetDrive endpoints:
   - `GET /api/jetdrive/hardware/monitor/status`
   - `GET /api/jetdrive/hardware/live/data`

## Technical Notes

### Why This Happened

The JetDrive hardware can send incomplete or malformed data packets, especially:
- During connection initialization
- When sensors are disconnected or faulty
- During rapid data streaming (20Hz update rate)
- When the dyno is in certain operating modes

### Prevention Strategy

The fix implements defensive programming:
1. **Always check for None before comparisons** with numeric literals
2. **Check for NaN values** when dealing with floating-point sensor data
3. **Use explicit fallback values** instead of relying on default parameters
4. **Non-blocking error handling** - errors are logged but don't stop data capture

### Performance Impact

**Zero performance impact** - The additional None/NaN checks are:
- O(1) operations
- Compiled by Python's bytecode optimizer
- Required only once per 50ms aggregation window
- Much faster than exception handling

## Related Files

- `api/services/jetdrive_realtime_analysis.py` - Main realtime analysis engine (FIXED)
- `api/services/jetdrive_live_queue.py` - Live data queue manager (catches errors, no changes needed)
- `api/routes/jetdrive.py` - JetDrive API endpoints (no changes needed)

## Additional Context

This is part of the JetDrive Live Auto-Tune system (RT-150) which provides:
- Real-time AFR monitoring during dyno pulls
- Coverage map tracking (RPM x MAP grid)
- VE delta calculation for instant tune corrections
- Quality metrics and alert detection

The fix ensures robust operation even with imperfect sensor data.
