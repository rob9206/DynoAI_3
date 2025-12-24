# Audio Engine System

## Overview

The DynoAI Audio Engine provides real-time synthesized engine sounds that synchronize with dyno pulls, creating an immersive tuning experience. The system generates realistic engine audio based on RPM and load, complete with exhaust notes, harmonics, and deceleration effects.

## Features

### 🎵 Real-Time Engine Sound Synthesis
- **RPM-synchronized audio**: Engine sound frequency matches current RPM
- **Harmonic generation**: Realistic engine character with fundamental + harmonics
- **Load-based modulation**: Sound intensity varies with throttle/load
- **Smooth transitions**: Exponential smoothing for natural sound changes

### 🔊 Audio Effects
- **Exhaust note simulation**: Pink noise filtered for realistic exhaust character
- **Deceleration crackle**: Pops and burbles on decel (high RPM, low load)
- **Event sounds**: Startup, shutdown, warning, and success tones
- **Configurable cylinders**: Adjust for V-twin, inline-4, V8, etc.

### 🎛️ User Controls
- **Start/Stop**: Manual engine sound control
- **Volume control**: 0-100% master volume
- **Mute toggle**: Quick silence
- **Auto-start**: Automatically play during dyno pulls
- **Compact mode**: Minimal UI for tight spaces

## Usage

### Basic Integration

```typescript
import { useAudioEngine } from '../hooks/useAudioEngine';

function MyComponent() {
  const {
    state,
    startEngine,
    stopEngine,
    setRpm,
    setLoad,
    setVolume,
  } = useAudioEngine({
    volume: 0.5,
    cylinders: 2, // V-twin
    enableCrackle: true,
  });

  // Update RPM and load in real-time
  useEffect(() => {
    if (state.isPlaying) {
      setRpm(currentRpm);
      setLoad(currentThrottle);
    }
  }, [currentRpm, currentThrottle, state.isPlaying]);

  return (
    <button onClick={startEngine}>Start Engine</button>
  );
}
```

### Using the AudioEngineControls Component

```typescript
import { AudioEngineControls } from '../components/jetdrive/AudioEngineControls';

function DynoPage() {
  return (
    <AudioEngineControls
      rpm={currentRpm}
      load={currentLoad} // 0-1 (0% to 100% throttle)
      autoStart={isCapturing}
      autoStartRpm={1000}
      compact={false}
      cylinders={2}
    />
  );
}
```

## API Reference

### `useAudioEngine(options)`

#### Options
```typescript
interface AudioEngineOptions {
  volume?: number;           // 0-1, default: 0.5
  cylinders?: number;        // Default: 2 (V-twin)
  enableCrackle?: boolean;   // Default: true
  enableBoost?: boolean;     // Default: false (future feature)
}
```

#### Returns
```typescript
interface UseAudioEngineReturn {
  // State
  state: {
    isPlaying: boolean;
    isMuted: boolean;
    volume: number;
    rpm: number;
    load: number;
    error: string | null;
  };
  
  // Actions
  startEngine: () => Promise<void>;
  stopEngine: () => void;
  setRpm: (rpm: number) => void;
  setLoad: (load: number) => void;  // 0-1
  setVolume: (volume: number) => void;
  toggleMute: () => void;
  
  // Sound effects
  playStartup: () => void;
  playShutdown: () => void;
  playWarning: () => void;
  playSuccess: () => void;
  playBeep: (frequency?: number, duration?: number) => void;
}
```

### `AudioEngineControls` Component

#### Props
```typescript
interface AudioEngineControlsProps {
  rpm: number;              // Current RPM from dyno
  load?: number;            // 0-1, throttle position
  autoStart?: boolean;      // Auto-start when RPM > threshold
  autoStartRpm?: number;    // Default: 1000
  compact?: boolean;        // Compact UI mode
  cylinders?: number;       // Default: 2
}
```

## Technical Details

### Audio Synthesis Architecture

1. **Web Audio API**: Uses browser's native audio synthesis
2. **Oscillator Bank**: Multiple oscillators for harmonics
   - Fundamental: (RPM / 60) × (cylinders / 2)
   - 2nd-5th harmonics for richness
   - Sub-harmonic for V-twin character
3. **Noise Generator**: Pink noise (1/f) for exhaust
4. **Filtering**: Bandpass/highpass filters for character
5. **Gain Nodes**: Dynamic volume control per layer

### Frequency Calculation

For a 4-stroke engine:
```
frequency = (RPM / 60) × (cylinders / 2)
```

Examples:
- V-twin @ 3000 RPM: 3000/60 × 2/2 = 50 Hz
- Inline-4 @ 6000 RPM: 6000/60 × 4/2 = 200 Hz

### Load-Based Modulation

- **Low load (0-0.3)**: Quieter, less aggressive
- **Medium load (0.3-0.7)**: Moderate volume
- **High load (0.7-1.0)**: Full volume, aggressive tone

### Deceleration Crackle

Activated when:
- RPM > 3000
- Load < 0.2
- Crackle enabled

Uses highpass-filtered noise for realistic pops.

## Browser Compatibility

### Requirements
- Modern browser with Web Audio API support
- Chrome 35+, Firefox 25+, Safari 14.1+, Edge 79+

### Autoplay Policy
Due to browser autoplay restrictions, audio context may be suspended until user interaction. The hook automatically resumes the context when `startEngine()` is called.

## Performance

### CPU Usage
- ~1-2% CPU on modern hardware
- Minimal impact on dyno data processing
- Uses requestAnimationFrame for smooth updates

### Memory
- ~2MB for audio buffers
- Constant memory usage (no leaks)

## Configuration Examples

### Harley V-Twin
```typescript
useAudioEngine({
  cylinders: 2,
  volume: 0.6,
  enableCrackle: true,
})
```

### Sportbike Inline-4
```typescript
useAudioEngine({
  cylinders: 4,
  volume: 0.5,
  enableCrackle: true,
})
```

### V8 Muscle Car
```typescript
useAudioEngine({
  cylinders: 8,
  volume: 0.7,
  enableCrackle: true,
})
```

## Future Enhancements

- [ ] Turbo/supercharger whine
- [ ] Backfire effects
- [ ] Intake noise
- [ ] Transmission whine
- [ ] Audio recording/export
- [ ] Custom engine profiles
- [ ] Reverb/environment simulation
- [ ] Multi-channel audio (stereo panning)

## Troubleshooting

### No sound playing
1. Check browser console for errors
2. Verify audio is not muted in browser/OS
3. Check `state.error` for error messages
4. Ensure user has interacted with page (autoplay policy)

### Choppy/stuttering audio
1. Reduce `pollInterval` in JetDrive hook
2. Check CPU usage
3. Close other audio-intensive tabs

### Sound doesn't match RPM
1. Verify `setRpm()` is being called with correct values
2. Check cylinder count configuration
3. Ensure RPM values are in correct range (0-10000)

## Examples

See `JetDriveAutoTunePage.tsx` for a complete integration example with:
- Auto-start during dyno pulls
- Load calculation from drum force
- Compact inline controls
- Synchronization with live data

## License

Part of DynoAI project - see main LICENSE file.







