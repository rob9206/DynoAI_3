#!/usr/bin/env python3
"""
JetDrive listener specifically for the 10.0.0.x network
where Dynoware RT is broadcasting
"""
import socket
import struct
import time

JETDRIVE_PORT = 22344
LISTEN_IFACE = "10.0.0.100"  # Same interface as Dynoware

print("=" * 60)
print(" JetDrive Listener on 10.0.0.100 (Ethernet 3)")
print(" Matching Dynoware RT's multicast interface")
print("=" * 60)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Bind specifically to the 10.0.0.100 interface
try:
    sock.bind(("0.0.0.0", JETDRIVE_PORT))
    print(f"[OK] Bound to 0.0.0.0:{JETDRIVE_PORT}")
except Exception as e:
    print(f"[FAIL] Could not bind: {e}")
    exit(1)

# Join multicast on the SPECIFIC interface (10.0.0.100)
for group in ["239.255.60.60", "224.0.2.10"]:
    try:
        # Use IP_ADD_MEMBERSHIP with specific interface
        mreq = socket.inet_aton(group) + socket.inet_aton(LISTEN_IFACE)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        print(f"[OK] Joined {group} on interface {LISTEN_IFACE}")
    except Exception as e:
        print(f"[FAIL] Could not join {group} on {LISTEN_IFACE}: {e}")

sock.settimeout(1.0)

print("\n" + "=" * 60)
print(" Listening for JetDrive packets from Dynoware RT...")
print(" Dynoware should be broadcasting on Ethernet 3 (10.0.0.100)")
print("=" * 60 + "\n")

start_time = time.time()
timeout = 30
packet_count = 0
sources = {}

while time.time() - start_time < timeout:
    try:
        data, addr = sock.recvfrom(4096)
        packet_count += 1
        source_ip = addr[0]
        
        if source_ip not in sources:
            sources[source_ip] = 0
        sources[source_ip] += 1
        
        # Show all packets
        if len(data) >= 8:
            key = data[0]
            print(f"  [RECV] #{packet_count} from {addr[0]}:{addr[1]} - Key={key}, {len(data)} bytes")
        else:
            print(f"  [RECV] #{packet_count} from {addr[0]}:{addr[1]} - {len(data)} bytes")
            
        if packet_count >= 50:
            break
            
    except socket.timeout:
        elapsed = int(time.time() - start_time)
        print(f"  ... waiting on 10.0.0.100 ({elapsed}s / {timeout}s)", end="\r")

sock.close()

print("\n\n" + "=" * 60)
print(" RESULTS (10.0.0.100 interface)")
print("=" * 60)
print(f"Total packets: {packet_count}")
if sources:
    print("Sources:")
    for ip, count in sources.items():
        print(f"  {ip}: {count} packets")
else:
    print("\n[WARN] No JetDrive packets received on 10.0.0.100!")
    print("\nPossible issues:")
    print("  1. Dynoware RT might not be actively sending (need live data/gauges)")
    print("  2. Try selecting a different interface in Dynoware JetDrive settings")
    print("  3. Check if both apps are on the same physical network adapter")
