#!/usr/bin/env python3
"""
Simplified JetDrive listener - just listen for ANY UDP on port 22344
"""
import socket
import struct
import time

JETDRIVE_PORT = 22344

print("=" * 60)
print(" Simple JetDrive UDP Listener")
print(" Listening on ALL interfaces for ANY UDP on port 22344")
print("=" * 60)

# Create raw UDP socket (no multicast)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Try to enable broadcast receive
try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print("[OK] Broadcast receive enabled")
except:
    print("[WARN] Could not enable broadcast")

# Bind to all interfaces
sock.bind(("0.0.0.0", JETDRIVE_PORT))
print(f"[OK] Bound to 0.0.0.0:{JETDRIVE_PORT}")

# Also join multicast groups
for group in ["239.255.60.60", "224.0.2.10"]:
    try:
        mreq = struct.pack("4s4s", 
            socket.inet_aton(group),
            socket.inet_aton("0.0.0.0")
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        print(f"[OK] Joined multicast {group}")
    except Exception as e:
        print(f"[WARN] Could not join {group}: {e}")

sock.settimeout(1.0)

print("\n" + "=" * 60)
print(" Waiting for JetDrive packets...")
print(" Make sure Dynoware RT JetDrive is enabled!")
print(" In Dynoware: Settings > JETDRIVE > Enable")
print("=" * 60 + "\n")

start_time = time.time()
timeout = 30  # Listen for 30 seconds
packet_count = 0
sources = {}

while time.time() - start_time < timeout:
    try:
        data, addr = sock.recvfrom(4096)
        packet_count += 1
        source_ip = addr[0]
        
        # Track sources
        if source_ip not in sources:
            sources[source_ip] = 0
        sources[source_ip] += 1
        
        # Skip our own packets (from local IPs)
        local_ips = ["192.168.1.86", "10.0.0.100", "169.254.22.100", "192.168.0.100"]
        if source_ip in local_ips:
            print(f"  [SELF] Packet from {addr} (our own broadcast)")
            continue
        
        # Parse and show external packets
        if len(data) >= 8:
            key = data[0]
            print(f"  [RECV] #{packet_count} from {addr[0]}:{addr[1]} - Key={key}, {len(data)} bytes")
            if key == 2:  # ChannelInfo
                print(f"         ^ This is a ChannelInfo response from the dyno!")
        else:
            print(f"  [RECV] #{packet_count} from {addr[0]}:{addr[1]} - {len(data)} bytes")
            
        if packet_count >= 50:
            break
            
    except socket.timeout:
        elapsed = int(time.time() - start_time)
        print(f"  ... listening ({elapsed}s / {timeout}s) - {packet_count} packets so far", end="\r")

sock.close()

print("\n\n" + "=" * 60)
print(" RESULTS")
print("=" * 60)
print(f"Total packets: {packet_count}")
print(f"Sources:")
for ip, count in sources.items():
    label = "(LOCAL)" if ip in ["192.168.1.86", "10.0.0.100", "169.254.22.100", "192.168.0.100"] else "(EXTERNAL/DYNO)"
    print(f"  {ip}: {count} packets {label}")

if not any(ip not in ["192.168.1.86", "10.0.0.100", "169.254.22.100", "192.168.0.100"] for ip in sources):
    print("\n[WARN] No packets from external sources (dyno)!")
    print("\nCheck in Dynoware RT:")
    print("  1. Go to Settings > JETDRIVE")
    print("  2. Make sure JetDrive is ENABLED")
    print("  3. Select the correct Multicast Interface (try Ethernet 3)")
    print("  4. Click 'Configure Channels' and enable some channels")
    print("  5. Click Apply/OK")
