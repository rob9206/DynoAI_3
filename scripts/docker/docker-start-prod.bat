@echo off
REM DynoAI Docker Production Mode Startup
REM Simple batch wrapper for Docker Compose

echo ======================================
echo   DynoAI Docker Production Mode
echo ======================================
echo.

REM Check for .env file
if not exist ".env" (
    echo ERROR: .env file not found!
    echo Please create .env from config/env.example:
    echo   copy config\env.example .env
    echo   REM Edit .env with your settings
    pause
    exit /b 1
)

echo Starting DynoAI containers...
echo Mode: Production
echo.

docker-compose up -d --build %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to start containers!
    echo.
    pause
    exit /b 1
)

echo.
echo Waiting for services to be healthy...
timeout /t 5 /nobreak >nul

echo.
echo Container Status:
docker-compose ps

echo.
echo ======================================
echo   DynoAI is Running!
echo ======================================
echo.
echo Frontend:             http://localhost
echo Backend API:          http://localhost:5001
echo API Health:           http://localhost:5001/api/health
echo API Docs:             http://localhost:5001/api/docs
echo.
echo Redis:                localhost:6379
echo.
echo Useful Commands:
echo   View logs:          docker-compose logs -f
echo   Check status:       docker-compose ps
echo   Restart:            docker-compose restart
echo   Stop:               docker-compose down
echo   Rebuild:            docker-compose up -d --build
echo.
echo Production Features:
echo   - Optimized builds with multi-stage Dockerfiles
echo   - Non-root user ^(dynoai:1000^)
echo   - Health checks enabled
echo   - Data persisted in Docker volumes
echo   - Rate limiting with Redis
echo   - Structured JSON logging
echo.
echo Data Volumes:
echo   dynoai-uploads, dynoai-outputs, dynoai-runs, dynoai-redis
echo.
pause
