# TASK-009: Prometheus Metrics Integration

**Status:** 🟡 Ready for Work  
**Priority:** Medium  
**Estimated Effort:** 2-3 hours  
**Dependencies:** None

## Objective

Add Prometheus metrics endpoint for monitoring and observability in production environments.

## Deliverables

### 1. Add Dependencies

```bash
# Add to requirements.txt
prometheus-flask-exporter>=0.23.0
```

### 2. Create Metrics Module (`api/metrics.py`)

```python
"""Prometheus metrics for DynoAI API."""

import os
from typing import Optional

from flask import Flask
from prometheus_flask_exporter import PrometheusMetrics


_metrics: Optional[PrometheusMetrics] = None


def init_metrics(app: Flask) -> Optional[PrometheusMetrics]:
    """Initialize Prometheus metrics."""
    global _metrics
    
    enabled = os.getenv("METRICS_ENABLED", "true").lower() == "true"
    if not enabled:
        return None
    
    _metrics = PrometheusMetrics(
        app,
        path="/metrics",
        export_defaults=True,
        defaults_prefix="dynoai",
    )
    
    # Custom metrics
    _metrics.info(
        "app_info",
        "DynoAI application info",
        version="1.2.0",
    )
    
    return _metrics


def get_metrics() -> Optional[PrometheusMetrics]:
    """Get metrics instance."""
    return _metrics


# Custom metric decorators for business metrics
def track_analysis_duration():
    """Decorator to track analysis duration."""
    if _metrics is None:
        return lambda f: f
    
    return _metrics.histogram(
        "analysis_duration_seconds",
        "Time spent on analysis",
        labels={"status": lambda r: "success" if r.status_code == 200 else "error"},
    )


def track_file_upload_size():
    """Decorator to track uploaded file sizes."""
    if _metrics is None:
        return lambda f: f
    
    return _metrics.histogram(
        "file_upload_bytes",
        "Size of uploaded files",
        buckets=[1024, 10240, 102400, 1048576, 10485760, 52428800],
    )
```

### 3. Custom Business Metrics

```python
# Track important business events
analysis_total = Counter(
    "dynoai_analysis_total",
    "Total number of analyses run",
    ["status", "source"]
)

jetstream_runs_total = Counter(
    "dynoai_jetstream_runs_total", 
    "Total Jetstream runs processed",
    ["status"]
)

ve_corrections_applied = Histogram(
    "dynoai_ve_corrections_count",
    "Number of VE corrections per analysis",
    buckets=[0, 10, 50, 100, 500, 1000]
)
```

### 4. Integrate with App

```python
# In app.py
from api.metrics import init_metrics

app = Flask(__name__)
metrics = init_metrics(app)
```

### 5. Add Environment Variables

```bash
METRICS_ENABLED=true
METRICS_PATH=/metrics
```

## Acceptance Criteria

- [ ] `/metrics` endpoint returns Prometheus format
- [ ] Default Flask metrics exported
- [ ] Custom DynoAI metrics defined
- [ ] Analysis duration tracked
- [ ] Upload size tracked
- [ ] Jetstream run counts tracked
- [ ] Metrics can be disabled via env var
- [ ] Grafana dashboard JSON exported

## Files to Create/Modify

- `/api/metrics.py` (new)
- `/api/app.py` (modify)
- `/requirements.txt` (modify)
- `/api/requirements.txt` (modify)
- `/grafana/dynoai-dashboard.json` (new - optional)

## Example Output

```
# HELP dynoai_request_duration_seconds Request duration
# TYPE dynoai_request_duration_seconds histogram
dynoai_request_duration_seconds_bucket{le="0.005",method="GET",path="/api/health"} 150
dynoai_request_duration_seconds_bucket{le="0.01",method="GET",path="/api/health"} 150

# HELP dynoai_analysis_total Total analyses
# TYPE dynoai_analysis_total counter
dynoai_analysis_total{status="success",source="upload"} 42
dynoai_analysis_total{status="success",source="jetstream"} 128

# HELP dynoai_app_info Application info
# TYPE dynoai_app_info gauge
dynoai_app_info{version="1.2.0"} 1
```

## Testing

```bash
# Verify metrics endpoint
curl http://localhost:5001/metrics | grep dynoai

# Run load test and check metrics
ab -n 100 -c 10 http://localhost:5001/api/health
curl http://localhost:5001/metrics | grep request_duration
```

