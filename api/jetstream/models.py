"""Data models for Jetstream integration."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class RunStatus(str, Enum):
    """Status of a run through the processing pipeline."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    CONVERTING = "converting"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class JetstreamRun:
    """Represents a run from the Jetstream API."""

    run_id: str
    timestamp: str
    vehicle: Optional[str] = None
    dyno_type: Optional[str] = None
    duration_seconds: Optional[int] = None
    data_points: Optional[int] = None
    processed: bool = False


@dataclass
class JetstreamRunMetadata:
    """Detailed metadata for a Jetstream run."""

    run_id: str
    timestamp: str
    vehicle: Optional[str] = None
    dyno_type: Optional[str] = None
    engine_type: Optional[str] = None
    ambient_temp_f: Optional[float] = None
    ambient_pressure_inhg: Optional[float] = None
    humidity_percent: Optional[float] = None
    duration_seconds: Optional[int] = None
    data_points: Optional[int] = None
    peak_hp: Optional[float] = None
    peak_torque: Optional[float] = None
    raw_data_url: Optional[str] = None
    processed: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunError:
    """Error information for a failed run."""

    stage: str
    code: str
    message: str


@dataclass
class RunState:
    """State of a run in the DynoAI system."""

    run_id: str
    status: RunStatus
    source: str  # 'jetstream' or 'manual_upload'
    created_at: str
    updated_at: str
    jetstream_id: Optional[str] = None
    current_stage: Optional[str] = None
    progress_percent: Optional[int] = None
    error: Optional[RunError] = None
    results_summary: Optional[Dict[str, Any]] = None
    files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "run_id": self.run_id,
            "status": (
                self.status.value if isinstance(self.status, RunStatus) else self.status
            ),
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "jetstream_id": self.jetstream_id,
            "current_stage": self.current_stage,
            "progress_percent": self.progress_percent,
            "files": self.files,
        }
        if self.error:
            result["error"] = {
                "stage": self.error.stage,
                "code": self.error.code,
                "message": self.error.message,
            }
        if self.results_summary:
            result["results_summary"] = self.results_summary
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunState":
        """Create from dictionary."""
        error = None
        if data.get("error"):
            error = RunError(
                stage=data["error"]["stage"],
                code=data["error"]["code"],
                message=data["error"]["message"],
            )
        return cls(
            run_id=data["run_id"],
            status=(
                RunStatus(data["status"])
                if isinstance(data["status"], str)
                else data["status"]
            ),
            source=data["source"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            jetstream_id=data.get("jetstream_id"),
            current_stage=data.get("current_stage"),
            progress_percent=data.get("progress_percent"),
            error=error,
            results_summary=data.get("results_summary"),
            files=data.get("files", []),
        )


@dataclass
class TuningOptions:
    """Tuning options for run processing."""

    # Decel Fuel Management
    decel_management: bool = False
    decel_severity: str = "medium"  # low, medium, high
    decel_rpm_min: int = 1500
    decel_rpm_max: int = 5500
    
    # Per-Cylinder Auto-Balancing
    balance_cylinders: bool = False
    balance_mode: str = "equalize"  # equalize, match_front, match_rear
    balance_max_correction: float = 3.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "decel_management": self.decel_management,
            "decel_severity": self.decel_severity,
            "decel_rpm_min": self.decel_rpm_min,
            "decel_rpm_max": self.decel_rpm_max,
            "balance_cylinders": self.balance_cylinders,
            "balance_mode": self.balance_mode,
            "balance_max_correction": self.balance_max_correction,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TuningOptions":
        """Create from dictionary."""
        return cls(
            decel_management=data.get("decel_management", False),
            decel_severity=data.get("decel_severity", "medium"),
            decel_rpm_min=data.get("decel_rpm_min", 1500),
            decel_rpm_max=data.get("decel_rpm_max", 5500),
            balance_cylinders=data.get("balance_cylinders", False),
            balance_mode=data.get("balance_mode", "equalize"),
            balance_max_correction=data.get("balance_max_correction", 3.0),
        )


@dataclass
class JetstreamConfig:
    """Configuration for Jetstream integration."""

    api_url: str
    api_key: str
    poll_interval_seconds: int = 30
    auto_process: bool = True
    enabled: bool = False
    tuning_options: TuningOptions = field(default_factory=TuningOptions)

    def to_dict(self, mask_key: bool = True) -> Dict[str, Any]:
        """Convert to dictionary, optionally masking the API key."""
        return {
            "api_url": self.api_url,
            "api_key": self._mask_key() if mask_key else self.api_key,
            "poll_interval_seconds": self.poll_interval_seconds,
            "auto_process": self.auto_process,
            "enabled": self.enabled,
            "tuning_options": self.tuning_options.to_dict(),
        }

    def _mask_key(self) -> str:
        """Mask the API key for safe display."""
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "*" * len(self.api_key)
        return self.api_key[:4] + "*" * (len(self.api_key) - 8) + self.api_key[-4:]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JetstreamConfig":
        """Create from dictionary."""
        tuning_data = data.get("tuning_options", {})
        return cls(
            api_url=data.get("api_url", ""),
            api_key=data.get("api_key", ""),
            poll_interval_seconds=data.get("poll_interval_seconds", 30),
            auto_process=data.get("auto_process", True),
            enabled=data.get("enabled", False),
            tuning_options=TuningOptions.from_dict(tuning_data),
        )


@dataclass
class PollerStatus:
    """Status of the Jetstream poller."""

    connected: bool
    last_poll: Optional[str] = None
    next_poll: Optional[str] = None
    pending_runs: int = 0
    processing_run: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "connected": self.connected,
            "last_poll": self.last_poll,
            "next_poll": self.next_poll,
            "pending_runs": self.pending_runs,
            "processing_run": self.processing_run,
            "error": self.error,
        }
