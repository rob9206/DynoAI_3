#!/usr/bin/env python3
"""
Try various commands to wake up the DLG-1 and trigger data streaming.
"""

import serial
import time

port = "COM5"
baudrate = 19200

print("=" * 60)
print("DLG-1 Wake-Up Test")
print("=" * 60)

try:
    ser = serial.Serial(port, baudrate, timeout=1)
    print(f"[OK] Connected to {port}")
    
    # Try various wake-up commands
    commands = [
        (b'G\r', "G command (LogWorks start)"),
        (b'g\r', "g command"),
        (b'A\r', "A command"),
        (b'?\r', "? query"),
        (b'\x47\x0D', "G with hex CR"),
        (b'\x00', "NULL byte"),
        (b'\xFF', "0xFF byte"),
    ]
    
    for cmd, desc in commands:
        print(f"\n[Testing] {desc}")
        print(f"  Sending: {cmd!r}")
        
        # Clear buffer
        if ser.in_waiting > 0:
            ser.reset_input_buffer()
        
        # Send command
        ser.write(cmd)
        time.sleep(0.5)
        
        # Check for response
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            print(f"  [RESPONSE] {len(data)} bytes: {data!r}")
            print(f"  Hex: {data.hex()}")
        else:
            print(f"  [No response]")
    
    # Final check - just listen for a bit
    print("\n[Final check] Listening for 5 seconds...")
    start = time.time()
    total_bytes = 0
    
    while time.time() - start < 5:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            total_bytes += len(data)
            print(f"  [{time.time()-start:.1f}s] {len(data)} bytes: {data!r}")
            print(f"  Hex: {data.hex()}")
        time.sleep(0.1)
    
    print(f"\n[Summary] Total bytes received: {total_bytes}")
    
    if total_bytes == 0:
        print("\n[ISSUE] Device is not sending data")
        print("\nPossible causes:")
        print("  1. Device serial output is disabled in settings")
        print("  2. Device needs to be configured with LM Programmer first")
        print("  3. Device only sends data when LogWorks is connected")
        print("  4. Baud rate mismatch (try 9600)")
        print("\nSuggestion:")
        print("  - Open LM Programmer")
        print("  - Check 'Serial Output' settings")
        print("  - Enable 'Output Data' or 'Serial Stream'")
    
    ser.close()
    
except Exception as e:
    print(f"[ERROR] {e}")

print("=" * 60)

