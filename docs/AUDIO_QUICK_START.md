# Audio Engine - Quick Start Guide

## 🎵 What You Get

DynoAI now includes a **real-time audio engine** that synthesizes engine sounds synchronized with your dyno pulls!

### Features at a Glance
- 🔊 **Realistic engine sounds** that match RPM and load
- 🎛️ **Volume controls** with mute
- 🏍️ **Configurable engines** (V-twin, inline-4, V8, etc.)
- 💥 **Decel crackle** - hear those exhaust pops!
- 🎯 **Auto-start** during dyno captures
- 🎨 **Beautiful UI** with visual feedback

## Quick Start

### Option 1: JetDrive Page (Automatic)

1. Navigate to **JetDrive** page
2. Start a dyno capture or simulator
3. **Audio automatically starts!** 🎉
4. Adjust volume with the inline controls

The audio will:
- ✅ Start when capture begins
- ✅ Match RPM from live data
- ✅ Adjust intensity based on load
- ✅ Stop when capture ends

### Option 2: Demo Page (Manual Testing)

1. Navigate to `/audio-demo` route
2. Click **"Start Engine"**
3. Move the **RPM slider** (500-8000)
4. Adjust **Load slider** (0-100%)
5. Try the **preset scenarios**:
   - 🔵 Idle (1000 RPM, 10% load)
   - 🟢 Cruise (3000 RPM, 30% load)
   - 🔴 WOT (6000 RPM, 100% load)
   - 💥 Decel (5000 RPM, 5% load) - hear the crackle!

## Controls

### Compact Mode (JetDrive Page)
```
[🔊] [🔇] [━━━━━━━━] 3500 RPM
```
- Power button: Start/stop
- Speaker: Mute/unmute
- Slider: Volume control
- Badge: Current RPM

### Full Mode (Demo Page)
- **RPM Slider**: 500-8000 RPM
- **Load Slider**: 0-100% throttle
- **Volume Slider**: 0-100%
- **Cylinder Config**: 1, 2, 4, 6, or 8 cylinders
- **Preset Buttons**: Quick scenarios
- **Sound Effects**: Test tones

## Tips & Tricks

### 🎯 Best Experience
1. **Use headphones** for full effect
2. **Start at 50% volume** and adjust
3. **Try the Decel preset** to hear exhaust pops
4. **Change cylinder count** for different engines

### 🏍️ Harley V-Twin Setup
- Cylinders: **2**
- Volume: **60%**
- Try WOT pull from 2000-6000 RPM

### 🏁 Sportbike Setup
- Cylinders: **4**
- Volume: **50%**
- Try WOT pull from 3000-12000 RPM

### 🚗 V8 Setup
- Cylinders: **8**
- Volume: **70%**
- Try WOT pull from 1500-7000 RPM

## Troubleshooting

### No Sound?
1. ✅ Check browser volume (not muted)
2. ✅ Check system volume
3. ✅ Click "Start Engine" button
4. ✅ Verify volume slider > 0%
5. ✅ Check mute button (should show 🔊 not 🔇)

### Choppy Audio?
1. Close other audio-heavy tabs
2. Reduce browser CPU usage
3. Try lower RPM values first

### Browser Says "Blocked"?
- Some browsers block audio until user interaction
- Just click "Start Engine" - it will work!

## Examples

### Code Example
```typescript
import { useAudioEngine } from '../hooks/useAudioEngine';

function MyComponent() {
  const { startEngine, setRpm, setLoad } = useAudioEngine({
    cylinders: 2,
    volume: 0.5,
  });

  return (
    <button onClick={startEngine}>
      Start Engine Sound
    </button>
  );
}
```

### Integration Example
```typescript
<AudioEngineControls
  rpm={currentRpm}
  load={currentLoad}
  autoStart={isCapturing}
  compact={true}
  cylinders={2}
/>
```

## What's Happening Under the Hood?

The audio engine:
1. **Calculates frequency** from RPM and cylinder count
2. **Generates harmonics** for realistic engine character
3. **Adds exhaust noise** using pink noise
4. **Modulates volume** based on load (throttle)
5. **Adds crackle** on deceleration
6. **Smooths transitions** for natural sound

### Frequency Formula
```
frequency = (RPM / 60) × (cylinders / 2)
```

Example: V-twin at 3000 RPM
```
frequency = (3000 / 60) × (2 / 2) = 50 Hz
```

## Next Steps

1. **Try the demo page** to get familiar
2. **Run a dyno pull** with audio enabled
3. **Adjust volume** to your preference
4. **Experiment** with different cylinder counts
5. **Share feedback** on sound quality!

## More Info

- 📖 [Full Documentation](AUDIO_ENGINE.md)
- 📋 [Implementation Details](AUDIO_IMPLEMENTATION_SUMMARY.md)
- 🐛 [Report Issues](../README.md)

---

**Enjoy the immersive dyno tuning experience!** 🎵🏍️💨

