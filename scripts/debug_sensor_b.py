#!/usr/bin/env python3
"""
Debug Sensor B readings from Innovate DLG-1.
This script will capture raw MTS packets and decode both channels to identify the issue.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import serial
import time
from datetime import datetime

def decode_mts_packet_debug(data: bytes):
    """
    Debug decoder for MTS packets - shows all interpretations.
    """
    if len(data) < 10:
        return None
    
    # Verify header
    if data[0] != 0xB2 or data[1] != 0x84:
        return None
    
    print(f"\n{'='*60}")
    print(f"MTS Packet: {' '.join(f'{b:02x}' for b in data[:10])}")
    print(f"{'='*60}")
    
    # Channel B data (bytes 2-5)
    ch_b_data = data[2:6]
    print(f"\nChannel B (Sensor B) bytes 2-5: {' '.join(f'{b:02x}' for b in ch_b_data)}")
    print(f"  Decimal: {' '.join(f'{b:3d}' for b in ch_b_data)}")
    print(f"  Binary:  {' '.join(f'{b:08b}' for b in ch_b_data)}")
    
    # Try different byte combinations for Channel B
    print(f"\n  Interpretation attempts for Channel B:")
    
    # Current implementation (bytes 2 and 3 of ch_data = bytes 4 and 5 of packet)
    low_byte_current = ch_b_data[2] & 0x7F
    high_byte_current = ch_b_data[3] & 0x7F
    raw_current = (high_byte_current << 7) | low_byte_current
    lambda_current = raw_current / 10000.0 + 0.5
    afr_current = lambda_current * 14.7
    print(f"    Current code (bytes [2],[3]): raw={raw_current}, lambda={lambda_current:.3f}, AFR={afr_current:.1f}")
    
    # Try bytes 0 and 1
    low_byte_01 = ch_b_data[0] & 0x7F
    high_byte_01 = ch_b_data[1] & 0x7F
    raw_01 = (high_byte_01 << 7) | low_byte_01
    lambda_01 = raw_01 / 10000.0 + 0.5
    afr_01 = lambda_01 * 14.7
    print(f"    Try bytes [0],[1]:             raw={raw_01}, lambda={lambda_01:.3f}, AFR={afr_01:.1f}")
    
    # Try bytes 1 and 2
    low_byte_12 = ch_b_data[1] & 0x7F
    high_byte_12 = ch_b_data[2] & 0x7F
    raw_12 = (high_byte_12 << 7) | low_byte_12
    lambda_12 = raw_12 / 10000.0 + 0.5
    afr_12 = lambda_12 * 14.7
    print(f"    Try bytes [1],[2]:             raw={raw_12}, lambda={lambda_12:.3f}, AFR={afr_12:.1f}")
    
    # Channel A data (bytes 6-9)
    ch_a_data = data[6:10]
    print(f"\nChannel A (Sensor A) bytes 6-9: {' '.join(f'{b:02x}' for b in ch_a_data)}")
    print(f"  Decimal: {' '.join(f'{b:3d}' for b in ch_a_data)}")
    print(f"  Binary:  {' '.join(f'{b:08b}' for b in ch_a_data)}")
    
    # Current implementation for Channel A
    low_byte_a = ch_a_data[2] & 0x7F
    high_byte_a = ch_a_data[3] & 0x7F
    raw_a = (high_byte_a << 7) | low_byte_a
    lambda_a = raw_a / 10000.0 + 0.5
    afr_a = lambda_a * 14.7
    print(f"\n  Interpretation for Channel A:")
    print(f"    Current code (bytes [2],[3]): raw={raw_a}, lambda={lambda_a:.3f}, AFR={afr_a:.1f}")
    
    return {
        'sensor_a_afr': afr_a,
        'sensor_b_afr_current': afr_current,
        'sensor_b_afr_alt1': afr_01,
        'sensor_b_afr_alt2': afr_12,
    }


def main():
    port = "COM5"  # Adjust if needed
    baudrate = 19200
    
    print("=" * 60)
    print("Innovate DLG-1 Sensor B Debug Tool")
    print("=" * 60)
    print(f"\nConnecting to {port} at {baudrate} baud...")
    
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        print("✓ Connected")
        
        # Clear buffer
        time.sleep(0.2)
        if ser.in_waiting > 0:
            ser.reset_input_buffer()
        
        print("\nReading MTS packets (Ctrl+C to stop)...")
        print("Expected: Sensor A = ~22.4 AFR (working)")
        print("          Sensor B = should also be ~22.4 AFR (currently erratic)\n")
        
        buffer = bytearray()
        packet_count = 0
        
        while packet_count < 10:  # Capture 10 packets for analysis
            if ser.in_waiting > 0:
                incoming = ser.read(ser.in_waiting)
                buffer.extend(incoming)
            
            # Look for complete MTS packet (B2 84 header + 8 bytes data)
            while len(buffer) >= 10:
                # Find sync header
                sync_idx = -1
                for i in range(len(buffer) - 1):
                    if buffer[i] == 0xB2 and buffer[i + 1] == 0x84:
                        sync_idx = i
                        break
                
                if sync_idx < 0:
                    # No sync found - keep last byte
                    buffer = buffer[-1:]
                    break
                
                # Discard data before sync
                if sync_idx > 0:
                    buffer = buffer[sync_idx:]
                
                # Check if we have complete packet
                if len(buffer) < 10:
                    break
                
                # Extract and decode packet
                packet = bytes(buffer[:10])
                buffer = buffer[10:]
                
                packet_count += 1
                result = decode_mts_packet_debug(packet)
                
                if result:
                    print(f"\n{'='*60}")
                    print(f"SUMMARY for packet #{packet_count}:")
                    print(f"  Sensor A AFR: {result['sensor_a_afr']:.1f}")
                    print(f"  Sensor B AFR (current):  {result['sensor_b_afr_current']:.1f}")
                    print(f"  Sensor B AFR (alt 1):    {result['sensor_b_afr_alt1']:.1f}")
                    print(f"  Sensor B AFR (alt 2):    {result['sensor_b_afr_alt2']:.1f}")
                    
                    # Check which interpretation is closest to expected 22.4
                    expected = 22.4
                    errors = {
                        'current': abs(result['sensor_b_afr_current'] - expected),
                        'alt1': abs(result['sensor_b_afr_alt1'] - expected),
                        'alt2': abs(result['sensor_b_afr_alt2'] - expected),
                    }
                    best = min(errors, key=errors.get)
                    print(f"\n  >>> BEST MATCH: {best} (error: {errors[best]:.1f} AFR)")
                    print(f"{'='*60}")
                
                time.sleep(0.1)
            
            time.sleep(0.05)
        
        ser.close()
        print("\n\nAnalysis complete. Check which interpretation consistently gives ~22.4 AFR for Sensor B.")
        
    except serial.SerialException as e:
        print(f"✗ Serial error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
        return 0
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

