@echo off
REM DynoAI Development Startup Script for Windows
REM Starts both backend (Flask) and frontend (Vite) servers

echo ======================================
echo Starting DynoAI Development Servers
echo ======================================
echo.

REM Resolve Python executable (prefer venv-reorg if valid)
set "PYTHON_EXE=python"
if exist "%~dp0..\.venv-reorg\Scripts\python.exe" (
    "%~dp0..\.venv-reorg\Scripts\python.exe" -c "import sys; sys.exit(0)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=%~dp0..\.venv-reorg\Scripts\python.exe"
    )
)

REM Check if Python is installed
%PYTHON_EXE% --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

REM Resolve Node.js executable (prefer PATH, fallback to default install)
set "NODE_EXE=node"
where node >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files\nodejs\node.exe" (
        set "NODE_EXE=C:\Program Files\nodejs\node.exe"
    )
)

REM Resolve npm executable (prefer PATH, fallback to default install)
set "NPM_EXE=npm"
where npm >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files\nodejs\npm.cmd" (
        set "NPM_EXE=C:\Program Files\nodejs\npm.cmd"
    )
)

REM Check if Node.js is installed
"%NODE_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo Node.js not found. Please install Node.js 18 or higher.
    pause
    exit /b 1
)

REM Install Python dependencies
echo Installing Python dependencies...
pip install -q -r requirements.txt

REM Install Node dependencies
echo Installing Node dependencies...
cd frontend
call "%NPM_EXE%" install --silent
cd ..

echo.
echo Dependencies installed
echo.

REM Start Flask backend in a new window
echo Starting Flask backend on http://localhost:5001
start "DynoAI Backend" cmd /k "cd /d %~dp0.. && %PYTHON_EXE% -m api.app"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start Vite frontend in a new window
echo Starting Vite frontend on http://localhost:5173
cd frontend
start "DynoAI Frontend" cmd /k ""%NPM_EXE%" run dev"
cd ..

echo.
echo ======================================
echo DynoAI is running!
echo ======================================
echo.
echo Backend API:  http://localhost:5001
echo Frontend UI:  http://localhost:5173
echo.
echo Close the terminal windows to stop the servers
echo.
pause
