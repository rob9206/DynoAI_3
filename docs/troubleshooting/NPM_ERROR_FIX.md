# URGENT FIX - NPM Module Error

## The Real Problem (from your screenshot)

You're getting this error:
```
Error: Cannot find module 'C:\Users\dawso\dynoai\DynoAI_3\frontend\node_modules\npm\bin\npm-prefix.js'
```

This is **NOT a hang** - it's a **corrupted npm installation** in your `frontend/node_modules` folder.

## Quick Fix Options

### Option 1: Simple Fix (Try This First)
```cmd
scripts\windows\fix-npm-simple.bat
```
Just reinstalls packages without deleting. Fastest and avoids permission issues.

### Option 2: Full Clean (If Option 1 Doesn't Work)
```cmd
scripts\windows\fix-npm-error.bat
```
Deletes and reinstalls everything. May show "Access denied" warnings but usually works.

### Option 3: Admin Mode (If Getting Permission Errors)
Right-click and "Run as administrator":
```cmd
scripts\windows\fix-npm-error-admin.bat
```
Uses admin privileges to force delete locked files.

All scripts take 2-5 minutes depending on your internet speed.

## Manual Fix (If You Prefer)

```cmd
cd frontend
rmdir /s /q node_modules
del package-lock.json
npm cache clean --force
npm install
cd ..
```

Then start the app:
```cmd
scripts\windows\quick-start.bat
```

## Why This Happened

Common causes of corrupted `node_modules`:
- Interrupted `npm install` (Ctrl+C, computer crash, etc.)
- Antivirus deleting files during installation
- Disk space issues during installation
- Switching Node.js versions mid-installation
- Multiple npm processes running simultaneously

## After the Fix

Once fixed, use these commands:

**Daily use (no updates):**
```cmd
scripts\windows\quick-start.bat
```

**When you need to update packages:**
```cmd
cd frontend
npm update
cd ..
scripts\windows\quick-start.bat
```

## Prevention

To avoid this in the future:
1. Don't interrupt `npm install` with Ctrl+C
2. Temporarily disable antivirus during npm install
3. Use `npm ci` instead of `npm install` for cleaner installs
4. Don't run multiple npm commands simultaneously

## If Fix Script Fails

If `fix-npm-error.bat` fails, try:

1. **Close all Node/npm processes:**
   ```cmd
   taskkill /F /IM node.exe
   taskkill /F /IM npm.exe
   ```

2. **Check Node.js version:**
   ```cmd
   node --version
   ```
   Should be v18 or higher. If not, update Node.js from `https://nodejs.org/`

3. **Try with administrator rights:**
   - Right-click `scripts\windows\fix-npm-error-admin.bat`
   - Choose "Run as administrator"

4. **Nuclear option - delete manually:**
   - Open File Explorer
   - Navigate to `C:\Users\dawso\dynoai\DynoAI_3\frontend`
   - Delete the `node_modules` folder (may take a while, it's huge)
   - Delete `package-lock.json`
   - Run: `npm install`

