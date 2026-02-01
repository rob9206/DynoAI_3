# AI Voice Assistant - Real-Time Dyno Feedback

## Overview

The AI Voice Assistant provides real-time voice feedback during dyno pulls, creating an immersive and informative tuning experience. The assistant uses browser Text-to-Speech (TTS) with a feminine voice personality that reacts to dyno events.

## Features

### 🎤 Voice Events

#### Pull Events
- **Pull Start** - Triggered when RPM exceeds threshold or capture starts
  - "Let's go! Full send!"
  - "Here we go baby!"
  - "Time to make some power!"

- **Pull End** - Triggered when pull completes
  - Announces peak horsepower: "142 horsepower! Nice!"
  - "Nice pull!"
  - "That was awesome!"

- **Record HP** - Triggered when a new personal best is achieved
  - "New record! 145 horsepower! Oh my god!"
  - "That's a new personal best!"

#### AFR Feedback (NEW!)
Real-time air/fuel ratio monitoring during pulls:

- **Good Pull** - AFR within 2% of target
  - "Perfect! AFR is right on target!"
  - "That's dialed in perfectly!"
  - "Ooh, she's running clean!"

- **Lean Condition** - AFR more than 4% above target
  - "Running a bit lean there!"
  - "She's thirsty, needs more fuel!"
  - "AFR is lean, add some fuel!"

- **Rich Condition** - AFR more than 4% below target
  - "Running rich! Could use less fuel."
  - "A little too much fuel there."
  - "AFR is on the rich side."

#### Performance Events
- **High RPM** - Triggered above 7000 RPM
  - "She's screaming!"
  - "Listen to her sing!"
  - "That sounds amazing!"

- **Knock Detected** - Triggered by audio capture panel
  - "Ooh, I heard some knock! Be careful!"
  - "Knock detected! Maybe pull some timing?"
  - "Careful! Knock detected!"

## Configuration

### Enable/Disable
The AI Assistant is tied to "Fun Mode" in the JetDrive Command Center:

1. Navigate to **JetDrive** page
2. Look for **Audio Controls** section (bottom right)
3. Toggle **Fun Mode** switch
4. When enabled, you'll see: 🎤 AI Assistant: [Voice Name]

### Voice Selection
The system automatically selects the best available voice:

**Preferred Voices (in order):**
1. Samantha (macOS)
2. Karen (macOS Australian)
3. Microsoft Zira (Windows)
4. Microsoft Eva (Windows)
5. Google US English Female (Chrome)
6. Any English female voice
7. Fallback to any English voice

### Voice Settings
Default settings optimized for excitement:
- **Volume**: 80%
- **Pitch**: 1.3 (slightly higher for feminine voice)
- **Rate**: 1.1 (slightly faster for excitement)

## Technical Implementation

### Hook: `useAIAssistant.ts`
```typescript
const aiAssistant = useAIAssistant({ 
    enabled: audioFunMode 
});

// Trigger events
aiAssistant.onPullStart();
aiAssistant.onPullEnd(peakHp);
aiAssistant.onHighRpm();
aiAssistant.onKnockDetected();
aiAssistant.onAfrLean();
aiAssistant.onAfrRich();
aiAssistant.onGoodPull();
```

### AFR Monitoring Logic
Located in `JetDriveAutoTunePage.tsx`:

```typescript
// Monitors AFR during pulls (RPM > 2000)
// Compares current AFR to target AFR from table
// Triggers voice events based on error percentage:
//   - Good: < 2% error
//   - Lean: > 4% above target
//   - Rich: > 4% below target
// Cooldown: 8 seconds between AFR comments
```

### Event Cooldowns
To prevent spam, events have cooldowns:
- **Same Event Type**: 3 seconds (general)
- **AFR Comments**: 8 seconds
- **High RPM**: 10 seconds

## Integration Points

### JetDrive Live Data
- Monitors `currentAfr` from live channels
- Monitors `currentTargetAfr` from AFR target table
- Only active during captures (`isCapturing === true`)
- Only active during pulls (`currentRpm > 2000`)

### Audio Capture Panel
- Knock detection triggers `aiAssistant.onKnockDetected()`
- Synchronized with audio recording events

### Simulator
- Works with both real hardware and simulator
- Detects pull end via simulator state transitions
- Announces peak HP at end of simulated pulls

## Browser Compatibility

### Requirements
- Modern browser with Web Speech API support
- User interaction required before first speech (browser security)

### Supported Browsers
✅ Chrome/Edge (Excellent - Google voices)
✅ Safari (Excellent - macOS voices)
✅ Firefox (Good - system voices)

### Troubleshooting

**No voice?**
1. Check that Fun Mode is enabled
2. Ensure browser volume is up
3. Click anywhere on page first (browser security)
4. Check console for voice loading errors

**Wrong voice?**
- The system auto-selects the best available voice
- Voice selection logged to console: `[AI Assistant] Voice loaded: [name]`

**Voice too fast/slow?**
- Currently uses fixed settings (pitch: 1.3, rate: 1.1)
- Future enhancement: User-adjustable settings

## Testing

### Quick Test
1. Enable Fun Mode
2. Click **Test Voice** button (🎤 icon)
3. Should hear: "Hey! I'm your DynoAI assistant! Let's make some power!"

### Full Test
1. Start simulator with M8 114 profile
2. Enable Fun Mode
3. Click "Trigger Pull"
4. Listen for:
   - Pull start announcement
   - AFR feedback during pull
   - Peak HP announcement at end

## Future Enhancements

### Planned
- [ ] User-adjustable voice settings (pitch, rate, volume)
- [ ] Custom phrase editor
- [ ] Multiple voice personalities
- [ ] Language support (Spanish, etc.)
- [ ] Voice event history/replay
- [ ] Integration with analysis results

### Ideas
- [ ] Coaching mode - "Try pulling to 6500 RPM"
- [ ] Comparison mode - "That's 3 HP better than last pull!"
- [ ] Safety warnings - "Coolant temp is high!"
- [ ] Celebration sounds on new records

## Related Files

- `frontend/src/hooks/useAIAssistant.ts` - Core hook implementation
- `frontend/src/pages/JetDriveAutoTunePage.tsx` - Integration and event triggers
- `frontend/src/components/jetdrive/AudioCapturePanel.tsx` - Knock detection integration
- `frontend/src/hooks/useAudioEngine.ts` - Synthetic engine sounds (separate system)

## Credits

Inspired by racing games and professional dyno software that provide audio feedback to operators. Designed to make tuning more engaging and informative without requiring constant screen monitoring.

---

**Status**: ✅ Fully implemented and tested
**Version**: v1.2.1
**Last Updated**: December 15, 2025

