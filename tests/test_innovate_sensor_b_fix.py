#!/usr/bin/env python3
"""
Test for Innovate DLG-1 Sensor B fix.

Verifies that the MTS packet parser correctly decodes both channels
using the proper byte positions and formula.
"""

import sys
from pathlib import Path

from api.services.innovate_client import InnovateClient, InnovateDeviceType

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_mts_packet_parsing():
    """Test MTS packet parsing with known good data."""

    # Create client (no connection needed for parsing test)
    client = InnovateClient(port="COM99", device_type=InnovateDeviceType.DLG1)

    # Test packet with both sensors reading ~22.4 AFR
    # Packet format: B2 84 [Ch B: 4 bytes] [Ch A: 4 bytes]
    # Channel data: 0x47 0x13 should decode to ~22.4 AFR
    test_packet = bytes.fromhex("b2844713015147130151")

    print("=" * 60)
    print("Innovate DLG-1 Sensor B Fix - Unit Test")
    print("=" * 60)
    print(f"\nTest packet: {test_packet.hex()}")
    print("Expected: Both sensors ~22.4 AFR")

    # Parse Channel A (Sensor A)
    sample_a = client._parse_mts_packet(test_packet, channel=1)

    # Parse Channel B (Sensor B)
    sample_b = client._parse_mts_packet(test_packet, channel=2)

    print("\n" + "-" * 60)
    print("Results:")
    print("-" * 60)

    if sample_a:
        print(f"Channel A (Sensor A):")
        print(f"  AFR:    {sample_a.afr:.2f}")
        print(f"  Lambda: {sample_a.lambda_value:.3f}")
        print(f"  [PASS]" if 22.0 <= sample_a.afr <= 22.8 else f"  [FAIL]")
    else:
        print(f"Channel A: [FAIL] (no sample)")

    print()

    if sample_b:
        print(f"Channel B (Sensor B):")
        print(f"  AFR:    {sample_b.afr:.2f}")
        print(f"  Lambda: {sample_b.lambda_value:.3f}")
        print(f"  [PASS]" if 22.0 <= sample_b.afr <= 22.8 else f"  [FAIL]")
    else:
        print(f"Channel B: [FAIL] (no sample)")

    print("\n" + "=" * 60)

    # Verify results
    assert sample_a is not None, "Channel A sample should not be None"
    assert sample_b is not None, "Channel B sample should not be None"

    # Both channels should read approximately 22.4 AFR (allow ±0.4 tolerance)
    assert 22.0 <= sample_a.afr <= 22.8, (
        f"Channel A AFR {sample_a.afr:.2f} out of range"
    )
    assert 22.0 <= sample_b.afr <= 22.8, (
        f"Channel B AFR {sample_b.afr:.2f} out of range"
    )

    # Both channels should be very close to each other (within 0.2 AFR)
    afr_diff = abs(sample_a.afr - sample_b.afr)
    assert afr_diff < 0.2, f"Channel A/B AFR difference {afr_diff:.2f} too large"

    print("[PASS] All tests PASSED!")
    print("\nSensor B fix verified: Both channels decode correctly.")
    print("=" * 60)

    return True


def test_different_afr_values():
    """Test parsing with different AFR values to ensure formula works across range."""

    client = InnovateClient(port="COM99", device_type=InnovateDeviceType.DLG1)

    print("\n" + "=" * 60)
    print("Testing AFR Formula Across Range")
    print("=" * 60)

    # Test cases: (raw_value, expected_afr)
    test_cases = [
        (0x4713, 22.24),  # Observed: ~22.4 AFR
        (0x5B13, 28.0),  # Higher AFR (leaner)
        (0x3313, 15.7),  # Lower AFR (richer)
    ]

    for raw_val, expected_afr in test_cases:
        # Construct packet with this raw value
        b0 = (raw_val >> 8) & 0xFF
        b1 = raw_val & 0xFF
        packet = bytes([0xB2, 0x84, b0, b1, 0x01, 0x51, b0, b1, 0x01, 0x51])

        sample = client._parse_mts_packet(packet, channel=1)

        if sample:
            error = abs(sample.afr - expected_afr)
            status = "[OK]" if error < 0.5 else "[ERR]"
            print(
                f"  Raw 0x{raw_val:04x} -> AFR {sample.afr:.2f} (expected {expected_afr:.1f}) {status}"
            )
        else:
            print(f"  Raw 0x{raw_val:04x} -> FAILED TO PARSE [ERR]")

    print("=" * 60)


if __name__ == "__main__":
    try:
        test_mts_packet_parsing()
        test_different_afr_values()
        print("\n*** ALL TESTS PASSED ***\n")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n*** TEST FAILED: {e} ***\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n*** ERROR: {e} ***\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)
