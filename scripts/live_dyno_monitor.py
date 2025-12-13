#!/usr/bin/env python3
"""
Live Dyno Data Monitor

Shows real-time data from JetDrive including atmospheric readings.
Press Ctrl+C to stop.
"""

import asyncio
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.services.jetdrive_client import (
    JetDriveConfig,
    JetDriveSample,
    discover_providers,
    subscribe,
)

# Channel name mapping based on typical Dynojet setup
CHANNEL_LABELS = {
    # Atmospheric Probe
    6: ("Temperature 1", "C"),
    7: ("Temperature 2", "C"),
    8: ("Humidity", "%"),
    9: ("Pressure", "kPa"),
    # Dyno
    39: ("Force Drum 1", "lbs"),
    40: ("Acceleration", "g"),
    41: ("Inductive 2 Str", ""),
    42: ("Digital RPM 1", "rpm"),
    43: ("Digital RPM 2", "rpm"),
    44: ("Inductive 1 Str", ""),
    # User Channels / AFR
    15: ("Lambda", ""),
    23: ("AFR 1", ":1"),
    28: ("AFR 2", ":1"),
    30: ("Correction", ""),
}

latest_values = {}
last_update = time.time()


def on_sample(sample: JetDriveSample):
    """Callback for each data sample."""
    global last_update
    latest_values[sample.channel_id] = (sample.channel_name, sample.value)
    last_update = time.time()


def clear_screen():
    """Clear terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def format_value(channel_id: int, name: str, value: float) -> str:
    """Format a channel value with label and units."""
    if channel_id in CHANNEL_LABELS:
        label, unit = CHANNEL_LABELS[channel_id]
        display_name = label
    else:
        display_name = name[:20] if name else f"Channel {channel_id}"
        unit = ""
    return f"{display_name:22s} {value:10.2f} {unit}"


async def display_loop(provider_name: str, stop_event: asyncio.Event):
    """Display loop that updates the screen."""
    while not stop_event.is_set():
        await asyncio.sleep(0.4)
        
        clear_screen()
        print("=" * 56)
        print("        LIVE DYNO DATA MONITOR - Dawson Dynamics")
        print("=" * 56)
        print(f"  Time: {datetime.now().strftime('%H:%M:%S')}    Provider: {provider_name}")
        print("-" * 56)
        
        # Atmospheric section
        atmo_ids = [6, 7, 8, 9]
        has_atmo = any(ch in latest_values for ch in atmo_ids)
        if has_atmo:
            print("  ATMOSPHERIC:")
            for ch_id in atmo_ids:
                if ch_id in latest_values:
                    name, val = latest_values[ch_id]
                    print(f"    {format_value(ch_id, name, val)}")
            print()
        
        # Dyno section
        dyno_ids = [39, 40, 42, 43]
        has_dyno = any(ch in latest_values for ch in dyno_ids)
        if has_dyno:
            print("  DYNO:")
            for ch_id in dyno_ids:
                if ch_id in latest_values:
                    name, val = latest_values[ch_id]
                    print(f"    {format_value(ch_id, name, val)}")
            print()
        
        # AFR section
        afr_ids = [15, 23, 28, 30]
        has_afr = any(ch in latest_values for ch in afr_ids)
        if has_afr:
            print("  AFR / LAMBDA:")
            for ch_id in afr_ids:
                if ch_id in latest_values:
                    name, val = latest_values[ch_id]
                    print(f"    {format_value(ch_id, name, val)}")
            print()
        
        # Other channels
        known_ids = set(atmo_ids + dyno_ids + afr_ids + [41, 44])
        other_ids = [k for k in latest_values.keys() if k not in known_ids]
        if other_ids:
            print("  OTHER CHANNELS:")
            for ch_id in sorted(other_ids)[:8]:
                name, val = latest_values[ch_id]
                print(f"    {format_value(ch_id, name, val)}")
            print()
        
        # Status
        print("-" * 56)
        age = time.time() - last_update
        if age < 2:
            status = "[LIVE]"
        elif age < 5:
            status = "[STALE]"
        else:
            status = "[NO DATA]"
        
        print(f"  Status: {status}  |  Channels: {len(latest_values)}  |  Age: {age:.1f}s")
        print("=" * 56)
        print("\nPress Ctrl+C to stop")


async def monitor():
    """Run the live monitor."""
    config = JetDriveConfig.from_env()
    
    print("Discovering JetDrive providers...")
    providers = await discover_providers(config, timeout=5.0)
    
    if not providers:
        print("[ERROR] No JetDrive providers found!")
        print("        Make sure Power Core is running with JetDrive enabled.")
        return
    
    provider = providers[0]
    print(f"[OK] Connected to: {provider.name}")
    print(f"     Channels available: {len(provider.channels)}")
    for ch_id, ch_info in list(provider.channels.items())[:10]:
        print(f"       [{ch_id:3d}] {ch_info.name}")
    if len(provider.channels) > 10:
        print(f"       ... and {len(provider.channels) - 10} more")
    print()
    print("Starting live monitor in 2 seconds...")
    await asyncio.sleep(2)
    
    stop_event = asyncio.Event()
    
    # Start display task
    display_task = asyncio.create_task(display_loop(provider.name, stop_event))
    
    try:
        # Subscribe to all channels
        await subscribe(
            provider=provider,
            channel_names=[],  # All channels
            on_sample=on_sample,
            config=config,
            stop_event=stop_event,
        )
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        stop_event.set()
        display_task.cancel()
        try:
            await display_task
        except asyncio.CancelledError:
            pass
        print("\n\n[OK] Monitor stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(monitor())
    except KeyboardInterrupt:
        print("\n[OK] Monitor stopped.")
