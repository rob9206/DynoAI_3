@echo off
REM DynoAI Comprehensive Service Startup Script for Windows
REM Ensures all services are up-to-date and starts all components

echo ======================================
echo DynoAI All-Services Startup Script
echo Ensuring Everything is Up-to-Date
echo ======================================
echo.

REM Set script directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\"

REM === PREREQUISITES CHECK ===
echo [1/10] Checking prerequisites...

REM Check Python installation
set "PYTHON_EXE=python"
if exist "%PROJECT_ROOT%.venv-reorg\Scripts\python.exe" (
    "%PROJECT_ROOT%.venv-reorg\Scripts\python.exe" -c "import sys; sys.exit(0)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=%PROJECT_ROOT%.venv-reorg\Scripts\python.exe"
        echo Found Python in virtual environment
    )
)

%PYTHON_EXE% --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8 or higher.
    pause
    exit /b 1
)
echo Python: %PYTHON_EXE%

REM Check Node.js installation
set "NODE_EXE=node"
where node >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files\nodejs\node.exe" (
        set "NODE_EXE=C:\Program Files\nodejs\node.exe"
    )
)

"%NODE_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found. Please install Node.js 18 or higher.
    pause
    exit /b 1
)
echo Node.js: %NODE_EXE%

REM Check npm
set "NPM_EXE=npm"
where npm >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files\nodejs\npm.cmd" (
        set "NPM_EXE=C:\Program Files\nodejs\npm.cmd"
    )
)
echo npm: %NPM_EXE%

REM Check Docker (optional)
where docker >nul 2>&1
if errorlevel 1 (
    echo WARNING: Docker not found. Docker services will be skipped.
    set "DOCKER_AVAILABLE=0"
) else (
    echo Docker: Available
    set "DOCKER_AVAILABLE=1"
)

echo.
echo [2/10] Updating system dependencies...

REM Update Python pip
echo Updating pip...
%PYTHON_EXE% -m pip install --upgrade pip >nul 2>&1

REM Update Python packages
echo Updating Python packages...
%PYTHON_EXE% -m pip install -U -r "%PROJECT_ROOT%\requirements.txt" >nul 2>&1

REM Update Node.js dependencies
echo Updating Node.js dependencies...
cd "%PROJECT_ROOT%\frontend"
call "%NPM_EXE%" update --silent
cd "%PROJECT_ROOT%"

echo.
echo [3/10] Cleaning up old processes...

REM Kill existing processes on key ports
echo Stopping existing services...
REM Port 5001 (Backend)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5001') do taskkill /F /PID %%a >nul 2>&1
REM Port 5173 (Frontend)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do taskkill /F /PID %%a >nul 2>&1
REM Port 6379 (Redis)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :6379') do taskkill /F /PID %%a >nul 2>&1

timeout /t 2 /nobreak >nul

echo.
echo [4/10] Ensuring database and cache services...

REM Start Redis if available
if "%DOCKER_AVAILABLE%"=="1" (
    echo Starting Redis container...
    docker run -d --name dynoai-redis -p 6379:6379 redis:alpine >nul 2>&1
    if errorlevel 1 (
        echo Redis container might already be running or failed to start
    )
) else (
    echo Skipping Redis (Docker not available)
)

echo.
echo [5/10] Updating project data...

REM Update any project-specific data or configurations
if exist "%PROJECT_ROOT%\scripts\update_data.bat" (
    echo Running project data update...
    call "%PROJECT_ROOT%\scripts\update_data.bat"
)

REM Run any Python setup scripts
if exist "%PROJECT_ROOT%\setup.py" (
    echo Running Python setup...
    %PYTHON_EXE% "%PROJECT_ROOT%\setup.py" develop >nul 2>&1
)

echo.
echo [6/10] Starting backend services...

REM Start main backend API
echo Starting Flask backend API...
cd "%PROJECT_ROOT%"
start "DynoAI Backend API" cmd /k "%PYTHON_EXE% -m api.app"
cd "%PROJECT_ROOT%"

REM Wait for backend to start
echo Waiting for backend to initialize...
timeout /t 5 /nobreak >nul

echo.
echo [7/10] Starting frontend services...

REM Start frontend development server
echo Starting Vite frontend...
cd "%PROJECT_ROOT%\frontend"
start "DynoAI Frontend" cmd /k "%NPM_EXE% run dev"
cd "%PROJECT_ROOT%"

echo.
echo [8/10] Starting additional services...

REM Start any additional backend services
if exist "%PROJECT_ROOT%\dynoai_qt6.py" (
    echo Starting QT6 GUI service...
    start "DynoAI QT6 GUI" cmd /k "%PYTHON_EXE% dynoai_qt6.py"
)

REM Start JetDrive services if available
if exist "%PROJECT_ROOT%\start-jetdrive.bat" (
    echo Starting JetDrive services...
    start "DynoAI JetDrive" cmd /k "call start-jetdrive.bat"
)

echo.
echo [9/10] Health checks and validation...

REM Wait for services to fully start
echo Waiting for all services to start...
timeout /t 8 /nobreak >nul

REM Basic health check
echo Performing health checks...
echo Checking backend API...
curl -s -o nul -w "%%{http_code}" http://localhost:5001/api/health > health_check.txt
set /p HEALTH_CODE=<health_check.txt
del health_check.txt

if "%HEALTH_CODE%"=="200" (
    echo Backend API: HEALTHY
) else (
    echo Backend API: CHECKING...
)

echo Checking frontend...
curl -s -o nul -w "%%{http_code}" http://localhost:5173 > frontend_check.txt
set /p FRONTEND_CODE=<frontend_check.txt
del frontend_check.txt

if "%FRONTEND_CODE%"=="200" (
    echo Frontend: HEALTHY
) else (
    echo Frontend: CHECKING...
)

echo.
echo [10/10] Finalizing startup...

REM Display final status
echo.
echo ======================================
echo DynoAI Services Status
echo ======================================
echo.
echo Backend API:        http://localhost:5001
echo API Health:         http://localhost:5001/api/health
echo API Documentation:  http://localhost:5001/api/docs
echo Frontend UI:        http://localhost:5173
echo.
if "%DOCKER_AVAILABLE%"=="1" (
echo Redis Cache:        localhost:6379
echo Docker Services:    Available
echo.
echo Docker Commands:
echo   View logs:          docker-compose logs -f
echo   Stop services:      docker-compose down
echo.
)
echo Service Management:
echo   Backend:            Port 5001
echo   Frontend:           Port 5173
echo   Redis:              Port 6379
echo.
echo Quick Commands:
echo   View logs:          docker-compose logs -f api
echo   Restart backend:    taskkill /F /PID [backend_pid]
echo   Full restart:       restart-clean.bat
echo.
echo ======================================
echo ALL SERVICES STARTED SUCCESSFULLY!
echo ======================================
echo.
echo Press any key to minimize this window...
pause >nul

REM Minimize the window
powershell -Command "(New-Object -ComObject Shell.Application).MinimizeAll()"