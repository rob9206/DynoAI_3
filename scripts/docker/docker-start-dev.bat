@echo off
REM DynoAI Docker Development Mode Startup
REM Simple batch wrapper for Docker Compose

echo ======================================
echo   DynoAI Docker Development Mode
echo ======================================
echo.

REM Check for .env file
if not exist ".env" (
    echo WARNING: .env file not found!
    echo Creating from config/env.example...
    copy config\env.example .env
    echo Created .env file
    echo.
    echo Please review .env and update settings if needed.
    echo.
)

echo Starting DynoAI containers...
echo Mode: Development ^(hot reload enabled^)
echo.

docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to start containers!
    echo.
    pause
    exit /b 1
)

echo.
echo Waiting for services...
timeout /t 3 /nobreak >nul

echo.
echo ======================================
echo   DynoAI is Running!
echo ======================================
echo.
echo Frontend ^(Vite Dev^):  http://localhost:5173
echo Backend API:          http://localhost:5001
echo API Health:           http://localhost:5001/api/health
echo API Docs:             http://localhost:5001/api/docs
echo.
echo Redis:                localhost:6379
echo.
echo Useful Commands:
echo   View logs:          docker-compose logs -f
echo   View API logs:      docker-compose logs -f api
echo   View frontend logs: docker-compose logs -f frontend
echo   Restart API:        docker-compose restart api
echo   Stop all:           docker-compose down
echo.
echo Development Features:
echo   - Hot reload enabled for frontend and backend
echo   - Source code mounted from local filesystem
echo   - Debug mode enabled
echo   - Local file persistence ^(uploads, outputs, runs^)
echo.
echo Press Ctrl+C to stop ^(or run: docker-compose down^)
echo.
pause
