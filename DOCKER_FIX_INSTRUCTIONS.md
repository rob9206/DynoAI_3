# Docker Flask Application Fix

## Problem
The Docker container was failing to start the Flask application with the error:
```
Error: Could not locate a Flask application. Use the 'flask --app' option, 'FLASK_APP' environment variable, or a 'wsgi.py' or 'app.py' file in the current directory.
```

## Solution
Updated the Dockerfile `CMD` instruction to run the application directly using Python instead of the Flask module loader.

**Changed from:**
```dockerfile
CMD ["python", "-m", "api.app"]
```

**Changed to:**
```dockerfile
CMD ["python", "api/app.py"]
```

## How to Apply the Fix

### Option 1: Rebuild and Restart (Recommended)

1. **Stop the current container:**
   ```bash
   docker-compose down
   ```

2. **Rebuild the image with the fix:**
   ```bash
   docker-compose build --no-cache api
   ```

3. **Start the services:**
   ```bash
   docker-compose up -d
   ```

4. **Verify the container is running:**
   ```bash
   docker-compose ps
   ```

5. **Check the logs to confirm successful startup:**
   ```bash
   docker-compose logs -f api
   ```

   You should see the startup banner with:
   ```
   [*] DynoAI API Server
   [*] Server running on http://localhost:5001
   ```

### Option 2: Quick Restart (If you've already rebuilt)

If you've already rebuilt the image:

```bash
docker-compose restart api
```

### Option 3: Complete Rebuild (Nuclear Option)

If you want to ensure a completely clean build:

```bash
# Stop and remove all containers, networks, and volumes
docker-compose down -v

# Remove the old images
docker-compose rm -f

# Rebuild from scratch
docker-compose build --no-cache

# Start everything
docker-compose up -d
```

## Verification Steps

After starting the container, verify it's working:

1. **Check container status:**
   ```bash
   docker ps | grep dynoai-api
   ```
   Should show status as "Up" (not "Exited")

2. **Test the health endpoint:**
   ```bash
   curl http://localhost:5001/api/health/ready
   ```
   Should return a 200 OK response

3. **Access the admin dashboard:**
   Open browser to: http://localhost:5001/admin

4. **View API documentation:**
   Open browser to: http://localhost:5001/api/docs

## Troubleshooting

### Container still failing?

1. **Check detailed logs:**
   ```bash
   docker-compose logs api --tail=100
   ```

2. **Inspect the container:**
   ```bash
   docker-compose exec api ls -la /app/api/
   ```

3. **Check if app.py exists in the container:**
   ```bash
   docker-compose exec api cat /app/api/app.py | head -20
   ```

4. **Verify Python path:**
   ```bash
   docker-compose exec api python --version
   docker-compose exec api which python
   ```

### Port conflicts?

If port 5001 is already in use:

1. Update `.env` file:
   ```bash
   API_PORT=5002
   ```

2. Restart:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

## Additional Notes

- The fix uses the built-in Flask development server which is configured in `api/app.py`
- For production deployments, consider using Gunicorn or uWSGI as the WSGI server
- The container runs as non-root user `dynoai` (UID 1000) for security
- Debug mode is disabled by default (`DYNOAI_DEBUG=false`)

## Related Files

- `Dockerfile` - Contains the container build instructions
- `docker-compose.yml` - Orchestrates all services
- `api/app.py` - Flask application entry point
- `.env` - Environment variables (copy from `.env.example`)
