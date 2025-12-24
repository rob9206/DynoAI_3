#!/usr/bin/env python3
"""
DLG-1 Calibration Monitor

Real-time monitoring of Innovate DLG-1 sensors during calibration.
Shows both channels with visual feedback for calibration status.

Usage:
    python calibration_monitor.py [COM_PORT]
    
Example:
    python calibration_monitor.py COM5
"""

import sys
import time
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.innovate_client import InnovateClient, InnovateDeviceType


# ANSI colors for terminal output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"


def get_afr_color(afr: float) -> str:
    """Return color based on AFR value."""
    if afr >= 20.0:  # Free air
        return Colors.CYAN
    elif afr >= 15.5:  # Lean
        return Colors.BLUE
    elif afr >= 14.0:  # Stoichiometric zone
        return Colors.GREEN
    elif afr >= 12.0:  # Rich
        return Colors.YELLOW
    else:  # Very rich
        return Colors.RED


def get_calibration_status(afr: float) -> str:
    """Return calibration status based on AFR."""
    if 21.0 <= afr <= 23.0:
        return f"{Colors.GREEN}✓ FREE AIR - CALIBRATED{Colors.RESET}"
    elif afr >= 20.0:
        return f"{Colors.YELLOW}~ FREE AIR - CLOSE{Colors.RESET}"
    elif 14.0 <= afr <= 15.5:
        return f"{Colors.GREEN}● STOICHIOMETRIC{Colors.RESET}"
    elif afr < 14.0:
        return f"{Colors.YELLOW}▼ RICH{Colors.RESET}"
    else:
        return f"{Colors.BLUE}▲ LEAN{Colors.RESET}"


def clear_line():
    """Clear current line in terminal."""
    print("\r" + " " * 80 + "\r", end="")


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    
    print(f"""
{Colors.BOLD}{'=' * 60}
       DLG-1 CALIBRATION MONITOR
{'=' * 60}{Colors.RESET}

{Colors.CYAN}Port:{Colors.RESET} {port}

{Colors.BOLD}Calibration Guide:{Colors.RESET}
  1. Open LM Programmer (Start → LogWorks3 → LM Programmer)
  2. Connect to DLG-1 in LM Programmer
  3. Ensure sensors are in FREE AIR (not in exhaust)
  4. Wait for sensors to heat up (~30 sec)
  5. Click "Free Air Cal" in LM Programmer
  6. Watch values below - should read 21-22 AFR

{Colors.BOLD}Expected Values:{Colors.RESET}
  {Colors.CYAN}Free Air (calibration):{Colors.RESET}  21.0 - 22.5 AFR  (λ ≈ 1.50)
  {Colors.GREEN}Stoichiometric:{Colors.RESET}          14.7 AFR        (λ = 1.00)
  {Colors.YELLOW}Rich:{Colors.RESET}                     10-13 AFR       (λ < 1.00)
  {Colors.BLUE}Lean:{Colors.RESET}                     15-18 AFR       (λ > 1.00)

{Colors.BOLD}Press Ctrl+C to stop monitoring{Colors.RESET}
{'─' * 60}
""")

    # Store latest readings
    latest = {1: None, 2: None}
    sample_count = 0
    start_time = None
    
    def on_sample(sample):
        nonlocal sample_count, start_time
        if start_time is None:
            start_time = time.time()
        
        latest[sample.channel] = sample
        sample_count += 1
        
        # Update display every sample
        ch1 = latest.get(1)
        ch2 = latest.get(2)
        
        elapsed = time.time() - start_time if start_time else 0
        
        # Build display line
        line_parts = [f"{Colors.BOLD}[{elapsed:6.1f}s]{Colors.RESET}"]
        
        if ch1:
            color = get_afr_color(ch1.afr)
            status = get_calibration_status(ch1.afr)
            line_parts.append(
                f"  {Colors.BOLD}CH1/A:{Colors.RESET} {color}{ch1.afr:5.1f} AFR{Colors.RESET} "
                f"(λ={ch1.lambda_value:.3f}) {status}"
            )
        
        if ch2:
            color = get_afr_color(ch2.afr)
            status = get_calibration_status(ch2.afr)
            line_parts.append(
                f"  {Colors.BOLD}CH2/B:{Colors.RESET} {color}{ch2.afr:5.1f} AFR{Colors.RESET} "
                f"(λ={ch2.lambda_value:.3f}) {status}"
            )
        
        # Print on new lines for better readability
        clear_line()
        print("\n".join(line_parts))
    
    try:
        client = InnovateClient(port=port, device_type=InnovateDeviceType.DLG1)
        
        print(f"{Colors.YELLOW}Connecting to DLG-1...{Colors.RESET}")
        if not client.connect():
            print(f"{Colors.RED}[ERROR] Failed to connect to {port}{Colors.RESET}")
            print("\nTroubleshooting:")
            print("  - Check COM port is correct")
            print("  - Close LM Programmer if it's using the port")
            print("  - Check device is powered on")
            return 1
        
        print(f"{Colors.GREEN}[OK] Connected!{Colors.RESET}\n")
        print(f"{Colors.BOLD}Live Readings:{Colors.RESET}")
        print("─" * 60)
        
        # Start streaming both channels
        client.start_streaming(callback=on_sample, channels=[1, 2])
        
        # Monitor until interrupted
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        
        # Stop and disconnect
        client.stop_streaming()
        client.disconnect()
        
        # Final summary
        print(f"\n{'─' * 60}")
        print(f"{Colors.BOLD}Session Summary:{Colors.RESET}")
        print(f"  Total samples: {sample_count}")
        
        if latest[1]:
            print(f"  Final CH1/A: {latest[1].afr:.1f} AFR (λ={latest[1].lambda_value:.3f})")
        if latest[2]:
            print(f"  Final CH2/B: {latest[2].afr:.1f} AFR (λ={latest[2].lambda_value:.3f})")
        
        # Calibration check
        print(f"\n{Colors.BOLD}Calibration Check:{Colors.RESET}")
        for ch, name in [(1, "A"), (2, "B")]:
            if latest[ch]:
                afr = latest[ch].afr
                if 21.0 <= afr <= 23.0:
                    print(f"  Sensor {name}: {Colors.GREEN}✓ CALIBRATED (reading free air correctly){Colors.RESET}")
                elif afr >= 20.0:
                    print(f"  Sensor {name}: {Colors.YELLOW}~ Close - may need fine calibration{Colors.RESET}")
                else:
                    print(f"  Sensor {name}: {Colors.RED}✗ Not in free air or needs calibration{Colors.RESET}")
        
        print(f"\n{Colors.GREEN}[OK] Monitoring stopped{Colors.RESET}")
        return 0
        
    except Exception as e:
        print(f"{Colors.RED}[ERROR] {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    # Enable ANSI colors on Windows
    if sys.platform == "win32":
        os.system("")  # Enables ANSI escape sequences
    
    sys.exit(main())

