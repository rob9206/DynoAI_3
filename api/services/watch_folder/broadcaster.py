"""SSE broadcaster + recent-event ring buffer for watch-folder events."""

from __future__ import annotations

import json
import queue
import threading
import time
from collections import deque
from typing import Any, Generator


class WatchFolderBroadcaster:
    """Broadcast watch-folder events to SSE clients."""

    def __init__(self, max_recent: int = 200):
        self._subscribers: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._recent: deque[dict[str, Any]] = deque(maxlen=max_recent)
        self._event_count = 0
        self._last_event_at: float | None = None

    def subscribe(self) -> Generator[str, None, None]:
        """Subscribe to events as an SSE stream generator."""
        client_queue: queue.Queue = queue.Queue(maxsize=200)
        with self._lock:
            self._subscribers.append(client_queue)

        try:
            yield self._format_sse("connected", {"status": "connected"})
            while True:
                try:
                    payload = client_queue.get(timeout=15)
                    if payload is None:
                        break
                    yield self._format_sse("watch_event", payload)
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            with self._lock:
                try:
                    self._subscribers.remove(client_queue)
                except ValueError:
                    pass

    def broadcast(self, payload: dict[str, Any]) -> None:
        """Broadcast one watch-folder payload to all subscribers."""
        with self._lock:
            self._event_count += 1
            self._last_event_at = time.time()
            self._recent.append(payload)
            subscribers = list(self._subscribers)

        for client_queue in subscribers:
            try:
                client_queue.put_nowait(payload)
            except queue.Full:
                continue

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return newest events first."""
        with self._lock:
            items = list(self._recent)
        if limit <= 0:
            return []
        return list(reversed(items[-limit:]))

    def status(self) -> dict[str, Any]:
        """Return broadcaster status summary."""
        with self._lock:
            return {
                "subscriber_count": len(self._subscribers),
                "event_count": self._event_count,
                "last_event_at": self._last_event_at,
            }

    @staticmethod
    def _format_sse(event_type: str, data: dict[str, Any]) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"

