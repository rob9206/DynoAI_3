# JetDrive Data Ingestion Reliability Guide

## Overview

The data ingestion system provides comprehensive reliability features for all data sources including:
- **Dynoware** (JetDrive UDP multicast)
- **Innovate** (DLG-1/LC-2 wideband AFR)
- **PowerVision** (.pvlog files)
- **WP8** (WinPEP8 dyno runs)
- **CSV** data imports

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Data Sources                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ JetDrive │  │ Innovate │  │   CSV    │  │   WP8    │         │
│  │   UDP    │  │  Serial  │  │  Files   │  │  Files   │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│       │             │             │             │               │
│       ▼             ▼             ▼             ▼               │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              Data Adapters                            │       │
│  │  (Format conversion & normalization)                  │       │
│  └────────────────────────┬─────────────────────────────┘       │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              Validation Schemas                       │       │
│  │  (Type checking, range validation, sanitization)      │       │
│  └────────────────────────┬─────────────────────────────┘       │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              Ingestion Queue                          │       │
│  │  (Priority-based, persistent, dead-letter support)    │       │
│  └────────────────────────┬─────────────────────────────┘       │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              Base Ingestion Client                    │       │
│  │  (Retry logic, circuit breaker, health monitoring)    │       │
│  └──────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Validation Schemas (`api/services/ingestion/schemas.py`)

Comprehensive data validation for all sensor types:

```python
from api.services.ingestion.schemas import (
    DataSample,
    DynoDataPointSchema,
    JetDriveSampleSchema,
    InnovateSampleSchema,
    ValidationResult,
)

# Create a validated sample
sample = DataSample(
    timestamp_ms=1000,
    source="jetdrive",
    channel="rpm",
    value=3500.0
)

# Validate
result = sample.validate()
if not result.is_valid:
    for error in result.errors:
        print(f"Validation error: {error.message}")
```

#### Sensor Ranges

Pre-defined ranges for common sensors:

| Sensor | Min | Max | Warning Min | Warning Max |
|--------|-----|-----|-------------|-------------|
| RPM | 0 | 20,000 | 500 | 15,000 |
| AFR | 6.0 | 35.0 | 10.0 | 20.0 |
| MAP (kPa) | 0 | 300 | 20 | 250 |
| Horsepower | -50 | 2,000 | - | 1,000 |
| Torque (ft-lb) | -100 | 2,000 | - | 800 |
| TPS | 0 | 100 | - | - |
| IAT (°F) | -40 | 300 | 32 | 200 |

### 2. Configuration (`api/services/ingestion/config.py`)

Centralized configuration for all ingestion parameters:

```python
from api.services.ingestion.config import (
    IngestionConfig,
    get_ingestion_config,
    RetrySettings,
    CircuitBreakerSettings,
)

# Load configuration
config = get_ingestion_config()

# Access source-specific config
jetdrive_config = config.get_source_config("jetdrive")

# Custom retry settings
retry = RetrySettings(
    max_attempts=5,
    initial_delay_sec=0.5,
    max_delay_sec=30.0,
    exponential_base=2.0,
    jitter=True,
)
```

Configuration file: `config/ingestion.json`

### 3. Ingestion Queue (`api/services/ingestion/queue.py`)

Priority-based queue with persistence support:

```python
from api.services.ingestion.queue import (
    IngestionQueue,
    QueuePriority,
    QueueItem,
)
from api.services.ingestion.config import QueueSettings

# Create queue
settings = QueueSettings(
    max_size=10000,
    batch_size=100,
    persist_to_disk=True,
    persist_path="data/ingestion_queue",
)
queue = IngestionQueue(settings)

# Enqueue with priority
queue.enqueue(
    source="jetdrive",
    data={"rpm": 3500, "hp": 85},
    priority=QueuePriority.HIGH,
)

# Process batch
def processor(item: QueueItem) -> bool:
    # Process item
    return True  # Return True on success

queue.start_processing(processor, interval=1.0)
```

#### Priority Levels

| Priority | Value | Use Case |
|----------|-------|----------|
| CRITICAL | 0 | Safety-critical data |
| HIGH | 1 | Real-time sensor data |
| NORMAL | 2 | Standard data |
| LOW | 3 | Metadata, diagnostics |
| BATCH | 4 | Bulk imports |

### 4. Base Ingestion Client (`api/services/ingestion/base_client.py`)

Abstract base class with built-in reliability:

```python
from api.services.ingestion.base_client import (
    BaseIngestionClient,
    IngestionState,
    IngestionStats,
)

class MyDataClient(BaseIngestionClient):
    def _connect_impl(self) -> bool:
        # Implement connection logic
        return True
    
    def _disconnect_impl(self) -> None:
        # Implement disconnection logic
        pass
    
    def _read_impl(self) -> MyDataType | None:
        # Implement data reading
        return None
    
    def _validate_sample(self, sample) -> ValidationResult:
        # Validate received data
        return ValidationResult(is_valid=True)

# Usage
client = MyDataClient("my_source")
client.connect()  # Automatic retry on failure
client.start_reading()  # Background reading with error recovery
```

### 5. Data Adapters (`api/services/ingestion/adapters.py`)

Format conversion between data sources:

```python
from api.services.ingestion.adapters import (
    JetDriveAdapter,
    CSVAdapter,
    get_adapter_for_source,
    convert_to_standard,
)

# Auto-detect adapter
adapter = get_adapter_for_source(data)
if adapter:
    standard_data = adapter.convert(data)

# Parse CSV file
csv_adapter = CSVAdapter()
run = csv_adapter.parse_file("path/to/data.csv")
print(f"Peak HP: {run.peak_hp}")

# Aggregate JetDrive samples
jd_adapter = JetDriveAdapter()
data_points = jd_adapter.aggregate_samples(samples, time_window_ms=50)
```

## Error Handling

### Retry Logic

Automatic retry with exponential backoff:

```
Attempt 1: immediate
Attempt 2: wait 0.1s
Attempt 3: wait 0.2s (exponential)
... with jitter to prevent thundering herd
```

### Circuit Breaker

Prevents cascading failures:

```
CLOSED → Service working normally
  │
  ▼ (5 failures)
OPEN → Requests blocked for 60s
  │
  ▼ (timeout elapsed)
HALF_OPEN → Test requests
  │         │
  ▼         ▼
CLOSED   OPEN
(2 successes) (1 failure)
```

### Dead Letter Queue

Failed items after max retries go to dead letter queue:

```python
# Get dead letter items
dead_items = queue.get_dead_letter_items(limit=100)

# Retry a specific item
queue.retry_dead_letter("item_id")

# Clear all dead letters
queue.clear_dead_letter()
```

## Monitoring

### Health Checks

```python
# Client health check
health = client.health_check()
# Returns: {"healthy": True, "state": "connected", ...}

# Queue statistics
stats = queue.get_stats()
print(f"Processed: {stats.total_processed}")
print(f"Failed: {stats.total_failed}")
print(f"Drop rate: {stats.total_dropped / stats.total_enqueued * 100:.1f}%")
```

### Metrics

Available metrics:
- `samples_received` - Total samples received
- `samples_processed` - Successfully processed
- `samples_failed` - Validation failures
- `samples_dropped` - Queue overflow drops
- `avg_latency_ms` - Average processing latency
- `samples_per_second` - Processing rate
- `circuit_state` - Circuit breaker state
- `consecutive_errors` - Error streak count

## Configuration Reference

### `config/ingestion.json`

```json
{
  "global_enabled": true,
  "log_level": "INFO",
  
  "queue": {
    "max_size": 10000,
    "batch_size": 100,
    "flush_interval_sec": 5.0,
    "persist_to_disk": false
  },
  
  "default_retry": {
    "max_attempts": 3,
    "initial_delay_sec": 0.1,
    "max_delay_sec": 30.0,
    "exponential_base": 2.0,
    "jitter": true
  },
  
  "default_circuit_breaker": {
    "failure_threshold": 5,
    "success_threshold": 2,
    "timeout_sec": 60.0
  },
  
  "jetdrive": {
    "multicast_group": "224.0.2.10",
    "port": 22344,
    "discovery_timeout_sec": 3.0,
    "auto_reconnect": true
  },
  
  "innovate": {
    "baudrate": 19200,
    "device_type": "AUTO",
    "channels": [1, 2],
    "auto_reconnect": true
  }
}
```

## Adding New Data Sources

1. **Create Adapter** in `adapters.py`:
   ```python
   class MyAdapter(DataAdapter):
       source_name = "my_source"
       
       def can_handle(self, data) -> bool:
           # Detect if this adapter handles the data
           
       def convert(self, data) -> DynoDataPointSchema:
           # Convert to standard format
   ```

2. **Create Client** extending `BaseIngestionClient`:
   ```python
   class MyClient(BaseIngestionClient):
       def _connect_impl(self) -> bool: ...
       def _disconnect_impl(self) -> None: ...
       def _read_impl(self) -> MyData | None: ...
       def _validate_sample(self, sample) -> ValidationResult: ...
   ```

3. **Add Configuration** in `config.py`:
   ```python
   @dataclass
   class MySourceConfig:
       setting1: str = "default"
       ...
   ```

4. **Register Adapter**:
   ```python
   from api.services.ingestion.adapters import register_adapter
   register_adapter("my_source", MyAdapter())
   ```

5. **Add Tests** in `tests/test_ingestion/`

## Testing

Run the test suite:

```bash
# All ingestion tests
python -m pytest tests/test_ingestion/ -v

# Specific test file
python -m pytest tests/test_ingestion/test_schemas.py -v

# With coverage
python -m pytest tests/test_ingestion/ --cov=api/services/ingestion
```

## Performance Considerations

- **Queue Size**: Default 10,000 items. Increase for high-volume sources.
- **Batch Size**: Default 100. Smaller = lower latency, larger = higher throughput.
- **Validation**: Can be disabled for performance if data is trusted.
- **Persistence**: Adds disk I/O overhead. Enable only if crash recovery needed.

## Troubleshooting

### High Drop Rate

1. Increase queue size
2. Increase batch size
3. Check processor performance
4. Consider multiple processing threads

### Circuit Breaker Opening

1. Check underlying service health
2. Increase failure threshold
3. Check network connectivity
4. Review error logs for root cause

### Validation Failures

1. Check sensor ranges in `schemas.py`
2. Enable `sanitize_values` in config
3. Set `strict_mode: false` for lenient validation
4. Review `reject_nan` and `reject_inf` settings


