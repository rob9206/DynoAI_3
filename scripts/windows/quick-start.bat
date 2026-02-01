@echo off
REM Quick Start - Skips dependency installation for faster startup

echo ======================================
echo DynoAI Quick Start
echo ======================================
echo.

REM Start Flask backend in a new window
echo Starting Flask backend on http://localhost:5001
start "DynoAI Backend" cmd /k "cd /d %~dp0 && python -m api.app"

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
echo Frontend UI:  http://localhost:5173/jetdrive
echo.
echo Close the terminal windows to stop the servers
echo.
pause
