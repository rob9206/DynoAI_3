"""Shared state for YourDyno live capture routes."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any

from api.services.yourdyno.yourdyno_client import YourDynoClient, YourDynoClientConfig

logger = logging.getLogger(__name__)

_live_data: dict[str, Any] = {
    "capturing": False,
    "connected": False,
    "channels": {},
    "last_update_ts": None,
    "last_update": None,
    "error": None,
    "status": "idle",
}
_live_data_lock = threading.Lock()
_live_data_event = threading.Event()

_sample_ring: deque[dict[str, Any]] = deque(maxlen=4000)

_client: YourDynoClient | None = None
_client_lock = threading.Lock()


def get_client() -> YourDynoClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = YourDynoClient(YourDynoClientConfig.from_env())
        return _client


def clear_live_buffers() -> None:
    with _live_data_lock:
        _live_data["channels"] = {}
        _live_data["last_update_ts"] = None
        _live_data["last_update"] = None
        _live_data["error"] = None
        _sample_ring.clear()
        _live_data_event.clear()


def mark_status(
    status: str, connected: bool | None = None, error: str | None = None
) -> None:
    with _live_data_lock:
        _live_data["status"] = status
        if connected is not None:
            _live_data["connected"] = connected
        if error is not None:
            _live_data["error"] = error
        _live_data["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S")
