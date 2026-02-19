@echo off
REM DynoAI Docker Validation Script
REM Checks if system is ready for Docker deployment

echo ======================================
echo   DynoAI Docker Setup Validator
echo ======================================
echo.

REM Check Docker installed
echo Checking: Docker Installed...
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker is not installed!
    echo Install from https://www.docker.com/products/docker-desktop
    goto :failed
)
echo OK: Docker CLI is available

REM Check Docker running
echo Checking: Docker Running...
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop
    goto :failed
)
echo OK: Docker daemon is running

REM Check Docker Compose
echo Checking: Docker Compose...
docker-compose --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker Compose is not installed!
    goto :failed
)
echo OK: Docker Compose is available

REM Check Dockerfile
echo Checking: Dockerfile Exists...
if not exist "Dockerfile" (
    echo ERROR: Dockerfile not found in project root
    goto :failed
)
echo OK: Main Dockerfile found

REM Check Frontend Dockerfile
echo Checking: Frontend Dockerfile...
if not exist "frontend\Dockerfile" (
    echo ERROR: frontend\Dockerfile not found
    goto :failed
)
echo OK: Frontend Dockerfile found

REM Check docker-compose.yml
echo Checking: docker-compose.yml...
if not exist "docker-compose.yml" (
    echo ERROR: docker-compose.yml not found
    goto :failed
)
echo OK: Main compose file found

REM Check .env file
echo Checking: Environment File...
if not exist ".env" (
    echo WARNING: .env file not found
    echo Will create from config\env.example when starting Docker
) else (
    echo OK: .env file exists
)

REM Check .dockerignore
echo Checking: .dockerignore...
if not exist ".dockerignore" (
    echo WARNING: .dockerignore not found ^(builds may be slow^)
) else (
    echo OK: .dockerignore found
)

echo.
echo ======================================
echo   Validation Summary
echo ======================================
echo.
echo Docker environment is ready!
echo.
echo Next steps:
echo   1. Review .env file and customize settings
echo   2. Start in development mode:
echo      docker-start-dev.bat
echo.
echo   3. Or start in production mode:
echo      docker-start-prod.bat
echo.
echo Documentation:
echo   - Quick start: DOCKER_QUICKSTART.md
echo   - Full guide: DOCKER_MIGRATION.md
echo.
pause
exit /b 0

:failed
echo.
echo ======================================
echo   Validation Failed
echo ======================================
echo.
echo Please resolve the errors above before running Docker.
echo.
pause
exit /b 1
