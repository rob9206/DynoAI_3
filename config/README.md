# DynoAI Configuration Files

This directory contains configuration templates and reference files for DynoAI.

## Environment Configuration Files

### `env.example` - Generic Template
All-purpose environment configuration template suitable for both native and Docker deployments.

**Usage:**
```powershell
# Native Windows deployment
Copy-Item config/env.example .env
notepad .env  # Edit as needed
python -m api.app
```

**Best for:**
- Native Windows installation
- First-time setup
- General reference

### `env.docker` - Docker-Optimized Template
Environment configuration specifically optimized for Docker deployments with container-friendly defaults.

**Usage:**
```powershell
# Docker deployment
Copy-Item config/env.docker .env
notepad .env  # Edit as needed
.\start-docker-prod.ps1
```

**Best for:**
- Docker deployments
- Production containers
- Kubernetes/orchestration

**Key Differences from env.example:**
- `REDIS_HOST=redis` (container name instead of localhost)
- `RATE_LIMIT_STORAGE=redis://redis:6379` (container URL)
- Container paths (`/app/uploads` instead of `uploads`)
- Host network settings for JetDrive

### `env.production` - Production Deployment
Production-specific configuration (already exists).

### `env.staging` - Staging Environment
Staging-specific configuration (already exists).

## Hardware Configuration Files

### `dynoware_rt150.json` - Dyno Hardware Reference
Reference configuration for the Dynojet Dynoware RT-150 at Dawson Dynamics.

**Contents:**
- Drum specifications (Serial 1000588)
- Drum mass: 14.121 kg
- Drum circumference: 4.673 ft
- Drum radius: 0.7437 ft
- Network configuration (192.168.1.115, UDP 22344)
- Firmware versions

**Usage:**
- Reference for API configuration
- Hardware specifications
- Network settings validation

### `afr_calibration.json` - AFR Sensor Calibration
Air-Fuel Ratio sensor calibration data.

### `ingestion.json` - Data Ingestion Configuration
Configuration for data ingestion pipelines.

## Choosing the Right Template

### For Native Windows Installation

```powershell
Copy-Item config/env.example .env
```

Edit these key settings:
- `DYNOAI_HOST=127.0.0.1` or `0.0.0.0`
- `RATE_LIMIT_STORAGE=memory://`
- `REDIS_HOST=localhost` (if using local Redis)

### For Docker Deployment

```powershell
Copy-Item config/env.docker .env
```

Docker-optimized defaults:
- `REDIS_HOST=redis` (container name)
- `RATE_LIMIT_STORAGE=redis://redis:6379`
- Container paths automatically configured

### For JetDrive Integration

Either template works, but ensure:
- `JETDRIVE_ENABLED=true`
- `JETDRIVE_PORT=22344`
- `DYNOWARE_IP=192.168.1.115`
- Windows Firewall allows UDP 22344

### For Production Deployment

Use `env.production` or `env.docker` with:
- `DYNOAI_DEBUG=false`
- `LOG_LEVEL=INFO` or `WARNING`
- `LOG_FORMAT=production` (JSON structured logs)
- `RATE_LIMIT_ENABLED=true`
- Specific CORS origins (not `*`)
- Secret keys configured
- API keys for Jetstream/xAI

## Environment Variables Priority

1. System environment variables (highest)
2. `.env` file in project root
3. Template defaults
4. Code defaults (lowest)

## Security Notes

⚠️ **Never commit `.env` files to version control!**

The `.env` file is in `.gitignore` for security:
- API keys
- Database passwords
- Secret keys
- Production URLs

Always use templates (`env.example`, `env.docker`) for version control.

## Validation

After creating `.env`, validate with:

```powershell
# Native validation
python -c "from api.config import DynoConfig; print('✓ Config loaded')"

# Docker validation
.\validate-docker-setup.ps1
```

## Quick Reference

| Deployment Type | Template | Key Settings |
|----------------|----------|--------------|
| Native Dev | `env.example` | `DYNOAI_DEBUG=true`, `memory://` |
| Native Prod | `env.production` | `DYNOAI_DEBUG=false`, Redis URL |
| Docker Dev | `env.docker` | Container names, hot reload |
| Docker Prod | `env.docker` | Container names, optimized |
| Docker + JetDrive | `env.docker` | Host network, UDP config |

## Troubleshooting

### Issue: Variables Not Loading

**Check:**
1. `.env` file exists in project root (not in `config/`)
2. No syntax errors in `.env`
3. No quotes around simple values
4. Boolean values are lowercase (`true`/`false`)

### Issue: Docker Can't Connect to Redis

**Fix:**
```bash
# In .env, use container name:
REDIS_HOST=redis
RATE_LIMIT_STORAGE=redis://redis:6379
```

### Issue: JetDrive Not Receiving Data

**Check:**
1. `JETDRIVE_ENABLED=true`
2. `JETDRIVE_PORT=22344`
3. `DYNOWARE_IP=192.168.1.115`
4. Windows Firewall allows UDP 22344
5. Network can reach 192.168.1.115

## Additional Resources

- [Main README](../README.md) - Project overview
- [Docker Quick Start](../DOCKER_QUICKSTART.md) - Docker in 5 minutes
- [Docker Migration Guide](../DOCKER_MIGRATION.md) - Complete Docker guide
- [API Documentation](http://localhost:5001/api/docs) - When running

---

**Last Updated**: 2026-01-09  
**Maintained By**: DynoAI Team
