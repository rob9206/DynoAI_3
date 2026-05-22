#!/usr/bin/env python3
"""
JetDrive AFR-focused live logger.

Subscribes to AFR + context channels (RPM, TPS, vehicle speed, desired AFR)
from a Dynojet Power Core provider, prints live values at ~5 Hz, and writes a
single CSV row each time any AFR channel updates -- with the most recent RPM/
TPS context attached.

Usage:
    python scripts/jetdrive/jetdrive_afr_log.py
    python scripts/jetdrive/jetdrive_afr_log.py --duration 60
    python scripts/jetdrive/jetdrive_afr_log.py --duration 120 --out runs/seanbike_pull.csv

Notes:
    - This script does NOT rescale or interpret AFR values. It writes whatever
      the JetDrive provider publishes for each channel, plus the unit code.
    - Per workspace rules, AFR canonicalization (volts vs AFR, plausibility,
      tagging) lives on the server. This is a pure passthrough capture tool.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import math
import signal
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.services.jetdrive.jetdrive_client import (  # noqa: E402
    JetDriveConfig,
    JetDriveSample,
    discover_providers,
    subscribe,
)

AFR_CHANNEL_NAMES = [
    "WBO2 AFR Front",
    "WBO2 AFR Rear",
    "LC1 Volts Petrol AFR",
    "LC2 Volts Petrol AFR2",
    "Desired Air/Fuel",
]

CONTEXT_CHANNEL_NAMES = [
    "Engine RPM",
    "Engine Speed",
    "Throttle Position",
    "Vehicle Speed",
    "Speed",
    "Manifold Absolute Pressure",
]

ALL_SUBSCRIBED = AFR_CHANNEL_NAMES + CONTEXT_CHANNEL_NAMES


@dataclass
class LatestValue:
    value: float
    timestamp_ms: int
    unit: int


def _is_finite_number(x: float) -> bool:
    return x is not None and math.isfinite(x)


async def main() -> int:
    parser = argparse.ArgumentParser(description="JetDrive AFR-focused live logger")
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Capture duration in seconds (0 = run until Ctrl+C)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="CSV output path (default: runs/jetdrive_afr_<timestamp>/afr.csv)",
    )
    parser.add_argument(
        "--print-hz",
        type=float,
        default=5.0,
        help="Console refresh rate in Hz (default 5)",
    )
    args = parser.parse_args()

    config = JetDriveConfig.from_env()
    print(f"JetDrive config: group={config.multicast_group} port={config.port} iface={config.iface}")

    print("Discovering JetDrive provider...", flush=True)
    providers = await discover_providers(config, timeout=4.0)
    if not providers:
        print("ERROR: no providers found. Is Power Core running with JetDrive enabled?")
        return 1
    provider = providers[0]
    print(f"Provider: {provider.name}  channels={len(provider.channels)}  host={provider.host}:{provider.port}")

    by_name: dict[str, list[int]] = defaultdict(list)
    for cid, ch in provider.channels.items():
        by_name[ch.name].append(cid)

    found_afr: list[str] = []
    missing_afr: list[str] = []
    for name in AFR_CHANNEL_NAMES:
        (found_afr if name in by_name else missing_afr).append(name)

    print(f"AFR channels found:   {found_afr}")
    if missing_afr:
        print(f"AFR channels missing: {missing_afr}")

    found_ctx = [n for n in CONTEXT_CHANNEL_NAMES if n in by_name]
    print(f"Context channels:     {found_ctx}")

    if not found_afr:
        print("ERROR: no AFR channels published by this provider.")
        return 1

    if args.out:
        out_path = Path(args.out)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = Path("runs") / f"jetdrive_afr_{ts}" / "afr.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"CSV: {out_path}")

    latest: dict[str, LatestValue] = {}
    sample_counts: dict[str, int] = defaultdict(int)
    afr_row_count = [0]
    start_perf = time.perf_counter()

    csv_file = out_path.open("w", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)

    csv_columns = ["wall_time_iso", "elapsed_s", "trigger_channel", "trigger_unit"]
    for n in AFR_CHANNEL_NAMES:
        csv_columns.append(f"afr__{n.replace(' ', '_').replace('/', '_')}")
    for n in CONTEXT_CHANNEL_NAMES:
        csv_columns.append(f"ctx__{n.replace(' ', '_').replace('/', '_')}")
    writer.writerow(csv_columns)

    stop_event = asyncio.Event()

    def _on_sample(sample: JetDriveSample) -> None:
        if not _is_finite_number(sample.value):
            return
        chan_info = provider.channels.get(sample.channel_id)
        unit = chan_info.unit if chan_info else 255
        latest[sample.channel_name] = LatestValue(
            value=sample.value, timestamp_ms=sample.timestamp_ms, unit=unit
        )
        sample_counts[sample.channel_name] += 1

        if sample.channel_name in AFR_CHANNEL_NAMES:
            row = [
                datetime.now().isoformat(timespec="milliseconds"),
                f"{time.perf_counter() - start_perf:.3f}",
                sample.channel_name,
                unit,
            ]
            for n in AFR_CHANNEL_NAMES:
                lv = latest.get(n)
                row.append(f"{lv.value:.4f}" if lv else "")
            for n in CONTEXT_CHANNEL_NAMES:
                lv = latest.get(n)
                row.append(f"{lv.value:.4f}" if lv else "")
            writer.writerow(row)
            afr_row_count[0] += 1

    async def _stopper_duration():
        if args.duration and args.duration > 0:
            await asyncio.sleep(args.duration)
            stop_event.set()

    async def _printer():
        period = 1.0 / max(args.print_hz, 0.1)
        header = (
            f"{'t(s)':>6}  "
            f"{'RPM':>6}  {'TPS':>6}  {'MPH':>6}  "
            f"{'AFR_F':>6}  {'AFR_R':>6}  {'LC1':>6}  {'LC2':>6}  {'Tgt':>6}  "
            f"{'rows':>6}"
        )
        print(header)
        print("-" * len(header))
        while not stop_event.is_set():
            await asyncio.sleep(period)

            def _v(name: str, fmt: str = "{:6.2f}") -> str:
                lv = latest.get(name)
                return fmt.format(lv.value) if lv else "   --"

            line = (
                f"{time.perf_counter() - start_perf:6.1f}  "
                f"{_v('Engine RPM', '{:6.0f}') if 'Engine RPM' in latest else _v('Engine Speed', '{:6.0f}')}  "
                f"{_v('Throttle Position')}  "
                f"{_v('Vehicle Speed') if 'Vehicle Speed' in latest else _v('Speed')}  "
                f"{_v('WBO2 AFR Front')}  "
                f"{_v('WBO2 AFR Rear')}  "
                f"{_v('LC1 Volts Petrol AFR')}  "
                f"{_v('LC2 Volts Petrol AFR2')}  "
                f"{_v('Desired Air/Fuel')}  "
                f"{afr_row_count[0]:>6d}"
            )
            print(line, flush=True)

    def _sigint(_signum, _frame):
        stop_event.set()

    with contextlib_suppress():
        signal.signal(signal.SIGINT, _sigint)

    duration_task = asyncio.create_task(_stopper_duration())
    print_task = asyncio.create_task(_printer())

    try:
        await subscribe(
            provider=provider,
            channel_names=ALL_SUBSCRIBED,
            on_sample=_on_sample,
            config=config,
            stop_event=stop_event,
        )
    finally:
        stop_event.set()
        duration_task.cancel()
        print_task.cancel()
        for t in (duration_task, print_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        csv_file.flush()
        csv_file.close()

    print()
    print(f"Wrote {afr_row_count[0]} AFR-triggered rows to {out_path}")
    print("Per-channel sample counts:")
    for name in sorted(sample_counts):
        print(f"  {name:30s} {sample_counts[name]:>6d}")
    return 0


class contextlib_suppress:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return True


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
