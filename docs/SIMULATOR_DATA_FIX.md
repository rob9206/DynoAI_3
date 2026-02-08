# Simulator Pull Data Fix - Implementation Summary

## Problem Fixed

The UI was showing the same synthetic data repeatedly instead of displaying actual simulator pull results. This was caused by a **silent fallback** mechanism that downgraded from real pull data to synthetic data without user awareness.

## Root Causes Identified

1. **Stale React Query Cache**: The `pullDataStatus` query polled every 2 seconds, so when users clicked "Analyze" immediately after a pull, the status was stale and showed `has_data: false`
2. **Silent Backend Fallback**: The backend silently fell back to synthetic `--simulate` mode when pull data wasn't available
3. **Similar Synthetic Data**: The synthetic data generator created structurally identical data each time, making all results look the same

## Changes Made

### Frontend Changes (`frontend/src/pages/JetDriveAutoTunePage.tsx`)

#### 1. Fresh Pull Data Check (Lines ~1408-1440)
**Before:**
```typescript
if (isSimulatorActive && mode === 'simulate') {
    if (pullDataStatus?.has_data) {  // STALE!
        actualMode = 'simulator_pull';
    } else {
        actualMode = 'simulate';  // Silent fallback
    }
}
```

**After:**
```typescript
if (isSimulatorActive && mode === 'simulate') {
    // FRESH check instead of stale React Query cache
    const freshStatusRes = await fetch(`${API_BASE}/simulator/pull-data`);
    const freshData = await freshStatusRes.json();
    
    if (freshData?.has_data) {
        actualMode = 'simulator_pull';
        console.log(`[Analyze] ✓ Using real pull data (${freshData.points} points)`);
    } else {
        console.warn('[Analyze] ⚠ No pull data - falling back to simulate');
        actualMode = 'simulate';
    }
}
```

#### 2. Mode Tracking State (Line ~637)
Added state to track which mode was actually used:
```typescript
const [selectedRunMode, setSelectedRunMode] = useState<'simulator_pull' | 'simulate' | 'csv' | null>(null);
```

#### 3. Mode Indicator Badge (Lines ~2567-2582)
Added visual indicator showing data source:
```typescript
{selectedRunMode && (
    <Badge 
        variant="outline" 
        className={selectedRunMode === 'simulator_pull' 
            ? "bg-blue-500/10 text-blue-400 border-blue-500/30" 
            : "bg-purple-500/10 text-purple-400 border-purple-500/30"}
    >
        {selectedRunMode === 'simulator_pull' ? '📊 Real Pull Data' : '🔮 Synthetic Data'}
    </Badge>
)}
```

### Backend Changes (`api/routes/jetdrive.py`)

#### Remove Silent Fallback (Lines ~694-708)
**Before:**
```python
if not pull_data or len(pull_data) == 0:
    logger.warning("No pull data available - falling back to simulate mode")
    mode = "simulate"
    cmd.append("--simulate")
    pull_data = None
```

**After:**
```python
if not pull_data or len(pull_data) == 0:
    logger.error("No pull data available when simulator_pull mode requested")
    return jsonify({
        "success": False,
        "error": "No pull data available. Complete a pull before analyzing.",
        "hint": "Trigger a WOT pull using the 'Trigger Pull' button, wait for it to complete, then click Analyze.",
        "mode_requested": "simulator_pull",
    }), 400
```

## Testing Instructions

### Test 1: Verify Real Pull Data is Used

1. Start the application (frontend and backend)
2. Navigate to the JetDrive page
3. Click "Start Simulator"
4. Click "Trigger Pull" and wait for the pull to complete (watch for "decel" or "cooldown" state)
5. Click "Analyze"
6. **Expected Results:**
   - Browser console shows: `[Analyze] ✓ Using real pull data (XXX points, XX.X HP)`
   - Toast notification says "from simulator pull data"
   - Results section shows blue badge: "📊 Real Pull Data"
   - VE table, coverage stats, and next test recommendations reflect the actual pull RPM range

### Test 2: Verify Error When No Pull Data

1. Start simulator
2. **Without triggering a pull**, click "Analyze"
3. **Expected Results:**
   - Error toast appears: "No pull data available. Complete a pull before analyzing."
   - Analysis does not proceed
   - No synthetic data is generated

### Test 3: Verify Multiple Pulls Generate Different Data

1. Start simulator
2. Trigger Pull #1 at 100% throttle → Analyze
3. Note the peak HP, VE corrections, and coverage stats
4. Trigger Pull #2 at 80% throttle → Analyze
5. **Expected Results:**
   - Pull #2 shows different peak HP (lower due to reduced throttle)
   - VE corrections differ based on actual AFR measurements
   - Coverage stats show different RPM/TPS zones
   - Each run has a unique run_id

### Test 4: Verify Synthetic Mode Still Works

1. Stop simulator (if running)
2. Click "Analyze" (should use simulate mode as fallback)
3. **Expected Results:**
   - Analysis completes with synthetic data
   - Results section shows purple badge: "🔮 Synthetic Data"
   - Toast says "from simulated data"

## Diagnostic Logging

The following console logs help diagnose issues:

- `[Analyze] Fetching fresh pull data status...` - Fresh check initiated
- `[Analyze] Fresh pull data status: {...}` - Shows actual pull data availability
- `[Analyze] ✓ Using real pull data (XXX points)` - Real data confirmed
- `[Analyze] ⚠ No pull data - falling back to simulate` - Fallback triggered
- `[Analyze] Mode: simulate → Actual mode: simulator_pull` - Mode upgrade occurred
- `[Analyze] Stale pullDataStatus (for comparison): {...}` - Shows what the old stale query had

## Files Modified

1. `frontend/src/pages/JetDriveAutoTunePage.tsx` - Fresh pull data check, mode tracking, UI indicator
2. `api/routes/jetdrive.py` - Remove silent fallback, return clear error

## Benefits

1. **Transparency**: Users can see whether they're viewing real or synthetic data
2. **Reliability**: Actual pull data is used when available (no more silent fallbacks)
3. **Debugging**: Enhanced logging makes it easy to diagnose mode selection issues
4. **User Experience**: Clear error messages guide users to complete a pull before analyzing

## Rollback Instructions

If issues occur, revert these commits:
- Frontend: Revert changes to `analyzeMutation` and restore original `pullDataStatus` check
- Backend: Restore the silent fallback logic at line 694-700

The system will fall back to the previous behavior (silent synthetic data generation).
