# Quick Start Troubleshooting Guide

## Issue: `start-all.bat` Gets Stuck at Step 2/10

### Specific Error: "Cannot find module npm-prefix.js"

If you see this error:
```
Error: Cannot find module 'C:\Users\...\frontend\node_modules\npm\bin\npm-prefix.js'
```

**This means your npm/node_modules installation is corrupted.** Run the fix script:

```cmd
FIX_NPM_ERROR.bat
```

This will:
1. Delete the corrupted `frontend\node_modules` folder
2. Remove `package-lock.json`
3. Clear npm cache
4. Reinstall all packages cleanly

**Or fix manually:**
```cmd
cd frontend
rmdir /s /q node_modules
del package-lock.json
npm cache clean --force
npm install
cd ..
```

Then use quick-start:
```cmd
scripts\windows\quick-start.bat
```

---

### What Happens at Step 2/10?
Step 2/10 attempts to update system dependencies:
1. Updates pip (Python package manager)
2. Updates all Python packages from `requirements.txt`
3. Updates all Node.js packages in the frontend directory

### Common Causes

#### 1. **Network/Timeout Issues**
- Package downloads timing out
- Slow internet connection
- Corporate firewall blocking package repositories

#### 2. **Package Build Issues**
- Some Python packages need to compile C extensions
- Missing Visual C++ build tools on Windows
- Can take 5-10 minutes for packages like scipy, numpy, etc.

#### 3. **Corrupted Cache**
- pip cache corruption
- npm cache corruption

#### 4. **Permission Issues**
- Can't write to package installation directories
- Antivirus blocking file writes

---

## Solutions

### Solution 1: Use Quick Start Instead (RECOMMENDED)
The `quick-start.bat` script skips all dependency updates and just starts the services:

```cmd
scripts\windows\quick-start.bat
```

This is faster and avoids the hanging issue entirely.

### Solution 2: Use the Verbose Version
I've created a verbose version that shows exactly what's happening:

```cmd
scripts\windows\start-all-verbose.bat
```

This will show you:
- Which command is running
- Real-time output from pip and npm
- Where it's getting stuck

### Solution 3: Update the Dependencies Manually
Update dependencies separately so you can see any errors:

```cmd
# Update pip
python -m pip install --upgrade pip

# Update Python packages
python -m pip install -U -r requirements.txt

# Update Node packages
cd frontend
npm update
cd ..

# Then use quick-start
scripts\windows\quick-start.bat
```

### Solution 4: Clear Package Caches
If caches are corrupted:

```cmd
# Clear pip cache
python -m pip cache purge

# Clear npm cache
cd frontend
npm cache clean --force
cd ..

# Try again
scripts\windows\start-all.bat
```

### Solution 5: Skip Problem Packages
If specific packages are causing issues:

1. Check `requirements.txt` for large packages like:
   - scipy
   - numpy
   - pandas
   - torch/tensorflow
   
2. Install them separately first:
   ```cmd
   python -m pip install numpy scipy pandas --timeout 300
   ```

3. Then run the startup script

### Solution 6: Use the Fixed Version
I've updated `start-all.bat` with:
- Timeouts to prevent infinite hangs
- Better error messages
- Continues even if updates fail
- Shows progress

Just run it again:
```cmd
scripts\windows\start-all.bat
```

---

## Quick Diagnostics

### Check if services are already running:
```cmd
# Check for Flask backend on port 5001
netstat -ano | findstr :5001

# Check for Vite frontend on port 5173
netstat -ano | findstr :5173
```

### Test Python environment:
```cmd
python --version
python -m pip --version
python -c "import flask; print(flask.__version__)"
```

### Test Node environment:
```cmd
node --version
npm --version
cd frontend && npm list vite
```

---

## Best Practice: Development Workflow

For daily development, use the **quick-start** script:
```cmd
scripts\windows\quick-start.bat
```

Only use **start-all** when:
- First time setup
- After pulling major updates
- After modifying requirements.txt or package.json
- Weekly/monthly maintenance

---

## Still Having Issues?

If the problem persists:

1. Run the verbose version and share the output:
   ```cmd
   scripts\windows\start-all-verbose.bat > startup-log.txt 2>&1
   ```

2. Check for specific error messages in the log

3. Common fixes:
   - Install Visual C++ Build Tools (for Python package compilation)
   - Update Python to latest version (3.11 or 3.12)
   - Update Node.js to latest LTS version
   - Disable antivirus temporarily during installation
   - Use a VPN if corporate firewall is blocking

4. Nuclear option - fresh virtual environment:
   ```cmd
   # Backup current environment
   python -m pip freeze > old-requirements.txt
   
   # Create fresh venv
   python -m venv .venv-new
   .venv-new\Scripts\activate
   
   # Install packages
   pip install -r requirements.txt
   
   # Update scripts to use new venv
   ```
