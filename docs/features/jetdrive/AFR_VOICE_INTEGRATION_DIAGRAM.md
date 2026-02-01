# AFR Voice Feedback - Integration Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     JetDrive Command Center                         │
│                  (JetDriveAutoTunePage.tsx)                        │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ Orchestrates
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│ useJetDrive  │        │ useAIAssist  │        │ useAudioEng  │
│    Live      │        │    ant       │        │    ine       │
└──────────────┘        └──────────────┘        └──────────────┘
        │                        │                        │
        │ Provides               │ Provides               │ Provides
        │ Live Data              │ Voice Events           │ Sound FX
        │                        │                        │
        ▼                        ▼                        ▼
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│ • currentRpm │        │ • onPullStart│        │ • playBeep() │
│ • currentAfr │        │ • onPullEnd  │        │ • playWarn() │
│ • currentMap │        │ • onHighRpm  │        │ • playSuccess│
│ • currentHp  │        │ • onKnock    │        │              │
│ • target AFR │        │ • onAfrLean  │◄───────┼──────────────┤
│              │        │ • onAfrRich  │  NEW!  │              │
│              │        │ • onGoodPull │◄───────┘              │
└──────────────┘        └──────────────┘                       
        │                        │                              
        │                        │                              
        └────────┬───────────────┘                              
                 │                                              
                 ▼                                              
        ┌─────────────────┐                                    
        │  AFR Monitoring │                                    
        │     Logic       │                                    
        └─────────────────┘                                    
```

---

## Data Flow - AFR Feedback

```
┌──────────────────────────────────────────────────────────────┐
│ 1. JetDrive Hardware / Simulator                             │
│    • Sends live AFR data via UDP multicast                   │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. Backend API (api/routes/jetdrive.py)                     │
│    • Receives multicast packets                              │
│    • Parses channel data                                     │
│    • Exposes /hardware/live/data endpoint                    │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. useJetDriveLive Hook                                      │
│    • Polls /hardware/live/data every 100ms                   │
│    • Extracts AFR from channels['AFR 1'] or chan_23          │
│    • Updates currentAfr state                                │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. AFR Target Table                                          │
│    • User-configured target AFR per MAP range                │
│    • Calculates currentTargetAfr based on currentMap         │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. AFR Monitoring Logic (NEW!)                              │
│    • Runs every 100ms during captures                        │
│    • Checks: audioFunMode && isCapturing && RPM > 2000       │
│    • Calculates: afrError = currentAfr - currentTargetAfr    │
│    • Calculates: afrErrorPercent = |error / target| * 100    │
│    • Applies thresholds:                                     │
│      - < 2%: onGoodPull()                                    │
│      - > 4% above: onAfrLean()                               │
│      - > 4% below: onAfrRich()                               │
│    • Enforces 8-second cooldown                              │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. useAIAssistant Hook                                       │
│    • Receives event trigger                                  │
│    • Selects random phrase from PHRASES array                │
│    • Creates SpeechSynthesisUtterance                        │
│    • Configures voice, pitch, rate, volume                   │
│    • Calls window.speechSynthesis.speak()                    │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 7. Browser TTS Engine                                        │
│    • Synthesizes speech using selected voice                 │
│    • Outputs audio to speakers                               │
│    • User hears: "Perfect! AFR is right on target!"          │
└──────────────────────────────────────────────────────────────┘
```

---

## Event Trigger Conditions

```
┌─────────────────────────────────────────────────────────────┐
│                    AFR Monitoring Decision Tree              │
└─────────────────────────────────────────────────────────────┘

                    [Every 100ms]
                         │
                         ▼
              ┌──────────────────┐
              │ Fun Mode Enabled?│
              └──────────────────┘
                    │         │
                   NO        YES
                    │         │
                    ▼         ▼
               [Silent]  ┌──────────────┐
                         │ Is Capturing?│
                         └──────────────┘
                              │      │
                             NO     YES
                              │      │
                              ▼      ▼
                         [Silent] ┌────────────┐
                                  │ RPM > 2000?│
                                  └────────────┘
                                       │     │
                                      NO    YES
                                       │     │
                                       ▼     ▼
                                  [Silent] ┌──────────────────┐
                                           │ Cooldown Active? │
                                           │ (< 8 seconds)    │
                                           └──────────────────┘
                                                │         │
                                               YES       NO
                                                │         │
                                                ▼         ▼
                                           [Silent]  ┌────────────────┐
                                                     │ AFR Data Valid?│
                                                     │ (AFR > 0)      │
                                                     └────────────────┘
                                                          │        │
                                                         NO       YES
                                                          │        │
                                                          ▼        ▼
                                                     [Silent]  ┌──────────────────┐
                                                               │ Calculate Error  │
                                                               │ error = AFR - tgt│
                                                               │ err% = |e/t|*100 │
                                                               └──────────────────┘
                                                                       │
                                    ┌──────────────────────────────────┼──────────────────────────────────┐
                                    │                                  │                                  │
                                    ▼                                  ▼                                  ▼
                            ┌──────────────┐                  ┌──────────────┐                  ┌──────────────┐
                            │ err% < 2%    │                  │ err > 0 &&   │                  │ err < 0 &&   │
                            │              │                  │ err% > 4%    │                  │ err% > 4%    │
                            └──────────────┘                  └──────────────┘                  └──────────────┘
                                    │                                  │                                  │
                                    ▼                                  ▼                                  ▼
                            ┌──────────────┐                  ┌──────────────┐                  ┌──────────────┐
                            │ onGoodPull() │                  │ onAfrLean()  │                  │ onAfrRich()  │
                            └──────────────┘                  └──────────────┘                  └──────────────┘
                                    │                                  │                                  │
                                    ▼                                  ▼                                  ▼
                            ┌──────────────┐                  ┌──────────────┐                  ┌──────────────┐
                            │   "Perfect!  │                  │  "Running    │                  │  "Running    │
                            │ AFR is right │                  │   lean!      │                  │   rich!      │
                            │  on target!" │                  │ Needs fuel!" │                  │ Less fuel."  │
                            └──────────────┘                  └──────────────┘                  └──────────────┘
```

---

## Threshold Examples

```
Target AFR: 13.2

┌─────────────────────────────────────────────────────────────────┐
│                        AFR Range                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  11.0    12.0    12.67   12.94   13.2    13.46   13.73   14.0  │
│   │       │       │       │       │       │       │       │    │
│   │       │       │       │       │       │       │       │    │
│   │       │   ┌───┴───────┴───────┴───────┴───┐   │       │    │
│   │       │   │      GOOD PULL (< 2%)        │   │       │    │
│   │       │   │   "Perfect! On target!"      │   │       │    │
│   │       │   └───────────────────────────────┘   │       │    │
│   │       │                                       │       │    │
│   │   ┌───┴───────────────────────────────────────┴───┐   │    │
│   │   │           RICH (> 4% below)                   │   │    │
│   │   │        "Running rich! Less fuel."             │   │    │
│   │   └───────────────────────────────────────────────┘   │    │
│   │                                                       │    │
│   │                                           ┌───────────┴────┴─┐
│   │                                           │  LEAN (> 4% above)│
│   │                                           │ "Running lean!    │
│   │                                           │  Needs fuel!"     │
│   │                                           └───────────────────┘
│   │                                                               │
│   └───────────────────────────────────────────────────────────────┘
│                    VERY RICH (silent)                             │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘

Legend:
  12.94 - 13.46  → Good Pull (within 2%)
  < 12.67        → Rich (more than 4% below)
  > 13.73        → Lean (more than 4% above)
```

---

## Cooldown System

```
Time →

0s      3s      6s      8s      11s     14s     16s     19s
│       │       │       │       │       │       │       │
│       │       │       │       │       │       │       │
├───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────►
│       │       │       │       │       │       │       │
▼       │       │       ▼       │       │       ▼       │
Lean    │       │       Rich    │       │       Good    │
Spoken  │       │       (silent)│       │       (silent)│
        │       │       ↑       │       │       ↑       │
        │       │       │       │       │       │       │
        │       │       └───────┼───────┘       └───────┘
        │       │          < 8s │                  < 8s
        │       │          from │                  from
        │       │          last │                  last
        │       │                                        
        └───────┴───────────────────────────────────────►
                   8-second AFR cooldown window


Rules:
  • First event at 0s → Speaks immediately
  • Second event at 8s → Blocked (< 8s since last)
  • Third event at 16s → Blocked (< 8s since last)
  • Fourth event at 24s → Would speak (≥ 8s since last)
```

---

## Integration with Existing Systems

```
┌─────────────────────────────────────────────────────────────────┐
│                    Existing AI Assistant Events                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✅ onPullStart()     → "Let's go! Full send!"                  │
│  ✅ onPullEnd(hp)     → "142 horsepower! Nice!"                 │
│  ✅ onHighRpm()       → "She's screaming!"                      │
│  ✅ onKnockDetected() → "Knock detected! Be careful!"           │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                    NEW AFR Events (v1.2.3)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🆕 onGoodPull()      → "Perfect! AFR is right on target!"      │
│  🆕 onAfrLean()       → "Running lean! Needs more fuel!"        │
│  🆕 onAfrRich()       → "Running rich! Could use less fuel."    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Complete Pull Sequence

```
Time  RPM   AFR   Target  Event                Voice
────  ────  ────  ──────  ───────────────────  ─────────────────────────
0.0s  1000  14.7  14.7    Idle                 (silent)
1.0s  1500  14.5  14.7    Revving              (silent - RPM < 2000)
2.0s  2500  14.0  13.8    Pull Start           "Let's go! Full send!"
3.0s  3000  13.9  13.5    AFR Good (1.5%)      "Perfect! On target!"
4.0s  3500  13.6  13.2    (cooldown)           (silent)
5.0s  4000  13.8  13.2    AFR Rich (4.5%)      (silent - cooldown)
6.0s  4500  14.2  13.2    AFR Lean (7.6%)      (silent - cooldown)
7.0s  5000  14.5  13.2    AFR Lean (9.8%)      (silent - cooldown)
8.0s  5500  14.8  13.2    AFR Lean (12.1%)     (silent - cooldown)
9.0s  6000  15.0  13.2    AFR Lean (13.6%)     (silent - cooldown)
10.0s 6500  15.2  13.2    AFR Lean (15.2%)     (silent - cooldown)
11.0s 7000  15.3  13.2    AFR Lean (15.9%)     "Running lean! Needs fuel!"
                          High RPM             "She's screaming!"
12.0s 6800  14.9  13.2    (cooldown)           (silent)
13.0s 6500  14.5  13.2    (cooldown)           (silent)
14.0s 6000  14.0  13.2    Pull End             "142 horsepower! Nice!"
15.0s 5000  13.8  13.2    Decel                (silent)
16.0s 3000  14.2  13.5    Decel                (silent)
17.0s 1500  14.7  14.7    Idle                 (silent)
```

---

## File Structure

```
DynoAI_3/
│
├── frontend/src/
│   ├── hooks/
│   │   ├── useAIAssistant.ts        ← Voice event definitions
│   │   ├── useJetDriveLive.ts       ← Live data source
│   │   └── useAudioEngine.ts        ← Sound effects
│   │
│   ├── pages/
│   │   └── JetDriveAutoTunePage.tsx ← AFR monitoring logic (NEW!)
│   │
│   └── components/jetdrive/
│       ├── AudioCapturePanel.tsx    ← Knock detection
│       └── AFRTargetTable.tsx       ← Target AFR configuration
│
├── docs/
│   ├── AI_VOICE_ASSISTANT.md        ← Complete documentation (NEW!)
│   └── AFR_VOICE_INTEGRATION_DIAGRAM.md ← This file (NEW!)
│
├── AFR_VOICE_FEEDBACK_TEST_GUIDE.md ← Quick test guide (NEW!)
├── AFR_VOICE_FEEDBACK_SUMMARY.md    ← Implementation summary (NEW!)
└── CHANGELOG.md                     ← Version history (UPDATED)
```

---

## Dependencies

```
useAIAssistant
    │
    ├─ Depends on: window.speechSynthesis (Browser API)
    ├─ Depends on: SpeechSynthesisUtterance (Browser API)
    └─ Provides: Voice event triggers

useJetDriveLive
    │
    ├─ Depends on: Backend API (/api/jetdrive/hardware/live/data)
    ├─ Depends on: React Query (useQuery)
    └─ Provides: currentAfr, currentMap, currentRpm

AFR Monitoring Logic
    │
    ├─ Depends on: useAIAssistant
    ├─ Depends on: useJetDriveLive
    ├─ Depends on: AFR Target Table (afrTargets state)
    └─ Provides: Real-time AFR feedback
```

---

## Performance Considerations

### Polling Frequency
- **Live Data**: 100ms (10 Hz)
- **AFR Check**: Every poll (100ms)
- **Voice Cooldown**: 8000ms (8 seconds)

### CPU Impact
- Minimal - simple percentage calculations
- No heavy processing
- Browser TTS handled by OS

### Network Impact
- No additional API calls
- Uses existing live data polling
- No extra bandwidth

### Memory Impact
- Single ref for cooldown timestamp
- No data accumulation
- Negligible memory footprint

---

**Status**: ✅ Complete and Production-Ready
**Version**: v1.2.3
**Date**: December 15, 2025

