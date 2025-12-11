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
DEFAULT_MCAST_GROUP = os.getenv("JETDRIVE_MCAST_GROUP", "224.0.2.10")
DEFAULT_PORT = int(os.getenv("JETDRIVE_PORT", "22344"))
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
        value = data[cls.HEADER.size : cls.HEADER.size + length]
        return key, length, host, seq, dest, value


def _clean_utf8(buf: bytes) -> str:
    return buf.decode("utf-8", errors="replace").split("\0", 1)[0].strip()


def _make_socket(cfg: JetDriveConfig) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    reuseport = getattr(socket, "SO_REUSEPORT", None)
    if reuseport is not None:
        with contextlib.suppress(OSError):
            sock.setsockopt(socket.SOL_SOCKET, reuseport, 1)
    bind_addr = cfg.iface or "0.0.0.0"
    try:
        sock.bind((bind_addr, cfg.port))
    except OSError:
        sock.bind(("", cfg.port))
    mreq = socket.inet_aton(cfg.multicast_group) + socket.inet_aton(bind_addr)
    with contextlib.suppress(OSError):
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.setblocking(False)
    return sock


def _parse_channel_info(
    host_id: int, host_ip: str, value: bytes
) -> JetDriveProviderInfo | None:
    if len(value) < PROVIDER_NAME_LEN:
        return None
    provider_name = _clean_utf8(value[:PROVIDER_NAME_LEN]) or "JetDrive Provider"
    idx = PROVIDER_NAME_LEN
    channels: dict[int, ChannelInfo] = {}
    while idx + CHANNEL_INFO_BLOCK <= len(value):
        chan_id = int.from_bytes(value[idx : idx + 2], "little")
        idx += 2
        vendor = value[idx]
        idx += 1
        raw_name = value[idx : idx + CHANNEL_NAME_LEN]
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
        port=DEFAULT_PORT,
        channels=channels,
    )


def _parse_channel_values(
    provider_id: int, channel_lookup: dict[int, ChannelInfo], value: bytes
) -> list[JetDriveSample]:
    samples: list[JetDriveSample] = []
    idx = 0
    while idx + CHANNEL_VALUES_BLOCK <= len(value):
        chan_id = int.from_bytes(value[idx : idx + 2], "little")
        idx += 2
        ts = int.from_bytes(value[idx : idx + 4], "little")
        idx += 4
        try:
            val = struct.unpack_from("<f", value, idx)[0]
        except struct.error:
            break
        idx += 4
        chan = channel_lookup.get(chan_id)
        name = chan.name if chan else f"chan_{chan_id}"
        samples.append(
            JetDriveSample(
                provider_id=provider_id,
                channel_id=chan_id,
                channel_name=name,
                timestamp_ms=ts,
                value=float(val),
            )
        )
    return samples


def parse_frame(
    data: bytes,
    channel_lookup: dict[int, ChannelInfo] | None = None,
    *,
    host_ip: str = "",
):
    decoded = _Wire.decode(data)
    if not decoded:
        return None
    key, _, host, _, _, value = decoded
    if key == KEY_CHANNEL_INFO:
        return key, _parse_channel_info(host, host_ip, value)
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


async def discover_providers(
    config: JetDriveConfig | None = None,
    timeout: float = 2.0,
) -> list[JetDriveProviderInfo]:
    """
    Join multicast, broadcast RequestChannelInfo, and collect ChannelInfo replies.
    """
    cfg = config or JetDriveConfig.from_env()
    loop = asyncio.get_running_loop()
    sock = _make_socket(cfg)
    seq = random.randint(1, 0xFF)
    host_id = random.randint(1, 0xFFFE)

    await send_request_channel_info(sock, cfg, host_id=host_id, seq=seq, dest=ALL_HOSTS)

    providers: dict[int, JetDriveProviderInfo] = {}
    deadline = loop.time() + timeout

    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                data, addr = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 4096), remaining
                )
            except asyncio.TimeoutError:
                break
            decoded = _Wire.decode(data)
            if not decoded:
                continue
            key, _, host, _, _, value = decoded
            if key == KEY_CHANNEL_INFO:
                try:
                    info = _parse_channel_info(host, addr[0], value)
                except Exception:
                    continue
                if info:
                    providers[host] = info
            # Ping/Pong and other keys are ignored for now
    finally:
        sock.close()
    return list(providers.values())


async def subscribe(
    provider: JetDriveProviderInfo,
    channel_names: list[str],
    on_sample: Callable[[JetDriveSample], None],
    *,
    config: JetDriveConfig | None = None,
    stop_event: asyncio.Event | None = None,
    recv_timeout: float = 0.5,
) -> None:
    """
    Listen for ChannelValues from a provider and invoke the callback.
    """
    cfg = config or JetDriveConfig.from_env()
    loop = asyncio.get_running_loop()
    sock = _make_socket(cfg)

    channel_lookup = provider.channels
    allowed_ids = set()
    if channel_names:
        names = {n.strip().lower() for n in channel_names}
        for chan_id, meta in channel_lookup.items():
            if meta.name.lower() in names:
                allowed_ids.add(chan_id)

    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            try:
                data, _ = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 4096), recv_timeout
                )
            except asyncio.TimeoutError:
                continue
            decoded = _Wire.decode(data)
            if not decoded:
                continue
            key, _, host, _, _, value = decoded
            if key != KEY_CHANNEL_VALUES or host != provider.provider_id:
                continue
            try:
                samples = _parse_channel_values(
                    provider.provider_id, channel_lookup, value
                )
            except Exception:
                # Skip malformed payloads
                continue
            for sample in samples:
                if allowed_ids and sample.channel_id not in allowed_ids:
                    continue
                on_sample(sample)
    finally:
        sock.close()


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
    """
    cfg = config or JetDriveConfig.from_env()
    opts = options or JetDrivePublishOptions()
    loop = asyncio.get_running_loop()
    sock = _make_socket(cfg)
    host_id = provider.provider_id or random.randint(1, 0xFFFE)
    seq = random.randint(1, 0xFF)

    try:
        while True:
            block = list(samples)
            if not block:
                return
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
