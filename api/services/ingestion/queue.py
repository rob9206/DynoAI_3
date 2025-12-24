"""
Ingestion Queue System

Provides queue-based ingestion for offline resilience:
- Priority-based queue with multiple levels
- Disk persistence for crash recovery
- Batch processing for efficiency
- Backpressure handling
- Dead letter queue for failed items
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable

from .config import QueueSettings

logger = logging.getLogger(__name__)


class QueuePriority(IntEnum):
    """Priority levels for queue items."""

    CRITICAL = 0  # Process immediately (e.g., safety-critical data)
    HIGH = 1  # High priority (e.g., real-time sensor data)
    NORMAL = 2  # Normal priority (e.g., historical data)
    LOW = 3  # Low priority (e.g., metadata, diagnostics)
    BATCH = 4  # Batch processing (e.g., bulk imports)


@dataclass
class QueueItem:
    """Item in the ingestion queue."""

    id: str
    source: str
    data: dict[str, Any]
    priority: int = QueuePriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0
    max_retries: int = 3
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: "QueueItem") -> bool:
        """Compare by priority then timestamp for priority queue."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "data": self.data,
            "priority": self.priority,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueueItem":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            source=data.get("source", "unknown"),
            data=data.get("data", {}),
            priority=data.get("priority", QueuePriority.NORMAL),
            timestamp=data.get("timestamp", time.time()),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )

    def can_retry(self) -> bool:
        """Check if item can be retried."""
        return self.retry_count < self.max_retries


@dataclass
class QueueStats:
    """Statistics for the ingestion queue."""

    total_enqueued: int = 0
    total_processed: int = 0
    total_failed: int = 0
    total_dropped: int = 0
    current_size: int = 0
    high_watermark: int = 0
    processing_rate_per_sec: float = 0.0
    average_latency_ms: float = 0.0
    last_process_time: float = 0.0
    items_by_priority: dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_enqueued": self.total_enqueued,
            "total_processed": self.total_processed,
            "total_failed": self.total_failed,
            "total_dropped": self.total_dropped,
            "current_size": self.current_size,
            "high_watermark": self.high_watermark,
            "processing_rate_per_sec": round(self.processing_rate_per_sec, 2),
            "average_latency_ms": round(self.average_latency_ms, 2),
            "last_process_time": self.last_process_time,
            "items_by_priority": self.items_by_priority,
        }


class IngestionQueue:
    """
    Priority queue for data ingestion with persistence support.

    Features:
    - Priority-based ordering
    - Optional disk persistence
    - Batch processing
    - Dead letter queue for failures
    - Statistics and monitoring
    """

    def __init__(self, settings: QueueSettings | None = None):
        self.settings = settings or QueueSettings()
        self._queue: queue.PriorityQueue[QueueItem] = queue.PriorityQueue(
            maxsize=self.settings.max_size
        )
        self._dead_letter_queue: list[QueueItem] = []
        self._stats = QueueStats()
        self._lock = threading.Lock()
        self._processing = False
        self._process_thread: threading.Thread | None = None
        self._processor: Callable[[QueueItem], bool] | None = None
        self._latency_samples: list[float] = []

        # Persistence
        if self.settings.persist_to_disk:
            self._persist_path = Path(self.settings.persist_path)
            self._persist_path.mkdir(parents=True, exist_ok=True)
            self._load_persisted()

    def enqueue(
        self,
        source: str,
        data: dict[str, Any],
        priority: int = QueuePriority.NORMAL,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Add item to the queue.

        Returns:
            Item ID if enqueued, None if dropped
        """
        item = QueueItem(
            id=str(uuid.uuid4()),
            source=source,
            data=data,
            priority=priority,
            metadata=metadata or {},
        )

        with self._lock:
            # Check if queue is full
            if self._queue.full():
                if self.settings.drop_on_full:
                    if self.settings.drop_oldest:
                        # Try to remove oldest item
                        try:
                            dropped = self._queue.get_nowait()
                            self._stats.total_dropped += 1
                            logger.warning(
                                f"Queue full, dropped oldest item: {dropped.id}"
                            )
                        except queue.Empty:
                            pass
                    else:
                        # Drop new item
                        self._stats.total_dropped += 1
                        logger.warning(f"Queue full, dropped new item: {item.id}")
                        return None
                else:
                    logger.warning("Queue full and drop disabled, blocking...")

            try:
                self._queue.put(item, block=not self.settings.drop_on_full, timeout=1.0)
                self._stats.total_enqueued += 1
                self._stats.current_size = self._queue.qsize()
                self._stats.high_watermark = max(
                    self._stats.high_watermark, self._stats.current_size
                )

                # Track by priority
                self._stats.items_by_priority[priority] = (
                    self._stats.items_by_priority.get(priority, 0) + 1
                )

                # Persist if enabled
                if self.settings.persist_to_disk:
                    self._persist_item(item)

                return item.id
            except queue.Full:
                self._stats.total_dropped += 1
                return None

    def dequeue(self, timeout: float | None = None) -> QueueItem | None:
        """
        Remove and return highest priority item.

        Args:
            timeout: Timeout in seconds, None for non-blocking

        Returns:
            QueueItem or None if empty
        """
        try:
            if timeout is None:
                item = self._queue.get_nowait()
            else:
                item = self._queue.get(block=True, timeout=timeout)

            with self._lock:
                self._stats.current_size = self._queue.qsize()

            return item
        except queue.Empty:
            return None

    def peek(self) -> QueueItem | None:
        """Peek at highest priority item without removing."""
        # PriorityQueue doesn't support peek, so we use internal queue
        with self._lock:
            if not self._queue.queue:
                return None
            # Internal heap is a list
            return min(self._queue.queue)

    def process_batch(
        self,
        processor: Callable[[QueueItem], bool],
        batch_size: int | None = None,
    ) -> int:
        """
        Process a batch of items.

        Args:
            processor: Function that processes item, returns True on success
            batch_size: Number of items to process

        Returns:
            Number of items successfully processed
        """
        batch_size = batch_size or self.settings.batch_size
        processed = 0
        failed_items = []

        for _ in range(batch_size):
            item = self.dequeue()
            if item is None:
                break

            start_time = time.time()
            try:
                success = processor(item)

                if success:
                    processed += 1
                    with self._lock:
                        self._stats.total_processed += 1

                    # Remove from persistence
                    if self.settings.persist_to_disk:
                        self._remove_persisted_item(item.id)
                else:
                    failed_items.append(item)
            except Exception as e:
                logger.error(f"Error processing item {item.id}: {e}")
                item.error = str(e)
                failed_items.append(item)

            # Track latency
            latency = (time.time() - start_time) * 1000
            self._latency_samples.append(latency)
            if len(self._latency_samples) > 100:
                self._latency_samples = self._latency_samples[-100:]

        # Handle failed items
        for item in failed_items:
            item.retry_count += 1
            if item.can_retry():
                # Re-enqueue with lower priority
                item.priority = min(item.priority + 1, QueuePriority.BATCH)
                try:
                    self._queue.put_nowait(item)
                except queue.Full:
                    self._send_to_dead_letter(item)
            else:
                self._send_to_dead_letter(item)

        # Update stats
        with self._lock:
            self._stats.last_process_time = time.time()
            if self._latency_samples:
                self._stats.average_latency_ms = sum(self._latency_samples) / len(
                    self._latency_samples
                )

        return processed

    def start_processing(
        self,
        processor: Callable[[QueueItem], bool],
        interval: float | None = None,
    ) -> None:
        """Start background processing thread."""
        if self._processing:
            logger.warning("Processing already started")
            return

        self._processor = processor
        self._processing = True
        interval = interval or self.settings.flush_interval_sec

        def process_loop():
            last_process = 0.0
            while self._processing:
                try:
                    now = time.time()
                    # Process if interval elapsed or queue is filling up
                    should_process = (
                        now - last_process >= interval
                        or self._queue.qsize() > self.settings.max_size * 0.8
                    )

                    if should_process and not self._queue.empty():
                        processed = self.process_batch(self._processor)
                        if processed > 0:
                            # Calculate rate
                            elapsed = now - last_process if last_process else 1.0
                            with self._lock:
                                self._stats.processing_rate_per_sec = processed / elapsed
                        last_process = now

                    time.sleep(0.1)  # Small sleep to prevent busy waiting
                except Exception as e:
                    logger.error(f"Error in processing loop: {e}")
                    time.sleep(1.0)

        self._process_thread = threading.Thread(target=process_loop, daemon=True)
        self._process_thread.start()
        logger.info("Queue processing started")

    def stop_processing(self) -> None:
        """Stop background processing."""
        self._processing = False
        if self._process_thread:
            self._process_thread.join(timeout=5.0)
            self._process_thread = None
        logger.info("Queue processing stopped")

    def _send_to_dead_letter(self, item: QueueItem) -> None:
        """Send failed item to dead letter queue."""
        with self._lock:
            self._dead_letter_queue.append(item)
            self._stats.total_failed += 1

            # Limit dead letter queue size
            if len(self._dead_letter_queue) > 1000:
                self._dead_letter_queue = self._dead_letter_queue[-1000:]

        if self.settings.persist_to_disk:
            self._persist_dead_letter(item)

        logger.warning(
            f"Item {item.id} sent to dead letter queue after {item.retry_count} retries"
        )

    def get_dead_letter_items(
        self, limit: int = 100
    ) -> list[QueueItem]:
        """Get items from dead letter queue."""
        with self._lock:
            return self._dead_letter_queue[:limit]

    def retry_dead_letter(self, item_id: str) -> bool:
        """Retry a specific dead letter item."""
        with self._lock:
            for i, item in enumerate(self._dead_letter_queue):
                if item.id == item_id:
                    item.retry_count = 0
                    item.error = None
                    self._dead_letter_queue.pop(i)
                    try:
                        self._queue.put_nowait(item)
                        return True
                    except queue.Full:
                        self._dead_letter_queue.append(item)
                        return False
        return False

    def clear_dead_letter(self) -> int:
        """Clear all dead letter items."""
        with self._lock:
            count = len(self._dead_letter_queue)
            self._dead_letter_queue.clear()
            return count

    def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        with self._lock:
            self._stats.current_size = self._queue.qsize()
            return self._stats

    def clear(self) -> int:
        """Clear all items from queue."""
        count = 0
        with self._lock:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    count += 1
                except queue.Empty:
                    break
            self._stats.current_size = 0
            self._stats.items_by_priority.clear()
        return count

    # Persistence methods

    def _persist_item(self, item: QueueItem) -> None:
        """Persist item to disk."""
        if not self.settings.persist_to_disk:
            return

        try:
            item_path = self._persist_path / f"{item.id}.json"
            with open(item_path, "w", encoding="utf-8") as f:
                json.dump(item.to_dict(), f)
        except Exception as e:
            logger.error(f"Failed to persist item {item.id}: {e}")

    def _remove_persisted_item(self, item_id: str) -> None:
        """Remove persisted item."""
        if not self.settings.persist_to_disk:
            return

        try:
            item_path = self._persist_path / f"{item_id}.json"
            if item_path.exists():
                item_path.unlink()
        except Exception as e:
            logger.error(f"Failed to remove persisted item {item_id}: {e}")

    def _persist_dead_letter(self, item: QueueItem) -> None:
        """Persist dead letter item."""
        if not self.settings.persist_to_disk:
            return

        try:
            dl_path = self._persist_path / "dead_letter"
            dl_path.mkdir(exist_ok=True)
            item_path = dl_path / f"{item.id}.json"
            with open(item_path, "w", encoding="utf-8") as f:
                json.dump(item.to_dict(), f)
        except Exception as e:
            logger.error(f"Failed to persist dead letter item {item.id}: {e}")

    def _load_persisted(self) -> None:
        """Load persisted items on startup."""
        if not self.settings.persist_to_disk:
            return

        try:
            loaded = 0
            for item_path in self._persist_path.glob("*.json"):
                try:
                    with open(item_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    item = QueueItem.from_dict(data)
                    self._queue.put_nowait(item)
                    loaded += 1
                except Exception as e:
                    logger.warning(f"Failed to load persisted item {item_path}: {e}")

            # Load dead letter items
            dl_path = self._persist_path / "dead_letter"
            if dl_path.exists():
                for item_path in dl_path.glob("*.json"):
                    try:
                        with open(item_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        item = QueueItem.from_dict(data)
                        self._dead_letter_queue.append(item)
                    except Exception as e:
                        logger.warning(f"Failed to load dead letter item {item_path}: {e}")

            if loaded > 0:
                logger.info(f"Loaded {loaded} persisted queue items")
        except Exception as e:
            logger.error(f"Failed to load persisted items: {e}")

    def __len__(self) -> int:
        return self._queue.qsize()

    def __bool__(self) -> bool:
        return not self._queue.empty()


# =============================================================================
# Batch Operations
# =============================================================================


def enqueue_batch(
    queue: IngestionQueue,
    items: list[tuple[str, dict[str, Any]]],
    priority: int = QueuePriority.BATCH,
) -> list[str | None]:
    """
    Enqueue multiple items efficiently.

    Args:
        queue: The ingestion queue
        items: List of (source, data) tuples
        priority: Priority for all items

    Returns:
        List of item IDs (or None for dropped items)
    """
    results = []
    for source, data in items:
        item_id = queue.enqueue(source, data, priority=priority)
        results.append(item_id)
    return results


def drain_queue(
    queue: IngestionQueue,
    processor: Callable[[QueueItem], bool],
    max_items: int = 10000,
    timeout_sec: float = 60.0,
) -> int:
    """
    Process all items in queue until empty or limits reached.

    Returns:
        Total items processed
    """
    start_time = time.time()
    total_processed = 0

    while total_processed < max_items and time.time() - start_time < timeout_sec:
        processed = queue.process_batch(processor)
        if processed == 0:
            break
        total_processed += processed

    return total_processed


