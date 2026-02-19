# DynoAI Restart Scripts

Quick reference for the restart scripts to fix performance issues and crashes.

## 🚀 Which Script Should I Use?

### 1. **Quick Restart** (Recommended - Use This First!)

**When to use:** 
- Daily restarts
- Performance feels sluggish
- After crashes
- Most common issues

**Commands:**
```bash
# Windows Batch
restart-quick.bat

# PowerShell
.\restart-quick.ps1
```

**What it does:**
- ✅ Stops all Python/Node processes
- ✅ Frees ports 5001 and 5173
- ✅ Clears Python cache
- ✅ Clears Flask logs
- ✅ Clears Vite cache
- ✅ Restarts services
- ❌ Does NOT reinstall dependencies (faster!)

**Time:** ~10-15 seconds

---

### 2. **Full Clean Restart** (Use If Quick Restart Doesn't Help)

**When to use:**
- Quick restart didn't fix the issue
- After updating dependencies
- After pulling new code
- Dependency-related errors

**Commands:**
```bash
# Windows Batch
restart-clean.bat

# PowerShell
.\restart-clean.ps1
```

**What it does:**
- ✅ Everything Quick Restart does, PLUS:
- ✅ Reinstalls Python dependencies
- ✅ Reinstalls Node dependencies
- ✅ Clears more temporary files

**Time:** ~30-60 seconds (depending on internet speed)

---

## 📋 Troubleshooting Flow

```
Issue occurs
    ↓
Try: restart-quick.bat
    ↓
Still broken?
    ↓
Try: restart-clean.bat
    ↓
Still broken?
    ↓
Check PERFORMANCE_TROUBLESHOOTING.md
```

## 🎯 Common Issues Fixed

### ✅ Performance Issues
- Slow UI
- High CPU/memory usage
- Laggy responses

**Solution:** `restart-quick.bat`

### ✅ Port Conflicts
- "Address already in use"
- "Port 5001 is already allocated"

**Solution:** `restart-quick.bat`

### ✅ Crashes
- Backend stops unexpectedly
- Frontend won't load
- Connection errors

**Solution:** `restart-quick.bat`

### ✅ Dependency Issues
- Import errors
- Module not found
- Package errors

**Solution:** `restart-clean.bat`

### ✅ Cache Issues
- Old code still running
- Changes not appearing
- Stale data

**Solution:** `restart-quick.bat`

## 💡 Pro Tips

1. **Start of Day:** Run `restart-quick.bat` at the beginning of each dev session
2. **After Git Pull:** Run `restart-clean.bat` to ensure dependencies are updated
3. **Memory Leaks:** Run `restart-quick.bat` every few hours if you notice memory growing
4. **Multiple Issues:** Try `restart-quick.bat` first, then `restart-clean.bat` if needed

## 🔍 What's Happening Behind the Scenes?

### Quick Restart Process:
```
1. Kill all Python processes
2. Kill all Node processes
3. Free up ports 5001 & 5173
4. Delete __pycache__ folders
5. Delete .pyc files
6. Clear flask_debug.log
7. Clear Vite cache
8. Wait 2 seconds
9. Start Flask backend
10. Wait 3 seconds
11. Start Vite frontend
```

### Full Clean Restart Process:
```
(Same as Quick Restart, PLUS:)
- Run: pip install -r requirements.txt
- Run: npm install in frontend/
- Clear test_output/
- Clear .pytest_cache/
```

## ⚠️ Known Issues

### Dependency Installation Errors

If you see errors like:
```
error: subprocess-exited-with-error
× Preparing metadata (pyproject.toml) did not run successfully.
```

**Don't worry!** The scripts now continue even if some dependencies fail to install. The app should still work if dependencies were previously installed.

If the app doesn't start:
1. Try running `restart-quick.bat` (skips dependency install)
2. Manually install dependencies later: `pip install -r requirements.txt`

### PowerShell Execution Policy

If you get:
```
cannot be loaded because running scripts is disabled
```

**Solution:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then run the script again.

## 📁 Script Locations

All scripts are in the project root:
- `restart-quick.bat` - Quick restart (Batch)
- `restart-quick.ps1` - Quick restart (PowerShell)
- `restart-clean.bat` - Full clean restart (Batch)
- `restart-clean.ps1` - Full clean restart (PowerShell)

## 🆘 Still Having Issues?

See the full troubleshooting guide:
```
PERFORMANCE_TROUBLESHOOTING.md
```

Or check the original startup scripts:
- `start-dev.bat` - Normal startup
- `start-web.ps1` - Normal startup (PowerShell)

## 📊 Performance Comparison

| Script | Time | Use Case | Dependency Install |
|--------|------|----------|-------------------|
| `restart-quick.bat` | ~15s | Daily use | ❌ No |
| `restart-clean.bat` | ~60s | After updates | ✅ Yes |
| `start-dev.bat` | ~30s | First time | ✅ Yes |

---

**Remember:** When in doubt, run `restart-quick.bat` first! It's fast and fixes 90% of issues. 🚀

