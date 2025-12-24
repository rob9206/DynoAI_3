@echo off
REM DynoAI Development Startup Script for Windows
REM Starts both backend (Flask) and frontend (Vite) servers

echo ======================================
echo Starting DynoAI Development Servers
echo ======================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
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
call npm install --silent
cd ..

echo.
echo Dependencies installed
echo.

REM Start Flask backend in a new window
echo Starting Flask backend on http://localhost:5001
start "DynoAI Backend" cmd /k "python -m api.app"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start Vite frontend in a new window
echo Starting Vite frontend on http://localhost:5173
cd frontend
start "DynoAI Frontend" cmd /k "npm run dev"
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
