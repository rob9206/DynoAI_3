# Troubleshooting: Virtual Tuning System

**Common issues and solutions**

---

## Issue: UI Shows "Iteration 0 / 10" and Stuck at 0%

### Cause
The first iteration takes 10-15 seconds to complete. The UI shows 0% until the first iteration finishes.

### What's Happening
```
Session starts → Status: RUNNING, Iteration: 0
  ↓ (10-15 seconds)
First iteration completes → Status: RUNNING, Iteration: 1
  ↓ (4-5 seconds per iteration)
Subsequent iterations → Progress updates
```

### Solution
**This is normal behavior!** Wait 10-15 seconds for the first iteration to complete.

The UI now shows:
```
"Running first iteration... This may take 10-15 seconds."
```

### Why It Takes Time
Each iteration:
1. Creates Virtual ECU (~0.1s)
2. Starts simulator (~0.5s)
3. Runs dyno pull (~8-10s) ← **Main time**
4. Analyzes AFR (~0.5s)
5. Calculates corrections (~0.2s)

**Total:** ~10-15 seconds for first iteration, ~4-5s for subsequent

---

## Issue: Session Status Shows "FAILED"

### Check Backend Logs
Look for error messages in the Flask console:
```
[ERROR] Tuning session failed: ...
```

### Common Causes

**1. Simulator Timeout**
```
Error: Pull did not complete within 30 seconds
```
**Solution:** Increase timeout in `virtual_tuning_session.py` line 380

**2. No Pull Data**
```
Error: No pull data collected
```
**Solution:** Check simulator state, ensure it's starting properly

**3. Missing Dependencies**
```
ModuleNotFoundError: No module named 'scipy'
```
**Solution:** `pip install scipy numpy pandas`

---

## Issue: Convergence Takes Too Long (>10 Iterations)

### Cause
- Starting VE error is very large (>20%)
- Corrections are too conservative
- Convergence threshold is too strict

### Solutions

**1. Increase correction limit:**
```python
config = TuningSessionConfig(
    max_correction_per_iteration_pct=20.0,  # Default: 15.0
)
```

**2. Relax convergence threshold:**
```python
config = TuningSessionConfig(
    convergence_threshold_afr=0.5,  # Default: 0.3
)
```

**3. Start with smaller VE error:**
```python
config = TuningSessionConfig(
    base_ve_scenario="custom",
    base_ve_error_pct=-5.0,  # Instead of -10.0
)
```

---

## Issue: Oscillation Detected

### Cause
Corrections are overshooting, causing AFR error to bounce back and forth.

### Solution

**1. Reduce correction limit:**
```python
config = TuningSessionConfig(
    max_correction_per_iteration_pct=10.0,  # Default: 15.0
)
```

**2. Disable oscillation detection temporarily:**
```python
config = TuningSessionConfig(
    oscillation_detection_enabled=False,
)
```

**3. Increase oscillation threshold:**
```python
config = TuningSessionConfig(
    oscillation_threshold=0.2,  # Default: 0.1
)
```

---

## Issue: UI Not Updating

### Check

**1. Is backend running?**
```bash
# Should see Flask server on port 5001
curl http://localhost:5001/api/virtual-tune/sessions
```

**2. Check browser console:**
- Open DevTools (F12)
- Look for network errors
- Check for CORS issues

**3. Verify session ID:**
```javascript
// In browser console
console.log('Session ID:', sessionId);
```

### Solution
- Restart backend
- Clear browser cache
- Check network tab for failed requests

---

## Issue: Backend Not Starting

### Check Dependencies

```bash
pip install flask numpy pandas scipy matplotlib
```

### Check Blueprint Registration

In `api/app.py`, verify:
```python
from api.routes.virtual_tune import virtual_tune_bp
app.register_blueprint(virtual_tune_bp)
```

### Check Imports

```bash
# Test imports
python -c "from api.services.virtual_ecu import VirtualECU; print('OK')"
python -c "from api.services.virtual_tuning_session import VirtualTuningOrchestrator; print('OK')"
```

---

## Issue: Tests Failing

### Run Tests Individually

```bash
# Test Virtual ECU
pytest tests/test_virtual_ecu.py -v

# Test Closed-Loop
pytest tests/test_closed_loop_tuning.py -v
```

### Common Test Issues

**1. Import errors:**
```bash
# Ensure you're in project root
cd C:\Dev\DynoAI_3
python -m pytest tests/test_virtual_ecu.py -v
```

**2. Tolerance issues:**
- Some tests have tolerance checks
- Interpolation can cause small variations
- Tolerances are set to accommodate this

---

## Performance Issues

### Iterations Taking Too Long (>20s each)

**Check:**
- Is simulator update rate too high?
- Are thermal effects enabled? (adds overhead)
- Is system under load?

**Solution:**
```python
config = SimulatorConfig(
    update_rate_hz=25.0,  # Reduce from 50Hz
    enable_thermal_effects=False,  # Disable if not needed
)
```

### Memory Usage High

**Check:**
- How many sessions are active?
- Are VE tables being stored?

**Solution:**
```python
# Clear old sessions
orchestrator.sessions.clear()
```

---

## Debugging Tips

### Enable Detailed Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Simulator State

```python
simulator = get_simulator()
print(f"State: {simulator.get_state().value}")
print(f"RPM: {simulator.physics.rpm}")
print(f"TPS: {simulator.physics.tps_actual}")
```

### Verify Virtual ECU

```python
from api.services.virtual_ecu import print_ecu_diagnostics

print_ecu_diagnostics(ecu, rpm=4000, map_kpa=80, actual_ve=0.85)
```

### Check Pull Data

```python
pull_data = simulator.get_pull_data()
print(f"Data points: {len(pull_data)}")
if pull_data:
    print(f"First point: {pull_data[0]}")
    print(f"Last point: {pull_data[-1]}")
```

---

## Known Limitations

### 1. First Iteration Delay
- First iteration takes 10-15 seconds
- This is expected (full dyno pull simulation)
- Subsequent iterations are faster (~4-5s)

### 2. Background Threading
- Sessions run in background threads
- May not see immediate progress
- Poll every 3 seconds for updates

### 3. Windows Console Encoding
- Emoji characters may not display
- Use `[OK]`, `[ERROR]` instead
- This is a Windows terminal limitation

---

## Getting Help

### Check Documentation
1. **[VIRTUAL_TUNING_COMPLETE_GUIDE.md](VIRTUAL_TUNING_COMPLETE_GUIDE.md)** - Complete guide
2. **[docs/CLOSED_LOOP_TUNING.md](docs/CLOSED_LOOP_TUNING.md)** - Technical details
3. **[VIRTUAL_TUNING_DOCS_INDEX.md](VIRTUAL_TUNING_DOCS_INDEX.md)** - All docs

### Run Tests
```bash
# Verify system works
pytest tests/test_virtual_ecu.py tests/test_closed_loop_tuning.py -v
```

### Check Examples
```bash
# Run demos
python examples/virtual_ecu_demo.py
python test_virtual_tune_quick.py  # Quick single-iteration test
```

---

## Quick Fixes

### UI Stuck at 0%
**Wait 10-15 seconds** - First iteration is running

### Session Not Starting
**Check backend logs** - Look for errors in Flask console

### No Progress Updates
**Increase poll interval** - Change from 2s to 3s in ClosedLoopTuningPanel.tsx

### Backend Errors
**Check dependencies** - Run `pip install -r requirements.txt`

---

## Summary

Most issues are related to:
1. ⏱️ **Timing** - First iteration takes 10-15 seconds (normal)
2. 🔌 **Backend** - Ensure Flask is running
3. 📦 **Dependencies** - Ensure all packages installed
4. 🔍 **Logging** - Check backend logs for errors

**The system works correctly - just needs patience for first iteration!** ✅







