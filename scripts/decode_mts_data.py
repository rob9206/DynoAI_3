#!/usr/bin/env python3
"""
Decode Innovate MTS binary protocol from DLG-1.

MTS Protocol Format (based on actual captured data):
- Packet: B2 84 [ch1_4bytes] [ch2_4bytes]
- Total: 10 bytes per reading (2 channels)

The data pattern: b2 84 47 13 01 51 47 13 01 51
"""

import serial
import time
import struct
from dataclasses import dataclass
from typing import Optional


@dataclass
class MTSReading:
    """A decoded MTS reading."""
    timestamp: float
    channel1_lambda: float
    channel1_afr: float
    channel2_lambda: float
    channel2_afr: float
    raw_hex: str


def decode_lambda_word(high: int, low: int) -> float:
    """
    Decode a 2-byte lambda word from MTS protocol.
    
    Multiple encoding methods to try based on Innovate documentation variants.
    """
    # Method 1: Simple 10-bit value (bits 9-0)
    # Lambda = (value + 500) / 1000
    word = (high << 8) | low
    
    # Method 2: 13-bit value masked
    value_13bit = word & 0x1FFF
    lambda_v2 = value_13bit / 8192.0 + 0.5
    
    # Method 3: Standard MTS with 7-bit words
    # Each byte uses only lower 7 bits
    value_7bit = ((high & 0x7F) << 7) | (low & 0x7F)
    lambda_v3 = (value_7bit + 500) / 10000.0
    
    # Method 4: Direct AFR encoding (value / 10)
    afr_direct = word / 10.0
    
    # Method 5: Little-endian interpretation
    word_le = (low << 8) | high
    value_le_13bit = word_le & 0x1FFF
    lambda_le = value_le_13bit / 8192.0 + 0.5
    
    return {
        'word_be': word,
        'word_le': word_le,
        'lambda_13bit_be': value_13bit / 8192.0 + 0.5,
        'lambda_13bit_le': value_le_13bit / 8192.0 + 0.5,
        'lambda_7bit': (value_7bit + 500) / 10000.0 if value_7bit < 20000 else None,
        'afr_direct_be': word / 10.0,
        'afr_direct_le': word_le / 10.0,
    }


def find_packet_start(data: bytes, start: int = 0) -> int:
    """Find the start of an MTS packet (sync byte 0xB2)."""
    for i in range(start, len(data) - 1):
        if data[i] == 0xB2 and data[i + 1] == 0x84:
            return i
    return -1


def decode_packet(data: bytes) -> Optional[dict]:
    """
    Decode a 10-byte MTS packet.
    
    Format: B2 84 [ch1: 4 bytes] [ch2: 4 bytes]
    """
    if len(data) < 10:
        return None
    
    if data[0] != 0xB2 or data[1] != 0x84:
        return None
    
    # Channel 1: bytes 2-5 (47 13 01 51)
    ch1_b0, ch1_b1, ch1_b2, ch1_b3 = data[2], data[3], data[4], data[5]
    
    # Channel 2: bytes 6-9 (47 13 01 51)  
    ch2_b0, ch2_b1, ch2_b2, ch2_b3 = data[6], data[7], data[8], data[9]
    
    # Try different decodings
    # Hypothesis 1: Each channel is 4 bytes, using first 2 bytes
    ch1_decode = decode_lambda_word(ch1_b0, ch1_b1)
    ch2_decode = decode_lambda_word(ch2_b0, ch2_b1)
    
    # Hypothesis 2: Using bytes 2-3 (01 51)
    ch1_decode_alt = decode_lambda_word(ch1_b2, ch1_b3)
    ch2_decode_alt = decode_lambda_word(ch2_b2, ch2_b3)
    
    return {
        'header': f"{data[0]:02X} {data[1]:02X}",
        'ch1_raw': f"{ch1_b0:02X} {ch1_b1:02X} {ch1_b2:02X} {ch1_b3:02X}",
        'ch2_raw': f"{ch2_b0:02X} {ch2_b1:02X} {ch2_b2:02X} {ch2_b3:02X}",
        'ch1_word1': ch1_decode,
        'ch1_word2': ch1_decode_alt,
        'ch2_word1': ch2_decode,
        'ch2_word2': ch2_decode_alt,
    }


def analyze_captured_data():
    """Analyze the data captured from the test."""
    print("=" * 70)
    print("MTS Protocol Decoder - Analyzing Captured Data")
    print("=" * 70)
    
    # The captured repeating pattern
    pattern = bytes.fromhex("b2844713015147130151")
    
    print(f"\nCaptured pattern: {pattern.hex()}")
    print(f"Pattern length: {len(pattern)} bytes")
    print(f"Bytes: {' '.join(f'{b:02X}' for b in pattern)}")
    
    result = decode_packet(pattern)
    
    if result:
        print(f"\n--- Header ---")
        print(f"  Sync: {result['header']}")
        
        print(f"\n--- Channel 1 ---")
        print(f"  Raw bytes: {result['ch1_raw']}")
        print(f"  Word 1 (bytes 0-1):")
        for k, v in result['ch1_word1'].items():
            if v is not None:
                print(f"    {k}: {v}")
        print(f"  Word 2 (bytes 2-3):")
        for k, v in result['ch1_word2'].items():
            if v is not None:
                print(f"    {k}: {v}")
        
        print(f"\n--- Channel 2 ---")
        print(f"  Raw bytes: {result['ch2_raw']}")
        print(f"  Word 1 (bytes 0-1):")
        for k, v in result['ch2_word1'].items():
            if v is not None:
                print(f"    {k}: {v}")
    
    # Most likely interpretation based on common Innovate encoding
    print("\n" + "=" * 70)
    print("MOST LIKELY INTERPRETATION:")
    print("=" * 70)
    
    # Using the 13-bit lambda encoding (common in MTS)
    # For 47 13: word = 0x4713 = 18195, masked = 18195 & 0x1FFF = 1811
    # Lambda = 1811 / 8192 + 0.5 = 0.721
    word1 = (0x47 << 8) | 0x13  # 18195
    value1 = word1 & 0x1FFF    # 1811
    lambda1 = value1 / 8192.0 + 0.5
    afr1 = lambda1 * 14.7
    
    # For 01 51: word = 0x0151 = 337
    word2 = (0x01 << 8) | 0x51  # 337
    value2 = word2 & 0x1FFF    # 337
    lambda2 = value2 / 8192.0 + 0.5
    afr2 = lambda2 * 14.7
    
    print(f"\n  Word 1 (47 13):")
    print(f"    Raw word: 0x{word1:04X} = {word1}")
    print(f"    13-bit value: {value1}")
    print(f"    Lambda: {lambda1:.3f}")
    print(f"    AFR (gasoline): {afr1:.1f}")
    
    print(f"\n  Word 2 (01 51):")
    print(f"    Raw word: 0x{word2:04X} = {word2}")
    print(f"    13-bit value: {value2}")  
    print(f"    Lambda: {lambda2:.3f}")
    print(f"    AFR (gasoline): {afr2:.1f}")
    
    # Alternative: Try reading as status + data
    print("\n" + "-" * 70)
    print("ALTERNATIVE: Status byte interpretation")
    print("-" * 70)
    print("  The '47 13 01 51' pattern might be:")
    print("    0x47 = Status byte (sensor OK, warmup status, etc.)")
    print("    0x13 0x01 = Lambda value (little-endian)")
    print("    0x51 = Checksum or additional status")
    
    # Try: 0x1301 as lambda
    word3 = 0x0113  # Little-endian 13 01
    lambda3 = (word3 & 0x1FFF) / 8192.0 + 0.5
    afr3 = lambda3 * 14.7
    print(f"\n  Lambda from 0x0113: {lambda3:.3f} = {afr3:.1f} AFR")


def live_decode(port: str = "COM5", baudrate: int = 19200, duration: float = 10.0):
    """Live decode MTS data from the DLG-1."""
    print("=" * 70)
    print(f"Live MTS Decoder - {port} @ {baudrate} baud")
    print("=" * 70)
    
    try:
        ser = serial.Serial(port, baudrate, timeout=1.0)
        print(f"[OK] Connected to {port}")
        
        time.sleep(0.5)
        ser.reset_input_buffer()
        
        print(f"\nDecoding for {duration} seconds...\n")
        
        buffer = bytearray()
        start_time = time.time()
        readings = []
        
        while time.time() - start_time < duration:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                buffer.extend(data)
                
                # Process complete packets
                while len(buffer) >= 10:
                    # Find packet start
                    idx = find_packet_start(buffer)
                    if idx < 0:
                        buffer = buffer[-9:]  # Keep last partial
                        break
                    
                    if idx > 0:
                        buffer = buffer[idx:]  # Align to packet
                    
                    if len(buffer) >= 10:
                        packet = bytes(buffer[:10])
                        result = decode_packet(packet)
                        
                        if result:
                            # Extract most likely AFR value
                            word1 = (packet[2] << 8) | packet[3]
                            value1 = word1 & 0x1FFF
                            lambda1 = value1 / 8192.0 + 0.5
                            afr1 = lambda1 * 14.7
                            
                            word2 = (packet[6] << 8) | packet[7]
                            value2 = word2 & 0x1FFF
                            lambda2 = value2 / 8192.0 + 0.5
                            afr2 = lambda2 * 14.7
                            
                            readings.append({
                                'time': time.time() - start_time,
                                'ch1_afr': afr1,
                                'ch1_lambda': lambda1,
                                'ch2_afr': afr2,
                                'ch2_lambda': lambda2,
                            })
                            
                            print(f"[{readings[-1]['time']:5.1f}s] CH1: λ={lambda1:.3f} AFR={afr1:5.1f} | CH2: λ={lambda2:.3f} AFR={afr2:5.1f}")
                        
                        buffer = buffer[10:]
            else:
                time.sleep(0.05)
        
        ser.close()
        
        print(f"\n{'=' * 70}")
        print(f"Summary: {len(readings)} readings in {duration}s ({len(readings)/duration:.1f} Hz)")
        
        if readings:
            ch1_afrs = [r['ch1_afr'] for r in readings]
            ch2_afrs = [r['ch2_afr'] for r in readings]
            print(f"\nChannel 1 AFR: min={min(ch1_afrs):.1f}, max={max(ch1_afrs):.1f}, avg={sum(ch1_afrs)/len(ch1_afrs):.1f}")
            print(f"Channel 2 AFR: min={min(ch2_afrs):.1f}, max={max(ch2_afrs):.1f}, avg={sum(ch2_afrs)/len(ch2_afrs):.1f}")
        
    except serial.SerialException as e:
        print(f"[ERROR] {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "live":
        port = sys.argv[2] if len(sys.argv) > 2 else "COM5"
        live_decode(port)
    else:
        # Analyze the captured data first
        analyze_captured_data()
        print("\n" + "=" * 70)
        print("To decode live data, run: python decode_mts_data.py live [COM_PORT]")
        print("=" * 70)

