# DynoAI Docker Deployment Guide

This guide covers containerized deployment of DynoAI using Docker.

## Quick Start

### Production Deployment

```bash
# Clone and navigate to the project
cd DynoAI_3

# Build and start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

The application will be available at:
- **Frontend**: http://localhost:80
- **API**: http://localhost:5001

### Development Mode

```bash
# Start with hot reload enabled
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Frontend will be at http://localhost:5173
# API will be at http://localhost:5001
```

## Configuration

### Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```bash
# API Configuration
DYNOAI_DEBUG=false
API_PORT=5001

# Frontend Configuration
FRONTEND_PORT=80
VITE_API_URL=  # Leave empty for nginx proxy

# Jetstream Integration
JETSTREAM_ENABLED=false
JETSTREAM_API_URL=
JETSTREAM_API_KEY=
JETSTREAM_STUB_MODE=false

# xAI Integration
XAI_ENABLED=false
XAI_API_KEY=
```

### Custom Ports

```bash
# Use custom ports
API_PORT=8080 FRONTEND_PORT=3000 docker compose up -d
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Docker Network                       │
│  ┌─────────────────┐       ┌─────────────────────────┐ │
│  │   Frontend      │       │      API Server         │ │
│  │   (Nginx)       │──────▶│      (Flask)            │ │
│  │   Port: 80      │       │      Port: 5001         │ │
│  └────────┬────────┘       └───────────┬─────────────┘ │
│           │                            │               │
│           │    ┌───────────────────────┼───────────┐   │
│           │    │        Volumes        │           │   │
│           │    │  ┌─────────┐ ┌────────┴─────────┐ │   │
│           │    │  │ uploads │ │ outputs │ runs   │ │   │
│           │    │  └─────────┘ └──────────────────┘ │   │
│           │    └───────────────────────────────────┘   │
└───────────┼─────────────────────────────────────────────┘
            │
        Host:80
```

## Building Images

### Build All Services

```bash
docker compose build
```

### Build Individual Services

```bash
# Backend only
docker build -t dynoai-api:latest .

# Frontend only
docker build -t dynoai-frontend:latest ./frontend
```

### Build with Custom Tags

```bash
docker compose build --build-arg VITE_API_URL=https://api.example.com
```

## Data Persistence

Data is persisted in Docker volumes:

| Volume | Purpose | Container Path |
|--------|---------|----------------|
| `dynoai-uploads` | Uploaded CSV files | `/app/uploads` |
| `dynoai-outputs` | Analysis outputs | `/app/outputs` |
| `dynoai-runs` | Run state and metadata | `/app/runs` |

### Backup Volumes

```bash
# Backup all data
docker run --rm \
  -v dynoai-uploads:/uploads \
  -v dynoai-outputs:/outputs \
  -v dynoai-runs:/runs \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/dynoai-backup-$(date +%Y%m%d).tar.gz /uploads /outputs /runs

# Restore from backup
docker run --rm \
  -v dynoai-uploads:/uploads \
  -v dynoai-outputs:/outputs \
  -v dynoai-runs:/runs \
  -v $(pwd)/backup:/backup \
  alpine tar xzf /backup/dynoai-backup-YYYYMMDD.tar.gz -C /
```

### Clear All Data

```bash
docker compose down -v
```

## Health Checks

Both services include health checks:

```bash
# Check API health
curl http://localhost:5001/api/health

# Check frontend health
curl http://localhost:80/health

# Docker health status
docker compose ps
```

## Logs and Debugging

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f api
docker compose logs -f frontend

# Get container shell access
docker compose exec api /bin/bash
docker compose exec frontend /bin/sh
```

## Production Recommendations

### 1. Use Secrets Management

```yaml
# docker-compose.prod.yml
services:
  api:
    secrets:
      - jetstream_api_key
      - xai_api_key
    environment:
      - JETSTREAM_API_KEY_FILE=/run/secrets/jetstream_api_key

secrets:
  jetstream_api_key:
    external: true
  xai_api_key:
    external: true
```

### 2. Resource Limits

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### 3. SSL/TLS with Traefik

```yaml
# Add Traefik reverse proxy for automatic SSL
services:
  traefik:
    image: traefik:v2.10
    command:
      - "--certificatesresolvers.letsencrypt.acme.email=admin@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./letsencrypt:/letsencrypt
      - /var/run/docker.sock:/var/run/docker.sock:ro

  frontend:
    labels:
      - "traefik.http.routers.frontend.rule=Host(`dynoai.example.com`)"
      - "traefik.http.routers.frontend.tls.certresolver=letsencrypt"
```

### 4. Monitoring with Prometheus

Add to `docker-compose.prod.yml`:

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs api

# Common issues:
# - Port already in use: Change API_PORT or FRONTEND_PORT
# - Permission denied: Check volume permissions
```

### API Not Responding

```bash
# Check if container is healthy
docker compose ps

# Test internal connectivity
docker compose exec frontend curl http://api:5001/api/health
```

### Frontend Can't Connect to API

1. Ensure both containers are on the same network
2. Check nginx proxy configuration
3. Verify `VITE_API_URL` is set correctly for external access

### Out of Disk Space

```bash
# Clean up unused Docker resources
docker system prune -a

# Remove old volumes
docker volume prune
```

## Upgrading

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker compose down
docker compose build --no-cache
docker compose up -d

# Verify health
docker compose ps
curl http://localhost:5001/api/health
```

