# Task 006: Rate Limiting

## Priority: LOW
## Estimated Effort: Low (30-60 minutes)
## Dependencies: None

---

## Objective
Add rate limiting to protect expensive endpoints (especially `/api/analyze` which handles file uploads) from abuse.

## Current State
- No rate limiting
- Any client can flood the API with requests
- File uploads consume disk space and CPU

## Target State
- Global rate limit for all endpoints
- Stricter limits for expensive operations (file upload)
- Configurable via environment variables
- Returns 429 Too Many Requests when exceeded

## Implementation

### 1. Install Dependencies
Add to `requirements.txt`:
```
Flask-Limiter>=3.5.0
```

### 2. Create `api/rate_limit.py`
```python
"""
DynoAI Rate Limiting Configuration.

Protects API endpoints from abuse with configurable rate limits.
"""

import os
from flask import Flask, jsonify, request, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from typing import Optional


def get_client_identifier() -> str:
    """
    Get client identifier for rate limiting.
    
    Uses X-Forwarded-For header if behind a proxy, otherwise remote address.
    Can be extended to use API keys for authenticated clients.
    """
    # Check for API key first (future enhancement)
    api_key = request.headers.get('X-API-Key')
    if api_key:
        return f"api_key:{api_key}"
    
    # Use forwarded address if behind proxy
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(',')[0].strip()
    
    return get_remote_address()


def init_rate_limiter(app: Flask) -> Limiter:
    """
    Initialize rate limiter with configuration from environment.
    
    Environment variables:
        RATE_LIMIT_ENABLED: "true" or "false" (default: "true")
        RATE_LIMIT_DEFAULT: Default limit (default: "100/minute")
        RATE_LIMIT_STORAGE: Storage backend URL (default: "memory://")
    """
    enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    default_limit = os.getenv("RATE_LIMIT_DEFAULT", "100/minute")
    storage_uri = os.getenv("RATE_LIMIT_STORAGE", "memory://")
    
    limiter = Limiter(
        key_func=get_client_identifier,
        app=app,
        default_limits=[default_limit] if enabled else [],
        storage_uri=storage_uri,
        strategy="fixed-window",
        headers_enabled=True,  # Add X-RateLimit-* headers
    )
    
    # Custom error handler for rate limit exceeded
    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        request_id = getattr(g, 'request_id', None)
        return jsonify({
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please slow down.",
                "request_id": request_id,
                "details": {
                    "retry_after": e.description
                }
            }
        }), 429
    
    return limiter


# Rate limit decorators for different endpoint types
class RateLimits:
    """Pre-defined rate limits for different endpoint types."""
    
    # Expensive operations (file upload, analysis)
    EXPENSIVE = "5/minute;20/hour"
    
    # Standard API calls
    STANDARD = "60/minute"
    
    # Read-only operations
    READ_ONLY = "120/minute"
    
    # Health checks (very permissive)
    HEALTH = "300/minute"
```

### 3. Update `api/app.py`
```python
from api.rate_limit import init_rate_limiter, RateLimits

# Initialize rate limiter after app creation
limiter = init_rate_limiter(app)

# Apply specific limits to endpoints
@app.route("/api/analyze", methods=["POST"])
@limiter.limit(RateLimits.EXPENSIVE)
@with_error_handling
def analyze():
    """Analyze uploaded CSV file (async)."""
    # ... existing implementation

@app.route("/api/runs", methods=["GET"])
@limiter.limit(RateLimits.READ_ONLY)
@with_error_handling
def list_runs():
    # ... existing implementation

@app.route("/api/health", methods=["GET"])
@limiter.limit(RateLimits.HEALTH)
def health_check():
    # ... existing implementation
```

### 4. Update `api/config.py`
```python
@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    enabled: bool = field(
        default_factory=lambda: os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    )
    default: str = field(
        default_factory=lambda: os.getenv("RATE_LIMIT_DEFAULT", "100/minute")
    )
    expensive: str = field(
        default_factory=lambda: os.getenv("RATE_LIMIT_EXPENSIVE", "5/minute;20/hour")
    )
    storage_uri: str = field(
        default_factory=lambda: os.getenv("RATE_LIMIT_STORAGE", "memory://")
    )
```

### 5. Update `.env.example`
```bash
# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_EXPENSIVE=5/minute;20/hour
RATE_LIMIT_STORAGE=memory://
# For production with Redis:
# RATE_LIMIT_STORAGE=redis://localhost:6379/0
```

## Response Headers

When rate limiting is enabled, responses include these headers:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1701789600
```

## Rate Limit Exceeded Response

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1701789600
Retry-After: 60

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please slow down.",
    "request_id": "abc123",
    "details": {
      "retry_after": "60 seconds"
    }
  }
}
```

## Endpoint Rate Limits

| Endpoint | Limit | Reason |
|----------|-------|--------|
| `POST /api/analyze` | 5/min, 20/hr | File upload is expensive |
| `GET /api/runs` | 120/min | Read-only, cheap |
| `GET /api/download/*` | 60/min | File download, moderate |
| `GET /api/health` | 300/min | Monitoring probes |
| Default | 100/min | General protection |

## Production Considerations

### Redis Backend (Recommended for Production)
```bash
# Install redis
pip install redis

# Configure storage
RATE_LIMIT_STORAGE=redis://redis:6379/0
```

### Docker Compose with Redis
```yaml
services:
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
  
  backend:
    environment:
      - RATE_LIMIT_STORAGE=redis://redis:6379/0
    depends_on:
      - redis

volumes:
  redis_data:
```

## Acceptance Criteria
- [ ] Rate limiting enabled by default
- [ ] `/api/analyze` has stricter limits (5/min)
- [ ] 429 response with proper error format
- [ ] Rate limit headers in responses
- [ ] Configurable via environment variables
- [ ] Disable option for development

## Files to Create/Modify
- Create `api/rate_limit.py`
- Update `api/app.py` - initialize limiter, apply to routes
- Update `api/config.py` - add RateLimitConfig
- Update `.env.example` - document rate limit env vars
- Update `requirements.txt` - add Flask-Limiter

## Testing
```bash
# Test rate limiting
for i in {1..10}; do curl -s http://localhost:5000/api/health | jq .status; done

# Should see "ok" for first few, then rate limit error
```

