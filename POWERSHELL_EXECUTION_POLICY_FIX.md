# PowerShell Execution Policy Fix

## Problem
When trying to run `.\start-jetdrive.ps1`, you get this error:

```
.\start-jetdrive.ps1 : File C:\Users\dawso\dynoai\DynoAI_3\start-jetdrive.ps1 cannot be loaded because running scripts
is disabled on this system. For more information, see about_Execution_Policies at
https://go.microsoft.com/fwlink/?LinkID=135170.
```

## What This Means
Windows PowerShell has a security feature called "Execution Policy" that prevents potentially harmful scripts from running. By default, it's set to `Restricted`, which blocks all scripts.

## Solution Options

### Option 1: Bypass for Single Command (Recommended for Quick Testing)

Run the script with a bypass flag:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-jetdrive.ps1
```

**Pros:** 
- No permanent changes to your system
- Works immediately
- Safest option

**Cons:**
- Need to use this command every time
- More typing

### Option 2: Set Execution Policy for Current User (Recommended)

This allows scripts to run for your user account only:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then you can run scripts normally:
```powershell
.\start-jetdrive.ps1
```

**Pros:**
- Permanent fix for your user
- Works for all scripts
- Doesn't require admin rights

**Cons:**
- Applies to all scripts you run (still safe with RemoteSigned policy)

### Option 3: Set Execution Policy Globally (Requires Admin)

Open PowerShell as Administrator and run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned
```

**Pros:**
- Works for all users
- Permanent solution

**Cons:**
- Requires administrator privileges
- Changes system-wide settings

## Understanding Execution Policies

- **Restricted** (Default): No scripts allowed
- **RemoteSigned** (Recommended): Local scripts OK, downloaded scripts must be signed
- **Unrestricted**: All scripts allowed (not recommended)
- **Bypass**: No restrictions, no warnings (use sparingly)

## Quick Fix Commands

### Check Current Policy
```powershell
Get-ExecutionPolicy
```

### Fix for Current Session Only
```powershell
powershell -ExecutionPolicy Bypass -File .\start-jetdrive.ps1
```

### Permanent Fix (Current User)
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Verify the Change
```powershell
Get-ExecutionPolicy -List
```

## Alternative: Use Batch File Instead

If you prefer not to change execution policies, use the batch file version:

```batch
start-jetdrive.bat
```

Or for development:
```batch
start-dev.bat
```

Batch files (.bat) don't have execution policy restrictions.

## Step-by-Step Instructions

### Recommended Approach (No Admin Required):

1. **Open PowerShell** (you already have it open)

2. **Run this command:**
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

3. **When prompted, type `Y` and press Enter**

4. **Now run your script:**
   ```powershell
   .\start-jetdrive.ps1
   ```

### Alternative Quick Fix (No Changes):

Just run this every time:
```powershell
powershell -ExecutionPolicy Bypass -File .\start-jetdrive.ps1
```

## Security Considerations

**RemoteSigned** is safe because:
- Local scripts you create can run
- Scripts downloaded from the internet must be digitally signed
- Provides good balance between security and usability
- Recommended by Microsoft for development

**RemoteSigned** protects you from:
- Accidentally running malicious scripts downloaded from the internet
- Scripts being injected via email or downloads
- Unauthorized script execution

## Troubleshooting

### Still Getting Errors?

If you're on a corporate/managed PC, your IT department may have locked down execution policies. In that case:

1. **Contact your IT department** to request RemoteSigned policy
2. **Use the bypass method** for individual script execution
3. **Use .bat files** instead of .ps1 files

### "Cannot be loaded because running scripts is disabled"

This specific error means you need to run one of the solutions above.

### "Execution policy is Restricted"

Run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## For Your Specific Case

Since you want to run `start-jetdrive.ps1`, here's what I recommend:

**Right now (immediate fix):**
```powershell
powershell -ExecutionPolicy Bypass -File .\start-jetdrive.ps1
```

**For permanent solution (run once):**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then you can use:
```powershell
.\start-jetdrive.ps1
```

## Related Commands

All of these scripts may require the same fix:
- `start-jetdrive.ps1` - JetDrive live capture
- `start-docker-dev.ps1` - Docker development environment
- `docker-rebuild.ps1` - Docker container rebuild
- Any other `.ps1` script in the project

## More Information

For detailed Microsoft documentation:
https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies
