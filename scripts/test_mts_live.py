#!/usr/bin/env python3
"""
Test live MTS data from Innovate DLG-1 using the updated InnovateClient.
"""

import sys
import time

from api.services.innovate_client import InnovateClient, InnovateDeviceType

# Add parent directory to path
sys.path.insert(0, "C:\\Dev\\DynoAI_3")


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0

    print("=" * 60)
    print("DLG-1 MTS Live Test")
    print("=" * 60)
    print(f"Port: {port}")
    print(f"Duration: {duration}s")
    print()

    samples = []

    def on_sample(sample):
        samples.append(sample)
        print(
            f"[{sample.timestamp - samples[0].timestamp:5.1f}s] "
            f"CH{sample.channel}: λ={sample.lambda_value:.3f} AFR={sample.afr:5.1f}"
        )

    try:
        client = InnovateClient(port=port, device_type=InnovateDeviceType.DLG1)

        print("Connecting...")
        if not client.connect():
            print("[ERROR] Failed to connect")
            return 1

        print("[OK] Connected!")
        print()
        print("Starting data stream...")
        print("-" * 60)

        # Start streaming both channels
        client.start_streaming(callback=on_sample, channels=[1, 2])

        # Wait for duration
        time.sleep(duration)

        # Stop and disconnect
        client.stop_streaming()
        client.disconnect()

        print("-" * 60)
        print()
        print(f"Total samples: {len(samples)}")

        if samples:
            ch1_samples = [s for s in samples if s.channel == 1]
            ch2_samples = [s for s in samples if s.channel == 2]

            if ch1_samples:
                afrs = [s.afr for s in ch1_samples]
                print(f"\nChannel 1:")
                print(f"  Samples: {len(ch1_samples)}")
                print(
                    f"  AFR: min={min(afrs):.1f}, max={max(afrs):.1f}, avg={sum(afrs) / len(afrs):.1f}"
                )

            if ch2_samples:
                afrs = [s.afr for s in ch2_samples]
                print(f"\nChannel 2:")
                print(f"  Samples: {len(ch2_samples)}")
                print(
                    f"  AFR: min={min(afrs):.1f}, max={max(afrs):.1f}, avg={sum(afrs) / len(afrs):.1f}"
                )

            print(f"\nSample rate: {len(samples) / duration:.1f} Hz")
        else:
            print("\n[WARNING] No samples received!")
            print("\nTroubleshooting:")
            print("  1. Check device is powered on")
            print("  2. Check COM port is correct")
            print("  3. Check cable is connected to OUT port")

        return 0

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
