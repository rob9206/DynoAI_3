# 🎵 Audio Engine - Test Instructions

## Quick Start (3 Steps!)

### Step 1: Start the Frontend
```powershell
cd C:\Dev\DynoAI_3\frontend
npm run dev
```

### Step 2: Open Browser
Navigate to: **http://localhost:5173**

### Step 3: Go to Audio Demo
Click **"Audio Demo"** in the top navigation bar (right side, cyan button with speaker icon 🔊)

---

## 🎮 How to Test

### Option A: Audio Demo Page (Recommended for First Test)

1. **Click "Start Engine"** button (big green button)
2. **Move the RPM slider** - you'll hear the engine sound change!
   - Start at 1000 RPM (idle)
   - Slowly move to 3000 RPM
   - Go up to 6000 RPM (WOT)
3. **Adjust Load slider** - changes sound intensity
   - 0% = idle/closed throttle
   - 100% = wide open throttle (WOT)
4. **Try the preset buttons:**
   - 🔵 **Idle** - 1000 RPM, 10% load
   - 🟢 **Cruise** - 3000 RPM, 30% load
   - 🔴 **WOT** - 6000 RPM, 100% load
   - 💥 **Decel** - 5000 RPM, 5% load (hear the crackle!)

### Option B: JetDrive Page (Real Simulation)

1. Go to **"Command Center"** (main page)
2. Scroll down to **"Testing & Development"** section
3. Click **"Start Simulator"** (orange button)
4. Click **"Trigger Pull"** to simulate a dyno run
5. **Audio will automatically start!** 🎉
6. Watch the gauges and listen as RPM increases
7. Use the audio controls (compact bar above capture controls) to adjust volume

---

## 🎛️ Controls Explained

### Demo Page Controls
- **RPM Slider**: 500-8000 RPM (engine speed)
- **Load Slider**: 0-100% (throttle position)
- **Volume Slider**: 0-100% (master volume)
- **Mute Button**: Quick silence
- **Cylinder Buttons**: Change engine type (1, 2, 4, 6, 8 cylinders)

### JetDrive Page Controls (Compact)
- **Power Button** (⚡): Start/stop engine sound
- **Speaker Button** (🔊): Mute/unmute
- **Volume Slider**: Adjust volume
- **RPM Badge**: Shows current RPM

---

## 🎯 What to Listen For

### Idle (1000 RPM, Low Load)
- Quiet, steady rumble
- Low frequency
- Smooth sound

### Cruise (3000 RPM, Medium Load)
- Moderate volume
- Clear engine note
- Steady tone

### WOT (6000 RPM, High Load)
- Loud, aggressive
- High frequency
- Full power sound

### Decel (5000 RPM, Very Low Load)
- **Listen for crackle/pops!** 💥
- Exhaust burbles
- Realistic deceleration sound

---

## 🏍️ Try Different Engines

### V-Twin (Harley)
1. Set **Cylinders: 2**
2. Try 1000 → 6000 RPM sweep
3. Listen for the characteristic V-twin rumble

### Inline-4 (Sportbike)
1. Set **Cylinders: 4**
2. Try 3000 → 8000 RPM sweep
3. Smoother, higher-pitched sound

### V8 (Muscle Car)
1. Set **Cylinders: 8**
2. Try 1500 → 7000 RPM sweep
3. Deep, powerful rumble

---

## 🔧 Troubleshooting

### No Sound?
✅ **Check these:**
1. Browser volume not muted
2. System volume up
3. "Start Engine" button clicked
4. Volume slider > 0%
5. Mute button shows 🔊 (not 🔇)

### Browser Says "Blocked"?
- Click anywhere on the page first
- Then click "Start Engine"
- This is normal browser security

### Choppy/Stuttering?
- Close other browser tabs
- Lower RPM values
- Refresh the page

---

## 🎬 Recommended Test Sequence

### 1. First Listen (Demo Page)
```
1. Start Engine
2. RPM: 1000 → 2000 → 3000 → 4000 → 5000 → 6000
3. Keep Load at 50%
4. Listen to how frequency changes
```

### 2. Load Test (Demo Page)
```
1. Set RPM to 3000
2. Load: 0% → 25% → 50% → 75% → 100%
3. Listen to how volume/intensity changes
```

### 3. Decel Test (Demo Page)
```
1. Click "Decel" preset button
2. Listen for exhaust pops/crackle
3. Try adjusting RPM while keeping load low
```

### 4. Full Simulation (JetDrive Page)
```
1. Start Simulator
2. Trigger Pull
3. Watch gauges while listening
4. Hear the full dyno run experience!
```

---

## 📊 What's Happening?

The audio engine:
1. **Calculates frequency** from your RPM
   - Formula: `(RPM / 60) × (cylinders / 2)`
   - Example: 3000 RPM V-twin = 50 Hz
2. **Generates harmonics** for realistic sound
   - Fundamental + 2nd, 3rd, 4th, 5th harmonics
   - Sub-harmonic for V-twin character
3. **Adds exhaust noise** (pink noise filtered)
4. **Modulates based on load** (throttle)
5. **Adds crackle** on decel (high RPM + low load)

---

## 🎵 Sound Quality Tips

### Best Experience
- Use **headphones** for full effect
- Start at **50% volume**
- Try in a **quiet room**
- **Slowly** move sliders to hear transitions

### Realistic Settings
- **Harley idle**: 1000 RPM, 10% load, 60% volume
- **Sportbike cruise**: 4000 RPM, 30% load, 50% volume
- **Muscle car WOT**: 5000 RPM, 100% load, 70% volume

---

## 🚀 Next Steps

After testing:
1. ✅ Try all preset scenarios
2. ✅ Test different cylinder counts
3. ✅ Run a full simulator pull on JetDrive page
4. ✅ Adjust volume to your preference
5. ✅ Share feedback!

---

## 📝 Feedback Questions

While testing, consider:
- Does the sound feel realistic?
- Is the RPM sync accurate?
- Do you like the decel crackle?
- Is the volume range good?
- Any features you'd like added?

---

**Enjoy the immersive dyno experience!** 🏍️💨🎵

Need help? Check the full docs:
- `docs/AUDIO_ENGINE.md` - Technical details
- `docs/AUDIO_QUICK_START.md` - User guide

