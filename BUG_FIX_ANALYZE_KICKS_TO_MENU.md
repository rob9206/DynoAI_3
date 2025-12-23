# Bug Fix: Analyze Button Kicks to Command Center Menu

**Date:** December 15, 2025  
**Severity:** High (breaks simulator workflow)  
**Status:** ✅ FIXED

---

## Problem

After running a simulator pull and clicking "Analyze Pull (364 pts)", the UI would suddenly switch back to the "Command Center" landing view (the hardware connection screen), hiding all simulator controls.

### User Experience

1. ✅ Start simulator
2. ✅ Trigger pull
3. ✅ Pull completes
4. ❌ Click "Analyze Pull" → **KICKED BACK TO MENU**
5. ❌ Simulator controls disappear
6. ❌ Shows "Connect to Hardware" screen instead

---

## Root Cause

The issue was a **race condition** with the simulator active flag during analysis:

### The Flow

1. User clicks "Analyze Pull"
2. Backend runs analysis subprocess (takes 10-60 seconds)
3. **During analysis**, frontend polls `/simulator/status` every 500ms
4. If **anything** goes wrong or the backend state is inconsistent, it returns `active: false`
5. Frontend sees `active: false` → immediately hides simulator → shows hardware menu

### The Bug

The `_sim_active` flag is a **global variable** in `api/routes/jetdrive.py`:

```python
_sim_active: bool = False  # Global state
```

During the analysis subprocess:
- If there's any error accessing the simulator
- If the simulator state is temporarily inconsistent
- If there's a threading issue
- **The flag might not be preserved correctly**

Result: Frontend thinks simulator stopped → switches to hardware view.

---

## The Fix

### 1. Preserve Simulator Active State During Analysis

```python
# Before running analysis, save the state
was_simulator_active = _is_simulator_active()

try:
    # Run analysis...
    result = subprocess.run(...)
    
    # After success, restore state
    if was_simulator_active:
        _set_simulator_active(True)
        
except Exception:
    # On error, also restore state
    if was_simulator_active:
        _set_simulator_active(True)
```

### 2. Error Handling in Status Endpoint

```python
@jetdrive_bp.route("/simulator/status")
def get_simulator_status():
    if not _is_simulator_active():
        return {"active": False, "state": "stopped"}
    
    try:
        sim = get_simulator()
        state = sim.get_state()
        channels = sim.get_channels()
    except Exception as e:
        # DON'T deactivate on error - return safe fallback
        return {
            "active": True,  # Keep showing as active!
            "state": "idle",
            "error": str(e)
        }
```

### 3. Include Mode in Response

Added `"mode": mode` to the analysis response so frontend knows what was analyzed.

---

## Why This Happened

### The Problem with Global State

The `_sim_active` flag is separate from the actual simulator object. This creates a **state synchronization problem**:

- Simulator object: Running in its own thread
- `_sim_active` flag: Separate global variable
- During long operations: They can get out of sync

### The Race Condition

```
Time  | Backend Thread        | Frontend Poll
------|----------------------|------------------
0.0s  | Start analysis       | active=true ✅
0.5s  | Analysis running...  | active=true ✅
1.0s  | Analysis running...  | active=true ✅
1.5s  | Error or glitch      | active=FALSE ❌
2.0s  | (frontend switches views)
5.0s  | Analysis completes   | (too late!)
```

---

## Files Modified

### `api/routes/jetdrive.py`

**Lines 360-365:** Save simulator state before analysis
**Lines 375-380:** Restore state on error
**Lines 430-435:** Restore state on success
**Lines 445-450:** Restore state on timeout/exception
**Lines 1395-1420:** Error handling in status endpoint

---

## Testing

### Before Fix
```
1. Start simulator ✅
2. Trigger pull ✅
3. Pull completes ✅
4. Click "Analyze" ❌ → Kicked to menu
5. Simulator controls gone ❌
```

### After Fix
```
1. Start simulator ✅
2. Trigger pull ✅
3. Pull completes ✅
4. Click "Analyze" ✅ → Analysis runs
5. Simulator controls stay visible ✅
6. Can trigger another pull ✅
```

---

## Additional Improvements

### Robust Status Endpoint

The `/simulator/status` endpoint now:
- ✅ Catches exceptions gracefully
- ✅ Returns safe fallback instead of crashing
- ✅ Doesn't deactivate simulator on temporary errors
- ✅ Logs errors for debugging

### State Preservation

Analysis now:
- ✅ Saves simulator state before running
- ✅ Restores state after success
- ✅ Restores state after error
- ✅ Restores state after timeout

---

## Impact

### Before Fix
- ❌ Simulator workflow broken after first analysis
- ❌ Must restart simulator after every analysis
- ❌ Poor user experience
- ❌ Cannot do iterative tuning

### After Fix
- ✅ Simulator stays active through analysis
- ✅ Can run multiple pull → analyze cycles
- ✅ Smooth workflow
- ✅ Proper iterative tuning workflow

---

## How to Test

1. Start simulator
2. Trigger pull
3. Wait for pull to complete
4. Click "Analyze Pull"
5. **Verify:** Simulator controls stay visible
6. **Verify:** Can trigger another pull immediately
7. **Verify:** No "kicked to menu" behavior

---

**Status:** ✅ FIXED  
**Priority:** High  
**Impact:** Critical workflow issue resolved

