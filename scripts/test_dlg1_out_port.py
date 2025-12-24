#!/usr/bin/env python3
"""
Test DLG-1 connected to OUT port.
Should see data streaming with Sensor A reading 22.4 AFR.
"""

import struct
import time

import serial

port = "COM5"
baudrate = 19200

print("=" * 60)
print("DLG-1 OUT Port Test")
print("=" * 60)
print("\nExpected: Sensor A = 22.4 AFR, Sensor B = not working")
print(f"Testing: {port} @ {baudrate} baud\n")

try:
    ser = serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=2.0,
    )

    print(f"[OK] Connected to {port}")

    # Clear buffer
    time.sleep(0.5)
    if ser.in_waiting > 0:
        ser.reset_input_buffer()

    print("\n[Listening for MTS data stream...]")
    print("(The DLG-1 should be continuously sending data)\n")

    start_time = time.time()
    packet_count = 0
    afr_readings = []

    try:
        while time.time() - start_time < 15:
            if ser.in_waiting > 0:
                # Read available data
                data = ser.read(ser.in_waiting)
                packet_count += 1

                print(f"\n[Packet {packet_count}] {len(data)} bytes:")
                print(f"  Hex: {data.hex()}")
                print(f"  Raw: {data!r}")

                # Try to decode as ASCII
                try:
                    text = data.decode("ascii", errors="replace").strip()
                    if text:
                        print(f"  ASCII: {text}")
                except:
                    pass

                # Try to parse as MTS binary
                # DLG-1 typically sends: [header][channel_data][channel_data]...
                # Look for AFR values around 22.4 (224 as int, or 0x00E0 as 16-bit)
                if len(data) >= 2:
                    # Try different interpretations
                    for i in range(len(data) - 1):
                        # 16-bit big-endian (AFR * 10)
                        val_be = int.from_bytes(data[i: i + 2], "big")
                        afr_be = val_be / 10.0
                        if 20.0 <= afr_be <= 25.0:  # Looking for ~22.4
                            print(
                                f"  Possible AFR @ byte {i}: {afr_be:.1f} (big-endian)"
                            )
                            afr_readings.append(afr_be)

                        # 16-bit little-endian
                        val_le = int.from_bytes(data[i: i + 2], "little")
                        afr_le = val_le / 10.0
                        if 20.0 <= afr_le <= 25.0:
                            print(
                                f"  Possible AFR @ byte {i}: {afr_le:.1f} (little-endian)"
                            )
                            afr_readings.append(afr_le)

                # Try 4-byte float
                if len(data) >= 4:
                    for i in range(len(data) - 3):
                        try:
                            afr_f = struct.unpack(">f", data[i: i + 4])[0]
                            if 20.0 <= afr_f <= 25.0:
                                print(
                                    f"  Possible AFR @ byte {i}: {afr_f:.1f} (float BE)"
                                )
                                afr_readings.append(afr_f)
                        except:
                            pass

                        try:
                            afr_f = struct.unpack("<f", data[i: i + 4])[0]
                            if 20.0 <= afr_f <= 25.0:
                                print(
                                    f"  Possible AFR @ byte {i}: {afr_f:.1f} (float LE)"
                                )
                                afr_readings.append(afr_f)
                        except:
                            pass
            else:
                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\n[Interrupted]")

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Packets received: {packet_count}")
    print(f"  AFR readings found: {len(afr_readings)}")

    if afr_readings:
        print(f"\n  AFR values detected:")
        for afr in afr_readings[:10]:  # Show first 10
            print(f"    {afr:.1f}")

        avg_afr = sum(afr_readings) / len(afr_readings)
        print(f"\n  Average: {avg_afr:.1f} (expected ~22.4)")

        if 21.0 <= avg_afr <= 24.0:
            print("\n  [SUCCESS] Data matches expected reading!")
        else:
            print("\n  [WARNING] Values don't match expected 22.4")
    else:
        print("\n  [NO DATA] No AFR values detected")
        print("\n  Troubleshooting:")
        print("    1. Verify cable is in OUT port (not IN port)")
        print("    2. Check device is powered and displaying AFR")
        print("    3. Try different baud rate (9600)")
        print("    4. Device may need specific initialization")

    ser.close()
    print("\n[OK] Test complete")

except serial.SerialException as e:
    print(f"[ERROR] {e}")
    print("\nCheck:")
    print("  - COM port is correct")
    print("  - No other software using the port")
    print("  - Cable is connected to OUT port")

print("=" * 60)
