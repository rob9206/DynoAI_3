@echo off
REM DynoAI Development Server Launcher
REM Starts backend first, then frontend

echo.
echo ========================================
echo   DynoAI Development Server Launcher
echo ========================================
echo.

REM Kill existing processes
echo [*] Cleaning up...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM Start backend in new window
echo [^>] Starting Backend API on port 5001...
start "DynoAI Backend" cmd /k "cd /d %~dp0.. && set FLASK_APP=api.app && set JETSTREAM_STUB_MODE=true && python -m flask run --host=0.0.0.0 --port=5001"

REM Wait for backend
echo [*] Waiting for backend...
timeout /t 5 /nobreak >nul

REM Start frontend in new window  
echo [^>] Starting Frontend on port 5000...
start "DynoAI Frontend" cmd /k "cd /d %~dp0..\frontend && npm run dev"

echo.
echo ========================================
echo   Services Starting!
echo ========================================
echo.
echo   Frontend:  http://localhost:5000
echo   Backend:   http://localhost:5001
echo.
echo   Close the terminal windows to stop.
echo.

