"""
YourDyno Live Capture Queue Manager.

Phase 2b equivalent of JetDrive's queue manager:
- 50ms aggregation windows (20Hz)
- Bounded ingestion queue with graceful degradation
- Optional CSV persistence
- Stats and health reporting
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.services.ingestion.config import create_live_capture_queue_config
from api.services.ingestion.queue import IngestionQueue, QueueItem, QueuePriority
from api.services.ingestion.schemas import DynoDataPointSchema
from api.services.yourdyno.yourdyno_client import YourDynoSample

logger = logging.getLogger(__name__)

AGGREGATION_WINDOW_MS = 50
BATCH_FLUSH_INTERVAL_SEC = 1.0


@dataclass
class YourDynoLiveQueueStats:
    samples_received: int = 0
    samples_aggregated: int = 0
    samples_enqueued: int = 0
    samples_dropped: int = 0
    samples_written: int = 0
    aggregation_windows: int = 0
    queue_high_watermark: int = 0
    last_flush_time: float = 0.0
    persist_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "samples_received": self.samples_received,
            "samples_aggregated": self.samples_aggregated,
            "samples_enqueued": self.samples_enqueued,
            "samples_dropped": self.samples_dropped,
            "samples_written": self.samples_written,
            "aggregation_windows": self.aggregation_windows,
            "queue_high_watermark": self.queue_high_watermark,
            "last_flush_time": self.last_flush_time,
            "persist_enabled": self.persist_enabled,
        }


class YourDynoLiveQueueManager:
    def __init__(self, output_path: Path | None = None, persist_enabled: bool = False):
        self.output_path = output_path

        queue_settings = create_live_capture_queue_config()
        queue_settings.persist_to_disk = persist_enabled
        queue_settings.persist_path = "data/yourdyno_live_queue"
        self.queue = IngestionQueue(settings=queue_settings)

        self._sample_buffer: list[YourDynoSample] = []
        self._buffer_lock = threading.Lock()
        self._last_window_start_ms: int = 0

        self._csv_file = None
        self._csv_writer = None
        self._csv_lock = threading.Lock()
        self._last_csv_flush_time: float = 0.0

        self.stats = YourDynoLiveQueueStats(persist_enabled=persist_enabled)
        self._stats_lock = threading.Lock()

    def on_sample(self, sample: YourDynoSample) -> None:
        with self._stats_lock:
            self.stats.samples_received += 1

        with self._buffer_lock:
            if self._last_window_start_ms == 0:
                self._last_window_start_ms = sample.timestamp_ms

            if (
                sample.timestamp_ms - self._last_window_start_ms
                >= AGGREGATION_WINDOW_MS
            ):
                self._flush_aggregation_window()
                self._last_window_start_ms = sample.timestamp_ms
                self._sample_buffer.clear()

            self._sample_buffer.append(sample)

    def force_flush(self) -> None:
        with self._buffer_lock:
            if self._sample_buffer:
                self._flush_aggregation_window()
                self._sample_buffer.clear()

    def _flush_aggregation_window(self) -> None:
        if not self._sample_buffer:
            return

        point = self._aggregate_samples(self._sample_buffer)
        if point is None:
            return

        payload = point.to_dict()
        item_id = self.queue.enqueue(
            source="yourdyno_live",
            data=payload,
            priority=QueuePriority.HIGH,
            metadata={
                "window_start_ms": self._last_window_start_ms,
                "sample_count": len(self._sample_buffer),
            },
        )

        with self._stats_lock:
            self.stats.samples_aggregated += len(self._sample_buffer)
            self.stats.aggregation_windows += 1
            if item_id:
                self.stats.samples_enqueued += 1
                self.stats.queue_high_watermark = max(
                    self.stats.queue_high_watermark,
                    len(self.queue),
                )
            else:
                self.stats.samples_dropped += 1

    @staticmethod
    def _aggregate_samples(samples: list[YourDynoSample]) -> DynoDataPointSchema | None:
        if not samples:
            return None

        last = samples[-1]
        rpm = _mean([s.engine_rpm for s in samples])
        hp = _mean([s.horsepower for s in samples])
        tq = _mean([s.torque_ftlb for s in samples])

        return DynoDataPointSchema(
            timestamp_ms=last.timestamp_ms,
            rpm=rpm,
            horsepower=hp,
            torque=tq,
            afr=_mean_opt([s.afr for s in samples]),
            afr_front=_mean_opt([s.afr_front for s in samples]),
            afr_rear=_mean_opt([s.afr_rear for s in samples]),
            map_kpa=_mean_opt([s.map_kpa for s in samples]),
            tps=_mean_opt([s.tps for s in samples]),
            iat=_mean_opt([s.iat_f for s in samples]),
            ect=_mean_opt([s.ect_f for s in samples]),
            speed_mph=_mean_opt([s.speed_mph for s in samples]),
            force_lbs=_mean_opt([s.force_lbs for s in samples]),
            acceleration=_mean_opt([s.acceleration for s in samples]),
        )

    def start_processing(self, csv_path: Path | None = None) -> None:
        if csv_path:
            self._open_csv(csv_path)

        def processor(item: QueueItem) -> bool:
            try:
                if self._csv_writer:
                    self._write_csv_row(item.data)
                    with self._stats_lock:
                        self.stats.samples_written += 1
                return True
            except Exception as exc:
                logger.error(
                    "Error processing yourdyno queue item %s: %s", item.id, exc
                )
                return False

        self.queue.start_processing(processor, interval=BATCH_FLUSH_INTERVAL_SEC)
        with self._stats_lock:
            self.stats.last_flush_time = time.time()

    def stop_processing(self) -> None:
        self.force_flush()
        self.queue.stop_processing()

        timeout = 10.0
        start = time.time()
        while len(self.queue) > 0 and (time.time() - start) < timeout:
            time.sleep(0.1)

        self._close_csv()

    def get_stats(self) -> dict[str, Any]:
        with self._stats_lock:
            stats = self.stats.to_dict()
        stats["queue"] = self.queue.get_stats().to_dict()
        return stats

    def reset(self) -> None:
        with self._buffer_lock:
            self._sample_buffer.clear()
            self._last_window_start_ms = 0

        with self._stats_lock:
            self.stats = YourDynoLiveQueueStats(
                persist_enabled=self.queue.settings.persist_to_disk
            )

        self.queue.clear()

    def _open_csv(self, path: Path) -> None:
        import csv

        with self._csv_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._csv_file = open(path, "w", newline="", encoding="utf-8")
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
            ]
            self._csv_writer = csv.DictWriter(
                self._csv_file,
                fieldnames=columns,
                extrasaction="ignore",
            )
            self._csv_writer.writeheader()
            self._last_csv_flush_time = time.time()

    def _write_csv_row(self, data: dict[str, Any]) -> None:
        with self._csv_lock:
            if self._csv_writer is None:
                return
            self._csv_writer.writerow(data)
            now = time.time()
            if self._csv_file and (now - self._last_csv_flush_time) >= 1.0:
                self._csv_file.flush()
                self._last_csv_flush_time = now

    def _close_csv(self) -> None:
        with self._csv_lock:
            if self._csv_file is None:
                return
            try:
                self._csv_file.flush()
                self._csv_file.close()
            finally:
                self._csv_file = None
                self._csv_writer = None


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _mean_opt(values: list[float | None]) -> float | None:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return float(sum(valid) / len(valid))


_yourdyno_live_queue_manager: YourDynoLiveQueueManager | None = None
_manager_lock = threading.Lock()


def get_yourdyno_live_queue_manager() -> YourDynoLiveQueueManager:
    global _yourdyno_live_queue_manager
    with _manager_lock:
        if _yourdyno_live_queue_manager is None:
            _yourdyno_live_queue_manager = YourDynoLiveQueueManager()
        return _yourdyno_live_queue_manager


def reset_yourdyno_live_queue_manager() -> None:
    global _yourdyno_live_queue_manager
    with _manager_lock:
        if _yourdyno_live_queue_manager is not None:
            _yourdyno_live_queue_manager.stop_processing()
            _yourdyno_live_queue_manager = None
