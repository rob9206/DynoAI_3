"""
DynoAI API Configuration Module.

Centralizes all configuration settings with environment variable support
and sensible defaults for development and production environments.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _get_bool_env(key: str, default: bool = False) -> bool:
    """Get boolean from environment variable."""
    val = os.environ.get(key, str(default)).lower()
    return val in ("true", "1", "yes", "on")


def _get_int_env(key: str, default: int) -> int:
    """Get integer from environment variable."""
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


@dataclass
class ServerConfig:
    """Flask server configuration."""

    host: str = field(default_factory=lambda: os.environ.get("DYNOAI_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _get_int_env("DYNOAI_PORT", 5001))
    debug: bool = field(default_factory=lambda: _get_bool_env("DYNOAI_DEBUG", True))
    threaded: bool = True


@dataclass
class StorageConfig:
    """File storage configuration."""

    upload_folder: Path = field(
        default_factory=lambda: Path(os.environ.get("DYNOAI_UPLOAD_DIR", "uploads"))
    )
    output_folder: Path = field(
        default_factory=lambda: Path(os.environ.get("DYNOAI_OUTPUT_DIR", "outputs"))
    )
    runs_folder: Path = field(
        default_factory=lambda: Path(os.environ.get("DYNOAI_RUNS_DIR", "runs"))
    )
    max_content_length: int = field(
        default_factory=lambda: _get_int_env("DYNOAI_MAX_UPLOAD_MB", 50) * 1024 * 1024
    )
    allowed_extensions: frozenset = field(
        default_factory=lambda: frozenset({"csv", "txt"})
    )

    def __post_init__(self) -> None:
        """Ensure storage directories exist."""
        self.upload_folder.mkdir(exist_ok=True)
        self.output_folder.mkdir(exist_ok=True)
        self.runs_folder.mkdir(exist_ok=True)


@dataclass
class TuningOptionsConfig:
    """Tuning options for run processing."""

    # Decel Fuel Management
    decel_management: bool = field(
        default_factory=lambda: _get_bool_env("DYNOAI_DECEL_MANAGEMENT", False)
    )
    decel_severity: str = field(
        default_factory=lambda: os.environ.get("DYNOAI_DECEL_SEVERITY", "medium")
    )
    decel_rpm_min: int = field(
        default_factory=lambda: _get_int_env("DYNOAI_DECEL_RPM_MIN", 1500)
    )
    decel_rpm_max: int = field(
        default_factory=lambda: _get_int_env("DYNOAI_DECEL_RPM_MAX", 5500)
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decel_management": self.decel_management,
            "decel_severity": self.decel_severity,
            "decel_rpm_min": self.decel_rpm_min,
            "decel_rpm_max": self.decel_rpm_max,
        }


@dataclass
class JetstreamConfig:
    """Jetstream integration configuration."""

    api_url: str = field(
        default_factory=lambda: os.environ.get("JETSTREAM_API_URL", "")
    )
    api_key: str = field(
        default_factory=lambda: os.environ.get("JETSTREAM_API_KEY", "")
    )
    poll_interval_seconds: int = field(
        default_factory=lambda: _get_int_env("JETSTREAM_POLL_INTERVAL", 30)
    )
    auto_process: bool = field(
        default_factory=lambda: _get_bool_env("JETSTREAM_AUTO_PROCESS", True)
    )
    enabled: bool = field(
        default_factory=lambda: _get_bool_env("JETSTREAM_ENABLED", False)
    )
    stub_mode: bool = field(
        default_factory=lambda: _get_bool_env("JETSTREAM_STUB_MODE", False)
    )
    tuning_options: TuningOptionsConfig = field(default_factory=TuningOptionsConfig)

    def to_dict(self, mask_key: bool = True) -> Dict[str, Any]:
        """Convert to dictionary, optionally masking the API key."""
        return {
            "api_url": self.api_url,
            "api_key": self._mask_key() if mask_key else self.api_key,
            "poll_interval_seconds": self.poll_interval_seconds,
            "auto_process": self.auto_process,
            "enabled": self.enabled,
            "stub_mode": self.stub_mode,
            "tuning_options": self.tuning_options.to_dict(),
        }

    def _mask_key(self) -> str:
        """Mask the API key for safe display."""
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "*" * len(self.api_key)
        return self.api_key[:4] + "*" * (len(self.api_key) - 8) + self.api_key[-4:]


@dataclass
class CORSConfig:
    """CORS configuration."""

    origins: List[str] = field(
        default_factory=lambda: os.environ.get("DYNOAI_CORS_ORIGINS", "*").split(",")
    )
    resources: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set up CORS resources pattern."""
        if not self.resources:
            self.resources = {r"/api/*": {"origins": self.origins}}


@dataclass
class AnalysisConfig:
    """Default analysis parameters."""

    default_smooth_passes: int = field(
        default_factory=lambda: _get_int_env("DYNOAI_SMOOTH_PASSES", 2)
    )
    default_clamp: float = field(
        default_factory=lambda: float(os.environ.get("DYNOAI_CLAMP", "15.0"))
    )
    default_rear_bias: float = field(
        default_factory=lambda: float(os.environ.get("DYNOAI_REAR_BIAS", "0.0"))
    )
    default_rear_rule_deg: float = field(
        default_factory=lambda: float(os.environ.get("DYNOAI_REAR_RULE_DEG", "2.0"))
    )
    default_hot_extra: float = field(
        default_factory=lambda: float(os.environ.get("DYNOAI_HOT_EXTRA", "-1.0"))
    )


@dataclass
class XAIConfig:
    """xAI (Grok) API configuration."""

    api_key: str = field(default_factory=lambda: os.environ.get("XAI_API_KEY", ""))
    api_url: str = field(
        default_factory=lambda: os.environ.get(
            "XAI_API_URL", "https://api.x.ai/v1/chat/completions"
        )
    )
    model: str = field(default_factory=lambda: os.environ.get("XAI_MODEL", "grok-beta"))
    enabled: bool = field(default_factory=lambda: _get_bool_env("XAI_ENABLED", False))


@dataclass
class AppConfig:
    """Main application configuration container."""

    # Application metadata
    app_name: str = "DynoAI"
    version: str = "1.2.0"

    # Sub-configurations
    server: ServerConfig = field(default_factory=ServerConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    jetstream: JetstreamConfig = field(default_factory=JetstreamConfig)
    cors: CORSConfig = field(default_factory=CORSConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    xai: XAIConfig = field(default_factory=XAIConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create configuration from environment variables."""
        return cls()

    def to_dict(self, include_secrets: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging."""
        return {
            "app_name": self.app_name,
            "version": self.version,
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "debug": self.server.debug,
            },
            "storage": {
                "upload_folder": str(self.storage.upload_folder),
                "output_folder": str(self.storage.output_folder),
                "runs_folder": str(self.storage.runs_folder),
                "max_content_length": self.storage.max_content_length,
            },
            "jetstream": self.jetstream.to_dict(mask_key=not include_secrets),
            "xai": {
                "enabled": self.xai.enabled,
                "api_url": self.xai.api_url,
                "model": self.xai.model,
            },
        }


# Global configuration instance (lazy loaded)
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = AppConfig.from_env()
    return _config


def reload_config() -> AppConfig:
    """Force reload configuration from environment."""
    global _config
    _config = AppConfig.from_env()
    return _config


# Convenience constants for direct imports
RUNS_DIR = get_config().storage.runs_folder