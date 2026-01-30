@echo off
REM JetDrive Starter - Wrapper for start-jetdrive.ps1
REM This batch file bypasses PowerShell execution policy restrictions
REM 
REM Usage:
REM   start-jetdrive.bat                    - Use default IP (192.168.1.81)
REM   start-jetdrive.bat 192.168.1.100     - Use custom computer IP

echo ========================================
echo Starting JetDrive Live Capture
echo ========================================
echo.

REM Check if custom IP provided
if "%~1"=="" (
    echo Using default computer IP: 192.168.1.81
    echo.
    echo To use a different IP, run:
    echo   start-jetdrive.bat YOUR_IP
    echo   Example: start-jetdrive.bat 192.168.1.100
    echo.
    REM Run PowerShell script with execution policy bypass (no custom IP)
    powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%~dp0start-jetdrive.ps1"
) else (
    echo Using custom computer IP: %~1
    echo.
    REM Run PowerShell script with execution policy bypass and custom IP parameter
    powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%~dp0start-jetdrive.ps1" -ComputerIP "%~1"
)

REM Check if script failed
if errorlevel 1 (
    echo.
    echo ========================================
    echo ERROR: Failed to start JetDrive
    echo ========================================
    echo.
    echo Troubleshooting:
    echo   1. Check Python is installed: python --version
    echo   2. Check network connection to dyno
    echo   3. Verify your computer's IP address: ipconfig
    echo   4. Update IP if changed
    echo.
    echo Your current IP addresses:
    ipconfig | findstr /C:"IPv4 Address"
    echo.
    echo To update IP:
    echo   Option 1: Run with IP parameter
    echo             start-jetdrive.bat YOUR_NEW_IP
    echo.
    echo   Option 2: Edit start-jetdrive.ps1 line 6
    echo             Change ComputerIP = "192.168.1.81" to your IP
    echo.
    echo   Option 3: Run update helper
    echo             update-jetdrive-ip.bat
    echo.
    pause
    exit /b 1
)
