"""
DynoAI Structured Logging Configuration.

Provides JSON-formatted logs for production and human-readable logs for development.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from flask import g, has_request_context, request


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add request context if available
        if has_request_context():
            log_data["request_id"] = getattr(g, "request_id", None)
            log_data["method"] = request.method
            log_data["path"] = request.path
            log_data["remote_addr"] = request.remote_addr

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data, default=str)


class DevelopmentFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")

        # Add request ID if available
        request_id = ""
        if has_request_context():
            rid = getattr(g, "request_id", None)
            if rid:
                request_id = f"[{rid[:8]}] "

        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]

        base_msg = (
            f"{color}{timestamp} {record.levelname:8}{self.RESET} "
            f"{request_id}{record.name}: {record.getMessage()}"
        )

        # Add extra data if present
        if hasattr(record, "extra_data") and record.extra_data:
            extra_str = " | " + ", ".join(
                f"{k}={v}" for k, v in record.extra_data.items()
            )
            base_msg += extra_str

        return base_msg


def setup_logging(log_format: str = "development", log_level: str = "INFO") -> None:
    """
    Configure logging for the application.

    Args:
        log_format: "development" for human-readable or "production" for JSON
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    root_logger = logging.getLogger()

    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    if log_format == "production":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(DevelopmentFormatter())

    root_logger.addHandler(handler)

    # Set levels for noisy libraries
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that supports extra_data for structured logging.

    Usage:
        logger = get_structured_logger(__name__)
        logger.info("File saved", path="/uploads/file.csv", size_bytes=1024)
    """

    def process(
        self, msg: str, kwargs: Dict[str, Any]
    ) -> tuple[str, Dict[str, Any]]:
        # Extract extra_data from kwargs
        extra_data = {}
        keys_to_remove = []

        for key, value in kwargs.items():
            if key not in ("exc_info", "stack_info", "stacklevel", "extra"):
                extra_data[key] = value
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del kwargs[key]

        # Merge with existing extra if present
        if "extra" not in kwargs:
            kwargs["extra"] = {}
        if extra_data:
            kwargs["extra"]["extra_data"] = extra_data

        return msg, kwargs


def get_structured_logger(name: str) -> LoggerAdapter:
    """
    Get a structured logger that supports keyword arguments for extra data.

    Usage:
        logger = get_structured_logger(__name__)
        logger.info("Saving file", path="/uploads/file.csv")
        logger.error("Analysis failed", error=str(e), stage="validation")
    """
    return LoggerAdapter(logging.getLogger(name), {})

