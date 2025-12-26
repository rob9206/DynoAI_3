# 🎬 VE Table Time Machine - Quick Test Guide

## ✅ Test Data Generated Successfully!

### Run ID
```
run_timeline_demo_20251206_000347
```

### What's Inside
- **10 Timeline Events** (baseline, 5 analyses, 3 applies, 1 rollback)
- **14 VE Snapshots** (before/after states)
- **Realistic Tuning Session** (progressive refinement, problem detection, rollback)

---

## 🚀 Quick Access

### If Web App is Already Running:
```
http://localhost:5000/time-machine/run_timeline_demo_20251206_000347
```

### If Not Running:
```powershell
.\start-web.ps1

# Then navigate to the URL above
```

---

## 🎮 Quick Feature Test Checklist

### ✅ Basic Navigation
- [ ] See 10 events in timeline sidebar
- [ ] Current step is highlighted
- [ ] Step counter shows "1 / 10"
- [ ] Event cards show type badges (Baseline, Analysis, Apply, Rollback)

### ✅ Playback Controls
- [ ] Click **Next** → advances to step 2
- [ ] Click **Prev** → goes back to step 1
- [ ] Drag **slider** → jumps to any step
- [ ] Click **Play** → auto-advances every 1.5s
- [ ] Click **Pause** → stops auto-playback

### ✅ VE Snapshots
- [ ] See VE heatmap at current step
- [ ] Hover over cells → tooltip shows exact values
- [ ] Different steps show different VE values
- [ ] Heatmap updates when changing steps

### ✅ Compare Mode
- [ ] At step 3, click **"Compare"** button
- [ ] Navigate to step 5
- [ ] Click **"Compare to Step 5"**
- [ ] See diff heatmap (green=increase, red=decrease)
- [ ] See stats (cells changed, avg/max/min)
- [ ] See top 20 largest changes

### ✅ Event Details
- [ ] See metadata for each event (rows processed, config, etc.)
- [ ] Analysis events show clamp % and smooth passes
- [ ] Apply events show cells modified
- [ ] Rollback event shows original apply timestamp

### ✅ Download
- [ ] Click **"Download Snapshot"** button
- [ ] CSV file downloads
- [ ] Open in Excel/text editor → valid VE table format

---

## 🔍 Interesting Scenarios to Test

### Scenario 1: Progressive Refinement
1. Start at **Step 1** (baseline)
2. **Compare** to **Step 3** (first apply)
3. ✅ Should see **large corrections** (±7%)
4. **Compare Step 3** to **Step 5** (refinement)
5. ✅ Should see **smaller corrections** (±2-3%)

### Scenario 2: Problem Detection & Rollback
1. Go to **Step 6** (problem detected)
2. ✅ Notice description mentions "problem in mid-range"
3. Go to **Step 7** (rollback)
4. ✅ See "Rollback" badge and description
5. **Compare Step 5** to **Step 7**
6. ✅ Should see **negative differences** (reverted changes)

### Scenario 3: Final Convergence
1. Go to **Step 10** (final verification)
2. **Compare** to **Step 9**
3. ✅ Should see **very small corrections** (<1%)
4. ✅ Indicates tune is dialed in

### Scenario 4: Auto-Playback
1. Go to **Step 1**
2. Click **Play** ▶️
3. ✅ Timeline auto-advances through all 10 steps
4. ✅ VE heatmap updates at each step
5. ✅ Stops at Step 10

---

## 📊 Expected Behavior

### Timeline Sidebar
- Event list on left
- Current event highlighted in blue/primary color
- Badges show event type with icons
- Relative timestamps (e.g., "2m ago")

### Main View
- VE heatmap fills the space
- Colorful cells (warmer = higher VE)
- Responsive to step changes
- Tabs for "Snapshot" and "Diff View"

### Compare Mode
- Banner shows "Comparing from Step X"
- Diff heatmap uses green/red scale
- Summary cards at top
- Top changes list below

---

## 🐛 If Something Doesn't Work

### Timeline won't load
```powershell
# Check backend
curl http://localhost:5001/api/timeline/run_timeline_demo_20251206_000347

# Should return JSON with 10 events
```

### Snapshots missing
```powershell
# Verify files exist
ls runs\run_timeline_demo_20251206_000347\snapshots

# Should show 14 .csv files
```

### Compare doesn't work
- Make sure you're not comparing a step to itself
- Both steps need snapshots (they all should)
- Check browser console for errors

---

## 🎓 What This Tests

✅ **Backend**: SessionLogger, Timeline API, snapshot storage  
✅ **Frontend**: Timeline UI, playback, VE visualization, diff view  
✅ **Integration**: Event recording, snapshot retrieval, diff computation  
✅ **Real-world workflow**: Multi-step tuning with rollback  

---

## 🔄 Generate Fresh Test Data

```powershell
# New session with different random values
python scripts/generate_timeline_test_data.py

# Get the new run_id from output, then:
# http://localhost:5000/time-machine/[new_run_id]
```

---

## ✨ Success Criteria

If you can:
- ✅ Navigate through all 10 steps
- ✅ See different VE tables at each step
- ✅ Compare two steps and see differences
- ✅ Use play/pause to auto-advance
- ✅ Download a snapshot as CSV

**The Time Machine is working perfectly!** 🎉

---

**Need help?** Check `docs/TIME_MACHINE_QUICK_START.md` for detailed guide.

