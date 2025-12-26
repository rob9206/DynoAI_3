# Simulator Pull Data Fix

## Problem

When running the dyno simulator and triggering a pull, the analysis would not use the actual simulated pull data. Instead, it would generate completely new random data, making the analysis results disconnected from what was displayed during the pull.

**Root Cause:**
- The simulator collects pull data in `DynoSimulator._pull_data` during a simulated pull
- The `/analyze` endpoint with `mode="simulate"` would call `jetdrive_autotune.py --simulate`
- This script generates fresh random data using `generate_simulated_dyno_run()`, completely ignoring the actual pull data

## Solution

Added a new analysis mode `simulator_pull` that:
1. Retrieves the actual pull data from the simulator
2. Saves it to a CSV file
3. Runs analysis on that CSV file

### Changes Made

#### 1. Backend API (`api/routes/jetdrive.py`)

**New Endpoint: `/simulator/save-pull`**
- Saves the last simulator pull data to a CSV file
- Maps simulator data format to analysis-expected format
- Returns the saved file path and metadata

**Enhanced: `/analyze` endpoint**
- Added new mode: `simulator_pull`
- When this mode is used:
  - Retrieves pull data from simulator
  - Saves it to CSV in uploads directory
  - Runs analysis on the saved CSV
  - Uses actual pull data instead of generating random data

#### 2. Frontend (`frontend/src/pages/JetDriveAutoTunePage.tsx`)

**Updated: `analyzeMutation`**
- Automatically detects when simulator is active
- When simulator is active and mode is 'simulate', uses 'simulator_pull' instead
- Ensures analysis always uses actual simulator pull data

### Data Flow

```
┌─────────────────┐
│ Simulator Pull  │
│  (generates     │
│   pull data)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  _pull_data     │
│  (in memory)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Save to CSV     │
│ (uploads dir)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Run Analysis    │
│ (jetdrive_      │
│  autotune.py)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Analysis Results│
│ (uses actual    │
│  pull data!)    │
└─────────────────┘
```

### CSV Format Mapping

The simulator stores data with these fields:
- `Engine RPM`
- `Torque`
- `Horsepower`
- `AFR Meas F` (front cylinder)
- `AFR Meas R` (rear cylinder)
- `MAP kPa`
- `TPS`
- `IAT F`

These are mapped to analysis-expected format:
- `timestamp_ms` - Generated from sample index (20Hz = 50ms intervals)
- `RPM` - From `Engine RPM`
- `Torque` - From `Torque`
- `Horsepower` - From `Horsepower`
- `AFR` - Average of front and rear AFR
- `MAP_kPa` - From `MAP kPa`
- `TPS` - From `TPS`
- `IAT` - From `IAT F`

## Usage

### Automatic (Recommended)

When using the JetDrive Command Center UI with simulator:
1. Start simulator
2. Trigger a pull
3. Wait for pull to complete
4. Click "Analyze"
5. The system automatically uses the actual pull data

### Manual API

```bash
# 1. Start simulator
curl -X POST http://localhost:5000/api/jetdrive/simulator/start \
  -H "Content-Type: application/json" \
  -d '{"profile": "m8_114"}'

# 2. Trigger pull
curl -X POST http://localhost:5000/api/jetdrive/simulator/pull

# 3. Wait for pull to complete (check status)
curl http://localhost:5000/api/jetdrive/simulator/status

# 4. Analyze using simulator pull data
curl -X POST http://localhost:5000/api/jetdrive/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "my_test_run",
    "mode": "simulator_pull",
    "afr_targets": {
      "20": 14.7,
      "40": 14.0,
      "60": 13.5,
      "80": 12.8,
      "100": 12.5
    }
  }'
```

## Testing

Run the automated test:

```bash
python test_simulator_pull_analysis.py
```

This test:
1. Starts the simulator
2. Triggers a pull
3. Waits for completion
4. Runs analysis with `simulator_pull` mode
5. Verifies the analysis results match the pull data

## Benefits

✅ **Consistency**: Analysis results now match what you see during the pull
✅ **Reproducibility**: Same pull data = same analysis results
✅ **Debugging**: Can save and inspect the exact data used for analysis
✅ **Accuracy**: No more random data generation during analysis
✅ **Transparency**: Clear data flow from simulator → CSV → analysis

## Backward Compatibility

- Old `mode="simulate"` still works (generates random data)
- New `mode="simulator_pull"` uses actual pull data
- Frontend automatically uses the correct mode when simulator is active
- No breaking changes to existing API contracts

