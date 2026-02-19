# JetDrive WiFi Quick Start

**Your Setup:**
- PC WiFi IP: `192.168.1.81`
- Dynoware RT IP: `192.168.1.115`
- Connection: WiFi (same subnet)

## Why Not Docker?

Docker Desktop on Windows **cannot handle UDP multicast** needed for JetDrive discovery. You must run the API **natively** (local Python) while the Dynoware RT is connected.

## Quick Start

### 1. Stop Docker API (keep frontend/redis running)

```powershell
docker compose stop api
```

### 2. Start Native API with JetDrive

```powershell
.\start-jetdrive.ps1 -DynoIP 192.168.1.115
```

This will:
- ✅ Create/activate virtual environment
- ✅ Install dependencies
- ✅ Set `JETDRIVE_IFACE=192.168.1.81` (your WiFi IP)
- ✅ Set `DYNO_IP=192.168.1.115` (Dynoware RT)
- ✅ Start API on http://localhost:5001
- ✅ Start frontend on http://localhost:5173

### 3. Open the App

- **Frontend:** http://localhost:5173 (Vite dev server)
- **API:** http://localhost:5001
- **JetDrive Live:** http://localhost:5173/jetdrive-live

### 4. Connect to Dynoware RT

1. Open **Dyno Connect** in your Dynoware software
2. Select the RT-150 at `192.168.1.115`
3. Click **Connect** and enable "Automatically connect next time"
4. In DynoAI web UI, go to JetDrive Live Dashboard
5. Click "Start Monitoring" - you should see live data

## Troubleshooting

### No providers found?

```powershell
# Test discovery
python scripts/jetdrive_hardware_test.py --discover

# Run diagnostics
python scripts/jetdrive_hardware_test.py --diagnose
```

### Check multicast binding

```powershell
netstat -an | Select-String "22344"
```

You should see `0.0.0.0:22344` or `192.168.1.81:22344`.

### Firewall blocking?

Windows Firewall may block UDP multicast. Add rule:
- **Protocol:** UDP
- **Port:** 22344
- **Direction:** Inbound
- **Action:** Allow

## Switching Back to Docker (non-JetDrive)

When not using live dyno data:

```powershell
# Stop native API
# (Ctrl+C in the terminal running start-jetdrive.ps1)

# Start Docker API
docker compose start api

# Access at http://localhost:80
```

## Environment Variables

Your `.env` already has:
```env
JETDRIVE_IFACE=192.168.1.81
DYNO_IP=192.168.1.115
```

The `start-jetdrive.ps1` script automatically sets these when running natively.
