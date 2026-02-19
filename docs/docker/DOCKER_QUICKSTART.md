# Docker Quick Start Guide

Get DynoAI running in Docker in 5 minutes.

## Prerequisites

- Docker Desktop for Windows installed and running
- 4GB RAM available for containers
- Administrator privileges (for firewall rules if using JetDrive)

## Quick Start

### 1. First Time Setup

```powershell
# Create environment file
Copy-Item config/env.example .env

# Edit .env if needed (optional for initial test)
notepad .env
```

### 2. Choose Your Mode

#### Development Mode (Recommended for Testing)

Hot reload, debug mode, easy file access:

```powershell
.\start-docker-dev.ps1 -Build
```

Access:
- Frontend: http://localhost:5173
- API: http://localhost:5001

#### Production Mode

Optimized, production-ready:

```powershell
.\start-docker-prod.ps1 -Build
```

Access:
- Frontend: http://localhost
- API: http://localhost:5001

#### JetDrive Mode (Live Dyno Integration)

For real dyno communication:

```powershell
.\start-docker-jetdrive.ps1 -Build
```

Access:
- Same as production
- JetDrive diagnostics: http://localhost:5001/api/jetdrive/diagnostics

### 3. Verify It's Working

```powershell
# Check containers are running
docker-compose ps

# Test API
curl http://localhost:5001/api/health

# Open frontend in browser
start http://localhost:5173  # Dev mode
start http://localhost       # Prod mode
```

## Common Commands

```powershell
# View logs
docker-compose logs -f

# Stop everything
docker-compose down

# Restart
.\start-docker-prod.ps1 -Restart

# Fresh start (removes all data!)
.\start-docker-dev.ps1 -Fresh

# Check status
.\start-docker-prod.ps1 -Status
```

## Troubleshooting

### "Docker is not running"

Start Docker Desktop from Start menu.

### "Port already in use"

Stop native services:
```powershell
# Close any terminal windows running the backend/frontend
# Or use Task Manager to kill python.exe and node.exe
```

### Frontend can't connect to API

Check `.env` file has:
```bash
VITE_API_URL=http://localhost:5001
```

Rebuild:
```powershell
.\start-docker-dev.ps1 -Build
```

### JetDrive not receiving data

1. Check Windows Firewall allows UDP 22344
2. Verify dyno is accessible: `ping 192.168.1.115`
3. Check diagnostics: http://localhost:5001/api/jetdrive/diagnostics
4. If still failing, run API natively (see full migration guide)

## What's Next?

- Read [DOCKER_MIGRATION.md](DOCKER_MIGRATION.md) for complete guide
- Review `.env` file and customize settings
- Test all features (upload, analysis, export)
- Set up your preferred deployment mode

## Getting Help

- Check logs: `docker-compose logs -f api`
- View diagnostics: http://localhost:5001/api/health
- Full troubleshooting: See [DOCKER_MIGRATION.md](DOCKER_MIGRATION.md)
