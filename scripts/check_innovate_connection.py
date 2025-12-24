#!/usr/bin/env python3
"""Quick script to check Innovate device connection and data."""

import requests
import json
import sys

base_url = "http://localhost:5001"

print("=" * 60)
print("Innovate Device Connection Check")
print("=" * 60)

# Check status
print("\n[1] Device Status:")
try:
    r = requests.get(f"{base_url}/api/jetdrive/innovate/status", timeout=5)
    status = r.json()
    print(f"  Connected: {status.get('connected', False)}")
    if status.get('connected'):
        print(f"  Port: {status.get('port', 'N/A')}")
        print(f"  Device Type: {status.get('device_type', 'N/A')}")
        samples = status.get('samples', {})
        if samples:
            print("  Latest Samples:")
            for ch, data in samples.items():
                print(f"    {ch}: AFR={data.get('afr', 'N/A')}, Lambda={data.get('lambda', 'N/A')}")
    else:
        print("  [Not connected]")
except Exception as e:
    print(f"  Error: {e}")

# Check live data
print("\n[2] Live Data Stream:")
try:
    r = requests.get(f"{base_url}/api/jetdrive/hardware/live/data", timeout=5)
    data = r.json()
    print(f"  Capturing: {data.get('capturing', False)}")
    print(f"  Channel Count: {data.get('channel_count', 0)}")
    
    channels = data.get('channels', {})
    innovate_channels = {k: v for k, v in channels.items() if 'Innovate' in k or 'innovate' in k.lower()}
    
    if innovate_channels:
        print("  Innovate Channels Found:")
        for name, ch_data in innovate_channels.items():
            value = ch_data.get('value', 'N/A')
            units = ch_data.get('units', '')
            print(f"    {name}: {value} {units}")
    else:
        print("  [No Innovate channels in live data]")
        if channels:
            print(f"  Other channels available: {list(channels.keys())[:5]}")
except Exception as e:
    print(f"  Error: {e}")

# Check available ports
print("\n[3] Available Serial Ports:")
try:
    r = requests.get(f"{base_url}/api/jetdrive/innovate/ports", timeout=5)
    ports_data = r.json()
    if ports_data.get('success'):
        ports = ports_data.get('ports', [])
        if ports:
            for p in ports:
                print(f"  {p['port']}: {p.get('description', 'N/A')}")
        else:
            print("  [No serial ports found]")
    else:
        print(f"  Error: {ports_data.get('error', 'Unknown error')}")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 60)
print("To connect your device:")
print(f"  POST /api/jetdrive/innovate/connect")
print(f"  Body: {{'port': 'COM5', 'device_type': 'LC-2'}}")
print("=" * 60)

