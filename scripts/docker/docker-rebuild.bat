@echo off
REM DynoAI Docker Container Fix and Restart Script
REM This script rebuilds and restarts the DynoAI API container

echo ========================================
echo DynoAI Docker Container Rebuild Script
echo ========================================
echo.

echo [1/5] Stopping containers...
docker-compose down
if errorlevel 1 (
    echo ERROR: Failed to stop containers
    pause
    exit /b 1
)
echo SUCCESS: Containers stopped
echo.

echo [2/5] Rebuilding API container (no cache)...
docker-compose build --no-cache api
if errorlevel 1 (
    echo ERROR: Failed to rebuild API container
    pause
    exit /b 1
)
echo SUCCESS: API container rebuilt
echo.

echo [3/5] Starting services...
docker-compose up -d
if errorlevel 1 (
    echo ERROR: Failed to start services
    pause
    exit /b 1
)
echo SUCCESS: Services started
echo.

echo [4/5] Waiting for services to initialize...
timeout /t 5 /nobreak >nul
echo.

echo [5/5] Checking container status...
docker-compose ps
echo.

echo ========================================
echo Container rebuild complete!
echo ========================================
echo.
echo Next steps:
echo   1. Check logs: docker-compose logs -f api
echo   2. Test health: curl http://localhost:5001/api/health/ready
echo   3. Open admin: http://localhost:5001/admin
echo   4. API docs: http://localhost:5001/api/docs
echo.
echo Press any key to view API logs...
pause >nul

docker-compose logs -f api
