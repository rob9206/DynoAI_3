# DynoAI Performance Troubleshooting Guide

## Quick Restart Scripts

### Quick Restart (Fastest - No Dependency Install)
**Use this most of the time:**
```bash
restart-quick.bat
```
or
```bash
.\restart-quick.ps1
```

### Full Clean Restart (Reinstalls Dependencies)
**Use this if quick restart doesn't fix the issue:**
```bash
restart-clean.bat
```
or
```bash
.\restart-clean.ps1
```

## What These Scripts Do

1. **Stop All Services**
   - Kills all Python/Flask processes
   - Kills all Node/Vite processes
   - Frees up ports 5001 (backend) and 5173 (frontend)

2. **Clear Caches**
   - Removes Python `__pycache__` directories
   - Removes `.pyc` compiled files
   - Clears Vite build cache
   - Clears Flask logs

3. **Clean Temporary Files**
   - Removes test output directories
   - Clears pytest cache

4. **Restart Services**
   - Reinstalls/updates dependencies
   - Starts Flask backend in a new window
   - Starts Vite frontend in a new window

## Common Performance Issues

### Issue: Application Running Slow

**Symptoms:**
- UI is sluggish
- API responses are delayed
- High CPU/memory usage

**Solutions:**
1. Run `restart-clean.bat` or `restart-clean.ps1`
2. Close unnecessary browser tabs
3. Check Task Manager for memory usage
4. Disable browser extensions temporarily
5. Clear browser cache (Ctrl+Shift+Delete)

### Issue: Application Crashes

**Symptoms:**
- Backend or frontend suddenly stops
- "Connection refused" errors
- Blank pages in browser

**Solutions:**
1. Run `restart-clean.bat` or `restart-clean.ps1`
2. Check the terminal windows for error messages
3. Look at `flask_debug.log` for backend errors
4. Check browser console (F12) for frontend errors

### Issue: Port Already in Use

**Symptoms:**
- "Address already in use" errors
- "Port 5001 is already allocated"
- Services won't start

**Solutions:**
1. Run `restart-clean.bat` - it automatically kills processes on ports 5001 and 5173
2. Or manually check ports:
   ```bash
   netstat -ano | findstr :5001
   netstat -ano | findstr :5173
   ```
3. Kill the process using the PID:
   ```bash
   taskkill /F /PID <PID>
   ```

### Issue: Memory Leaks

**Symptoms:**
- Memory usage keeps increasing
- Application slows down over time
- System becomes unresponsive

**Solutions:**
1. Run `restart-clean.bat` regularly (every few hours if needed)
2. Monitor memory in Task Manager
3. Close browser tabs when not actively testing
4. Restart your computer if memory usage is very high

### Issue: Database Locked

**Symptoms:**
- "Database is locked" errors
- Can't save tuning sessions
- API errors about SQLite

**Solutions:**
1. Run `restart-clean.bat` to stop all processes
2. Wait 5 seconds
3. Check if `dynoai.db` is being accessed by another program
4. Restart the services

## Performance Best Practices

### Development Environment

1. **Use SSD Storage**
   - Ensure project is on an SSD, not HDD
   - Faster file I/O = better performance

2. **Close Unnecessary Programs**
   - Close other IDEs, browsers, applications
   - Free up system resources

3. **Regular Restarts**
   - Run `restart-clean.bat` at start of each dev session
   - Run it again if you notice slowdowns

4. **Browser Optimization**
   - Use Chrome/Edge Developer Mode
   - Disable unnecessary extensions
   - Clear cache regularly

### Production Deployment

1. **Use Production Builds**
   ```bash
   cd frontend
   npm run build
   ```

2. **Enable Caching**
   - Configure proper HTTP caching headers
   - Use Redis for session storage

3. **Database Optimization**
   - Use PostgreSQL instead of SQLite for production
   - Add proper indexes
   - Regular VACUUM operations

4. **Resource Monitoring**
   - Monitor CPU, memory, disk usage
   - Set up alerts for high resource usage
   - Use application performance monitoring (APM)

## Advanced Troubleshooting

### Check Running Processes

```powershell
# PowerShell
Get-Process python* | Select-Object Id, ProcessName, CPU, WorkingSet
Get-Process node* | Select-Object Id, ProcessName, CPU, WorkingSet
```

```bash
# Command Prompt
tasklist | findstr python
tasklist | findstr node
```

### Check Port Usage

```bash
netstat -ano | findstr :5001
netstat -ano | findstr :5173
```

### View Flask Logs

```bash
type flask_debug.log
```

Or use PowerShell:
```powershell
Get-Content flask_debug.log -Tail 50
```

### Monitor Real-time Logs

```powershell
Get-Content flask_debug.log -Wait
```

### Clear Everything Manually

If the scripts don't work, manually:

1. Close all terminal windows
2. Open Task Manager (Ctrl+Shift+Esc)
3. End all `python.exe` and `node.exe` processes
4. Delete these folders:
   - All `__pycache__` folders
   - `frontend/node_modules/.vite`
   - `test_output`
   - `.pytest_cache`
5. Delete `flask_debug.log`
6. Restart services normally

## When to Contact Support

If you've tried all the above and still have issues:

1. **Collect Information:**
   - Python version: `python --version`
   - Node version: `node --version`
   - OS version: `winver`
   - Error messages from logs
   - Screenshots of errors

2. **Check System Requirements:**
   - Windows 10/11
   - Python 3.8+
   - Node.js 18+
   - 8GB+ RAM recommended
   - SSD storage recommended

3. **Create an Issue:**
   - Include all collected information
   - Describe steps to reproduce
   - Mention what you've already tried

## Quick Command Reference

| Task | Command |
|------|---------|
| **Quick restart** | `restart-quick.bat` or `.\restart-quick.ps1` |
| **Full clean restart** | `restart-clean.bat` or `.\restart-clean.ps1` |
| Normal start | `start-dev.bat` |
| Stop Python | `taskkill /F /IM python.exe` |
| Stop Node | `taskkill /F /IM node.exe` |
| Check ports | `netstat -ano \| findstr :5001` |
| View logs | `type flask_debug.log` |
| Clear cache | Delete `__pycache__` folders |

## Monitoring Tips

### Task Manager
- Press `Ctrl+Shift+Esc`
- Go to "Performance" tab
- Monitor CPU, Memory, Disk usage
- Look for `python.exe` and `node.exe` in "Processes" tab

### Browser DevTools
- Press `F12` in browser
- Go to "Console" tab for errors
- Go to "Network" tab for API calls
- Go to "Performance" tab for profiling

### Resource Monitor
- Press `Win+R`, type `resmon`, press Enter
- Monitor disk, network, memory, CPU in detail
- Useful for finding bottlenecks

---

**Remember:** When in doubt, run `restart-clean.bat`! It solves 90% of performance issues.

