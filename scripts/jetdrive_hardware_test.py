#!/usr/bin/env python3
"""
JetDrive Hardware Testing Tool

Comprehensive diagnostic and testing utility for JetDrive/Dynojet hardware integration.
Use this tool to verify connectivity before running autotune sessions.

Features:
- Network interface detection
- Multicast connectivity test
- Provider discovery with timeout
- Channel enumeration
- Live data capture test
- Connection health monitoring

Usage:
    python scripts/jetdrive_hardware_test.py --diagnose
    python scripts/jetdrive_hardware_test.py --discover
    python scripts/jetdrive_hardware_test.py --capture --duration 30
    python scripts/jetdrive_hardware_test.py --monitor
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import socket
import struct
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from synthetic.jetdrive_client import (
    JetDriveConfig,
    JetDriveProviderInfo,
    JetDriveSample,
    discover_providers,
    subscribe,
    DEFAULT_MCAST_GROUP,
    DEFAULT_PORT,
)


# =============================================================================
# Console Output Helpers
# =============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"


def print_header(text: str) -> None:
    """Print a section header."""
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print()


def print_success(text: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {text}")


def print_warning(text: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {text}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {text}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {text}")


# =============================================================================
# Network Diagnostics
# =============================================================================

@dataclass
class NetworkInterface:
    """Represents a network interface."""
    name: str
    ip: str
    is_loopback: bool
    is_up: bool


def get_network_interfaces() -> list[NetworkInterface]:
    """Detect available network interfaces."""
    interfaces = []
    
    try:
        import netifaces
        for iface_name in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface_name)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr.get('addr', '')
                    if ip:
                        interfaces.append(NetworkInterface(
                            name=iface_name,
                            ip=ip,
                            is_loopback=ip.startswith('127.'),
                            is_up=True,
                        ))
    except ImportError:
        # Fallback: use socket to get hostname IP
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            interfaces.append(NetworkInterface(
                name="default",
                ip=ip,
                is_loopback=ip.startswith('127.'),
                is_up=True,
            ))
        except socket.error:
            pass
        
        # Always add loopback
        interfaces.append(NetworkInterface(
            name="loopback",
            ip="127.0.0.1",
            is_loopback=True,
            is_up=True,
        ))
    
    return interfaces


def test_multicast_support(interface_ip: str = "0.0.0.0") -> tuple[bool, str]:
    """Test if multicast is supported on the system."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Try to join multicast group
        mreq = struct.pack(
            "4s4s",
            socket.inet_aton(DEFAULT_MCAST_GROUP),
            socket.inet_aton(interface_ip)
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.close()
        return True, "Multicast join successful"
    except OSError as e:
        return False, f"Multicast error: {e}"
    except Exception as e:
        return False, f"Unknown error: {e}"


def test_port_available(port: int = DEFAULT_PORT) -> tuple[bool, str]:
    """Test if the JetDrive port is available."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", port))
        sock.close()
        return True, f"Port {port} is available"
    except OSError as e:
        return False, f"Port {port} unavailable: {e}"


# =============================================================================
# JetDrive Discovery and Connection
# =============================================================================

async def discover_with_status(
    config: JetDriveConfig,
    timeout: float = 5.0
) -> list[JetDriveProviderInfo]:
    """Discover providers with progress output."""
    print_info(f"Scanning for JetDrive providers on {config.multicast_group}:{config.port}...")
    print_info(f"Timeout: {timeout}s")
    print()
    
    start = time.time()
    providers = await discover_providers(config, timeout=timeout)
    elapsed = time.time() - start
    
    print_info(f"Discovery completed in {elapsed:.1f}s")
    return providers


async def capture_samples(
    provider: JetDriveProviderInfo,
    duration: float,
    output_path: Optional[Path] = None,
    config: JetDriveConfig | None = None,
) -> list[JetDriveSample]:
    """Capture live samples from a provider."""
    samples: list[JetDriveSample] = []
    stop_event = asyncio.Event()
    
    def on_sample(sample: JetDriveSample) -> None:
        samples.append(sample)
        if len(samples) % 100 == 0:
            print(f"\r  Captured {len(samples)} samples...", end="", flush=True)
    
    # Schedule stop after duration
    async def stop_after_duration():
        await asyncio.sleep(duration)
        stop_event.set()
    
    print_info(f"Capturing data for {duration}s...")
    print_info(f"Channels: {list(provider.channels.keys())}")
    print()
    
    stop_task = asyncio.create_task(stop_after_duration())
    
    try:
        await subscribe(
            provider=provider,
            channel_names=[],  # All channels
            on_sample=on_sample,
            config=config,
            stop_event=stop_event,
        )
    except asyncio.CancelledError:
        pass
    finally:
        stop_task.cancel()
    
    print()
    print_info(f"Captured {len(samples)} total samples")
    
    # Save to CSV if path provided
    if output_path and samples:
        save_samples_to_csv(samples, output_path)
    
    return samples


def save_samples_to_csv(samples: list[JetDriveSample], path: Path) -> None:
    """Save captured samples to CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Group samples by timestamp
    timestamps: dict[int, dict[str, float]] = {}
    for s in samples:
        if s.timestamp_ms not in timestamps:
            timestamps[s.timestamp_ms] = {}
        timestamps[s.timestamp_ms][s.channel_name] = s.value
    
    # Get all channel names
    all_channels = sorted(set(s.channel_name for s in samples))
    
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_ms"] + all_channels)
        
        for ts in sorted(timestamps.keys()):
            row = [ts]
            for ch in all_channels:
                row.append(timestamps[ts].get(ch, ""))
            writer.writerow(row)
    
    print_success(f"Saved to {path}")


# =============================================================================
# Diagnostic Commands
# =============================================================================

def run_diagnostics() -> int:
    """Run full system diagnostics."""
    print_header("JetDrive Hardware Diagnostics")
    
    errors = 0
    
    # 1. Check network interfaces
    print(f"{Colors.BOLD}1. Network Interfaces{Colors.RESET}")
    print("-" * 40)
    interfaces = get_network_interfaces()
    if interfaces:
        for iface in interfaces:
            status = "loopback" if iface.is_loopback else "ethernet"
            print(f"   {iface.name}: {iface.ip} ({status})")
        print_success(f"Found {len(interfaces)} network interface(s)")
    else:
        print_error("No network interfaces found")
        errors += 1
    print()
    
    # 2. Check multicast support
    print(f"{Colors.BOLD}2. Multicast Support{Colors.RESET}")
    print("-" * 40)
    print(f"   Multicast Group: {DEFAULT_MCAST_GROUP}")
    
    # Test on each interface
    for iface in interfaces:
        if iface.is_loopback:
            continue
        ok, msg = test_multicast_support(iface.ip)
        if ok:
            print_success(f"{iface.ip}: {msg}")
        else:
            print_warning(f"{iface.ip}: {msg}")
    
    # Also test default
    ok, msg = test_multicast_support("0.0.0.0")
    if ok:
        print_success(f"0.0.0.0 (any): {msg}")
    else:
        print_error(f"0.0.0.0 (any): {msg}")
        errors += 1
    print()
    
    # 3. Check port availability
    print(f"{Colors.BOLD}3. Port Availability{Colors.RESET}")
    print("-" * 40)
    ok, msg = test_port_available(DEFAULT_PORT)
    if ok:
        print_success(msg)
    else:
        print_error(msg)
        errors += 1
    print()
    
    # 4. Check environment configuration
    print(f"{Colors.BOLD}4. Environment Configuration{Colors.RESET}")
    print("-" * 40)
    env_vars = [
        ("JETDRIVE_MCAST_GROUP", DEFAULT_MCAST_GROUP),
        ("JETDRIVE_PORT", str(DEFAULT_PORT)),
        ("JETDRIVE_IFACE", "0.0.0.0"),
    ]
    for var, default in env_vars:
        value = os.getenv(var, default)
        is_default = value == default
        status = "(default)" if is_default else "(custom)"
        print(f"   {var}: {value} {status}")
    print_info("Set environment variables to override defaults")
    print()
    
    # Summary
    print_header("Diagnostic Summary")
    if errors == 0:
        print_success("All diagnostics passed! System is ready for JetDrive.")
        print()
        print("Next steps:")
        print("  1. Ensure Dynojet Power Core is running")
        print("  2. Enable JetDrive in Power Core settings")
        print("  3. Configure channels (RPM, Torque, AFR, etc.)")
        print("  4. Run: python scripts/jetdrive_hardware_test.py --discover")
    else:
        print_error(f"{errors} diagnostic(s) failed")
        print()
        print("Troubleshooting:")
        print("  - Check firewall settings for UDP port 22344")
        print("  - Ensure computer and dyno are on same network")
        print("  - Try disabling VPN if enabled")
    
    return errors


async def run_discovery(timeout: float = 5.0) -> int:
    """Run provider discovery."""
    print_header("JetDrive Provider Discovery")
    
    config = JetDriveConfig.from_env()
    providers = await discover_with_status(config, timeout)
    
    if not providers:
        print_warning("No JetDrive providers found")
        print()
        print("Possible causes:")
        print("  - Dynojet Power Core not running")
        print("  - JetDrive not enabled in Power Core")
        print("  - Wrong network interface")
        print("  - Firewall blocking UDP multicast")
        print()
        print("Try:")
        print("  1. Open Power Core and check JetDrive settings")
        print("  2. Set JETDRIVE_IFACE environment variable to your network IP")
        print("  3. Run with --diagnose to check system configuration")
        return 1
    
    print_success(f"Found {len(providers)} provider(s)")
    print()
    
    for i, provider in enumerate(providers):
        print(f"{Colors.BOLD}Provider {i + 1}: {provider.name}{Colors.RESET}")
        print(f"   ID: 0x{provider.provider_id:04X}")
        print(f"   Host: {provider.host}:{provider.port}")
        print(f"   Channels ({len(provider.channels)}):")
        for chan_id, chan in sorted(provider.channels.items()):
            print(f"      [{chan_id:3d}] {chan.name:20s} (unit={chan.unit})")
        print()
    
    return 0


async def run_capture(duration: float, output_dir: str = "runs") -> int:
    """Run live data capture."""
    print_header("JetDrive Live Capture")
    
    config = JetDriveConfig.from_env()
    
    # First discover providers
    print_info("Discovering providers...")
    providers = await discover_providers(config, timeout=3.0)
    
    if not providers:
        print_error("No JetDrive providers found")
        return 1
    
    provider = providers[0]
    print_success(f"Using provider: {provider.name}")
    print()
    
    # Generate output path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(output_dir) / f"jetdrive_capture_{timestamp}" / "run.csv"
    
    # Capture samples
    samples = await capture_samples(
        provider=provider,
        duration=duration,
        output_path=output_path,
        config=config,
    )
    
    if not samples:
        print_warning("No samples captured")
        print("Check that the dyno is running and generating data")
        return 1
    
    # Print summary
    print()
    print_header("Capture Summary")
    
    # Channel statistics
    channel_counts: dict[str, int] = {}
    channel_values: dict[str, list[float]] = {}
    for s in samples:
        if s.channel_name not in channel_counts:
            channel_counts[s.channel_name] = 0
            channel_values[s.channel_name] = []
        channel_counts[s.channel_name] += 1
        channel_values[s.channel_name].append(s.value)
    
    print(f"{'Channel':<20} {'Samples':>10} {'Min':>12} {'Max':>12} {'Avg':>12}")
    print("-" * 70)
    for ch in sorted(channel_counts.keys()):
        values = channel_values[ch]
        print(f"{ch:<20} {channel_counts[ch]:>10} {min(values):>12.2f} {max(values):>12.2f} {sum(values)/len(values):>12.2f}")
    
    print()
    print_success(f"Capture saved to: {output_path}")
    print()
    print("Next: Run analysis with:")
    print(f"  python scripts/jetdrive_autotune.py --csv {output_path}")
    
    return 0


async def run_monitor() -> int:
    """Run continuous connection monitor."""
    print_header("JetDrive Connection Monitor")
    print("Press Ctrl+C to stop")
    print()
    
    config = JetDriveConfig.from_env()
    last_provider_count = -1
    
    try:
        while True:
            providers = await discover_providers(config, timeout=2.0)
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            if len(providers) != last_provider_count:
                if providers:
                    print(f"[{timestamp}] {Colors.GREEN}Connected{Colors.RESET}: {len(providers)} provider(s)")
                    for p in providers:
                        print(f"           - {p.name} ({len(p.channels)} channels)")
                else:
                    print(f"[{timestamp}] {Colors.YELLOW}Searching...{Colors.RESET}")
                last_provider_count = len(providers)
            else:
                status = f"{Colors.GREEN}OK{Colors.RESET}" if providers else f"{Colors.YELLOW}--{Colors.RESET}"
                print(f"[{timestamp}] Status: {status}", end="\r")
            
            await asyncio.sleep(3.0)
            
    except KeyboardInterrupt:
        print()
        print_info("Monitor stopped")
        return 0


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="JetDrive Hardware Testing Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --diagnose              Run full system diagnostics
  %(prog)s --discover              Discover JetDrive providers
  %(prog)s --capture --duration 60 Capture 60 seconds of data
  %(prog)s --monitor               Monitor connection status

Environment Variables:
  JETDRIVE_MCAST_GROUP  Multicast group (default: 224.0.2.10)
  JETDRIVE_PORT         Port number (default: 22344)
  JETDRIVE_IFACE        Network interface IP (default: 0.0.0.0)
        """
    )
    
    parser.add_argument(
        "--diagnose", "-d",
        action="store_true",
        help="Run full system diagnostics"
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Discover JetDrive providers on the network"
    )
    parser.add_argument(
        "--capture", "-c",
        action="store_true",
        help="Capture live data from JetDrive"
    )
    parser.add_argument(
        "--monitor", "-m",
        action="store_true",
        help="Continuously monitor connection status"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Capture duration in seconds (default: 30)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Discovery timeout in seconds (default: 5)"
    )
    parser.add_argument(
        "--output-dir",
        default="runs",
        help="Output directory for captures (default: runs)"
    )
    
    args = parser.parse_args()
    
    # Default to diagnose if no command specified
    if not any([args.diagnose, args.discover, args.capture, args.monitor]):
        args.diagnose = True
    
    if args.diagnose:
        return run_diagnostics()
    elif args.discover:
        return asyncio.run(run_discovery(args.timeout))
    elif args.capture:
        return asyncio.run(run_capture(args.duration, args.output_dir))
    elif args.monitor:
        return asyncio.run(run_monitor())
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

