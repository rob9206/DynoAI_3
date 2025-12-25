# API Authentication

DynoAI supports optional API key authentication to protect endpoints from unauthorized access.

## Overview

- **Development:** Authentication disabled by default for ease of local testing
- **Production:** Authentication enabled with API key validation
- **Keys:** Loaded from environment variables or files
- **Format:** Keys provided in `X-API-Key` HTTP header

## Configuration

### Environment Variables

```bash
# Enable/disable authentication
API_AUTH_ENABLED=true

# Option 1: Comma-separated keys in environment
API_KEYS=dynoai_key1,dynoai_key2,dynoai_key3

# Option 2: Load keys from file
API_KEYS_FILE=/etc/dynoai/api_keys.txt

# Or use both sources
```

### API Keys File Format

```txt
# Lines starting with # are comments
dynoai_production_key_abc123
dynoai_staging_key_xyz789

# Empty lines are ignored
dynoai_backup_key_def456
```

## Generating API Keys

### Using Python

```bash
# Generate a single key
python -m api.auth generate

# Generate multiple keys
python -m api.auth generate 5
```

### Programmatically

```python
from api.auth import generate_api_key

key = generate_api_key()
print(f"New API key: {key}")
```

### Using Secrets Module

```bash
python -c "import secrets; print(f'dynoai_{secrets.token_urlsafe(32)}')"
```

## Using API Keys

### cURL

```bash
# Without authentication (development)
curl http://localhost:5001/api/analyze -X POST -F "file=@log.csv"

# With authentication (production)
curl http://localhost:5001/api/analyze \
  -X POST \
  -H "X-API-Key: dynoai_your_api_key_here" \
  -F "file=@log.csv"
```

### Python Requests

```python
import requests

api_key = "dynoai_your_api_key_here"
headers = {"X-API-Key": api_key}

# Upload file for analysis
with open("log.csv", "rb") as f:
    response = requests.post(
        "http://localhost:5001/api/analyze",
        headers=headers,
        files={"file": f}
    )

print(response.json())
```

### JavaScript/Fetch

```javascript
const apiKey = "dynoai_your_api_key_here";

fetch("http://localhost:5001/api/analyze", {
  method: "POST",
  headers: {
    "X-API-Key": apiKey,
  },
  body: formData,
})
  .then((res) => res.json())
  .then((data) => console.log(data));
```

## Protected Endpoints

The following endpoints require API key authentication when enabled:

### Write Operations
- `POST /api/analyze` - Run analysis (expensive operation)
- `POST /api/apply` - Apply VE corrections (state-changing)
- `POST /api/virtual-tune/start` - Start tuning session
- `POST /api/jetdrive/capture/start` - Start live capture

### Always Public
- `GET /api/health` - Health check
- `GET /api/health/live` - Liveness probe
- `GET /api/health/ready` - Readiness probe
- `GET /api/docs` - API documentation

### Read Operations
Most GET endpoints are public by default but can be protected by adding the `@require_api_key` decorator.

## Error Responses

### 401 Unauthorized (Missing Key)

```json
{
  "error": {
    "code": "AUTH_REQUIRED",
    "message": "API key required. Provide X-API-Key header."
  }
}
```

### 403 Forbidden (Invalid Key)

```json
{
  "error": {
    "code": "INVALID_API_KEY",
    "message": "Invalid or expired API key."
  }
}
```

## Security Best Practices

### Key Storage

✅ **DO:**
- Store keys in environment variables or secret management systems
- Use `.env` files for local development (excluded from git)
- Use dedicated files with restricted permissions (`chmod 600`)
- Rotate keys periodically
- Use different keys for different environments (dev/staging/prod)

❌ **DON'T:**
- Hard-code keys in source code
- Commit keys to version control
- Share keys via insecure channels (email, Slack, etc.)
- Use the same key across multiple environments

### Key Distribution

**For Team Members:**
```bash
# Generate a new key for each team member
python -m api.auth generate

# Securely share via encrypted channel (1Password, Vault, etc.)
```

**For Production:**
```bash
# Use secret management
# AWS Secrets Manager, HashiCorp Vault, etc.

# Or environment variables in deployment
kubectl create secret generic dynoai-api-keys \
  --from-literal=api-key=$(python -m api.auth generate)
```

### Monitoring

All authentication attempts are logged for auditing:

```python
# Successful authentication
logger.debug(f"Authenticated request to {request.path} (Key: dynoai_abc...)")

# Failed authentication
logger.warning(f"Forbidden request to {request.path} - Invalid API key. IP: {request.remote_addr}")
```

## Hot-Reloading Keys

Keys can be reloaded without restarting the server:

```python
from api.auth import get_auth

# Reload keys from environment/file
auth = get_auth()
count = auth.reload_keys()
print(f"Reloaded {count} API keys")
```

## Development Mode

For local development, authentication is disabled by default:

```bash
# .env (development)
API_AUTH_ENABLED=false
```

This allows developers to test endpoints without managing keys locally.

## Production Deployment

### Docker Compose

```yaml
services:
  api:
    environment:
      - API_AUTH_ENABLED=true
      - API_KEYS_FILE=/run/secrets/api_keys
    secrets:
      - api_keys

secrets:
  api_keys:
    file: ./secrets/api_keys.txt
```

### Kubernetes

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: dynoai-api-keys
type: Opaque
data:
  api-keys: ZHlub2FpX3lvdXJfa2V5X2hlcmU=  # base64 encoded

---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: dynoai-api
          env:
            - name: API_AUTH_ENABLED
              value: "true"
            - name: API_KEYS
              valueFrom:
                secretKeyRef:
                  name: dynoai-api-keys
                  key: api-keys
```

## Testing

```bash
# Run authentication tests
pytest tests/api/test_api_authentication.py -v
```

## Extending Authentication

To protect additional endpoints:

```python
from api.auth import require_api_key

@app.route("/api/custom-endpoint", methods=["POST"])
@require_api_key  # Add this decorator
def custom_endpoint():
    return jsonify({"message": "Protected endpoint"})
```

## Troubleshooting

### Authentication Always Fails

Check:
1. `API_AUTH_ENABLED=true` is set
2. Keys are loaded: check logs for "Loaded X key(s)"
3. Header is correctly named: `X-API-Key`
4. Key matches exactly (no extra spaces)

### Keys Not Loading from File

Check:
1. File path is absolute or relative to working directory
2. File exists and is readable
3. File permissions (`ls -l /path/to/api_keys.txt`)
4. No BOM or encoding issues (should be UTF-8)

### Need to Disable Auth Temporarily

```bash
# .env
API_AUTH_ENABLED=false
```

Or unset the environment variable:
```bash
unset API_AUTH_ENABLED
```

## Related Documentation

- [Environment Configuration](.env.example)
- [API Reference](/api/docs)
- [Security Best Practices](SECURITY.md)

