# Task 002: Structured Logging

## Priority: HIGH
## Estimated Effort: Low (1-2 hours)
## Dependencies: None

---

## Objective
Replace basic `print()` statements and simple logging with JSON-structured logs for better debugging, monitoring, and log aggregation.

## Current State
- Mix of `print()` statements and `logging.warning()`
- No consistent log format
- No request context in logs
- Difficult to parse/aggregate in production

## Target State
- All logs in JSON format
- Consistent fields: timestamp, level, message, request_id, module
- Easy integration with ELK, CloudWatch, Datadog, etc.
- Development mode: human-readable; Production mode: JSON

## Implementation

### 1. Create `api/logging_config.py`
```python
"""
DynoAI Structured Logging Configuration.

Provides JSON-formatted logs for production and human-readable logs for development.
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import json
from flask import g, has_request_context, request

class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add request context if available
        if has_request_context():
            log_data["request_id"] = getattr(g, 'request_id', None)
            log_data["method"] = request.method
            log_data["path"] = request.path
            log_data["remote_addr"] = request.remote_addr
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'extra_data'):
            log_data["extra"] = record.extra_data
        
        return json.dumps(log_data)


class DevelopmentFormatter(logging.Formatter):
    """Human-readable formatter for development."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, '')
        
        # Add request ID if available
        request_id = ""
        if has_request_context():
            rid = getattr(g, 'request_id', None)
            if rid:
                request_id = f"[{rid[:8]}] "
        
        timestamp = datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]
        
        return (
            f"{color}{timestamp} {record.levelname:8}{self.RESET} "
            f"{request_id}{record.name}: {record.getMessage()}"
        )


def setup_logging(app_env: str = "development") -> None:
    """
    Configure logging for the application.
    
    Args:
        app_env: "development" or "production"
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    
    if app_env == "production":
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
```

### 2. Update `api/app.py`
```python
# At the top, after imports
from api.logging_config import setup_logging, get_logger

# Initialize logging based on environment
setup_logging(os.getenv("FLASK_ENV", "development"))

logger = get_logger(__name__)

# Replace print() statements with logger calls:
# Before: print(f"[>] Saving uploaded file to: {upload_path}")
# After:  logger.info("Saving uploaded file", extra={'extra_data': {'path': str(upload_path)}})
```

### 3. Replace All print() Statements
Search and replace pattern:
```python
# Before
print(f"[>] Saving uploaded file to: {upload_path}")
print(f"[+] File saved successfully ({file_size} bytes)")
print(f"[!] Analysis failed: {str(e)}")

# After
logger.info("Saving uploaded file", extra={'extra_data': {'path': str(upload_path)}})
logger.info("File saved successfully", extra={'extra_data': {'size_bytes': file_size}})
logger.error("Analysis failed", extra={'extra_data': {'error': str(e)}})
```

### 4. Add to `api/config.py`
```python
@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    format: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "development"))
    # "development" = human-readable, "production" = JSON
```

## Example Output

### Development Mode
```
10:23:45.123 INFO     [abc12def] api.app: Saving uploaded file
10:23:45.456 INFO     [abc12def] api.app: File saved successfully
10:23:46.789 INFO     [abc12def] api.app: Analysis started
```

### Production Mode (JSON)
```json
{"timestamp":"2025-12-05T15:23:45.123Z","level":"INFO","logger":"api.app","message":"Saving uploaded file","request_id":"abc12def-1234-5678","method":"POST","path":"/api/analyze","extra":{"path":"/uploads/abc123/file.csv"}}
```

## Acceptance Criteria
- [ ] All `print()` statements replaced with logger calls
- [ ] JSON logging in production mode
- [ ] Human-readable logging in development mode
- [ ] Request context (ID, path, method) included in logs
- [ ] No breaking changes to existing functionality
- [ ] Update `.env.example` with `LOG_LEVEL` and `LOG_FORMAT`

## Files to Modify
- Create `api/logging_config.py`
- Update `api/app.py` - replace prints, initialize logging
- Update `api/config.py` - add LoggingConfig
- Update `api/errors.py` - use structured logging
- Update `.env.example` - document new env vars

## Testing
```bash
# Development mode
FLASK_ENV=development python -m api.app

# Production mode
FLASK_ENV=production python -m api.app
```

