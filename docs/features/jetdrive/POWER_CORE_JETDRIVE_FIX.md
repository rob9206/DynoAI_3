# Power Core JetDrive Configuration Fix

## Current Configuration (from diagnostic export)

Based on your Power Core diagnostic export, here's what I found:

### ✅ JetDrive is Configured
- **JetdriveSelectedIface**: `10.0.0.100`
- **JetdriveChannels**: Multiple channels configured (RPM, Torque, AFR, etc.)

### ❌ Problems Found

1. **Invalid Network Interface**
   - Power Core is trying to use `10.0.0.100` as the JetDrive interface
   - Error: "The requested address is not valid in its context"
   - This IP address doesn't match any valid network interface

2. **Multicast May Be Disabled**
   - `dynoUseMulticast` is set to `False` in the config
   - This might prevent JetDrive from broadcasting

3. **Network Interface Mismatch**
   - Your dyno PC has interface `169.254.22.100` (from connected_devices.txt)
   - Power Core is configured to use `10.0.0.100` (which doesn't exist)

## How to Fix in Power Core

### Step 1: Open Power Core Settings

1. Open **Power Core** on the dyno PC (AK47)
2. Go to: **Tools** → **Options** or **Settings** → **Environment Options**
3. Look for **JetDrive** or **Network** settings tab

### Step 2: Fix Network Interface

1. Find **"JetDrive Network Interface"** or **"JetDrive Selected Interface"**
2. **Change from `10.0.0.100` to `169.254.22.100`**
   - This is the IP address shown in connected_devices.txt as "Connected To"
   - This is the interface that's actually connected to the DynoWare RT-150

### Step 3: Enable Multicast (if available)

1. Look for **"Use Multicast"** or **"Enable Multicast"** setting
2. **Enable it** (set to `True`)
3. If there's a multicast address field, set it to: `239.255.60.60`

### Step 4: Verify Port

1. Ensure the port is set to: `22344`
2. Some versions might have this in a separate "Port" or "UDP Port" field

### Step 5: Save and Restart

1. Click **Apply** or **OK** to save settings
2. **Restart Power Core** if prompted
3. Look for "JetDrive Active" indicator in the status bar

## Alternative: Edit Config File Directly

If you can't find the settings in the UI, you can edit the config file directly:

**Location**: `%AppData%\Dynojet\Power Core\user.config`

**Changes needed**:
```xml
<!-- Change this line: -->
<setting name="JetdriveSelectedIface" serializeAs="String">
    <value>169.254.22.100</value>  <!-- Changed from 10.0.0.100 -->
</setting>

<!-- Enable multicast if available: -->
<setting name="dynoUseMulticast" serializeAs="String">
    <value>True</value>  <!-- Changed from False -->
</setting>
```

**⚠️ Warning**: 
- Close Power Core before editing the config file
- Make a backup first
- Restart Power Core after editing

## Verification

After making changes:

1. **Check Power Core Status**
   - Look for "JetDrive Active" or "Broadcasting" indicator
   - No error messages about JetDrive

2. **Test from DynoAI**
   ```powershell
   .\scripts\test-multi-discovery.ps1
   ```

3. **Check Logs**
   - Power Core logs should show "JetDrive started successfully"
   - No more "Error starting jetdrive!" messages

## Network Interface Detection

To find the correct interface IP on the dyno PC:

1. Open **Command Prompt** on the dyno PC
2. Run: `ipconfig`
3. Look for the interface connected to your tuning computer
4. Use that IP address in Power Core JetDrive settings

Based on your diagnostic export:
- **DynoWare RT-150 IP**: `169.254.187.108`
- **Dyno PC Interface**: `169.254.22.100` (the "Connected To" address)
- **Use this interface**: `169.254.22.100` for JetDrive

## Summary

**Current Problem**: Power Core is trying to use invalid IP `10.0.0.100`

**Solution**: Change JetDrive interface to `169.254.22.100` (the actual connected interface)

**Expected Result**: JetDrive should start successfully and broadcast to `239.255.60.60:22344`
