# Quick Test Guide - DynoAI Qt6

## ✅ Application Launched Successfully!

Your Qt6 desktop app is now running. Here's how to test all the features:

## 🧪 Test Checklist

### 1. JetDrive Tab (Currently Open)

You're currently on the JetDrive tab. Let's test the simulator:

**Test Steps:**
1. ✅ Click **"▶️ Start Simulator"** button
2. ✅ Watch the gauges - they should show idle RPM (~900 RPM)
3. ✅ Click **"🚀 Trigger Pull"** to simulate a dyno run
4. ✅ Watch gauges update in real-time:
   - RPM should climb from 2000 → 6500
   - HP should peak around 100-120 HP
   - Torque should show realistic values
   - AFR should show 12-14 range
   - MAP should increase with throttle
   - TPS should show 100% (WOT)
5. ✅ Click **"⏹️ Stop Simulator"** when done

### 2. Analysis Tab

**Test Steps:**
1. Click the **"📊 Analysis"** tab
2. Click **"Browse..."** button
3. Select a CSV file (or use a test file from `data/` folder)
4. Click **"🚀 Run Analysis"** button
5. Watch the progress bar
6. View results when complete

### 3. Results Tab

**Test Steps:**
1. Click the **"📈 Results"** tab
2. You should see a list of previous runs
3. Click on a run to view:
   - Run summary (Peak HP, Torque, Samples)
   - VE Correction Grid (color-coded)
4. Try the export buttons (PVV, Text, CSV)

### 4. Settings Tab

**Test Steps:**
1. Click the **"⚙️ Settings"** tab
2. Change some values:
   - Smooth Passes: try 3
   - Correction Clamp: try 20%
   - Change output directory
3. Click **"💾 Save Settings"**
4. Restart the app - settings should persist!

### 5. Menu Bar

**Test the menus:**
- **File** → **Open CSV...** (same as Analysis tab browse)
- **File** → **Exit** (closes app)
- **Tools** → **Start Simulator** (switches to JetDrive tab)
- **Help** → **About DynoAI** (shows version info)
- **Help** → **Documentation** (opens docs)

### 6. Keyboard Shortcuts

Try these:
- **Ctrl+O**: Open CSV file
- **Ctrl+Q**: Quit application

## 🐛 Known Issues (Fixed in Latest Code)

- ~~Simulator update error~~ → **FIXED**: Updated to use `get_channels()` method
- Export functions → Placeholders (to be implemented)

## 🎯 Expected Behavior

### Simulator Should:
- ✅ Start without errors
- ✅ Show idle RPM (~900)
- ✅ Update gauges every 50ms (smooth animation)
- ✅ Complete pulls in ~3-4 seconds
- ✅ Return to idle after pull

### Analysis Should:
- ✅ Run in background (UI doesn't freeze)
- ✅ Show progress updates
- ✅ Complete in < 10 seconds for typical CSV
- ✅ Save results to `runs/` directory

### Results Tab Should:
- ✅ List all runs
- ✅ Show newest runs first
- ✅ Display VE grid with colors:
  - 🟢 Green: < 2% correction
  - 🟡 Yellow: 2-5% correction
  - 🔴 Red: > 5% correction

## 🔍 Troubleshooting

### If Simulator Doesn't Start:
- Check console for error messages
- Ensure no other instance is running
- Try restarting the app

### If Analysis Fails:
- Check CSV file has required columns
- View error message in Analysis tab
- Check `runs/` directory exists and is writable

### If Gauges Don't Update:
- Restart the app (fixed in latest code)
- Check that **Start Simulator** was clicked
- Look for errors in status bar

## 📝 Next Steps

1. **Test thoroughly** - Try all features
2. **Report any bugs** - Note what doesn't work
3. **Test with real data** - Try your actual dyno CSVs
4. **Build standalone** - Run `.\build_qt6.ps1` to create .exe

## 🎉 Success Indicators

You should see:
- ✅ **No errors** in status bar (bottom of window)
- ✅ **Smooth gauge updates** when simulator running
- ✅ **Analysis completes** without freezing UI
- ✅ **Settings persist** after restart

---

**Enjoy your new Qt6 desktop app!** 🚀
