# Virtual Tuning System - Quick Reference Card

**Everything you need to know on one page**

---

## ⏱️ Expected Timeline

```
Click "Start Closed-Loop Tuning"
  ↓
0s:    Session created - Shows "Iteration 0/10" ← WAIT HERE
  ↓    (Running first dyno pull + analysis)
  ↓
10-15s: Iteration 1 completes - Shows "Iteration 1/10"
  ↓    AFR Error: ~1.4, VE Correction: +10.8%
  ↓
18-20s: Iteration 2 completes - Shows "Iteration 2/10"
  ↓    AFR Error: ~0.8, VE Correction: +4.2%
  ↓
26-28s: Iteration 3 completes - Shows "Iteration 3/10"
  ↓    AFR Error: ~0.4, VE Correction: +2.2%
  ↓
34-36s: Iteration 4 completes - Shows "CONVERGED!"
        Final AFR Error: ~0.2 ✓
```

**Total Time:** ~35 seconds for complete tuning

---

## 🎯 Quick Start

### 1. Configure Virtual ECU
- Open Settings (⚙️)
- Scroll to "Virtual ECU"
- Toggle ON
- Select "Lean (VE -10%)"

### 2. Start Closed-Loop Tuning
- Scroll to "Closed-Loop Auto-Tune"
- Click "Start Closed-Loop Tuning"
- **WAIT 10-15 seconds** for first iteration

### 3. Watch Progress
- Progress bar will update every 3 seconds
- Iteration history populates
- Convergence message appears when done

---

## 🔍 What You'll See

### Initial State (0-10 seconds)
```
Iteration: 0 / 10
Progress: 5% (pulsing)
Message: "Running first iteration... (10-15 seconds)"
```

### After First Iteration (10-15 seconds)
```
Iteration: 1 / 10
Progress: 10%
Max AFR Error: 1.423
VE Correction: +10.85%
History: #1 ↓ 1.423 AFR  +10.8% VE
```

### Convergence (30-40 seconds)
```
Status: CONVERGED
Message: "Converged in 4 iterations!"
Final AFR error: 0.224 points
Duration: 35.2s
```

---

## 🛠️ Troubleshooting

### Stuck at "Iteration 0 / 10"?
**✅ This is normal!** Wait 10-15 seconds for first iteration.

### Still stuck after 30 seconds?
**Check:**
- Is backend running? (Flask on port 5001)
- Check backend logs for errors
- Try refreshing the page

### Session shows "FAILED"?
**Check backend logs** for error message

### Want to restart?
**Click "Stop"** then start a new session

---

## 📊 Typical Results

| Iteration | Time | AFR Error | VE Correction | Status |
|-----------|------|-----------|---------------|---------|
| 0 | 0s | - | - | Starting... |
| 1 | 15s | 1.42 | +10.8% | Tuning |
| 2 | 20s | 0.76 | +4.2% | Tuning |
| 3 | 25s | 0.41 | +2.2% | Tuning |
| 4 | 30s | 0.22 | +1.1% | ✅ CONVERGED |

---

## 🎯 Key Points

### Timing
- ⏱️ **First iteration:** 10-15 seconds (full dyno pull)
- ⏱️ **Subsequent iterations:** 4-5 seconds each
- ⏱️ **Total convergence:** ~35 seconds (4 iterations)

### Progress
- 🔄 UI updates every 3 seconds
- 📊 Progress bar shows completion %
- 📝 Iteration history populates in real-time

### Convergence
- 🎯 **Target:** AFR error < 0.3 points
- ✅ **Typical:** Converges in 4-5 iterations
- 🚀 **Rate:** FAST (4 iterations) or NORMAL (5-7 iterations)

---

## 📚 Documentation

- **Quick Start:** [QUICK_START_VIRTUAL_ECU.md](QUICK_START_VIRTUAL_ECU.md)
- **Complete Guide:** [VIRTUAL_TUNING_COMPLETE_GUIDE.md](VIRTUAL_TUNING_COMPLETE_GUIDE.md)
- **Troubleshooting:** [TROUBLESHOOTING_VIRTUAL_TUNING.md](TROUBLESHOOTING_VIRTUAL_TUNING.md)
- **All Docs:** [VIRTUAL_TUNING_DOCS_INDEX.md](VIRTUAL_TUNING_DOCS_INDEX.md)

---

## 💡 Pro Tips

1. **Be patient** - First iteration takes 10-15 seconds
2. **Watch the spinner** - Spinning icon means it's working
3. **Check backend logs** - See detailed progress
4. **Use "Lean" scenario** - Best for testing (converges in 4 iterations)
5. **Don't refresh** - Let it complete

---

## ✅ Summary

**The system is working correctly!**

- "Iteration 0/10" = First iteration is running
- Wait 10-15 seconds for first update
- Progress bar will pulse to show activity
- Subsequent iterations are faster (4-5s each)
- Typical convergence: 4 iterations (~35 seconds total)

**Just be patient - it's running a full dyno pull simulation!** ⏱️







