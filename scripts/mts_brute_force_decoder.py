#!/usr/bin/env python3
"""
Brute force approach to find the encoding that gives us 22.4 AFR.
We know both sensors read 22.4, so the packet MUST contain this value somehow.
"""

packet_hex = "b2844713015147130151"
packet = bytes.fromhex(packet_hex)

target_afr = 22.4
target_lambda = target_afr / 14.7  # 1.524

print("=" * 60)
print("MTS Brute Force Decoder")
print("=" * 60)
print(f"\nTarget: {target_afr} AFR (Lambda {target_lambda:.3f})")
print(f"Packet: {packet_hex}\n")

# Try every possible interpretation
matches = []

# Method 1: Direct byte values with various scalings
print("[1] Testing single byte values...")
for i, b in enumerate(packet):
    for scale in [1, 10, 100, 1000]:
        val = b / scale
        afr = val * 14.7  # Assume it's lambda
        if 21.0 <= afr <= 24.0:
            matches.append(f"  Byte {i} (0x{b:02x}={b}): /{scale} = {val:.3f} Lambda -> {afr:.1f} AFR")

# Method 2: 16-bit words with various scalings
print("\n[2] Testing 16-bit words...")
for i in range(len(packet) - 1):
    word_be = int.from_bytes(packet[i:i+2], 'big')
    word_le = int.from_bytes(packet[i:i+2], 'little')
    
    for scale in [1, 10, 100, 1000, 10000, 128, 256, 512, 1024, 2048]:
        # Big-endian
        val_be = word_be / scale
        afr_be = val_be * 14.7
        if 21.0 <= afr_be <= 24.0:
            matches.append(f"  Bytes {i}-{i+1} (0x{word_be:04x}={word_be}): /{scale} BE = {val_be:.4f} Lambda -> {afr_be:.1f} AFR")
        
        # Little-endian
        val_le = word_le / scale
        afr_le = val_le * 14.7
        if 21.0 <= afr_le <= 24.0:
            matches.append(f"  Bytes {i}-{i+1} (0x{word_le:04x}={word_le}): /{scale} LE = {val_le:.4f} Lambda -> {afr_le:.1f} AFR")

# Method 3: Maybe it's AFR directly, not Lambda
print("\n[3] Testing as direct AFR (not Lambda)...")
for i in range(len(packet) - 1):
    word_be = int.from_bytes(packet[i:i+2], 'big')
    word_le = int.from_bytes(packet[i:i+2], 'little')
    
    for scale in [1, 10, 100, 1000, 10000]:
        afr_be = word_be / scale
        afr_le = word_le / scale
        
        if 21.0 <= afr_be <= 24.0:
            matches.append(f"  Bytes {i}-{i+1} (0x{word_be:04x}={word_be}): /{scale} BE = {afr_be:.1f} AFR (direct)")
        if 21.0 <= afr_le <= 24.0:
            matches.append(f"  Bytes {i}-{i+1} (0x{word_le:04x}={word_le}): /{scale} LE = {afr_le:.1f} AFR (direct)")

# Method 4: Bit-shifted or masked values
print("\n[4] Testing with bit masking...")
for i in range(len(packet) - 1):
    word = int.from_bytes(packet[i:i+2], 'big')
    
    # Try different bit masks (12-bit, 11-bit, 10-bit data)
    for bits in [10, 11, 12, 13]:
        mask = (1 << bits) - 1
        data = word & mask
        
        for scale in [10, 100, 1000]:
            val = data / scale
            afr = val * 14.7
            if 21.0 <= afr <= 24.0:
                matches.append(f"  Bytes {i}-{i+1}: {bits}-bit masked (0x{data:04x}={data}): /{scale} = {val:.3f} Lambda -> {afr:.1f} AFR")

print("\n" + "=" * 60)
print(f"MATCHES FOUND: {len(matches)}")
print("=" * 60)

if matches:
    for match in matches[:20]:  # Show first 20
        print(match)
else:
    print("No matches found!")
    print("\nThe encoding might be:")
    print("  - Custom lookup table")
    print("  - Non-linear scaling")
    print("  - Proprietary format")

print("\n" + "=" * 60)




