"""
Prometheus Metrics for DynoAI API.

Provides:
- Standard Flask metrics (request duration, count, etc.)
- Custom business metrics (analysis count, VE corrections, etc.)
- Optional metrics export (can be disabled in development)
- Prometheus-compatible /metrics endpoint
"""

import os
import logging
from typing import Optional

from flask import Flask
from prometheus_client import Counter, Histogram, Gauge, Info

logger = logging.getLogger(__name__)

# =============================================================================
# Global Metrics Instance
# =============================================================================

_metrics_enabled: bool = False
_flask_metrics = None

# =============================================================================
# Custom Business Metrics
# =============================================================================

# Analysis metrics
analysis_total = Counter(
    "dynoai_analysis_total",
    "Total number of analyses run",
    ["status", "source"],  # success/error, upload/jetstream/simulator
)

analysis_duration = Histogram(
    "dynoai_analysis_duration_seconds",
    "Time spent on analysis operations",
    ["source"],
    buckets=[1, 5, 10, 30, 60, 120, 300],  # seconds
)

# VE correction metrics
ve_corrections_count = Histogram(
    "dynoai_ve_corrections_count",
    "Number of VE corrections per analysis",
    buckets=[0, 10, 25, 50, 100, 250, 500, 1000],
)

ve_corrections_magnitude = Histogram(
    "dynoai_ve_corrections_magnitude_percent",
    "Magnitude of VE corrections (percent)",
    buckets=[0.5, 1, 2, 5, 7, 10, 15],  # percent
)

# Jetstream integration metrics
jetstream_runs_total = Counter(
    "dynoai_jetstream_runs_total",
    "Total Jetstream runs processed",
    ["status"],  # pending/processing/complete/error
)

jetstream_poll_duration = Histogram(
    "dynoai_jetstream_poll_duration_seconds",
    "Time spent polling Jetstream API",
    buckets=[0.1, 0.5, 1, 2, 5, 10],
)

# Virtual tuning metrics
virtual_tuning_sessions_total = Counter(
    "dynoai_virtual_tuning_sessions_total",
    "Total virtual tuning sessions",
    ["status"],  # running/converged/failed/stopped
)

virtual_tuning_iterations = Histogram(
    "dynoai_virtual_tuning_iterations",
    "Number of iterations to convergence",
    buckets=[1, 2, 3, 5, 7, 10, 15, 20],
)

# Upload metrics
file_upload_bytes = Histogram(
    "dynoai_file_upload_bytes",
    "Size of uploaded files in bytes",
    buckets=[
        1024,  # 1 KB
        10240,  # 10 KB
        102400,  # 100 KB
        1048576,  # 1 MB
        10485760,  # 10 MB
        52428800,  # 50 MB
    ],
)

# System metrics
active_sessions = Gauge(
    "dynoai_active_sessions",
    "Number of active tuning sessions",
)

# Application info
app_info = Info(
    "dynoai_app",
    "DynoAI application information",
)


# =============================================================================
# Initialization
# =============================================================================


def init_metrics(app: Flask) -> Optional[object]:
    """
    Initialize Prometheus metrics for the Flask app.

    Args:
        app: Flask application instance

    Returns:
        PrometheusMetrics instance if enabled, None otherwise

    Environment Variables:
        PROMETHEUS_METRICS_ENABLED: Enable/disable metrics (default: false)
        PROMETHEUS_METRICS_PORT: Port for metrics endpoint (default: uses main Flask port)
    """
    global _metrics_enabled, _flask_metrics

    enabled = os.getenv("PROMETHEUS_METRICS_ENABLED", "false").lower() == "true"

    if not enabled:
        logger.info("Prometheus metrics DISABLED (set PROMETHEUS_METRICS_ENABLED=true to enable)")
        return None

    try:
        from prometheus_flask_exporter import PrometheusMetrics

        _flask_metrics = PrometheusMetrics(
            app,
            path="/metrics",  # Endpoint for Prometheus scraping
            export_defaults=True,  # Export default Flask metrics
            defaults_prefix="dynoai",  # Prefix for default metrics
            group_by="endpoint",  # Group metrics by endpoint
        )

        _metrics_enabled = True

        # Set application info
        from dynoai import __version__

        app_info.info(
            {
                "version": __version__,
                "python_version": "3.10+",
                "environment": os.getenv("FLASK_ENV", "production"),
            }
        )

        logger.info(f"Prometheus metrics ENABLED at /metrics (DynoAI v{__version__})")

        return _flask_metrics

    except ImportError:
        logger.warning(
            "prometheus-flask-exporter not installed. "
            "Install with: pip install prometheus-flask-exporter"
        )
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Prometheus metrics: {e}")
        return None


def get_metrics():
    """
    Get the Flask metrics instance.

    Returns:
        PrometheusMetrics instance if enabled, None otherwise
    """
    return _flask_metrics


def is_enabled() -> bool:
    """
    Check if metrics are enabled.

    Returns:
        True if metrics are enabled, False otherwise
    """
    return _metrics_enabled


# =============================================================================
# Metric Recording Helpers
# =============================================================================


def record_analysis(status: str, source: str = "upload", duration: float = 0):
    """
    Record an analysis operation.

    Args:
        status: "success" or "error"
        source: "upload", "jetstream", or "simulator"
        duration: Time taken in seconds
    """
    if not _metrics_enabled:
        return

    analysis_total.labels(status=status, source=source).inc()
    if duration > 0:
        analysis_duration.labels(source=source).observe(duration)


def record_ve_corrections(count: int, max_magnitude: float):
    """
    Record VE corrections applied.

    Args:
        count: Number of corrections applied
        max_magnitude: Maximum correction magnitude in percent
    """
    if not _metrics_enabled:
        return

    ve_corrections_count.observe(count)
    ve_corrections_magnitude.observe(abs(max_magnitude))


def record_jetstream_run(status: str):
    """
    Record a Jetstream run.

    Args:
        status: "pending", "processing", "complete", or "error"
    """
    if not _metrics_enabled:
        return

    jetstream_runs_total.labels(status=status).inc()


def record_virtual_tuning_session(status: str, iterations: int = 0):
    """
    Record a virtual tuning session.

    Args:
        status: "running", "converged", "failed", or "stopped"
        iterations: Number of iterations (if converged)
    """
    if not _metrics_enabled:
        return

    virtual_tuning_sessions_total.labels(status=status).inc()
    if iterations > 0:
        virtual_tuning_iterations.observe(iterations)


def record_file_upload(size_bytes: int):
    """
    Record a file upload.

    Args:
        size_bytes: File size in bytes
    """
    if not _metrics_enabled:
        return

    file_upload_bytes.observe(size_bytes)


def set_active_sessions(count: int):
    """
    Set the number of active tuning sessions.

    Args:
        count: Number of active sessions
    """
    if not _metrics_enabled:
        return

    active_sessions.set(count)


# =============================================================================
# CLI Utility
# =============================================================================

if __name__ == "__main__":
    import sys

    print("DynoAI Prometheus Metrics")
    print("=" * 50)
    print("\nAvailable metrics:")
    print("  - dynoai_analysis_total")
    print("  - dynoai_analysis_duration_seconds")
    print("  - dynoai_ve_corrections_count")
    print("  - dynoai_ve_corrections_magnitude_percent")
    print("  - dynoai_jetstream_runs_total")
    print("  - dynoai_jetstream_poll_duration_seconds")
    print("  - dynoai_virtual_tuning_sessions_total")
    print("  - dynoai_virtual_tuning_iterations")
    print("  - dynoai_file_upload_bytes")
    print("  - dynoai_active_sessions")
    print("  - dynoai_app (info)")
    print("\nEndpoint: /metrics")
    print("\nEnable with: PROMETHEUS_METRICS_ENABLED=true")
