# VE Table Time Machine - Quick Start

## ✅ What's Working

The VE Table Time Machine is now fully integrated and operational:

- **Backend API**: All timeline endpoints working on port 5001
- **Frontend UI**: Complete Time Machine page with playback controls
- **Auto-Recording**: Analysis runs automatically create timeline events
- **Demo Data**: Sample timeline created for `run_jetstream_demo_complete`

## 🚀 How to Use It

### Option 1: View Demo Data (Quickest)

```powershell
# 1. Make sure the web app is running
.\start-web.ps1

# 2. Open your browser to:
http://localhost:5000/time-machine/run_jetstream_demo_complete
```

This demo has **2 timeline events**:
- Initial analysis (clamp=7%, smooth_passes=2)
- Refined analysis (clamp=5%, smooth_passes=3)

You can:
- 📜 View the timeline of events
- ⏯️ Use playback controls (play/pause/step)
- 📸 See VE snapshots at each step
- 🔀 Compare between steps to see differences
- 📥 Download any snapshot as CSV

### Option 2: Create New Timeline Data

Any new analysis you run will automatically record timeline events:

```powershell
# Run an analysis (via web UI or API)
# Then access the Time Machine from the Results page
```

### Option 3: Seed More Demo Data

```powershell
# Seed timeline for any existing run
python scripts/seed_timeline_demo.py [run_id]

# Or let it auto-find a complete run
python scripts/seed_timeline_demo.py
```

## 🔧 What Was Fixed

The initial error `Run not found: cb1d274a-8512-445a-8396-2c86813f01c9` occurred because:

1. **Problem**: Timeline API was only checking `runs/` folder
2. **Solution**: Updated to check both `runs/` (Jetstream) and `outputs/` (direct uploads)

The fix was in `api/routes/timeline.py` → `get_run_dir()` function.

## 📁 Timeline Data Structure

Each run with a timeline has:

```
runs/[run_id]/                      or    outputs/[run_id]/
├── session_log.json                      ← Timeline events
├── snapshots/                            ← VE table snapshots
│   ├── snap_abc123.csv
│   └── snap_def456.csv
└── output/
    └── VE_Correction_Delta_DYNO.csv
```

## 🎯 Navigation

From any **Results page**:
- Click the **"Time Machine"** button in the top-right
- Or navigate directly to: `/time-machine/[run_id]`

## 🔑 Key Features

| Feature | Description |
|---------|-------------|
| **Timeline View** | Chronological list of all operations |
| **Step Navigation** | Prev/Next buttons, step slider, play/pause |
| **VE Snapshots** | See table state at any point in time |
| **Diff Comparison** | Cell-by-cell comparison between steps |
| **Change Stats** | Summary of cells changed, avg/max/min deltas |
| **CSV Export** | Download any snapshot |

## 🐛 Troubleshooting

**"Timeline Not Available"** error:
- The run needs to have a `session_log.json` file
- Either run `python scripts/seed_timeline_demo.py [run_id]`
- Or wait for new Apply/Rollback operations to record events

**API errors**:
- Ensure backend is running on port 5001: `python -m api.app`
- Check `api/routes/timeline.py` is loaded (should see endpoints in startup banner)

**No events showing**:
- Timeline is created when you use Apply/Rollback
- For existing runs, use the seed script to create demo data

## 📝 Example Workflow

1. Upload a dyno log → Analysis runs
2. View Results page → VE corrections shown
3. Click "Time Machine" button
4. Step through the analysis timeline
5. Click "Apply" to apply corrections (creates new timeline event)
6. Use Time Machine to see before/after comparison
7. Click "Rollback" if needed (creates rollback event)

## 🎬 Next Steps

The Time Machine will become more useful as you:
- Apply VE corrections (records apply event)
- Rollback changes (records rollback event)
- Run multiple analyses (each creates a timeline event)
- Refine your tune over multiple dyno sessions

Each operation builds your session history, allowing you to replay and understand every tuning decision!

