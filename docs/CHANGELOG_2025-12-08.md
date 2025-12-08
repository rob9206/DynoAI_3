# DynoAI Changes - December 8, 2025

## Overview
Added Power Core LiveLink integration for real-time data streaming from Dynojet dynos, plus several bug fixes.

---

## New Features

### 🔴 LiveLink Real-Time Dashboard
Real-time data streaming from Dynojet Power Core to the DynoAI frontend.

**Components Added:**
- `api/services/livelink_client.py` - WCF/simulation client for Power Core
- `api/services/livelink_websocket.py` - WebSocket server for streaming
- `frontend/src/pages/LiveLinkPage.tsx` - Dashboard UI
- `frontend/src/components/livelink/` - Gauges, charts, status components
- `frontend/src/hooks/useLiveLink.ts` - React hook for WebSocket

**How to Use:**
```powershell
# Start WebSocket server (simulation mode for testing)
python scripts/start-livelink-ws.py --port 5003 --mode simulation

# Start with real Power Core data (when dyno connected)
python scripts/start-livelink-ws.py --port 5003 --mode wcf
```

Then navigate to: http://localhost:5000/livelink

**Supported Channels:**
- Engine RPM
- AFR Front/Rear
- TPS (Throttle Position)
- MAP (Manifold Absolute Pressure)
- More channels available when connected to real dyno

---

### 🚀 Startup Scripts
Prevents port conflicts by starting backend before frontend.

**PowerShell (Recommended):**
```powershell
.\scripts\start-dev.ps1              # Start backend + frontend
.\scripts\start-dev.ps1 -WithLiveLink # Also start LiveLink server
.\scripts\start-dev.ps1 -BackendOnly  # Backend only
```

**Batch File:**
```cmd
scripts\start-dev.bat
```

---

### 🔧 Power Core Integration Services

**File Parsing:**
- `api/services/powercore_integration.py` - Parse PVV tune files and Power Vision CSVs
- `api/services/wp8_parser.py` - Parse WinPEP8 binary run files
- `api/services/autotune_workflow.py` - Auto-tune VE correction workflow

**JETDRIVE Discovery:**
- `scripts/jetdrive_discover.py` - Scan for JETDRIVE UDP multicast broadcasts

---

## Bug Fixes

### 🐛 Download Endpoint (500 Error)
**Problem:** Downloads failed with "Internal Server Error" for both Jetstream and direct upload runs.

**Root Causes:**
1. `/api/download` only checked `outputs/` folder, not `runs/` folder (Jetstream)
2. `OUTPUT_FOLDER` used relative path that resolved to `api/outputs/` instead of project root

**Fix:**
- Download endpoint now checks `runs/` folder first (via run_manager), then `outputs/`
- Changed to absolute paths: `PROJECT_ROOT / "outputs"`

---

## Files Changed

### New Files
```
api/services/livelink_client.py
api/services/livelink_websocket.py
api/services/powercore_integration.py
api/services/wp8_parser.py
api/services/autotune_workflow.py
api/services/agent_orchestrator.py
api/services/livelink_bridge.ps1
api/routes/powercore.py

frontend/src/pages/LiveLinkPage.tsx
frontend/src/components/livelink/LiveLinkStatus.tsx
frontend/src/components/livelink/LiveLinkGauge.tsx
frontend/src/components/livelink/LiveLinkChart.tsx
frontend/src/components/livelink/LiveLinkPanel.tsx
frontend/src/components/livelink/index.ts
frontend/src/hooks/useLiveLink.ts
frontend/livelink-test.html

scripts/start-dev.ps1
scripts/start-dev.bat
scripts/start-livelink-ws.py
scripts/jetdrive_discover.py

tests/test_livelink_client.py
tests/test_autotune_workflow.py
tests/test_agent_orchestrator.py
```

### Modified Files
```
api/app.py                    # Fixed paths, added download fallback
api/requirements.txt          # Added flask-socketio, eventlet
frontend/package.json         # Added socket.io-client
frontend/src/App.tsx          # Added /livelink route
frontend/src/components/Layout.tsx  # Added LiveLink nav link
frontend/src/pages/RunDetailPage.tsx  # Added download toast notifications
```

---

## Git Branch
All changes on: `feature/livelink-integration`

**Pull Request:** https://github.com/rob9206/DynoAI_3/pull/43

---

## Next Steps (When Dyno Connected)

1. Start Power Core on the dyno PC
2. Run LiveLink in WCF mode:
   ```powershell
   python scripts/start-livelink-ws.py --port 5003 --mode wcf
   ```
3. Open http://localhost:5000/livelink
4. Click "Connect" to start streaming real data

**Alternative - JETDRIVE Protocol:**
If Power Core broadcasts via JETDRIVE (UDP multicast):
```powershell
python scripts/jetdrive_discover.py
```
This will scan for the broadcast address/port.

---

## Service Ports

| Service | Port | URL |
|---------|------|-----|
| Backend API | 5001 | http://localhost:5001 |
| Frontend | 5000 | http://localhost:5000 |
| LiveLink WS | 5003 | ws://localhost:5003/livelink |

