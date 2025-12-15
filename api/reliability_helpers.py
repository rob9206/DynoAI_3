"""
Reliability helpers for DynoAI subsystems.

Provides pre-configured retry and circuit breaker wrappers
for common operations like JetDrive communication, API calls, etc.
"""

import asyncio
import logging
from typing import Any, Callable, Optional, TypeVar
from urllib.error import HTTPError, URLError
import socket

from api.reliability_agent import (
    CircuitBreakerConfig,
    RetryConfig,
    get_reliability_agent,
    with_retry,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')

# === Pre-configured retry policies ===

JETDRIVE_RETRY = RetryConfig(
    max_attempts=3,
    initial_delay=0.2,
    max_delay=2.0,
    exponential_base=2.0,
    retry_on=(socket.timeout, OSError, ConnectionError),
)

API_RETRY = RetryConfig(
    max_attempts=3,
    initial_delay=0.1,
    max_delay=5.0,
    exponential_base=2.0,
    retry_on=(HTTPError, URLError, ConnectionError, TimeoutError),
)

DATABASE_RETRY = RetryConfig(
    max_attempts=5,
    initial_delay=0.1,
    max_delay=10.0,
    exponential_base=2.0,
    retry_on=(Exception,),  # Catch all DB errors
)

# === Pre-configured circuit breaker policies ===

JETDRIVE_CIRCUIT = CircuitBreakerConfig(
    failure_threshold=5,  # Open after 5 failures
    success_threshold=2,  # Close after 2 successes in half-open
    timeout=30.0,  # Try again after 30s
)

EXTERNAL_API_CIRCUIT = CircuitBreakerConfig(
    failure_threshold=3,
    success_threshold=1,
    timeout=60.0,
)


# === Helper Functions ===


def jetdrive_call(func: Callable[..., T], *args, **kwargs) -> T:
    """
    Execute JetDrive operation with retry and circuit breaker.
    
    Example:
        result = jetdrive_call(discover_providers, timeout=2.0)
    """
    agent = get_reliability_agent()
    circuit = agent.get_circuit_breaker("jetdrive", JETDRIVE_CIRCUIT)
    
    @with_retry(JETDRIVE_RETRY)
    def wrapped():
        return circuit.call(func, *args, **kwargs)
    
    return wrapped()


async def jetdrive_call_async(func: Callable[..., T], *args, **kwargs) -> T:
    """
    Execute async JetDrive operation with retry and circuit breaker.
    
    Example:
        providers = await jetdrive_call_async(discover_providers, timeout=2.0)
    """
    agent = get_reliability_agent()
    circuit = agent.get_circuit_breaker("jetdrive", JETDRIVE_CIRCUIT)
    
    @with_retry(JETDRIVE_RETRY)
    async def wrapped():
        # Circuit breaker call is synchronous, but the function is async
        if circuit.state.value == "open":
            from api.reliability_agent import CircuitBreakerOpenError
            raise CircuitBreakerOpenError(f"Circuit breaker 'jetdrive' is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            circuit._on_success()
            return result
        except Exception as e:
            circuit._on_failure()
            raise e
    
    return await wrapped()


def api_call(service_name: str, func: Callable[..., T], *args, **kwargs) -> T:
    """
    Execute external API call with retry and circuit breaker.
    
    Example:
        result = api_call("jetstream", client.get_runs)
    """
    agent = get_reliability_agent()
    circuit = agent.get_circuit_breaker(f"api_{service_name}", EXTERNAL_API_CIRCUIT)
    
    @with_retry(API_RETRY)
    def wrapped():
        return circuit.call(func, *args, **kwargs)
    
    return wrapped()


def record_health(
    subsystem: str,
    status: str,
    latency_ms: Optional[float] = None,
    error: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """
    Record health check result for a subsystem.
    
    Args:
        subsystem: Name of subsystem (e.g., "jetdrive", "jetstream")
        status: "healthy", "degraded", or "unhealthy"
        latency_ms: Optional latency measurement
        error: Optional error message
        metadata: Optional additional data
    """
    agent = get_reliability_agent()
    monitor = agent.get_health_monitor(subsystem)
    monitor.record_check(status, latency_ms, error, metadata)


async def health_check_jetdrive() -> dict[str, Any]:
    """
    Perform JetDrive health check.
    
    Returns health status dict.
    """
    import time
    from api.services.jetdrive_client import discover_providers, JetDriveConfig
    
    start = time.time()
    try:
        config = JetDriveConfig.from_env()
        providers = await asyncio.wait_for(
            discover_providers(config, timeout=2.0),
            timeout=3.0
        )
        
        latency_ms = (time.time() - start) * 1000
        
        if providers:
            record_health(
                "jetdrive",
                "healthy",
                latency_ms=latency_ms,
                metadata={"provider_count": len(providers)},
            )
            return {
                "status": "healthy",
                "providers": len(providers),
                "latency_ms": latency_ms,
            }
        else:
            record_health(
                "jetdrive",
                "degraded",
                latency_ms=latency_ms,
                error="No providers found",
            )
            return {
                "status": "degraded",
                "message": "No JetDrive providers discovered",
                "latency_ms": latency_ms,
            }
    except asyncio.TimeoutError:
        latency_ms = (time.time() - start) * 1000
        record_health(
            "jetdrive",
            "unhealthy",
            latency_ms=latency_ms,
            error="Discovery timeout",
        )
        return {
            "status": "unhealthy",
            "message": "JetDrive discovery timed out",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        record_health(
            "jetdrive",
            "unhealthy",
            latency_ms=latency_ms,
            error=str(e),
        )
        return {
            "status": "unhealthy",
            "message": f"JetDrive error: {e}",
            "latency_ms": latency_ms,
        }


def health_check_jetstream(client) -> dict[str, Any]:
    """
    Perform Jetstream API health check.
    
    Args:
        client: JetstreamClient instance
        
    Returns health status dict.
    """
    import time
    
    start = time.time()
    try:
        success = client.test_connection()
        latency_ms = (time.time() - start) * 1000
        
        if success:
            record_health(
                "jetstream",
                "healthy",
                latency_ms=latency_ms,
            )
            return {
                "status": "healthy",
                "latency_ms": latency_ms,
            }
        else:
            record_health(
                "jetstream",
                "unhealthy",
                latency_ms=latency_ms,
                error="Connection test failed",
            )
            return {
                "status": "unhealthy",
                "message": "Jetstream connection test failed",
                "latency_ms": latency_ms,
            }
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        record_health(
            "jetstream",
            "unhealthy",
            latency_ms=latency_ms,
            error=str(e),
        )
        return {
            "status": "unhealthy",
            "message": f"Jetstream error: {e}",
            "latency_ms": latency_ms,
        }


# === Decorators for route handlers ===


def with_jetdrive_reliability(func):
    """Decorator for JetDrive route handlers."""
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"JetDrive operation failed: {e}")
            # Record failure for monitoring
            record_health("jetdrive", "unhealthy", error=str(e))
            raise
    
    return wrapper


def with_api_reliability(service_name: str):
    """Decorator for external API route handlers."""
    def decorator(func):
        from functools import wraps
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"{service_name} operation failed: {e}")
                record_health(service_name, "unhealthy", error=str(e))
                raise
        
        return wrapper
    
    return decorator

