# 🎤 AFR Voice Feedback - Quick Test Guide

## What's New?

The AI Assistant now gives **real-time voice feedback** on your air/fuel ratio during dyno pulls!

---

## 🚀 Quick Test (5 Minutes)

### Step 1: Start the Frontend
```powershell
cd C:\Dev\DynoAI_3\frontend
npm run dev
```

Open browser to: `http://localhost:5173`

### Step 2: Navigate to JetDrive
1. Click **JetDrive** in the top navigation
2. Scroll to **Testing & Development** section
3. Enable **Fun Mode** toggle (bottom right, Audio Controls)
   - You should see: 🎤 AI Assistant: [Voice Name]

### Step 3: Test Voice
1. Click the **🎤 Test Voice** button
2. Should hear: "Hey! I'm your DynoAI assistant! Let's make some power!"

✅ If you hear the voice, you're ready!

### Step 4: Run Simulator Pull
1. Click **Start Simulator** (if not already running)
2. Select profile: **M8 114** (default)
3. Click **Trigger Pull** (big green button)

### Step 5: Listen for AFR Feedback! 🎧

During the pull, you should hear:

| Condition | What You'll Hear |
|-----------|------------------|
| **Pull Starts** | "Let's go! Full send!" |
| **AFR On Target** | "Perfect! AFR is right on target!" |
| **AFR Too Lean** | "Running lean! She's thirsty, needs more fuel!" |
| **AFR Too Rich** | "Running rich! Could use less fuel." |
| **High RPM** | "She's screaming!" |
| **Pull Ends** | "142 horsepower! Nice!" |

---

## 🔧 What's Happening?

### AFR Monitoring Logic
```
During Pull (RPM > 2000):
  ├─ AFR within 2% of target → "Perfect! AFR is right on target!"
  ├─ AFR >4% above target   → "Running lean! Needs more fuel!"
  └─ AFR >4% below target   → "Running rich! Could use less fuel."

Cooldown: 8 seconds between AFR comments
```

### Example Scenarios

**Scenario 1: Perfect Tune**
- Target AFR: 13.2
- Measured AFR: 13.1
- Error: 0.8% ✅
- **Voice**: "Perfect! AFR is right on target!"

**Scenario 2: Lean Condition**
- Target AFR: 13.2
- Measured AFR: 14.0
- Error: 6.1% ⚠️
- **Voice**: "Running lean! She's thirsty, needs more fuel!"

**Scenario 3: Rich Condition**
- Target AFR: 13.2
- Measured AFR: 12.5
- Error: 5.3% ⚠️
- **Voice**: "Running rich! Could use less fuel."

---

## 🎯 Advanced Testing

### Test Different AFR Targets

1. Click **Settings** (gear icon)
2. Modify **AFR Target Table**
3. Change values for different MAP ranges
4. Run pulls and hear feedback adapt to new targets

### Test with Real Hardware

If you have a Dynojet connected:
1. Ensure hardware monitor is started
2. Enable Fun Mode
3. Do a real dyno pull
4. AI will monitor live AFR vs your target table

---

## 🐛 Troubleshooting

### No Voice?
- ✅ Check Fun Mode is enabled (toggle should be ON)
- ✅ Check browser volume
- ✅ Click "Test Voice" button first
- ✅ Check browser console for errors

### Wrong Feedback?
- Check AFR Target Table values
- Ensure AFR sensor is connected and reading
- Look at live gauges - is AFR showing valid data?

### Too Many Comments?
- 8-second cooldown should prevent spam
- Only triggers during pulls (RPM > 2000)
- Only triggers when AFR data is valid (> 0)

---

## 📊 Monitoring in Console

Open browser DevTools (F12) and watch for:

```
[AI Assistant] triggerEvent called: good_pull enabled: true
[AI Assistant] Selected phrase: Perfect! AFR is right on target!
[AI Assistant] Speaking: Perfect! AFR is right on target!
```

---

## 🎓 Understanding the Thresholds

### Why 2% for "Good"?
- Tight tolerance ensures tune is truly dialed in
- Typical tuning goal: ±0.2-0.3 AFR units
- Example: 13.2 ± 0.26 = 12.94 to 13.46

### Why 4% for "Lean/Rich"?
- Gives buffer zone between "good" and "needs attention"
- Prevents constant flip-flopping
- Example: 13.2 ± 0.53 = 12.67 to 13.73

### Cooldown Strategy
- **3 seconds**: General event cooldown (same type)
- **8 seconds**: AFR-specific cooldown
- **10 seconds**: High RPM cooldown
- Prevents voice spam while keeping feedback relevant

---

## ✅ Success Criteria

You've successfully tested the feature if you:
- [x] Heard the test voice
- [x] Heard pull start announcement
- [x] Heard at least one AFR feedback comment
- [x] Heard peak HP announcement at end
- [x] No browser errors in console

---

## 🚀 Next Steps

### Try These:
1. **Modify AFR targets** and hear feedback change
2. **Enable audio capture** for knock detection + voice feedback
3. **Compare multiple runs** with different AFR targets
4. **Test with real hardware** if available

### Future Enhancements:
- User-adjustable voice settings (pitch, rate)
- Custom phrase editor
- Multiple voice personalities
- Language support

---

## 📚 Related Docs

- [AI_VOICE_ASSISTANT.md](docs/AI_VOICE_ASSISTANT.md) - Complete feature documentation
- [AUDIO_QUICK_TEST.txt](AUDIO_QUICK_TEST.txt) - Audio engine test guide
- [AUDIO_TEST_INSTRUCTIONS.md](AUDIO_TEST_INSTRUCTIONS.md) - Detailed audio testing

---

**Status**: ✅ Ready to test!
**Security**: ✅ Snyk scan passed (0 issues)
**Version**: v1.2.3
**Date**: December 15, 2025

