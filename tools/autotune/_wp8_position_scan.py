"""Find byte positions of each AFR-related name in a WP8 file.

If an AFR name only appears once near the top of the file, it's probably a
metadata/definition entry. If it appears many times (once per sample or
every N bytes), there's actual time-series data attached.
"""
from __future__ import annotations

import sys
from pathlib import Path


def find_all(haystack: bytes, needle: bytes) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx < 0:
            break
        positions.append(idx)
        start = idx + len(needle)
    return positions


def main() -> int:
    needles = [
        b"AFR 1",
        b"AFR 2",
        b"AFR Front",
        b"AFR Rear",
        b"WBO2 AFR Front",
        b"WBO2 AFR Rear",
        b"WBO2 LAMBDA Front",
        b"WBO2 LAMBDA Rear",
        b"LC2 Volts Petrol AFR2",
        b"Engine RPM",
        b"MAP Rear",
        b"Manifold Absolute Pressure",
    ]

    for arg in sys.argv[1:]:
        p = Path(arg)
        data = p.read_bytes()
        print(f"\n=== {p.name} ({len(data)/1024:.1f} KB) ===")
        file_size = len(data)
        for n in needles:
            positions = find_all(data, n)
            if not positions:
                continue
            first = positions[0]
            last = positions[-1]
            pct_first = 100.0 * first / file_size
            pct_last = 100.0 * last / file_size
            print(
                "  %-28s hits=%3d  first=%d (%.1f%%)  last=%d (%.1f%%)"
                % (n.decode(), len(positions), first, pct_first, last, pct_last)
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
