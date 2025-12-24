#!/usr/bin/env python3
"""
Find 22.4 AFR in the MTS packet.
Packet pattern: b2 84 47 13 01 51 (repeating)
"""

import struct

packet_hex = "b2844713015147130151"
packet = bytes.fromhex(packet_hex)

print("=" * 60)
print("Finding AFR 22.4 in MTS Packet")
print("=" * 60)
print(f"\nPacket: {' '.join(f'{b:02x}' for b in packet)}")
print(f"Decimal: {' '.join(f'{b:3d}' for b in packet)}")

# MTS protocol insight: packets often have:
# - Sync/header byte(s)
# - Channel data (AFR, Lambda, status)
# - Checksum or terminator

# Looking at the pattern: b2 84 47 13 01 51
# This repeats, suggesting it's a complete packet for both sensors

print("\n" + "-" * 60)
print("Hypothesis: b2 = header, then channel data")
print("-" * 60)

# If b2 is header, data starts at byte 1
data_bytes = packet[1:]
print(f"\nData bytes (skip b2): {' '.join(f'{b:02x}' for b in data_bytes)}")
print(f"Decimal: {' '.join(f'{b:3d}' for b in data_bytes)}")

# Try: 84 47 = Sensor A, 13 01 = Sensor B, 51 = checksum?
print("\n[Test 1] 84 47 = Sensor A, 13 01 = Sensor B")
s1_be = int.from_bytes(bytes([0x84, 0x47]), "big")
s1_le = int.from_bytes(bytes([0x84, 0x47]), "little")
s2_be = int.from_bytes(bytes([0x13, 0x01]), "big")
s2_le = int.from_bytes(bytes([0x13, 0x01]), "little")

print(
    f"  Sensor A (84 47): BE={s1_be} ({s1_be / 10:.1f}), LE={s1_le} ({s1_le / 10:.1f})"
)
print(
    f"  Sensor B (13 01): BE={s2_be} ({s2_be / 10:.1f}), LE={s2_le} ({s2_le / 10:.1f})"
)

# Try different divisions
for div in [1, 10, 100, 128, 256]:
    afr_a = s1_be / div
    afr_b = s2_be / div
    if 20 <= afr_a <= 25:
        print(f"  >>> MATCH A: {afr_a:.2f} AFR (BE /{div})")
    if 20 <= afr_b <= 25:
        print(f"  >>> MATCH B: {afr_b:.2f} AFR (BE /{div})")

# Try Lambda encoding
print("\n[Test 2] Lambda * 100 encoding")
for b in data_bytes:
    lambda_val = b / 100.0
    afr_from_lambda = lambda_val * 14.7
    if 20 <= afr_from_lambda <= 25:
        print(
            f"  Byte 0x{b:02x} ({b}): Lambda={lambda_val:.2f}, AFR={afr_from_lambda:.1f}"
        )

# Try special MTS format: 2 bytes per channel with status bits
print("\n[Test 3] MTS format with status bits")
# Format might be: [status_bits][afr_high][afr_low]
# Or: [afr_with_status_in_high_bits]

# 0x84 = 10000100 binary
# If top 4 bits are status: 1000 = 8
# Bottom 12 bits for data: 0100 0100 0111 = 0x447 = 1095
val_12bit = ((0x84 & 0x0F) << 8) | 0x47
print(f"  12-bit from 84 47: {val_12bit} = {val_12bit / 10:.1f} AFR")

# Try: top 3 bits status, 13 bits data
val_13bit = ((0x84 & 0x1F) << 8) | 0x47
print(f"  13-bit from 84 47: {val_13bit} = {val_13bit / 10:.1f} AFR")

# Maybe it's scaled differently - try /128 (7-bit fraction)
val_scaled = s1_be / 128.0
print(f"  Scaled /128: {val_scaled:.2f}")

# Or maybe Lambda * 10000
lambda_10k = s1_be / 10000.0
afr_10k = lambda_10k * 14.7
print(f"  Lambda*10000: {lambda_10k:.4f} -> AFR={afr_10k:.1f}")

print("\n" + "=" * 60)
