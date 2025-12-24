@echo off
REM ======================================================================
REM DynoAI Clean Restart Script
REM Stops all services, clears caches, and restarts everything fresh
REM ======================================================================

color 0E
echo.
echo ======================================================================
echo   DynoAI Clean Restart
echo ======================================================================
echo.
echo [1/6] Stopping all running services...
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
echo [2/6] Clearing Python cache...
echo   [*] Removing __pycache__ directories...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
echo   [*] Removing .pyc files...
del /s /q *.pyc >nul 2>&1
echo   [+] Python cache cleared
echo.

REM Clear Flask logs
echo [3/6] Clearing Flask logs...
if exist flask_debug.log (
    del /q flask_debug.log >nul 2>&1
    echo   [+] Flask logs cleared
) else (
    echo   [*] No Flask logs to clear
)
if exist logs\*.log (
    del /q logs\*.log >nul 2>&1
    echo   [+] Application logs cleared
)
echo.

REM Clear Vite cache
echo [4/6] Clearing Vite cache...
if exist frontend\node_modules\.vite (
    rd /s /q frontend\node_modules\.vite 2>nul
    echo   [+] Vite cache cleared
) else (
    echo   [*] No Vite cache to clear
)
echo.

REM Clear temporary files
echo [5/6] Clearing temporary files...
if exist test_output (
    echo   [*] Clearing test_output...
    rd /s /q test_output 2>nul
)
if exist .pytest_cache (
    echo   [*] Clearing pytest cache...
    rd /s /q .pytest_cache 2>nul
)
echo   [+] Temporary files cleared
echo.

REM Wait a moment for everything to settle
echo [6/6] Waiting for system to settle...
timeout /t 2 /nobreak >nul
echo   [+] Ready to restart
echo.

echo ======================================================================
echo   Cleanup Complete!
echo ======================================================================
echo.
echo Starting DynoAI services...
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

REM Install/update Python dependencies
echo [*] Checking Python dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    color 0E
    echo [WARNING] Some dependencies failed to install, but continuing...
    echo [*] If the app doesn't work, try: pip install -r requirements.txt
    timeout /t 2 /nobreak >nul
)

REM Install/update Node dependencies
echo [*] Checking Node dependencies...
cd frontend
call npm install --silent
if errorlevel 1 (
    color 0E
    echo [WARNING] Some Node dependencies failed to install, but continuing...
    echo [*] If the app doesn't work, try: cd frontend ^&^& npm install
    timeout /t 2 /nobreak >nul
)
cd ..

echo.
color 0A
echo ======================================================================
echo   Dependencies Ready - Starting Services
echo ======================================================================
echo.

REM Start Flask backend in a new window
echo [*] Starting Flask backend on http://localhost:5001
start "DynoAI Backend (Clean)" cmd /k "color 0B && python -m api.app"

REM Wait for backend to initialize
echo [*] Waiting for backend to initialize...
timeout /t 4 /nobreak >nul

REM Start Vite frontend in a new window
echo [*] Starting Vite frontend on http://localhost:5173
cd frontend
start "DynoAI Frontend (Clean)" cmd /k "color 0D && npm run dev"
cd ..

REM Wait for frontend to initialize
timeout /t 3 /nobreak >nul

echo.
color 0A
echo ======================================================================
echo   DynoAI is Running! (Clean Start)
echo ======================================================================
echo.
echo   Backend API:  http://localhost:5001
echo   Frontend UI:  http://localhost:5173
echo.
echo   Performance Tips:
echo   - Close any unnecessary browser tabs
echo   - Check Task Manager for memory usage
echo   - If issues persist, run this script again
echo.
echo   Close the terminal windows to stop the servers
echo   Or run this script again for another clean restart
echo.
echo ======================================================================
color 0F
pause

