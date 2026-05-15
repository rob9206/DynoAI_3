"""Strict WP8 inspection: pull only printable ASCII strings directly from bytes.

Rather than trusting the reverse-engineered protobuf parser (which produced
artifacts like 'afr1`'), we extract length-prefixed strings conservatively
and report which AFR/MAP/RPM-like names actually appear. Also reports rough
byte-level presence/absence so we can spot when a channel name is real
vs a parser false-positive.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{3,}")

PROBE_TOKENS = [
    b"AFR 1",
    b"AFR 2",
    b"AFR Front",
    b"AFR Rear",
    b"AFR Meas F",
    b"AFR Meas R",
    b"WBO2 F",
    b"WBO2 R",
    b"WBO2 AFR Front",
    b"WBO2 AFR Rear",
    b"WBO2 LAMBDA Front",
    b"WBO2 LAMBDA Rear",
    b"LC2 Volts Petrol AFR1",
    b"LC2 Volts Petrol AFR2",
    b"Engine RPM",
    b"RPM",
    b"MAP",
    b"MAP Front",
    b"MAP Rear",
    b"Manifold Absolute Pressure",
    b"Throttle Position",
    b"Time",
]


def extract_ascii_strings(data: bytes, min_len: int = 4) -> list[str]:
    out: list[str] = []
    for m in PRINTABLE_RE.finditer(data):
        s = m.group().decode("ascii", errors="ignore")
        if len(s) >= min_len:
            out.append(s)
    return out


def keep_channel_like(strings: list[str]) -> list[str]:
    """Heuristic filter: keep strings that look like channel names."""
    keepers: list[str] = []
    seen: set[str] = set()
    for s in strings:
        s_stripped = s.strip()
        if not s_stripped or s_stripped in seen:
            continue

        # Drop obvious garbage: too short, too long, no letters.
        if len(s_stripped) < 3 or len(s_stripped) > 60:
            continue
        if not any(ch.isalpha() for ch in s_stripped):
            continue

        # Keep if it contains useful tokens.
        lower = s_stripped.lower()
        keywords = (
            "afr",
            "lambda",
            "wbo2",
            "wideband",
            "rpm",
            "map",
            "manifold",
            "throttle",
            "engine",
            "spark",
            "knock",
            "target",
            "front",
            "rear",
            "tps",
            "lc-",
            "lc1",
            "lc2",
        )
        if not any(k in lower for k in keywords):
            continue

        keepers.append(s_stripped)
        seen.add(s_stripped)
    return keepers


def main() -> int:
    out_path = Path(__file__).parent / "_wp8_strings.txt"
    report_lines: list[str] = []

    for arg in sys.argv[1:]:
        p = Path(arg)
        data = p.read_bytes()
        report_lines.append(f"\n=== {p.name} ({len(data)/1024:.1f} KB) ===")

        # Exact probe hits.
        hits = [t.decode("ascii") for t in PROBE_TOKENS if t in data]
        report_lines.append(f"  Exact probe hits ({len(hits)}):")
        for h in hits:
            report_lines.append(f"    OK  {h}")
        misses = [t.decode("ascii") for t in PROBE_TOKENS if t not in data]
        report_lines.append(f"  Probe misses ({len(misses)}):")
        for m in misses:
            report_lines.append(f"    --  {m}")

        # Broad keyword scan.
        all_strings = extract_ascii_strings(data, min_len=4)
        channel_like = keep_channel_like(all_strings)
        report_lines.append(f"  Channel-like strings ({len(channel_like)}):")
        for s in channel_like[:80]:
            report_lines.append(f"    * {s}")
        if len(channel_like) > 80:
            report_lines.append(f"    ... {len(channel_like) - 80} more")

    out_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size/1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
