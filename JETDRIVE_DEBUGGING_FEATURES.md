# JetDrive Real-Time Features Debugging Guide

## Overview

This document describes the comprehensive debugging and enhancement features added to the JetDrive real-time functionality in DynoAI_3. These features help diagnose and resolve issues with live data capture, auto-tune operations, VE table updates, and session replay.

## Table of Contents

1. [Backend Enhancements](#backend-enhancements)
2. [Frontend Hook Enhancements](#frontend-hook-enhancements)
3. [Component Enhancements](#component-enhancements)
4. [Quick Reference](#quick-reference)
5. [Troubleshooting](#troubleshooting)

---

## Backend Enhancements

### 1. Channel Discovery Endpoint

**Endpoint:** `GET /api/jetdrive/hardware/channels/discover`

Discovers all available channels with their current values and suggests appropriate configuration.

**Response:**
```json
{
  "success": true,
  "channel_count": 45,
  "channels": [
    {
      "id": 42,
      "name": "Digital RPM 1",
      "value": 3250.5,
      "timestamp": 1234567890,
      "suggested_config": {
        "label": "RPM",
        "units": "rpm",
        "min": 0,
        "max": 8000,
        "decimals": 0,
        "color": "#4ade80"
      }
    }
  ],
  "timestamp": "2025-12-15T19:35:00.000Z"
}
```

**Usage:**
```javascript
const res = await fetch('/api/jetdrive/hardware/channels/discover');
const data = await res.json();
console.table(data.channels);
```

**Features:**
- Auto-detects channel types based on name patterns
- Suggests appropriate units, ranges, and colors
- Works with both real hardware and simulator
- Useful for debugging channel name mismatches

---

### 2. Hardware Health Monitoring Endpoint

**Endpoint:** `GET /api/jetdrive/hardware/health`

Checks hardware connection health with latency measurement.

**Response:**
```json
{
  "healthy": true,
  "connected": true,
  "simulated": false,
  "latency_ms": 12.5,
  "channel_count": 45,
  "last_update": "2025-12-15T19:35:00.000Z",
  "mode": "hardware"
}
```

**Usage:**
```javascript
// Check health periodically
const { data: health } = useQuery({
  queryKey: ['jetdrive-health'],
  queryFn: async () => {
    const res = await fetch('/api/jetdrive/hardware/health');
    return res.json();
  },
  refetchInterval: 5000, // Check every 5 seconds
});
```

**Features:**
- Measures connection latency
- Detects stale data (no updates in 5+ seconds)
- Works with simulator and real hardware
- Returns 503 status when unhealthy

---

### 3. Channel Configuration Suggestions

**Function:** `suggest_channel_config(channel_name, channel_data)`

Automatically suggests configuration for channels based on naming patterns.

**Patterns Recognized:**
- RPM: `rpm`, `digital rpm`, etc.
- AFR: `afr`, `air/fuel`, `air-fuel`
- Lambda: `lambda`
- Force: `force`, `load`, `drum`
- Horsepower: `hp`, `horsepower`, `power`
- Torque: `tq`, `torque`
- MAP: `map`
- TPS: `tps`, `throttle`
- Temperature: `temp`, `iat`, `ect`
- Humidity: `humid`
- Pressure: `pressure`, `baro`
- Voltage: `volt`, `vbatt`, `battery`

---

## Frontend Hook Enhancements

### useJetDriveLive Hook

Enhanced with flexible channel name mapping and debug logging.

#### 1. Flexible Channel Name Matching

**Function:** `getChannelConfig(channelName)`

Matches channel names using multiple strategies:
1. Exact match
2. Case-insensitive match
3. Partial pattern matching

**Example:**
```typescript
// All these will match correctly:
getChannelConfig('Digital RPM 1');    // Exact match
getChannelConfig('digital rpm 1');    // Case-insensitive
getChannelConfig('Some RPM Channel'); // Partial match (contains 'rpm')
getChannelConfig('chan_42');          // Fallback mapping
```

#### 2. Debug Logging

The hook now logs channel mapping information every 100 polls (every 5 seconds at 50ms poll rate):

**Console Output:**
```
[useJetDriveLive] Raw channels: (45) ["Digital RPM 1", "Force Drum 1", ...]
[useJetDriveLive] Mapped channels: 45
[useJetDriveLive] Unmapped channels (using fallback config): ["chan_99", "chan_100"]
```

**Features:**
- Logs raw channel names from hardware
- Identifies unmapped channels using fallback config
- Throttled logging to avoid console spam
- Helpful for debugging channel name mismatches

---

## Component Enhancements

### 1. QuickTunePanel - Auto-Detection

The QuickTunePanel now includes robust auto-detection logic for dyno runs.

#### Features

**RPM Monitoring:**
- Continuously monitors RPM from multiple channel sources
- Maintains rolling history (last 20 samples = 1 second)
- Calculates average RPM for stable detection

**Configurable Detection:**
```typescript
interface AutoDetectConfig {
  enabled: boolean;        // Enable/disable auto-detection
  rpmThreshold: number;    // RPM threshold (default: 2000)
  minDuration: number;     // Minimum run duration (default: 3 sec)
  cooldownPeriod: number;  // Cooldown between runs (default: 5 sec)
}
```

**Visual Feedback:**
- Alert shown when run is detected
- Toast notifications for run start/end
- RPM and detection status display in dev mode

**Usage:**
```tsx
<QuickTunePanel apiUrl="http://127.0.0.1:5001/api/jetdrive" />
```

#### Debug Display (Development Mode)

```
Current RPM: 3250
Avg RPM: 3245
Run Detected: YES
Capturing: YES
```

---

### 2. LiveVETable - Performance Monitoring

The LiveVETable component now includes performance monitoring.

#### Features

**Update Tracking:**
- Tracks updates per second
- Displays in development mode
- Helps identify performance issues

**Display:**
```tsx
<Badge variant="outline" className="text-[10px]">
  20.5 ups  {/* Updates per second */}
</Badge>
```

**Clear History Button:**
- Renamed from "Reset" to "Clear History" for clarity
- Tooltip explains functionality
- Clears all cell history and VE corrections

#### Already Implemented Features

The LiveVETable already had excellent features:
- ✅ Efficient cell tracking with active cell highlighting
- ✅ Cell history tracking (hit counts)
- ✅ Visual cell highlighting with animations
- ✅ Bilinear interpolation for smooth tracking
- ✅ Color-coded cells (lean/rich/ok)
- ✅ Real-time VE corrections

---

### 3. SessionReplayPanel - Session Playback

New component for smooth playback of recorded dyno sessions.

#### Features

**Playback Controls:**
- Play/Pause button
- Reset to beginning
- Seek bar for jumping to specific time
- Speed control (0.5x, 1x, 2x, 4x)

**Data Interpolation:**
- Linear interpolation between data points
- Smooth 60 FPS playback
- Accurate time tracking

**Progress Display:**
- Current time / Total duration
- Progress percentage
- Data point count

**Usage:**
```tsx
<SessionReplayPanel
  apiUrl="http://127.0.0.1:5001/api/jetdrive"
  sessionId="run_12345"
  onDataUpdate={(channels) => {
    // Update gauges/charts with interpolated data
    updateGauges(channels);
  }}
/>
```

#### Session Data Format

Expected session data structure:
```typescript
interface SessionData {
  run_id: string;
  duration_sec: number;
  data_points: Array<{
    timestamp: number;  // seconds from start
    channels: Record<string, number>;
  }>;
}
```

---

## Quick Reference

### Diagnostic Checklist

#### Live Data Not Updating

1. **Check Hardware Connection:**
   ```bash
   curl http://127.0.0.1:5001/api/jetdrive/hardware/health
   ```

2. **Discover Available Channels:**
   ```bash
   curl http://127.0.0.1:5001/api/jetdrive/hardware/channels/discover
   ```

3. **Check Console Logs:**
   ```
   [useJetDriveLive] Raw channels: ...
   [useJetDriveLive] Unmapped channels: ...
   ```

4. **Verify Data Flow:**
   - Is `isCapturing` true?
   - Are channels being updated?
   - Check poll interval (should be 50ms)

#### Auto-Detection Not Working

1. **Check RPM Availability:**
   - Is RPM channel data being received?
   - Check channel names: 'Digital RPM 1', 'RPM', 'chan_42'

2. **Verify Configuration:**
   - Is auto-detection enabled?
   - Is RPM threshold appropriate? (default: 2000)

3. **Check Debug Display:**
   - What is current RPM?
   - Is average RPM calculated correctly?

#### VE Table Not Updating

1. **Check Live Status:**
   - Is `isLive` true?
   - Are gauges updating?

2. **Check RPM/MAP Values:**
   - Are they within table range?
   - Check console for active cell info

3. **Performance Monitoring:**
   - Check updates per second (should be ~20)
   - Look for console warnings

#### Session Replay Issues

1. **Check Session Loading:**
   - Does session endpoint return data?
   - Is data format correct?

2. **Verify Playback:**
   - Are data points being interpolated?
   - Check console for errors

---

## Troubleshooting

### Common Issues

#### Channel Names Don't Match

**Problem:** Channels are available but not displaying due to name mismatches.

**Solution:**
1. Use channel discovery endpoint to see actual names
2. Check debug logs for unmapped channels
3. The flexible matching should handle most variations
4. Add custom mappings to `JETDRIVE_CHANNEL_CONFIG` if needed

#### Performance is Slow

**Problem:** UI is laggy or updates are slow.

**Solution:**
1. Check updates per second in LiveVETable (should be 15-20)
2. Reduce poll interval if needed (default: 50ms)
3. Check browser console for errors
4. Ensure data isn't being logged too frequently

#### Auto-Detection Too Sensitive

**Problem:** Runs detected incorrectly or too frequently.

**Solution:**
1. Increase RPM threshold (try 2500-3000)
2. Increase cooldown period (try 10-15 seconds)
3. Check average RPM calculation in debug display
4. Ensure RPM data is stable (not noisy)

#### Session Replay Choppy

**Problem:** Playback is not smooth.

**Solution:**
1. Check data point density (need at least 10-20 points/sec)
2. Verify interpolation is working (check console)
3. Try slower playback speed (0.5x)
4. Ensure browser isn't throttling

---

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/jetdrive/hardware/channels/discover` | GET | Discover and suggest channel configs |
| `/api/jetdrive/hardware/health` | GET | Check connection health and latency |
| `/api/jetdrive/hardware/monitor/status` | GET | Get monitor status (existing) |
| `/api/jetdrive/hardware/live/data` | GET | Get live channel data (existing) |
| `/api/jetdrive/hardware/live/start` | POST | Start live capture (existing) |
| `/api/jetdrive/hardware/live/stop` | POST | Stop live capture (existing) |

---

## Component Props Summary

### QuickTunePanel
```typescript
interface QuickTunePanelProps {
  apiUrl: string;  // e.g., "http://127.0.0.1:5001/api/jetdrive"
}
```

### LiveVETable
```typescript
interface LiveVETableProps {
  currentRpm: number;
  currentMap: number;
  currentAfr: number;
  afrTargets?: Record<number, number>;
  targetAfr?: number;  // Deprecated
  isLive: boolean;
  enginePreset?: EnginePreset;
  onEnginePresetChange?: (preset: EnginePreset) => void;
  veCorrections?: number[][];
  hitCounts?: number[][];
  onCellClick?: (rpmIdx: number, mapIdx: number) => void;
}
```

### SessionReplayPanel
```typescript
interface SessionReplayPanelProps {
  apiUrl: string;
  sessionId: string;
  onDataUpdate?: (channels: Record<string, number>) => void;
}
```

---

## Development Tips

### Enable Debug Logging

Most debug features are automatically enabled in development mode (`process.env.NODE_ENV === 'development'`):
- Channel mapping logs
- RPM detection display
- Performance stats
- VE table update counts

### Testing Without Hardware

The system works seamlessly with the simulator:
```bash
# Start simulator
curl -X POST http://127.0.0.1:5001/api/jetdrive/simulator/start

# All features work identically with simulated data
```

### Performance Optimization

For best performance:
1. Keep poll interval at 50ms (20 Hz) for smooth updates
2. Use throttled logging (every 100 polls)
3. Clear VE table history periodically
4. Monitor updates per second metric

---

## Future Enhancements

Potential improvements for future versions:

1. **Channel Mapper UI:**
   - Visual tool to map unknown channels to known types
   - Save custom mappings to configuration

2. **Advanced Auto-Detection:**
   - Machine learning-based run detection
   - Multiple detection strategies (RPM, TPS, etc.)
   - Configurable detection regions (partial throttle vs WOT)

3. **Session Management:**
   - List and browse recorded sessions
   - Session metadata and tagging
   - Compare multiple sessions

4. **Real-time Alerts:**
   - Configurable alerts for AFR, knock, etc.
   - Audio notifications
   - Alert history

---

## Support

For issues or questions:
1. Check console logs for diagnostic information
2. Use channel discovery endpoint to debug naming issues
3. Verify hardware health endpoint shows connected
4. Review this guide's troubleshooting section

---

**Version:** 1.0.0  
**Last Updated:** 2025-12-15  
**Author:** DynoAI Development Team
