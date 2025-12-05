# TASK-007: Production Environment Configuration

**Status:** 🟡 Ready for Work  
**Priority:** High  
**Estimated Effort:** 1-2 hours  
**Dependencies:** None

## Objective

Create comprehensive environment configuration files for development, staging, and production deployments.

## Deliverables

### 1. Create `.env.example` Template

```bash
# Copy to .env and customize for your environment

# =============================================================================
# Server Configuration
# =============================================================================
DYNOAI_HOST=0.0.0.0
DYNOAI_PORT=5001
DYNOAI_DEBUG=false

# =============================================================================
# Logging Configuration  
# =============================================================================
LOG_LEVEL=INFO
LOG_FORMAT=production  # "development" or "production" (JSON)

# =============================================================================
# Rate Limiting
# =============================================================================
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_EXPENSIVE=5/minute;20/hour
RATE_LIMIT_STORAGE=memory://  # Use redis:// for distributed

# =============================================================================
# Storage Configuration
# =============================================================================
DYNOAI_UPLOAD_DIR=uploads
DYNOAI_OUTPUT_DIR=outputs
DYNOAI_RUNS_DIR=runs
DYNOAI_MAX_UPLOAD_MB=50

# =============================================================================
# CORS Configuration
# =============================================================================
DYNOAI_CORS_ORIGINS=*  # Restrict in production: https://yourdomain.com

# =============================================================================
# Jetstream Integration
# =============================================================================
JETSTREAM_ENABLED=false
JETSTREAM_STUB_MODE=true
JETSTREAM_API_URL=
JETSTREAM_API_KEY=
JETSTREAM_POLL_INTERVAL=30
JETSTREAM_AUTO_PROCESS=true

# =============================================================================
# xAI (Grok) Integration
# =============================================================================
XAI_ENABLED=false
XAI_API_KEY=
XAI_API_URL=https://api.x.ai/v1/chat/completions
XAI_MODEL=grok-beta
```

### 2. Create `.env.production` Template

Production-specific overrides with security hardening.

### 3. Create `.env.staging` Template

Staging environment with Jetstream stub mode enabled.

### 4. Update `docker-compose.yml`

- Add environment file references
- Add Redis service for rate limit storage
- Configure secrets management

## Acceptance Criteria

- [ ] `.env.example` created with all documented variables
- [ ] `.env.production` template with secure defaults
- [ ] `.env.staging` template for testing
- [ ] Docker compose updated to use env files
- [ ] README updated with environment setup instructions

## Files to Create/Modify

- `/.env.example` (new)
- `/.env.production.example` (new)
- `/.env.staging.example` (new)
- `/docker-compose.yml` (modify)
- `/README.md` (modify)

## Testing

```bash
# Verify env loading
python -c "from api.config import get_config; print(get_config().to_dict())"
```

