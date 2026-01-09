"""
DynoAI API Configuration Module.

Centralizes all configuration settings with environment variable support
and sensible defaults for development and production environments.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from dynoai.version import __version__ as DYNOAI_VERSION


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
        default_factory=lambda: Path(os.environ.get("DYNOAI_UPLOAD_DIR", "data/uploads"))
    )
    output_folder: Path = field(
        default_factory=lambda: Path(os.environ.get("DYNOAI_OUTPUT_DIR", "data/outputs"))
    )
    runs_folder: Path = field(
        default_factory=lambda: Path(os.environ.get("DYNOAI_RUNS_DIR", "data/runs"))
    )
    public_export_folder: Path = field(
        default_factory=lambda: Path(os.environ.get("DYNOAI_PUBLIC_EXPORT_DIR", "data/public_export"))
    )
    max_content_length: int = field(
        default_factory=lambda: _get_int_env("DYNOAI_MAX_UPLOAD_MB", 50) * 1024 * 1024
    )
    allowed_extensions: frozenset = field(
        default_factory=lambda: frozenset({"csv", "txt"})
    )

    def __post_init__(self) -> None:
        """Ensure storage directories exist."""
        self.upload_folder.mkdir(parents=True, exist_ok=True)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.runs_folder.mkdir(parents=True, exist_ok=True)
        self.public_export_folder.mkdir(parents=True, exist_ok=True)


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

    # Per-Cylinder Auto-Balancing
    balance_cylinders: bool = field(
        default_factory=lambda: _get_bool_env("DYNOAI_BALANCE_CYLINDERS", False)
    )
    balance_mode: str = field(
        default_factory=lambda: os.environ.get("DYNOAI_BALANCE_MODE", "equalize")
    )
    balance_max_correction: float = field(
        default_factory=lambda: float(
            os.environ.get("DYNOAI_BALANCE_MAX_CORRECTION", "3.0")
        )
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decel_management": self.decel_management,
            "decel_severity": self.decel_severity,
            "decel_rpm_min": self.decel_rpm_min,
            "decel_rpm_max": self.decel_rpm_max,
            "balance_cylinders": self.balance_cylinders,
            "balance_mode": self.balance_mode,
            "balance_max_correction": self.balance_max_correction,
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
class LoggingConfig:
    """Logging configuration."""

    level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))
    format: str = field(
        default_factory=lambda: os.environ.get("LOG_FORMAT", "development")
    )
    # "development" = human-readable with colors
    # "production" = JSON structured logs


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    enabled: bool = field(
        default_factory=lambda: os.environ.get("RATE_LIMIT_ENABLED", "true").lower()
        == "true"
    )
    default: str = field(
        default_factory=lambda: os.environ.get("RATE_LIMIT_DEFAULT", "1200/minute")
    )  # 1200/min allows live data polling at 100ms intervals (10/sec)
    expensive: str = field(
        default_factory=lambda: os.environ.get(
            "RATE_LIMIT_EXPENSIVE", "5/minute;20/hour"
        )
    )
    storage_uri: str = field(
        default_factory=lambda: os.environ.get("RATE_LIMIT_STORAGE", "memory://")
    )


@dataclass
class DrumConfig:
    """Individual dyno drum configuration."""

    serial_number: str = ""
    mass_kg: float = 0.0  # Drum mass in kg (Dynoware calibration factor)
    retarder_mass_kg: float = 0.0  # Retarder/brake mass
    circumference_ft: float = 0.0  # Drum circumference in feet
    num_tabs: int = 1  # Number of pickup tabs

    @property
    def radius_ft(self) -> float:
        """Calculate drum radius from circumference."""
        import math

        if self.circumference_ft <= 0:
            return 0.0
        return self.circumference_ft / (2 * math.pi)

    @property
    def radius_m(self) -> float:
        """Drum radius in meters."""
        return self.radius_ft * 0.3048

    @property
    def total_mass_kg(self) -> float:
        """Total rotating mass including retarder."""
        return self.mass_kg + self.retarder_mass_kg

    @property
    def rotational_inertia_kgm2(self) -> float:
        """
        Calculate rotational inertia (I = 0.5 × m × r²) for solid cylinder.
        Used for inertia-based power calculations.
        """
        if self.radius_m <= 0 or self.total_mass_kg <= 0:
            return 0.0
        return 0.5 * self.total_mass_kg * (self.radius_m**2)

    @property
    def rotational_inertia_lbft2(self) -> float:
        """Rotational inertia in lb·ft² (for compatibility with simulator)."""
        # 1 kg·m² = 23.73 lb·ft²
        return self.rotational_inertia_kgm2 * 23.73

    def is_configured(self) -> bool:
        """Check if drum has valid configuration."""
        return self.mass_kg > 0 and self.circumference_ft > 0


@dataclass
class DynoConfig:
    """
    Dynoware RT hardware configuration.

    Stores actual drum specifications from the connected dynamometer
    for accurate power calculations. Values should match the Device
    Information dialog in Dynoware RT software.

    Power calculation for inertia dyno:
        HP = (I × α × ω) / 5252
    Where:
        I = rotational inertia (lb·ft²)
        α = angular acceleration (rad/s²)
        ω = angular velocity (rad/s)
    """

    # Dyno identification
    model: str = field(
        default_factory=lambda: os.environ.get("DYNO_MODEL", "Dynoware RT-150")
    )
    serial_number: str = field(
        default_factory=lambda: os.environ.get("DYNO_SERIAL", "RT00220413")
    )
    location: str = field(
        default_factory=lambda: os.environ.get("DYNO_LOCATION", "Dawson Dynamics")
    )

    # Network configuration
    ip_address: str = field(
        default_factory=lambda: os.environ.get("DYNO_IP", "192.168.1.115")
    )
    jetdrive_port: int = field(
        default_factory=lambda: _get_int_env("DYNO_JETDRIVE_PORT", 22344)
    )

    # Drum 1 configuration (primary/front drum)
    # Values from Dynoware RT Device Information > Drum Information
    drum1_serial: str = field(
        default_factory=lambda: os.environ.get("DYNO_DRUM1_SERIAL", "1000588")
    )
    drum1_mass_kg: float = field(
        default_factory=lambda: float(os.environ.get("DYNO_DRUM1_MASS_KG", "14.121"))
    )
    drum1_retarder_mass_kg: float = field(
        default_factory=lambda: float(
            os.environ.get("DYNO_DRUM1_RETARDER_MASS_KG", "0.0")
        )
    )
    drum1_circumference_ft: float = field(
        default_factory=lambda: float(
            os.environ.get("DYNO_DRUM1_CIRCUMFERENCE_FT", "4.673")
        )
    )
    drum1_tabs: int = field(default_factory=lambda: _get_int_env("DYNO_DRUM1_TABS", 1))

    # Drum 2 configuration (secondary/rear drum, if equipped)
    drum2_serial: str = field(
        default_factory=lambda: os.environ.get("DYNO_DRUM2_SERIAL", "")
    )
    drum2_mass_kg: float = field(
        default_factory=lambda: float(os.environ.get("DYNO_DRUM2_MASS_KG", "0.0"))
    )
    drum2_retarder_mass_kg: float = field(
        default_factory=lambda: float(
            os.environ.get("DYNO_DRUM2_RETARDER_MASS_KG", "0.0")
        )
    )
    drum2_circumference_ft: float = field(
        default_factory=lambda: float(
            os.environ.get("DYNO_DRUM2_CIRCUMFERENCE_FT", "0.0")
        )
    )
    drum2_tabs: int = field(default_factory=lambda: _get_int_env("DYNO_DRUM2_TABS", 0))

    # Firmware/hardware info
    firmware_version: str = field(
        default_factory=lambda: os.environ.get("DYNO_FIRMWARE", "2.1.7034.17067")
    )
    atmo_version: str = field(
        default_factory=lambda: os.environ.get("DYNO_ATMO_VERSION", "1.1")
    )
    num_modules: int = field(
        default_factory=lambda: _get_int_env("DYNO_NUM_MODULES", 4)
    )

    @property
    def drum1(self) -> DrumConfig:
        """Get Drum 1 configuration object."""
        return DrumConfig(
            serial_number=self.drum1_serial,
            mass_kg=self.drum1_mass_kg,
            retarder_mass_kg=self.drum1_retarder_mass_kg,
            circumference_ft=self.drum1_circumference_ft,
            num_tabs=self.drum1_tabs,
        )

    @property
    def drum2(self) -> DrumConfig:
        """Get Drum 2 configuration object."""
        return DrumConfig(
            serial_number=self.drum2_serial,
            mass_kg=self.drum2_mass_kg,
            retarder_mass_kg=self.drum2_retarder_mass_kg,
            circumference_ft=self.drum2_circumference_ft,
            num_tabs=self.drum2_tabs,
        )

    def calculate_hp_from_force(self, force_lbs: float, rpm: float) -> float:
        """
        Calculate horsepower from drum force and RPM.

        HP = (Force × Drum Surface Velocity) / 550
           = (Force × π × Circumference × RPM) / (60 × 550)
           = (Force × Circumference × RPM) / 10504.2

        Args:
            force_lbs: Force measured on drum (lbs)
            rpm: Drum RPM

        Returns:
            Calculated horsepower
        """
        if rpm <= 0 or force_lbs <= 0:
            return 0.0

        # Surface velocity = circumference × RPM / 60 (ft/s)
        surface_velocity_fps = self.drum1_circumference_ft * rpm / 60.0

        # Power = Force × Velocity (ft-lbs/s)
        # 1 HP = 550 ft-lbs/s
        hp = (force_lbs * surface_velocity_fps) / 550.0

        return hp

    def calculate_torque_from_force(self, force_lbs: float) -> float:
        """
        Calculate torque from drum force.

        Torque = Force × Radius

        Args:
            force_lbs: Force measured on drum (lbs)

        Returns:
            Calculated torque in ft-lbs
        """
        return force_lbs * self.drum1.radius_ft

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "model": self.model,
            "serial_number": self.serial_number,
            "location": self.location,
            "ip_address": self.ip_address,
            "jetdrive_port": self.jetdrive_port,
            "firmware_version": self.firmware_version,
            "atmo_version": self.atmo_version,
            "num_modules": self.num_modules,
            "drum1": {
                "serial_number": self.drum1_serial,
                "mass_kg": self.drum1_mass_kg,
                "retarder_mass_kg": self.drum1_retarder_mass_kg,
                "circumference_ft": self.drum1_circumference_ft,
                "num_tabs": self.drum1_tabs,
                "radius_ft": self.drum1.radius_ft,
                "inertia_lbft2": self.drum1.rotational_inertia_lbft2,
                "configured": self.drum1.is_configured(),
            },
            "drum2": {
                "serial_number": self.drum2_serial,
                "mass_kg": self.drum2_mass_kg,
                "circumference_ft": self.drum2_circumference_ft,
                "configured": self.drum2.is_configured(),
            },
        }


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
    version: str = DYNOAI_VERSION

    # Sub-configurations
    server: ServerConfig = field(default_factory=ServerConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    jetstream: JetstreamConfig = field(default_factory=JetstreamConfig)
    cors: CORSConfig = field(default_factory=CORSConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    xai: XAIConfig = field(default_factory=XAIConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    dyno: DynoConfig = field(default_factory=DynoConfig)

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
                "public_export_folder": str(self.storage.public_export_folder),
                "max_content_length": self.storage.max_content_length,
            },
            "jetstream": self.jetstream.to_dict(mask_key=not include_secrets),
            "xai": {
                "enabled": self.xai.enabled,
                "api_url": self.xai.api_url,
                "model": self.xai.model,
            },
            "dyno": self.dyno.to_dict(),
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
