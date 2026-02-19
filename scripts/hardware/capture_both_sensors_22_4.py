#!/usr/bin/env python3
"""
Capture MTS data with BOTH sensors reading 22.4 AFR.
This will help us decode the packet format.
"""

import time

import serial

port = "COM5"
baudrate = 19200

print("=" * 60)
print("Capturing MTS Data - Both Sensors at 22.4 AFR")
print("=" * 60)

ser = serial.Serial(port, baudrate, timeout=1)

# Clear and start
time.sleep(0.2)
if ser.in_waiting > 0:
    ser.reset_input_buffer()

print("\n[Sending 'G' command...]")
ser.write(b"G")
time.sleep(0.5)

print("\n[Capturing packets...]")
packets = []

for i in range(10):
    if ser.in_waiting > 0:
        data = ser.read(min(ser.in_waiting, 100))
        packets.append(data)
        print(f"\nPacket {i + 1}: {len(data)} bytes")
        print(f"  Hex: {data.hex()}")

        # Show first packet in detail
        if i == 0:
            print(f"  Bytes: {' '.join(f'{b:02x}' for b in data[:30])}")
            print(f"  Decimal: {' '.join(f'{b:3d}' for b in data[:30])}")
    time.sleep(0.3)

ser.close()

# Analyze the pattern
if packets:
    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)

    # Find the repeating pattern
    first_packet = packets[0]
    print(f"\nFirst packet: {first_packet.hex()}")

    # Look for 224 (0xE0) or patterns that repeat
    print("\nLooking for value 224 (22.4 * 10):")
    for i in range(len(first_packet) - 1):
        val_be = int.from_bytes(first_packet[i: i + 2], "big")
        val_le = int.from_bytes(first_packet[i: i + 2], "little")

        if val_be == 224:
            print(
                f"  FOUND at byte {i}: 0x{first_packet[i]:02x}{first_packet[i + 1]:02x} (big-endian)"
            )
        if val_le == 224:
            print(
                f"  FOUND at byte {i}: 0x{first_packet[i]:02x}{first_packet[i + 1]:02x} (little-endian)"
            )

        # Also check /10 for values around 22.4
        if 21.0 <= val_be / 10 <= 24.0:
            print(f"  Possible at byte {i}: {val_be} /10 = {val_be / 10:.1f} (BE)")
        if 21.0 <= val_le / 10 <= 24.0:
            print(f"  Possible at byte {i}: {val_le} /10 = {val_le / 10:.1f} (LE)")

    # Compare with previous pattern (when only one sensor worked)
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)
    print("Previous (Sensor A=22.4, B=off): b2 84 47 13 01 51")
    print(f"Current  (Both=22.4):            {first_packet[:6].hex()}")

    if len(first_packet) >= 6:
        print("\nByte-by-byte comparison:")
        old = bytes.fromhex("b2844713015147130151")
        for i in range(min(6, len(first_packet))):
            old_byte = old[i] if i < len(old) else 0
            new_byte = first_packet[i]
            changed = "CHANGED" if old_byte != new_byte else "same"
            print(f"  Byte {i}: {old_byte:02x} -> {new_byte:02x}  ({changed})")

print("\n" + "=" * 60)
