# JetDrive Real-Time Features Debugging Guide

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
