@echo off
REM ======================================================================
REM DynoAI Quick Restart Script
REM Stops all services and restarts WITHOUT reinstalling dependencies
REM Use this for faster restarts when dependencies are already installed
REM ======================================================================

color 0E
echo.
echo ======================================================================
echo   DynoAI Quick Restart (No Dependency Install)
echo ======================================================================
echo.
echo [1/5] Stopping all running services...
echo.

REM Kill all Python processes (Flask backend)
echo   [*] Stopping Python/Flask processes...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
timeout /t 1 /nobreak >nul

REM Kill all Node processes (Vite frontend)
echo   [*] Stopping Node/Vite processes...
taskkill /F /IM node.exe >nul 2>&1
taskkill /F /IM npm.cmd >nul 2>&1
timeout /t 1 /nobreak >nul

REM Kill processes on specific ports
echo   [*] Freeing up ports 5001 and 5173...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5001') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173') do taskkill /F /PID %%a >nul 2>&1
timeout /t 1 /nobreak >nul

echo   [+] All services stopped
echo.

REM Clear Python cache
echo [2/5] Clearing Python cache...
echo   [*] Removing __pycache__ directories...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
echo   [*] Removing .pyc files...
del /s /q *.pyc >nul 2>&1
echo   [+] Python cache cleared
echo.

REM Clear Flask logs
echo [3/5] Clearing Flask logs...
if exist flask_debug.log (
    del /q flask_debug.log >nul 2>&1
    echo   [+] Flask logs cleared
) else (
    echo   [*] No Flask logs to clear
)
echo.

REM Clear Vite cache
echo [4/5] Clearing Vite cache...
if exist frontend\node_modules\.vite (
    rd /s /q frontend\node_modules\.vite 2>nul
    echo   [+] Vite cache cleared
) else (
    echo   [*] No Vite cache to clear
)
echo.

REM Wait a moment for everything to settle
echo [5/5] Waiting for system to settle...
timeout /t 2 /nobreak >nul
echo   [+] Ready to restart
echo.

echo ======================================================================
echo   Cleanup Complete - Starting Services
echo ======================================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERROR] Python not found. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERROR] Node.js not found. Please install Node.js 18 or higher.
    pause
    exit /b 1
)

color 0A
echo ======================================================================
echo   Starting Services (Quick Mode)
echo ======================================================================
echo.

REM Start Flask backend in a new window
echo [*] Starting Flask backend on http://localhost:5001
start "DynoAI Backend (Quick)" cmd /k "color 0B && python api/app.py"

REM Wait for backend to initialize
echo [*] Waiting for backend to initialize...
timeout /t 3 /nobreak >nul

REM Start Vite frontend in a new window
echo [*] Starting Vite frontend on http://localhost:5173
cd frontend
start "DynoAI Frontend (Quick)" cmd /k "color 0D && npm run dev"
cd ..

REM Wait for frontend to initialize
timeout /t 2 /nobreak >nul

echo.
color 0A
echo ======================================================================
echo   DynoAI is Running! (Quick Start)
echo ======================================================================
echo.
echo   Backend API:  http://localhost:5001
echo   Frontend UI:  http://localhost:5173
echo.
echo   Note: This quick restart skips dependency installation
echo   If you have issues, run: restart-clean.bat
echo.
echo   Close the terminal windows to stop the servers
echo.
echo ======================================================================
color 0F
pause

