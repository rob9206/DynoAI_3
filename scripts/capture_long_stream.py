#!/usr/bin/env python3
"""
Capture a longer MTS stream to find different packet types.
"""

import serial
import time
from collections import Counter

port = "COM5"
baudrate = 19200

print("=" * 60)
print("Long MTS Stream Capture")
print("=" * 60)

ser = serial.Serial(port, baudrate, timeout=2)
time.sleep(0.3)
if ser.in_waiting > 0:
    ser.reset_input_buffer()

print("\nSending 'G' command...")
ser.write(b'G')
time.sleep(0.5)

print("Capturing 5 seconds of data...\n")

all_data = b''
packet_headers = []
unique_patterns = set()

start = time.time()
while time.time() - start < 5:
    if ser.in_waiting > 0:
        chunk = ser.read(ser.in_waiting)
        all_data += chunk
        
        # Look for potential packet headers
        for i in range(len(chunk)):
            b = chunk[i]
            if b >= 0xA0 and b <= 0xBF:  # Common MTS header range
                packet_headers.append(b)
                # Capture 10-byte pattern after header
                if i + 10 < len(chunk):
                    pattern = chunk[i:i+10]
                    unique_patterns.add(pattern)
    
    time.sleep(0.1)

ser.close()

print(f"Total bytes received: {len(all_data)}")
print(f"Hex: {all_data[:100].hex()}...")

# Analyze packet headers
if packet_headers:
    header_counts = Counter(packet_headers)
    print(f"\nPacket headers found: {len(packet_headers)}")
    for header, count in header_counts.most_common():
        print(f"  0x{header:02X}: {count} times")

# Show unique patterns
print(f"\nUnique patterns found: {len(unique_patterns)}")
for i, pattern in enumerate(list(unique_patterns)[:10]):
    print(f"  Pattern {i+1}: {pattern.hex()}")

# Look for any changing values
print("\n[Looking for changing values...]")
if len(all_data) >= 100:
    # Compare first and last 20 bytes
    first_20 = all_data[:20]
    last_20 = all_data[-20:]
    print(f"First 20 bytes: {first_20.hex()}")
    print(f"Last 20 bytes:  {last_20.hex()}")
    
    if first_20 == last_20:
        print("  >>> IDENTICAL - Data is static (not changing)")
    else:
        print("  >>> DIFFERENT - Data is changing")
        # Show what changed
        for i in range(min(len(first_20), len(last_20))):
            if first_20[i] != last_20[i]:
                print(f"    Byte {i}: 0x{first_20[i]:02x} -> 0x{last_20[i]:02x}")

print("\n" + "=" * 60)




