# Agent Prompts: JetDrive Real-Time Features Debugging

## 🎯 Purpose

Specific diagnostic and fix prompts for JetDrive-related real-time features including:
- Live data capture and display
- Auto-tune operations
- VE table updates
- Quick tune panel
- Session replay
- Hardware communication

---

## 🔍 Diagnostic Prompt: Live Data Not Updating

### Context
JetDrive live gauges/charts are not updating or showing stale data.

### Prompt

```
The JetDrive live data dashboard is not showing real-time updates from the dyno hardware.

Feature details:
- Component: frontend/src/components/jetdrive/JetDriveLiveDashboard.tsx
- Hook: frontend/src/hooks/useJetDriveLive.ts
- Backend: api/routes/jetdrive.py

Please investigate:

1. **Hardware Connection:**
   - Is the dyno hardware connected? Check `/api/jetdrive/hardware/monitor/status`
   - Is the monitor capturing data? Check `capturing: true` in status
   - Are channels being detected? Check `channel_count` in status
   - Is this simulated or real hardware? Check `simulated` flag

2. **Backend Data Flow:**
   - Is `/api/jetdrive/hardware/live/start` returning 200?
   - Is `/api/jetdrive/hardware/live/data` returning channel data?
   - Check the response structure - does it match expected format?
   - Are channel values changing over time?

3. **Frontend Hook (useJetDriveLive):**
   - Is `isCapturing` state true?
   - Is `pollLiveData()` being called every 50ms?
   - Are channels being updated in state?
   - Check console for "[useJetDriveLive]" debug logs

4. **Component Rendering:**
   - Is the component receiving updated channel data?
   - Are gauges/charts re-rendering on data change?
   - Check for any memo/useMemo that might prevent updates

5. **Channel Configuration:**
   - Are channel names matching JETDRIVE_CHANNEL_CONFIG?
   - Are fallback chan_X names being handled?
   - Check for typos in channel names

Please provide:
- Root cause of data not updating
- Specific code location
- Recommended fix
- Any channel mapping issues
```

---

## 🔧 Fix Prompt: Add Channel Name Mapping Debug

**Use when:** Channels are available but not displaying due to name mismatches

```
Add debug logging and flexible channel name mapping to handle various JetDrive channel naming conventions.

Requirements:

1. **Add channel name debug logging in useJetDriveLive.ts:**
```typescript
// In pollLiveData(), after receiving data
console.log('[useJetDriveLive] Raw channels:', Object.keys(data.channels));
console.log('[useJetDriveLive] Mapped channels:', Object.keys(newChannels));

// Log unmapped channels
const unmapped = Object.keys(data.channels).filter(
  name => !JETDRIVE_CHANNEL_CONFIG[name]
);
if (unmapped.length > 0) {
  console.warn('[useJetDriveLive] Unmapped channels:', unmapped);
}
```

2. **Add flexible channel name matching:**
```typescript
// Add to JETDRIVE_CHANNEL_CONFIG
function getChannelConfig(channelName: string) {
  // Try exact match first
  if (JETDRIVE_CHANNEL_CONFIG[channelName]) {
    return JETDRIVE_CHANNEL_CONFIG[channelName];
  }
  
  // Try case-insensitive match
  const lowerName = channelName.toLowerCase();
  for (const [key, config] of Object.entries(JETDRIVE_CHANNEL_CONFIG)) {
    if (key.toLowerCase() === lowerName) {
      return config;
    }
  }
  
  // Try partial match for common patterns
  if (lowerName.includes('rpm')) {
    return JETDRIVE_CHANNEL_CONFIG['RPM'];
  }
  if (lowerName.includes('afr') || lowerName.includes('air/fuel')) {
    return JETDRIVE_CHANNEL_CONFIG['AFR'];
  }
  if (lowerName.includes('force') || lowerName.includes('load')) {
    return JETDRIVE_CHANNEL_CONFIG['Force Drum 1'];
  }
  
  // Default fallback
  return {
    label: channelName,
    units: '',
    min: 0,
    max: 100,
    decimals: 2,
    color: '#888'
  };
}
```

3. **Add channel discovery endpoint:**
```python
@jetdrive_bp.route("/hardware/channels/discover", methods=["GET"])
def discover_channels():
    """
    Discover all available channels with their current values.
    Useful for debugging channel name mismatches.
    """
    try:
        data = get_live_data()
        
        channels = []
        for name, ch in data.get('channels', {}).items():
            channels.append({
                'id': ch.get('id'),
                'name': name,
                'value': ch.get('value'),
                'sample_values': get_recent_values(name, count=10),
                'value_range': get_value_range(name),
                'suggested_config': suggest_channel_config(name, ch)
            })
        
        return jsonify({
            'success': True,
            'channel_count': len(channels),
            'channels': channels
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

4. **Add "Discover Channels" button in frontend:**
```typescript
<Button onClick={async () => {
  const res = await fetch('/api/jetdrive/hardware/channels/discover');
  const data = await res.json();
  console.table(data.channels);
  toast.info(`Found ${data.channel_count} channels - check console`);
}}>
  Discover Channels
</Button>
```
```

---

## 🔍 Diagnostic Prompt: Quick Tune Not Auto-Detecting Runs

### Context
The Quick Tune Panel should auto-detect dyno runs based on RPM threshold but isn't triggering.

### Prompt

```
The Quick Tune Panel is not auto-detecting dyno runs even though the bike is running on the dyno.

Feature details:
- Component: frontend/src/components/jetdrive/QuickTunePanel.tsx
- Auto-detection logic: RPM threshold monitoring
- Expected: Auto-capture when RPM > 2000

Please investigate:

1. **RPM Data Availability:**
   - Is RPM channel data being received?
   - Check channel names: 'Digital RPM 1', 'Digital RPM 2', 'RPM', 'chan_42', 'chan_43'
   - What are the actual RPM values? (should be > 0 when engine running)
   - Is RPM data updating in real-time?

2. **Auto-Detection Logic:**
   - Is the auto-detection enabled? Check `autoDetectEnabled` state
   - Is the RPM threshold correct? (default: 2000)
   - Is the detection logic running? Check for useEffect with RPM monitoring
   - Are there any console logs for detection attempts?

3. **State Management:**
   - Is `isCapturing` from useJetDriveLive true?
   - Is the component mounted and active?
   - Are there any conditions preventing detection?

4. **Timing Issues:**
   - Is the poll interval too slow? (should be 50ms)
   - Is there a debounce that's too long?
   - Is detection only checked on mount vs continuously?

Please provide:
- Why auto-detection isn't triggering
- Specific code location
- Recommended fix
- Any threshold adjustments needed
```

---

## 🔧 Fix Prompt: Add Robust Auto-Detection Logic

**Use when:** Auto-detection is unreliable or not working

```
Implement robust auto-detection logic for dyno runs in the Quick Tune Panel.

Requirements:

1. **Add comprehensive RPM monitoring:**
```typescript
// In QuickTunePanel.tsx
const [rpmHistory, setRpmHistory] = useState<number[]>([]);
const [runDetected, setRunDetected] = useState(false);

// Get RPM from multiple possible channels
const getRPM = useCallback(() => {
  const rpmChannels = [
    'Digital RPM 1',
    'Digital RPM 2', 
    'RPM',
    'chan_42',
    'chan_43'
  ];
  
  for (const channel of rpmChannels) {
    const value = getChannelValue(channel);
    if (value !== null && value > 0) {
      return value;
    }
  }
  
  return 0;
}, [getChannelValue]);

// Monitor RPM continuously
useEffect(() => {
  if (!isCapturing || !autoDetectEnabled) return;
  
  const rpm = getRPM();
  
  // Update history (keep last 20 samples = 1 second at 50ms poll)
  setRpmHistory(prev => [...prev.slice(-19), rpm]);
  
  // Detection logic
  const avgRPM = rpmHistory.reduce((a, b) => a + b, 0) / rpmHistory.length;
  const threshold = 2000;
  
  // Detect run start: RPM crosses threshold going up
  if (!runDetected && avgRPM > threshold && rpmHistory.length >= 10) {
    console.log('[QuickTune] Run detected! Avg RPM:', avgRPM);
    setRunDetected(true);
    handleAutoCapture();
  }
  
  // Detect run end: RPM drops below threshold
  if (runDetected && avgRPM < threshold * 0.5) {
    console.log('[QuickTune] Run ended');
    setRunDetected(false);
  }
  
}, [isCapturing, autoDetectEnabled, rpmHistory, runDetected, getRPM]);

// Debug display
{process.env.NODE_ENV === 'development' && (
  <div className="text-xs text-muted-foreground">
    RPM: {getRPM().toFixed(0)} | Avg: {(rpmHistory.reduce((a,b) => a+b, 0) / rpmHistory.length).toFixed(0)}
    | Detected: {runDetected ? 'YES' : 'NO'}
  </div>
)}
```

2. **Add configurable detection parameters:**
```typescript
interface AutoDetectConfig {
  enabled: boolean;
  rpmThreshold: number;
  minDuration: number; // seconds
  cooldownPeriod: number; // seconds between runs
}

const [autoDetectConfig, setAutoDetectConfig] = useState<AutoDetectConfig>({
  enabled: true,
  rpmThreshold: 2000,
  minDuration: 3,
  cooldownPeriod: 5
});

// Settings UI
<div className="space-y-2">
  <Label>Auto-Detect Settings</Label>
  <div className="flex items-center gap-2">
    <Switch
      checked={autoDetectConfig.enabled}
      onCheckedChange={(enabled) => 
        setAutoDetectConfig(prev => ({ ...prev, enabled }))
      }
    />
    <span>Auto-detect runs</span>
  </div>
  <div className="flex items-center gap-2">
    <Label>RPM Threshold:</Label>
    <Input
      type="number"
      value={autoDetectConfig.rpmThreshold}
      onChange={(e) => 
        setAutoDetectConfig(prev => ({ 
          ...prev, 
          rpmThreshold: parseInt(e.target.value) 
        }))
      }
      className="w-24"
    />
  </div>
</div>
```

3. **Add visual feedback:**
```typescript
{runDetected && (
  <Alert className="border-green-500 bg-green-500/10">
    <Zap className="h-4 w-4 text-green-500 animate-pulse" />
    <AlertDescription>
      Dyno run detected! Auto-capture in progress...
    </AlertDescription>
  </Alert>
)}
```
```

---

## 🔍 Diagnostic Prompt: VE Table Not Updating in Real-Time

### Context
The Live VE Table should show real-time updates as the engine runs but cells aren't highlighting or updating.

### Prompt

```
The Live VE Table is not showing real-time cell updates during dyno runs.

Feature details:
- Component: frontend/src/components/jetdrive/LiveVETable.tsx
- Expected: Active cell highlights, value updates
- Observed: Static table, no updates

Please investigate:

1. **Data Flow:**
   - Is RPM data available? Check `getChannelValue('Digital RPM 1')`
   - Is MAP/TPS data available? (for cell lookup)
   - Are VE values being calculated/received?
   - Check console for "[LiveVETable]" logs

2. **Cell Lookup Logic:**
   - Is `getActiveCell()` function working?
   - Are RPM/MAP values within table range?
   - Is the table grid properly initialized?
   - Are row/column indices correct?

3. **Update Mechanism:**
   - Is the component re-rendering on data change?
   - Is the poll interval fast enough? (should be 50ms)
   - Are updates being throttled or debounced?
   - Is there a memo preventing updates?

4. **Visual Feedback:**
   - Are CSS classes being applied to active cells?
   - Is the highlight animation working?
   - Are colors showing correctly?

Please provide:
- Why VE table isn't updating
- Specific code location
- Recommended fix
- Any performance issues
```

---

## 🔧 Fix Prompt: Optimize Live VE Table Updates

**Use when:** VE table updates are slow or not visible

```
Optimize the Live VE Table component for smooth real-time updates.

Requirements:

1. **Add efficient cell tracking:**
```typescript
// In LiveVETable.tsx
const [activeCell, setActiveCell] = useState<{row: number, col: number} | null>(null);
const [cellHistory, setCellHistory] = useState<Map<string, number>>(new Map());

// Update active cell based on current RPM/MAP
useEffect(() => {
  if (!isCapturing) return;
  
  const rpm = getChannelValue('Digital RPM 1') || 0;
  const map = getChannelValue('MAP') || 0;
  
  if (rpm === 0 || map === 0) {
    setActiveCell(null);
    return;
  }
  
  // Find cell in VE table
  const rowIndex = findRowIndex(rpm, veTable.rpmBreakpoints);
  const colIndex = findColIndex(map, veTable.mapBreakpoints);
  
  if (rowIndex >= 0 && colIndex >= 0) {
    setActiveCell({ row: rowIndex, col: colIndex });
    
    // Track cell hit count
    const cellKey = `${rowIndex},${colIndex}`;
    setCellHistory(prev => {
      const newMap = new Map(prev);
      newMap.set(cellKey, (newMap.get(cellKey) || 0) + 1);
      return newMap;
    });
  }
  
}, [isCapturing, getChannelValue, veTable]);

// Helper functions
function findRowIndex(rpm: number, breakpoints: number[]): number {
  for (let i = 0; i < breakpoints.length - 1; i++) {
    if (rpm >= breakpoints[i] && rpm < breakpoints[i + 1]) {
      return i;
    }
  }
  return breakpoints.length - 1;
}

function findColIndex(map: number, breakpoints: number[]): number {
  for (let i = 0; i < breakpoints.length - 1; i++) {
    if (map >= breakpoints[i] && map < breakpoints[i + 1]) {
      return i;
    }
  }
  return breakpoints.length - 1;
}
```

2. **Add visual cell highlighting:**
```typescript
// Cell rendering with active highlight
function renderCell(value: number, rowIdx: number, colIdx: number) {
  const isActive = activeCell?.row === rowIdx && activeCell?.col === colIdx;
  const hitCount = cellHistory.get(`${rowIdx},${colIdx}`) || 0;
  const opacity = Math.min(hitCount / 100, 1); // Fade in based on hits
  
  return (
    <div
      className={cn(
        "p-2 text-center transition-all duration-100",
        isActive && "ring-2 ring-cyan-500 bg-cyan-500/20 scale-105",
        hitCount > 0 && "bg-green-500/10"
      )}
      style={{
        backgroundColor: hitCount > 0 
          ? `rgba(34, 197, 94, ${opacity * 0.2})` 
          : undefined
      }}
    >
      {value.toFixed(1)}
      {hitCount > 10 && (
        <div className="text-xs text-green-500">
          {hitCount}
        </div>
      )}
    </div>
  );
}
```

3. **Add performance monitoring:**
```typescript
const [updateStats, setUpdateStats] = useState({
  updatesPerSec: 0,
  lastUpdate: Date.now()
});

useEffect(() => {
  const interval = setInterval(() => {
    const now = Date.now();
    const elapsed = (now - updateStats.lastUpdate) / 1000;
    const updates = cellHistory.size;
    
    setUpdateStats({
      updatesPerSec: updates / elapsed,
      lastUpdate: now
    });
  }, 1000);
  
  return () => clearInterval(interval);
}, [cellHistory, updateStats.lastUpdate]);

// Display stats
<div className="text-xs text-muted-foreground">
  {updateStats.updatesPerSec.toFixed(1)} updates/s | 
  {cellHistory.size} cells hit
</div>
```

4. **Add "Clear History" button:**
```typescript
<Button
  variant="outline"
  size="sm"
  onClick={() => {
    setCellHistory(new Map());
    toast.success('Cell history cleared');
  }}
>
  Clear History
</Button>
```
```

---

## 🔍 Diagnostic Prompt: Session Replay Not Playing Back

### Context
Session replay feature should play back recorded dyno sessions but isn't working.

### Prompt

```
The Session Replay feature is not playing back recorded sessions.

Feature details:
- Component: frontend/src/components/jetdrive/SessionReplayPanel.tsx
- Backend: api/routes/jetdrive.py (replay endpoints)
- Expected: Smooth playback of recorded data

Please investigate:

1. **Session Loading:**
   - Are sessions being listed? Check `/api/jetdrive/sessions`
   - Can a session be loaded? Check `/api/jetdrive/sessions/<id>`
   - Is session data in correct format?
   - Are all required fields present?

2. **Playback Mechanism:**
   - Is the playback timer running?
   - Is `currentTime` state updating?
   - Are data points being interpolated correctly?
   - Is playback speed being applied?

3. **Data Interpolation:**
   - Are timestamps in the data?
   - Is interpolation logic working?
   - Are there gaps in the data?
   - Is the playback position correct?

4. **UI Updates:**
   - Are gauges updating during playback?
   - Are charts showing historical data?
   - Is the progress bar moving?
   - Are controls (play/pause/seek) working?

Please provide:
- Why playback isn't working
- Specific code location
- Recommended fix
- Any data format issues
```

---

## 🔧 Fix Prompt: Implement Smooth Session Replay

**Use when:** Session replay is choppy or not working

```
Implement smooth session replay with proper interpolation and controls.

Requirements:

1. **Add playback state management:**
```typescript
interface PlaybackState {
  isPlaying: boolean;
  currentTime: number; // seconds from start
  playbackSpeed: number; // 1.0 = normal, 2.0 = 2x, etc.
  duration: number; // total session duration
  sessionData: DataPoint[];
}

const [playback, setPlayback] = useState<PlaybackState>({
  isPlaying: false,
  currentTime: 0,
  playbackSpeed: 1.0,
  duration: 0,
  sessionData: []
});

// Load session
const loadSession = async (sessionId: string) => {
  const res = await fetch(`/api/jetdrive/sessions/${sessionId}`);
  const data = await res.json();
  
  const duration = data.duration_sec || calculateDuration(data.data_points);
  
  setPlayback({
    isPlaying: false,
    currentTime: 0,
    playbackSpeed: 1.0,
    duration,
    sessionData: data.data_points
  });
};
```

2. **Add smooth playback loop:**
```typescript
// Playback effect
useEffect(() => {
  if (!playback.isPlaying) return;
  
  const startTime = Date.now();
  const startPosition = playback.currentTime;
  
  const interval = setInterval(() => {
    const elapsed = (Date.now() - startTime) / 1000;
    const newTime = startPosition + (elapsed * playback.playbackSpeed);
    
    if (newTime >= playback.duration) {
      // End of session
      setPlayback(prev => ({ ...prev, isPlaying: false, currentTime: prev.duration }));
      return;
    }
    
    setPlayback(prev => ({ ...prev, currentTime: newTime }));
    
  }, 16); // ~60 FPS
  
  return () => clearInterval(interval);
}, [playback.isPlaying, playback.duration, playback.playbackSpeed]);
```

3. **Add data interpolation:**
```typescript
// Get interpolated data at current time
const getCurrentData = useCallback(() => {
  if (playback.sessionData.length === 0) return null;
  
  const time = playback.currentTime;
  
  // Find surrounding data points
  let before: DataPoint | null = null;
  let after: DataPoint | null = null;
  
  for (let i = 0; i < playback.sessionData.length; i++) {
    const point = playback.sessionData[i];
    if (point.timestamp <= time) {
      before = point;
    } else {
      after = point;
      break;
    }
  }
  
  if (!before) return playback.sessionData[0];
  if (!after) return playback.sessionData[playback.sessionData.length - 1];
  
  // Linear interpolation
  const t = (time - before.timestamp) / (after.timestamp - before.timestamp);
  
  const interpolated: Record<string, number> = {};
  for (const key of Object.keys(before.channels)) {
    const v1 = before.channels[key];
    const v2 = after.channels[key];
    interpolated[key] = v1 + (v2 - v1) * t;
  }
  
  return { timestamp: time, channels: interpolated };
}, [playback.currentTime, playback.sessionData]);

// Update gauges with interpolated data
useEffect(() => {
  const data = getCurrentData();
  if (data) {
    updateGauges(data.channels);
  }
}, [getCurrentData]);
```

4. **Add playback controls:**
```typescript
<div className="flex items-center gap-2">
  {/* Play/Pause */}
  <Button
    onClick={() => setPlayback(prev => ({ ...prev, isPlaying: !prev.isPlaying }))}
  >
    {playback.isPlaying ? <Pause /> : <Play />}
  </Button>
  
  {/* Speed control */}
  <Select
    value={playback.playbackSpeed.toString()}
    onValueChange={(value) => 
      setPlayback(prev => ({ ...prev, playbackSpeed: parseFloat(value) }))
    }
  >
    <SelectTrigger className="w-24">
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="0.5">0.5x</SelectItem>
      <SelectItem value="1">1x</SelectItem>
      <SelectItem value="2">2x</SelectItem>
      <SelectItem value="4">4x</SelectItem>
    </SelectContent>
  </Select>
  
  {/* Progress bar */}
  <Slider
    value={[playback.currentTime]}
    max={playback.duration}
    step={0.1}
    onValueChange={([value]) => 
      setPlayback(prev => ({ ...prev, currentTime: value }))
    }
    className="flex-1"
  />
  
  {/* Time display */}
  <span className="text-sm text-muted-foreground">
    {formatTime(playback.currentTime)} / {formatTime(playback.duration)}
  </span>
</div>

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
```
```

---

## 🔍 Diagnostic Prompt: Hardware Communication Timeout

### Context
Communication with JetDrive hardware is timing out or failing intermittently.

### Prompt

```
The system is experiencing timeouts or failures when communicating with JetDrive hardware.

Feature details:
- Hardware: Dynojet Dynoware RT (192.168.1.115)
- Protocol: Power Core JetDrive (UDP multicast port 22344)
- Backend: api/routes/jetdrive.py

Please investigate:

1. **Network Connectivity:**
   - Can the backend reach 192.168.1.115?
   - Is port 22344 accessible?
   - Are there any firewall rules blocking UDP?
   - Is multicast working on the network?

2. **Protocol Implementation:**
   - Is the JetDrive protocol implementation correct?
   - Are packets being sent/received?
   - Is the packet format correct?
   - Are checksums/validation passing?

3. **Timeout Configuration:**
   - What is the current timeout value?
   - Is it too short for the network?
   - Are retries configured?
   - Is there exponential backoff?

4. **Error Handling:**
   - What error messages are being logged?
   - Are timeouts being caught and handled?
   - Is the connection being re-established?
   - Are there any resource leaks?

Please provide:
- Root cause of timeouts
- Network configuration issues
- Recommended timeout values
- Retry strategy
```

---

## 🔧 Fix Prompt: Add Robust Hardware Communication

**Use when:** Hardware communication is unreliable

```
Implement robust hardware communication with proper timeout handling and retries.

Requirements:

1. **Add connection manager with retries:**
```python
import socket
import time
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class JetDriveConnection:
    def __init__(
        self,
        host: str = "192.168.1.115",
        port: int = 22344,
        timeout: float = 2.0,
        max_retries: int = 3
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_retries = max_retries
        self.socket: Optional[socket.socket] = None
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to JetDrive hardware with retries"""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Connecting to {self.host}:{self.port} (attempt {attempt + 1}/{self.max_retries})")
                
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.socket.settimeout(self.timeout)
                
                # Test connection with ping packet
                self.send_ping()
                response = self.socket.recv(1024)
                
                if response:
                    self.connected = True
                    logger.info("Connected to JetDrive hardware")
                    return True
                
            except socket.timeout:
                logger.warning(f"Connection timeout (attempt {attempt + 1})")
                time.sleep(1 * (attempt + 1))  # Exponential backoff
                
            except Exception as e:
                logger.error(f"Connection error: {e}")
                time.sleep(1)
        
        logger.error("Failed to connect after all retries")
        return False
    
    def send_with_retry(self, data: bytes) -> Optional[bytes]:
        """Send data with automatic retry on failure"""
        for attempt in range(self.max_retries):
            try:
                self.socket.send(data)
                response = self.socket.recv(4096)
                return response
                
            except socket.timeout:
                logger.warning(f"Send timeout (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    time.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"Send error: {e}")
                # Try to reconnect
                self.connected = False
                if self.connect():
                    continue
                break
        
        return None
    
    def close(self):
        """Close connection"""
        if self.socket:
            self.socket.close()
        self.connected = False

# Global connection instance
_connection: Optional[JetDriveConnection] = None

def get_connection() -> JetDriveConnection:
    global _connection
    if _connection is None or not _connection.connected:
        _connection = JetDriveConnection()
        _connection.connect()
    return _connection
```

2. **Add health monitoring:**
```python
@jetdrive_bp.route("/hardware/health", methods=["GET"])
def check_hardware_health():
    """Check hardware connection health"""
    try:
        conn = get_connection()
        
        # Send ping
        start = time.time()
        response = conn.send_with_retry(b"PING")
        latency = (time.time() - start) * 1000  # ms
        
        if response:
            return jsonify({
                "healthy": True,
                "connected": True,
                "latency_ms": latency,
                "host": conn.host,
                "port": conn.port
            })
        else:
            return jsonify({
                "healthy": False,
                "connected": False,
                "error": "No response from hardware"
            }), 503
            
    except Exception as e:
        return jsonify({
            "healthy": False,
            "connected": False,
            "error": str(e)
        }), 503
```

3. **Add frontend connection monitor:**
```typescript
const { data: health } = useQuery({
  queryKey: ['jetdrive-health'],
  queryFn: async () => {
    const res = await fetch('/api/jetdrive/hardware/health');
    return res.json();
  },
  refetchInterval: 5000, // Check every 5 seconds
});

// Display connection status
<div className="flex items-center gap-2">
  <div className={cn(
    "h-2 w-2 rounded-full",
    health?.healthy ? "bg-green-500 animate-pulse" : "bg-red-500"
  )} />
  <span className="text-sm">
    {health?.healthy 
      ? `Connected (${health.latency_ms.toFixed(0)}ms)` 
      : 'Disconnected'}
  </span>
</div>
```
```

---

## 📋 Quick Reference: JetDrive Issues

| Issue | Diagnostic Prompt | Fix Prompt |
|-------|-------------------|-----------|
| Live data not updating | Live Data Not Updating | Channel Name Mapping Debug |
| Auto-detect not working | Quick Tune Not Auto-Detecting | Robust Auto-Detection Logic |
| VE table not updating | VE Table Not Updating | Optimize Live VE Table |
| Replay not working | Session Replay Not Playing | Implement Smooth Replay |
| Hardware timeouts | Hardware Communication Timeout | Robust Hardware Communication |

---

## 🎯 JetDrive Feature Testing Checklist

- [ ] Hardware connection established
- [ ] Live data updates at 20 Hz (50ms interval)
- [ ] All channels mapped correctly
- [ ] Gauges display real-time values
- [ ] Charts scroll smoothly
- [ ] Auto-detect triggers on RPM threshold
- [ ] Quick tune captures and analyzes
- [ ] VE table highlights active cells
- [ ] Session replay plays smoothly
- [ ] Controls (play/pause/seek) work
- [ ] Connection survives network hiccups
- [ ] Timeouts handled gracefully
- [ ] Error messages are clear
- [ ] Performance is smooth (no lag)

---

## 💡 JetDrive-Specific Best Practices

1. **Always check for multiple channel name variants:**
   ```typescript
   const rpm = getChannelValue('Digital RPM 1') 
     || getChannelValue('RPM') 
     || getChannelValue('chan_42') 
     || 0;
   ```

2. **Use fast poll intervals for real-time feel:**
   ```typescript
   pollInterval: 50, // 50ms = 20 Hz
   ```

3. **Implement fallback for missing channels:**
   ```typescript
   const config = JETDRIVE_CHANNEL_CONFIG[name] || DEFAULT_CONFIG;
   ```

4. **Add visual feedback for active operations:**
   ```typescript
   {isCapturing && <Badge>LIVE</Badge>}
   ```

5. **Log channel discovery for debugging:**
   ```typescript
   console.log('[JetDrive] Available channels:', Object.keys(channels));
   ```

---

This document provides comprehensive prompts for debugging and fixing all JetDrive real-time features. Use in combination with the general async patterns document for complete coverage.

