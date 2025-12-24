#!/usr/bin/env python3
"""Debug script to check Innovate data flow."""

import json
import time

import requests

base_url = "http://localhost:5001"

print("=" * 60)
print("Innovate Data Debug")
print("=" * 60)

# Check Innovate status with samples
print("\n[1] Innovate Device Status (with samples):")
try:
    r = requests.get(f"{base_url}/api/jetdrive/innovate/status", timeout=5)
    status = r.json()
    print(json.dumps(status, indent=2))

    samples = status.get("samples", {})
    if samples:
        print("\n  Latest Samples from Device:")
        for ch, data in samples.items():
            print(
                f"    {ch}: AFR={data.get('afr', 'N/A')}, Lambda={data.get('lambda', 'N/A')}"
            )
    else:
        print("  [No samples yet - device may not be sending data]")
except Exception as e:
    print(f"  Error: {e}")

# Check live data
print("\n[2] Live Data Channels:")
try:
    r = requests.get(f"{base_url}/api/jetdrive/hardware/live/data", timeout=5)
    data = r.json()
    print(f"  Capturing: {data.get('capturing')}")
    print(f"  Total Channels: {data.get('channel_count', 0)}")

    channels = data.get("channels", {})
    print(f"\n  All Channel Names:")
    for name in sorted(channels.keys())[:20]:
        ch_data = channels[name]
        value = ch_data.get("value", "N/A")
        print(f"    {name}: {value}")

    innovate_channels = {
        k: v for k, v in channels.items() if "Innovate" in k or "innovate" in k.lower()
    }
    if innovate_channels:
        print(f"\n  Innovate Channels Found:")
        for name, ch_data in innovate_channels.items():
            print(f"    {name}: {ch_data.get('value', 'N/A')}")
    else:
        print(f"\n  [No Innovate channels found]")
        print(
            f"  This means the integration may not be working, or device isn't sending data yet."
        )

except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 60)
print("Troubleshooting:")
print("1. Check if device is powered on and sensor is connected")
print("2. Verify device is sending data (check device display)")
print("3. The device may need time to warm up the sensor")
print("4. Check backend logs for any errors")
print("=" * 60)
