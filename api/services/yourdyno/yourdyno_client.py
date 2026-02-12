from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

DEFAULT_HOST = os.getenv("YOURDYNO_BRIDGE_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("YOURDYNO_BRIDGE_PORT", "9877"))
DEFAULT_CONNECT_TIMEOUT_SEC = float(os.getenv("YOURDYNO_CONNECT_TIMEOUT_SEC", "2.0"))
DEFAULT_RECONNECT_DELAY_SEC = float(os.getenv("YOURDYNO_RECONNECT_DELAY_SEC", "1.5"))
DEFAULT_RECV_CHUNK_BYTES = int(os.getenv("YOURDYNO_RECV_CHUNK_BYTES", "65536"))


@dataclass
class YourDynoClientConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    connect_timeout_sec: float = DEFAULT_CONNECT_TIMEOUT_SEC
    reconnect_delay_sec: float = DEFAULT_RECONNECT_DELAY_SEC
    recv_chunk_bytes: int = DEFAULT_RECV_CHUNK_BYTES

    @classmethod
    def from_env(cls) -> "YourDynoClientConfig":
        return cls(
            host=os.getenv("YOURDYNO_BRIDGE_HOST", DEFAULT_HOST),
            port=int(os.getenv("YOURDYNO_BRIDGE_PORT", str(DEFAULT_PORT))),
            connect_timeout_sec=float(
                os.getenv(
                    "YOURDYNO_CONNECT_TIMEOUT_SEC",
                    str(DEFAULT_CONNECT_TIMEOUT_SEC),
                )
            ),
            reconnect_delay_sec=float(
                os.getenv(
                    "YOURDYNO_RECONNECT_DELAY_SEC",
                    str(DEFAULT_RECONNECT_DELAY_SEC),
                )
            ),
            recv_chunk_bytes=int(
                os.getenv("YOURDYNO_RECV_CHUNK_BYTES", str(DEFAULT_RECV_CHUNK_BYTES))
            ),
        )


@dataclass
class YourDynoSample:
    """Normalized live sample emitted from the DynoAIBridge plugin."""

    timestamp_ms: int
    elapsed_s: float
    engine_rpm: float
    roller_rpm: float = 0.0
    horsepower: float = 0.0
    torque_ftlb: float = 0.0
    horsepower_wheel: float = 0.0
    torque_wheel_ftlb: float = 0.0
    afr: float | None = None
    afr_front: float | None = None
    afr_rear: float | None = None
    map_kpa: float | None = None
    tps: float | None = None
    iat_f: float | None = None
    ect_f: float | None = None
    force_lbs: float | None = None
    acceleration: float | None = None
    speed_mph: float | None = None
    ambient_temp_f: float | None = None
    ambient_pressure_inhg: float | None = None
    ambient_humidity: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_ms": self.timestamp_ms,
            "elapsed_s": self.elapsed_s,
            "engine_rpm": self.engine_rpm,
            "roller_rpm": self.roller_rpm,
            "horsepower": self.horsepower,
            "torque_ftlb": self.torque_ftlb,
            "horsepower_wheel": self.horsepower_wheel,
            "torque_wheel_ftlb": self.torque_wheel_ftlb,
            "afr": self.afr,
            "afr_front": self.afr_front,
            "afr_rear": self.afr_rear,
            "map_kpa": self.map_kpa,
            "tps": self.tps,
            "iat_f": self.iat_f,
            "ect_f": self.ect_f,
            "force_lbs": self.force_lbs,
            "acceleration": self.acceleration,
            "speed_mph": self.speed_mph,
            "ambient_temp_f": self.ambient_temp_f,
            "ambient_pressure_inhg": self.ambient_pressure_inhg,
            "ambient_humidity": self.ambient_humidity,
        }


@dataclass
class YourDynoClientStats:
    lines_received: int = 0
    samples_received: int = 0
    reconnect_count: int = 0
    parse_errors: int = 0
    last_hello: float = 0.0
    last_sample_ts: float = 0.0
    last_error: str | None = None
    connected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "lines_received": self.lines_received,
            "samples_received": self.samples_received,
            "reconnect_count": self.reconnect_count,
            "parse_errors": self.parse_errors,
            "last_hello": self.last_hello,
            "last_sample_ts": self.last_sample_ts,
            "last_error": self.last_error,
            "connected": self.connected,
        }


class YourDynoClient:
    """
    Connects to the DynoAIBridge TCP server and streams JSON-lines samples.

    Expected bridge:
    - host: 127.0.0.1
    - port: 9877
    - first line: {"type":"hello", ...}
    - subsequent lines: sample JSON payloads
    """

    def __init__(self, config: YourDynoClientConfig | None = None):
        self.config = config or YourDynoClientConfig.from_env()
        self.stats = YourDynoClientStats()

        self._on_sample: Callable[[YourDynoSample], None] | None = None
        self._on_status: Callable[[dict[str, Any]], None] | None = None

        self._running = False
        self._thread: threading.Thread | None = None
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self.stats.connected

    def start(
        self,
        on_sample: Callable[[YourDynoSample], None],
        on_status: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if self._running:
            logger.warning("YourDyno client already running")
            return

        self._on_sample = on_sample
        self._on_status = on_status

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_forever,
            name="yourdyno-client",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "YourDyno client started (host=%s port=%d)",
            self.config.host,
            self.config.port,
        )

    def stop(self) -> None:
        if not self._running:
            return

        self._running = False
        self._stop_event.set()
        self._close_socket()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

        with self._lock:
            self.stats.connected = False

        logger.info("YourDyno client stopped")

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return self.stats.to_dict()

    def _run_forever(self) -> None:
        while self._running and not self._stop_event.is_set():
            try:
                self._connect_and_read()
            except Exception as exc:
                with self._lock:
                    self.stats.last_error = str(exc)
                    self.stats.connected = False
                    self.stats.reconnect_count += 1

                self._emit_status(
                    {
                        "type": "error",
                        "message": str(exc),
                        "host": self.config.host,
                        "port": self.config.port,
                    }
                )
                logger.debug("YourDyno connect/read loop error: %s", exc)

                if self._stop_event.wait(self.config.reconnect_delay_sec):
                    break

    def _connect_and_read(self) -> None:
        sock = socket.create_connection(
            (self.config.host, self.config.port),
            timeout=self.config.connect_timeout_sec,
        )
        sock.settimeout(1.0)
        self._sock = sock

        with self._lock:
            self.stats.connected = True
            self.stats.last_error = None

        self._emit_status(
            {
                "type": "connected",
                "host": self.config.host,
                "port": self.config.port,
            }
        )

        logger.info(
            "Connected to DynoAIBridge at %s:%d",
            self.config.host,
            self.config.port,
        )

        buffer = bytearray()
        while self._running and not self._stop_event.is_set():
            try:
                chunk = sock.recv(self.config.recv_chunk_bytes)
            except socket.timeout:
                continue
            except OSError as exc:
                raise RuntimeError(f"socket read failed: {exc}") from exc

            if not chunk:
                raise RuntimeError("bridge closed connection")

            buffer.extend(chunk)
            while True:
                nl = buffer.find(b"\n")
                if nl < 0:
                    break

                line = bytes(buffer[:nl]).decode("utf-8", errors="replace").strip()
                del buffer[: nl + 1]
                if not line:
                    continue

                with self._lock:
                    self.stats.lines_received += 1

                self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            with self._lock:
                self.stats.parse_errors += 1
            return

        if isinstance(payload, dict) and payload.get("type") == "hello":
            with self._lock:
                self.stats.last_hello = time.time()
            self._emit_status({"type": "hello", **payload})
            return

        sample = self._parse_sample(payload)
        if sample is None:
            with self._lock:
                self.stats.parse_errors += 1
            return

        with self._lock:
            self.stats.samples_received += 1
            self.stats.last_sample_ts = time.time()

        if self._on_sample:
            self._on_sample(sample)

    def _parse_sample(self, payload: Any) -> YourDynoSample | None:
        if not isinstance(payload, dict):
            return None

        ts = _coerce_float(payload.get("ts"))
        elapsed = _coerce_float(payload.get("elapsed"), default=0.0)
        rpm = _coerce_float(payload.get("engine_rpm"), default=0.0)

        if ts is None:
            return None

        timestamp_ms = _to_timestamp_ms(ts)

        if rpm <= 0.0:
            rpm = _coerce_float(payload.get("current_rpm"), default=0.0)

        return YourDynoSample(
            timestamp_ms=timestamp_ms,
            elapsed_s=elapsed,
            engine_rpm=rpm,
            roller_rpm=_coerce_float(payload.get("roller_rpm"), default=0.0),
            horsepower=_coerce_float(payload.get("engine_hp"), default=0.0),
            torque_ftlb=_coerce_float(payload.get("engine_torque_ftlb"), default=0.0),
            horsepower_wheel=_coerce_float(payload.get("wheel_hp"), default=0.0),
            torque_wheel_ftlb=_coerce_float(
                payload.get("wheel_torque_ftlb"), default=0.0
            ),
            afr=_coerce_float(payload.get("afr")),
            afr_front=_coerce_float(payload.get("afr_front")),
            afr_rear=_coerce_float(payload.get("afr_rear")),
            map_kpa=_coerce_float(payload.get("map_kpa")),
            tps=_coerce_float(payload.get("tps")),
            iat_f=_coerce_float(payload.get("iat_f")),
            ect_f=_coerce_float(payload.get("engine_temp_f")),
            force_lbs=_coerce_float(payload.get("force_lbs")),
            acceleration=_coerce_float(payload.get("acceleration")),
            speed_mph=_coerce_float(payload.get("speed_mph")),
            ambient_temp_f=_coerce_float(payload.get("ambient_temp_f")),
            ambient_pressure_inhg=_coerce_float(payload.get("ambient_pressure_inhg")),
            ambient_humidity=_coerce_float(payload.get("ambient_humidity")),
            raw=payload,
        )

    def _emit_status(self, status: dict[str, Any]) -> None:
        if self._on_status:
            try:
                self._on_status(status)
            except Exception:
                logger.exception("YourDyno status callback failed")

    def _close_socket(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            finally:
                self._sock = None


def _coerce_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_timestamp_ms(ts: float) -> int:
    """
    Bridge can emit seconds with fractional precision.
    Normalize all inputs to integer milliseconds.
    """
    if ts <= 0:
        return int(time.time() * 1000)
    # If it's already very large, treat as milliseconds.
    if ts > 1e11:
        return int(ts)
    return int(ts * 1000.0)

