from __future__ import annotations

import asyncio
import contextlib
import os
import random
import socket
import struct
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable

# KLHDV transport defaults (overridable via env vars)
# 224.0.2.10 = Official Dynojet/JetDrive vendor multicast address
DEFAULT_MCAST_GROUP = os.getenv("JETDRIVE_MCAST_GROUP", "224.0.2.10")
DEFAULT_PORT = int(os.getenv("JETDRIVE_PORT", "22344"))
# Default to all interfaces (0.0.0.0) to receive from external devices like Dynoware RT.
# Set JETDRIVE_IFACE to a specific IP (e.g., 169.254.x.x) if you need to bind to a particular interface.
DEFAULT_IFACE = os.getenv("JETDRIVE_IFACE", "0.0.0.0")
ALL_HOSTS = 0xFFFF

# Message keys
KEY_CHANNEL_INFO = 0x01
KEY_CHANNEL_VALUES = 0x02
KEY_CLEAR_CHANNEL_INFO = 0x03
KEY_PING = 0x04
KEY_PONG = 0x05
KEY_REQUEST_CHANNEL_INFO = 0x06

PROVIDER_NAME_LEN = 50
CHANNEL_NAME_LEN = 30
CHANNEL_INFO_BLOCK = 34  # id(2) + vendor(1) + name(30) + unit(1)
CHANNEL_VALUES_BLOCK = 10  # id(2) + ts(4) + float(4)


class JDUnit(IntEnum):
    Time = 0
    Distance = 1
    Speed = 2
    Force = 3
    Power = 4
    Torque = 5
    Temperature = 6
    Pressure = 7
    EngineSpeed = 8
    RPM = 8
    GearRatio = 9
    Acceleration = 10
    AFR = 11
    FlowRate = 12
    Lambda = 13
    Volts = 14
    Amps = 15
    Percentage = 16
    Extended = 254
    NoUnit = 255


# =============================================================================
# Comprehensive Channel Registry
# =============================================================================
# Single source of truth for channel ID -> canonical name + metadata mapping.
# Used when RT module broadcasts values without channel info metadata.
#
# Categories:
#   - atmospheric: Environmental sensors (humidity, temp, pressure)
#   - dyno: Dyno core measurements (RPM, force, power, torque, speed)
#   - afr: Air/fuel ratio sensors
#   - engine: Engine parameters (MAP, TPS, IAT, etc.)
#   - misc: System/diagnostic channels
# =============================================================================

CHANNEL_CATEGORIES = {
    "atmospheric": {"label": "Atmospheric", "icon": "Cloud", "order": 1},
    "dyno": {"label": "Dyno", "icon": "Gauge", "order": 2},
    "afr": {"label": "Air/Fuel", "icon": "Flame", "order": 3},
    "engine": {"label": "Engine", "icon": "Zap", "order": 4},
    "misc": {"label": "System", "icon": "Activity", "order": 5},
}

CHANNEL_REGISTRY: dict[int, dict[str, str | int | float]] = {
    # =========================================================================
    # ATMOSPHERIC PROBE CHANNELS (IDs 6-9, 35-38)
    # =========================================================================
    6: {"name": "Humidity", "category": "atmospheric", "units": "%"},
    7: {"name": "Temperature 1", "category": "atmospheric", "units": "°C"},
    8: {"name": "Temperature 2", "category": "atmospheric", "units": "°C"},
    9: {"name": "Pressure", "category": "atmospheric", "units": "kPa"},
    35: {"name": "Humidity", "category": "atmospheric", "units": "%"},
    36: {"name": "Temperature 1", "category": "atmospheric", "units": "°C"},
    37: {"name": "Temperature 2", "category": "atmospheric", "units": "°C"},
    38: {"name": "Pressure", "category": "atmospheric", "units": "kPa"},
    
    # =========================================================================
    # DYNO CORE CHANNELS (Drum, Force, Power, Torque)
    # =========================================================================
    # RPM Channels
    10: {"name": "Digital RPM 1", "category": "dyno", "units": "rpm"},
    11: {"name": "Digital RPM 2", "category": "dyno", "units": "rpm"},
    39: {"name": "Digital RPM 1", "category": "dyno", "units": "rpm"},
    40: {"name": "Digital RPM 2", "category": "dyno", "units": "rpm"},
    
    # Force/Drum Channels
    12: {"name": "Force Drum 1", "category": "dyno", "units": "lbs"},
    19: {"name": "Force Drum 2", "category": "dyno", "units": "lbs"},
    32: {"name": "Force", "category": "dyno", "units": "lbs"},
    34: {"name": "Force 1", "category": "dyno", "units": "lbs"},
    
    # Power/Torque Channels
    3: {"name": "Torque", "category": "dyno", "units": "ft-lb"},
    4: {"name": "Horsepower", "category": "dyno", "units": "HP"},
    5: {"name": "Power", "category": "dyno", "units": "HP"},
    
    # Speed/Distance/Acceleration
    1: {"name": "Speed", "category": "dyno", "units": "mph"},
    2: {"name": "Distance", "category": "dyno", "units": "ft"},
    13: {"name": "Acceleration", "category": "dyno", "units": "g"},
    14: {"name": "Speed 1", "category": "dyno", "units": "mph"},
    
    # =========================================================================
    # AIR/FUEL RATIO CHANNELS
    # =========================================================================
    # User Analog inputs (typically LC-2 Wideband sensors)
    20: {"name": "User Analog 1", "category": "afr", "units": ":1"},  # AFR Front
    21: {"name": "User Analog 2", "category": "afr", "units": ":1"},  # AFR Rear
    22: {"name": "User Analog 3", "category": "afr", "units": "V"},
    23: {"name": "User Analog 4", "category": "afr", "units": "V"},
    
    # Named AFR channels
    24: {"name": "Air/Fuel Ratio 1", "category": "afr", "units": ":1"},
    25: {"name": "Air/Fuel Ratio 2", "category": "afr", "units": ":1"},
    26: {"name": "Lambda 1", "category": "afr", "units": "λ"},
    27: {"name": "Lambda 2", "category": "afr", "units": "λ"},
    
    # =========================================================================
    # ENGINE PARAMETER CHANNELS
    # =========================================================================
    28: {"name": "MAP", "category": "engine", "units": "kPa"},
    29: {"name": "TPS", "category": "engine", "units": "%"},
    30: {"name": "IAT", "category": "engine", "units": "°F"},
    31: {"name": "ECT", "category": "engine", "units": "°F"},
    33: {"name": "VBatt", "category": "engine", "units": "V"},
    
    # =========================================================================
    # SYSTEM/DIAGNOSTIC CHANNELS
    # =========================================================================
    0: {"name": "Sampling", "category": "misc", "units": ""},
    15: {"name": "Correction Factor", "category": "misc", "units": ""},
    16: {"name": "Gear Ratio", "category": "misc", "units": ""},
    17: {"name": "Internal Temp 1", "category": "misc", "units": "°C"},
    18: {"name": "Internal Temp 2", "category": "misc", "units": "°C"},
}

# Legacy fallback for backwards compatibility
FALLBACK_CHANNEL_NAMES = {chan_id: info["name"] for chan_id, info in CHANNEL_REGISTRY.items()}


def get_channel_info_from_registry(chan_id: int) -> dict[str, str | int | float] | None:
    """
    Get channel info from the registry by ID.
    Returns dict with name, category, units or None if not found.
    """
    return CHANNEL_REGISTRY.get(chan_id)


@dataclass
class JetDriveConfig:
    multicast_group: str = DEFAULT_MCAST_GROUP
    port: int = DEFAULT_PORT
    iface: str = DEFAULT_IFACE

    @classmethod
    def from_env(cls) -> JetDriveConfig:
        return cls(
            multicast_group=os.getenv("JETDRIVE_MCAST_GROUP", DEFAULT_MCAST_GROUP),
            port=int(os.getenv("JETDRIVE_PORT", DEFAULT_PORT)),
            iface=os.getenv("JETDRIVE_IFACE", DEFAULT_IFACE),
        )


@dataclass
class ChannelInfo:
    chan_id: int
    name: str
    unit: int
    vendor: int = 0


@dataclass
class JetDriveProviderInfo:
    provider_id: int
    name: str
    host: str
    port: int
    channels: dict[int, ChannelInfo] = field(default_factory=dict)


@dataclass
class JetDriveSample:
    provider_id: int
    channel_id: int
    channel_name: str
    timestamp_ms: int
    value: float
    category: str = "misc"  # Channel category (atmospheric, dyno, afr, engine, misc)
    units: str = ""  # Channel units


@dataclass
class JetDrivePublishOptions:
    playback_rate: float = 1.0
    loop: bool = False


class _Wire:
    # key(u8), len(u16), host(u16), seq(u8), dest(u16)
    HEADER = struct.Struct("<B H H B H")

    @classmethod
    def encode(cls, key: int, host: int, dest: int, seq: int, value: bytes) -> bytes:
        return cls.HEADER.pack(key, len(value), host, seq & 0xFF, dest) + value

    @classmethod
    def decode(cls, data: bytes):
        if len(data) < cls.HEADER.size:
            return None
        try:
            key, length, host, seq, dest = cls.HEADER.unpack_from(data, 0)
        except struct.error:
            return None
        if len(data) < cls.HEADER.size + length:
            return None
        value = data[cls.HEADER.size: cls.HEADER.size + length]
        return key, length, host, seq, dest, value


def _clean_utf8(buf: bytes) -> str:
    return buf.decode("utf-8", errors="replace").split("\0", 1)[0].strip()


def _resolve_iface_address(iface: str) -> str:
    """
    Resolve the configured interface to an IP address.
    Accepts dotted-quad or resolvable hostname.
    Raises a clear error on failure.
    """
    target = iface.strip() if iface else "0.0.0.0"
    try:
        # If already an IP, inet_aton will succeed.
        socket.inet_aton(target)
        return target
    except OSError:
        # Fall back to DNS/hosts resolution for names.
        try:
            return socket.gethostbyname(target)
        except OSError as exc:
            raise RuntimeError(f"Invalid interface '{iface}': {exc}") from exc


def _make_socket(cfg: JetDriveConfig) -> socket.socket:
    # #region agent log
    import json as _json; _log_path = r"c:\Users\dawso\OneDrive\Documents\GitHub\DynoAI_3\.cursor\debug.log"
    with open(_log_path, "a") as _f: _f.write(_json.dumps({"location":"jetdrive_client.py:_make_socket:entry","message":"Creating socket","data":{"iface":cfg.iface,"multicast_group":cfg.multicast_group,"port":cfg.port},"hypothesisId":"H5","timestamp":__import__("time").time()}) + "\n")
    # #endregion
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    reuseport = getattr(socket, "SO_REUSEPORT", None)
    if reuseport is not None:
        with contextlib.suppress(OSError):
            sock.setsockopt(socket.SOL_SOCKET, reuseport, 1)

    iface_ip = _resolve_iface_address(cfg.iface)
    # #region agent log
    with open(_log_path, "a") as _f: _f.write(_json.dumps({"location":"jetdrive_client.py:_make_socket:resolved_iface","message":"Resolved interface","data":{"cfg_iface":cfg.iface,"resolved_ip":iface_ip},"hypothesisId":"H5","timestamp":__import__("time").time()}) + "\n")
    # #endregion
    # On Windows, bind to 0.0.0.0 but join multicast on the specific interface
    # This allows receiving from all sources while directing multicast traffic correctly
    bind_ip = "0.0.0.0"
    try:
        sock.bind((bind_ip, cfg.port))
        # #region agent log
        with open(_log_path, "a") as _f: _f.write(_json.dumps({"location":"jetdrive_client.py:_make_socket:bind_success","message":"Socket bound successfully","data":{"bind_ip":bind_ip,"iface_ip":iface_ip,"port":cfg.port},"hypothesisId":"H5","timestamp":__import__("time").time()}) + "\n")
        # #endregion
    except OSError as exc:
        # #region agent log
        with open(_log_path, "a") as _f: _f.write(_json.dumps({"location":"jetdrive_client.py:_make_socket:bind_failed","message":"BIND FAILED","data":{"bind_ip":bind_ip,"iface_ip":iface_ip,"port":cfg.port,"error":str(exc),"errno":exc.errno},"hypothesisId":"H5","timestamp":__import__("time").time()}) + "\n")
        # #endregion
        sock.close()
        raise RuntimeError(
            f"Failed to bind JetDrive socket on {bind_ip}:{cfg.port}: {exc}"
        ) from exc

    # Join multicast on the configured interface (iface_ip).
    # This MUST match the interface Dynoware RT is broadcasting on.
    multicast_iface = iface_ip if iface_ip else "0.0.0.0"
    mreq = socket.inet_aton(cfg.multicast_group) + socket.inet_aton(multicast_iface)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        # #region agent log
        with open(_log_path, "a") as _f: _f.write(_json.dumps({"location":"jetdrive_client.py:_make_socket:multicast_joined","message":"Joined multicast group","data":{"group":cfg.multicast_group,"multicast_iface":multicast_iface,"cfg_iface":iface_ip},"hypothesisId":"H6","timestamp":__import__("time").time()}) + "\n")
        # #endregion
    except OSError as exc:
        # #region agent log
        with open(_log_path, "a") as _f: _f.write(_json.dumps({"location":"jetdrive_client.py:_make_socket:multicast_failed","message":"MULTICAST JOIN FAILED","data":{"group":cfg.multicast_group,"multicast_iface":multicast_iface,"error":str(exc),"errno":exc.errno},"hypothesisId":"H6","timestamp":__import__("time").time()}) + "\n")
        # #endregion
        sock.close()
        raise RuntimeError(
            f"Failed to join multicast group {cfg.multicast_group} on {multicast_iface}: {exc}"
        ) from exc

    sock.setblocking(False)
    return sock


def _parse_channel_info(
    host_id: int,
    host_ip: str,
    value: bytes,
    *,
    port: int = DEFAULT_PORT,
) -> JetDriveProviderInfo | None:
    """Parse a ChannelInfo payload into provider metadata."""
    if len(value) < PROVIDER_NAME_LEN:
        return None
    provider_name = _clean_utf8(value[:PROVIDER_NAME_LEN]) or "JetDrive Provider"
    idx = PROVIDER_NAME_LEN
    channels: dict[int, ChannelInfo] = {}
    while idx + CHANNEL_INFO_BLOCK <= len(value):
        chan_id = int.from_bytes(value[idx: idx + 2], "little")
        idx += 2
        vendor = value[idx]
        idx += 1
        raw_name = value[idx: idx + CHANNEL_NAME_LEN]
        idx += CHANNEL_NAME_LEN
        unit = value[idx]
        idx += 1
        channels[chan_id] = ChannelInfo(
            chan_id=chan_id,
            name=_clean_utf8(raw_name),
            unit=unit,
            vendor=vendor,
        )
    return JetDriveProviderInfo(
        provider_id=host_id,
        name=provider_name,
        host=host_ip,
        port=port,
        channels=channels,
    )


def _parse_channel_values(
    provider_id: int, channel_lookup: dict[int, ChannelInfo], value: bytes
) -> list[JetDriveSample]:
    """
    Parse channel values from a JetDrive wire frame.
    
    Name resolution priority:
    1. Hardware ChannelInfo metadata (if available)
    2. CHANNEL_REGISTRY by ID (comprehensive known channels)
    3. Generic fallback name (chan_X)
    """
    samples: list[JetDriveSample] = []
    idx = 0
    while idx + CHANNEL_VALUES_BLOCK <= len(value):
        chan_id = int.from_bytes(value[idx: idx + 2], "little")
        idx += 2
        ts = int.from_bytes(value[idx: idx + 4], "little")
        idx += 4
        try:
            val = struct.unpack_from("<f", value, idx)[0]
        except struct.error:
            break
        idx += 4
        
        # Resolve channel name, category, and units
        chan = channel_lookup.get(chan_id)
        registry_info = get_channel_info_from_registry(chan_id)
        
        if chan and chan.name:
            # Priority 1: Hardware ChannelInfo metadata has the name - TRUST IT
            name = chan.name
            # Infer category from channel name
            name_lower = name.lower()
            if any(x in name_lower for x in ['humidity', 'temperature', 'pressure', 'atmospheric']):
                category = "atmospheric"
            elif any(x in name_lower for x in ['rpm', 'force', 'power', 'torque', 'speed', 'distance', 'acceleration']):
                category = "dyno"
            elif any(x in name_lower for x in ['afr', 'lambda', 'lc2', 'lc1', 'fuel', 'o2']):
                category = "afr"
            elif any(x in name_lower for x in ['map', 'tps', 'iat', 'ect', 'vbat', 'volt']):
                category = "engine"
            else:
                category = "misc"
            units = ""  # Let frontend handle units based on name
        elif registry_info:
            # Priority 2: Use CHANNEL_REGISTRY (fallback for channels without metadata)
            name = str(registry_info["name"])
            category = str(registry_info.get("category", "misc"))
            units = str(registry_info.get("units", ""))
        else:
            # Priority 3: Generic fallback with channel ID
            name = f"Channel {chan_id}"
            category = "misc"
            units = ""
        
        samples.append(
            JetDriveSample(
                provider_id=provider_id,
                channel_id=chan_id,
                channel_name=name,
                timestamp_ms=ts,
                value=float(val),
                category=category,
                units=units,
            )
        )
    return samples


def parse_frame(
    data: bytes,
    channel_lookup: dict[int, ChannelInfo] | None = None,
    *,
    host_ip: str = "",
    port: int = DEFAULT_PORT,
) -> tuple[int, JetDriveProviderInfo | list[JetDriveSample] | None] | None:
    """
    Parse a JetDrive wire frame.

    Returns:
        None if frame is malformed, otherwise (key, payload) where payload is:
        - JetDriveProviderInfo for KEY_CHANNEL_INFO
        - list[JetDriveSample] for KEY_CHANNEL_VALUES
        - None for other keys
    """
    decoded = _Wire.decode(data)
    if not decoded:
        return None
    key, _, host, _, _, value = decoded
    if key == KEY_CHANNEL_INFO:
        return key, _parse_channel_info(host, host_ip, value, port=port)
    if key == KEY_CHANNEL_VALUES:
        return key, _parse_channel_values(host, channel_lookup or {}, value)
    return key, None


async def send_request_channel_info(
    sock: socket.socket,
    cfg: JetDriveConfig,
    host_id: int,
    seq: int,
    dest: int = ALL_HOSTS,
) -> None:
    msg = _Wire.encode(KEY_REQUEST_CHANNEL_INFO, host_id, dest, seq, b"")
    loop = asyncio.get_running_loop()
    await loop.sock_sendto(sock, msg, (cfg.multicast_group, cfg.port))


# Cache provider info across discoveries so we don't lose channel names
_provider_cache: dict[int, JetDriveProviderInfo] = {}


def merge_all_providers(providers: list[JetDriveProviderInfo]) -> JetDriveProviderInfo:
    """
    Merge all discovered providers into a single "virtual" provider.
    This is useful because Power Core CPU and Atmospheric Probe are separate providers
    but we want to treat them as one for the UI.
    """
    if not providers:
        return JetDriveProviderInfo(
            provider_id=0,
            name="No Providers",
            host="",
            port=DEFAULT_PORT,
            channels={},
        )
    
    if len(providers) == 1:
        return providers[0]
    
    # Merge all channels, using unique IDs
    merged_channels: dict[int, ChannelInfo] = {}
    provider_names = []
    
    for p in providers:
        provider_names.append(f"{p.name} (0x{p.provider_id:04X})")
        for chan_id, chan_info in p.channels.items():
            # If channel ID already exists, use provider-prefixed ID to avoid collision
            if chan_id in merged_channels:
                # Create a unique ID by combining provider ID and channel ID
                unique_id = (p.provider_id << 16) | chan_id
                merged_channels[unique_id] = ChannelInfo(
                    chan_id=unique_id,
                    name=chan_info.name,
                    unit=chan_info.unit,
                    vendor=chan_info.vendor,
                )
            else:
                merged_channels[chan_id] = chan_info
    
    return JetDriveProviderInfo(
        provider_id=providers[0].provider_id,  # Use first provider's ID as primary
        name=" + ".join(provider_names),
        host=providers[0].host,
        port=providers[0].port,
        channels=merged_channels,
    )


def get_all_cached_channels() -> dict[int, ChannelInfo]:
    """Get all channels from all cached providers."""
    all_channels: dict[int, ChannelInfo] = {}
    for provider in _provider_cache.values():
        all_channels.update(provider.channels)
    return all_channels


def _discover_providers_sync(
    cfg: JetDriveConfig,
    timeout: float = 2.0,
) -> list[JetDriveProviderInfo]:
    """
    Synchronous discovery using blocking sockets (works reliably on Windows).
    Caches provider info so channel names persist even if ChannelInfo isn't re-sent.
    
    Note: Power Core sends multiple ChannelInfo packets (e.g., 39 channels + 3 channels).
    This function MERGES them instead of overwriting, ensuring all channels are captured.
    """
    global _provider_cache
    import time
    
    # Create BLOCKING socket (don't call _make_socket which sets non-blocking)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", cfg.port))
    
    # Join BOTH multicast groups on specific interface (Power Core may use either)
    for group in [cfg.multicast_group, "224.0.2.10"]:
        try:
            mreq = socket.inet_aton(group) + socket.inet_aton(cfg.iface)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except Exception:
            pass  # May fail if already joined
    
    # Set timeout for blocking recv
    sock.settimeout(1.0)
    
    # Send RequestChannelInfo to request ChannelInfo (Key=1) from providers
    seq = random.randint(1, 0xFF)
    host_id = random.randint(1, 0xFFFE)
    msg = _Wire.encode(KEY_REQUEST_CHANNEL_INFO, host_id, ALL_HOSTS, seq, b"")
    sock.sendto(msg, (cfg.multicast_group, cfg.port))
    
    providers: dict[int, JetDriveProviderInfo] = {}
    deadline = time.time() + timeout
    
    try:
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
                decoded = _Wire.decode(data)
                if not decoded:
                    continue
                key, _, host, _, _, value = decoded
                
                if key == KEY_CHANNEL_INFO:
                    try:
                        info = _parse_channel_info(host, addr[0], value, port=cfg.port)
                        if info:
                            # MERGE channels instead of overwriting
                            # Power Core sends multiple ChannelInfo packets that should be combined
                            if host in providers:
                                providers[host].channels.update(info.channels)
                            else:
                                providers[host] = info
                            _provider_cache[host] = providers[host]  # Cache the merged version
                    except Exception:
                        continue
                elif key == KEY_CHANNEL_VALUES and host not in providers:
                    # Check cache first - use cached info if we have it
                    if host in _provider_cache:
                        providers[host] = _provider_cache[host]
                    else:
                        # Create minimal entry - we know a provider exists at this host
                        providers[host] = JetDriveProviderInfo(
                            provider_id=host,
                            name=f"JetDrive Provider 0x{host:04X}",
                            host=addr[0],
                            port=cfg.port,
                            channels={},  # Empty dict - unknown until ChannelInfo received
                        )
            except socket.timeout:
                continue
    finally:
        sock.close()
    
    return list(providers.values())


async def discover_providers(
    config: JetDriveConfig | None = None,
    timeout: float = 2.0,
) -> list[JetDriveProviderInfo]:
    """
    Join multicast, broadcast RequestChannelInfo, and collect ChannelInfo replies.
    Uses synchronous blocking socket in a thread pool (works reliably on Windows).
    """
    cfg = config or JetDriveConfig.from_env()
    # Run sync discovery in thread pool to avoid blocking event loop
    return await asyncio.to_thread(_discover_providers_sync, cfg, timeout)


def _subscribe_sync(
    provider: JetDriveProviderInfo,
    channel_names: list[str],
    on_sample: Callable[[JetDriveSample], None],
    cfg: JetDriveConfig,
    stop_flag: list,  # Use mutable list as thread-safe flag [False]
    recv_timeout: float = 0.5,
    debug: bool = False,
    accept_all_providers: bool = True,  # NEW: Accept data from ALL providers
) -> dict[str, int]:
    """
    Synchronous subscribe using blocking sockets (works reliably on Windows).
    
    Args:
        accept_all_providers: If True, accept ChannelValues from ANY provider on the network.
            This is necessary because Power Core CPU and Atmospheric Probe are separate providers.
    """
    global _provider_cache
    
    # Create BLOCKING socket for Windows multicast compatibility
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", cfg.port))
    
    # Join multicast on specific interface
    for group in [cfg.multicast_group, "224.0.2.10"]:
        try:
            mreq = socket.inet_aton(group) + socket.inet_aton(cfg.iface)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except Exception:
            pass
    
    sock.settimeout(recv_timeout)

    # Build channel lookup from provider AND cache (for multi-provider support)
    channel_lookup = dict(provider.channels)
    for cached_provider in _provider_cache.values():
        for chan_id, chan_info in cached_provider.channels.items():
            if chan_id not in channel_lookup:
                channel_lookup[chan_id] = chan_info
    
    allowed_ids = set()
    if channel_names:
        names = {n.strip().lower() for n in channel_names}
        for chan_id, meta in channel_lookup.items():
            if meta.name.lower() in names:
                allowed_ids.add(chan_id)

    dropped_frames = 0
    non_provider_frames = 0
    total_frames = 0
    accepted_providers: set[int] = set()

    try:
        while not stop_flag[0]:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue

            total_frames += 1
            decoded = _Wire.decode(data)
            if not decoded:
                dropped_frames += 1
                continue
            key, _, host, _, _, value = decoded
            
            # Handle ChannelInfo packets - update cache dynamically
            if key == KEY_CHANNEL_INFO:
                try:
                    info = _parse_channel_info(host, addr[0], value, port=cfg.port)
                    if info:
                        _provider_cache[host] = info
                        # Merge into our channel lookup
                        for chan_id, chan_info in info.channels.items():
                            if chan_id not in channel_lookup:
                                channel_lookup[chan_id] = chan_info
                except Exception:
                    pass
                continue
            
            if key != KEY_CHANNEL_VALUES:
                continue
                
            # Accept data from specified provider OR all providers
            if not accept_all_providers and host != provider.provider_id:
                non_provider_frames += 1
                continue
            
            accepted_providers.add(host)
            
            # Get channel lookup for this specific provider if available
            provider_channels = _provider_cache.get(host, provider).channels if host in _provider_cache else channel_lookup
            
            try:
                samples = _parse_channel_values(
                    host, provider_channels, value
                )
            except Exception:
                dropped_frames += 1
                continue
            for sample in samples:
                if allowed_ids and sample.channel_id not in allowed_ids:
                    continue
                on_sample(sample)
    finally:
        sock.close()
        if debug:
            print(
                f"[jetdrive_client._subscribe_sync] dropped_frames={dropped_frames}, "
                f"non_provider_frames={non_provider_frames}, total_frames={total_frames}, "
                f"accepted_providers={[hex(p) for p in accepted_providers]}",
                flush=True,
            )

    return {
        "dropped_frames": dropped_frames,
        "non_provider_frames": non_provider_frames,
        "total_frames": total_frames,
        "accepted_providers": list(accepted_providers),
    }


async def subscribe(
    provider: JetDriveProviderInfo,
    channel_names: list[str],
    on_sample: Callable[[JetDriveSample], None],
    *,
    config: JetDriveConfig | None = None,
    stop_event: asyncio.Event | None = None,
    recv_timeout: float = 0.5,
    debug: bool = False,
    return_stats: bool = False,
) -> dict[str, int] | None:
    """
    Listen for ChannelValues from a provider and invoke the callback.
    Uses synchronous blocking socket in a thread (works reliably on Windows).
    """
    cfg = config or JetDriveConfig.from_env()
    
    # Use a mutable list as a thread-safe stop flag
    stop_flag = [False]
    
    async def monitor_stop():
        if stop_event:
            await stop_event.wait()
            stop_flag[0] = True
    
    # Start stop monitor task
    monitor_task = asyncio.create_task(monitor_stop()) if stop_event else None
    
    try:
        # Run sync subscribe in thread pool
        result = await asyncio.to_thread(
            _subscribe_sync,
            provider, channel_names, on_sample, cfg, stop_flag, recv_timeout, debug
        )
        if return_stats:
            return result
        return None
    finally:
        stop_flag[0] = True
        if monitor_task:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass


async def run_until_cancelled(
    provider: JetDriveProviderInfo,
    channel_names: list[str],
    on_sample: Callable[[JetDriveSample], None],
    *,
    config: JetDriveConfig | None = None,
) -> None:
    stop_event = asyncio.Event()
    try:
        await subscribe(
            provider, channel_names, on_sample, config=config, stop_event=stop_event
        )
    except asyncio.CancelledError:
        stop_event.set()
        raise


async def publish_run(
    provider: JetDriveProviderInfo,
    samples: Iterable[JetDriveSample],
    options: JetDrivePublishOptions | None = None,
    *,
    config: JetDriveConfig | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """
    Experimental: emit ChannelValues blocks back onto JetDrive.

    Args:
        provider: Provider info (provider_id must be 1-0xFFFE or 0 for random)
        samples: Iterable of samples to publish
        options: Playback options (rate, loop)
        config: Network config (defaults to env)
        stop_event: Optional event to signal stop
    """
    cfg = config or JetDriveConfig.from_env()
    opts = options or JetDrivePublishOptions()
    loop = asyncio.get_running_loop()
    sock = _make_socket(cfg)

    # Validate and resolve provider_id
    pid = provider.provider_id
    if pid == 0:
        pid = random.randint(1, 0xFFFE)
    elif not (1 <= pid <= 0xFFFE):
        raise ValueError(f"provider_id must be 0 (random) or 1-0xFFFE, got {pid}")
    host_id = pid
    seq = random.randint(1, 0xFF)

    # Convert iterable to list ONCE (outside loop for efficiency)
    block = list(samples)
    if not block:
        sock.close()
        return

    try:
        while True:
            payload = bytearray()
            for sample in block:
                payload.extend(
                    struct.pack(
                        "<HIf",
                        sample.channel_id,
                        int(sample.timestamp_ms),
                        float(sample.value),
                    )
                )
            try:
                msg = _Wire.encode(
                    KEY_CHANNEL_VALUES, host_id, ALL_HOSTS, seq, bytes(payload)
                )
            except Exception:
                break
            seq = (seq + 1) % 256
            await loop.sock_sendto(sock, msg, (cfg.multicast_group, cfg.port))
            await asyncio.sleep(max(0.0, 0.001 / max(opts.playback_rate, 1e-6)))
            if stop_event is not None and stop_event.is_set():
                return
            if not opts.loop:
                break
    finally:
        sock.close()


__all__ = [
    "ALL_HOSTS",
    "ChannelInfo",
    "JDUnit",
    "JetDriveConfig",
    "JetDriveProviderInfo",
    "JetDrivePublishOptions",
    "JetDriveSample",
    "KEY_CHANNEL_INFO",
    "KEY_CHANNEL_VALUES",
    "KEY_CLEAR_CHANNEL_INFO",
    "KEY_PING",
    "KEY_PONG",
    "KEY_REQUEST_CHANNEL_INFO",
    "discover_providers",
    "parse_frame",
    "publish_run",
    "run_until_cancelled",
    "send_request_channel_info",
    "subscribe",
]
