# ✅ VE Table Time Machine - Test Data Generated!

## 🎯 What Was Created

A **comprehensive, realistic dyno tuning session** with:

### Run ID
```
run_timeline_demo_20251206_000347
```

### Timeline Overview

**10 Events** simulating a complete tuning workflow:

| # | Event Type | Description |
|---|------------|-------------|
| 1 | **BASELINE** | Initial baseline VE table loaded from ECM |
| 2 | **ANALYSIS** | First dyno pull: Initial tune analysis (baseline) |
| 3 | **APPLY** | Applied initial corrections (±7% clamp) |
| 4 | **ANALYSIS** | Second pull: Refinement pass (tighter clamp) |
| 5 | **APPLY** | Applied refinement corrections (±5% clamp) |
| 6 | **ANALYSIS** | Third pull: Problem detected in mid-range/high load area |
| 7 | **ROLLBACK** | Rolled back to Pass 1: investigating mid-range issue |
| 8 | **ANALYSIS** | Fourth pull: Problem resolved, smoother corrections |
| 9 | **APPLY** | Applied final corrections after problem resolution |
| 10 | **ANALYSIS** | Final verification: Tune dialed in, minimal corrections needed |

### Data Files

- **Session Log**: `session_log.json` with 10 events
- **Snapshots**: 14 CSV files (before/after for each operation)
- **VE Tables**: 10 CSV files showing progression

---

## 🚀 Try It Now

### Option 1: Open in Browser (if web app is running)

```
http://localhost:5000/time-machine/run_timeline_demo_20251206_000347
```

### Option 2: Start Web App First

```powershell
# Terminal 1: Backend
python -m api.app

# Terminal 2: Frontend
cd frontend
npm run dev

# Then open:
http://localhost:5000/time-machine/run_timeline_demo_20251206_000347
```

---

## 🎮 What You Can Explore

### 1. **View the Timeline**
- See all 10 events chronologically
- Event cards show type, description, and timestamp
- Current step is highlighted

### 2. **Playback Controls**
- **Play/Pause**: Auto-advance through events
- **Prev/Next**: Step through manually
- **Slider**: Jump to any step
- **Step counter**: Shows current position (e.g., "5 / 10")

### 3. **VE Snapshots**
- View VE table state at each step
- Heatmap visualization shows values
- Hover over cells for exact values
- See how the tune evolved over time

### 4. **Compare Steps**
- Click **"Compare"** button
- Select first step (e.g., step 3)
- Navigate to another step (e.g., step 5)
- Click **"Compare to Step 5"**
- See cell-by-cell differences with color-coded heatmap

### 5. **Diff Analysis**
- Green cells: VE increased
- Red cells: VE decreased
- Darker colors: Larger changes
- Summary stats: cells changed, avg/max/min
- Top 20 largest changes listed with exact values

### 6. **Event Details**
- Each event shows metadata
- Analysis events: rows processed, config settings
- Apply events: cells modified, clamp percentage
- Rollback events: original apply timestamp

### 7. **Download Snapshots**
- Click **"Download Snapshot"** button
- Get CSV of VE table at current step
- Use for external analysis or backup

---

## 🔍 Interesting Things to Try

### Progressive Refinement
1. Start at Step 1 (baseline)
2. Compare to Step 3 (after first apply)
3. See large corrections applied (±7% clamp)
4. Compare Step 3 to Step 5 (after refinement)
5. Notice smaller, more precise corrections (±5% clamp)

### Problem Detection & Rollback
1. Go to Step 6 (problem detected)
2. Notice analysis shows issues in mid-range/high load
3. Step 7 shows **rollback** operation
4. Compare Step 5 (before rollback) to Step 7 (after)
5. See how the table reverted to previous good state

### Final Verification
1. Navigate to Step 10 (final verification)
2. Compare to Step 9 (last apply)
3. Notice very small corrections (tune is dialed in)
4. Shows convergence - tune is nearly perfect

### Auto-Playback
1. Go to Step 1
2. Click **Play** button
3. Watch timeline auto-advance every 1.5 seconds
4. Observe how VE table evolves through the session

---

## 📊 Data Characteristics

### Baseline (Step 1)
- Typical VE values: 85-110%
- Lower at low RPM/MAP, higher in middle
- Natural variation: ±2%

### Initial Corrections (Step 2)
- Large corrections needed: up to ±7%
- More corrections at high load
- Simulates fresh baseline tune

### Refinement (Step 4)
- Smaller corrections: ±2%
- Even distribution
- Simulates tuning convergence

### Problem Area (Step 6)
- Hot spot at mid-range RPM, high load
- Running rich: -3% to -5% corrections
- Simulates real-world issue (e.g., injector, airflow)

### Final (Step 10)
- Minimal corrections: ±0.5%
- Tune is dialed in
- Ready for street/track use

---

## 🎓 Learning Opportunities

This test data demonstrates:

1. **Iterative Tuning Process**: Multiple dyno pulls refining the tune
2. **Safety Features**: Clamping prevents dangerous changes
3. **Problem Diagnosis**: Detecting issues through VE patterns
4. **Undo Capability**: Rollback when something goes wrong
5. **Convergence**: Progressive reduction in correction magnitude
6. **Documentation**: Complete audit trail of every decision

---

## 🔄 Generate More Test Data

```powershell
# Generate another session with different patterns
python scripts/generate_timeline_test_data.py

# Or specify custom run_id
python scripts/generate_timeline_test_data.py my_custom_run_id
```

Each run will have unique VE values and correction patterns (randomized within realistic bounds).

---

## 🐛 Troubleshooting

**Timeline doesn't load:**
- Check backend is running: `python -m api.app`
- Verify run exists: `ls runs/run_timeline_demo_*`
- Check API: `curl http://localhost:5001/api/timeline/[run_id]`

**No snapshots visible:**
- Snapshots are in `runs/[run_id]/snapshots/`
- Should see `.csv` files named `snap_*.csv`

**Can't compare steps:**
- Both steps need snapshots (all should have them in test data)
- Try comparing non-adjacent steps for bigger differences

---

**Enjoy exploring the Time Machine! 🚀**

This is a powerful feature for understanding tuning decisions and learning from past sessions.

