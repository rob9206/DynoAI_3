"""
Ingestion Configuration System

Provides comprehensive configuration for all data ingestion parameters:
- Retry settings (attempts, delays, backoff)
- Circuit breaker settings (thresholds, timeouts)
- Queue settings (size, priorities, persistence)
- Data source specific settings
- Validation thresholds
- Logging configuration
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration Dataclasses
# =============================================================================


@dataclass
class RetrySettings:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    initial_delay_sec: float = 0.1
    max_delay_sec: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_timeout: bool = True
    retry_on_connection_error: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "initial_delay_sec": self.initial_delay_sec,
            "max_delay_sec": self.max_delay_sec,
            "exponential_base": self.exponential_base,
            "jitter": self.jitter,
            "retry_on_timeout": self.retry_on_timeout,
            "retry_on_connection_error": self.retry_on_connection_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetrySettings":
        return cls(
            max_attempts=data.get("max_attempts", 3),
            initial_delay_sec=data.get("initial_delay_sec", 0.1),
            max_delay_sec=data.get("max_delay_sec", 30.0),
            exponential_base=data.get("exponential_base", 2.0),
            jitter=data.get("jitter", True),
            retry_on_timeout=data.get("retry_on_timeout", True),
            retry_on_connection_error=data.get("retry_on_connection_error", True),
        )


@dataclass
class CircuitBreakerSettings:
    """Configuration for circuit breaker pattern."""

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_sec: float = 60.0
    half_open_max_calls: int = 3
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
            "timeout_sec": self.timeout_sec,
            "half_open_max_calls": self.half_open_max_calls,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CircuitBreakerSettings":
        return cls(
            failure_threshold=data.get("failure_threshold", 5),
            success_threshold=data.get("success_threshold", 2),
            timeout_sec=data.get("timeout_sec", 60.0),
            half_open_max_calls=data.get("half_open_max_calls", 3),
            enabled=data.get("enabled", True),
        )


@dataclass
class QueueSettings:
    """Configuration for ingestion queue."""

    max_size: int = 10000
    batch_size: int = 100
    flush_interval_sec: float = 5.0
    persist_to_disk: bool = False
    persist_path: str = "data/ingestion_queue"
    priority_enabled: bool = True
    drop_on_full: bool = True
    drop_oldest: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_size": self.max_size,
            "batch_size": self.batch_size,
            "flush_interval_sec": self.flush_interval_sec,
            "persist_to_disk": self.persist_to_disk,
            "persist_path": self.persist_path,
            "priority_enabled": self.priority_enabled,
            "drop_on_full": self.drop_on_full,
            "drop_oldest": self.drop_oldest,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueueSettings":
        return cls(
            max_size=data.get("max_size", 10000),
            batch_size=data.get("batch_size", 100),
            flush_interval_sec=data.get("flush_interval_sec", 5.0),
            persist_to_disk=data.get("persist_to_disk", False),
            persist_path=data.get("persist_path", "data/ingestion_queue"),
            priority_enabled=data.get("priority_enabled", True),
            drop_on_full=data.get("drop_on_full", True),
            drop_oldest=data.get("drop_oldest", True),
        )


@dataclass
class ValidationSettings:
    """Configuration for data validation."""

    enabled: bool = True
    strict_mode: bool = False
    max_validation_errors: int = 100
    sanitize_values: bool = True
    reject_nan: bool = True
    reject_inf: bool = True
    reject_out_of_range: bool = False
    log_warnings: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "strict_mode": self.strict_mode,
            "max_validation_errors": self.max_validation_errors,
            "sanitize_values": self.sanitize_values,
            "reject_nan": self.reject_nan,
            "reject_inf": self.reject_inf,
            "reject_out_of_range": self.reject_out_of_range,
            "log_warnings": self.log_warnings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationSettings":
        return cls(
            enabled=data.get("enabled", True),
            strict_mode=data.get("strict_mode", False),
            max_validation_errors=data.get("max_validation_errors", 100),
            sanitize_values=data.get("sanitize_values", True),
            reject_nan=data.get("reject_nan", True),
            reject_inf=data.get("reject_inf", True),
            reject_out_of_range=data.get("reject_out_of_range", False),
            log_warnings=data.get("log_warnings", True),
        )


@dataclass
class DataSourceConfig:
    """Configuration for a specific data source."""

    name: str
    enabled: bool = True
    connection_timeout_sec: float = 10.0
    read_timeout_sec: float = 30.0
    buffer_size: int = 4096
    retry: RetrySettings = field(default_factory=RetrySettings)
    circuit_breaker: CircuitBreakerSettings = field(
        default_factory=CircuitBreakerSettings
    )
    validation: ValidationSettings = field(default_factory=ValidationSettings)
    custom_settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "connection_timeout_sec": self.connection_timeout_sec,
            "read_timeout_sec": self.read_timeout_sec,
            "buffer_size": self.buffer_size,
            "retry": self.retry.to_dict(),
            "circuit_breaker": self.circuit_breaker.to_dict(),
            "validation": self.validation.to_dict(),
            "custom_settings": self.custom_settings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DataSourceConfig":
        return cls(
            name=data.get("name", "unknown"),
            enabled=data.get("enabled", True),
            connection_timeout_sec=data.get("connection_timeout_sec", 10.0),
            read_timeout_sec=data.get("read_timeout_sec", 30.0),
            buffer_size=data.get("buffer_size", 4096),
            retry=RetrySettings.from_dict(data.get("retry", {})),
            circuit_breaker=CircuitBreakerSettings.from_dict(
                data.get("circuit_breaker", {})
            ),
            validation=ValidationSettings.from_dict(data.get("validation", {})),
            custom_settings=data.get("custom_settings", {}),
        )


# =============================================================================
# JetDrive Specific Configuration
# =============================================================================


@dataclass
class JetDriveConfig:
    """JetDrive-specific configuration."""

    multicast_group: str = "224.0.2.10"
    port: int = 22344
    interface: str = "0.0.0.0"
    discovery_timeout_sec: float = 3.0
    subscribe_timeout_sec: float = 0.5
    channel_filter: list[str] = field(default_factory=list)
    provider_filter: list[int] = field(default_factory=list)
    auto_reconnect: bool = True
    reconnect_delay_sec: float = 5.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "multicast_group": self.multicast_group,
            "port": self.port,
            "interface": self.interface,
            "discovery_timeout_sec": self.discovery_timeout_sec,
            "subscribe_timeout_sec": self.subscribe_timeout_sec,
            "channel_filter": self.channel_filter,
            "provider_filter": self.provider_filter,
            "auto_reconnect": self.auto_reconnect,
            "reconnect_delay_sec": self.reconnect_delay_sec,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JetDriveConfig":
        return cls(
            multicast_group=data.get("multicast_group", "224.0.2.10"),
            port=data.get("port", 22344),
            interface=data.get("interface", "0.0.0.0"),
            discovery_timeout_sec=data.get("discovery_timeout_sec", 3.0),
            subscribe_timeout_sec=data.get("subscribe_timeout_sec", 0.5),
            channel_filter=data.get("channel_filter", []),
            provider_filter=data.get("provider_filter", []),
            auto_reconnect=data.get("auto_reconnect", True),
            reconnect_delay_sec=data.get("reconnect_delay_sec", 5.0),
        )

    @classmethod
    def from_env(cls) -> "JetDriveConfig":
        """Load configuration from environment variables."""
        return cls(
            multicast_group=os.getenv("JETDRIVE_MCAST_GROUP", "224.0.2.10"),
            port=int(os.getenv("JETDRIVE_PORT", "22344")),
            interface=os.getenv("JETDRIVE_IFACE", "0.0.0.0"),
        )


# =============================================================================
# Innovate Specific Configuration
# =============================================================================


@dataclass
class InnovateConfig:
    """Innovate device configuration."""

    port: str | None = None
    baudrate: int = 19200
    device_type: str = "AUTO"  # AUTO, DLG-1, LC-2
    channels: list[int] = field(default_factory=lambda: [1, 2])
    auto_detect_port: bool = True
    auto_reconnect: bool = True
    reconnect_delay_sec: float = 3.0
    read_interval_sec: float = 0.08  # ~12 Hz
    buffer_size: int = 1024

    def to_dict(self) -> dict[str, Any]:
        return {
            "port": self.port,
            "baudrate": self.baudrate,
            "device_type": self.device_type,
            "channels": self.channels,
            "auto_detect_port": self.auto_detect_port,
            "auto_reconnect": self.auto_reconnect,
            "reconnect_delay_sec": self.reconnect_delay_sec,
            "read_interval_sec": self.read_interval_sec,
            "buffer_size": self.buffer_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InnovateConfig":
        return cls(
            port=data.get("port"),
            baudrate=data.get("baudrate", 19200),
            device_type=data.get("device_type", "AUTO"),
            channels=data.get("channels", [1, 2]),
            auto_detect_port=data.get("auto_detect_port", True),
            auto_reconnect=data.get("auto_reconnect", True),
            reconnect_delay_sec=data.get("reconnect_delay_sec", 3.0),
            read_interval_sec=data.get("read_interval_sec", 0.08),
            buffer_size=data.get("buffer_size", 1024),
        )


# =============================================================================
# Master Ingestion Configuration
# =============================================================================


@dataclass
class IngestionConfig:
    """Master configuration for all data ingestion."""

    # Global settings
    global_enabled: bool = True
    log_level: str = "INFO"
    metrics_enabled: bool = True
    metrics_interval_sec: float = 60.0

    # Queue settings
    queue: QueueSettings = field(default_factory=QueueSettings)

    # Default retry/circuit breaker (can be overridden per source)
    default_retry: RetrySettings = field(default_factory=RetrySettings)
    default_circuit_breaker: CircuitBreakerSettings = field(
        default_factory=CircuitBreakerSettings
    )
    default_validation: ValidationSettings = field(default_factory=ValidationSettings)

    # Data source specific configs
    jetdrive: JetDriveConfig = field(default_factory=JetDriveConfig)
    innovate: InnovateConfig = field(default_factory=InnovateConfig)
    data_sources: dict[str, DataSourceConfig] = field(default_factory=dict)

    def get_source_config(self, source_name: str) -> DataSourceConfig:
        """Get configuration for a specific data source."""
        if source_name in self.data_sources:
            return self.data_sources[source_name]

        # Return default config
        return DataSourceConfig(
            name=source_name,
            retry=self.default_retry,
            circuit_breaker=self.default_circuit_breaker,
            validation=self.default_validation,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "global_enabled": self.global_enabled,
            "log_level": self.log_level,
            "metrics_enabled": self.metrics_enabled,
            "metrics_interval_sec": self.metrics_interval_sec,
            "queue": self.queue.to_dict(),
            "default_retry": self.default_retry.to_dict(),
            "default_circuit_breaker": self.default_circuit_breaker.to_dict(),
            "default_validation": self.default_validation.to_dict(),
            "jetdrive": self.jetdrive.to_dict(),
            "innovate": self.innovate.to_dict(),
            "data_sources": {
                name: config.to_dict() for name, config in self.data_sources.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IngestionConfig":
        data_sources = {}
        for name, source_data in data.get("data_sources", {}).items():
            data_sources[name] = DataSourceConfig.from_dict(source_data)

        return cls(
            global_enabled=data.get("global_enabled", True),
            log_level=data.get("log_level", "INFO"),
            metrics_enabled=data.get("metrics_enabled", True),
            metrics_interval_sec=data.get("metrics_interval_sec", 60.0),
            queue=QueueSettings.from_dict(data.get("queue", {})),
            default_retry=RetrySettings.from_dict(data.get("default_retry", {})),
            default_circuit_breaker=CircuitBreakerSettings.from_dict(
                data.get("default_circuit_breaker", {})
            ),
            default_validation=ValidationSettings.from_dict(
                data.get("default_validation", {})
            ),
            jetdrive=JetDriveConfig.from_dict(data.get("jetdrive", {})),
            innovate=InnovateConfig.from_dict(data.get("innovate", {})),
            data_sources=data_sources,
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "IngestionConfig":
        """Load configuration from JSON file."""
        path = Path(path)
        if not path.exists():
            logger.warning(f"Config file not found: {path}, using defaults")
            return cls()

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}")
            return cls()

    def save_to_file(self, path: str | Path) -> None:
        """Save configuration to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

        logger.info(f"Saved ingestion config to {path}")


# =============================================================================
# Global Configuration Instance
# =============================================================================

_config: IngestionConfig | None = None


def get_ingestion_config() -> IngestionConfig:
    """Get global ingestion configuration."""
    global _config
    if _config is None:
        # Try to load from default locations
        config_paths = [
            Path("config/ingestion.json"),
            Path(__file__).parent.parent.parent.parent / "config" / "ingestion.json",
        ]

        for path in config_paths:
            if path.exists():
                _config = IngestionConfig.from_file(path)
                break

        if _config is None:
            _config = IngestionConfig()
            logger.info("Using default ingestion configuration")

    return _config


def set_ingestion_config(config: IngestionConfig) -> None:
    """Set global ingestion configuration."""
    global _config
    _config = config


def reset_ingestion_config() -> None:
    """Reset global configuration (for testing)."""
    global _config
    _config = None


# =============================================================================
# Default Configurations for Common Scenarios
# =============================================================================


def create_default_jetdrive_config() -> DataSourceConfig:
    """Create default configuration for JetDrive."""
    return DataSourceConfig(
        name="jetdrive",
        connection_timeout_sec=5.0,
        read_timeout_sec=0.5,
        buffer_size=4096,
        retry=RetrySettings(
            max_attempts=3,
            initial_delay_sec=0.2,
            max_delay_sec=2.0,
        ),
        circuit_breaker=CircuitBreakerSettings(
            failure_threshold=5,
            success_threshold=2,
            timeout_sec=30.0,
        ),
    )


def create_default_innovate_config() -> DataSourceConfig:
    """Create default configuration for Innovate devices."""
    return DataSourceConfig(
        name="innovate",
        connection_timeout_sec=5.0,
        read_timeout_sec=1.0,
        retry=RetrySettings(
            max_attempts=5,
            initial_delay_sec=0.5,
            max_delay_sec=5.0,
        ),
        circuit_breaker=CircuitBreakerSettings(
            failure_threshold=3,
            success_threshold=1,
            timeout_sec=15.0,
        ),
    )


def create_high_reliability_config() -> IngestionConfig:
    """Create configuration optimized for maximum reliability."""
    return IngestionConfig(
        queue=QueueSettings(
            max_size=50000,
            persist_to_disk=True,
            drop_on_full=False,
        ),
        default_retry=RetrySettings(
            max_attempts=5,
            initial_delay_sec=0.5,
            max_delay_sec=60.0,
        ),
        default_circuit_breaker=CircuitBreakerSettings(
            failure_threshold=10,
            timeout_sec=340.0,
        ),
        default_validation=ValidationSettings(
            strict_mode=True,
            reject_out_of_range=True,
        ),
    )


def create_low_latency_config() -> IngestionConfig:
    """Create configuration optimized for low latency."""
    return IngestionConfig(
        queue=QueueSettings(
            max_size=1000,
            batch_size=10,
            flush_interval_sec=0.5,
            persist_to_disk=False,
        ),
        default_retry=RetrySettings(
            max_attempts=1,
            initial_delay_sec=0.05,
            max_delay_sec=0.5,
        ),
        default_circuit_breaker=CircuitBreakerSettings(
            failure_threshold=3,
            timeout_sec=10.0,
        ),
        default_validation=ValidationSettings(
            strict_mode=False,
            reject_out_of_range=False,
        ),
    )
