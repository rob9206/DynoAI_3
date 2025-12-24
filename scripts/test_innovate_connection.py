#!/usr/bin/env python3
"""Test Innovate device connection and data flow."""

import requests
import json
import time

base_url = "http://localhost:5001"

print("=" * 60)
print("Innovate Device Connection Test")
print("=" * 60)

# Connect to COM5
print("\n[1] Connecting to COM5...")
try:
    r = requests.post(
        f"{base_url}/api/jetdrive/innovate/connect",
        json={"port": "COM5", "device_type": "LC-2"},
        timeout=10
    )
    result = r.json()
    print(f"  Success: {result.get('success')}")
    print(f"  Connected: {result.get('connected')}")
except Exception as e:
    print(f"  Error: {e}")
    sys.exit(1)

# Start live capture
print("\n[2] Starting live capture...")
try:
    r = requests.post(f"{base_url}/api/jetdrive/hardware/live/start", timeout=5)
    print(f"  Status: {r.json().get('status')}")
except Exception as e:
    print(f"  Error: {e}")

# Wait and check for data
print("\n[3] Waiting for data (10 seconds)...")
time.sleep(10)

# Check status
print("\n[4] Checking device status...")
try:
    r = requests.get(f"{base_url}/api/jetdrive/innovate/status", timeout=5)
    status = r.json()
    print(f"  Connected: {status.get('connected')}")
    samples = status.get('samples', {})
    if samples:
        print("  Samples received:")
        for ch, data in samples.items():
            print(f"    {ch}: AFR={data.get('afr', 'N/A')}, Lambda={data.get('lambda', 'N/A')}")
    else:
        print("  [No samples yet]")
except Exception as e:
    print(f"  Error: {e}")

# Check live data
print("\n[5] Checking live data channels...")
try:
    r = requests.get(f"{base_url}/api/jetdrive/hardware/live/data", timeout=5)
    data = r.json()
    print(f"  Capturing: {data.get('capturing')}")
    print(f"  Total Channels: {data.get('channel_count', 0)}")
    
    channels = data.get('channels', {})
    innovate_channels = {k: v for k, v in channels.items() if 'Innovate' in k or 'innovate' in k.lower()}
    
    if innovate_channels:
        print("\n  [SUCCESS] Innovate channels found:")
        for name, ch_data in innovate_channels.items():
            value = ch_data.get('value', 'N/A')
            units = ch_data.get('units', '')
            print(f"    {name}: {value} {units}")
    else:
        print("\n  [No Innovate channels in live data]")
        print("\n  Troubleshooting:")
        print("    1. Check device display - does it show AFR values?")
        print("    2. Is the O2 sensor connected and warmed up?")
        print("    3. Check backend logs for errors")
        print("    4. Device may need to be in a specific mode")
        print("    5. Try different baud rates (some devices use 9600)")
        
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 60)

