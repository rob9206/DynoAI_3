"""Server-Sent Events (SSE) progress broadcaster for real-time updates."""

import json
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ProgressEvent:
    """A progress event to broadcast."""

    run_id: str
    event_type: str  # 'stage', 'complete', 'error'
    data: Dict[str, Any]


class ProgressBroadcaster:
    """
    Broadcasts progress events to connected SSE clients.

    Each run can have multiple connected clients receiving real-time updates.
    """

    def __init__(self):
        """Initialize the broadcaster."""
        self._subscribers: Dict[str, List[queue.Queue]] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 60  # seconds

    def subscribe(self, run_id: str) -> Generator[str, None, None]:
        """
        Subscribe to progress events for a run.

        Args:
            run_id: The run ID to subscribe to

        Yields:
            SSE formatted event strings
        """
        client_queue: queue.Queue = queue.Queue()

        with self._lock:
            if run_id not in self._subscribers:
                self._subscribers[run_id] = []
            self._subscribers[run_id].append(client_queue)

        try:
            # Send initial connection event
            yield self._format_sse("connected", {"run_id": run_id})

            while True:
                try:
                    # Wait for events with timeout to allow periodic keepalive
                    event = client_queue.get(timeout=30)
                    if event is None:
                        # None signals end of stream
                        break
                    yield self._format_sse(event.event_type, event.data)
                except queue.Empty:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        finally:
            # Clean up subscription
            with self._lock:
                if run_id in self._subscribers:
                    try:
                        self._subscribers[run_id].remove(client_queue)
                    except ValueError:
                        pass
                    if not self._subscribers[run_id]:
                        del self._subscribers[run_id]

    def broadcast_stage(
        self,
        run_id: str,
        stage: str,
        substage: Optional[str] = None,
        progress: Optional[int] = None,
    ) -> None:
        """
        Broadcast a stage progress update.

        Args:
            run_id: The run ID
            stage: Current processing stage
            substage: Optional substage name
            progress: Optional progress percentage (0-100)
        """
        event = ProgressEvent(
            run_id=run_id,
            event_type="stage",
            data={
                "run_id": run_id,
                "stage": stage,
                "substage": substage,
                "progress": progress,
            },
        )
        self._broadcast(run_id, event)

    def broadcast_complete(
        self, run_id: str, results_summary: Optional[Dict] = None
    ) -> None:
        """
        Broadcast a completion event.

        Args:
            run_id: The run ID
            results_summary: Optional summary of results
        """
        event = ProgressEvent(
            run_id=run_id,
            event_type="complete",
            data={
                "run_id": run_id,
                "status": "complete",
                "results_summary": results_summary or {},
            },
        )
        self._broadcast(run_id, event)

        # Signal end of stream for this run
        self._end_stream(run_id)

    def broadcast_error(self, run_id: str, stage: str, code: str, message: str) -> None:
        """
        Broadcast an error event.

        Args:
            run_id: The run ID
            stage: Stage where error occurred
            code: Error code
            message: Error message
        """
        event = ProgressEvent(
            run_id=run_id,
            event_type="error",
            data={
                "run_id": run_id,
                "error": {
                    "stage": stage,
                    "code": code,
                    "message": message,
                },
            },
        )
        self._broadcast(run_id, event)

        # Signal end of stream for this run
        self._end_stream(run_id)

    def _broadcast(self, run_id: str, event: ProgressEvent) -> None:
        """Broadcast an event to all subscribers for a run."""
        with self._lock:
            subscribers = self._subscribers.get(run_id, [])
            for client_queue in subscribers:
                try:
                    client_queue.put_nowait(event)
                except queue.Full:
                    logger.warning(f"Client queue full for run {run_id}")

    def _end_stream(self, run_id: str) -> None:
        """Signal end of stream for all subscribers of a run."""
        with self._lock:
            subscribers = self._subscribers.get(run_id, [])
            for client_queue in subscribers:
                try:
                    client_queue.put_nowait(None)
                except queue.Full:
                    pass

    def _format_sse(self, event_type: str, data: Dict[str, Any]) -> str:
        """Format data as SSE event string."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    def has_subscribers(self, run_id: str) -> bool:
        """Check if a run has any subscribers."""
        with self._lock:
            return run_id in self._subscribers and len(self._subscribers[run_id]) > 0


# Global broadcaster instance
_broadcaster: Optional[ProgressBroadcaster] = None


def get_broadcaster() -> ProgressBroadcaster:
    """Get or create the global broadcaster instance."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = ProgressBroadcaster()
    return _broadcaster
