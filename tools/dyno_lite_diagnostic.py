#!/usr/bin/env python3
"""
DynoAI Lite Diagnostic - Dynoware RT-150 Data Confirmation Tool

A lightweight standalone app to verify data is flowing from:
- Dynojet Dynoware RT-150 dyno (via JetDrive UDP multicast)
- Wideband AFR sensors

Target: RT-150 at 192.168.1.115, JetDrive port 22344

Usage:
    python dyno_lite_diagnostic.py

Press Ctrl+C to exit.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass, field

# Add project root for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.services.jetdrive_client import (  # noqa: E402
    JDUnit,
    JetDriveConfig,
    JetDriveProviderInfo,
    JetDriveSample,
    discover_providers,
    subscribe,
)

# =============================================================================
# Configuration - Dynoware RT-150 Defaults
# =============================================================================

RT150_CONFIG = {
    "name": "Dynoware RT-150",
    "expected_ip": "192.168.1.115",
    "serial": "RT00220413",
    "drum_serial": "1000588",
    "drum_mass_slugs": 14.121,
    "drum_circumference_ft": 4.673,
    "firmware": "DWRT 2.1.7034.17067",
}

# Channels we care most about
PRIORITY_CHANNELS = {
    # Dyno channels
    "rpm": ["rpm", "engine rpm", "engine speed", "drum rpm"],
    "force": ["force", "tractive force", "drum force"],
    "power": ["power", "hp", "horsepower", "wheel hp"],
    "torque": ["torque", "wheel torque", "ft-lb"],
    "speed": ["speed", "mph", "vehicle speed", "drum speed"],
    # Wideband AFR channels (these confirm wideband is connected)
    "afr": ["afr", "a/f", "air fuel", "wideband", "lambda", "o2"],
    "afr_front": ["afr front", "afr f", "afr1", "front o2", "wb1"],
    "afr_rear": ["afr rear", "afr r", "afr2", "rear o2", "wb2"],
}

# Unit name mapping
UNIT_NAMES = {
    JDUnit.RPM: "RPM",
    JDUnit.Force: "lbf",
    JDUnit.Power: "HP",
    JDUnit.Torque: "ft-lb",
    JDUnit.Speed: "MPH",
    JDUnit.AFR: "AFR",
    JDUnit.Lambda: "λ",
    JDUnit.Temperature: "°F",
    JDUnit.Pressure: "psi",
    JDUnit.Percentage: "%",
    JDUnit.Volts: "V",
}


class Colors:
    """ANSI colors for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"


# Check if terminal supports colors
USE_COLORS = sys.stdout.isatty() and os.name != "nt" or os.environ.get("TERM")


def c(text: str, color: str) -> str:
    """Apply color if terminal supports it."""
    if USE_COLORS:
        return f"{color}{text}{Colors.RESET}"
    return text


# =============================================================================
# Data Tracking
# =============================================================================


@dataclass
class ChannelStats:
    """Track statistics for a single channel."""

    name: str
    unit: int
    last_value: float = 0.0
    min_value: float = float("inf")
    max_value: float = float("-inf")
    sample_count: int = 0
    last_update: float = 0.0
    values_per_second: float = 0.0
    _recent_times: list[float] = field(default_factory=list)

    def update(self, value: float, timestamp: float):
        self.last_value = value
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)
        self.sample_count += 1
        self.last_update = timestamp

        # Track sample rate (last 2 seconds of timestamps)
        now = time.time()
        self._recent_times.append(now)
        self._recent_times = [t for t in self._recent_times if now - t < 2.0]
        if len(self._recent_times) > 1:
            self.values_per_second = len(self._recent_times) / 2.0

    @property
    def is_stale(self) -> bool:
        """Channel is stale if no update in 2 seconds."""
        return time.time() - self.last_update > 2.0 if self.last_update > 0 else True

    @property
    def unit_name(self) -> str:
        """Get human-readable unit name."""
        try:
            unit_enum = JDUnit(self.unit)
            return UNIT_NAMES.get(unit_enum, "")
        except ValueError:
            return ""


@dataclass
class DiagnosticState:
    """Global diagnostic state."""

    provider: JetDriveProviderInfo | None = None
    channels: dict[int, ChannelStats] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    total_samples: int = 0
    connection_status: str = "disconnected"
    last_error: str = ""

    # Wideband detection
    wideband_detected: bool = False
    afr_channels: list[str] = field(default_factory=list)

    def get_channel_by_name(self, name: str) -> ChannelStats | None:
        """Find channel by name (case-insensitive partial match)."""
        name_lower = name.lower()
        for ch in self.channels.values():
            if name_lower in ch.name.lower():
                return ch
        return None

    def categorize_channel(self, name: str) -> str | None:
        """Categorize a channel name into priority groups."""
        name_lower = name.lower()
        for category, keywords in PRIORITY_CHANNELS.items():
            if any(kw in name_lower for kw in keywords):
                return category
        return None


# =============================================================================
# Display Functions
# =============================================================================


def clear_screen():
    """Clear terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def print_header(state: DiagnosticState):
    """Print diagnostic header."""
    runtime = time.time() - state.start_time
    mins, secs = divmod(int(runtime), 60)

    print(c("=" * 70, Colors.CYAN))
    print(
        c(
            "  DynoAI Lite Diagnostic - Dynoware RT-150 Data Monitor",
            Colors.BOLD + Colors.CYAN,
        )
    )
    print(c("=" * 70, Colors.CYAN))
    print()

    # Connection status
    if state.connection_status == "connected":
        status = c(" ● CONNECTED ", Colors.BG_GREEN + Colors.WHITE + Colors.BOLD)
    elif state.connection_status == "searching":
        status = c(" ○ SEARCHING ", Colors.BG_YELLOW + Colors.WHITE)
    else:
        status = c(" ✗ DISCONNECTED ", Colors.BG_RED + Colors.WHITE)

    print(f"  Status: {status}  Runtime: {c(f'{mins:02d}:{secs:02d}', Colors.WHITE)}")

    if state.provider:
        print(
            f"  Provider: {c(state.provider.name, Colors.GREEN)} @ {c(state.provider.host, Colors.YELLOW)}"
        )
        print(
            f"  Channels: {c(str(len(state.provider.channels)), Colors.CYAN)} available, "
            f"{c(str(len(state.channels)), Colors.GREEN)} receiving data"
        )

    # Sample rate
    if state.total_samples > 0:
        rate = state.total_samples / max(runtime, 1)
        print(
            f"  Samples: {c(f'{state.total_samples:,}', Colors.WHITE)} total ({c(f'{rate:.1f}/sec', Colors.CYAN)})"
        )

    print()


def print_wideband_status(state: DiagnosticState):
    """Print wideband/AFR status section."""
    print(c("─" * 70, Colors.DIM))
    print(c("  WIDEBAND / AFR STATUS", Colors.BOLD + Colors.MAGENTA))
    print(c("─" * 70, Colors.DIM))

    afr_channels = []
    for ch in state.channels.values():
        category = state.categorize_channel(ch.name)
        if category and "afr" in category:
            afr_channels.append(ch)

    if afr_channels:
        state.wideband_detected = True
        print(f"  {c('✓ WIDEBAND DATA DETECTED', Colors.GREEN + Colors.BOLD)}")
        print()
        for ch in afr_channels:
            value_color = Colors.GREEN if 10 < ch.last_value < 18 else Colors.RED
            stale_indicator = c(" (stale)", Colors.RED) if ch.is_stale else ""
            print(
                f"    {ch.name:25} = {c(f'{ch.last_value:6.2f}', value_color)} AFR  "
                f"[{ch.min_value:.2f} - {ch.max_value:.2f}]{stale_indicator}"
            )
    else:
        print(c("  ✗ NO WIDEBAND DATA", Colors.RED))
        print("    Looking for AFR/Lambda channels...")
        print("    Ensure wideband controller is connected and streaming to JetDrive")

    print()


def print_dyno_channels(state: DiagnosticState):
    """Print dyno data channels."""
    print(c("─" * 70, Colors.DIM))
    print(c("  DYNO CHANNELS", Colors.BOLD + Colors.BLUE))
    print(c("─" * 70, Colors.DIM))

    # Categorize channels
    categorized: dict[str, list[ChannelStats]] = defaultdict(list)
    uncategorized: list[ChannelStats] = []

    for ch in sorted(state.channels.values(), key=lambda x: x.name):
        category = state.categorize_channel(ch.name)
        if category and "afr" not in category:  # AFR shown separately
            categorized[category].append(ch)
        elif category is None:
            uncategorized.append(ch)

    # Priority channels first
    priority_order = ["rpm", "force", "power", "torque", "speed"]
    for category in priority_order:
        if category in categorized:
            for ch in categorized[category]:
                _print_channel_line(ch)

    # Other channels
    if uncategorized:
        print()
        print(f"  {c('Other Channels:', Colors.DIM)}")
        for ch in uncategorized[:10]:  # Limit to 10
            _print_channel_line(ch, indent=4)
        if len(uncategorized) > 10:
            print(f"    ... and {len(uncategorized) - 10} more")

    print()


def _print_channel_line(ch: ChannelStats, indent: int = 2):
    """Print a single channel line."""
    stale = c("●", Colors.RED) if ch.is_stale else c("●", Colors.GREEN)
    unit = ch.unit_name or ""
    rate = f"{ch.values_per_second:.0f}/s" if ch.values_per_second > 0 else "---"

    print(
        f"  {' ' * indent}{stale} {ch.name:25} = {ch.last_value:12.2f} {unit:6}  "
        f"[{rate:>5}] samples:{ch.sample_count}"
    )


def print_channel_list(state: DiagnosticState):
    """Print all available channels from provider."""
    if not state.provider:
        return

    print(c("─" * 70, Colors.DIM))
    print(c("  ALL AVAILABLE CHANNELS", Colors.BOLD + Colors.YELLOW))
    print(c("─" * 70, Colors.DIM))

    for chan_id, info in sorted(
        state.provider.channels.items(), key=lambda x: x[1].name
    ):
        receiving = chan_id in state.channels
        indicator = c("●", Colors.GREEN) if receiving else c("○", Colors.DIM)
        print(f"    {indicator} [{chan_id:3}] {info.name}")

    print()


def print_instructions():
    """Print usage instructions."""
    print(c("─" * 70, Colors.DIM))
    print(
        f"  Press {c('Ctrl+C', Colors.YELLOW)} to exit  |  Data updates every {c('250ms', Colors.CYAN)}"
    )
    print(c("─" * 70, Colors.DIM))


def render_display(state: DiagnosticState, show_all_channels: bool = False):
    """Render the full diagnostic display."""
    clear_screen()
    print_header(state)
    print_wideband_status(state)
    print_dyno_channels(state)
    if show_all_channels:
        print_channel_list(state)
    print_instructions()


# =============================================================================
# Main Diagnostic Loop
# =============================================================================


async def run_diagnostic():
    """Main diagnostic routine."""
    state = DiagnosticState()
    state.connection_status = "searching"

    print(c("\n  DynoAI Lite Diagnostic - Starting...\n", Colors.CYAN + Colors.BOLD))
    print(f"  Target: {c(RT150_CONFIG['name'], Colors.GREEN)}")
    print(f"  Expected IP: {c(RT150_CONFIG['expected_ip'], Colors.YELLOW)}")
    print(f"  JetDrive Port: {c('22344', Colors.CYAN)}")
    print()

    # Configure JetDrive
    config = JetDriveConfig.from_env()
    print(
        f"  JetDrive config: {config.multicast_group}:{config.port} on {config.iface}"
    )
    print()

    # Discover providers
    print(c("  Searching for JetDrive providers...", Colors.YELLOW))

    try:
        providers = await discover_providers(config, timeout=5.0)
    except Exception as e:
        print(c(f"\n  ERROR: Failed to discover providers: {e}", Colors.RED))
        print(c("  Check network connection and firewall settings.", Colors.DIM))
        return

    if not providers:
        print(c("\n  No JetDrive providers found!", Colors.RED))
        print()
        print(c("  Troubleshooting:", Colors.YELLOW))
        print("    1. Ensure Dynoware RT is running")
        print("    2. Check that JetDrive broadcasting is enabled in Dynoware")
        print("    3. Verify network connectivity (ping 192.168.1.115)")
        print("    4. Check firewall allows UDP port 22344")
        print()

        # Offer to wait and retry
        print(c("  Retrying discovery...", Colors.YELLOW))
        for attempt in range(3):
            await asyncio.sleep(3)
            providers = await discover_providers(config, timeout=5.0)
            if providers:
                break
            print(f"    Attempt {attempt + 2}/4...")

        if not providers:
            print(
                c(
                    "\n  Could not find any JetDrive providers after multiple attempts.",
                    Colors.RED,
                )
            )
            return

    # Use first provider (should be the RT-150)
    state.provider = providers[0]
    state.connection_status = "connected"

    print(c(f"\n  ✓ Found: {state.provider.name}", Colors.GREEN + Colors.BOLD))
    print(f"    IP: {state.provider.host}")
    print(f"    Channels: {len(state.provider.channels)}")

    # Check if it's our expected RT-150
    if state.provider.host != RT150_CONFIG["expected_ip"]:
        print(
            c(
                f"\n  NOTE: Provider IP ({state.provider.host}) differs from expected "
                f"({RT150_CONFIG['expected_ip']})",
                Colors.YELLOW,
            )
        )

    print()
    print(c("  Starting data capture...", Colors.CYAN))
    await asyncio.sleep(1)

    # Set up sample callback
    def on_sample(sample: JetDriveSample):
        state.total_samples += 1

        if sample.channel_id not in state.channels:
            # Get unit from provider channel info
            unit = 0
            if state.provider and sample.channel_id in state.provider.channels:
                unit = state.provider.channels[sample.channel_id].unit

            state.channels[sample.channel_id] = ChannelStats(
                name=sample.channel_name,
                unit=unit,
            )

        state.channels[sample.channel_id].update(
            sample.value, sample.timestamp_ms / 1000.0
        )

    # Create stop event for clean shutdown
    stop_event = asyncio.Event()

    # Start subscription task
    subscribe_task = asyncio.create_task(
        subscribe(
            state.provider,
            [],  # Subscribe to all channels
            on_sample,
            config=config,
            stop_event=stop_event,
        )
    )

    # Display update loop
    last_render = 0.0
    render_interval = 0.25  # 250ms updates

    try:
        while True:
            now = time.time()
            if now - last_render >= render_interval:
                render_display(state)
                last_render = now
            await asyncio.sleep(0.05)

    except asyncio.CancelledError:
        pass
    finally:
        stop_event.set()
        subscribe_task.cancel()
        with suppress(asyncio.CancelledError):
            await subscribe_task


def main():
    """Entry point."""
    # Set console to UTF-8 for Windows
    if os.name == "nt":
        try:
            import sys

            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print(
        c(
            """
    ====================================================================
    
         DynoAI Lite Diagnostic
         Dynoware RT-150 Data Confirmation Tool
    
         Confirms data flow from:
           - Dynojet Dynoware RT dyno
           - Wideband AFR sensors
    
    ====================================================================
    """,
            Colors.CYAN,
        )
    )

    try:
        asyncio.run(run_diagnostic())
    except KeyboardInterrupt:
        print(c("\n\n  Diagnostic stopped by user.", Colors.YELLOW))
        print()


if __name__ == "__main__":
    main()
