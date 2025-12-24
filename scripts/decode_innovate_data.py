#!/usr/bin/env python3
"""
Decode the Innovate MTS data stream.
Pattern observed: b'\xb2\x84G\x13\x01Q' repeating
"""

import serial
import time
import struct

port = "COM5"
baudrate = 19200

print("=" * 60)
print("Innovate MTS Data Decoder")
print("=" * 60)

ser = serial.Serial(port, baudrate, timeout=1)

# Clear buffer
time.sleep(0.2)
if ser.in_waiting > 0:
    ser.reset_input_buffer()

# Send 'G' command to start streaming
print("\n[Starting stream with 'G' command...]")
ser.write(b'G')
time.sleep(0.5)

print("\n[Decoding data stream...]")
print("Expected: Sensor A = ~22.4 AFR, Sensor B = not working\n")

for i in range(20):  # Read 20 packets
    if ser.in_waiting > 0:
        # Read a chunk
        data = ser.read(min(ser.in_waiting, 100))
        
        # MTS packet structure analysis
        # Pattern: \xb2\x84G\x13\x01Q (6 bytes repeating)
        # Let's try to decode different interpretations
        
        print(f"[Packet {i+1}] {len(data)} bytes")
        
        # Try to find AFR value around 22.4 (224 as int)
        for j in range(len(data) - 1):
            # 16-bit big-endian
            val_be = int.from_bytes(data[j:j+2], 'big')
            afr_be = val_be / 10.0
            if 20.0 <= afr_be <= 25.0:
                print(f"  Byte {j}: AFR = {afr_be:.1f} (16-bit BE, raw={val_be})")
            
            # 16-bit little-endian
            val_le = int.from_bytes(data[j:j+2], 'little')
            afr_le = val_le / 10.0
            if 20.0 <= afr_le <= 25.0:
                print(f"  Byte {j}: AFR = {afr_le:.1f} (16-bit LE, raw={val_le})")
        
        # Show hex for pattern analysis
        if i < 3:  # Only show first 3
            print(f"  Hex: {data.hex()}")
            print(f"  Bytes: {[hex(b) for b in data[:12]]}")
        
    time.sleep(0.3)

ser.close()

print("\n" + "=" * 60)
print("Analysis:")
print("  The device IS streaming data!")
print("  Pattern: repeating 6-byte sequences")
print("  Need to decode the MTS packet format")
print("=" * 60)

