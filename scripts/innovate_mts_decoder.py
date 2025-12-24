#!/usr/bin/env python3
"""
Live decoder for Innovate DLG-1 MTS stream (COM5 by default).

Finds sync bytes (0xB2 0x84), parses 10-byte frames, and extracts AFR for
channel 1 and 2 using several candidate formulas. Best-guess AFR is chosen
from plausible candidates (7–25 AFR) with a preference for the 7-bit-packed
value scaled by 409.6 (matches observed DLG-1 stream like 0x47 0x13 -> ~22 AFR).

Usage examples:
  python scripts/innovate_mts_decoder.py --port COM5 --duration 5
  python scripts/innovate_mts_decoder.py --port COM5 --max-packets 50 --quiet
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import deque
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

try:
    import serial
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    print("pyserial is required. Install with: pip install pyserial", file=sys.stderr)
    raise SystemExit(1) from exc


SYNC0 = 0xB2
SYNC1 = 0x84
FRAME_LEN = 10  # B2 84 + 4 bytes ch1 + 4 bytes ch2
AFR_MIN, AFR_MAX = 7.0, 25.0


@dataclass
class ChannelDecode:
    """Decoded AFR for a single channel."""

    afr: Optional[float]
    candidates: List[Tuple[str, float]]


@dataclass
class Frame:
    """Decoded MTS frame."""

    ch1: ChannelDecode
    ch2: ChannelDecode
    raw: bytes


def best_candidate(candidates: Iterable[Tuple[str, float]]) -> Optional[Tuple[str, float]]:
    """Pick the first candidate in range 7–25 AFR."""
    for label, val in candidates:
        if AFR_MIN <= val <= AFR_MAX:
            return label, val
    return None


def decode_channel(ch_bytes: bytes) -> ChannelDecode:
    """Decode a 4-byte channel block."""
    b0, b1, b2, b3 = ch_bytes

    # Candidate formulas (ordered by preference)
    candidates: List[Tuple[str, float]] = []

    # 7-bit packed (two bytes), scale to AFR (empirically close to 22.4 at 0x47 0x13)
    val_7b = ((b0 & 0x7F) << 7) | (b1 & 0x7F)
    candidates.append(("7bit/409.6", val_7b / 409.6))
    candidates.append(("7bit/400.0", val_7b / 400.0))

    # 16-bit interpretations of first word
    be = (b0 << 8) | b1
    le = (b1 << 8) | b0
    candidates.append(("BE/10", be / 10.0))
    candidates.append(("LE/10", le / 10.0))
    candidates.append(("BE/100", be / 100.0))
    candidates.append(("LE/100", le / 100.0))

    # 16-bit interpretations of second word
    be2 = (b2 << 8) | b3
    le2 = (b3 << 8) | b2
    candidates.append(("BE2/10", be2 / 10.0))
    candidates.append(("LE2/10", le2 / 10.0))
    candidates.append(("BE2/100", be2 / 100.0))
    candidates.append(("LE2/100", le2 / 100.0))

    choice = best_candidate(candidates)
    afr = choice[1] if choice else None
    return ChannelDecode(afr=afr, candidates=candidates)


def decode_frame(frame: bytes) -> Optional[Frame]:
    """Decode a single 10-byte frame starting with sync bytes."""
    if len(frame) != FRAME_LEN or frame[0] != SYNC0 or frame[1] != SYNC1:
        return None
    ch1 = decode_channel(frame[2:6])
    ch2 = decode_channel(frame[6:10])
    return Frame(ch1=ch1, ch2=ch2, raw=frame)


def iter_frames(stream: bytes) -> Iterable[bytes]:
    """Yield aligned 10-byte frames from a raw byte stream."""
    i = 0
    while i <= len(stream) - FRAME_LEN:
        if stream[i] == SYNC0 and stream[i + 1] == SYNC1:
            yield stream[i : i + FRAME_LEN]
            i += FRAME_LEN
        else:
            i += 1


def run_live(port: str, baud: int, duration: float, max_packets: int, quiet: bool) -> None:
    print(f"[live] port={port} baud={baud} duration={duration}s max_packets={max_packets or '∞'}")

    frames: List[Frame] = []
    buffer = bytearray()
    end_time = time.time() + duration

    with serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.05,
    ) as ser:
        while time.time() < end_time and (max_packets == 0 or len(frames) < max_packets):
            waiting = ser.in_waiting
            if waiting:
                buffer.extend(ser.read(waiting))

                # Parse any complete frames now present
                for frame_bytes in list(iter_frames(buffer)):
                    frame = decode_frame(frame_bytes)
                    if frame:
                        frames.append(frame)
                        if not quiet:
                            print_frame(frame, len(frames))
                    # Drop consumed bytes from buffer
                    start_idx = buffer.find(frame_bytes)
                    if start_idx != -1:
                        del buffer[: start_idx + FRAME_LEN]

            time.sleep(0.01)

    summarize(frames)


def print_frame(frame: Frame, idx: int) -> None:
    ch1 = frame.ch1.afr
    ch2 = frame.ch2.afr
    ch1_txt = f"{ch1:.2f}" if ch1 is not None else "n/a"
    ch2_txt = f"{ch2:.2f}" if ch2 is not None else "n/a"
    print(f"[{idx:04d}] CH1={ch1_txt} AFR  CH2={ch2_txt} AFR  raw={frame.raw.hex()}")


def summarize(frames: List[Frame]) -> None:
    if not frames:
        print("[summary] no frames decoded")
        return

    def avg(values: Iterable[Optional[float]]) -> Optional[float]:
        vals = [v for v in values if v is not None]
        return sum(vals) / len(vals) if vals else None

    ch1_avg = avg(f.ch1.afr for f in frames)
    ch2_avg = avg(f.ch2.afr for f in frames)
    print("\n[summary]")
    print(f"  frames: {len(frames)}")
    if ch1_avg is not None:
        print(f"  CH1 avg AFR: {ch1_avg:.2f}")
    else:
        print("  CH1 avg AFR: n/a")
    if ch2_avg is not None:
        print(f"  CH2 avg AFR: {ch2_avg:.2f}")
    else:
        print("  CH2 avg AFR: n/a")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Decode Innovate DLG-1 MTS stream.")
    p.add_argument("--port", default="COM5", help="Serial port (default: COM5)")
    p.add_argument("--baudrate", type=int, default=19200, help="Baud rate (default: 19200)")
    p.add_argument("--duration", type=float, default=5.0, help="Duration to read seconds")
    p.add_argument("--max-packets", type=int, default=0, help="Stop after N packets (0 = unlimited)")
    p.add_argument("--quiet", action="store_true", help="Suppress per-frame output; show summary only")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    run_live(
        port=args.port,
        baud=args.baudrate,
        duration=args.duration,
        max_packets=args.max_packets,
        quiet=args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

