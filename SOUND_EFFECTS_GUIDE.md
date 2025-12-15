# 🔊 Sound Effects Guide

## What You'll Hear Now

The JetDrive page now plays **automatic sound effects** during key events!

## 🎵 Sound Effects Map

### ✅ Success Events

**🎉 Success Arpeggio** (C-E-G chord)
- **When:** Analysis completes successfully
- **Sound:** Rising musical notes
- **Why:** Celebrate your successful dyno run!

### 🚀 Startup Events

**⬆️ Startup Chime** (Rising tones: 200Hz → 400Hz → 600Hz)
- **When:** 
  - Simulator starts
  - Hardware monitor connects
- **Sound:** Three rising beeps
- **Why:** System is powering up!

### 🛑 Shutdown Events

**⬇️ Shutdown Tone** (Falling tones: 600Hz → 400Hz → 200Hz)
- **When:** Simulator stops
- **Sound:** Three falling beeps
- **Why:** System is powering down

### ⚠️ Warning Events

**🔔 Warning Alert** (Alternating 800Hz/600Hz)
- **When:**
  - Simulator fails to start
  - Analysis fails
  - Pull trigger fails
  - Hardware monitor fails
  - **Knock detected!**
- **Sound:** Three alternating beeps
- **Why:** Something needs attention!

### 🎯 Action Beeps

**📍 Quick Beeps** (Single tone)
- **When:**
  - Pull triggered: 600Hz beep (confirmation)
  - Audio recording starts: 800Hz beep (high)
  - Audio recording stops: 400Hz beep (low)
- **Sound:** Quick single beep
- **Why:** Instant feedback for your action

---

## 🎮 Try It Out!

### Test All Sounds:

1. **Startup Sound:**
   - Click "Start Simulator" → Hear rising chime! ⬆️

2. **Action Beep:**
   - Click "Trigger Pull" → Hear confirmation beep! 📍

3. **Success Sound:**
   - Click "Analyze" → Hear success arpeggio! 🎉

4. **Shutdown Sound:**
   - Click "Stop Simulator" → Hear falling tone! ⬇️

5. **Warning Sound:**
   - Try to trigger pull when not ready → Hear warning! ⚠️

6. **Audio Recording Beeps:**
   - Open Audio panel (Mic button)
   - Start recording → High beep! 🔊
   - Stop recording → Low beep! 🔉

7. **Knock Detection:**
   - If knock detected → Warning sound! 💥

---

## 🔧 How It Works

### Sound Effect Functions:

```typescript
playStartup()   // Rising: 200→400→600 Hz
playShutdown()  // Falling: 600→400→200 Hz
playSuccess()   // Arpeggio: C-E-G chord
playWarning()   // Alternating: 800↔600 Hz
playBeep(freq, duration) // Custom beep
```

### Event Mapping:

| Event | Sound | Frequency |
|-------|-------|-----------|
| Simulator Start | Startup | 200→400→600 Hz |
| Simulator Stop | Shutdown | 600→400→200 Hz |
| Analysis Complete | Success | 523→659→784 Hz |
| Error/Warning | Warning | 800↔600 Hz |
| Pull Triggered | Beep | 600 Hz |
| Recording Start | Beep | 800 Hz |
| Recording Stop | Beep | 400 Hz |
| Knock Detected | Warning | 800↔600 Hz |

---

## 🎛️ Volume Control

Sound effects use the **same audio engine** as the engine sounds, so:

1. Open **Settings** (⚙️ button)
2. Look for **Audio Mode** setting
3. The volume is controlled by the audio controls bar

Or use the compact audio controls to adjust volume.

---

## 🔇 Disable Sounds

If you want to disable sound effects:

1. Click the **power button** (⚡) in the audio controls
2. Or click the **mute button** (🔇)
3. Sound effects will be silent

---

## 🎨 Sound Design

### Startup (Rising)
- **Feeling:** Power up, getting ready
- **Pattern:** Low → Medium → High
- **Duration:** ~200ms total

### Shutdown (Falling)
- **Feeling:** Power down, complete
- **Pattern:** High → Medium → Low
- **Duration:** ~200ms total

### Success (Arpeggio)
- **Feeling:** Achievement, celebration
- **Pattern:** Major chord (happy!)
- **Duration:** ~240ms total

### Warning (Alternating)
- **Feeling:** Alert, attention needed
- **Pattern:** Oscillating tones
- **Duration:** ~360ms total

### Beep (Single)
- **Feeling:** Confirmation, feedback
- **Pattern:** Single tone
- **Duration:** 100ms

---

## 💡 Pro Tips

1. **Volume:** Start at 30-50% for sound effects
2. **Headphones:** You'll hear all the nuances
3. **Fun Mode:** Makes engine sounds exaggerated, but effects stay the same
4. **Realistic Mode:** Natural engine sounds, same effects
5. **Knock Detection:** Warning sound helps you catch issues immediately!

---

## 🎯 Quick Reference

**Want to hear all sounds quickly?**

```
1. Start Simulator     → ⬆️ Startup chime
2. Trigger Pull        → 📍 Beep
3. Wait for completion → (automatic)
4. Analyze             → 🎉 Success!
5. Stop Simulator      → ⬇️ Shutdown tone
```

**Total time:** ~30 seconds to hear all sounds!

---

## 🔊 Sound Effect Summary

| Icon | Sound | When |
|------|-------|------|
| ⬆️ | Startup | System starts |
| ⬇️ | Shutdown | System stops |
| 🎉 | Success | Task completes |
| ⚠️ | Warning | Error/Issue |
| 📍 | Beep | Action confirmed |
| 🔊 | High Beep | Recording starts |
| 🔉 | Low Beep | Recording stops |
| 💥 | Warning | Knock detected |

---

**Enjoy the immersive audio feedback!** 🎵🔥

Every action now has audio confirmation, making the tuning experience more engaging and intuitive!

