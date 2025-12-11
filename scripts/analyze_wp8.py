"""Analyze WP8 file structure for reverse engineering."""
import re
import struct
from pathlib import Path

# Find WP8 files
wp8_dir = Path.home() / "OneDrive" / "Documents" / "DynoRuns" / "dyna"
wp8_files = list(wp8_dir.glob("*.wp8"))

if not wp8_files:
    print("No WP8 files found")
    exit(1)

# Use the largest file for analysis
wp8_file = max(wp8_files, key=lambda p: p.stat().st_size)
print(f"Analyzing: {wp8_file.name} ({wp8_file.stat().st_size:,} bytes)")

with open(wp8_file, "rb") as f:
    data = f.read()

print(f"\n=== Header Analysis ===")
print(f"Magic: {data[:4].hex().upper()}")

# Check if it's a protobuf-like format
# FECEFACE suggests a custom format marker
if data[:4] == b"\xfe\xce\xfa\xce":
    print("Format: Dynojet proprietary (FECEFACE marker)")

# Look for readable strings
print(f"\n=== String Extraction ===")
strings = re.findall(rb"[\x20-\x7e]{6,}", data)
print(f"Found {len(strings)} readable strings")

# Categorize strings
channels = []
devices = []
units = []
other = []

for s in strings:
    text = s.decode("ascii", errors="ignore")
    if any(unit in text.lower() for unit in ["rpm", "kpa", "deg", "mph", "%", "volts", "ms"]):
        units.append(text)
    elif "channel" in text.lower() or any(ch in text for ch in ["AFR", "MAP", "TPS", "VE", "RPM"]):
        channels.append(text)
    elif "dyno" in text.lower() or "drum" in text.lower() or "cpu" in text.lower():
        devices.append(text)
    else:
        other.append(text)

print(f"\nDevice-related strings ({len(devices)}):")
for s in devices[:15]:
    print(f"  - {s}")

print(f"\nChannel-related strings ({len(channels)}):")
for s in channels[:15]:
    print(f"  - {s}")

print(f"\nUnit-related strings ({len(units)}):")
for s in units[:15]:
    print(f"  - {s}")

print(f"\nOther strings ({len(other)}):")
for s in other[:15]:
    print(f"  - {s}")

# Hex dump of header
print(f"\n=== Header Hex Dump (first 256 bytes) ===")
for i in range(0, min(256, len(data)), 16):
    chunk = data[i : i + 16]
    hex_str = " ".join(f"{b:02X}" for b in chunk)
    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
    print(f"{i:04X}: {hex_str:<48} {ascii_str}")

# Look for data section markers
print(f"\n=== Looking for data patterns ===")
# Search for float patterns (likely dyno data)
float_candidates = []
for i in range(0, len(data) - 4, 4):
    try:
        val = struct.unpack("<f", data[i : i + 4])[0]
        # Typical dyno values: RPM 0-10000, HP 0-300, Torque 0-200, Speed 0-200
        if 0 < val < 10000 and val == val:  # not NaN
            if i not in [c[0] for c in float_candidates[-10:]]:  # avoid duplicates
                float_candidates.append((i, val))
    except:
        pass

print(f"Found {len(float_candidates)} potential float values")
if float_candidates:
    print("Sample floats (offset, value):")
    for offset, val in float_candidates[:20]:
        print(f"  0x{offset:04X}: {val:.2f}")

# Look for protobuf-like varint patterns
print(f"\n=== Structure Analysis ===")
# Count byte frequencies to understand encoding
freq = {}
for b in data[:5000]:
    freq[b] = freq.get(b, 0) + 1

common_bytes = sorted(freq.items(), key=lambda x: -x[1])[:20]
print("Most common bytes in first 5000:")
for b, count in common_bytes:
    print(f"  0x{b:02X} ({chr(b) if 32 <= b < 127 else '.'}) : {count}")

