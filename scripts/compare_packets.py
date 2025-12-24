#!/usr/bin/env python3
"""Compare the two different packets to find what changed."""

old_hex = "b2844713015147130151"
new_hex = "b2845b1300025b130002"

old = bytes.fromhex(old_hex)
new = bytes.fromhex(new_hex)

print("=" * 60)
print("MTS Packet Comparison")
print("=" * 60)
print("\nOld packet (earlier): b2 84 47 13 01 51 47 13 01 51")
print("New packet (now):     b2 84 5b 13 00 02 5b 13 00 02")
print("\nByte-by-byte changes:")

for i in range(min(len(old), len(new))):
    old_b = old[i]
    new_b = new[i]
    change = new_b - old_b
    status = "SAME" if change == 0 else f"CHANGED ({change:+d})"
    print(f"  Byte {i}: 0x{old_b:02x} ({old_b:3d}) -> 0x{new_b:02x} ({new_b:3d})  {status}")

print("\n16-bit word changes:")
for i in range(1, min(len(old), len(new))-1, 2):
    old_w = int.from_bytes(old[i:i+2], 'big')
    new_w = int.from_bytes(new[i:i+2], 'big')
    change = new_w - old_w
    status = "SAME" if change == 0 else f"CHANGED ({change:+d})"
    print(f"  Word @ {i}: 0x{old_w:04x} ({old_w:5d}) -> 0x{new_w:04x} ({new_w:5d})  {status}")

print("\n" + "=" * 60)
print("ANALYSIS")
print("=" * 60)

# The pattern structure
print("\nPacket structure appears to be:")
print("  [b2] [word1] [word2] [word3] [word1] [word2] [word3]")
print("  Header + 3 words repeated twice")
print()
print("  Word 1: 0x8447 -> 0x845b  (changed)")
print("  Word 2: 0x1301 -> 0x1300  (changed)")  
print("  Word 3: 0x5147 -> 0x025b  (changed)")
print()
print("This suggests the data IS changing with AFR!")
print("The values must encode the AFR, we just need the right formula.")

print("\n" + "=" * 60)






