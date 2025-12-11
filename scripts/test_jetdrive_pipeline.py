#!/usr/bin/env python3
"""
Full JetDrive Pipeline Test
- Publisher: Generates synthetic dyno data and broadcasts over KLHDV
- Subscriber: Receives data and writes to CSV
"""

import asyncio
import csv
import random
import struct
import socket
from pathlib import Path

from api.services.jetdrive_client import (
    JetDriveProviderInfo,
    ChannelInfo,
    JDUnit,
    JetDriveConfig,
    KEY_CHANNEL_INFO,
    KEY_CHANNEL_VALUES,
    _Wire,
    ALL_HOSTS,
    PROVIDER_NAME_LEN,
    CHANNEL_NAME_LEN,
)


provider = JetDriveProviderInfo(
    provider_id=0xDA10,
    name="DynoAI_Simulator",
    host="127.0.0.1",
    port=22344,
    channels={
        1: ChannelInfo(chan_id=1, name="RPM", unit=int(JDUnit.EngineSpeed)),
        2: ChannelInfo(chan_id=2, name="Torque", unit=int(JDUnit.Torque)),
        3: ChannelInfo(chan_id=3, name="Horsepower", unit=int(JDUnit.Power)),
        4: ChannelInfo(chan_id=4, name="AFR", unit=int(JDUnit.AFR)),
    },
)

CHAN_NAMES = {1: "RPM", 2: "Torque", 3: "Horsepower", 4: "AFR"}


def generate_samples():
    """Generate realistic dyno pull data."""
    samples = []
    ts = 0

    # Idle phase
    for _ in range(20):
        rpm = 1000 + random.uniform(-50, 50)
        tq = 15 + random.uniform(-2, 2)
        afr = 14.7 + random.uniform(-0.2, 0.2)
        samples.append((ts, rpm, tq, afr))
        ts += 100

    # Ramp to trigger (5+ consecutive >= 1500 RPM)
    for rpm in [1600, 1700, 1800, 1900, 2000, 2200, 2500, 2800, 3000, 3200, 3500]:
        tq = 80 + (rpm - 1500) * 0.04 + random.uniform(-3, 3)
        afr = 13.2 + random.uniform(-0.3, 0.3)
        samples.append((ts, float(rpm), tq, afr))
        ts += 100

    # Peak power phase
    for rpm in range(3500, 5800, 100):
        tq = 145 - abs(rpm - 4800) * 0.015 + random.uniform(-2, 2)
        afr = 12.5 + random.uniform(-0.2, 0.2)
        samples.append((ts, float(rpm), tq, afr))
        ts += 100

    # Decel (5+ consecutive <= 1200 RPM to end)
    for rpm in [5000, 4000, 3000, 2000, 1500, 1200, 1100, 1100, 1100, 1000, 950]:
        tq = 20 + random.uniform(-5, 5)
        afr = 14.0 + random.uniform(-0.3, 0.3)
        samples.append((ts, float(rpm), tq, afr))
        ts += 100

    return samples


async def run_test():
    cfg = JetDriveConfig()

    print("=" * 60)
    print("JETDRIVE Full Pipeline Test")
    print("=" * 60)
    print(f"Multicast: {cfg.multicast_group}:{cfg.port}")
    print()

    # Create receiver socket (subscriber)
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    recv_sock.bind(("", cfg.port))
    mreq = struct.pack(
        "4s4s",
        socket.inet_aton(cfg.multicast_group),
        socket.inet_aton("0.0.0.0"),
    )
    recv_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    recv_sock.setblocking(False)

    # Create sender socket (publisher)
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    send_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    samples = generate_samples()
    received = []

    print("[PUBLISHER] Broadcasting channel info...")

    # Broadcast channel info
    payload = bytearray(provider.name.encode("utf-8").ljust(PROVIDER_NAME_LEN, b"\x00"))
    for cid, info in provider.channels.items():
        payload.extend(struct.pack("<H", cid))
        payload.append(info.vendor)
        payload.extend(info.name.encode("utf-8").ljust(CHANNEL_NAME_LEN, b"\x00"))
        payload.append(info.unit)

    msg = _Wire.encode(
        KEY_CHANNEL_INFO, provider.provider_id, ALL_HOSTS, 0, bytes(payload)
    )
    send_sock.sendto(msg, (cfg.multicast_group, cfg.port))
    await asyncio.sleep(0.1)

    print(f"[PUBLISHER] Publishing {len(samples)} timestamped frames...")
    print("[SUBSCRIBER] Listening for KLHDV packets...")
    print()

    seq = 1

    for i, (ts, rpm, tq, afr) in enumerate(samples):
        hp = (tq * rpm) / 5252

        # Build and send packet
        payload = bytearray()
        for cid, val in [(1, rpm), (2, tq), (3, hp), (4, afr)]:
            payload.extend(struct.pack("<HIf", cid, int(ts), float(val)))

        msg = _Wire.encode(
            KEY_CHANNEL_VALUES, provider.provider_id, ALL_HOSTS, seq, bytes(payload)
        )
        send_sock.sendto(msg, (cfg.multicast_group, cfg.port))
        seq = (seq + 1) % 256

        # Receive any pending packets
        await asyncio.sleep(0.02)
        try:
            while True:
                data, addr = recv_sock.recvfrom(4096)
                decoded = _Wire.decode(data)
                if decoded and decoded[0] == KEY_CHANNEL_VALUES:
                    key, length, host, dest, seq_num, value = decoded
                    n_samples = len(value) // 10
                    for j in range(n_samples):
                        offset = j * 10
                        cid, tstamp, val = struct.unpack(
                            "<HIf", value[offset : offset + 10]
                        )
                        received.append({"ts": tstamp, "chan": cid, "value": val})
        except BlockingIOError:
            pass

        if i % 20 == 0:
            print(
                f"  [{i:3d}] RPM: {rpm:5.0f}  TQ: {tq:5.1f}  HP: {hp:5.1f}  AFR: {afr:.1f}"
            )

    recv_sock.close()
    send_sock.close()

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Published: {len(samples)} frames")
    print(f"Received:  {len(received)} channel samples")

    # Write CSV
    outdir = Path("runs/jetdrive_test")
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "run.csv"

    # Reorganize by timestamp
    by_ts = {}
    for r in received:
        ts = r["ts"]
        if ts not in by_ts:
            by_ts[ts] = {}
        chan_name = CHAN_NAMES.get(r["chan"], f"Ch{r['chan']}")
        by_ts[ts][chan_name] = r["value"]

    rows = []
    for ts in sorted(by_ts.keys()):
        row = by_ts[ts]
        row["timestamp_ms"] = ts
        rows.append(row)

    if rows:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "RPM", "Torque", "Horsepower", "AFR"]
            )
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV saved: {csv_path}")
        print(f"  Rows: {len(rows)}")

        # Show peak values
        max_rpm = max(r.get("RPM", 0) for r in rows)
        max_hp = max(r.get("Horsepower", 0) for r in rows)
        max_tq = max(r.get("Torque", 0) for r in rows)
        print(f"  Peak RPM: {max_rpm:.0f}")
        print(f"  Peak HP:  {max_hp:.1f}")
        print(f"  Peak TQ:  {max_tq:.1f} ft-lb")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_test())
