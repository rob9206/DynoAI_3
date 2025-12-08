"""
DynoAI Prometheus Metrics Module.

Provides application metrics for monitoring and observability.
Exports metrics at /metrics endpoint in Prometheus format.
"""

import os
import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from flask import Flask, Request, Response, request

# Type variable for decorator typing
F = TypeVar("F", bound=Callable[..., Any])

# Module-level metrics instance
_metrics: Optional["PrometheusMetrics"] = None  # type: ignore
_enabled: bool = False

# Import prometheus_flask_exporter only if metrics are enabled
# This allows graceful degradation when the package isn't installed
try:
    from prometheus_flask_exporter import PrometheusMetrics
    from prometheus_client import Counter, Histogram, Gauge, Info

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    PrometheusMetrics = None  # type: ignore
    Counter = None  # type: ignore
    Histogram = None  # type: ignore
    Gauge = None  # type: ignore
    Info = None  # type: ignore


# Custom business metrics (created after init)
_analysis_counter: Optional["Counter"] = None
_analysis_duration: Optional["Histogram"] = None
_file_upload_size: Optional["Histogram"] = None
_jetstream_runs_counter: Optional["Counter"] = None
_ve_corrections_histogram: Optional["Histogram"] = None
_active_analyses: Optional["Gauge"] = None


def is_metrics_enabled() -> bool:
    """Check if metrics collection is enabled."""
    return _enabled and _PROMETHEUS_AVAILABLE


def get_metrics() -> Optional["PrometheusMetrics"]:
    """Get the PrometheusMetrics instance, if initialized."""
    return _metrics


def init_metrics(app: Flask) -> Optional["PrometheusMetrics"]:
    """
    Initialize Prometheus metrics for the Flask application.

    Environment variables:
        METRICS_ENABLED: "true" or "false" (default: "true")
        METRICS_PATH: Path for metrics endpoint (default: "/metrics")

    Args:
        app: Flask application instance

    Returns:
        PrometheusMetrics instance if enabled and available, None otherwise
    """
    global _metrics, _enabled
    global _analysis_counter, _analysis_duration, _file_upload_size
    global _jetstream_runs_counter, _ve_corrections_histogram, _active_analyses

    # Check if metrics are enabled
    _enabled = os.getenv("METRICS_ENABLED", "true").lower() == "true"

    if not _enabled:
        app.logger.info("Prometheus metrics disabled via METRICS_ENABLED=false")
        return None

    if not _PROMETHEUS_AVAILABLE:
        app.logger.warning(
            "prometheus-flask-exporter not installed. "
            "Install with: pip install prometheus-flask-exporter"
        )
        return None

    # Get metrics path from environment
    metrics_path = os.getenv("METRICS_PATH", "/metrics")

    # Initialize PrometheusMetrics with DynoAI prefix
    _metrics = PrometheusMetrics(
        app,
        path=metrics_path,
        export_defaults=True,
        defaults_prefix="dynoai",
        # Exclude health endpoints from default metrics to reduce noise
        excluded_paths=["^/api/health"],
    )

    # Register application info metric
    _metrics.info(
        "app_info",
        "DynoAI application information",
        version=os.getenv("DYNOAI_VERSION", "1.2.0"),
        environment=os.getenv("DYNOAI_ENV", "development"),
    )

    # Create custom business metrics
    _analysis_counter = Counter(
        "dynoai_analysis_total",
        "Total number of analyses performed",
        ["status", "source"],
    )

    _analysis_duration = Histogram(
        "dynoai_analysis_duration_seconds",
        "Time spent performing analysis",
        ["source"],
        buckets=[0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
    )

    _file_upload_size = Histogram(
        "dynoai_file_upload_bytes",
        "Size of uploaded files in bytes",
        buckets=[
            1024,  # 1KB
            10240,  # 10KB
            102400,  # 100KB
            1048576,  # 1MB
            10485760,  # 10MB
            52428800,  # 50MB
        ],
    )

    _jetstream_runs_counter = Counter(
        "dynoai_jetstream_runs_total",
        "Total Jetstream runs processed",
        ["status"],
    )

    _ve_corrections_histogram = Histogram(
        "dynoai_ve_corrections_count",
        "Number of VE corrections applied per analysis",
        buckets=[0, 10, 50, 100, 250, 500, 1000, 2500],
    )

    _active_analyses = Gauge(
        "dynoai_active_analyses",
        "Number of currently running analyses",
    )

    app.logger.info(f"Prometheus metrics initialized at {metrics_path}")

    return _metrics


# =============================================================================
# Metric Recording Functions
# =============================================================================


def record_analysis_started(source: str = "upload") -> None:
    """
    Record that an analysis has started.

    Args:
        source: Source of the analysis ("upload" or "jetstream")
    """
    if _active_analyses is not None:
        _active_analyses.inc()


def record_analysis_completed(
    source: str = "upload",
    success: bool = True,
    duration_seconds: Optional[float] = None,
    corrections_count: Optional[int] = None,
) -> None:
    """
    Record that an analysis has completed.

    Args:
        source: Source of the analysis ("upload" or "jetstream")
        success: Whether the analysis succeeded
        duration_seconds: Time taken for analysis
        corrections_count: Number of VE corrections applied
    """
    status = "success" if success else "error"

    if _analysis_counter is not None:
        _analysis_counter.labels(status=status, source=source).inc()

    if _active_analyses is not None:
        _active_analyses.dec()

    if duration_seconds is not None and _analysis_duration is not None:
        _analysis_duration.labels(source=source).observe(duration_seconds)

    if corrections_count is not None and _ve_corrections_histogram is not None:
        _ve_corrections_histogram.observe(corrections_count)


def record_file_upload(size_bytes: int) -> None:
    """
    Record a file upload.

    Args:
        size_bytes: Size of the uploaded file in bytes
    """
    if _file_upload_size is not None:
        _file_upload_size.observe(size_bytes)


def record_jetstream_run(status: str) -> None:
    """
    Record a Jetstream run event.

    Args:
        status: Status of the run ("queued", "processing", "complete", "error")
    """
    if _jetstream_runs_counter is not None:
        _jetstream_runs_counter.labels(status=status).inc()


# =============================================================================
# Decorator for Tracking Analysis Duration
# =============================================================================


def track_analysis_duration(source: str = "upload") -> Callable[[F], F]:
    """
    Decorator to track analysis duration.

    Usage:
        @track_analysis_duration("upload")
        def analyze_file(path):
            ...

    Args:
        source: Source identifier for the analysis

    Returns:
        Decorated function
    """

    def decorator(f: F) -> F:
        @wraps(f)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            if not is_metrics_enabled():
                return f(*args, **kwargs)

            record_analysis_started(source)
            start_time = time.time()
            success = True

            try:
                result = f(*args, **kwargs)
                return result
            except Exception:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                record_analysis_completed(
                    source=source,
                    success=success,
                    duration_seconds=duration,
                )

        return wrapped  # type: ignore

    return decorator


def track_file_upload() -> Callable[[F], F]:
    """
    Decorator to track uploaded file size from Flask request.

    Usage:
        @track_file_upload()
        def upload_handler():
            file = request.files['file']
            ...

    Returns:
        Decorated function
    """

    def decorator(f: F) -> F:
        @wraps(f)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            if is_metrics_enabled() and request.content_length:
                record_file_upload(request.content_length)
            return f(*args, **kwargs)

        return wrapped  # type: ignore

    return decorator




