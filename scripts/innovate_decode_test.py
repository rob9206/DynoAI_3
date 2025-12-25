#!/usr/bin/env python3
"""
Innovate DLG-1 MTS Protocol Decoder
Based on observed binary stream: b2 84 47 13 01 51...
"""

import struct
import threading
import time

import serial


def decode_innovate_packet(packet):
    """
    Decodes a standard Innovate MTS packet.

    Structure appears to be:
    [Header 2 bytes] [Function 2 bytes] [Value 2 bytes] ...

    Based on standard MTS:
    Header: 0xB2 0x84 (Synchronization)
    Channel Word: 0x47 0x13

    The value is typically AFR * 1000 + 500 or similar depending on fuel type.
    But let's look at the raw bytes: 47 13
    0x4713 = 18195 decimal

    Standard Innovate scaling:
    AFR = (Value * 0.001) + 0.0
    Lambda = (Value * 0.0001) + 0.5

    Let's try to interpret the 0x4713 value.
    """
    if len(packet) < 6:
        return None

    header = packet[0:2]
    # DLG-1 header is typically B2 82 (1 ch) or B2 84 (2 ch?)
    # Observed: B2 84 -> 2 words following?

    # Word 1 (Channel 1)
    # The observed stream has "47 13 01 51" repeated twice.
    # Let's look at standard MTS packet bit layout:
    # Word: [F2 F1 F0 V12 V11 V10 V9 V8] [V7 V6 V5 V4 V3 V2 V1 V0]
    # F2-F0: Function (000 = Normal Operation, 010 = Free Air Cal, etc)
    # V12-V0: Value (13 bits)

    # 0x47 0x13
    # Binary: 0100 0111  0001 0013 (Wait, hex 13 is 0001 0011)
    # 0x47 = 0100 0111
    # 0x13 = 0001 0011

    # If first 3 bits are function:
    # 010 (Function 2 = Free Air Cal?) -> Remaining: 0 0111 0001 0011
    # 13-bit value: 0 0111 0001 0011 -> 0x0713 (1811 decimal)

    # Let's just try to parse it as raw values first.

    raw_val_1 = (packet[2] << 8) | packet[3]

    # Innovate packet usually has high bit set on second byte of word?
    # Actually, Innovate protocol is:
    # Byte 1: 1 0 F2 F1 F0 V9 V8 V7
    # Byte 2: 0 V6 V5 V4 V3 V2 V1 V0

    # Wait, the observed bytes are: 0x47 0x13
    # 0x47 = 0100 0111
    # 0x13 = 0001 0011
    # This doesn't match the "1xxxxxxx 0xxxxxxx" header format of older LC-1.
    # Maybe it's the newer MTS format.

    return {
        "header": header.hex(),
        "raw_1": raw_val_1,
        "raw_2": (packet[4] << 8) | packet[5] if len(packet) >= 6 else None,
    }


def main():
    print("Connecting to COM5...")
    try:
        ser = serial.Serial("COM5", 19200, timeout=1)

        buffer = b""
        print("Listening for MTS packets...")

        while True:
            # Read chunks
            if ser.in_waiting:
                chunk = ser.read(ser.in_waiting)
                buffer += chunk

                # Look for sync header B2 84
                while len(buffer) >= 6:
                    # Find header
                    if buffer[0] != 0xB2 or buffer[1] != 0x84:
                        # Slide window
                        if 0xB2 in buffer:
                            idx = buffer.find(0xB2)
                            buffer = buffer[idx:]
                            if len(buffer) < 2:
                                break
                            if buffer[1] != 0x84:
                                buffer = buffer[1:]
                                continue
                        else:
                            buffer = b""
                            break

                    # We have header at 0
                    if (
                        len(buffer) < 10
                    ):  # Expecting 2 channels (4 bytes each? or 2 bytes each?)
                        # Observed: B2 84 47 13 01 51 47 13 01 51 (Total 10 bytes?)
                        # 47 13 01 51 -> Word 1?
                        break

                    packet = buffer[:10]
                    buffer = buffer[10:]

                    # Decode
                    # 47 13 -> AFR?
                    # 01 51 -> Status?

                    # Let's print raw for analysis
                    print(f"Packet: {packet.hex()}")

                    # Try to interpret 47 13
                    # 0x4713 = 18195
                    # Lambda = (Value + 500) / 1000 ?? -> 18.695?
                    # AFR = Lambda * 14.7 -> 274?? No.

                    # Innovate LC-1 Protocol:
                    # Word is 16 bits.
                    # Top 3 bits function.
                    # Lower 13 bits value.
                    # Value 0..8191 corresponds to Lambda 0.5 .. 1.523
                    # Lambda = (Value / 8192) + 0.5

                    # 0x47 = 01000111
                    # Function = 010 (2) -> Free Air Cal?
                    # Value bits: 00111 00010011 (0x3913 ??)

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nStopped.")
        ser.close()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
