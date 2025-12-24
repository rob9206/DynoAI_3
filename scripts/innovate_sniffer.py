#!/usr/bin/env python3
"""
Innovate Serial Sniffer / Proxy

This script acts as a Man-in-the-Middle (MITM) proxy to sniff serial traffic
between a real Innovate device and the LM Programmer software.

Prerequisites:
1.  A real Innovate device connected to a COM port (e.g., COM3).
2.  A pair of virtual COM ports connected to each other (e.g., COM10 <-> COM11).
    - Windows: Use 'com0com' (Open Source) or similar.
    - Linux: Use 'socat'.

Usage:
    python innovate_sniffer.py --real COM3 --app COM10

Setup:
    1.  Install com0com and create a pair (COM10 <-> COM11).
    2.  Connect your DLG-1 to COM3.
    3.  Run this script: `python innovate_sniffer.py --real COM3 --app COM10`
    4.  Open LM Programmer.
    5.  Select COM11 in LM Programmer (the other end of the virtual pair).
    6.  The script will print all traffic passing between them.

Protocol Notes:
    - Innovate uses 19200 baud, 8N1.
"""

import argparse
import queue
import sys
import threading
import time

import serial

# Thread-safe print
print_lock = threading.Lock()


def log(direction, data):
    timestamp = time.time()
    hex_str = " ".join([f"{b:02X}" for b in data])
    ascii_str = "".join([chr(b) if 32 <= b <= 126 else "." for b in data])

    with print_lock:
        print(
            f"[{timestamp:.3f}] {direction:<10} | HEX: {hex_str:<20} | ASCII: {ascii_str}"
        )


def forward(
    source: serial.Serial,
    destination: serial.Serial,
    direction: str,
    stop_event: threading.Event,
):
    """Forward data from source to destination and log it."""
    try:
        while not stop_event.is_set():
            if source.in_waiting > 0:
                data = source.read(source.in_waiting)
                if data:
                    log(direction, data)
                    destination.write(data)
            else:
                time.sleep(0.001)  # Low latency sleep
    except Exception as e:
        with print_lock:
            print(f"Error in {direction} thread: {e}")
        stop_event.set()


def main():
    parser = argparse.ArgumentParser(description="Innovate Serial Sniffer")
    parser.add_argument(
        "--real", required=True, help="Real COM port (connected to device)"
    )
    parser.add_argument(
        "--app", required=True, help="Application-facing COM port (virtual)"
    )
    parser.add_argument(
        "--baud", type=int, default=19200, help="Baud rate (default 19200)"
    )

    args = parser.parse_args()

    print(f"Opening Real Port: {args.real}")
    print(f"Opening App Port:  {args.app}")
    print("Press Ctrl+C to stop...")

    try:
        real_ser = serial.Serial(args.real, args.baud, timeout=0.1)
        app_ser = serial.Serial(args.app, args.baud, timeout=0.1)

        stop_event = threading.Event()

        # Create threads
        t1 = threading.Thread(
            target=forward, args=(real_ser, app_ser, "DEV -> APP", stop_event)
        )
        t2 = threading.Thread(
            target=forward, args=(app_ser, real_ser, "APP -> DEV", stop_event)
        )

        t1.daemon = True
        t2.daemon = True

        t1.start()
        t2.start()

        while not stop_event.is_set():
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping...")
        stop_event.set()
    except serial.SerialException as e:
        print(f"\nSerial Error: {e}")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if "real_ser" in locals() and real_ser.is_open:
            real_ser.close()
        if "app_ser" in locals() and app_ser.is_open:
            app_ser.close()


if __name__ == "__main__":
    main()
