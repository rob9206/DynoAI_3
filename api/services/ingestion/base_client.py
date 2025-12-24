"""
Base Ingestion Client

Provides a base class for all data source clients with:
- Retry logic with exponential backoff
- Circuit breaker pattern
- Connection state management
- Health monitoring
- Statistics tracking
- Queue integration
"""

from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

from .config import (
    CircuitBreakerSettings,
    DataSourceConfig,
    RetrySettings,
    get_ingestion_config,
)
from .queue import IngestionQueue, QueueItem, QueuePriority
from .schemas import DataSample, IngestionError, ValidationResult

logger = logging.getLogger(__name__)

T = TypeVar("T")


class IngestionState(Enum):
    """State of the ingestion client."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    CIRCUIT_OPEN = "circuit_open"


class CircuitState(Enum):
    """State of circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class IngestionStats:
    """Statistics for an ingestion client."""

    source_name: str
    state: IngestionState = IngestionState.DISCONNECTED

    # Connection stats
    connect_attempts: int = 0
    successful_connects: int = 0
    failed_connects: int = 0
    last_connect_time: float | None = None
    last_disconnect_time: float | None = None
    total_uptime_sec: float = 0.0

    # Data stats
    samples_received: int = 0
    samples_processed: int = 0
    samples_failed: int = 0
    samples_dropped: int = 0
    bytes_received: int = 0

    # Error stats
    total_errors: int = 0
    last_error: str | None = None
    last_error_time: float | None = None
    consecutive_errors: int = 0

    # Performance stats
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    samples_per_second: float = 0.0

    # Circuit breaker stats
    circuit_state: CircuitState = CircuitState.CLOSED
    circuit_failure_count: int = 0
    circuit_last_state_change: float | None = None

    # Health tracking
    health_checks_passed: int = 0
    health_checks_failed: int = 0
    last_health_check: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "state": self.state.value,
            "connect_attempts": self.connect_attempts,
            "successful_connects": self.successful_connects,
            "failed_connects": self.failed_connects,
            "last_connect_time": self.last_connect_time,
            "samples_received": self.samples_received,
            "samples_processed": self.samples_processed,
            "samples_failed": self.samples_failed,
            "total_errors": self.total_errors,
            "last_error": self.last_error,
            "consecutive_errors": self.consecutive_errors,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "samples_per_second": round(self.samples_per_second, 2),
            "circuit_state": self.circuit_state.value,
            "circuit_failure_count": self.circuit_failure_count,
        }


@dataclass
class CircuitBreaker:
    """Circuit breaker implementation for ingestion clients."""

    settings: CircuitBreakerSettings
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float | None = None
    last_state_change: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.settings.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.settings.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

    def should_allow_request(self) -> bool:
        """Check if request should be allowed."""
        with self._lock:
            if not self.settings.enabled:
                return True

            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                # Check if timeout has elapsed
                if self.last_failure_time is None:
                    return True
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.settings.timeout_sec:
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                return True

            return False

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state."""
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.time()

        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
            logger.info(f"Circuit breaker: {old_state.value} -> {new_state.value}")
        elif new_state == CircuitState.OPEN:
            self.success_count = 0
            logger.warning(
                f"Circuit breaker OPENED after {self.failure_count} failures"
            )
        elif new_state == CircuitState.HALF_OPEN:
            self.success_count = 0
            logger.info("Circuit breaker entering HALF_OPEN state")

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None


class BaseIngestionClient(ABC, Generic[T]):
    """
    Abstract base class for data ingestion clients.

    Provides common functionality:
    - Connection management with retry
    - Circuit breaker pattern
    - Data validation
    - Queue integration
    - Statistics tracking
    - Health monitoring

    Subclasses must implement:
    - _connect_impl: Actual connection logic
    - _disconnect_impl: Actual disconnection logic
    - _read_impl: Read data from source
    - _validate_sample: Validate received sample
    """

    def __init__(
        self,
        source_name: str,
        config: DataSourceConfig | None = None,
        queue: IngestionQueue | None = None,
    ):
        self.source_name = source_name
        self.config = config or get_ingestion_config().get_source_config(source_name)
        self.queue = queue

        # State
        self._state = IngestionState.DISCONNECTED
        self._state_lock = threading.Lock()

        # Circuit breaker
        self._circuit = CircuitBreaker(settings=self.config.circuit_breaker)

        # Statistics
        self._stats = IngestionStats(source_name=source_name)
        self._latency_samples: deque[float] = deque(maxlen=100)
        self._sample_times: deque[float] = deque(maxlen=100)

        # Callbacks
        self._on_sample_callbacks: list[Callable[[T], None]] = []
        self._on_error_callbacks: list[Callable[[Exception], None]] = []
        self._on_state_change_callbacks: list[
            Callable[[IngestionState, IngestionState], None]
        ] = []

        # Background processing
        self._running = False
        self._read_thread: threading.Thread | None = None

    @property
    def state(self) -> IngestionState:
        """Get current state."""
        with self._state_lock:
            return self._state

    @state.setter
    def state(self, new_state: IngestionState) -> None:
        """Set state and notify callbacks."""
        with self._state_lock:
            old_state = self._state
            self._state = new_state
            self._stats.state = new_state

        if old_state != new_state:
            logger.info(
                f"[{self.source_name}] State: {old_state.value} -> {new_state.value}"
            )
            for callback in self._on_state_change_callbacks:
                try:
                    callback(old_state, new_state)
                except Exception as e:
                    logger.error(f"State change callback error: {e}")

    def add_sample_callback(self, callback: Callable[[T], None]) -> None:
        """Add callback for received samples."""
        self._on_sample_callbacks.append(callback)

    def add_error_callback(self, callback: Callable[[Exception], None]) -> None:
        """Add callback for errors."""
        self._on_error_callbacks.append(callback)

    def add_state_change_callback(
        self, callback: Callable[[IngestionState, IngestionState], None]
    ) -> None:
        """Add callback for state changes."""
        self._on_state_change_callbacks.append(callback)

    def connect(self) -> bool:
        """
        Connect to data source with retry logic.

        Returns:
            True if connected successfully
        """
        if self.state == IngestionState.CONNECTED:
            return True

        if not self._circuit.should_allow_request():
            self.state = IngestionState.CIRCUIT_OPEN
            raise IngestionError(
                f"Circuit breaker is open for {self.source_name}",
                error_type="circuit_open",
                source=self.source_name,
                recoverable=True,
            )

        self.state = IngestionState.CONNECTING
        self._stats.connect_attempts += 1

        retry_settings = self.config.retry
        delay = retry_settings.initial_delay_sec
        last_error = None

        for attempt in range(retry_settings.max_attempts):
            try:
                success = self._connect_impl()
                if success:
                    self.state = IngestionState.CONNECTED
                    self._stats.successful_connects += 1
                    self._stats.last_connect_time = time.time()
                    self._stats.consecutive_errors = 0
                    self._circuit.record_success()
                    logger.info(f"[{self.source_name}] Connected successfully")
                    return True
                else:
                    raise IngestionError(
                        "Connection returned False",
                        error_type="connection_failed",
                        source=self.source_name,
                    )
            except Exception as e:
                last_error = e
                self._record_error(e)

                if attempt < retry_settings.max_attempts - 1:
                    # Calculate delay with jitter
                    actual_delay = delay
                    if retry_settings.jitter:
                        actual_delay *= 0.5 + random.random()

                    logger.warning(
                        f"[{self.source_name}] Connect attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {actual_delay:.2f}s..."
                    )
                    time.sleep(actual_delay)
                    delay = min(
                        delay * retry_settings.exponential_base,
                        retry_settings.max_delay_sec,
                    )

        # All attempts failed
        self.state = IngestionState.ERROR
        self._stats.failed_connects += 1
        self._circuit.record_failure()

        raise IngestionError(
            f"Failed to connect after {retry_settings.max_attempts} attempts",
            error_type="connection_exhausted",
            source=self.source_name,
            recoverable=True,
            context={"last_error": str(last_error)},
        )

    async def connect_async(self) -> bool:
        """Async version of connect."""
        if self.state == IngestionState.CONNECTED:
            return True

        if not self._circuit.should_allow_request():
            self.state = IngestionState.CIRCUIT_OPEN
            raise IngestionError(
                f"Circuit breaker is open for {self.source_name}",
                error_type="circuit_open",
                source=self.source_name,
                recoverable=True,
            )

        self.state = IngestionState.CONNECTING
        self._stats.connect_attempts += 1

        retry_settings = self.config.retry
        delay = retry_settings.initial_delay_sec
        last_error = None

        for attempt in range(retry_settings.max_attempts):
            try:
                if asyncio.iscoroutinefunction(self._connect_impl):
                    success = await self._connect_impl()
                else:
                    success = self._connect_impl()

                if success:
                    self.state = IngestionState.CONNECTED
                    self._stats.successful_connects += 1
                    self._stats.last_connect_time = time.time()
                    self._stats.consecutive_errors = 0
                    self._circuit.record_success()
                    return True
            except Exception as e:
                last_error = e
                self._record_error(e)

                if attempt < retry_settings.max_attempts - 1:
                    actual_delay = delay
                    if retry_settings.jitter:
                        actual_delay *= 0.5 + random.random()
                    await asyncio.sleep(actual_delay)
                    delay = min(
                        delay * retry_settings.exponential_base,
                        retry_settings.max_delay_sec,
                    )

        self.state = IngestionState.ERROR
        self._circuit.record_failure()
        raise IngestionError(
            f"Failed to connect after {retry_settings.max_attempts} attempts",
            error_type="connection_exhausted",
            source=self.source_name,
            context={"last_error": str(last_error)},
        )

    def disconnect(self) -> None:
        """Disconnect from data source."""
        self._running = False

        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=5.0)

        try:
            self._disconnect_impl()
        except Exception as e:
            logger.error(f"[{self.source_name}] Disconnect error: {e}")

        self._stats.last_disconnect_time = time.time()
        if self._stats.last_connect_time:
            self._stats.total_uptime_sec += (
                self._stats.last_disconnect_time - self._stats.last_connect_time
            )

        self.state = IngestionState.DISCONNECTED
        logger.info(f"[{self.source_name}] Disconnected")

    def reconnect(self) -> bool:
        """Attempt to reconnect to data source."""
        self.state = IngestionState.RECONNECTING
        self.disconnect()
        time.sleep(0.5)  # Brief pause before reconnect
        return self.connect()

    def start_reading(self) -> None:
        """Start background reading thread."""
        if self._running:
            logger.warning(f"[{self.source_name}] Already reading")
            return

        if self.state != IngestionState.CONNECTED:
            self.connect()

        self._running = True
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()
        logger.info(f"[{self.source_name}] Started reading")

    def stop_reading(self) -> None:
        """Stop background reading."""
        self._running = False
        if self._read_thread:
            self._read_thread.join(timeout=5.0)
        logger.info(f"[{self.source_name}] Stopped reading")

    def _read_loop(self) -> None:
        """Background reading loop with error handling."""
        consecutive_empty = 0

        while self._running:
            try:
                # Check circuit breaker
                if not self._circuit.should_allow_request():
                    self.state = IngestionState.CIRCUIT_OPEN
                    time.sleep(1.0)
                    continue

                # Read data
                start_time = time.time()
                sample = self._read_impl()
                latency = (time.time() - start_time) * 1000

                if sample is not None:
                    consecutive_empty = 0
                    self._process_sample(sample, latency)
                    self._circuit.record_success()
                else:
                    consecutive_empty += 1
                    if consecutive_empty > 100:
                        logger.debug(f"[{self.source_name}] No data for 100 reads")
                        consecutive_empty = 0

            except Exception as e:
                self._record_error(e)
                self._circuit.record_failure()

                # Check if we should reconnect
                if self._stats.consecutive_errors >= 5:
                    logger.warning(
                        f"[{self.source_name}] Too many errors, attempting reconnect..."
                    )
                    try:
                        self.reconnect()
                    except Exception as re:
                        logger.error(f"[{self.source_name}] Reconnect failed: {re}")
                        time.sleep(5.0)

    def _process_sample(self, sample: T, latency_ms: float) -> None:
        """Process a received sample."""
        self._stats.samples_received += 1
        self._latency_samples.append(latency_ms)
        self._sample_times.append(time.time())

        # Update stats
        if self._latency_samples:
            self._stats.avg_latency_ms = sum(self._latency_samples) / len(
                self._latency_samples
            )
            self._stats.max_latency_ms = max(
                self._stats.max_latency_ms, max(self._latency_samples)
            )

        # Calculate sample rate
        if len(self._sample_times) >= 2:
            time_span = self._sample_times[-1] - self._sample_times[0]
            if time_span > 0:
                self._stats.samples_per_second = len(self._sample_times) / time_span

        # Validate sample
        validation_result = self._validate_sample(sample)
        if not validation_result.is_valid:
            self._stats.samples_failed += 1
            if self.config.validation.strict_mode:
                logger.warning(
                    f"[{self.source_name}] Sample validation failed: "
                    f"{[e.message for e in validation_result.errors]}"
                )
                return

        self._stats.samples_processed += 1

        # Enqueue if queue is configured
        if self.queue is not None:
            sample_dict = self._sample_to_dict(sample)
            item_id = self.queue.enqueue(
                source=self.source_name,
                data=sample_dict,
                priority=QueuePriority.HIGH,
            )
            if item_id is None:
                self._stats.samples_dropped += 1

        # Notify callbacks
        for callback in self._on_sample_callbacks:
            try:
                callback(sample)
            except Exception as e:
                logger.error(f"[{self.source_name}] Sample callback error: {e}")

    def _record_error(self, error: Exception) -> None:
        """Record an error."""
        self._stats.total_errors += 1
        self._stats.consecutive_errors += 1
        self._stats.last_error = str(error)
        self._stats.last_error_time = time.time()

        for callback in self._on_error_callbacks:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error callback failed: {e}")

    def health_check(self) -> dict[str, Any]:
        """Perform health check and return status."""
        self._stats.last_health_check = time.time()

        is_healthy = (
            self.state == IngestionState.CONNECTED
            and self._circuit.state != CircuitState.OPEN
            and self._stats.consecutive_errors < 3
        )

        if is_healthy:
            self._stats.health_checks_passed += 1
        else:
            self._stats.health_checks_failed += 1

        return {
            "source": self.source_name,
            "healthy": is_healthy,
            "state": self.state.value,
            "circuit_state": self._circuit.state.value,
            "consecutive_errors": self._stats.consecutive_errors,
            "samples_per_second": round(self._stats.samples_per_second, 2),
            "last_error": self._stats.last_error,
            "timestamp": time.time(),
        }

    def get_stats(self) -> IngestionStats:
        """Get current statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = IngestionStats(source_name=self.source_name)
        self._stats.state = self.state
        self._latency_samples.clear()
        self._sample_times.clear()

    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker."""
        self._circuit.reset()
        if self.state == IngestionState.CIRCUIT_OPEN:
            self.state = IngestionState.DISCONNECTED

    # Abstract methods to be implemented by subclasses

    @abstractmethod
    def _connect_impl(self) -> bool:
        """Implement actual connection logic."""
        pass

    @abstractmethod
    def _disconnect_impl(self) -> None:
        """Implement actual disconnection logic."""
        pass

    @abstractmethod
    def _read_impl(self) -> T | None:
        """Implement actual data reading logic."""
        pass

    @abstractmethod
    def _validate_sample(self, sample: T) -> ValidationResult:
        """Validate a received sample."""
        pass

    def _sample_to_dict(self, sample: T) -> dict[str, Any]:
        """Convert sample to dictionary for queue storage."""
        if hasattr(sample, "to_dict"):
            return sample.to_dict()
        elif hasattr(sample, "__dict__"):
            return dict(sample.__dict__)
        else:
            return {"value": sample}

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False


# =============================================================================
# Utility Functions
# =============================================================================


def create_client_with_queue(
    client_class: type[BaseIngestionClient],
    source_name: str,
    processor: Callable[[QueueItem], bool],
    **kwargs,
) -> BaseIngestionClient:
    """
    Create a client with an integrated processing queue.

    The queue will automatically process items in the background.
    """
    config = get_ingestion_config()
    queue = IngestionQueue(settings=config.queue)
    queue.start_processing(processor)

    client = client_class(source_name=source_name, queue=queue, **kwargs)
    return client


async def health_check_all(clients: list[BaseIngestionClient]) -> dict[str, Any]:
    """
    Run health checks on all clients.

    Returns aggregate health status.
    """
    results = {}
    healthy_count = 0

    for client in clients:
        check = client.health_check()
        results[client.source_name] = check
        if check["healthy"]:
            healthy_count += 1

    return {
        "overall_healthy": healthy_count == len(clients),
        "healthy_count": healthy_count,
        "total_count": len(clients),
        "clients": results,
        "timestamp": time.time(),
    }
