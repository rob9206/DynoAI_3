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

from .schemas import (
    # Base schemas
    DataSample,
    IngestionError,
    ValidationError,
    # JetDrive schemas
    JetDriveSampleSchema,
    JetDriveChannelSchema,
    JetDriveProviderSchema,
    # Innovate schemas
    InnovateSampleSchema,
    # Dyno data schemas
    DynoDataPointSchema,
    DynoRunSchema,
    # Validation results
    ValidationResult,
)

from .config import (
    IngestionConfig,
    get_ingestion_config,
    DataSourceConfig,
    RetrySettings,
    CircuitBreakerSettings,
    QueueSettings,
)

from .base_client import (
    BaseIngestionClient,
    IngestionState,
    IngestionStats,
)

from .queue import (
    IngestionQueue,
    QueueItem,
    QueuePriority,
)

from .adapters import (
    DataAdapter,
    JetDriveAdapter,
    InnovateAdapter,
    CSVAdapter,
    WP8Adapter,
    get_adapter_for_source,
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


