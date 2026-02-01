#!/usr/bin/env python3
"""
Analyze MTS packet structure to find AFR value.
Packet: b2 84 47 13 01 51 (repeating)
Expected: Sensor A = 22.4 AFR
"""

# The repeating packet
packet_hex = "b2844713015147130151"
packet = bytes.fromhex(packet_hex)

print("=" * 60)
print("MTS Packet Analysis")
print("=" * 60)
print(f"\nPacket: {packet_hex}")
print(f"Bytes: {' '.join(f'{b:02x}' for b in packet)}")
print(f"Decimal: {' '.join(f'{b:3d}' for b in packet)}")
print(f"\nExpected: Sensor A = 22.4 AFR (224 as int/10)")
print(f"          Lambda = 1.52 (22.4/14.7)")

# MTS format is typically: [word1][word2][word3]...
# where each word is 2 bytes

print("\n" + "-" * 60)
print("16-bit word analysis:")
print("-" * 60)

for i in range(0, len(packet) - 1, 2):
    word_be = int.from_bytes(packet[i: i + 2], "big")
    word_le = int.from_bytes(packet[i: i + 2], "little")

    print(f"\nBytes [{i}:{i + 2}]: {packet[i : i + 2].hex()}")
    print(f"  Big-endian:    {word_be:5d} (0x{word_be:04X})")
    print(f"    /10:  {word_be / 10:6.1f}")
    print(f"    /100: {word_be / 100:6.2f}")
    print(f"  Little-endian: {word_le:5d} (0x{word_le:04X})")
    print(f"    /10:  {word_le / 10:6.1f}")
    print(f"    /100: {word_le / 100:6.2f}")

    # Check if close to 22.4
    if 21.0 <= word_be / 10 <= 24.0:
        print(f"  >>> MATCH: {word_be / 10:.1f} AFR (big-endian /10)")
    if 21.0 <= word_le / 10 <= 24.0:
        print(f"  >>> MATCH: {word_le / 10:.1f} AFR (little-endian /10)")
    if 1.4 <= word_be / 100 <= 1.6:
        print(f"  >>> MATCH: {word_be / 100:.2f} Lambda (big-endian /100)")
    if 1.4 <= word_le / 100 <= 1.6:
        print(f"  >>> MATCH: {word_le / 100:.2f} Lambda (little-endian /100)")

# Try 3-byte sequences
print("\n" + "-" * 60)
print("3-byte sequence analysis:")
print("-" * 60)

for i in range(0, len(packet) - 2, 3):
    val = int.from_bytes(packet[i: i + 3], "big")
    print(f"\nBytes [{i}:{i + 3}]: {packet[i : i + 3].hex()}")
    print(f"  Value: {val} (0x{val:06X})")
    print(f"    /10:   {val / 10:.1f}")
    print(f"    /100:  {val / 100:.2f}")
    print(f"    /1000: {val / 1000:.3f}")

print("\n" + "=" * 60)
print("CONCLUSION:")
print("  Looking for value ~224 (for 22.4 AFR)")
print("  or ~152 (for Lambda 1.52)")
print("=" * 60)
