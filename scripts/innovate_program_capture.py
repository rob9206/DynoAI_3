#!/usr/bin/env python3
"""
Capture and replay raw Innovate DLG-1 serial frames during LM Programmer
"Program" operations.

Use this to sniff what LogWorks/LM Programmer sends on COM5 when you click
Program. Default baud is 19200 (DLG-1/LC-2). Example:

  python scripts/innovate_program_capture.py capture --port COM5 --duration 8
    # Start the script, arm, then click Program in LM Programmer. The capture
    # is written to capture/innovate_program.bin.

  python scripts/innovate_program_capture.py replay --port COM5 --infile capture/innovate_program.bin
    # Replays the captured bytes back to the device.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    import serial
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    print("pyserial is required. Install with: pip install pyserial", file=sys.stderr)
    raise SystemExit(1) from exc


def hexdump(data: bytes, width: int = 16) -> str:
    """Return a simple hex dump string."""
    lines: list[str] = []
    for i in range(0, len(data), width):
        chunk = data[i : i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        printable = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        lines.append(f"{i:04x}: {hex_part:<{width * 3}} {printable}")
    return "\n".join(lines)


def capture_raw(
    port: str,
    baudrate: int,
    duration: float,
    outfile: Path,
    arm_seconds: int,
    max_bytes: int | None,
    show_hexdump: bool,
) -> int:
    """Capture raw bytes while LM Programmer is running."""
    print(f"[capture] Port={port} baud={baudrate} duration={duration}s")
    print("         Arm window lets you alt-tab to LM Programmer and click Program.")
    for remaining in range(arm_seconds, 0, -1):
        print(f"  Arming in {remaining}...", end="\r", flush=True)
        time.sleep(1)
    print("  Capturing...".ljust(24))

    buffer = bytearray()
    start = time.time()
    last_report = start

    try:
        with serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.05,
        ) as ser:
            while time.time() - start < duration:
                waiting = ser.in_waiting
                if waiting:
                    chunk = ser.read(waiting)
                    if not chunk:
                        continue

                    if max_bytes is not None:
                        remaining_bytes = max_bytes - len(buffer)
                        if remaining_bytes <= 0:
                            print("  [warn] max-bytes reached; stopping early.")
                            break
                        chunk = chunk[:remaining_bytes]

                    buffer.extend(chunk)
                    if show_hexdump:
                        print(hexdump(chunk))

                now = time.time()
                if now - last_report >= 1.0:
                    print(f"  Collected {len(buffer)} bytes...", end="\r")
                    last_report = now

                time.sleep(0.01)

    except serial.SerialException as exc:
        print(f"[error] Serial problem: {exc}", file=sys.stderr)
        return 1

    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_bytes(buffer)

    print(f"\n[capture complete] wrote {len(buffer)} bytes to {outfile}")
    if buffer:
        preview = buffer[: min(64, len(buffer))]
        print("Preview (first bytes):")
        print(hexdump(preview))
    else:
        print("No bytes captured. Ensure LM Programmer sent data during the window.")
    return 0


def replay_raw(port: str, baudrate: int, infile: Path, inter_byte_delay: float) -> int:
    """Replay previously captured bytes back to the device."""
    if not infile.exists():
        print(f"[error] infile not found: {infile}", file=sys.stderr)
        return 1

    data = infile.read_bytes()
    print(f"[replay] Port={port} baud={baudrate} bytes={len(data)}")

    try:
        with serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1,
        ) as ser:
            for b in data:
                ser.write(bytes((b,)))
                if inter_byte_delay > 0:
                    time.sleep(inter_byte_delay)
    except serial.SerialException as exc:
        print(f"[error] Serial problem: {exc}", file=sys.stderr)
        return 1

    print("[replay complete]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture/replay Innovate DLG-1 program-mode traffic."
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    cap = sub.add_parser("capture", help="Capture bytes while clicking Program in LM Programmer.")
    cap.add_argument("--port", default="COM5", help="Serial port (default: COM5).")
    cap.add_argument("--baudrate", type=int, default=19200, help="Baud rate (default: 19200).")
    cap.add_argument("--duration", type=float, default=8.0, help="Capture window in seconds.")
    cap.add_argument(
        "--outfile",
        type=Path,
        default=Path("capture/innovate_program.bin"),
        help="Where to write the capture.",
    )
    cap.add_argument("--arm-seconds", type=int, default=3, help="Countdown before capture starts.")
    cap.add_argument(
        "--max-bytes",
        type=int,
        default=None,
        help="Optional ceiling on bytes to store (prevents runaway).",
    )
    cap.add_argument(
        "--hexdump",
        action="store_true",
        help="Print hex as bytes arrive (verbose).",
    )

    rep = sub.add_parser("replay", help="Replay a captured byte sequence.")
    rep.add_argument("--port", default="COM5", help="Serial port (default: COM5).")
    rep.add_argument("--baudrate", type=int, default=19200, help="Baud rate (default: 19200).")
    rep.add_argument("--infile", type=Path, required=True, help="Captured file to replay.")
    rep.add_argument(
        "--inter-byte-delay",
        type=float,
        default=0.0,
        help="Optional delay (seconds) between bytes on replay.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.mode == "capture":
        return capture_raw(
            port=args.port,
            baudrate=args.baudrate,
            duration=args.duration,
            outfile=args.outfile,
            arm_seconds=args.arm_seconds,
            max_bytes=args.max_bytes,
            show_hexdump=args.hexdump,
        )

    if args.mode == "replay":
        return replay_raw(
            port=args.port,
            baudrate=args.baudrate,
            infile=args.infile,
            inter_byte_delay=args.inter_byte_delay,
        )

    print(f"Unknown mode: {args.mode}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

