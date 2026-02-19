# Quick Start: Simulator Analysis

## Problem Solved ✅

**Before:** When you ran a simulator pull and analyzed it, the analysis would use random data instead of your actual pull data, giving you different HP/TQ numbers than what you saw during the pull.

**Now:** The analysis uses the exact data from your simulator pull, so the results match what you saw!

## How to Use (Web UI)

### Step 1: Start Simulator
1. Open JetDrive Command Center
2. Click "Start Simulator"
3. Select engine profile (e.g., M8-114)
4. Click "Start"

### Step 2: Run a Pull
1. Click "Trigger Pull" button
2. Watch the gauges as RPM climbs
3. Note the peak HP and torque displayed
4. Wait for pull to complete (RPM drops back to idle)

### Step 3: Analyze
1. Click "Analyze" button
2. The system automatically uses your pull data
3. Results will match what you saw during the pull! ✅

That's it! The system now automatically saves and uses your actual pull data.

## How It Works

```
Your Pull → Saved Automatically → Used in Analysis
  110 HP  →   (in memory)      →     110 HP ✅
```

## API Usage (Advanced)

If you're using the API directly:

```bash
# 1. Start simulator
curl -X POST http://localhost:5000/api/jetdrive/simulator/start

# 2. Trigger pull
curl -X POST http://localhost:5000/api/jetdrive/simulator/pull

# 3. Wait for pull to complete (check status until state is "idle" or "cooldown")
curl http://localhost:5000/api/jetdrive/simulator/status

# 4. Analyze using the pull data
curl -X POST http://localhost:5000/api/jetdrive/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "my_test",
    "mode": "simulator_pull"
  }'
```

## Troubleshooting

### "No simulator pull data available"

**Cause:** You tried to analyze before running a pull.

**Solution:** 
1. Click "Trigger Pull"
2. Wait for pull to complete
3. Then click "Analyze"

### "Simulator not running"

**Cause:** Simulator was stopped or never started.

**Solution:**
1. Click "Start Simulator"
2. Wait for it to start
3. Then trigger a pull

### Results still don't match

**Cause:** You might be looking at different runs.

**Solution:**
1. Make sure you're viewing the correct run in the results panel
2. Check the run ID matches
3. Peak values should be within 1-2 HP/TQ due to processing

## What Changed?

### Before (Old Behavior)
- ❌ Analysis generated new random data
- ❌ Results didn't match your pull
- ❌ Confusing and unpredictable

### After (New Behavior)
- ✅ Analysis uses your actual pull data
- ✅ Results match what you saw
- ✅ Consistent and predictable

## Technical Details

When you click "Analyze" with the simulator active:

1. **Data Capture**: The simulator stores every data point during your pull (RPM, HP, TQ, AFR, MAP, etc.)

2. **Automatic Save**: The system saves this data to a CSV file in the `uploads/` directory

3. **Analysis**: The analysis engine processes your actual pull data

4. **Results**: You get results based on what actually happened during your pull

## Files Created

Each simulator pull creates a CSV file:
```
uploads/
  └── sim_20231215_123456_pull.csv  ← Your pull data
```

You can open this file to see the exact data that was analyzed.

## Comparison

| Scenario | Old System | New System |
|----------|-----------|------------|
| Pull shows 110 HP | Analysis: 96 HP ❌ | Analysis: 110 HP ✅ |
| Pull shows 122 TQ | Analysis: 108 TQ ❌ | Analysis: 122 TQ ✅ |
| AFR at 5000 RPM: 12.8 | Analysis: Random ❌ | Analysis: 12.8 ✅ |
| Reproducibility | Different every time ❌ | Same every time ✅ |

## Benefits

✅ **Trust**: Results match what you see
✅ **Consistency**: Same pull = same analysis
✅ **Debugging**: Can inspect the actual data file
✅ **Learning**: Understand how changes affect results
✅ **Validation**: Verify the system is working correctly

## Questions?

**Q: Does this work with real hardware?**
A: This fix is specifically for the simulator. Real hardware already uses actual data.

**Q: Can I still use the old random mode?**
A: Yes, use `mode: "simulate"` in the API, but the UI automatically uses the better mode.

**Q: Where is my data saved?**
A: In the `uploads/` directory as CSV files.

**Q: Can I delete the CSV files?**
A: Yes, they're just for your reference. The analysis results are saved separately.

**Q: Does this slow down the analysis?**
A: No, it's actually faster because it doesn't need to generate random data.

## Next Steps

1. Try running a few pulls with different profiles
2. Compare the results
3. Experiment with different AFR targets
4. Build confidence in the system!

Happy tuning! 🏍️💨

