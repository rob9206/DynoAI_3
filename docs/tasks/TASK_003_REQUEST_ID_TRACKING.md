# Task 003: Request ID Tracking

## Priority: MEDIUM
## Estimated Effort: Low (30-60 minutes)
## Dependencies: Task 002 (Structured Logging) - recommended but not required

---

## Objective
Add unique request IDs to every API request for end-to-end traceability across logs, errors, and responses.

## Current State
- No request tracking
- Difficult to correlate logs from the same request
- Error responses don't include tracking info

## Target State
- Every request gets a unique ID (UUID or shorter)
- ID flows through all logs for that request
- ID returned in response headers (`X-Request-ID`)
- ID included in error responses
- Supports client-provided IDs (pass-through)

## Implementation

### 1. Create Request ID Middleware
Add to `api/middleware.py` (new file):

```python
"""
DynoAI Request Middleware.

Provides request ID tracking and other cross-cutting concerns.
"""

import uuid
from flask import Flask, g, request, Response
from typing import Optional


def generate_request_id() -> str:
    """Generate a short, unique request ID."""
    return uuid.uuid4().hex[:12]  # 12 chars is enough for tracing


def init_request_id_middleware(app: Flask) -> None:
    """
    Initialize request ID middleware.
    
    - Generates or accepts request ID for each request
    - Stores in Flask's g object for access during request
    - Adds to response headers
    """
    
    @app.before_request
    def set_request_id() -> None:
        """Set request ID from header or generate new one."""
        # Accept client-provided ID or generate new one
        request_id = request.headers.get('X-Request-ID')
        if not request_id:
            request_id = generate_request_id()
        g.request_id = request_id
    
    @app.after_request
    def add_request_id_header(response: Response) -> Response:
        """Add request ID to response headers."""
        request_id = getattr(g, 'request_id', None)
        if request_id:
            response.headers['X-Request-ID'] = request_id
        return response


def get_request_id() -> Optional[str]:
    """Get current request ID, if available."""
    return getattr(g, 'request_id', None)
```

### 2. Update `api/app.py`
```python
# After app initialization
from api.middleware import init_request_id_middleware

app = Flask(__name__)

# Initialize middleware
init_request_id_middleware(app)
```

### 3. Update `api/errors.py`
Include request ID in error responses:

```python
from flask import g

def error_response(
    message: str,
    status_code: int = 500,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Tuple[Response, int]:
    """Create a standardized error response."""
    response = {
        "error": {
            "code": error_code or f"ERR_{status_code}",
            "message": message,
        }
    }
    
    # Add request ID for tracing
    request_id = getattr(g, 'request_id', None)
    if request_id:
        response["error"]["request_id"] = request_id
    
    if details:
        response["error"]["details"] = details
    
    return jsonify(response), status_code
```

### 4. Update Success Responses (Optional)
For consistency, include request ID in success responses too:

```python
def success_response(data: Dict[str, Any], status_code: int = 200) -> Tuple[Response, int]:
    """Create a standardized success response with request ID."""
    response = {
        "data": data,
        "request_id": getattr(g, 'request_id', None)
    }
    return jsonify(response), status_code
```

## Example Flow

### Request
```http
POST /api/analyze HTTP/1.1
Content-Type: multipart/form-data
X-Request-ID: my-custom-id-123  # Optional client-provided ID
```

### Response (Success)
```http
HTTP/1.1 200 OK
X-Request-ID: my-custom-id-123

{
  "run_id": "abc123",
  "status": "processing",
  "request_id": "my-custom-id-123"
}
```

### Response (Error)
```http
HTTP/1.1 400 Bad Request
X-Request-ID: a1b2c3d4e5f6

{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "No file provided",
    "request_id": "a1b2c3d4e5f6"
  }
}
```

### Logs
```
10:23:45.123 INFO [a1b2c3d4e5f6] api.app: POST /api/analyze
10:23:45.124 ERROR [a1b2c3d4e5f6] api.app: Validation error - No file provided
```

## Acceptance Criteria
- [ ] Every request gets a unique ID
- [ ] ID returned in `X-Request-ID` response header
- [ ] ID included in error responses
- [ ] Client can provide own ID via `X-Request-ID` header
- [ ] ID available in logs (via `g.request_id`)
- [ ] ID is 8-12 characters (short but unique enough)

## Files to Create/Modify
- Create `api/middleware.py`
- Update `api/app.py` - initialize middleware
- Update `api/errors.py` - include request ID in responses

## Testing
```bash
# Test auto-generated ID
curl -i http://localhost:5000/api/health
# Should see X-Request-ID in response headers

# Test client-provided ID
curl -i -H "X-Request-ID: my-trace-123" http://localhost:5000/api/health
# Should see X-Request-ID: my-trace-123 in response
```

