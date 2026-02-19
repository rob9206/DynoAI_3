#!/usr/bin/env python3
"""
JETDRIVE Protocol Discovery Tool

Listens for UDP multicast traffic to discover JETDRIVE data format.
JETDRIVE is an open industry standard for dyno data sharing.

Common multicast addresses to try:
- 224.0.0.x - Local network control
- 239.x.x.x - Administratively scoped

Usage:
    python jetdrive_discover.py --interface 127.0.0.1
"""

import argparse
import json
import socket
import struct
import time
from datetime import datetime

# Common multicast addresses to scan
MULTICAST_ADDRESSES = [
    "224.0.0.1",  # All hosts
    "224.0.0.251",  # mDNS
    "224.0.1.0",  # Common app range
    "239.0.0.1",  # Admin scoped
    "239.192.0.1",  # Local scope
    "239.255.0.1",  # Site-local
    "239.255.255.250",  # SSDP
]

# Common ports for data streaming
PORTS_TO_SCAN = [5000, 5001, 5002, 5003, 5100, 5555, 6000, 6666, 7000, 8000, 8888, 9000]


def create_multicast_socket(
    multicast_group: str, port: int, interface: str = "0.0.0.0"
):
    """Create a socket to receive multicast traffic."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
        pass  # Not available on Windows

    sock.bind(("", port))

    # Join multicast group
    mreq = struct.pack(
        "4s4s", socket.inet_aton(multicast_group), socket.inet_aton(interface)
    )
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.settimeout(2.0)

    return sock


def listen_for_data(multicast_group: str, port: int, interface: str, duration: int = 5):
    """Listen for multicast data on a specific group/port."""
    try:
        sock = create_multicast_socket(multicast_group, port, interface)
        print(f"  Listening on {multicast_group}:{port}...", end=" ", flush=True)

        start_time = time.time()
        packets = []

        while time.time() - start_time < duration:
            try:
                data, addr = sock.recvfrom(4096)
                packets.append(
                    {
                        "source": addr,
                        "size": len(data),
                        "data": data[:100].hex(),  # First 100 bytes
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                print(f"✓ Got {len(data)} bytes from {addr}")
            except socket.timeout:
                pass

        sock.close()

        if not packets:
            print("No data")

        return packets

    except Exception as e:
        print(f"Error: {e}")
        return []


def scan_for_jetdrive(interface: str = "0.0.0.0"):
    """Scan common multicast addresses/ports for JETDRIVE traffic."""
    print("=" * 60)
    print("JETDRIVE Protocol Discovery")
    print("=" * 60)
    print(f"Interface: {interface}")
    print(
        f"Scanning {len(MULTICAST_ADDRESSES)} multicast groups x {len(PORTS_TO_SCAN)} ports"
    )
    print()

    found_streams = []

    for addr in MULTICAST_ADDRESSES:
        for port in PORTS_TO_SCAN:
            packets = listen_for_data(addr, port, interface, duration=1)
            if packets:
                found_streams.append(
                    {"multicast_group": addr, "port": port, "packets": packets}
                )

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)

    if found_streams:
        print(f"Found {len(found_streams)} active streams!")
        for stream in found_streams:
            print(f"\n  Multicast: {stream['multicast_group']}:{stream['port']}")
            for pkt in stream["packets"][:3]:
                print(f"    - {pkt['size']} bytes from {pkt['source']}")
                print(f"      Hex: {pkt['data'][:60]}...")
    else:
        print("No multicast streams found.")
        print("\nTips:")
        print("  1. Make sure JETDRIVE is enabled in Power Core")
        print("  2. Select the correct interface in Power Core's JETDRIVE settings")
        print("  3. Click 'Configure Channels' to enable data channels")
        print("  4. Try selecting 'Loopback' interface in Power Core")

    return found_streams


def listen_continuous(multicast_group: str, port: int, interface: str = "0.0.0.0"):
    """Continuously listen and decode JETDRIVE data."""
    print(f"Listening on {multicast_group}:{port}...")
    print("Press Ctrl+C to stop")
    print()

    sock = create_multicast_socket(multicast_group, port, interface)
    sock.settimeout(None)  # Blocking

    try:
        while True:
            data, addr = sock.recvfrom(4096)
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            # Try to decode as different formats
            print(f"[{timestamp}] {len(data)} bytes from {addr}")

            # Try JSON
            try:
                decoded = json.loads(data.decode("utf-8"))
                print(f"  JSON: {decoded}")
                continue
            except:
                pass

            # Try UTF-8 text
            try:
                text = data.decode("utf-8")
                if text.isprintable():
                    print(f"  Text: {text[:100]}")
                    continue
            except:
                pass

            # Show hex dump
            hex_str = data.hex()
            print(f"  Hex: {hex_str[:80]}{'...' if len(hex_str) > 80 else ''}")

            # Try to decode as floats (common for channel data)
            if len(data) >= 4:
                try:
                    floats = struct.unpack(
                        f"<{len(data) // 4}f", data[: len(data) // 4 * 4]
                    )
                    if all(-1e6 < f < 1e6 for f in floats):  # Sanity check
                        print(f"  Floats: {floats[:10]}...")
                except:
                    pass

            print()

    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JETDRIVE Protocol Discovery")
    parser.add_argument(
        "--interface", "-i", default="0.0.0.0", help="Network interface IP"
    )
    parser.add_argument("--scan", action="store_true", help="Scan for JETDRIVE streams")
    parser.add_argument(
        "--listen",
        "-l",
        help="Listen on specific multicast:port (e.g., 239.0.0.1:5000)",
    )

    args = parser.parse_args()

    if args.listen:
        parts = args.listen.split(":")
        multicast = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 5000
        listen_continuous(multicast, port, args.interface)
    else:
        scan_for_jetdrive(args.interface)
