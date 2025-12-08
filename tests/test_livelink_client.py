"""Test the LiveLink client."""

import sys
import time
from pathlib import Path

from api.services.livelink_client import LiveLinkClient

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_simulation_mode():
    """Test LiveLink client in simulation mode."""
    print("=== LiveLink Client Test (Simulation Mode) ===")
    print()

    client = LiveLinkClient(mode="simulation")

    # Connect
    print("Connecting...")
    success = client.connect()
    print(f"Connected: {success}")
    print(f"Mode: {client.mode}")
    print()

    # Register callback
    samples_received = []

    def on_sample(sample):
        samples_received.append(sample)

    client.on_data(on_sample)

    # Wait for some data
    print("Collecting data for 2 seconds...")
    time.sleep(2)

    # Get snapshot
    snapshot = client.get_snapshot()
    print(f"\nSnapshot (timestamp: {snapshot.timestamp:.3f}):")
    for name, value in snapshot.channels.items():
        units = snapshot.units.get(name, "")
        print(f"  {name}: {value} {units}")

    print(f"\nSamples received: {len(samples_received)}")

    # Get specific channel
    rpm = client.get_channel_value("Engine RPM")
    print(f"Engine RPM: {rpm}")

    # Disconnect
    print("\nDisconnecting...")
    client.disconnect()
    print(f"Connected: {client.connected}")

    print("\n=== Test Complete ===")


def test_auto_mode():
    """Test LiveLink client in auto mode."""
    print("=== LiveLink Client Test (Auto Mode) ===")
    print()

    client = LiveLinkClient(mode="auto")

    # Connect - will use simulation if Power Core not running
    print("Connecting (auto mode)...")
    success = client.connect()
    print(f"Connected: {success}")
    print(f"Selected mode: {client.mode}")

    if success:
        time.sleep(1)
        snapshot = client.get_snapshot()
        print(f"Channels: {list(snapshot.channels.keys())}")

    client.disconnect()
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    test_simulation_mode()
    print("\n" + "=" * 50 + "\n")
    test_auto_mode()
