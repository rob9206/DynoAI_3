# JetDrive IP Configuration Guide

## Quick Fix: Update Your Computer's IP

If JetDrive is using an old IP address, you have **3 easy options**:

---

## Option 1: Use IP Parameter (Quickest - One Time)

Run the start script with your current IP:

```batch
start-jetdrive.bat YOUR_CURRENT_IP
```

**Example:**
```batch
start-jetdrive.bat 192.168.1.100
```

✅ **Best for:** Testing with a new IP before making it permanent

---

## Option 2: Use Update Helper Script (Easiest - Permanent)

Run the interactive helper:

```batch
update-jetdrive-ip.bat
```

This will:
1. Show your current IP addresses
2. Show current JetDrive configuration
3. Let you update the IP permanently
4. Test the configuration

✅ **Best for:** Permanent IP change with guided help

---

## Option 3: Manual Edit (Advanced - Permanent)

Edit `start-jetdrive.ps1` directly:

1. Open `start-jetdrive.ps1` in a text editor
2. Find line 6:
   ```powershell
   [string]$ComputerIP = "192.168.1.81",
   ```
3. Change `192.168.1.81` to your new IP
4. Save the file

✅ **Best for:** Quick manual update if you know your IP

---

## Finding Your Computer's IP Address

### Method 1: Command Line (Quick)
```batch
ipconfig | findstr "IPv4"
```

Look for your WiFi adapter's IPv4 address (usually starts with 192.168.1.x)

### Method 2: Full Network Info
```batch
ipconfig
```

Look for the "Wireless LAN adapter Wi-Fi" section and find the IPv4 Address.

### Method 3: Windows Settings
1. Open **Settings** > **Network & Internet**
2. Click **Wi-Fi**
3. Click your connected network name
4. Scroll down to see "IPv4 address"

---

## Understanding the IP Configuration

JetDrive uses **two** IP settings:

### 1. Your Computer's IP (`ComputerIP`)
- **What it is:** Your PC's network adapter IP address
- **Default:** `192.168.1.81`
- **When to change:** When your computer's IP changes (DHCP, new network, etc.)
- **Example:** `192.168.1.100`

### 2. Dyno Multicast Group (`DynoIP`)
- **What it is:** UDP multicast address for JetDrive protocol
- **Default:** `239.255.60.60`
- **When to change:** Almost never (standard JetDrive protocol)
- **Note:** This is NOT the dyno's IP address

---

## Common Scenarios

### Scenario 1: DHCP Changed Your IP
Your router assigned you a new IP address.

**Solution:**
```batch
# Check your new IP
ipconfig | findstr "IPv4"

# Start with new IP
start-jetdrive.bat YOUR_NEW_IP

# Or update permanently
update-jetdrive-ip.bat
```

### Scenario 2: Switched Networks
You moved from one WiFi network to another.

**Solution:**
1. Check your IP on the new network
2. Update the configuration
3. Ensure dyno is on same network (192.168.1.x subnet)

### Scenario 3: WiFi vs Ethernet
You switched from WiFi to Ethernet (or vice versa).

**Solution:**
```batch
# Check IP of active adapter
ipconfig

# Use the IP from the connected adapter
start-jetdrive.bat IP_FROM_CONNECTED_ADAPTER
```

### Scenario 4: Multiple Network Adapters
You have multiple adapters and aren't sure which one to use.

**Solution:**
1. The dyno is usually on WiFi (192.168.1.x)
2. Use the WiFi adapter's IP
3. Make sure you're on same subnet as dyno

---

## Troubleshooting

### "Cannot reach dyno" or "Connection timeout"

**Check 1: Same Network**
- Your computer: `192.168.1.X`
- Dyno should be: `192.168.1.Y`
- They must match the first three numbers

**Check 2: Firewall**
```powershell
# Allow UDP port 22344 in Windows Firewall
netsh advfirewall firewall add rule name="JetDrive" dir=in action=allow protocol=UDP localport=22344
```

**Check 3: Network Adapter**
Make sure you're using the correct adapter (WiFi, not Ethernet)

### "Old IP still being used"

**Check where IP is configured:**
1. In `start-jetdrive.ps1` (line 6) - `ComputerIP` parameter
2. In `.env` file (line 107) - `JETDRIVE_IFACE` setting

**Solution:**
Update both to match:
```powershell
# start-jetdrive.ps1 line 6
[string]$ComputerIP = "YOUR_NEW_IP",

# .env line 107
JETDRIVE_IFACE=YOUR_NEW_IP
```

Or just use the start script parameter (it overrides both):
```batch
start-jetdrive.bat YOUR_NEW_IP
```

### "Realtime analysis errors"

These are unrelated to IP configuration and have been fixed separately.
See: `JETDRIVE_REALTIME_FIX.md`

---

## Testing Your Configuration

After updating the IP:

### Test 1: Start JetDrive
```batch
start-jetdrive.bat
```

Look for this in the output:
```
  Your IP:         192.168.1.XXX  (should match your actual IP)
  Multicast Group: 239.255.60.60
  JetDrive Port:   22344 (UDP multicast)
```

### Test 2: Check API Health
```powershell
curl http://localhost:5001/api/health/ready
```

Should return: `200 OK`

### Test 3: Check JetDrive Status
```powershell
curl http://localhost:5001/api/jetdrive/hardware/monitor/status
```

Should return hardware status (if dyno connected)

### Test 4: Check Network Multicast
```powershell
netstat -an | findstr 22344
```

Should show UDP port 22344 listening

---

## Quick Reference

| Task | Command |
|------|---------|
| Find your IP | `ipconfig \| findstr "IPv4"` |
| Start with custom IP | `start-jetdrive.bat YOUR_IP` |
| Update IP (helper) | `update-jetdrive-ip.bat` |
| Edit IP manually | Edit `start-jetdrive.ps1` line 6 |
| Test configuration | `curl http://localhost:5001/api/health` |
| Show network info | `ipconfig` |

---

## Advanced: Environment Variable Override

You can also set the IP via environment variable (temporary):

```powershell
$env:JETDRIVE_IFACE = "192.168.1.100"
start-jetdrive.bat
```

This overrides the script setting for the current PowerShell session only.

---

## Network Requirements

For JetDrive to work:

✅ **Same Subnet:**
- Computer: `192.168.1.X`
- Dyno: `192.168.1.Y`

✅ **UDP Multicast Enabled:**
- Protocol: UDP
- Port: 22344
- Multicast: 239.255.60.60

✅ **Firewall Rules:**
- Allow incoming UDP on port 22344
- Allow multicast traffic

✅ **Network Type:**
- WiFi is most common
- Direct Ethernet connection also works
- Must be on same physical/logical network

---

## Files That Control IP Configuration

1. **`start-jetdrive.ps1`** (line 6)
   - `ComputerIP` parameter
   - Default: `192.168.1.81`
   - **This is the main setting**

2. **`.env`** (line 107)
   - `JETDRIVE_IFACE` variable
   - Overridden by start-jetdrive.ps1
   - Used as fallback

3. **Command line parameter**
   - `start-jetdrive.bat YOUR_IP`
   - Overrides everything
   - Temporary (not saved)

**Priority:** Command line > start-jetdrive.ps1 > .env

---

## Summary

**Fastest solution if IP changed:**
```batch
# Find your current IP
ipconfig | findstr "IPv4"

# Start JetDrive with new IP
start-jetdrive.bat YOUR_NEW_IP_FROM_ABOVE
```

**Make it permanent:**
```batch
update-jetdrive-ip.bat
```

That's it! JetDrive should now connect using the correct IP.

---

## Related Documentation

- `QUICK_START.md` - All startup commands
- `START_JETDRIVE_WIFI.md` - WiFi setup guide
- `JETDRIVE_REALTIME_FIX.md` - Realtime analysis fix
- `SESSION_FIX_SUMMARY.md` - All recent fixes
