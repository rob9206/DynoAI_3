#!/usr/bin/env python3
"""
Protocol sniffer - try to capture what LogWorks sends to initiate streaming.

Based on research:
- LogWorks uses 'G' command to start streaming
- MTS protocol may use specific initialization sequences
"""

import serial
import time
import sys

port = "COM5"
baudrates = [19200, 9600, 38400, 57600]

print("=" * 60)
print("Innovate MTS Protocol Sniffer")
print("=" * 60)
print("\nBased on MTS protocol documentation:")
print("  - 'G' or 0x47 command may start streaming")
print("  - Device may auto-stream after power-on")
print("  - Some devices need specific init sequence")
print("\nTrying multiple approaches...\n")

for baudrate in baudrates:
    print(f"\n[Testing {baudrate} baud]")
    
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
        )
        
        # Clear buffer
        time.sleep(0.2)
        if ser.in_waiting > 0:
            junk = ser.read(ser.in_waiting)
            print(f"  Cleared {len(junk)} bytes from buffer")
        
        # Try 'G' command (LogWorks start command)
        print("  Sending 'G' command...")
        ser.write(b'G')
        time.sleep(0.3)
        
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            print(f"  [SUCCESS!] Received {len(data)} bytes after 'G'")
            print(f"  Data: {data!r}")
            print(f"  Hex: {data.hex()}")
            
            # Continue reading
            print("  Continuing to read...")
            for i in range(5):
                time.sleep(0.5)
                if ser.in_waiting > 0:
                    more = ser.read(ser.in_waiting)
                    print(f"  [{i+1}] {len(more)} bytes: {more!r}")
            
            ser.close()
            print(f"\n[FOUND] Device responds at {baudrate} baud with 'G' command!")
            sys.exit(0)
        
        # Try just listening (auto-stream)
        print("  Listening for auto-stream...")
        time.sleep(1.0)
        
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            print(f"  [SUCCESS!] Auto-streaming {len(data)} bytes")
            print(f"  Data: {data!r}")
            print(f"  Hex: {data.hex()}")
            ser.close()
            print(f"\n[FOUND] Device auto-streams at {baudrate} baud!")
            sys.exit(0)
        
        ser.close()
        print("  No response")
        
    except serial.SerialException as e:
        print(f"  Error: {e}")
        continue

print("\n" + "=" * 60)
print("[CONCLUSION]")
print("Device is not responding to any standard MTS commands.")
print("\nThis means:")
print("  1. Serial output is DISABLED in device settings")
print("  2. Device needs configuration via LM Programmer")
print("\nACTION REQUIRED:")
print("  - Open LM Programmer")
print("  - Connect to DLG-1")
print("  - Look for 'Serial Output' or 'Data Output' setting")
print("  - Enable it and save to device")
print("=" * 60)

