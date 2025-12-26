# TASK-008: API Key Authentication

**Status:** 🟡 Ready for Work  
**Priority:** High  
**Estimated Effort:** 2-3 hours  
**Dependencies:** None

## Objective

Implement API key authentication to protect endpoints from unauthorized access.

## Deliverables

### 1. Create Authentication Module (`api/auth.py`)

```python
"""API Key Authentication for DynoAI."""

import os
import hashlib
import secrets
from functools import wraps
from typing import Optional

from flask import request, g, jsonify


class APIKeyAuth:
    """API Key authentication handler."""
    
    def __init__(self):
        self.enabled = os.getenv("API_AUTH_ENABLED", "false").lower() == "true"
        self._valid_keys = self._load_api_keys()
    
    def _load_api_keys(self) -> set:
        """Load valid API keys from environment or file."""
        keys = set()
        
        # Load from environment (comma-separated)
        env_keys = os.getenv("API_KEYS", "")
        if env_keys:
            keys.update(k.strip() for k in env_keys.split(",") if k.strip())
        
        # Load from file if exists
        keys_file = os.getenv("API_KEYS_FILE", "")
        if keys_file and os.path.exists(keys_file):
            with open(keys_file) as f:
                keys.update(line.strip() for line in f if line.strip())
        
        return keys
    
    def validate_key(self, api_key: str) -> bool:
        """Validate an API key."""
        if not self.enabled:
            return True
        return api_key in self._valid_keys
    
    def generate_key(self) -> str:
        """Generate a new API key."""
        return f"dynoai_{secrets.token_urlsafe(32)}"


# Global instance
_auth = None


def get_auth() -> APIKeyAuth:
    """Get or create auth instance."""
    global _auth
    if _auth is None:
        _auth = APIKeyAuth()
    return _auth


def require_api_key(f):
    """Decorator to require API key authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = get_auth()
        
        if not auth.enabled:
            return f(*args, **kwargs)
        
        api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            return jsonify({
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "API key required. Provide X-API-Key header."
                }
            }), 401
        
        if not auth.validate_key(api_key):
            return jsonify({
                "error": {
                    "code": "INVALID_API_KEY", 
                    "message": "Invalid or expired API key."
                }
            }), 403
        
        g.api_key = api_key
        return f(*args, **kwargs)
    
    return decorated
```

### 2. Apply to Endpoints

```python
# In app.py - protect write endpoints
@app.route("/api/analyze", methods=["POST"])
@require_api_key
@rate_limit("5/minute;20/hour")
def analyze():
    ...
```

### 3. Exempt Public Endpoints

- `/api/health` - Always public
- `/api/health/live` - Always public
- `/api/health/ready` - Always public
- `/api/docs` - Optionally public

### 4. Add Environment Variables

```bash
API_AUTH_ENABLED=true
API_KEYS=dynoai_key1,dynoai_key2
API_KEYS_FILE=/etc/dynoai/api_keys.txt
```

## Acceptance Criteria

- [ ] `api/auth.py` module created
- [ ] `@require_api_key` decorator working
- [ ] Health endpoints remain public
- [ ] 401 returned for missing key
- [ ] 403 returned for invalid key
- [ ] Key validation logged for audit
- [ ] Tests cover auth scenarios
- [ ] Documentation updated

## Files to Create/Modify

- `/api/auth.py` (new)
- `/api/app.py` (modify - add decorator)
- `/tests/api/test_authentication.py` (new)
- `/docs/API_AUTHENTICATION.md` (new)

## Testing

```bash
# Without auth
curl http://localhost:5001/api/health  # Should work

# With auth enabled
curl -H "X-API-Key: invalid" http://localhost:5001/api/analyze  # 403
curl -H "X-API-Key: valid_key" http://localhost:5001/api/analyze  # Works
```

