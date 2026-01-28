"""
JetDrive Live Capture Queue Manager

Manages the ingestion queue for live JetDrive capture with:
- 50ms sample aggregation for stable UI updates (20Hz)
- Bounded queue with graceful degradation on overload
- Optional persistence for crash recovery
- CSV writing via batch processing
- Health metrics tracking
- Real-time analysis integration (Phase 4)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from api.services.ingestion.adapters import JetDriveAdapter
from api.services.ingestion.config import create_live_capture_queue_config
from api.services.ingestion.queue import IngestionQueue, QueueItem, QueuePriority
from api.services.jetdrive_client import JetDriveSample

if TYPE_CHECKING:
    from api.services.jetdrive_realtime_analysis import RealtimeAnalysisEngine

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGGREGATION_WINDOW_MS = 50  # 50ms window = 20Hz UI update rate
BATCH_FLUSH_INTERVAL_SEC = 1.0  # Write CSV data every second

# =============================================================================
# Stats
# =============================================================================


@dataclass
class LiveCaptureQueueStats:
    """Statistics for live capture queue."""

    samples_received: int = 0
    samples_aggregated: int = 0
    samples_enqueued: int = 0
    samples_dropped: int = 0
    samples_written: int = 0

    aggregation_windows: int = 0
    queue_high_watermark: int = 0
    last_flush_time: float = 0.0

    persist_enabled: bool = False
    persist_lag_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "samples_received":
            self.samples_received,
            "samples_aggregated":
            self.samples_aggregated,
            "samples_enqueued":
            self.samples_enqueued,
            "samples_dropped":
            self.samples_dropped,
            "samples_written":
            self.samples_written,
            "aggregation_windows":
            self.aggregation_windows,
            "queue_high_watermark":
            self.queue_high_watermark,
            "last_flush_time":
            self.last_flush_time,
            "persist_enabled":
            self.persist_enabled,
            "persist_lag_ms":
            round(self.persist_lag_ms, 2),
            "enqueue_rate_hz": (round(
                self.samples_enqueued /
                max(time.time() - self.last_flush_time, 1.0),
                2,
            ) if self.last_flush_time > 0 else 0),
        }


# =============================================================================
# Live Capture Queue Manager
# =============================================================================


class LiveCaptureQueueManager:
    """
    Manages ingestion queue for JetDrive live capture.

    Aggregates raw samples into 50ms windows before enqueueing,
    maintains bounded queue with graceful degradation, and handles
    batch writing to CSV.
    """

    def __init__(
        self,
        output_path: Path | None = None,
        persist_enabled: bool = False,
    ):
        """
        Initialize live capture queue manager.

        Args:
            output_path: Path to write CSV data (if None, no writing)
            persist_enabled: Enable disk persistence for crash recovery
        """
        self.output_path = output_path

        # Create queue
        queue_settings = create_live_capture_queue_config()
        queue_settings.persist_to_disk = persist_enabled
        self.queue = IngestionQueue(settings=queue_settings)

        # Create adapter for sample aggregation
        self.adapter = JetDriveAdapter()

        # Sample aggregation buffer (grouped by window)
        self._sample_buffer: list[JetDriveSample] = []
        self._buffer_lock = threading.Lock()
        self._last_window_start_ms: int = 0

        # CSV writer
        self._csv_file = None
        self._csv_writer = None
        self._csv_lock = threading.Lock()

        # Stats
        self.stats = LiveCaptureQueueStats()
        self.stats.persist_enabled = persist_enabled
        self._stats_lock = threading.Lock()

        # Background processor thread
        self._processing = False
        self._process_thread: threading.Thread | None = None

        # Real-time analysis engine (Phase 4)
        self._realtime_engine: RealtimeAnalysisEngine | None = None

    def on_sample(self, sample: JetDriveSample) -> None:
        """
        Receive a raw sample from JetDrive.

        Buffers samples for aggregation into 50ms windows.
        """
        with self._stats_lock:
            self.stats.samples_received += 1

        with self._buffer_lock:
            # Initialize window start if first sample
            if self._last_window_start_ms == 0:
                self._last_window_start_ms = sample.timestamp_ms

            # Check if we need to flush the current window
            if (sample.timestamp_ms - self._last_window_start_ms
                    >= AGGREGATION_WINDOW_MS):
                # Flush current window
                self._flush_aggregation_window()

                # Start new window
                self._last_window_start_ms = sample.timestamp_ms
                self._sample_buffer.clear()

            # Add to current window
            self._sample_buffer.append(sample)

    def _flush_aggregation_window(self) -> None:
        """
        Flush the current aggregation window to the queue.

        Called from within buffer lock.
        """
        if not self._sample_buffer:
            return

        try:
            # Aggregate samples using adapter
            # adapter.aggregate_samples() takes list and returns list of DynoDataPointSchema
            aggregated = self.adapter.aggregate_samples(
                self._sample_buffer, time_window_ms=AGGREGATION_WINDOW_MS)

            if not aggregated:
                return

            with self._stats_lock:
                self.stats.samples_aggregated += len(self._sample_buffer)
                self.stats.aggregation_windows += 1

            # Enqueue aggregated data point(s)
            for point in aggregated:
                point_dict = point.to_dict()

                # Feed to real-time analysis engine (Phase 4)
                if self._realtime_engine is not None:
                    try:
                        self._realtime_engine.on_aggregated_sample(point_dict)
                    except Exception as e:
                        # Don't let analysis errors block capture
                        logger.warning(
                            f"Realtime analysis error (non-blocking): {e}")

                item_id = self.queue.enqueue(
                    source="jetdrive_live",
                    data=point_dict,
                    priority=QueuePriority.
                    HIGH,  # Real-time data is high priority
                    metadata={
                        "window_start_ms": self._last_window_start_ms,
                        "sample_count": len(self._sample_buffer),
                    },
                )

                if item_id:
                    with self._stats_lock:
                        self.stats.samples_enqueued += 1
                        queue_size = len(self.queue)
                        self.stats.queue_high_watermark = max(
                            self.stats.queue_high_watermark, queue_size)
                else:
                    with self._stats_lock:
                        self.stats.samples_dropped += 1
                    logger.warning("Queue full, dropped aggregated sample")

        except Exception as e:
            logger.error(f"Error flushing aggregation window: {e}")

    def force_flush(self) -> None:
        """Force flush the current aggregation window."""
        with self._buffer_lock:
            if self._sample_buffer:
                self._flush_aggregation_window()
                self._sample_buffer.clear()

    def start_processing(self, csv_path: Path | None = None) -> None:
        """
        Start background queue processing.

        Args:
            csv_path: Optional path to write CSV data
        """
        if self._processing:
            logger.warning("Processing already started")
            return

        self._processing = True

        # Open CSV file if path provided
        if csv_path:
            self._open_csv(csv_path)

        # Define processor function
        def processor(item: QueueItem) -> bool:
            """Process a queue item (write to CSV)."""
            try:
                if self._csv_writer:
                    # Write data point to CSV
                    data = item.data
                    self._write_csv_row(data)

                    with self._stats_lock:
                        self.stats.samples_written += 1

                return True
            except Exception as e:
                logger.error(f"Error processing item {item.id}: {e}")
                return False

        # Start queue processing
        self.queue.start_processing(processor,
                                    interval=BATCH_FLUSH_INTERVAL_SEC)

        with self._stats_lock:
            self.stats.last_flush_time = time.time()

        logger.info("Live capture queue processing started")

    def stop_processing(self) -> None:
        """Stop background processing and close CSV file."""
        # Force flush any remaining samples
        self.force_flush()

        # Stop queue processing
        self.queue.stop_processing()

        # Wait for queue to drain (with timeout)
        timeout = 10.0
        start = time.time()
        while len(self.queue) > 0 and time.time() - start < timeout:
            time.sleep(0.1)

        self._processing = False

        # Close CSV
        self._close_csv()

        logger.info("Live capture queue processing stopped")

    def _open_csv(self, path: Path) -> None:
        """Open CSV file for writing."""
        import csv

        with self._csv_lock:
            try:
                # Ensure parent directory exists
                path.parent.mkdir(parents=True, exist_ok=True)

                self._csv_file = open(path, "w", newline="", encoding="utf-8")

                # Define columns (based on DynoDataPointSchema)
                columns = [
                    "timestamp_ms",
                    "rpm",
                    "horsepower",
                    "torque",
                    "afr",
                    "afr_front",
                    "afr_rear",
                    "map_kpa",
                    "tps",
                    "iat",
                    "ect",
                    "force_lbs",
                    "acceleration",
                    "speed_mph",
                    "gear",
                ]

                self._csv_writer = csv.DictWriter(
                    self._csv_file,
                    fieldnames=columns,
                    extrasaction="ignore",  # Ignore extra fields
                )
                self._csv_writer.writeheader()

                logger.info(f"Opened CSV file: {path}")
            except Exception as e:
                logger.error(f"Failed to open CSV file {path}: {e}")
                self._csv_file = None
                self._csv_writer = None

    def _write_csv_row(self, data: dict[str, Any]) -> None:
        """Write a single row to CSV."""
        with self._csv_lock:
            if self._csv_writer:
                try:
                    self._csv_writer.writerow(data)
                    # Flush periodically (every second via batch processor)
                    if self.stats.samples_written % 20 == 0:
                        self._csv_file.flush()
                except Exception as e:
                    logger.error(f"Failed to write CSV row: {e}")

    def _close_csv(self) -> None:
        """Close CSV file."""
        with self._csv_lock:
            if self._csv_file:
                try:
                    self._csv_file.flush()
                    self._csv_file.close()
                    logger.info("Closed CSV file")
                except Exception as e:
                    logger.error(f"Error closing CSV file: {e}")
                finally:
                    self._csv_file = None
                    self._csv_writer = None

    def get_stats(self) -> dict[str, Any]:
        """Get current statistics."""
        with self._stats_lock:
            stats = self.stats.to_dict()

        # Add queue stats
        queue_stats = self.queue.get_stats()
        stats["queue"] = queue_stats.to_dict()

        return stats

    def reset(self) -> None:
        """Reset all state (for testing or restart)."""
        with self._buffer_lock:
            self._sample_buffer.clear()
            self._last_window_start_ms = 0

        with self._stats_lock:
            self.stats = LiveCaptureQueueStats()
            self.stats.persist_enabled = self.queue.settings.persist_to_disk

        self.queue.clear()
        self.adapter.reset()

        # Reset realtime analysis if enabled
        if self._realtime_engine is not None:
            self._realtime_engine.reset()

    # =========================================================================
    # Real-time Analysis Integration (Phase 4)
    # =========================================================================

    def enable_realtime_analysis(self, target_afr: float = 14.7) -> None:
        """
        Enable real-time analysis during capture.

        Args:
            target_afr: Target AFR for VE delta calculation (default stoich)
        """
        from api.services.jetdrive_realtime_analysis import RealtimeAnalysisEngine

        if self._realtime_engine is None:
            self._realtime_engine = RealtimeAnalysisEngine(
                target_afr=target_afr)
            logger.info(
                f"Realtime analysis enabled (target AFR: {target_afr})")
        else:
            # Update target AFR if already enabled
            self._realtime_engine.target_afr = target_afr
            self._realtime_engine.reset()
            logger.info(f"Realtime analysis reset (target AFR: {target_afr})")

    def disable_realtime_analysis(self) -> None:
        """Disable real-time analysis."""
        self._realtime_engine = None
        logger.info("Realtime analysis disabled")

    def get_realtime_analysis(self) -> dict[str, Any] | None:
        """
        Get current real-time analysis state.

        Returns:
            Analysis state dict, or None if analysis is disabled
        """
        if self._realtime_engine is None:
            return None
        return self._realtime_engine.get_state()

    @property
    def realtime_analysis_enabled(self) -> bool:
        """Check if real-time analysis is enabled."""
        return self._realtime_engine is not None


# =============================================================================
# Global Manager Instance
# =============================================================================

_live_queue_manager: LiveCaptureQueueManager | None = None
_manager_lock = threading.Lock()


def get_live_queue_manager() -> LiveCaptureQueueManager:
    """Get or create the global live capture queue manager."""
    global _live_queue_manager
    with _manager_lock:
        if _live_queue_manager is None:
            _live_queue_manager = LiveCaptureQueueManager()
        return _live_queue_manager


def reset_live_queue_manager() -> None:
    """Reset the global manager (for testing or restart)."""
    global _live_queue_manager
    with _manager_lock:
        if _live_queue_manager is not None:
            _live_queue_manager.stop_processing()
            _live_queue_manager = None
