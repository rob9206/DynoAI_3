# DynoAI Docker Migration Guide

Complete guide for migrating DynoAI from native Windows installation to Docker containers.

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Migration Steps](#migration-steps)
- [Network Configuration](#network-configuration)
- [Data Migration](#data-migration)
- [Startup Options](#startup-options)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Rollback Plan](#rollback-plan)

## Overview

DynoAI includes production-ready Docker configurations:

- ✅ Multi-stage Dockerfiles (optimized builds)
- ✅ Development & Production compose files
- ✅ Health checks and monitoring
- ✅ Volume management for data persistence
- ✅ Redis for rate limiting and caching
- ✅ Special JetDrive UDP multicast support

## Prerequisites

### 1. Install Docker Desktop for Windows

Download from: https://www.docker.com/products/docker-desktop

```powershell
# Verify installation
docker --version
docker-compose --version
```

Expected output:
```
Docker version 24.x.x
Docker Compose version v2.x.x
```

### 2. Configure Docker Desktop

Recommended settings:
- **Memory**: 4GB minimum (8GB recommended)
- **CPU**: 2 cores minimum (4 recommended)
- **Disk**: 20GB available space
- **WSL 2 Backend**: Enabled (default on Windows 11)

### 3. System Requirements

- Windows 10/11 Pro, Enterprise, or Education
- Hyper-V and WSL 2 enabled
- Administrator privileges
- Network access to Dynojet hardware (if using JetDrive)

## Migration Steps

### Step 1: Create Environment File

```powershell
# Copy template
Copy-Item config/env.example .env

# Edit with your settings
notepad .env
```

Key settings to configure:

```bash
# API Configuration
DYNOAI_HOST=0.0.0.0
DYNOAI_PORT=5001
API_PORT=5001

# Frontend Configuration
FRONTEND_PORT=80
VITE_API_URL=http://localhost:5001

# JetDrive (if using live dyno)
JETDRIVE_PORT=22344
DYNOWARE_IP=192.168.1.115

# Redis
RATE_LIMIT_STORAGE=redis://redis:6379
REDIS_HOST=redis
REDIS_PORT=6379

# Environment
DYNOAI_DEBUG=false
LOG_LEVEL=INFO
```

### Step 2: Choose Your Migration Path

#### Option A: Development Mode (Hot Reload)

Best for: Active development, testing

```powershell
.\start-docker-dev.ps1
```

Features:
- Source code mounted (changes reflected immediately)
- Debug mode enabled
- Frontend on port 5173 (Vite dev server)
- Local file persistence

#### Option B: Production Mode

Best for: Production deployment, stable builds

```powershell
.\start-docker-prod.ps1
```

Features:
- Optimized builds
- Non-root user security
- Frontend on port 80
- Data in Docker volumes
- Health checks enabled

#### Option C: JetDrive Mode

Best for: Live dyno integration with UDP multicast

```powershell
.\start-docker-jetdrive.ps1
```

Features:
- Host network mode for UDP multicast
- JetDrive diagnostics
- Communication with Dynoware RT-150
- Production or development variants

### Step 3: Initial Startup

First time setup:

```powershell
# Development mode
.\start-docker-dev.ps1 -Build

# Production mode
.\start-docker-prod.ps1 -Build

# JetDrive mode
.\start-docker-jetdrive.ps1 -Build
```

The `-Build` flag ensures Docker builds fresh images.

### Step 4: Verify Services

```powershell
# Check container status
docker-compose ps

# Check logs
docker-compose logs -f

# Test health endpoints
curl http://localhost:5001/api/health
curl http://localhost:5001/api/health/ready
```

## Network Configuration

### Standard Configuration (Bridge Network)

Used by default for development and production modes:

- **Backend API**: http://localhost:5001
- **Frontend**: http://localhost:80 (prod) or http://localhost:5173 (dev)
- **Redis**: localhost:6379

Services communicate via Docker network `dynoai-network`.

### JetDrive Configuration (Host Network)

Required for UDP multicast communication with Dynojet hardware:

```yaml
# docker-compose.jetdrive.yml
services:
  api:
    network_mode: "host"
    environment:
      - JETDRIVE_PORT=22344
      - JETDRIVE_MCAST_GROUP=239.255.60.60
      - DYNOWARE_IP=192.168.1.115
```

**Important Windows Limitations:**
- Docker Desktop on Windows has limited host network support
- UDP multicast may not work reliably
- Alternative: Run API natively, keep Redis/Frontend in Docker

### Firewall Configuration

Allow UDP port 22344 for JetDrive:

```powershell
# Add Windows Firewall rule
New-NetFirewallRule -DisplayName "DynoAI JetDrive" -Direction Inbound -Protocol UDP -LocalPort 22344 -Action Allow
```

## Data Migration

### Migrate Existing Data to Docker Volumes

#### Method 1: Using Docker Commands (Recommended)

```powershell
# Create volumes
docker volume create dynoai-uploads
docker volume create dynoai-outputs
docker volume create dynoai-runs

# Copy data to volumes
docker run --rm -v dynoai-uploads:/target -v ${PWD}/uploads:/source alpine cp -r /source/. /target/
docker run --rm -v dynoai-outputs:/target -v ${PWD}/outputs:/source alpine cp -r /source/. /target/
docker run --rm -v dynoai-runs:/target -v ${PWD}/runs:/source alpine cp -r /source/. /target/

# Verify
docker run --rm -v dynoai-uploads:/data alpine ls -la /data
```

#### Method 2: Using Bind Mounts (Development)

In `docker-compose.dev.yml` (already configured):

```yaml
volumes:
  - ./uploads:/app/uploads
  - ./outputs:/app/outputs
  - ./runs:/app/runs
```

This keeps data in your local filesystem for easy access.

### Database Migration

#### Option A: Keep SQLite (Simple)

Add to `docker-compose.yml`:

```yaml
services:
  api:
    volumes:
      - ./dynoai.db:/app/dynoai.db
```

#### Option B: Migrate to PostgreSQL (Recommended for Production)

1. Uncomment PostgreSQL service in `docker-compose.yml`
2. Export SQLite data:

```powershell
# Export data
python -c "
from api.models.database import db
# Export logic here
"
```

3. Import to PostgreSQL:

```powershell
docker-compose exec postgres psql -U dynoai -d dynoai < export.sql
```

## Startup Options

### Development Mode Scripts

```powershell
# Normal start
.\start-docker-dev.ps1

# With rebuild
.\start-docker-dev.ps1 -Build

# Fresh start (remove volumes)
.\start-docker-dev.ps1 -Fresh

# With logs in foreground
.\start-docker-dev.ps1 -Logs
```

### Production Mode Scripts

```powershell
# Start
.\start-docker-prod.ps1

# With rebuild
.\start-docker-prod.ps1 -Build

# Restart
.\start-docker-prod.ps1 -Restart

# Stop
.\start-docker-prod.ps1 -Stop

# View logs
.\start-docker-prod.ps1 -Logs

# Check status
.\start-docker-prod.ps1 -Status
```

### JetDrive Mode Scripts

```powershell
# Production with JetDrive
.\start-docker-jetdrive.ps1

# Development with JetDrive
.\start-docker-jetdrive.ps1 -Dev

# With rebuild
.\start-docker-jetdrive.ps1 -Build

# Stop
.\start-docker-jetdrive.ps1 -Stop
```

### Manual Docker Compose Commands

```powershell
# Development
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Production
docker-compose up -d

# JetDrive
docker-compose -f docker-compose.yml -f docker-compose.jetdrive.yml up -d

# Stop all
docker-compose down

# Stop and remove volumes
docker-compose down -v

# View logs
docker-compose logs -f api
docker-compose logs -f frontend

# Restart single service
docker-compose restart api

# Rebuild single service
docker-compose up -d --build api
```

## Verification

### 1. Container Health

```powershell
# Check all containers are running
docker-compose ps

# Expected output: All containers in "Up" state with "(healthy)"
```

### 2. API Health Checks

```powershell
# Basic health
curl http://localhost:5001/api/health

# Readiness check
curl http://localhost:5001/api/health/ready

# Expected: {"status": "ok", "version": "1.2.1", ...}
```

### 3. Frontend Access

Open browser to:
- Production: http://localhost
- Development: http://localhost:5173

### 4. JetDrive Diagnostics

```powershell
# Run diagnostics
curl http://localhost:5001/api/jetdrive/diagnostics

# Check dyno config
curl http://localhost:5001/api/dyno/config

# Verify UDP port binding
netstat -an | findstr :22344
```

### 5. Test File Upload

```powershell
# Upload test file
curl -X POST -F "file=@test.csv" http://localhost:5001/api/jetdrive/upload
```

### 6. Performance Check

```powershell
# View resource usage
docker stats --no-stream

# Expected:
# - API: <200MB RAM, <10% CPU (idle)
# - Frontend: <50MB RAM, <1% CPU
# - Redis: <50MB RAM, <1% CPU
```

## Troubleshooting

### Issue: Containers Won't Start

```powershell
# Check Docker daemon
docker info

# Check logs
docker-compose logs

# Common fixes:
# 1. Restart Docker Desktop
# 2. Remove old containers: docker-compose down -v
# 3. Rebuild: docker-compose up --build
```

### Issue: Frontend Can't Connect to API

**Symptoms**: Network errors in browser console

**Solutions**:

1. Check VITE_API_URL in `.env`:
   ```bash
   VITE_API_URL=http://localhost:5001
   ```

2. Verify API is accessible:
   ```powershell
   curl http://localhost:5001/api/health
   ```

3. Check CORS settings in API

### Issue: JetDrive UDP Not Receiving Data

**Symptoms**: No dyno data in diagnostics

**Solutions**:

1. Verify network mode:
   ```powershell
   docker inspect dynoai-api | grep NetworkMode
   # Should show "host" for JetDrive mode
   ```

2. Check Windows Firewall:
   ```powershell
   Get-NetFirewallRule -DisplayName "DynoAI JetDrive"
   ```

3. Test UDP port:
   ```powershell
   netstat -an | findstr :22344
   ```

4. Ping Dynoware:
   ```powershell
   ping 192.168.1.115
   ```

5. **Fallback**: Run API natively:
   ```powershell
   # Stop Docker API
   docker-compose stop api
   
   # Run natively
   $env:REDIS_HOST="localhost"
   python -m api.app
   ```

### Issue: Permission Denied on Volumes

**Symptoms**: Container can't write to volumes

**Solutions**:

1. Use bind mounts instead (development):
   ```yaml
   volumes:
     - ./uploads:/app/uploads
   ```

2. Check volume permissions:
   ```powershell
   docker run --rm -v dynoai-uploads:/data alpine ls -la /data
   ```

### Issue: Slow Build Times

**Solutions**:

1. Check `.dockerignore` is in place
2. Use Docker build cache:
   ```powershell
   docker-compose build --parallel
   ```
3. Increase Docker Desktop resources

### Issue: Database Connection Failed

**Symptoms**: API won't start, database errors in logs

**Solutions**:

1. Check database file exists:
   ```powershell
   ls dynoai.db
   ```

2. Verify volume mount:
   ```yaml
   volumes:
     - ./dynoai.db:/app/dynoai.db
   ```

3. Reset database:
   ```powershell
   # Backup first!
   Copy-Item dynoai.db dynoai.db.backup
   
   # Remove and let API recreate
   Remove-Item dynoai.db
   docker-compose restart api
   ```

## Rollback Plan

If Docker migration doesn't work, revert to native:

```powershell
# 1. Stop Docker containers
docker-compose down

# 2. Restore native startup
.\start-dev.bat

# or

cd C:\Dev\DynoAI_3
python -m api.app

# Terminal 2
cd C:\Dev\DynoAI_3\frontend
npm run dev
```

Your original files remain unchanged, so native mode continues to work.

## Migration Checklist

- [ ] Docker Desktop installed and running
- [ ] `.env` file created and configured
- [ ] Firewall rules added for JetDrive (if needed)
- [ ] Data backed up (`uploads`, `outputs`, `runs`, `dynoai.db`)
- [ ] Containers start successfully
- [ ] Health checks passing
- [ ] Frontend accessible
- [ ] API endpoints working
- [ ] File uploads working
- [ ] JetDrive diagnostics passing (if applicable)
- [ ] Performance acceptable
- [ ] Documentation updated

## Next Steps

After successful migration:

1. **Monitor for 1 week** in development mode
2. **Test all features** (upload, analysis, export, JetDrive)
3. **Benchmark performance** vs native
4. **Update deployment scripts** in CI/CD
5. **Document any issues** and workarounds
6. **Train team** on Docker commands
7. **Consider Kubernetes** for production scaling

## Support

For issues:

1. Check logs: `docker-compose logs -f`
2. Review diagnostics: `http://localhost:5001/api/jetdrive/diagnostics`
3. Check this guide's troubleshooting section
4. Open GitHub issue with logs attached

---

**Version**: 1.0  
**Last Updated**: 2026-01-09  
**Maintained By**: DynoAI Team
