#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick Multicast Discovery Tool for DynoWare RT-150

Listens on multiple multicast addresses simultaneously to discover
which one the dyno is actually broadcasting on.
"""

import socket
import struct
import sys
import threading
import time
from datetime import datetime

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Multicast addresses to test (ordered by likelihood)
MULTICAST_ADDRESSES = [
<<<<<<< Current (Your changes)
    "224.0.2.10",  # Official JetDrive address from vendor
    "239.255.60.60",  # Docker config address
    "224.0.0.1",  # All hosts on subnet
    "239.192.0.1",  # Admin scoped
    "239.255.255.250",  # SSDP
=======
    "224.0.2.10",      # Official JetDrive address from Dynojet vendor (PRIMARY)
    "239.255.60.60",   # Alternative address
    "224.0.0.1",       # All hosts on subnet
    "239.192.0.1",     # Admin scoped
    "239.255.255.250", # SSDP
>>>>>>> Incoming (Background Agent changes)
]

PORT = 22344
INTERFACE = "0.0.0.0"  # Listen on all interfaces
TIMEOUT = 30  # Listen for 30 seconds

results = {}
stop_flag = threading.Event()


def listen_on_address(multicast_group: str, port: int):
    """Listen on a specific multicast address."""
    try:
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind to port
        sock.bind(("", port))

        # Join multicast group
        mreq = struct.pack(
            "4s4s", socket.inet_aton(multicast_group), socket.inet_aton(INTERFACE)
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(1.0)

        print(f"[OK] Listening on {multicast_group}:{port}")

        packet_count = 0
        first_packet_time = None

        while not stop_flag.is_set():
            try:
                data, addr = sock.recvfrom(4096)
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                if packet_count == 0:
                    first_packet_time = timestamp
                    print(f"\n>>> FOUND DATA on {multicast_group}:{port}")
                    print(f"   Source: {addr}")
                    print(f"   First packet at: {timestamp}")
                    print(f"   Packet size: {len(data)} bytes")

                    # Try to show first few bytes
                    hex_preview = data[:32].hex()
                    print(f"   Data preview: {hex_preview}...")

                packet_count += 1

                # Store results
                if multicast_group not in results:
                    results[multicast_group] = {
                        "source": addr,
                        "first_packet": first_packet_time,
                        "packet_count": 0,
                        "packet_size": len(data),
                    }
                results[multicast_group]["packet_count"] = packet_count

            except socket.timeout:
                continue
            except Exception as e:
                if not stop_flag.is_set():
                    print(f"[!] Error on {multicast_group}: {e}")
                break

        sock.close()

        if packet_count > 0:
            print(f"[OK] {multicast_group}: Received {packet_count} packets")

    except Exception as e:
        print(f"[FAIL] Failed to listen on {multicast_group}:{port} - {e}")


def main():
    print("=" * 70)
    print("DynoWare RT-150 Multicast Discovery Tool")
    print("=" * 70)
    print(f"\nTesting {len(MULTICAST_ADDRESSES)} multicast addresses on port {PORT}")
    print(f"Will listen for {TIMEOUT} seconds...\n")

    # Start a thread for each multicast address
    threads = []
    for mcast_addr in MULTICAST_ADDRESSES:
        thread = threading.Thread(
            target=listen_on_address, args=(mcast_addr, PORT), daemon=True
        )
        thread.start()
        threads.append(thread)
        time.sleep(0.1)  # Stagger thread starts

    print(f"\n[*] Listening for {TIMEOUT} seconds...")
    print("[*] Press Ctrl+C to stop early\n")

    try:
        # Wait for timeout or Ctrl+C
        time.sleep(TIMEOUT)
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user")

    # Stop all threads
    print("\n\n[*] Stopping listeners...\n")
    stop_flag.set()

    # Wait for threads to finish
    for thread in threads:
        thread.join(timeout=2.0)

    # Print results
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)

    if results:
        print("\n[SUCCESS] Found data on the following addresses:\n")
        for mcast_addr, info in results.items():
            print(f">> {mcast_addr}:{PORT}")
            print(f"   Source IP:     {info['source'][0]}:{info['source'][1]}")
            print(f"   First packet:  {info['first_packet']}")
            print(f"   Packets:       {info['packet_count']}")
            print(f"   Packet size:   {info['packet_size']} bytes")
            print()

        # Recommendation
        best_address = max(results.keys(), key=lambda k: results[k]["packet_count"])
        print("=" * 70)
        print("RECOMMENDATION")
        print("=" * 70)
        print(f"\n*** Use this multicast address: {best_address} ***\n")
        print("Set in PowerShell:")
        print(f'  $env:JETDRIVE_MCAST_GROUP = "{best_address}"')
        print()

    else:
        print("\n[NO DATA] NO DATA RECEIVED on any multicast address!\n")
        print("Troubleshooting steps:")
        print("  1. Verify DynoWare RT-150 is powered on")
        print("  2. Check that JetDrive is enabled in Power Core software")
        print("  3. Ensure both devices are on the same network subnet")
        print("  4. Check Windows Firewall allows UDP port 22344 inbound")
        print("  5. Try connecting directly with link-local cable (169.254.x.x)")
        print()


if __name__ == "__main__":
    main()
