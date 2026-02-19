"""Services module for DynoAI API."""

from .progress_broadcaster import ProgressBroadcaster
from .run_manager import RunManager

# JetDrive validation (optional import to avoid circular dependencies)
__all__ = ["RunManager", "ProgressBroadcaster"]

try:
    from .jetdrive_validation import (  # noqa: F401
        ChannelHealth,
        ChannelMetrics,
        FrameStats,
        JetDriveDataValidator,
        get_validator,
    )

    __all__.extend(
        [
            "ChannelHealth",
            "ChannelMetrics",
            "FrameStats",
            "JetDriveDataValidator",
            "get_validator",
        ]
    )
except ImportError:
    pass
