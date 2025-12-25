#!/usr/bin/env python3
"""
AFR Sensor Calibration Tool

Interactive tool to calibrate Innovate DLG-1 AFR sensors using free air calibration.
Measures actual free air readings and calculates correction offsets.

Free air (atmospheric O2) should read approximately 20.9 AFR.

Usage:
    python scripts/calibrate_afr.py [COM_PORT]

Example:
    python scripts/calibrate_afr.py COM5
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev

from api.services.innovate_client import InnovateClient, InnovateDeviceType

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ANSI colors for terminal output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"


# Expected free air AFR (atmospheric O2 content)
EXPECTED_FREE_AIR_AFR = 20.9
ACCEPTABLE_RANGE = (20.5, 21.3)  # ±0.4 AFR tolerance
SAMPLE_COUNT = 30  # Number of samples to collect for averaging
SAMPLE_INTERVAL = 0.5  # Seconds between samples


def calculate_offset(
    measured_afr: float, expected_afr: float = EXPECTED_FREE_AIR_AFR
) -> float:
    """
    Calculate the offset needed to correct AFR reading.

    Args:
        measured_afr: Average AFR measured in free air
        expected_afr: Expected AFR in free air (default 20.9)

    Returns:
        Offset to add to raw readings (positive = add, negative = subtract)
    """
    # Offset = expected - measured
    # If sensor reads 21.5 but should read 20.9, offset = 20.9 - 21.5 = -0.6
    # If sensor reads 20.3 but should read 20.9, offset = 20.9 - 20.3 = +0.6
    return expected_afr - measured_afr


def is_calibrated(afr: float) -> bool:
    """Check if AFR reading is within acceptable range."""
    return ACCEPTABLE_RANGE[0] <= afr <= ACCEPTABLE_RANGE[1]


def get_status_color(afr: float) -> str:
    """Get color based on how close to expected free air AFR."""
    if is_calibrated(afr):
        return Colors.GREEN
    elif abs(afr - EXPECTED_FREE_AIR_AFR) < 1.0:
        return Colors.YELLOW
    else:
        return Colors.RED


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"

    print(f"""
{Colors.BOLD}{"=" * 70}
               AFR SENSOR CALIBRATION TOOL
{"=" * 70}{Colors.RESET}

{Colors.CYAN}Port:{Colors.RESET} {port}

{Colors.BOLD}CALIBRATION PROCEDURE:{Colors.RESET}

{Colors.YELLOW}⚠ IMPORTANT - Before Starting:{Colors.RESET}
  1. {Colors.BOLD}REMOVE BOTH SENSORS FROM EXHAUST{Colors.RESET} (free air)
  2. Ensure sensors are powered (engine running or bench power)
  3. Wait 30-60 seconds for sensors to warm up completely
  4. Sensors should be in clean, ambient air (not near exhaust fumes)

{Colors.BOLD}Expected Reading:{Colors.RESET}
  Free Air AFR: {Colors.GREEN}{EXPECTED_FREE_AIR_AFR} ± 0.4{Colors.RESET} (atmospheric oxygen content)
  
  {Colors.GREEN}✓ Good:{Colors.RESET}     {ACCEPTABLE_RANGE[0]} - {ACCEPTABLE_RANGE[1]} AFR (no calibration needed)
  {Colors.YELLOW}~ Close:{Colors.RESET}    Within 1.0 AFR (minor calibration recommended)
  {Colors.RED}✗ Bad:{Colors.RESET}      Outside 1.0 AFR (calibration required)

{Colors.BOLD}Press Ctrl+C at any time to cancel{Colors.RESET}
{"─" * 70}
""")

    input(
        f"{Colors.BOLD}Press ENTER when sensors are in free air and warmed up...{Colors.RESET} "
    )

    # Store samples for each channel
    samples = {1: [], 2: []}

    def on_sample(sample):
        if len(samples[sample.channel]) < SAMPLE_COUNT:
            samples[sample.channel].append(sample.afr)

            # Progress indicator
            ch1_progress = len(samples[1])
            ch2_progress = len(samples[2])
            print(
                f"\r{Colors.CYAN}Collecting samples...{Colors.RESET} "
                f"CH1: [{ch1_progress}/{SAMPLE_COUNT}] "
                f"CH2: [{ch2_progress}/{SAMPLE_COUNT}]",
                end="",
                flush=True,
            )

    try:
        # Connect without loading calibration (we want raw readings)
        client = InnovateClient(port=port, device_type=InnovateDeviceType.DLG1)

        print(f"\n{Colors.YELLOW}Connecting to DLG-1...{Colors.RESET}")
        if not client.connect():
            print(f"\n{Colors.RED}[ERROR] Failed to connect to {port}{Colors.RESET}")
            print("\nTroubleshooting:")
            print("  - Check COM port is correct")
            print("  - Close any other programs using the port (LM Programmer, etc.)")
            print("  - Verify device is powered on and USB connected")
            return 1

        print(f"{Colors.GREEN}[OK] Connected!{Colors.RESET}\n")
        print(
            f"{Colors.BOLD}Collecting {SAMPLE_COUNT} samples from each sensor...{Colors.RESET}"
        )

        # Start streaming both channels
        client.start_streaming(callback=on_sample, channels=[1, 2])

        # Wait for all samples to be collected
        start_time = time.time()
        timeout = 60  # 60 second timeout

        while len(samples[1]) < SAMPLE_COUNT or len(samples[2]) < SAMPLE_COUNT:
            time.sleep(SAMPLE_INTERVAL)

            if time.time() - start_time > timeout:
                print(
                    f"\n{Colors.RED}[ERROR] Timeout waiting for samples{Colors.RESET}"
                )
                print("Check that sensors are connected and transmitting data")
                client.stop_streaming()
                client.disconnect()
                return 1

        # Stop streaming
        client.stop_streaming()
        client.disconnect()

        print(f"\n\n{Colors.GREEN}[OK] Sample collection complete!{Colors.RESET}\n")
        print("─" * 70)

        # Analyze results
        results = {}
        for channel in [1, 2]:
            if len(samples[channel]) == 0:
                print(f"{Colors.RED}Channel {channel}: No data received{Colors.RESET}")
                continue

            avg_afr = mean(samples[channel])
            std_afr = stdev(samples[channel]) if len(samples[channel]) > 1 else 0.0
            min_afr = min(samples[channel])
            max_afr = max(samples[channel])
            offset = calculate_offset(avg_afr)

            results[channel] = {
                "average": avg_afr,
                "std_dev": std_afr,
                "min": min_afr,
                "max": max_afr,
                "offset": offset,
                "calibrated": is_calibrated(avg_afr),
            }

            # Print results
            status_color = get_status_color(avg_afr)
            status = "✓ CALIBRATED" if is_calibrated(avg_afr) else "✗ NEEDS CALIBRATION"

            print(
                f"{Colors.BOLD}Channel {channel} (Sensor {'A' if channel == 1 else 'B'}):{Colors.RESET}"
            )
            print(
                f"  Measured AFR: {status_color}{avg_afr:.2f} ± {std_afr:.2f}{Colors.RESET} (min: {min_afr:.2f}, max: {max_afr:.2f})"
            )
            print(
                f"  Expected AFR: {Colors.GREEN}{EXPECTED_FREE_AIR_AFR}{Colors.RESET}"
            )
            print(
                f"  Error: {status_color}{avg_afr - EXPECTED_FREE_AIR_AFR:+.2f} AFR{Colors.RESET}"
            )
            print(f"  Status: {status_color}{status}{Colors.RESET}")

            if not is_calibrated(avg_afr):
                print(
                    f"  {Colors.YELLOW}Recommended offset: {offset:+.2f} AFR{Colors.RESET}"
                )
            else:
                print(f"  {Colors.GREEN}No offset needed{Colors.RESET}")

            print()

        # Check if calibration is needed
        needs_calibration = any(not r["calibrated"] for r in results.values())

        if not needs_calibration:
            print(
                f"{Colors.GREEN}{Colors.BOLD}🎉 All sensors are properly calibrated!{Colors.RESET}"
            )
            print(f"{Colors.GREEN}No calibration file changes needed.{Colors.RESET}\n")
            return 0

        print("─" * 70)
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠ Calibration Recommended{Colors.RESET}\n")

        # Ask user if they want to apply calibration
        response = input(
            f"{Colors.BOLD}Apply calibration offsets to config file? (y/n):{Colors.RESET} "
        ).lower()

        if response != "y":
            print(
                f"\n{Colors.YELLOW}Calibration cancelled. No changes made.{Colors.RESET}"
            )
            print(f"\nTo manually apply offsets, edit: config/afr_calibration.json")
            for ch, data in results.items():
                if not data["calibrated"]:
                    print(f'  Channel {ch}: "offset_afr": {data["offset"]:.2f}')
            return 0

        # Load calibration file
        config_dir = Path(__file__).parent.parent / "config"
        cal_file = config_dir / "afr_calibration.json"

        if not cal_file.exists():
            print(
                f"{Colors.RED}[ERROR] Calibration file not found: {cal_file}{Colors.RESET}"
            )
            return 1

        with open(cal_file, "r") as f:
            cal_data = json.load(f)

        # Update offsets
        for channel, data in results.items():
            ch_str = str(channel)
            if ch_str in cal_data["channels"]:
                cal_data["channels"][ch_str]["offset_afr"] = round(data["offset"], 2)
                cal_data["channels"][ch_str]["last_free_air_reading"] = round(
                    data["average"], 2
                )
                cal_data["channels"][ch_str]["calibration_date"] = (
                    datetime.now().isoformat()
                )

        cal_data["last_calibrated"] = datetime.now().isoformat()

        # Save calibration file
        with open(cal_file, "w") as f:
            json.dump(cal_data, f, indent=2)

        print(f"\n{Colors.GREEN}[OK] Calibration saved to {cal_file}{Colors.RESET}")
        print(f"\n{Colors.BOLD}Applied Offsets:{Colors.RESET}")
        for ch, data in results.items():
            print(f"  Channel {ch}: {data['offset']:+.2f} AFR")

        print(f"\n{Colors.CYAN}{Colors.BOLD}Next Steps:{Colors.RESET}")
        print(f"  1. Reinstall sensors in exhaust")
        print(f"  2. Restart DynoAI to load new calibration")
        print(f"  3. Verify readings with calibration_monitor.py")
        print()

        return 0

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Calibration cancelled by user{Colors.RESET}")
        return 0
    except Exception as e:
        print(f"\n{Colors.RED}[ERROR] {e}{Colors.RESET}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    # Enable ANSI colors on Windows
    if sys.platform == "win32":
        os.system("")  # Enables ANSI escape sequences

    sys.exit(main())
