@echo off
REM JetDrive IP Configuration Update Script
REM Use this to quickly update your computer's IP address for JetDrive

echo ========================================
echo JetDrive IP Configuration Helper
echo ========================================
echo.
echo This script helps you update your computer's IP address
echo for JetDrive communication with the dyno.
echo.
echo ========================================
echo Current Network Configuration:
echo ========================================
echo.

REM Show current IP addresses
ipconfig | findstr /C:"IPv4 Address"

echo.
echo ========================================
echo Current JetDrive Configuration:
echo ========================================
echo.

REM Show current setting from start-jetdrive.ps1
findstr /C:"ComputerIP" start-jetdrive.ps1 | findstr /V /C:"#"

echo.
echo ========================================
echo.
echo What would you like to do?
echo.
echo 1. Update computer IP address (permanent)
echo 2. Show full network info (ipconfig)
echo 3. Test current configuration
echo 4. Cancel
echo.

set /p choice="Enter choice (1-4): "

if "%choice%"=="1" (
    echo.
    echo Enter your computer's NEW IP address.
    echo This should be the WiFi adapter IP shown above.
    echo.
    set /p newip="Your computer's IP (e.g., 192.168.1.100): "
    
    echo.
    echo Updating start-jetdrive.ps1...
    
    REM Use PowerShell to update the file
    powershell -Command "(Get-Content start-jetdrive.ps1) -replace 'ComputerIP = \"[0-9.]+\"', 'ComputerIP = \"%newip%\"' | Set-Content start-jetdrive.ps1"
    
    echo.
    echo ========================================
    echo SUCCESS! Updated configuration
    echo ========================================
    echo.
    echo   Old IP: 192.168.1.81
    echo   New IP: %newip%
    echo.
    echo You can now run: start-jetdrive.bat
    echo.
    pause
    exit /b 0
)

if "%choice%"=="2" (
    echo.
    echo ========================================
    echo Full Network Configuration:
    echo ========================================
    echo.
    ipconfig
    echo.
    pause
    exit /b 0
)

if "%choice%"=="3" (
    echo.
    echo ========================================
    echo Testing Configuration
    echo ========================================
    echo.
    echo Current JetDrive Settings:
    findstr /C:"ComputerIP\|DynoIP" start-jetdrive.ps1 | findstr /V /C:"#"
    echo.
    echo Your Network Adapters:
    ipconfig | findstr /C:"adapter\|IPv4"
    echo.
    echo TIP: Your ComputerIP should match one of the IPv4 addresses above
    echo      (Usually the WiFi adapter IP)
    echo.
    pause
    exit /b 0
)

echo.
echo Cancelled. No changes made.
echo.
pause
