# Testing the AI Model Correction System (v3 Session)

This guide covers multiple ways to test and verify that the new AI correction system is working correctly.

## Overview

The v3 AI correction system uses:
- **Gaussian Process (GP) Surrogate** - Learns VE corrections from observations
- **Pull Advisor** - Recommends optimal RPM/MAP points to test using Bayesian optimization
- **Math Integration** - Uses core VE math to calculate corrections from AFR measurements
- **Simulation Pipeline** - Can simulate pulls using DynoSimulator + VirtualECU

## Quick Test Methods

### 1. Run Automated Unit Tests

```bash
# Run all v3 module tests
pytest tests/test_v3_modules.py -v

# Run specific test classes
pytest tests/test_v3_modules.py::TestGPSurrogate -v
pytest tests/test_v3_modules.py::TestPullAdvisor -v
```

**What it tests:**
- GP surrogate can learn from observations
- Pull advisor suggests valid recommendations
- Convergence detection works
- Operator vetoes are respected
- Unsafe points are filtered out

### 2. Run Math Integration Verification Script

```bash
# From project root
python scripts/verify_math_integration.py
```

**What it tests:**
- Session creation works
- Raw AFR data ingestion triggers VE math calculation
- Calculated VE values match expected math (AFR ratio)
- Simulation pipeline (`simulate_pull_realistic`) works end-to-end
- Observations are stored correctly in GP surrogate

**Expected output:**
```
=== DynoAI V3: Math Integration Verification ===

[OK] Session Created: <session_id>
Simulating Pull:
  RPM: 3000.0
  MAP: 80.0 kPa
  AFR: 14.0 (Target: 13.0)
  Base VE: 80.0%

[OK] Pull Ingested (Pull #1)
  Observations Added: 1

Observation Found in GP Surrogate:
  RPM: 3000.0
  MAP: 80.0
  VE Absolute: 86.1538%
  Expected Absolute VE: 86.1538%

[OK] SUCCESS: Calculated Absolute VE matches Core Math expectation!
```

### 3. Manual UI Testing (Frontend)

#### Test Workflow:
1. **Start Backend Server**
   ```bash
   cd api
   python app.py
   ```

2. **Start Frontend Dev Server**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Navigate to JetDrive Page**
   - Open `http://localhost:5173/jetdrive`
   - Click "Start AI Session" or "New Session"

4. **Verify AI Coach Updates**
   - After starting session, AI Coach should show:
     - Coverage percentages (Overall, Front, Rear)
     - Next pull recommendation (RPM/MAP)
     - Uncertainty map
     - Convergence status

5. **Trigger a Simulated Pull**
   - Enable "SIMULATOR MODE" toggle
   - Click "Trigger Pull"
   - Wait for pull to complete (state changes: idle → pull → decel → cooldown → idle)

6. **Verify AI Coach Updates After Pull**
   - AI Coach should automatically update after pull completes
   - Check console for: `[AI Coach] Pull complete event received`
   - Check console for: `[AI Coach] Starting simulate() after pull completion`
   - Coverage percentages should increase
   - Next pull recommendation should change

7. **Verify Corrections Are Generated**
   - After AI Coach updates, check:
     - VE Heatmap shows corrections (colored cells)
     - Correction values are reasonable (±20% range)
     - "Accept Corrections" button becomes enabled

8. **Test Multiple Pulls**
   - Trigger 3-5 pulls at different RPM/MAP points
   - Verify:
     - Coverage increases with each pull
     - Uncertainty decreases
     - Pull advisor suggests different points (not repeating same cell)
     - Hit count penalty prevents over-sampling (cells hit >5 times get penalized)

9. **Test Accept Corrections**
   - Click "Accept Corrections" button
   - Verify:
     - No 400 errors in console
     - Toast shows success message
     - Run ID is generated
     - Corrections are materialized

### 4. API Testing (Using curl or Postman)

#### Create a Session
```bash
curl -X POST http://localhost:5001/api/v3/session/create \
  -H "Content-Type: application/json" \
  -d '{
    "engine_family": "m8_114",
    "rpm_bins": [2000, 3000, 4000, 5000, 6000],
    "map_bins": [40, 60, 80, 100]
  }'
```

**Response:**
```json
{
  "session_id": "abc123...",
  "estimated_pulls": 15,
  "grid_size": {"rpm": 5, "map": 4}
}
```

#### Get Next Pull Recommendation
```bash
curl http://localhost:5001/api/v3/session/<session_id>/next-pull
```

**Response:**
```json
{
  "rpm": 4500,
  "map_kpa": 100,
  "pull_mode": "steady_state",
  "reason": "High uncertainty in WOT zone",
  "alternatives": [...]
}
```

#### Simulate a Pull (Realistic Mode)
```bash
curl -X POST http://localhost:5001/api/v3/session/<session_id>/simulate-pull \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "realistic",
    "rpm": 4500,
    "map_kpa": 100
  }'
```

**Response:**
```json
{
  "pull_number": 1,
  "observations_added": 25,
  "target_rpm": 4500,
  "target_map_kpa": 100,
  "convergence": {...},
  "next_suggestion": {...},
  "mode": "realistic",
  "afr_metrics": {
    "max_afr_error": 0.3,
    "mean_afr_error": 0.15,
    "data_points": 25,
    "zones_corrected": 8,
    "max_ve_correction_pct": 12.5
  }
}
```

#### Check Convergence Status
```bash
curl http://localhost:5001/api/v3/session/<session_id>/convergence
```

**Response:**
```json
{
  "converged": false,
  "coverage_pct": 35.2,
  "mean_uncertainty": 0.85,
  "pulls_remaining": 8
}
```

#### Get Uncertainty Map
```bash
curl http://localhost:5001/api/v3/session/<session_id>/uncertainty-map
```

**Response:**
```json
{
  "rpm_bins": [2000, 3000, 4000, 5000, 6000],
  "map_bins": [40, 60, 80, 100],
  "uncertainty": [[0.5, 0.8, ...], [...], ...],
  "confidence": [[0.9, 0.7, ...], [...], ...]
}
```

#### Materialize Run (Generate Corrections File)
```bash
curl -X POST http://localhost:5001/api/v3/session/<session_id>/materialize-run
```

**Response:**
```json
{
  "run_id": "v3_abc123_20260219_153045",
  "ve_2d_path": "/path/to/VE_Corrections_2D.csv",
  "ve_delta_path": "/path/to/VE_Correction_Delta_DYNO.csv"
}
```

## Comprehensive Test Scenarios

### Scenario 1: Fresh Session → First Pull
**Goal:** Verify system initializes correctly and first pull works

**Steps:**
1. Create new session
2. Get next pull recommendation (should suggest WOT sweep)
3. Simulate pull at recommended point
4. Verify:
   - Observations added > 0
   - Coverage increases from 0%
   - Next recommendation changes
   - Uncertainty map shows data

### Scenario 2: Multiple Pulls → Convergence
**Goal:** Verify system learns and converges

**Steps:**
1. Create session
2. Run 10 simulated pulls (use advisor recommendations)
3. After each pull, check:
   - Coverage increases
   - Mean uncertainty decreases
   - Pull advisor suggests different points
4. After 10 pulls, verify:
   - Coverage > 50%
   - Convergence status shows progress
   - Uncertainty map shows lower values in sampled areas

### Scenario 3: Hit Count Penalty
**Goal:** Verify system avoids over-sampling same cells

**Steps:**
1. Create session
2. Manually simulate pulls at same RPM/MAP (e.g., 4000 RPM, 80 kPa) 10 times
3. Verify:
   - After 5 hits, advisor starts suggesting different points
   - After 50 hits, that cell gets very low weight (penalty = 0.01)
   - Advisor prioritizes unexplored areas

### Scenario 4: Math Verification
**Goal:** Verify VE corrections match expected math

**Steps:**
1. Create session
2. Ingest pull with known AFR values:
   - Measured AFR: 14.0
   - Target AFR: 13.0
   - Base VE: 80%
   - Expected correction: 14.0 / 13.0 = 1.0769 (+7.69%)
   - Expected absolute VE: 80% * 1.0769 = 86.15%
3. Verify stored observation has VE ≈ 86.15%

### Scenario 5: Operator Veto
**Goal:** Verify vetoed points are excluded

**Steps:**
1. Create session
2. Get recommendation (e.g., 5000 RPM, 100 kPa)
3. Veto that point: `POST /api/v3/session/<id>/veto` with `{"rpm": 5000, "map_kpa": 100, "reason": "test"}`
4. Get next recommendation again
5. Verify: New recommendation is different from vetoed point

### Scenario 6: End-to-End Workflow
**Goal:** Test complete workflow from session creation to corrections export

**Steps:**
1. Create session
2. Run 5 simulated pulls (using advisor recommendations)
3. Check convergence status
4. Materialize run (generate corrections files)
5. Verify:
   - Run ID is generated
   - CSV files are created
   - Files contain valid VE correction data
   - Frontend can accept corrections

## Debugging Tips

### Check Session State
```python
from api.services.v3_session_service import _get_session

session = _get_session("<session_id>")
print(f"Observations: {len(session.surrogate.observations)}")
print(f"Is fitted: {session.surrogate.is_fitted}")
print(f"Coverage: {session.advisor.check_convergence().coverage_pct}%")
```

### Inspect GP Surrogate
```python
session = _get_session("<session_id>")
surrogate = session.surrogate

# Check observations
for obs in surrogate.observations[-5:]:  # Last 5
    print(f"Pull #{obs.pull_number}: RPM={obs.rpm}, MAP={obs.map_kpa}, VE={obs.ve_delta}%")

# Check uncertainty map
unc_map = surrogate.get_uncertainty_map()
print(f"Uncertainty range: {unc_map.min():.2f} - {unc_map.max():.2f}")
```

### Check Pull Advisor Logic
```python
session = _get_session("<session_id>")
advisor = session.advisor

# Get next recommendation
rec = advisor.suggest_next_pull()
print(f"Next: {rec.rpm} RPM @ {rec.map_kpa} kPa")
print(f"Reason: {rec.reason}")

# Check hit counts
unc_map = session.surrogate.get_uncertainty_map()
weights = advisor._importance_weights()
hit_penalty = advisor._get_hit_count_penalty()
weighted = unc_map * weights * hit_penalty
print(f"Max weighted uncertainty: {weighted.max():.2f}")
```

## Common Issues and Solutions

### Issue: "No cached v3 corrections found"
**Solution:** Run `simulate()` or `simulate_pull_realistic()` first to generate corrections

### Issue: AI Coach not updating after pull
**Solution:** 
- Check console for `dynoai:simulator-pull-complete` event
- Verify `v3.simulate()` is being called
- Check for errors in console

### Issue: Pull advisor keeps suggesting same point
**Solution:**
- Check hit count penalty is working
- Verify uncertainty map is updating
- Check if all other points are vetoed/unsafe

### Issue: Corrections seem wrong
**Solution:**
- Verify AFR measurements are correct
- Check base VE values are reasonable
- Run math verification script to validate calculations

## Performance Benchmarks

Expected performance:
- **Session creation:** < 100ms
- **Pull simulation (realistic):** 2-5 seconds
- **GP refit (100 observations):** < 5 seconds
- **Pull recommendation:** < 50ms
- **Uncertainty map generation:** < 100ms

## Next Steps

After verifying the system works:
1. Run full test suite: `pytest tests/`
2. Test with real dyno data (if available)
3. Monitor performance with many observations (100+)
4. Test edge cases (empty sessions, single observation, etc.)
