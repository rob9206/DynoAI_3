"""
DynoAI Data Ingestion Package

Comprehensive data ingestion system with:
- Robust error handling and retry logic
- Data validation schemas for all sources
- Connection resilience with circuit breakers
- Queue-based ingestion for offline resilience
- Format adapters and auto-detection
- Structured logging and monitoring
"""

from .adapters import (
    CSVAdapter,
    DataAdapter,
    InnovateAdapter,
    JetDriveAdapter,
    WP8Adapter,
    get_adapter_for_source,
)
from .base_client import (
    BaseIngestionClient,
    IngestionState,
    IngestionStats,
)
from .config import (
    CircuitBreakerSettings,
    DataSourceConfig,
    IngestionConfig,
    QueueSettings,
    RetrySettings,
    get_ingestion_config,
)
from .queue import (
    IngestionQueue,
    QueueItem,
    QueuePriority,
)
from .schemas import (  # Base schemas; JetDrive schemas; Innovate schemas; Dyno data schemas; Validation results
    DataSample,
    DynoDataPointSchema,
    DynoRunSchema,
    IngestionError,
    InnovateSampleSchema,
    JetDriveChannelSchema,
    JetDriveProviderSchema,
    JetDriveSampleSchema,
    ValidationError,
    ValidationResult,
)

__all__ = [
    # Schemas
    "DataSample",
    "IngestionError",
    "ValidationError",
    "JetDriveSampleSchema",
    "JetDriveChannelSchema",
    "JetDriveProviderSchema",
    "InnovateSampleSchema",
    "DynoDataPointSchema",
    "DynoRunSchema",
    "ValidationResult",
    # Config
    "IngestionConfig",
    "get_ingestion_config",
    "DataSourceConfig",
    "RetrySettings",
    "CircuitBreakerSettings",
    "QueueSettings",
    # Base client
    "BaseIngestionClient",
    "IngestionState",
    "IngestionStats",
    # Queue
    "IngestionQueue",
    "QueueItem",
    "QueuePriority",
    # Adapters
    "DataAdapter",
    "JetDriveAdapter",
    "InnovateAdapter",
    "CSVAdapter",
    "WP8Adapter",
    "get_adapter_for_source",
]
