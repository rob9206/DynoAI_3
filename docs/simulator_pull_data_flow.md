# Simulator Pull Data Flow - Before and After

## Before (Problem)

```
┌──────────────────────────────────────────────────────────────┐
│                    SIMULATOR PULL                            │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  _pull_data     │
                    │  [160 points]   │
                    │  HP: 110.2      │
                    │  TQ: 122.5      │
                    └─────────────────┘
                              │
                              │ ❌ NOT USED!
                              │
                              ▼
                         (discarded)


┌──────────────────────────────────────────────────────────────┐
│                    USER CLICKS ANALYZE                        │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ mode="simulate" │
                    └─────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │ generate_simulated_dyno_run() │
              │ (creates NEW random data)     │
              └───────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  NEW DATA       │
                    │  [200 points]   │
                    │  HP: 95.7  ❌   │
                    │  TQ: 108.3 ❌   │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Analysis       │
                    │  (wrong data!)  │
                    └─────────────────┘

Result: Analysis shows different HP/TQ than what user saw during pull!
```

## After (Fixed)

```
┌──────────────────────────────────────────────────────────────┐
│                    SIMULATOR PULL                            │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  _pull_data     │
                    │  [160 points]   │
                    │  HP: 110.2      │
                    │  TQ: 122.5      │
                    └─────────────────┘
                              │
                              │ ✅ SAVED!
                              │
                              ▼


┌──────────────────────────────────────────────────────────────┐
│                    USER CLICKS ANALYZE                        │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │ mode="simulator_    │
                    │       pull"         │
                    └─────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │ 1. Get _pull_data from sim    │
              │ 2. Save to CSV file           │
              │ 3. Run analysis on CSV        │
              └───────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  SAME DATA      │
                    │  [160 points]   │
                    │  HP: 110.2  ✅  │
                    │  TQ: 122.5  ✅  │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Analysis       │
                    │  (correct data!)│
                    └─────────────────┘

Result: Analysis shows same HP/TQ that user saw during pull!
```

## Key Changes

### 1. New Endpoint: `/simulator/save-pull`

Allows manual saving of pull data:

```python
POST /api/jetdrive/simulator/save-pull
{
  "run_id": "my_run"  // optional
}

Response:
{
  "success": true,
  "run_id": "sim_20231215_123456",
  "csv_path": "uploads/sim_20231215_123456.csv",
  "points": 160
}
```

### 2. Enhanced: `/analyze` endpoint

New mode that uses actual pull data:

```python
POST /api/jetdrive/analyze
{
  "run_id": "my_run",
  "mode": "simulator_pull",  // ← NEW MODE
  "afr_targets": { ... }
}
```

### 3. Frontend Auto-Detection

```typescript
// OLD: Always used "simulate" mode
const mode = "simulate";

// NEW: Detects simulator and uses actual pull data
const actualMode = (isSimulatorActive && mode === 'simulate') 
  ? 'simulator_pull'  // ← Use actual pull data
  : mode;
```

## Data Mapping

Simulator data → Analysis format:

| Simulator Field | Analysis Field | Notes |
|----------------|----------------|-------|
| `Engine RPM` | `RPM` | Direct mapping |
| `Torque` | `Torque` | Direct mapping |
| `Horsepower` | `Horsepower` | Direct mapping |
| `AFR Meas F` + `AFR Meas R` | `AFR` | Average of both cylinders |
| `MAP kPa` | `MAP_kPa` | Direct mapping |
| `TPS` | `TPS` | Direct mapping |
| `IAT F` | `IAT` | Direct mapping |
| `timestamp` | `timestamp_ms` | Generated (20Hz = 50ms) |

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Data Source** | Random generation | Actual simulator pull |
| **Consistency** | ❌ Different every time | ✅ Same as displayed |
| **HP/TQ Values** | ❌ Random | ✅ Match pull display |
| **Reproducibility** | ❌ Impossible | ✅ Repeatable |
| **Debugging** | ❌ Can't inspect data | ✅ CSV file saved |
| **User Trust** | ❌ Confusing results | ✅ Expected results |

## Example Scenario

### Before:
1. User runs simulator pull
2. Sees: **110 HP @ 5000 RPM**
3. Clicks "Analyze"
4. Gets: **96 HP @ 4800 RPM** ❌ (different!)
5. User confused: "Why did the HP change?"

### After:
1. User runs simulator pull
2. Sees: **110 HP @ 5000 RPM**
3. Clicks "Analyze"
4. Gets: **110 HP @ 5000 RPM** ✅ (same!)
5. User happy: "Perfect, that's what I saw!"

## Testing

The automated test verifies:
- ✅ Simulator pull data is captured
- ✅ Data is saved to CSV correctly
- ✅ Analysis uses the saved data
- ✅ Results match the pull (within tolerance)

Run test:
```bash
python test_simulator_pull_analysis.py
```

Expected output:
```
============================================================
Testing Simulator Pull Data Analysis
============================================================

1. Starting simulator...
✅ Simulator started

2. Triggering pull...
✅ Pull triggered

3. Waiting for pull to complete...
   State: pull
   State: decel
   State: cooldown
✅ Pull completed

4. Checking pull data...
✅ Pull data available: 160 points
   Peak HP: 110.2
   Peak TQ: 122.5

5. Running analysis with simulator_pull mode...
✅ Analysis completed successfully

6. Verifying analysis used pull data...
   Analysis HP: 110.2
   Analysis TQ: 122.5
✅ Analysis results match pull data (within tolerance)
   HP difference: 0.0
   TQ difference: 0.0

7. Stopping simulator...
✅ Simulator stopped

============================================================
✅ ALL TESTS PASSED
============================================================
```

