# Quick Start Reference - DynoAI

This document provides quick commands for starting DynoAI in different modes.

## JetDrive Live Capture Mode

### Option 1: Batch File (No Admin/Policy Changes Required)
```batch
start-jetdrive.bat
```
✅ **Recommended** - No execution policy issues

### Option 2: PowerShell with Bypass
```powershell
powershell -ExecutionPolicy Bypass -File .\start-jetdrive.ps1
```
✅ Works without changing system settings

### Option 3: Direct PowerShell (After Fixing Execution Policy)
```powershell
.\start-jetdrive.ps1
```
⚠️ Requires: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

---

## Standard Development Mode

### Windows
```batch
start-dev.bat
```

### With Network Interface Selection
```batch
start-dev-ziggle.bat
```

---

## Docker Mode

### Production
```batch
docker-start-prod.bat
```

### Development
```powershell
powershell -ExecutionPolicy Bypass -File .\start-docker-dev.ps1
```

### Rebuild After Changes
```powershell
powershell -ExecutionPolicy Bypass -File .\docker-rebuild.ps1
```

Or using batch:
```batch
docker-rebuild.bat
```

---

## Fix PowerShell Execution Policy (One-Time Setup)

If you want to use `.ps1` scripts directly without bypass:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then verify:
```powershell
Get-ExecutionPolicy
```

Should show: `RemoteSigned`

---

## Troubleshooting

### "Cannot be loaded because running scripts is disabled"

**Quick Fix:**
- Use the `.bat` file instead: `start-jetdrive.bat`
- Or use bypass: `powershell -ExecutionPolicy Bypass -File .\start-jetdrive.ps1`

**Permanent Fix:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### "Docker container failed to start"

See: `DOCKER_FIX_INSTRUCTIONS.md`

### "Realtime analysis error"

Fixed in: `JETDRIVE_REALTIME_FIX.md` (auto-reloads in dev mode)

### Port Already in Use

Check what's using the port:
```powershell
netstat -ano | findstr :5001
```

Stop conflicting process or change port in `.env`:
```
API_PORT=5002
```

---

## Environment Files

### Development
- `.env` - Main environment configuration

### Docker
- `.env.docker` - Docker-specific settings

### JetDrive WiFi Mode
See: `START_JETDRIVE_WIFI.md`

---

## Verification Commands

### Check if API is running
```powershell
curl http://localhost:5001/api/health/ready
```

### Check JetDrive listener
```powershell
curl http://localhost:5001/api/jetdrive/hardware/monitor/status
```

### View logs
```powershell
# In PowerShell terminal where server is running
# Press Ctrl+C to stop
```

---

## Quick Command Summary

| Task | Command |
|------|---------|
| Start JetDrive (easiest) | `start-jetdrive.bat` |
| Start Development | `start-dev.bat` |
| Docker Production | `docker-start-prod.bat` |
| Docker Development | `powershell -ExecutionPolicy Bypass -File .\start-docker-dev.ps1` |
| Rebuild Docker | `docker-rebuild.bat` |
| Fix PowerShell Policy | `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Test Realtime Fix | `python test_realtime_fix.py` |

---

## Documentation Index

- `README.md` - Main project documentation
- `DOCKER_FIX_INSTRUCTIONS.md` - Docker troubleshooting
- `JETDRIVE_REALTIME_FIX.md` - Realtime analysis fix details
- `POWERSHELL_EXECUTION_POLICY_FIX.md` - PowerShell policy help
- `START_JETDRIVE_WIFI.md` - WiFi mode configuration
- `VIEWING_RESULTS.md` - How to view analysis results

---

## Current Status (Based on Your Session)

✅ **Fixed Issues:**
- Docker Flask application startup (Dockerfile CMD fixed)
- Realtime analysis NoneType comparison error (jetdrive_realtime_analysis.py)
- PowerShell execution policy (created .bat wrapper)

🔧 **Ready to Use:**
- `start-jetdrive.bat` - Start JetDrive without policy issues
- `docker-rebuild.bat` - Rebuild Docker containers
- `test_realtime_fix.py` - Test realtime analysis (all tests passed)

📝 **Next Steps:**
1. Run `start-jetdrive.bat` to start JetDrive capture
2. Open http://localhost:5001/admin in browser
3. Monitor for the realtime analysis errors (should be gone)
4. Test dyno capture with live bike/dyno connection

---

## Support

For issues not covered here, check the `docs/` folder or the specific fix documentation files listed above.
