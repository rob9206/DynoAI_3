# JetDrive Hardware Testing Options

## Current Status

✅ **Backend is running**: `http://localhost:5001`  
✅ **Hardware diagnostics**: All systems operational  
⚠️ **No providers found**: This is normal without physical hardware

## What "No Providers Found" Means

The JetDrive discovery system is working correctly, but it's not detecting any Dynojet Power Core devices on your network (`192.168.1.160`). This happens when:

1. No physical dyno hardware is connected to your network
2. The hardware is powered off or on a different network segment
3. Firewall is blocking multicast UDP traffic on port 22344

## Testing Options

### Option 1: Connect Physical Hardware

If you have a **Dynojet Power Core** with JetDrive capability:

1. **Ensure it's on the same network** as your computer (192.168.1.x)
2. **Power on the device** and wait for it to boot up
3. **Click "Discover"** button in the UI to scan for providers
4. **Check firewall settings** if nothing appears:
   - Allow UDP port 22344
   - Allow multicast group 224.0.2.10

### Option 2: Use Stub Mode (Testing Without Hardware)

For development and testing without physical hardware, use Jetstream stub mode with sample data:

#### Quick Start - Stub Mode

**Stop the current backend** first, then run:

```powershell
# Stop current backend
Get-Process python | Where-Object {$_.Id -eq <BACKEND_PID>} | Stop-Process

# Start in stub mode
cd C:\Dev\DynoAI_3
.\start-stub-mode.ps1
```

This will:
- Start backend on port 5100 with sample Jetstream data
- Show 3 demo runs (complete, processing, error states)
- Let you test the UI without hardware

### Option 3: Upload CSV Data

You can test the dyno analysis features by uploading CSV log files:

1. Navigate to **Control Center** in the UI
2. Click **Upload Log** 
3. Select a CSV file from:
   - Previous dyno runs
   - Sample data from `experiments/` folder
   - Your own Power Vision or JetDrive logs

The system will analyze the data and generate VE corrections without needing live hardware.

### Option 4: Use Simulated Dyno Run

The system can generate synthetic dyno data for testing:

```powershell
cd C:\Dev\DynoAI_3
.\.venv\Scripts\python.exe scripts\jetdrive_autotune.py --run-id test_sim_001 --simulate
```

This creates a simulated dyno run in the `runs/test_sim_001/` directory.

## Network Troubleshooting

If you have hardware but it's not being detected:

### Check Network Connectivity

```powershell
# Check your IP is on the right subnet
ipconfig | findstr "IPv4"

# Verify multicast is working
Test-NetConnection -ComputerName 224.0.2.10 -Port 22344
```

### Check Firewall Rules

```powershell
# Add firewall rule for multicast (if needed)
New-NetFirewallRule -DisplayName "JetDrive Discovery" -Direction Inbound -Protocol UDP -LocalPort 22344 -Action Allow
```

### Enable Network Discovery

On Windows:
1. Open **Network and Sharing Center**
2. Click **Change advanced sharing settings**
3. Enable **Network discovery**
4. Enable **File and printer sharing**

## Current System Configuration

- **Network Interface**: 192.168.1.160
- **Multicast Group**: 224.0.2.10
- **Discovery Port**: 22344
- **Backend API**: http://localhost:5001
- **Frontend UI**: http://localhost:5000

## Environment Variables (Advanced)

You can customize the discovery settings:

```powershell
# Change multicast group
$env:JETDRIVE_MCAST_GROUP = "224.0.2.10"

# Change port
$env:JETDRIVE_PORT = "22344"

# Bind to specific interface
$env:JETDRIVE_IFACE = "192.168.1.160"
```

## Next Steps

1. **If you have hardware**: Check that it's powered on and on the same network
2. **If testing without hardware**: Use `.\start-stub-mode.ps1` for demo data
3. **If analyzing logs**: Use the Upload feature in Control Center

Need help? The system is working correctly - you just need to either connect hardware or use test data!

