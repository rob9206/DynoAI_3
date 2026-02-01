#!/usr/bin/env python3
"""
Dynoware RT Connection Test

Test connectivity to Dynoware RT hardware at the specified IP and port.
Based on your Hardware Manager showing: 192.168.1.115:63391

Usage:
    python scripts/test_dynoware_connection.py
    python scripts/test_dynoware_connection.py --ip 192.168.1.115 --port 63391
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
from datetime import datetime


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
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print()


def print_success(text: str) -> None:
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {text}")


def print_warning(text: str) -> None:
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {text}")


def print_error(text: str) -> None:
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {text}")


def print_info(text: str) -> None:
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {text}")


def test_network_reachability(ip: str, timeout: float = 2.0) -> tuple[bool, str]:
    """Test if the IP is reachable on the network (ICMP-like via UDP)."""
    try:
        # Create a UDP socket to test reachability
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.connect((ip, 1))  # Connect to any port for route lookup
        local_ip = sock.getsockname()[0]
        sock.close()
        return True, f"Route available via local interface {local_ip}"
    except socket.error as e:
        return False, f"Network unreachable: {e}"


def test_tcp_connection(
    ip: str, port: int, timeout: float = 5.0
) -> tuple[bool, str, bytes | None]:
    """Test TCP connection to the Dynoware RT."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        print_info(f"Connecting to {ip}:{port}...")
        start_time = time.time()
        sock.connect((ip, port))
        connect_time = (time.time() - start_time) * 1000

        # Try to receive any initial data
        try:
            sock.settimeout(2.0)
            initial_data = sock.recv(1024)
        except socket.timeout:
            initial_data = None

        sock.close()
        return True, f"Connected successfully in {connect_time:.1f}ms", initial_data

    except socket.timeout:
        return (
            False,
            "Connection timed out - device may be busy or firewall blocking",
            None,
        )
    except ConnectionRefusedError:
        return False, "Connection refused - Dynoware service may not be running", None
    except socket.error as e:
        return False, f"Socket error: {e}", None


def test_port_open(ip: str, port: int, timeout: float = 2.0) -> bool:
    """Quick check if port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except socket.error:
        return False


def run_full_diagnostics(ip: str, port: int) -> int:
    """Run full connection diagnostics."""
    print_header("Dynoware RT Connection Test")

    errors = 0

    # Device info from Hardware Manager
    print(f"{Colors.BOLD}Target Device{Colors.RESET}")
    print("-" * 40)
    print(f"   IP Address:    {ip}")
    print(f"   Port:          {port}")
    print(f"   Protocol:      TCP")
    print(f"   Expected:      Dynoware RT (Model 150)")
    print()

    # 1. Check local network interfaces
    print(f"{Colors.BOLD}1. Local Network Status{Colors.RESET}")
    print("-" * 40)
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print_success(f"Local hostname: {hostname}")
        print_success(f"Local IP: {local_ip}")
    except socket.error as e:
        print_error(f"Could not determine local network: {e}")
        errors += 1
    print()

    # 2. Test network route
    print(f"{Colors.BOLD}2. Network Reachability{Colors.RESET}")
    print("-" * 40)
    ok, msg = test_network_reachability(ip)
    if ok:
        print_success(msg)
    else:
        print_error(msg)
        errors += 1
    print()

    # 3. Test TCP connection
    print(f"{Colors.BOLD}3. TCP Connection Test{Colors.RESET}")
    print("-" * 40)
    ok, msg, data = test_tcp_connection(ip, port)
    if ok:
        print_success(msg)
        if data:
            print_info(f"Received {len(data)} bytes of initial data")
            # Try to decode as ASCII for display
            try:
                decoded = data.decode("ascii", errors="replace")[:100]
                print_info(f"Data preview: {repr(decoded)}")
            except Exception:
                print_info(f"Raw bytes: {data[:50].hex()}")
    else:
        print_error(msg)
        errors += 1
    print()

    # 4. Port scan for related services
    print(f"{Colors.BOLD}4. Related Port Scan{Colors.RESET}")
    print("-" * 40)
    related_ports = [port, 80, 443, 22344, 502]  # Common dyno-related ports
    for p in related_ports:
        if test_port_open(ip, p, timeout=1.0):
            label = ""
            if p == port:
                label = " (Main Dynoware port)"
            elif p == 80:
                label = " (HTTP/Web interface)"
            elif p == 443:
                label = " (HTTPS)"
            elif p == 22344:
                label = " (JetDrive)"
            elif p == 502:
                label = " (Modbus)"
            print_success(f"Port {p} is OPEN{label}")
        else:
            if p == port:
                print_error(f"Port {p} is CLOSED (this is your main port!)")
    print()

    # Summary
    print_header("Connection Summary")
    if errors == 0:
        print_success("All connection tests passed!")
        print()
        print(f"Your Dynoware RT at {ip}:{port} is reachable.")
        print()
        print("Device Details (from Hardware Manager):")
        print("  - Model:        150 (Dynoware RT)")
        print("  - Serial:       RT00220413")
        print("  - Location:     Dawson Dynamics")
        print("  - Firmware:     2.1.7034.17067")
        print()
        print("Next steps:")
        print("  1. Ensure Dynoware RT is in streaming mode")
        print("  2. Use the DynoAI web interface for live data")
        print("  3. Or run JetDrive diagnostics for Power Core integration")
    else:
        print_error(f"{errors} test(s) failed")
        print()
        print("Troubleshooting:")
        print("  1. Verify the Dynoware RT is powered on")
        print("  2. Check network cable connection")
        print("  3. Ensure you're on the same network (192.168.1.x)")
        print("  4. Check Windows Firewall allows port 63391")
        print("  5. Try restarting the Dynoware service")

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Test connection to Dynoware RT dynamometer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          Test default IP 192.168.1.115:63391
  %(prog)s --ip 192.168.1.115       Test specific IP with default port
  %(prog)s --ip 192.168.1.115 --port 63391  Test specific IP and port
        """,
    )

    # Default values from Hardware Manager screenshot
    parser.add_argument(
        "--ip",
        default="192.168.1.115",
        help="Dynoware RT IP address (default: 192.168.1.115)",
    )
    parser.add_argument(
        "--port", type=int, default=63391, help="Dynoware RT port (default: 63391)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Connection timeout in seconds (default: 5)",
    )

    args = parser.parse_args()

    return run_full_diagnostics(args.ip, args.port)


if __name__ == "__main__":
    sys.exit(main())
