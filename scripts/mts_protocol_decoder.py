#!/usr/bin/env python3
"""
MTS Protocol Decoder - Based on reverse engineering.

MTS (Modular Tuning System) uses multiplexed 16-bit words.
Each word contains: [function_type][data]

Common structure:
- Word format: 16 bits
- Bits 15-13: Function type (0-7)
- Bits 12-0: Data (13 bits)

Function types:
- 0: Lambda (AFR)
- 1: O2 level
- 2: Status/Error
- 3-7: Other sensors

For Lambda/AFR:
- 13-bit value represents Lambda * 1000 (or similar scaling)
- AFR = Lambda * 14.7 (for gasoline)
"""

import serial
import time

def decode_mts_word(word_bytes):
    """
    Decode a 16-bit MTS word.
    
    Args:
        word_bytes: 2 bytes (big-endian assumed)
    
    Returns:
        (function_type, data_value)
    """
    if len(word_bytes) < 2:
        return None, None
    
    # MTS uses big-endian 16-bit words
    word = int.from_bytes(word_bytes, 'big')
    
    # Extract function type (top 3 bits)
    function_type = (word >> 13) & 0x07
    
    # Extract data (bottom 13 bits)
    data = word & 0x1FFF
    
    return function_type, data


def decode_mts_packet(packet):
    """
    Decode an MTS packet.
    
    Packet structure:
    - Byte 0: Sync/header (often 0xA0, 0xA2, 0xB0, 0xB2)
    - Remaining bytes: 16-bit words
    """
    if len(packet) < 3:
        return []
    
    results = []
    
    # Skip header byte (0xB2)
    data_start = 1
    
    # Process 16-bit words
    for i in range(data_start, len(packet) - 1, 2):
        word_bytes = packet[i:i+2]
        func_type, data_val = decode_mts_word(word_bytes)
        
        if func_type is not None:
            # Interpret based on function type
            if func_type == 0:  # Lambda
                # Lambda is typically encoded as value / 1000
                lambda_val = data_val / 1000.0
                afr = lambda_val * 14.7
                results.append({
                    'type': 'Lambda/AFR',
                    'function': func_type,
                    'raw': data_val,
                    'lambda': lambda_val,
                    'afr': afr,
                })
            elif func_type == 1:  # O2 level
                results.append({
                    'type': 'O2',
                    'function': func_type,
                    'raw': data_val,
                    'value': data_val,
                })
            else:
                results.append({
                    'type': f'Function {func_type}',
                    'function': func_type,
                    'raw': data_val,
                })
    
    return results


# Test with actual packet
print("=" * 60)
print("MTS Protocol Decoder Test")
print("=" * 60)

packet_hex = "b2844713015147130151"
packet = bytes.fromhex(packet_hex)

print(f"\nPacket: {packet_hex}")
print(f"Expected: Both sensors = 22.4 AFR (Lambda 1.52)")

print("\n[Decoding as MTS multiplexed format...]")
results = decode_mts_packet(packet)

for i, result in enumerate(results):
    print(f"\nWord {i}:")
    print(f"  Type: {result['type']}")
    print(f"  Function: {result['function']}")
    print(f"  Raw value: {result['raw']}")
    if 'lambda' in result:
        print(f"  Lambda: {result['lambda']:.3f}")
        print(f"  AFR: {result['afr']:.1f}")
        if 21.0 <= result['afr'] <= 24.0:
            print(f"  >>> MATCH! Close to 22.4")

print("\n" + "=" * 60)
print("Analysis:")
print("  Word 0 (84 47): Function={}, Data={}".format(
    (0x8447 >> 13) & 0x07,
    0x8447 & 0x1FFF
))
print(f"    Data value: {0x8447 & 0x1FFF} = {(0x8447 & 0x1FFF) / 1000:.3f} Lambda")
print(f"    AFR: {((0x8447 & 0x1FFF) / 1000) * 14.7:.1f}")

print("\n  Word 1 (13 01): Function={}, Data={}".format(
    (0x1301 >> 13) & 0x07,
    0x1301 & 0x1FFF
))
print(f"    Data value: {0x1301 & 0x1FFF} = {(0x1301 & 0x1FFF) / 1000:.3f} Lambda")
print(f"    AFR: {((0x1301 & 0x1FFF) / 1000) * 14.7:.1f}")

print("\n  Word 2 (51 47): Function={}, Data={}".format(
    (0x5147 >> 13) & 0x07,
    0x5147 & 0x1FFF
))
print(f"    Data value: {0x5147 & 0x1FFF} = {(0x5147 & 0x1FFF) / 1000:.3f} Lambda")
print(f"    AFR: {((0x5147 & 0x1FFF) / 1000) * 14.7:.1f}")

print("=" * 60)






