# JetDrive Hardware Testing Guide

This guide walks you through connecting DynoAI to a real Dynojet dyno via the JetDrive protocol.

## Prerequisites

### Hardware
- [ ] Dynojet dynamometer (Power Core compatible)
- [ ] Computer running DynoAI on the same network as the dyno
- [ ] Network cable (or verified WiFi connection)

### Software
- [ ] Dynojet Power Core installed and running
- [ ] DynoAI installed with dependencies (`pip install -r requirements.txt`)
- [ ] Python 3.9+

## Quick Start

### 1. Run Diagnostics

First, verify your system is ready for JetDrive:

```bash
python scripts/jetdrive_hardware_test.py --diagnose
```

Expected output:
```
[OK] Found 2 network interface(s)
[OK] 192.168.1.100: Multicast join successful
[OK] Port 22344 is available
```

### 2. Configure Power Core

In Dynojet Power Core:

1. **Open Settings** → **JetDrive Configuration**
2. **Enable JetDrive** checkbox
3. **Select Network Interface** - Choose the interface connected to your computer
4. **Configure Channels** - Enable these channels:
   - `RPM` (Engine Speed)
   - `Torque` (ft-lb or Nm)
   - `Power` (HP or kW)
   - `AFR` or `Lambda` (if available)
   - `TPS` (Throttle Position)
   - `MAP` or `Manifold Pressure` (if available)
   - `ECT` (Engine Coolant Temperature)
   - `IAT` (Intake Air Temperature)

5. **Apply** and **Save**

### 3. Discover Providers

With Power Core running and JetDrive enabled:

```bash
python scripts/jetdrive_hardware_test.py --discover
```

Expected output:
```
[OK] Found 1 provider(s)

Provider 1: PowerCore
   ID: 0x1234
   Host: 192.168.1.50:22344
   Channels (8):
      [  1] RPM                  (unit=8)
      [  2] Torque               (unit=5)
      [  3] Power                (unit=4)
      ...
```

### 4. Test Live Capture

Capture data during a short dyno pull:

```bash
python scripts/jetdrive_hardware_test.py --capture --duration 30
```

This will:
- Connect to the first discovered provider
- Capture 30 seconds of data
- Save to `runs/jetdrive_capture_YYYYMMDD_HHMMSS/run.csv`

### 5. Run Full Autotune

Once capture works, run the complete autotune pipeline:

```bash
python scripts/jetdrive_autotune.py --csv runs/jetdrive_capture_*/run.csv
```

Or for live capture + analysis:

```bash
python scripts/jetdrive_autotune.py --live --duration 60
```

## Troubleshooting

### No Providers Found

**Symptoms:**
```
[WARN] No JetDrive providers found
```

**Solutions:**
1. **Check Power Core is running** - JetDrive only broadcasts when Power Core is active
2. **Verify JetDrive is enabled** - Settings → JetDrive Configuration → Enable
3. **Check network interface** - Set the correct interface in Power Core
4. **Try specifying interface:**
   ```bash
   JETDRIVE_IFACE=192.168.1.100 python scripts/jetdrive_hardware_test.py --discover
   ```

### Multicast Error

**Symptoms:**
```
[FAIL] 0.0.0.0 (any): Multicast error: [Errno 19] No such device
```

**Solutions:**
1. **Specify correct interface:**
   ```bash
   export JETDRIVE_IFACE=192.168.1.100
   ```
2. **Check network adapter is enabled**
3. **Disable VPN** - VPNs often block multicast traffic
4. **Check firewall:**
   - Windows: Allow UDP port 22344 inbound
   - Linux: `sudo ufw allow 22344/udp`

### Port Already in Use

**Symptoms:**
```
[FAIL] Port 22344 unavailable: [Errno 98] Address already in use
```

**Solutions:**
1. **Close other JetDrive applications**
2. **Check for zombie processes:**
   ```bash
   # Linux/Mac
   lsof -i :22344
   
   # Windows
   netstat -ano | findstr 22344
   ```
3. **Use a different port:**
   ```bash
   export JETDRIVE_PORT=22345
   ```
   (Must match Power Core configuration)

### No Data During Capture

**Symptoms:**
```
[WARN] No samples captured
```

**Solutions:**
1. **Start the dyno** - Data only flows during a run
2. **Check channel selection** - Ensure channels are enabled in Power Core
3. **Verify Power Core is streaming** - Look for "JetDrive Active" indicator
4. **Monitor connection:**
   ```bash
   python scripts/jetdrive_hardware_test.py --monitor
   ```

## Network Configuration

### Recommended Setup

```
┌─────────────────┐     ┌─────────────────┐
│  Dyno Computer  │     │  Tuning Laptop  │
│  (Power Core)   │────▶│  (DynoAI)       │
│  192.168.1.50   │     │  192.168.1.100  │
└─────────────────┘     └─────────────────┘
         │                       │
         └───────────────────────┘
               Same Network
               (Multicast Enabled)
```

### Network Requirements

| Requirement | Details |
|-------------|---------|
| Protocol | UDP Multicast |
| Multicast Group | 224.0.2.10 (default) |
| Port | 22344 (default) |
| Same Subnet | Yes, required |
| Router/Switch | Must support IGMP snooping |

### Environment Variables

Configure via environment or `.env` file:

```bash
# .env
JETDRIVE_MCAST_GROUP=224.0.2.10
JETDRIVE_PORT=22344
JETDRIVE_IFACE=192.168.1.100  # Your computer's IP
```

## Channel Mapping

DynoAI expects these channel names (case-insensitive):

| DynoAI Name | Common Alternatives | Required |
|-------------|---------------------|----------|
| `RPM` | Engine Speed, EngineRPM | ✅ Yes |
| `Torque` | TQ, Torque_ftlb | ✅ Yes |
| `AFR` | AFR_Measured, Lambda × 14.7 | ✅ Yes |
| `TPS` | Throttle, ThrottlePos | Recommended |
| `MAP` | Manifold, ManifoldPressure | Recommended |
| `ECT` | CoolantTemp, EngineTemp | Optional |
| `IAT` | IntakeTemp, AirTemp | Optional |
| `Power` | HP, Horsepower, kW | Optional |

## API Integration

For programmatic access, use the API endpoints:

```bash
# Check status
curl http://localhost:5001/api/jetdrive/status

# Run analysis on uploaded CSV
curl -X POST http://localhost:5001/api/jetdrive/upload \
  -F "file=@runs/capture.csv"

# Get results
curl http://localhost:5001/api/jetdrive/run/{run_id}

# Download PVV corrections
curl http://localhost:5001/api/jetdrive/run/{run_id}/pvv
```

## Safety Reminders

⚠️ **Always follow dyno safety procedures:**

1. Secure the vehicle properly on the dyno
2. Ensure adequate ventilation
3. Have fire extinguisher accessible
4. Never leave dyno unattended during a run
5. Follow Dynojet's official safety guidelines

## Support

If you encounter issues:

1. Run full diagnostics: `--diagnose`
2. Check this guide's troubleshooting section
3. Review Power Core's JetDrive documentation
4. Open an issue on GitHub with diagnostic output

