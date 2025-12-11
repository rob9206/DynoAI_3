from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from dataclasses import asdict
from typing import cast

from synthetic.jetdrive_client import (
    JetDriveProviderInfo,
    JetDriveSample,
    discover_providers,
    publish_run,
    subscribe,
)

from .winpep8_synthesizer import (
    EngineFamily,
    PeakInfo,
    generate_winpep8_like_run,
    save_winpep8_run,
)


def _normalize_run_id(raw: str) -> str:
    normalized = raw.strip().replace("\\", "/").strip("/")
    if not normalized or normalized in {".", ".."} or ".." in normalized.split("/"):
        raise ValueError(f"Invalid run identifier: {raw!r}")
    # Ensure the final path stays under the current working directory for safe writes.
    from pathlib import Path

    candidate = Path("runs", normalized).resolve(strict=False)
    root = Path.cwd().resolve()
    if not str(candidate).startswith(str(root)):
        raise ValueError(f"Run identifier points outside project root: {raw!r}")
    return normalized


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate WinPEP8-style CSV files from peak HP/TQ data or JetDrive streams.",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # Legacy synthetic path from peaks
    base = subparsers.add_parser("peaks", help="Generate CSV from peak HP/TQ inputs.")
    base.add_argument(
        "--run-id",
        required=True,
        help="Directory under runs/ where the CSV should be saved (e.g. fuelmoto/demo_run).",
    )
    base.add_argument(
        "--family",
        choices=["M8", "TwinCam", "Sportbike", "Generic"],
        default="M8",
        help="Engine family preset used for idle/redline heuristics.",
    )
    base.add_argument(
        "--displacement-ci",
        type=float,
        required=True,
        help="Engine displacement in cubic inches (used for metadata only).",
    )
    base.add_argument(
        "--max-hp",
        type=float,
        required=True,
        help="Peak horsepower value read from the source chart.",
    )
    base.add_argument(
        "--hp-peak-rpm",
        type=float,
        required=True,
        help="RPM at which the horsepower peak occurs.",
    )
    base.add_argument(
        "--max-tq",
        type=float,
        required=True,
        help="Peak torque (ft-lb) value read from the source chart.",
    )
    base.add_argument(
        "--tq-peak-rpm",
        type=float,
        required=True,
        help="RPM at which the torque peak occurs.",
    )
    base.add_argument(
        "--rpm-points",
        type=int,
        default=400,
        help="Number of RPM samples in the generated CSV (default: 400).",
    )
    base.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the dataframe but do not write a CSV (useful for debugging).",
    )

    # JetDrive-driven capture
    jd = subparsers.add_parser(
        "jetdrive-run", help="Capture a run from JetDrive and synthesize CSV."
    )
    jd.add_argument(
        "--provider",
        required=True,
        help="Provider name or id prefix to match.",
    )
    jd.add_argument(
        "--run-id",
        required=True,
        help="Directory under runs/ where the CSV should be saved.",
    )
    jd.add_argument(
        "--family",
        choices=["M8", "TwinCam", "Sportbike", "Generic"],
        default="M8",
        help="Engine family preset used for idle/redline heuristics.",
    )
    jd.add_argument(
        "--displacement-ci",
        type=float,
        required=True,
        help="Engine displacement in cubic inches (used for metadata only).",
    )
    jd.add_argument(
        "--channels",
        default="RPM,Torque,AFR",
        help="Comma-separated channel names to subscribe to (default: RPM,Torque,AFR).",
    )
    jd.add_argument(
        "--trigger",
        choices=["auto", "button"],
        default="auto",
        help="Run trigger mode (auto thresholds or button/Enter).",
    )
    jd.add_argument(
        "--min-duration",
        type=float,
        default=3.0,
        help="Minimum run duration in seconds.",
    )
    jd.add_argument(
        "--max-duration",
        type=float,
        default=20.0,
        help="Maximum run duration in seconds.",
    )
    jd.add_argument(
        "--rpm-start-threshold",
        type=int,
        default=1500,
        help="RPM threshold to consider run started.",
    )
    jd.add_argument(
        "--rpm-end-threshold",
        type=int,
        default=1200,
        help="RPM threshold to consider run ended.",
    )
    jd.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Overall discovery/collection timeout in seconds.",
    )
    jd.add_argument(
        "--restream-jetdrive",
        action="store_true",
        help="Experimental: re-stream synthetic samples back over JetDrive after writing CSV.",
    )

    return parser


def _handle_peaks(args: argparse.Namespace) -> int:
    peaks = PeakInfo(
        max_hp=args.max_hp,
        hp_peak_rpm=args.hp_peak_rpm,
        max_tq=args.max_tq,
        tq_peak_rpm=args.tq_peak_rpm,
    )
    family = cast(EngineFamily, args.family)
    df = generate_winpep8_like_run(
        peaks=peaks,
        family=family,
        displacement_ci=args.displacement_ci,
        rpm_points=args.rpm_points,
    )

    if args.dry_run:
        print("DRY RUN: generated dataframe preview")
        print(df.head())
        return 0

    run_id = _normalize_run_id(args.run_id)
    output_path = save_winpep8_run(run_id, df)
    print("Saved synthetic WinPEP8 run:")
    print(f"  output: {output_path}")
    print(f"  family: {family}")
    print(f"  peaks : {asdict(peaks)}")
    return 0


def _select_provider(
    providers: list[JetDriveProviderInfo], query: str
) -> JetDriveProviderInfo:
    if not providers:
        raise RuntimeError("No JetDrive providers discovered.")
    q = query.lower()
    exact = [
        p for p in providers if p.name.lower() == q or str(p.provider_id).lower() == q
    ]
    if len(exact) == 1:
        return exact[0]
    matches = [
        p
        for p in providers
        if p.name.lower().startswith(q) or str(p.provider_id).lower().startswith(q)
    ]
    if len(matches) == 1:
        return matches[0]
    names = ", ".join(f"{p.name}({p.provider_id})" for p in providers)
    if not matches:
        raise RuntimeError(
            f"No provider matched '{query}'. Discovered: {names or 'none'}."
        )
    raise RuntimeError(f"Ambiguous provider '{query}'. Candidates: {names}.")


def _validate_channels(
    provider: JetDriveProviderInfo, requested: list[str]
) -> dict[str, int]:
    channel_iter = (
        provider.channels.values()
        if hasattr(provider.channels, "values")
        else provider.channels
    )
    available: dict[str, int] = {}
    for c in channel_iter:
        name = getattr(c, "name", None)
        chan_id = getattr(c, "chan_id", getattr(c, "channel_id", None))
        if name is None or chan_id is None:
            continue
        available[str(name).lower()] = int(chan_id)
    missing: list[str] = []
    mapping: dict[str, int] = {}
    for name in requested:
        key = name.strip().lower()
        if key in available:
            mapping[key] = available[key]
        else:
            missing.append(name)
    if missing:
        raise RuntimeError(
            f"Missing channels: {', '.join(missing)}. Available: {', '.join(available.keys()) or 'none'}."
        )
    return mapping


async def _wait_for_enter(prompt: str) -> None:
    print(prompt, flush=True)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, sys.stdin.readline)


async def _collect_jetdrive_run(
    provider: JetDriveProviderInfo,
    required_channels: list[str],
    *,
    min_duration: float,
    max_duration: float,
    rpm_start_threshold: int,
    rpm_end_threshold: int,
    trigger_mode: str,
    overall_timeout: float,
) -> dict[str, list[JetDriveSample]]:
    buffers: dict[str, list[JetDriveSample]] = {
        name.lower(): [] for name in required_channels
    }
    stop_event = asyncio.Event()
    state = "IDLE"
    rpm_key = next((name for name in required_channels if name.lower() == "rpm"), None)
    start_ts: int | None = None
    consec_start = 0
    consec_end = 0
    START_SAMPLES = 5
    END_SAMPLES = 5

    if rpm_key is None:
        raise RuntimeError("RPM channel is required for run detection.")

    async def on_button_mode():
        nonlocal state
        await _wait_for_enter("Press Enter to start capture...")
        state = "RUNNING"
        await _wait_for_enter("Press Enter to stop capture...")
        state = "DONE"
        stop_event.set()

    if trigger_mode == "button":
        asyncio.create_task(on_button_mode())

    def on_sample(sample: JetDriveSample) -> None:
        nonlocal state, start_ts, consec_start, consec_end
        chan_name = sample.channel_name.lower()
        if chan_name not in buffers:
            return
        buffers[chan_name].append(sample)

        if state == "DONE":
            return

        if trigger_mode == "auto" and chan_name == rpm_key.lower():
            rpm = sample.value
            if state in {"IDLE", "ARMED"}:
                if rpm >= rpm_start_threshold:
                    consec_start += 1
                    if consec_start >= START_SAMPLES:
                        state = "RUNNING"
                        start_ts = getattr(sample, "timestamp_ms", None)
                else:
                    consec_start = 0
            if state == "RUNNING":
                elapsed = 0.0
                if start_ts is not None:
                    elapsed = (
                        getattr(sample, "timestamp_ms", start_ts) - start_ts
                    ) / 1000.0
                if rpm <= rpm_end_threshold:
                    consec_end += 1
                else:
                    consec_end = 0
                if (consec_end >= END_SAMPLES) or (elapsed >= max_duration):
                    state = "DONE"
                    stop_event.set()

    await subscribe(
        provider,
        required_channels,
        on_sample=on_sample,
        stop_event=stop_event,
        recv_timeout=0.5,
    )

    # Validate duration
    rpm_samples = buffers.get(rpm_key.lower(), [])
    if not rpm_samples:
        raise RuntimeError("No RPM samples captured; no run detected.")
    ts_values = [getattr(s, "timestamp_ms", 0) for s in rpm_samples]
    duration = (max(ts_values) - min(ts_values)) / 1000.0
    if duration < min_duration:
        raise RuntimeError(
            f"Run too short ({duration:.2f}s); min required {min_duration}s."
        )
    if duration > max_duration + 5.0:
        raise RuntimeError(f"Run exceeded expected duration ({duration:.2f}s).")
    return buffers


def _derive_peaks(buffers: dict[str, list[JetDriveSample]]) -> PeakInfo:
    rpm_key = next((k for k in buffers if k == "rpm"), None)
    tq_key = next((k for k in buffers if k == "torque"), None)
    if rpm_key is None or tq_key is None:
        raise RuntimeError("RPM and Torque channels are required to derive peaks.")
    rpm_samples = buffers[rpm_key]
    tq_samples = buffers[tq_key]
    if not rpm_samples or not tq_samples:
        raise RuntimeError("Insufficient RPM/Torque samples to derive peaks.")

    # Align by timestamp: use simple dict by timestamp for torque
    tq_by_ts = {getattr(s, "timestamp_ms", 0): s.value for s in tq_samples}
    max_tq = max(tq_samples, key=lambda s: s.value)
    max_tq_rpm = next(
        (
            r.value
            for r in rpm_samples
            if getattr(r, "timestamp_ms", None) == getattr(max_tq, "timestamp_ms", None)
        ),
        rpm_samples[-1].value,
    )
    hp_peaks: list[tuple[float, float]] = []
    for r in rpm_samples:
        if getattr(r, "timestamp_ms", None) in tq_by_ts:
            tq = tq_by_ts[getattr(r, "timestamp_ms", 0)]
            hp = tq * r.value / 5252.0
            hp_peaks.append((hp, r.value))
    if not hp_peaks:
        hp_peaks.append((max_tq.value * max_tq_rpm / 5252.0, max_tq_rpm))
    max_hp_val, max_hp_rpm = max(hp_peaks, key=lambda x: x[0])

    return PeakInfo(
        max_hp=max_hp_val,
        hp_peak_rpm=max_hp_rpm,
        max_tq=max_tq.value,
        tq_peak_rpm=max_tq_rpm,
    )


def _handle_jetdrive(args: argparse.Namespace) -> int:
    # Discover providers
    providers = asyncio.run(discover_providers(timeout=args.timeout))
    try:
        provider = _select_provider(providers, args.provider)
    except RuntimeError as exc:
        names = ", ".join(f"{p.name}({p.provider_id})" for p in providers) or "none"
        print(f"{exc}\nDiscovered: {names}")
        return 1

    requested_channels = [c.strip() for c in args.channels.split(",") if c.strip()]
    if not requested_channels:
        print("No channels specified.")
        return 1

    try:
        _validate_channels(provider, requested_channels)
    except RuntimeError as exc:
        print(exc)
        return 1

    print(f"Selected provider: {provider.name} ({provider.provider_id})")
    print(f"Subscribing to channels: {', '.join(requested_channels)}")

    try:
        buffers = asyncio.run(
            _collect_jetdrive_run(
                provider,
                required_channels=requested_channels,
                min_duration=args.min_duration,
                max_duration=args.max_duration,
                rpm_start_threshold=args.rpm_start_threshold,
                rpm_end_threshold=args.rpm_end_threshold,
                trigger_mode=args.trigger,
                overall_timeout=args.timeout,
            )
        )
    except RuntimeError as exc:
        print(exc)
        return 1

    peaks = _derive_peaks(buffers)
    family = cast(EngineFamily, args.family)
    df = generate_winpep8_like_run(
        peaks=peaks,
        family=family,
        displacement_ci=args.displacement_ci,
        rpm_points=400,
    )

    run_id = _normalize_run_id(args.run_id)
    output_path = save_winpep8_run(run_id, df)
    print("Saved synthetic WinPEP8 run from JetDrive:")
    print(f"  output: {output_path}")
    print(f"  family: {family}")
    print(f"  peaks : {asdict(peaks)}")

    if args.restream_jetdrive:
        try:
            print("Re-streaming synthetic samples back to JetDrive (experimental)...")
            asyncio.run(
                publish_run(
                    provider,
                    [],  # Not re-streaming until structured mapping is defined
                )
            )
        except Exception:
            print("JetDrive re-stream not implemented; use CSV import instead.")

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.subcommand is None:
        # Backward compatibility: treat as peaks path
        return _handle_peaks(args)
    if args.subcommand == "peaks":
        return _handle_peaks(args)
    if args.subcommand == "jetdrive-run":
        return _handle_jetdrive(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
