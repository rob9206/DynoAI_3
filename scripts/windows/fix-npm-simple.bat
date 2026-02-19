@echo off
REM Simple fix - just reinstall without deleting
REM Use this if the delete operations are failing

echo ======================================
echo Simple NPM Fix (No Delete)
echo ======================================
echo.

REM Go to frontend/ (this file lives in scripts\windows)
cd /d "%~dp0\..\..\frontend"

echo [1/3] Clearing npm cache...
call npm cache clean --force
echo Done!

echo.
echo [2/3] Installing/updating packages...
echo This will take 2-5 minutes...
call npm install --force
if errorlevel 1 (
    echo.
    echo ERROR: npm install failed!
    pause
    exit /b 1
)

echo.
echo [3/3] Verifying installation...
call npm list --depth=0
echo.

cd ..

echo.
echo ======================================
echo Done! Try starting the app now.
echo ======================================
echo.
echo Run: scripts\windows\quick-start.bat
echo.
pause

