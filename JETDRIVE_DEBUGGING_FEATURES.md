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
This document describes the debugging and robustness features implemented for JetDrive real-time data capture and analysis.

## 🎯 Overview

The following debugging features have been implemented to help diagnose and fix common JetDrive issues:

1. **Channel Discovery & Flexible Mapping** - Automatically detect and map channels with intelligent fallbacks
2. **Auto-Detection for Dyno Runs** - Automatically capture data when RPM exceeds threshold
3. **Performance Monitoring** - Track VE table update rates and performance
4. **Hardware Health Monitoring** - Monitor connection status and latency
5. **Debug Logging** - Comprehensive console logging for troubleshooting

---

## 📋 Features Implemented

### 1. Channel Discovery & Flexible Mapping

#### Backend: `/api/jetdrive/hardware/channels/discover`

**Purpose:** Discover all available channels and suggest appropriate configurations.

**Response Format:**
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
      "value": 2450.0,
      "suggested_units": "rpm",
      "suggested_type": "Engine Speed",
      "suggested_label": "Digital RPM 1"
    },
    {
      "id": 23,
      "name": "chan_23",
      "value": 13.2,
      "suggested_units": ":1",
      "suggested_type": "Air/Fuel Ratio",
      "suggested_label": "Channel 23"
    }
  ]
}
```

**Frontend Usage:**
- Click the **Search** icon button in the Live Dashboard
- Console displays a table of all discovered channels
- Toast notification confirms discovery
- Use this to debug channel name mismatches

**Implementation Details:**
- Located in: `api/routes/jetdrive.py`
- Intelligently detects channel types based on value ranges and names
- Works with both simulated and real hardware
- Suggests appropriate units and labels

#### Flexible Channel Mapping Function

**Location:** `frontend/src/hooks/useJetDriveLive.ts`

**Function:** `getChannelConfig(channelName: string)`

**Features:**
- Exact name matching first
- Case-insensitive fallback
- Pattern-based partial matching (e.g., "rpm" → RPM config)
- Graceful fallback for unknown channels
- Null-safe with default configs

**Supported Pattern Matches:**
- `rpm` → RPM configuration
- `afr`, `air/fuel` → AFR configuration
- `force`, `load` → Force configuration
- `map`, `manifold` → MAP configuration
- `tps`, `throttle` → TPS configuration
- `horsepower`, `hp` → Horsepower configuration
- `torque`, `tq` → Torque configuration

**Debug Logging:**
```typescript
// Development mode only
console.log('[useJetDriveLive] Raw channels:', Object.keys(channels));
console.log('[useJetDriveLive] Mapped channels:', Object.keys(newChannels));
console.warn('[useJetDriveLive] Unmapped channels:', unmappedChannels);
```

---

### 2. Auto-Detection for Dyno Runs

#### Location: `frontend/src/components/jetdrive/QuickTunePanel.tsx`

**Purpose:** Automatically detect and capture dyno runs based on RPM threshold.

**Features:**
- Multi-channel RPM detection (Digital RPM 1, RPM, chan_42, chan_43)
- Configurable RPM threshold (default: 2000 RPM)
- Configurable cooldown period between runs (default: 5 seconds)
- Visual feedback with alerts
- Development mode debug display

**Configuration UI:**
```typescript
interface AutoDetectConfig {
  enabled: boolean;           // Master enable/disable
  rpmThreshold: number;       // RPM to trigger detection (default: 2000)
  minDuration: number;        // Minimum run duration in seconds (default: 3)
  cooldownPeriod: number;     // Time between runs in seconds (default: 5)
}
```

**How It Works:**
1. Monitors RPM from multiple possible channels
2. Maintains 1-second rolling average (20 samples at 50ms poll)
3. Detects run start when average RPM > threshold
4. Detects run end when average RPM < threshold * 0.5
5. Enforces cooldown period to prevent multiple triggers
6. Shows visual alert during detected runs

**Debug Display (Dev Mode):**
```
RPM: 2450 | Avg: 2398 | Detected: YES
```

**Visual Feedback:**
- Green alert box with pulsing icon during run
- Toast notifications for run start/end
- Real-time RPM display in settings panel

---

### 3. Performance Monitoring

#### Location: `frontend/src/components/jetdrive/LiveVETable.tsx`

**Purpose:** Track and display VE table update performance.

**Metrics Tracked:**
- Updates per second
- Total update count
- Hit counts per cell
- Active cells

**Display:**
```
[LIVE] [X hits] [Y.Z updates/s] [Reset]
```

**Implementation:**
- Tracks cell updates in real-time
- Calculates update rate every second
- Displays as badge in VE table header
- Resets with "Reset" button

**Code Example:**
```typescript
const [updateStats, setUpdateStats] = useState({
  updatesPerSec: 0,
  lastUpdate: Date.now(),
  updateCount: 0,
});

// Update tracking
setUpdateStats(prev => ({
  ...prev,
  updateCount: prev.updateCount + 1,
}));

// Calculate rate every second
useEffect(() => {
  const interval = setInterval(() => {
    const elapsed = (now - lastUpdate) / 1000;
    const updatesPerSec = updateCount / elapsed;
    // Reset counter
  }, 1000);
}, []);
```

---

### 4. Hardware Health Monitoring

#### Backend: `/api/jetdrive/hardware/health`

**Purpose:** Monitor connection health and latency.

**Response Format:**
```json
{
  "healthy": true,
  "connected": true,
  "simulated": false,
  "capturing": true,
  "latency_ms": 12.5,
  "channel_count": 45
}
```

**Frontend Usage:**
- Automatic polling every 5 seconds
- Displayed in Live Dashboard header
- Shows connection status with indicator dot
- Displays latency in milliseconds
- Shows "SIMULATED" badge when using simulator

**Status Indicators:**
- 🟢 Green pulsing dot = Connected
- 🔴 Red dot = Disconnected
- Latency displayed in parentheses (e.g., "12ms")
- Yellow "SIMULATED" badge when using simulator

**Implementation:**
```typescript
const { data: health } = useQuery({
  queryKey: ['jetdrive-health', apiUrl],
  queryFn: async () => {
    const res = await fetch(`${apiUrl}/hardware/health`);
    return res.json();
  },
  refetchInterval: 5000,
  retry: false,
});
```

---

### 5. Debug Logging

#### Console Logging Locations

**useJetDriveLive Hook:**
```javascript
// Channel mapping (development only)
'[useJetDriveLive] Raw channels: [...channels]'
'[useJetDriveLive] Mapped channels: [...mapped]'
'[useJetDriveLive] Unmapped channels (using fallback): [...unmapped]'
```

**QuickTunePanel:**
```javascript
'[QuickTune] Run detected! Avg RPM: 2450'
'[QuickTune] Run ended'
```

**LiveVETable:**
- Cell hit tracking logged in real-time
- Performance stats updated every second
- Active cell position tracked

---

## 🔧 Usage Examples

### Example 1: Debug Channel Name Mismatch

**Problem:** AFR gauge not showing data

**Solution:**
1. Click Search icon in Live Dashboard
2. Check console for channel names
3. Look for AFR-related channels
4. Verify channel name in `JETDRIVE_CHANNEL_CONFIG`
5. If missing, flexible mapping will provide fallback

**Console Output:**
```
Found 45 channels - check console
┌─────────┬──────────────────┬─────────┬──────────────┬─────────────────────┐
│ (index) │      name        │  value  │ suggested... │  suggested_type     │
├─────────┼──────────────────┼─────────┼──────────────┼─────────────────────┤
│    0    │ 'chan_23'        │  13.2   │    ':1'      │ 'Air/Fuel Ratio'    │
└─────────┴──────────────────┴─────────┴──────────────┴─────────────────────┘
```

### Example 2: Monitor Auto-Detection

**Problem:** Runs not being auto-detected

**Solution:**
1. Enable auto-detection in Quick Tune Panel
2. Verify RPM threshold is appropriate (default: 2000)
3. Open browser console (F12)
4. Watch for detection logs during dyno pulls

**Console Output:**
```
[QuickTune] Run detected! Avg RPM: 2450
[Toast] Dyno run detected! RPM above 2000 - Auto-capture started
... (run in progress) ...
[QuickTune] Run ended
[Toast] Dyno run completed
```

### Example 3: Check Connection Health

**Problem:** Intermittent disconnections

**Solution:**
1. Watch the connection indicator in dashboard header
2. Note the latency values
3. Check for "SIMULATED" badge if unexpected
4. High latency (>100ms) indicates network issues

**Visual Indicators:**
- 🟢 Connected (12ms) ← Good
- 🟢 Connected (250ms) ← Slow network
- 🔴 Disconnected ← Connection lost

---

## 🎯 Troubleshooting Guide

### Issue: Live Data Not Updating

**Diagnostic Steps:**
1. Check connection indicator (should be green and pulsing)
2. Verify "LIVE" badge is showing
3. Click Discover Channels to verify data flow
4. Check console for `[useJetDriveLive]` logs
5. Verify poll interval is 50ms for responsive updates

**Common Causes:**
- Hardware not started (click "Start Monitor")
- Live capture not started (click "Start Live Capture")
- Network issues (check latency)
- Channel name mismatch (use Discover Channels)

### Issue: Auto-Detection Not Triggering

**Diagnostic Steps:**
1. Verify auto-detection is enabled (toggle switch)
2. Check RPM threshold is appropriate for bike
3. Enable development mode debug display
4. Verify RPM channel is being detected
5. Check cooldown period isn't too long

**Common Causes:**
- RPM threshold too high for bike
- RPM channel name mismatch
- Still in cooldown period from previous run
- RPM data not being received

### Issue: VE Table Not Updating

**Diagnostic Steps:**
1. Check "LIVE" badge is showing
2. Verify updates/s badge shows >0
3. Check that RPM and MAP are >0
4. Verify hit counts are incrementing
5. Check active cell highlighting

**Common Causes:**
- Not in live mode
- RPM or MAP data missing
- Operating point outside table range
- Polling too slow (should be 50ms)

### Issue: High Latency

**Diagnostic Steps:**
1. Check health monitor latency
2. If >100ms, check network connection
3. Verify not running over WiFi
4. Check for network congestion
5. Consider reducing poll interval

**Common Causes:**
- WiFi vs wired connection
- Network congestion
- Server overload
- Firewall/antivirus interference

---

## 🏁 Best Practices

### 1. Channel Naming
- Use descriptive names when possible
- Leverage flexible mapping for compatibility
- Document custom channel mappings
- Use Discover Channels to verify

### 2. Auto-Detection Settings
- Set RPM threshold ~500 below idle
- Use longer cooldown for multiple pulls
- Monitor debug output during testing
- Adjust based on bike characteristics

### 3. Performance Monitoring
- Watch updates/s during live sessions
- Target 10-20 updates/s for smooth updates
- Reset stats between sessions
- Monitor hit counts for coverage

### 4. Connection Health
- Monitor latency regularly
- Investigate if >50ms consistently
- Use wired connection for best results
- Enable SIMULATED mode for testing

### 5. Debug Logging
- Enable development mode for detailed logs
- Use Discover Channels before every session
- Check console for warnings
- Save logs when reporting issues

---

## 📊 API Reference

### Backend Endpoints

#### GET `/api/jetdrive/hardware/channels/discover`
Discover all available channels with suggested configurations.

**Response:** `{ success: boolean, channel_count: number, channels: Channel[] }`

#### GET `/api/jetdrive/hardware/health`
Check hardware connection health and latency.

**Response:** `{ healthy: boolean, connected: boolean, latency_ms: number, ... }`

#### GET `/api/jetdrive/hardware/live/data`
Get current live channel data (existing endpoint).

**Response:** `{ capturing: boolean, channels: {...}, ... }`

### Frontend Hooks

#### `useJetDriveLive(options)`
React hook for JetDrive live data.

**Options:**
```typescript
{
  apiUrl?: string;           // API base URL
  autoConnect?: boolean;     // Auto-start on mount
  pollInterval?: number;     // Poll interval in ms (default: 50)
  maxHistoryPoints?: number; // Max history (default: 300)
}
```

**Returns:**
```typescript
{
  isConnected: boolean;
  isCapturing: boolean;
  channels: Record<string, JetDriveChannel>;
  getChannelValue: (name: string) => number | null;
  startCapture: () => Promise<void>;
  stopCapture: () => Promise<void>;
  // ... more
}
```

#### `getChannelConfig(channelName)`
Get channel configuration with flexible matching.

**Returns:** `ChannelConfig` with label, units, min, max, decimals, color

---

## 🔍 Testing Checklist

- [ ] Hardware connection established
- [ ] Live data updates at 20 Hz (50ms interval)
- [ ] All channels mapped correctly
- [ ] Gauges display real-time values
- [ ] Charts scroll smoothly
- [ ] Auto-detect triggers on RPM threshold
- [ ] VE table highlights active cells
- [ ] Performance stats show updates/s
- [ ] Connection health displays latency
- [ ] Discovery tool lists all channels
- [ ] Debug logs appear in console
- [ ] Timeouts handled gracefully
- [ ] Error messages are clear
- [ ] UI remains responsive

---

## 📝 Notes

- All debug logging is development-mode only (`process.env.NODE_ENV === 'development'`)
- Channel discovery works with both real hardware and simulator
- Auto-detection uses rolling average to prevent false triggers
- Performance monitoring resets every second for accuracy
- Health checks run every 5 seconds automatically
- Flexible channel mapping prevents missing data due to name variations

---

## 🚀 Future Enhancements

Potential improvements not yet implemented:

1. **Session Replay**
   - Record dyno sessions for playback
   - Interpolate data for smooth replay
   - Add playback controls (play/pause/seek/speed)
   - Would require backend storage endpoints

2. **Advanced Connection Management**
   - Retry logic with exponential backoff
   - Automatic reconnection on disconnect
   - Connection quality indicators
   - Bandwidth optimization

3. **Enhanced Analytics**
   - Cell hit heatmaps
   - Coverage statistics
   - Session comparison
   - Export capabilities

4. **Configuration Persistence**
   - Save auto-detect settings
   - Save channel mappings
   - User preferences
   - Custom presets

---

For more information, see the main problem statement document or the inline code documentation.
