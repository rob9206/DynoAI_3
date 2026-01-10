#!/usr/bin/env python3
"""
Simple JetDrive Multicast Test
Tests raw UDP multicast connectivity to Dynoware RT-150
"""
import socket
import struct
import sys
import time

# JetDrive protocol constants
JETDRIVE_PORT = 22344
MULTICAST_GROUPS = [
    "239.255.60.60",   # Standard KLHDV
    "224.0.2.10",      # Alternative Dynojet address
]

def get_local_interfaces():
    """Get list of local IPv4 addresses."""
    interfaces = []
    try:
        # Get all addresses
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                interfaces.append(ip)
    except Exception:
        pass
    
    # Also try common Windows method
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        interfaces.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    
    return list(set(interfaces))

def test_multicast_receive(multicast_group, timeout=10):
    """Test receiving multicast packets on a specific group."""
    print(f"\n{'='*60}")
    print(f"Testing multicast group: {multicast_group}:{JETDRIVE_PORT}")
    print(f"{'='*60}")
    
    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind to all interfaces
        sock.bind(("0.0.0.0", JETDRIVE_PORT))
        print(f"[OK] Bound to 0.0.0.0:{JETDRIVE_PORT}")
        
        # Join multicast group on all interfaces
        mreq = struct.pack("4s4s", 
            socket.inet_aton(multicast_group),
            socket.inet_aton("0.0.0.0")
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        print(f"[OK] Joined multicast group {multicast_group}")
        
        # Set timeout
        sock.settimeout(1.0)
        
        print(f"\nListening for {timeout} seconds...")
        print("(Make sure Dynoware RT is running with JetDrive enabled)\n")
        
        start_time = time.time()
        packet_count = 0
        sources = set()
        
        while time.time() - start_time < timeout:
            try:
                data, addr = sock.recvfrom(4096)
                packet_count += 1
                sources.add(addr[0])
                
                # Parse JetDrive header (first 12 bytes)
                if len(data) >= 12:
                    key, length, host, seq, dest = struct.unpack("<BHHHB", data[:8])
                    print(f"  [OK] Packet #{packet_count} from {addr[0]}:{addr[1]} - "
                          f"Key={key}, Host={host}, Len={len(data)} bytes")
                else:
                    print(f"  [OK] Packet #{packet_count} from {addr[0]}:{addr[1]} - {len(data)} bytes")
                    
                if packet_count >= 20:
                    print(f"\n  ... received {packet_count} packets, stopping")
                    break
                    
            except socket.timeout:
                elapsed = int(time.time() - start_time)
                print(f"  ... waiting ({elapsed}s / {timeout}s)", end="\r")
                continue
        
        sock.close()
        
        print(f"\n\nResults for {multicast_group}:")
        print(f"  Packets received: {packet_count}")
        print(f"  Sources: {sources if sources else 'None'}")
        
        return packet_count > 0, sources
        
    except OSError as e:
        print(f"[FAIL] Error: {e}")
        return False, set()

def send_discovery_request(multicast_group):
    """Send a JetDrive discovery request."""
    print(f"\nSending discovery request to {multicast_group}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # JetDrive RequestChannelInfo message
        # Key=1 (RequestChannelInfo), Host=random, Dest=0xFFFF (broadcast)
        import random
        host_id = random.randint(1, 0xFFFE)
        seq = random.randint(1, 0xFF)
        
        # KLHDV header: Key(1) + Length(2) + Host(2) + Seq(1) + Dest(2) = 8 bytes
        header = struct.pack("<BHHHB", 
            1,      # Key = RequestChannelInfo
            0,      # Length (no payload)
            host_id,
            seq,
            0xFF    # Dest high byte (0xFFFF = all hosts)
        )
        # Add dest low byte
        header += struct.pack("<B", 0xFF)
        
        sock.sendto(header, (multicast_group, JETDRIVE_PORT))
        print(f"[OK] Sent RequestChannelInfo (host={host_id}, seq={seq})")
        sock.close()
        return True
    except Exception as e:
        print(f"[FAIL] Failed to send: {e}")
        return False

def main():
    print("=" * 60)
    print(" JetDrive Multicast Connectivity Test")
    print(" Dynoware RT-150 @ 169.254.187.108")
    print("=" * 60)
    
    # Show local interfaces
    print("\nLocal network interfaces:")
    interfaces = get_local_interfaces()
    for ip in interfaces:
        print(f"  - {ip}")
    
    # Test each multicast group
    results = {}
    for group in MULTICAST_GROUPS:
        # Send discovery request first
        send_discovery_request(group)
        time.sleep(0.5)
        
        # Then listen for responses
        success, sources = test_multicast_receive(group, timeout=8)
        results[group] = (success, sources)
    
    # Summary
    print("\n" + "=" * 60)
    print(" SUMMARY")
    print("=" * 60)
    
    any_success = False
    for group, (success, sources) in results.items():
        status = "[OK] WORKING" if success else "[FAIL] NO PACKETS"
        print(f"  {group}: {status}")
        if success:
            any_success = True
            print(f"    Sources: {sources}")
    
    if not any_success:
        print("\n[WARN] No JetDrive packets received on any multicast group!")
        print("\nTroubleshooting:")
        print("  1. Is Dynoware RT running with JetDrive enabled?")
        print("  2. Check Windows Firewall: allow UDP port 22344 inbound")
        print("  3. Is your computer on the same network as the dyno?")
        print("  4. Try selecting a different interface in Dynoware RT JetDrive settings")
        print("  5. The dyno (169.254.187.108) is on a link-local subnet - ensure")
        print("     your Ethernet adapter has a 169.254.x.x address")
    else:
        print("\n[OK] JetDrive multicast is working!")

if __name__ == "__main__":
    main()
