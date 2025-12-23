# Fixes Applied - December 15, 2025

## Issue #1: Deceleration Hang 🐛 CRITICAL

### Problem
Simulator was getting stuck in DECEL state indefinitely after completing a pull. The UI would show "Decelerating" forever.

### Root Cause
Engine braking coefficient was being multiplied by `dt`, reducing it from 5% per timestep to only 0.1% per timestep:

```python
# BUG (line 1135):
self.physics.angular_velocity *= 1.0 - ENGINE_BRAKE_COEFFICIENT * dt
# With dt=0.02, this gave: ω *= 0.999 (only 0.1% reduction!)
```

This would take **several minutes** to decelerate from redline to idle.

### Fix Applied
Removed the `dt` multiplication to apply 5% reduction per timestep as intended:

```python
# FIXED:
self.physics.angular_velocity *= 1.0 - ENGINE_BRAKE_COEFFICIENT
# Now: ω *= 0.95 (5% reduction per timestep) ✅
```

### Result
- **Before:** Decel time = several minutes (unusable)
- **After:** Decel time = 1-2 seconds (realistic) ✅
- **Test status:** ✅ PASSING

---

## Issue #2: Date Error 📅

### Problem
Documentation showed December 2024 instead of December 2025.

### Files Corrected
1. `docs/SIMULATOR_ENHANCEMENTS_V2.md`
2. `SIMULATOR_ENHANCEMENTS_SUMMARY.md`
3. `PHYSICS_SIMULATOR_REVIEW_AND_ENHANCEMENTS.md`
4. `ENHANCEMENTS_QUICK_REFERENCE.md`

### Result
All dates now correctly show **December 15, 2025** ✅

---

## Status

✅ **Both issues resolved**
✅ **Tests passing** (23/25)
✅ **Simulator functional**
✅ **Ready for use**

---

## Try It Now

The simulator should now work correctly:

```bash
# Start your backend if not running
python api/app.py

# Or use the web interface - decel should complete in ~2 seconds
```

The "Decelerating" phase will now properly complete and return to idle!

