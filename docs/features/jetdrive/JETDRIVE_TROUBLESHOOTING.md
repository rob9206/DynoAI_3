# JetDrive Troubleshooting Guide

## Quick Diagnostics

### 1. Test Discovery on Multiple Multicast Addresses

Use the new multi-discovery endpoint to test both the old and new multicast addresses:

```bash
curl http://localhost:5001/api/jetdrive/hardware/discover/multi
```

Or in PowerShell:
```powershell
Invoke-RestMethod -Uri "http://localhost:5001/api/jetdrive/hardware/discover/multi" | ConvertTo-Json -Depth 10
```

This will test both:
- `224.0.2.10` (old default)
- `239.255.60.60` (new Docker config)

The response will show which address (if any) finds providers and recommend the best one to use.

### 2. Auto-Configure Network Interface

Run the auto-configuration script to automatically detect and set your network interface:

```powershell
.\scripts\auto-configure-jetdrive.ps1
```

This script will:
- Detect your computer's primary network IP address
- Set `JETDRIVE_IFACE` to that IP (instead of `0.0.0.0`)
- Set `JETDRIVE_MCAST_GROUP` to `239.255.60.60`
- Set `JETDRIVE_PORT` to `22344`
- Set `DYNO_IP` to `239.255.60.60`

### 3. Manual Network Interface Configuration

If you need to set it manually:

```powershell
# Find your IP address
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }

# Set environment variables
$env:JETDRIVE_IFACE = "192.168.1.86"  # Your computer's IP
$env:JETDRIVE_MCAST_GROUP = "239.255.60.60"
$env:JETDRIVE_PORT = "22344"
```

## Common Issues

### No Providers Found

If `provider_count` is 0:

1. **Check Power Core Settings**
   - Open Power Core software on the dyno PC
   - Verify JetDrive is enabled
   - Check the multicast address setting - it should be `239.255.60.60`
   - Verify the port is `22344`

2. **Test Network Connectivity**
   ```powershell
   # Test if you can reach the dyno PC
   Test-Connection -ComputerName <dyno-pc-ip> -Count 2
   ```

3. **Check Firewall**
   ```powershell
   # Allow UDP port 22344
   New-NetFirewallRule -DisplayName "JetDrive UDP" -Direction Inbound -Protocol UDP -LocalPort 22344 -Action Allow
   ```

4. **Try Different Interface Binding**
   - Instead of `0.0.0.0`, try binding to your specific IP address
   - Run `.\scripts\auto-configure-jetdrive.ps1` to auto-detect

### Data Coming from localhost (127.0.0.1)

If discovery finds data but the source is `127.0.0.1`, this means:
- The socket is working correctly
- But the actual hardware isn't broadcasting
- Check Power Core settings to ensure JetDrive is enabled and broadcasting

### Socket Test Fails

If `socket_test.success` is `false`:

1. **Check Port Availability**
   ```powershell
   netstat -an | findstr :22344
   ```
   If the port is in use, stop the conflicting application

2. **Check Permissions**
   - On Windows, you may need administrator privileges to bind to multicast addresses
   - Try running as administrator

## API Endpoints

### Multi-Discovery Endpoint
```
GET /api/jetdrive/hardware/discover/multi?timeout=3
```

Tests discovery on both multicast addresses and returns which one works.

### Standard Discovery Endpoint
```
GET /api/jetdrive/hardware/discover?timeout=3
```

Tests discovery on the configured multicast address only.

### Debug Endpoint
```
GET /api/jetdrive/hardware/live/debug
```

Returns comprehensive debug information including:
- Current configuration
- Discovery results
- Socket test results
- Troubleshooting recommendations

## Configuration Files

### Environment Variables
- `JETDRIVE_IFACE`: Network interface IP (default: `0.0.0.0`)
- `JETDRIVE_MCAST_GROUP`: Multicast address (default: `239.255.60.60`)
- `JETDRIVE_PORT`: UDP port (default: `22344`)
- `DYNO_IP`: DynoWare RT-150 IP address (default: `239.255.60.60`)

### Configuration Files
- `config/dynoware_rt150.json`: Hardware configuration
- `config/env.docker`: Docker environment defaults
- `config/env.example`: Example environment configuration

## Next Steps

1. Run `.\scripts\auto-configure-jetdrive.ps1` to set up your network interface
2. Test discovery: `curl http://localhost:5001/api/jetdrive/hardware/discover/multi`
3. Check Power Core settings to ensure it's broadcasting to `239.255.60.60:22344`
4. If still not working, check the debug endpoint for detailed diagnostics
