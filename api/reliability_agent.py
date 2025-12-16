"""
DynoAI Reliability Agent

Monitors system health, implements retry logic, circuit breakers,
and automatic recovery mechanisms across all subsystems.
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, ParamSpec
from functools import wraps
import threading

logger = logging.getLogger(__name__)


# === Circuit Breaker Pattern ===


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout: float = 60.0  # Seconds before trying half-open
    window_size: int = 100  # Rolling window for failure rate


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.
    
    When a service fails repeatedly, the circuit "opens" and blocks
    requests for a timeout period. After timeout, it enters "half-open"
    state to test if service recovered.
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.recent_calls: deque = deque(maxlen=self.config.window_size)
        self._lock = threading.Lock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"[{self.name}] Circuit entering HALF_OPEN state")
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Service unavailable for {self.config.timeout}s"
                    )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open."""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time >= self.config.timeout

    def _on_success(self):
        """Record successful call."""
        with self._lock:
            self.recent_calls.append((time.time(), True))
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self._close_circuit()
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def _on_failure(self):
        """Record failed call."""
        with self._lock:
            self.recent_calls.append((time.time(), False))
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                self._open_circuit()
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    self._open_circuit()

    def _open_circuit(self):
        """Open circuit to block requests."""
        self.state = CircuitState.OPEN
        self.success_count = 0
        logger.warning(
            f"[{self.name}] Circuit breaker OPENED after {self.failure_count} failures"
        )

    def _close_circuit(self):
        """Close circuit to resume normal operation."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"[{self.name}] Circuit breaker CLOSED - service recovered")

    def get_health(self) -> Dict[str, Any]:
        """Get current health metrics."""
        with self._lock:
            recent_success_rate = 0.0
            if self.recent_calls:
                successes = sum(1 for _, success in self.recent_calls if success)
                recent_success_rate = successes / len(self.recent_calls)

            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_rate": recent_success_rate,
                "last_failure": self.last_failure_time,
            }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# === Retry Logic with Exponential Backoff ===


P = ParamSpec('P')
T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 0.1  # seconds
    max_delay: float = 10.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd
    retry_on: tuple = (Exception,)  # Which exceptions to retry


def with_retry(config: Optional[RetryConfig] = None):
    """Decorator to add retry logic with exponential backoff."""
    cfg = config or RetryConfig()

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import random
            
            last_exception = None
            delay = cfg.initial_delay

            for attempt in range(cfg.max_attempts):
                try:
                    return func(*args, **kwargs)
                except cfg.retry_on as e:
                    last_exception = e
                    
                    if attempt < cfg.max_attempts - 1:
                        # Add jitter to prevent thundering herd
                        actual_delay = delay
                        if cfg.jitter:
                            actual_delay *= (0.5 + random.random())
                        
                        logger.warning(
                            f"Attempt {attempt + 1}/{cfg.max_attempts} failed for "
                            f"{func.__name__}: {e}. Retrying in {actual_delay:.2f}s..."
                        )
                        time.sleep(actual_delay)
                        delay = min(delay * cfg.exponential_base, cfg.max_delay)
                    else:
                        logger.error(
                            f"All {cfg.max_attempts} attempts failed for {func.__name__}"
                        )

            raise last_exception

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import random
            
            last_exception = None
            delay = cfg.initial_delay

            for attempt in range(cfg.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except cfg.retry_on as e:
                    last_exception = e
                    
                    if attempt < cfg.max_attempts - 1:
                        actual_delay = delay
                        if cfg.jitter:
                            actual_delay *= (0.5 + random.random())
                        
                        logger.warning(
                            f"Attempt {attempt + 1}/{cfg.max_attempts} failed for "
                            f"{func.__name__}: {e}. Retrying in {actual_delay:.2f}s..."
                        )
                        await asyncio.sleep(actual_delay)
                        delay = min(delay * cfg.exponential_base, cfg.max_delay)
                    else:
                        logger.error(
                            f"All {cfg.max_attempts} attempts failed for {func.__name__}"
                        )

            raise last_exception

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


# === Health Monitoring ===


@dataclass
class HealthMetric:
    """Single health metric reading."""
    timestamp: float
    status: str  # "healthy", "degraded", "unhealthy"
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class HealthMonitor:
    """
    Monitors health of various subsystems.
    
    Tracks metrics, detects degradation, and triggers alerts.
    """

    def __init__(self, name: str, check_interval: float = 30.0):
        self.name = name
        self.check_interval = check_interval
        self.history: deque = deque(maxlen=100)
        self.current_status = "unknown"
        self.last_check: Optional[float] = None
        self.consecutive_failures = 0
        self._callbacks: List[Callable[[HealthMetric], None]] = []

    def add_callback(self, callback: Callable[[HealthMetric], None]):
        """Add callback to be notified of health changes."""
        self._callbacks.append(callback)

    def record_check(
        self,
        status: str,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record a health check result."""
        metric = HealthMetric(
            timestamp=time.time(),
            status=status,
            latency_ms=latency_ms,
            error=error,
            metadata=metadata or {},
        )
        
        self.history.append(metric)
        self.last_check = metric.timestamp
        
        # Track consecutive failures
        if status == "unhealthy":
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0

        # Update current status
        old_status = self.current_status
        self.current_status = status

        # Notify callbacks if status changed
        if old_status != status:
            for callback in self._callbacks:
                try:
                    callback(metric)
                except Exception as e:
                    logger.error(f"Health callback error: {e}")

    def get_health_summary(self) -> Dict[str, Any]:
        """Get current health summary."""
        if not self.history:
            return {
                "name": self.name,
                "status": "unknown",
                "message": "No health checks performed yet",
            }

        recent = list(self.history)[-10:]  # Last 10 checks
        healthy = sum(1 for m in recent if m.status == "healthy")
        success_rate = healthy / len(recent) if recent else 0

        avg_latency = None
        latencies = [m.latency_ms for m in recent if m.latency_ms is not None]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)

        return {
            "name": self.name,
            "status": self.current_status,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency,
            "consecutive_failures": self.consecutive_failures,
            "last_check": self.last_check,
            "time_since_last_check": time.time() - self.last_check if self.last_check else None,
        }


# === Reliability Agent ===


class ReliabilityAgent:
    """
    Central reliability coordinator.
    
    Manages circuit breakers, health monitors, and recovery actions.
    """

    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.health_monitors: Dict[str, HealthMonitor] = {}
        self.alerts: deque = deque(maxlen=100)
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

    def get_circuit_breaker(
        self, name: str, config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get or create circuit breaker for a service."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, config)
        return self.circuit_breakers[name]

    def get_health_monitor(
        self, name: str, check_interval: float = 30.0
    ) -> HealthMonitor:
        """Get or create health monitor for a subsystem."""
        if name not in self.health_monitors:
            monitor = HealthMonitor(name, check_interval)
            monitor.add_callback(self._on_health_change)
            self.health_monitors[name] = monitor
        return self.health_monitors[name]

    def _on_health_change(self, metric: HealthMetric):
        """Handle health status changes."""
        if metric.status == "unhealthy":
            self.add_alert(
                "health_degraded",
                f"Health check failed: {metric.error}",
                {"metric": metric},
            )

    def add_alert(self, alert_type: str, message: str, data: Optional[Dict] = None):
        """Add alert to history."""
        alert = {
            "type": alert_type,
            "message": message,
            "timestamp": time.time(),
            "data": data or {},
        }
        self.alerts.append(alert)
        logger.warning(f"[ReliabilityAgent] ALERT: {message}")

    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health summary."""
        circuit_health = {
            name: cb.get_health() for name, cb in self.circuit_breakers.items()
        }
        
        monitor_health = {
            name: mon.get_health_summary() for name, mon in self.health_monitors.items()
        }

        # Overall status
        unhealthy_circuits = sum(
            1 for cb in circuit_health.values() if cb["state"] == "open"
        )
        unhealthy_monitors = sum(
            1 for mon in monitor_health.values() if mon["status"] == "unhealthy"
        )

        overall_status = "healthy"
        if unhealthy_circuits > 0 or unhealthy_monitors > 0:
            overall_status = "degraded"
        if unhealthy_circuits > 2 or unhealthy_monitors > 3:
            overall_status = "unhealthy"

        recent_alerts = list(self.alerts)[-10:]

        return {
            "status": overall_status,
            "timestamp": time.time(),
            "circuit_breakers": circuit_health,
            "health_monitors": monitor_health,
            "recent_alerts": recent_alerts,
            "stats": {
                "total_circuits": len(self.circuit_breakers),
                "open_circuits": unhealthy_circuits,
                "unhealthy_monitors": unhealthy_monitors,
                "alerts_count": len(self.alerts),
            },
        }

    async def start_monitoring(self):
        """Start background health monitoring."""
        self._running = True
        logger.info("[ReliabilityAgent] Starting background monitoring")
        
        while self._running:
            try:
                # Check all monitors
                for monitor in self.health_monitors.values():
                    if monitor.last_check is None or (
                        time.time() - monitor.last_check > monitor.check_interval
                    ):
                        # Trigger health check (actual check logic depends on subsystem)
                        pass
                
                await asyncio.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"[ReliabilityAgent] Monitoring error: {e}")
                await asyncio.sleep(10)

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._running = False
        logger.info("[ReliabilityAgent] Stopping monitoring")


# === Global Instance ===


_agent: Optional[ReliabilityAgent] = None


def get_reliability_agent() -> ReliabilityAgent:
    """Get global reliability agent instance."""
    global _agent
    if _agent is None:
        _agent = ReliabilityAgent()
    return _agent

