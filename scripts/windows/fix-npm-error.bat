@echo off
REM Fix for corrupted npm/node_modules issue
echo ======================================
echo Fixing NPM Module Error
echo ======================================
echo.

REM Go to repo root (this file lives in scripts\windows)
cd /d "%~dp0\..\.."

echo [1/4] Removing corrupted node_modules...
if exist "frontend\node_modules" (
    echo Deleting frontend\node_modules...
    rmdir /s /q "frontend\node_modules"
    echo Done!
) else (
    echo No node_modules found, skipping...
)

echo.
echo [2/4] Removing package-lock.json...
if exist "frontend\package-lock.json" (
    del /f /q "frontend\package-lock.json"
    echo Done!
) else (
    echo No package-lock.json found, skipping...
)

echo.
echo [3/4] Clearing npm cache...
cd frontend
call npm cache clean --force
echo Done!

echo.
echo [4/4] Reinstalling node_modules (this will take a few minutes)...
call npm install
if errorlevel 1 (
    echo.
    echo ERROR: npm install failed!
    echo Try running this manually:
    echo   cd frontend
    echo   npm install
    pause
    exit /b 1
)

echo.
echo ======================================
echo SUCCESS! Node modules reinstalled
echo ======================================
echo.
echo You can now run:
echo   scripts\windows\quick-start.bat
echo.
pause

