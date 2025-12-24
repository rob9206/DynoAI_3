"""
Tests for ingestion queue system.

Tests:
- Queue operations (enqueue, dequeue)
- Priority handling
- Batch processing
- Dead letter queue
- Statistics tracking
- Persistence (if enabled)
"""

import pytest
import sys
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.services.ingestion.queue import (
    IngestionQueue,
    QueueItem,
    QueuePriority,
    QueueStats,
    enqueue_batch,
    drain_queue,
)
from api.services.ingestion.config import QueueSettings


class TestQueueItem:
    """Tests for QueueItem class."""

    def test_create_item(self):
        """Test creating a queue item."""
        item = QueueItem(
            id="test-1",
            source="jetdrive",
            data={"rpm": 3500},
        )
        assert item.id == "test-1"
        assert item.source == "jetdrive"
        assert item.priority == QueuePriority.NORMAL

    def test_item_ordering(self):
        """Test items are ordered by priority then timestamp."""
        item1 = QueueItem(id="1", source="test", data={}, priority=QueuePriority.HIGH, timestamp=100)
        item2 = QueueItem(id="2", source="test", data={}, priority=QueuePriority.LOW, timestamp=50)
        item3 = QueueItem(id="3", source="test", data={}, priority=QueuePriority.HIGH, timestamp=50)

        # Higher priority (lower number) comes first
        assert item1 < item2  # HIGH < LOW
        
        # Same priority, earlier timestamp comes first
        assert item3 < item1  # Same priority, earlier timestamp

    def test_can_retry(self):
        """Test retry logic."""
        item = QueueItem(id="1", source="test", data={}, max_retries=3)
        
        assert item.can_retry()
        item.retry_count = 2
        assert item.can_retry()
        item.retry_count = 3
        assert not item.can_retry()

    def test_to_dict(self):
        """Test serialization to dict."""
        item = QueueItem(
            id="test-1",
            source="jetdrive",
            data={"rpm": 3500},
            priority=QueuePriority.HIGH,
        )
        d = item.to_dict()
        assert d["id"] == "test-1"
        assert d["source"] == "jetdrive"
        assert d["data"]["rpm"] == 3500
        assert d["priority"] == QueuePriority.HIGH

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "id": "test-1",
            "source": "jetdrive",
            "data": {"rpm": 3500},
            "priority": QueuePriority.HIGH,
        }
        item = QueueItem.from_dict(data)
        assert item.id == "test-1"
        assert item.source == "jetdrive"
        assert item.priority == QueuePriority.HIGH


class TestIngestionQueue:
    """Tests for IngestionQueue class."""

    def test_create_queue(self):
        """Test creating a queue."""
        queue = IngestionQueue()
        assert len(queue) == 0
        assert not queue

    def test_enqueue_dequeue(self):
        """Test basic enqueue/dequeue."""
        queue = IngestionQueue()
        
        item_id = queue.enqueue("test", {"value": 1})
        assert item_id is not None
        assert len(queue) == 1
        
        item = queue.dequeue()
        assert item is not None
        assert item.data["value"] == 1
        assert len(queue) == 0

    def test_priority_ordering(self):
        """Test items are dequeued by priority."""
        queue = IngestionQueue()
        
        queue.enqueue("test", {"priority": "low"}, priority=QueuePriority.LOW)
        queue.enqueue("test", {"priority": "critical"}, priority=QueuePriority.CRITICAL)
        queue.enqueue("test", {"priority": "normal"}, priority=QueuePriority.NORMAL)
        
        # Should get critical first
        item = queue.dequeue()
        assert item.data["priority"] == "critical"
        
        # Then normal
        item = queue.dequeue()
        assert item.data["priority"] == "normal"
        
        # Then low
        item = queue.dequeue()
        assert item.data["priority"] == "low"

    def test_queue_full_drop_oldest(self):
        """Test dropping oldest when queue is full."""
        settings = QueueSettings(max_size=3, drop_on_full=True, drop_oldest=True)
        queue = IngestionQueue(settings)
        
        # Fill queue
        queue.enqueue("test", {"value": 1})
        queue.enqueue("test", {"value": 2})
        queue.enqueue("test", {"value": 3})
        
        # This should drop oldest
        item_id = queue.enqueue("test", {"value": 4})
        assert item_id is not None
        
        # Verify oldest was dropped
        stats = queue.get_stats()
        assert stats.total_dropped == 1

    def test_dequeue_timeout(self):
        """Test dequeue with timeout."""
        queue = IngestionQueue()
        
        # Should return None immediately for empty queue
        start = time.time()
        item = queue.dequeue(timeout=0.1)
        elapsed = time.time() - start
        
        assert item is None
        assert elapsed >= 0.09  # Allow some tolerance

    def test_peek(self):
        """Test peeking at queue."""
        queue = IngestionQueue()
        
        queue.enqueue("test", {"value": 1})
        
        # Peek should not remove
        item = queue.peek()
        assert item is not None
        assert len(queue) == 1
        
        # Dequeue should get same item
        item2 = queue.dequeue()
        assert item2.id == item.id

    def test_process_batch(self):
        """Test batch processing."""
        queue = IngestionQueue()
        
        for i in range(10):
            queue.enqueue("test", {"value": i})
        
        processed_values = []
        
        def processor(item: QueueItem) -> bool:
            processed_values.append(item.data["value"])
            return True
        
        count = queue.process_batch(processor, batch_size=5)
        
        assert count == 5
        assert len(processed_values) == 5
        assert len(queue) == 5

    def test_process_batch_with_failures(self):
        """Test batch processing with some failures."""
        queue = IngestionQueue()
        
        for i in range(5):
            queue.enqueue("test", {"value": i})
        
        def processor(item: QueueItem) -> bool:
            # Fail on value 2
            return item.data["value"] != 2
        
        count = queue.process_batch(processor, batch_size=5)
        
        assert count == 4  # 4 succeeded
        
        # Failed item should be re-queued or in dead letter
        stats = queue.get_stats()
        assert stats.total_processed == 4

    def test_dead_letter_queue(self):
        """Test dead letter queue for failed items."""
        settings = QueueSettings(max_size=100)
        queue = IngestionQueue(settings)
        
        # Add item that will fail max retries
        queue.enqueue("test", {"will_fail": True})
        
        fail_count = 0
        
        def processor(item: QueueItem) -> bool:
            nonlocal fail_count
            if item.data.get("will_fail"):
                fail_count += 1
                return False
            return True
        
        # Process multiple times to exhaust retries
        for _ in range(5):
            queue.process_batch(processor, batch_size=10)
        
        # Check dead letter queue
        dead_items = queue.get_dead_letter_items()
        assert len(dead_items) >= 1

    def test_retry_dead_letter(self):
        """Test retrying a dead letter item."""
        queue = IngestionQueue()
        
        # Manually add to dead letter
        item = QueueItem(id="test", source="test", data={})
        item.retry_count = 5
        queue._dead_letter_queue.append(item)
        
        # Retry it
        success = queue.retry_dead_letter("test")
        assert success
        assert len(queue.get_dead_letter_items()) == 0
        assert len(queue) == 1

    def test_statistics(self):
        """Test statistics tracking."""
        queue = IngestionQueue()
        
        # Enqueue some items
        for i in range(10):
            queue.enqueue("test", {"value": i})
        
        stats = queue.get_stats()
        assert stats.total_enqueued == 10
        assert stats.current_size == 10
        
        # Process some
        queue.process_batch(lambda x: True, batch_size=5)
        
        stats = queue.get_stats()
        assert stats.total_processed == 5
        assert stats.current_size == 5

    def test_clear_queue(self):
        """Test clearing the queue."""
        queue = IngestionQueue()
        
        for i in range(10):
            queue.enqueue("test", {"value": i})
        
        count = queue.clear()
        
        assert count == 10
        assert len(queue) == 0

    def test_background_processing(self):
        """Test background processing thread."""
        queue = IngestionQueue()
        processed = []
        
        def processor(item: QueueItem) -> bool:
            processed.append(item.data["value"])
            return True
        
        queue.start_processing(processor, interval=0.1)
        
        # Add some items
        for i in range(5):
            queue.enqueue("test", {"value": i})
        
        # Wait for processing
        time.sleep(0.5)
        
        queue.stop_processing()
        
        assert len(processed) == 5


class TestQueueBatchOperations:
    """Tests for batch operations."""

    def test_enqueue_batch(self):
        """Test batch enqueue."""
        queue = IngestionQueue()
        
        items = [("source", {"value": i}) for i in range(10)]
        ids = enqueue_batch(queue, items)
        
        assert len(ids) == 10
        assert all(id is not None for id in ids)
        assert len(queue) == 10

    def test_drain_queue(self):
        """Test draining entire queue."""
        queue = IngestionQueue()
        
        for i in range(20):
            queue.enqueue("test", {"value": i})
        
        processed = []
        
        def processor(item: QueueItem) -> bool:
            processed.append(item.data["value"])
            return True
        
        count = drain_queue(queue, processor, max_items=100, timeout_sec=5.0)
        
        assert count == 20
        assert len(processed) == 20
        assert len(queue) == 0


class TestQueuePersistence:
    """Tests for queue persistence (when enabled)."""

    def test_persistence_disabled_by_default(self):
        """Test persistence is disabled by default."""
        settings = QueueSettings()
        assert not settings.persist_to_disk

    def test_persistence_enabled(self, tmp_path):
        """Test persistence when enabled."""
        settings = QueueSettings(
            persist_to_disk=True,
            persist_path=str(tmp_path / "queue"),
        )
        queue = IngestionQueue(settings)
        
        # Enqueue item
        queue.enqueue("test", {"value": 1})
        
        # Check file was created
        persist_path = Path(settings.persist_path)
        assert persist_path.exists()
        assert len(list(persist_path.glob("*.json"))) == 1

    def test_persistence_load_on_startup(self, tmp_path):
        """Test items are loaded from disk on startup."""
        settings = QueueSettings(
            persist_to_disk=True,
            persist_path=str(tmp_path / "queue"),
        )
        
        # Create queue and add items
        queue1 = IngestionQueue(settings)
        queue1.enqueue("test", {"value": 1})
        queue1.enqueue("test", {"value": 2})
        
        # Create new queue instance (simulating restart)
        queue2 = IngestionQueue(settings)
        
        # Should load persisted items
        assert len(queue2) == 2


class TestQueueThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_enqueue(self):
        """Test concurrent enqueue from multiple threads."""
        queue = IngestionQueue(QueueSettings(max_size=10000))
        
        def enqueue_items(thread_id: int):
            for i in range(100):
                queue.enqueue(f"thread_{thread_id}", {"value": i})
        
        threads = [
            threading.Thread(target=enqueue_items, args=(i,))
            for i in range(10)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(queue) == 1000

    def test_concurrent_process(self):
        """Test concurrent processing."""
        queue = IngestionQueue()
        
        for i in range(100):
            queue.enqueue("test", {"value": i})
        
        processed = []
        lock = threading.Lock()
        
        def processor(item: QueueItem) -> bool:
            with lock:
                processed.append(item.data["value"])
            return True
        
        def process_items():
            while len(queue) > 0:
                queue.process_batch(processor, batch_size=10)
        
        threads = [threading.Thread(target=process_items) for _ in range(4)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(processed) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


