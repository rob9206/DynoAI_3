# Quick Start: Run Comparison Table

## What is it?

The Run Comparison Table automatically appears on the JetDrive Auto Tune page after you complete 2 or more dyno runs. It provides a side-by-side comparison of your tuning iterations, making it easy to track improvements and validate changes.

## How to Use

### Step 1: Complete Multiple Runs

1. Navigate to **JetDrive Command Center** (Auto Tune page)
2. Connect to your dyno or start the simulator
3. Complete your first dyno run
4. Make tuning adjustments
5. Complete additional runs

### Step 2: View the Comparison

After completing 2+ runs, the comparison table automatically appears below your results section.

**You'll see**:
- All your recent runs in columns
- The first run marked as **BASELINE**
- Delta indicators showing improvements/decreases
- Color-coded metrics for easy scanning

### Step 3: Interpret the Results

#### HP/Torque Deltas
- 🟢 **Green ↗** = Improvement from baseline
- 🔴 **Red ↘** = Decrease from baseline  
- ⚪ **Gray —** = Minimal change (<0.5)

#### AFR Status
- 🟢 **OK/BALANCED** = Good tune
- 🔴 **LEAN** = Needs richening
- 🔵 **RICH** = Needs leaning

#### VE Cells
- Progress bar shows percentage of cells tuned correctly
- Higher percentage = better tune coverage
- Green number = cells that are OK
- Total = all cells with data

#### Issues
- ✓ **None** = Perfect tune, no corrections needed
- ⚠ **X lean** = Cells that need richening
- ⚠ **X rich** = Cells that need leaning

### Step 4: Track Progress

Use the comparison to:
- **Validate changes** - Did your adjustment improve HP?
- **Measure gains** - How much HP did you gain?
- **Identify regressions** - Did something get worse?
- **Verify consistency** - Are results repeatable?

## Example Workflow

### Scenario: Tuning a Harley M8-114

**Run 1 (Baseline)**
- Peak HP: 108.5 @ 5800 RPM
- Peak TQ: 115.2 @ 3400 RPM
- AFR Status: LEAN
- VE Cells: 45/120 OK (38%)
- Issues: 75 lean cells

**Run 2 (After VE correction)**
- Peak HP: 110.2 @ 5800 RPM (+1.7 HP 🟢)
- Peak TQ: 116.8 @ 3400 RPM (+1.6 TQ 🟢)
- AFR Status: BALANCED
- VE Cells: 98/120 OK (82%)
- Issues: 15 lean, 7 rich

**Run 3 (After fine-tuning)**
- Peak HP: 110.8 @ 5800 RPM (+2.3 HP 🟢)
- Peak TQ: 117.1 @ 3400 RPM (+1.9 TQ 🟢)
- AFR Status: OK
- VE Cells: 115/120 OK (96%)
- Issues: 3 lean, 2 rich

**Result**: +2.3 HP gain, 96% of cells tuned correctly!

## Tips & Tricks

### Best Practices

1. **Consistent Test Conditions**
   - Same ambient temperature
   - Same fuel level
   - Same coolant temperature
   - Helps ensure valid comparisons

2. **Make One Change at a Time**
   - Change VE, test, compare
   - Change spark, test, compare
   - Isolate the effect of each change

3. **Document Your Changes**
   - Note what you changed between runs
   - Use the run ID to track versions
   - Keep a tuning log

4. **Watch for Trends**
   - Consistent improvements = good direction
   - Inconsistent results = check test conditions
   - Plateauing = approaching optimal tune

### Common Questions

**Q: Why doesn't the table appear?**
A: You need at least 2 completed runs. Complete another run and it will appear automatically.

**Q: Can I compare specific runs?**
A: Currently shows the 5 most recent runs. Future versions will add run selection.

**Q: What if I want to compare more than 5 runs?**
A: The table shows the 5 most recent to keep it readable. Older runs are still saved and can be viewed individually.

**Q: Can I export the comparison?**
A: Not yet, but it's on the roadmap! For now, take a screenshot or manually record the data.

**Q: Why is my baseline different from what I expected?**
A: The baseline is always the first run in the comparison (leftmost column). This is typically your most recent run.

## Keyboard Shortcuts

- **Click run header** - View detailed results for that run
- **Scroll horizontally** - View more runs if table is wide
- **Click .PVV button** - Download Power Vision file for selected run

## Visual Guide

### Table Layout

```
┌─────────────┬──────────┬──────────┬──────────┬──────────┐
│ Metric      │ Run 1    │ Run 2    │ Run 3    │ Run 4    │
│             │ BASELINE │          │          │          │
├─────────────┼──────────┼──────────┼──────────┼──────────┤
│ Peak HP     │ 108.5    │ 110.2    │ 110.8    │ 111.2    │
│             │          │ +1.7 ↗   │ +2.3 ↗   │ +2.7 ↗   │
├─────────────┼──────────┼──────────┼──────────┼──────────┤
│ Peak Torque │ 115.2    │ 116.8    │ 117.1    │ 117.4    │
│             │          │ +1.6 ↗   │ +1.9 ↗   │ +2.2 ↗   │
├─────────────┼──────────┼──────────┼──────────┼──────────┤
│ AFR Status  │ LEAN     │ BALANCED │ OK       │ OK       │
├─────────────┼──────────┼──────────┼──────────┼──────────┤
│ VE Cells    │ 45/120   │ 98/120   │ 115/120  │ 118/120  │
│             │ ████░░   │ ████████ │ █████████│ █████████│
│             │ 38%      │ 82%      │ 96%      │ 98%      │
└─────────────┴──────────┴──────────┴──────────┴──────────┘
```

## Troubleshooting

### Table Not Appearing
- ✅ Check you have 2+ completed runs
- ✅ Refresh the page
- ✅ Check browser console for errors

### Incorrect Data
- ✅ Verify runs completed successfully
- ✅ Check manifest files exist in `runs/` directory
- ✅ Ensure analysis completed without errors

### Performance Issues
- ✅ Table is optimized for 5 runs
- ✅ Clear old runs if you have 100+ runs
- ✅ Check network speed for API calls

## Next Steps

After using the comparison table to validate your tune:

1. **Export .PVV file** - Click the .PVV button for your best run
2. **Flash to bike** - Use Power Vision to apply the tune
3. **Road test** - Verify the tune on the road
4. **Iterate** - Come back for fine-tuning if needed

## Related Documentation

- [RUN_COMPARISON_FEATURE.md](RUN_COMPARISON_FEATURE.md) - Technical details
- [QUICK_START.md](../QUICK_START.md) - General quick start guide
- [JETDRIVE_TESTING_OPTIONS.md](../JETDRIVE_TESTING_OPTIONS.md) - Testing options

## Feedback

Have suggestions for the comparison table? Let us know!

- Add run selection
- Export to CSV/PDF
- Overlay power curves
- Add custom metrics
- Your idea here!

---

**Happy Tuning! 🏍️💨**

