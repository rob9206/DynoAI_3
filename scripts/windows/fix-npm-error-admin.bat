@echo off
REM Fix for corrupted npm/node_modules issue - ADMIN VERSION
REM Run this as Administrator if fix-npm-error.bat fails

echo ======================================
echo Fixing NPM Module Error (Admin Mode)
echo ======================================
echo.

REM Check if running as admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo.
    echo Right-click this file and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

REM Go to repo root (this file lives in scripts\windows)
cd /d "%~dp0\..\.."

echo [0/5] Stopping any running Node/npm processes...
taskkill /F /IM node.exe >nul 2>&1
taskkill /F /IM npm.exe >nul 2>&1
timeout /t 2 /nobreak >nul
echo Done!

echo.
echo [1/5] Taking ownership of node_modules...
if exist "frontend\node_modules" (
    takeown /F "frontend\node_modules" /R /D Y >nul 2>&1
    icacls "frontend\node_modules" /grant %username%:F /T /C /Q >nul 2>&1
    echo Done!
) else (
    echo No node_modules found, skipping...
)

echo.
echo [2/5] Removing corrupted node_modules (this may take a minute)...
if exist "frontend\node_modules" (
    echo Deleting frontend\node_modules...
    rmdir /s /q "frontend\node_modules" 2>nul
    if exist "frontend\node_modules" (
        echo Some files couldn't be deleted, trying harder...
        rd /s /q "frontend\node_modules" 2>nul
    )
    if exist "frontend\node_modules" (
        echo WARNING: Some files still remain, but continuing anyway...
    ) else (
        echo Done!
    )
) else (
    echo No node_modules found, skipping...
)

echo.
echo [3/5] Removing package-lock.json...
if exist "frontend\package-lock.json" (
    del /f /q "frontend\package-lock.json"
    echo Done!
) else (
    echo No package-lock.json found, skipping...
)

echo.
echo [4/5] Clearing npm cache...
cd frontend
call npm cache clean --force
echo Done!

echo.
echo [5/5] Reinstalling node_modules (this will take 2-5 minutes)...
echo Please be patient, do not close this window...
call npm install
if errorlevel 1 (
    echo.
    echo ERROR: npm install failed!
    echo.
    echo Try these steps:
    echo 1. Check your internet connection
    echo 2. Disable antivirus temporarily
    echo 3. Run: npm install --verbose (to see detailed errors)
    echo.
    pause
    exit /b 1
)

cd ..

echo.
echo ======================================
echo SUCCESS! Node modules reinstalled
echo ======================================
echo.
echo You can now run:
echo   scripts\windows\quick-start.bat
echo.
pause

