# Power Core JetDrive Setup Guide

## Where to Find JetDrive Settings in Power Core

The exact location may vary by Power Core version, but here's where to look:

### Method 1: Settings Menu (Most Common)

1. **Open Power Core** on the dyno PC
2. Look for one of these menu paths:
   - **Settings** → **Network** → **JetDrive**
   - **Settings** → **Communication** → **JetDrive**
   - **Tools** → **Settings** → **JetDrive Configuration**
   - **File** → **Preferences** → **JetDrive**

3. In the JetDrive settings window, you should see:
   - **Enable JetDrive** checkbox (check this!)
   - **Multicast Address** or **Network Address** field
   - **Port** field (should be `22344`)
   - **Network Interface** dropdown (select the interface connected to your computer)

### Method 2: Network/Communication Tab

Some Power Core versions have JetDrive settings in:
- **Network Settings** tab
- **Communication Settings** tab
- **Data Export** or **Data Sharing** section

### Method 3: During Dyno Run Setup

Some versions allow enabling JetDrive when:
- Starting a new dyno run
- Configuring data channels
- Setting up data logging

## What to Configure

### Required Settings

1. **Enable JetDrive**: ✅ Check this box
2. **Multicast Address**: Set to `239.255.60.60`
   - Some versions may call this "Network Address" or "Broadcast Address"
   - Older versions might default to `224.0.2.10` - change it to `239.255.60.60`
3. **Port**: Set to `22344`
4. **Network Interface**: Select the network adapter connected to your tuning computer
   - If you're using a direct Ethernet cable, select that interface
   - If using WiFi/router, select the WiFi interface

### Channel Configuration

Enable these channels for best results:
- ✅ **RPM** (Engine Speed) - Required
- ✅ **Torque** (ft-lb or Nm) - Required  
- ✅ **Power** (HP or kW) - Recommended
- ✅ **AFR** or **Lambda** - Required for tuning
- ✅ **TPS** (Throttle Position) - Recommended
- ✅ **MAP** (Manifold Pressure) - Recommended
- ⚪ **ECT** (Engine Coolant Temperature) - Optional
- ⚪ **IAT** (Intake Air Temperature) - Optional

## Visual Indicators

When JetDrive is working correctly, you should see:
- **"JetDrive Active"** indicator in Power Core status bar
- **"Broadcasting"** or **"Streaming"** message
- Network activity indicator (if available)

## Troubleshooting

### Can't Find JetDrive Settings?

1. **Check Power Core Version**
   - Older versions may not have JetDrive
   - Update to the latest Power Core version if needed
   - JetDrive requires Power Core 2.0 or later

2. **Check License/Features**
   - Some Power Core licenses may not include JetDrive
   - Contact Dynojet support if JetDrive option is missing

3. **Look in Different Menus**
   - Try **View** → **Options**
   - Try **Edit** → **Preferences**
   - Try right-clicking on the main window for context menu

### Settings Not Saving?

1. **Run as Administrator**
   - Right-click Power Core → **Run as Administrator**
   - Some settings require admin privileges

2. **Check File Permissions**
   - Ensure Power Core can write to its config directory
   - Usually in: `C:\Program Files\Dynojet\Power Core\` or `%AppData%\Dynojet\`

## Verification Steps

After configuring JetDrive in Power Core:

1. **Save Settings** - Click **Apply** or **OK**
2. **Restart Power Core** (if prompted)
3. **Check Status** - Look for "JetDrive Active" indicator
4. **Test from DynoAI**:
   ```powershell
   # Run multi-discovery test
   .\scripts\test-multi-discovery.ps1
   ```

## Power Core Version-Specific Notes

### Power Core 2.x
- Settings usually in: **Settings** → **Network** → **JetDrive**
- Multicast address field may be labeled "Broadcast Address"

### Power Core 3.x
- Settings may be in: **Tools** → **Communication Settings**
- May have separate "Data Streaming" section

### Power Vision Integration
- If using Power Vision, JetDrive settings may be in Power Vision software
- Check Power Vision → **Settings** → **Data Export**

## Still Can't Find It?

If you can't locate the JetDrive settings:

1. **Check Power Core Help**
   - Press **F1** in Power Core
   - Search for "JetDrive" or "Network"

2. **Contact Dynojet Support**
   - They can provide version-specific instructions
   - May need to enable a feature or update software

3. **Check Documentation**
   - Look for Power Core user manual
   - Search for "JetDrive" or "Network Broadcasting"

## Alternative: Check if JetDrive is Already Enabled

Even if you can't find the settings, JetDrive might already be enabled. Test it:

```powershell
# Test discovery
.\scripts\test-multi-discovery.ps1
```

If providers are found, JetDrive is already working - you just need to verify the multicast address matches (`239.255.60.60`).
