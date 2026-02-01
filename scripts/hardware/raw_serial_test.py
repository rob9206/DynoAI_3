#!/usr/bin/env python3
"""
Direct serial port test - bypass all parsing to see raw data.
"""

import sys
import time

import serial

port = "COM5"
baudrate = 19200

print("=" * 60)
print(f"Raw Serial Test: {port} @ {baudrate} baud")
print("=" * 60)
print("\nAttempting to connect...")

try:
    ser = serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=1.0,
    )

    print(f"[OK] Connected to {port}")
    print(f"  Baudrate: {baudrate}")
    print(f"  Timeout: {ser.timeout}s")

    # Clear buffer
    if ser.in_waiting > 0:
        ser.reset_input_buffer()
        print("  Cleared input buffer")

    # Try sending wake-up commands
    print("\n[1] Sending wake-up commands...")
    try:
        ser.write(b"\r\n")
        time.sleep(0.1)
        ser.write(b"?\r\n")  # Query command (some devices respond to this)
        time.sleep(0.1)
        print("  Sent: \\r\\n and ?\\r\\n")
    except Exception as e:
        print(f"  Error sending: {e}")

    # Listen for data
    print("\n[2] Listening for data (10 seconds)...")
    print("  Press Ctrl+C to stop early\n")

    start_time = time.time()
    data_received = False
    byte_count = 0

    try:
        while time.time() - start_time < 10:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                data_received = True
                byte_count += len(data)

                # Show raw data in multiple formats
                print(
                    f"\n[{time.time() - start_time:.2f}s] Received {len(data)} bytes:"
                )
                print(f"  Raw bytes: {data!r}")
                print(f"  Hex: {data.hex()}")

                # Try to decode as ASCII
                try:
                    text = data.decode("ascii", errors="replace")
                    if text.strip():
                        print(f"  ASCII: {text!r}")
                except:
                    pass

                # Show as integers
                if len(data) <= 20:
                    ints = [b for b in data]
                    print(f"  Integers: {ints}")
            else:
                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\n[Interrupted by user]")

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Data received: {'YES' if data_received else 'NO'}")
    print(f"  Total bytes: {byte_count}")

    if not data_received:
        print("\n[TROUBLESHOOTING]")
        print("  1. Check device is powered on")
        print("  2. Check device display shows it's active")
        print("  3. Verify correct COM port (check Device Manager)")
        print("  4. Try different baud rates: 9600, 19200, 38400")
        print("  5. Check if device needs LogWorks to be closed first")
        print("  6. Some devices only send data when sensor is active")

    ser.close()
    print("\n[OK] Connection closed")

except serial.SerialException as e:
    print(f"[ERROR] Failed to connect: {e}")
    print("\nPossible issues:")
    print("  - Port already in use (close LogWorks or other apps)")
    print("  - Wrong COM port")
    print("  - Device not connected")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Unexpected error: {e}")
    sys.exit(1)

print("=" * 60)
