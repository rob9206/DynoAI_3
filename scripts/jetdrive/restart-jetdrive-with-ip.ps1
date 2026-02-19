# Restart JetDrive with correct IP configuration
# This script stops any running backend and restarts it with your IP address

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Restarting JetDrive with IP Config" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to project root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

# Stop any running Python processes that might be the backend
Write-Host "[*] Stopping any running backend processes..." -ForegroundColor Yellow
$pythonProcs = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*DynoAI_3*" -or $_.CommandLine -like "*api.app*"
}
if ($pythonProcs) {
    foreach ($proc in $pythonProcs) {
        Write-Host "  Stopping process $($proc.Id)..." -ForegroundColor Gray
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    Write-Host "  [OK] Stopped" -ForegroundColor Green
} else {
    Write-Host "  [INFO] No running backend found" -ForegroundColor Gray
}
Write-Host ""

# Get your IP address
Write-Host "[*] Detecting your IP address..." -ForegroundColor Yellow
$yourIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { 
    $_.IPAddress -notlike "127.*" -and 
    $_.IPAddress -notlike "169.254.*" -and
    $_.IPAddress -notlike "172.*"
} | Select-Object -First 1).IPAddress

if (-not $yourIP) {
    # Fallback method
    $yourIP = (ipconfig | Select-String "IPv4" | Select-Object -First 1) -replace ".*:\s*", ""
    $yourIP = $yourIP.Trim()
}

if ($yourIP) {
    Write-Host "  [OK] Found IP: $yourIP" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Could not detect IP address" -ForegroundColor Red
    Write-Host "  Please set JETDRIVE_IFACE manually" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Set environment variables
Write-Host "[*] Setting environment variables..." -ForegroundColor Yellow
$env:JETDRIVE_IFACE = $yourIP
$env:JETDRIVE_MCAST_GROUP = "239.255.60.60"  # Multicast group
$env:JETDRIVE_PORT = "22344"

# Also set DynoWare RT-150 IP (from memory/config)
$env:DYNO_IP = "239.255.60.60"

Write-Host "  JETDRIVE_IFACE = $env:JETDRIVE_IFACE" -ForegroundColor Cyan
Write-Host "  JETDRIVE_MCAST_GROUP = $env:JETDRIVE_MCAST_GROUP" -ForegroundColor Cyan
Write-Host "  JETDRIVE_PORT = $env:JETDRIVE_PORT" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "[ERROR] Virtual environment not found. Run start-jetdrive.ps1 first." -ForegroundColor Red
    exit 1
}

# Activate virtual environment
Write-Host "[*] Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
Write-Host "  [OK] Activated" -ForegroundColor Green
Write-Host ""

Write-Host "======================================" -ForegroundColor Green
Write-Host " Starting Backend with IP Config" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Your IP:         $env:JETDRIVE_IFACE" -ForegroundColor Cyan
Write-Host "  Multicast Group: $env:JETDRIVE_MCAST_GROUP" -ForegroundColor Cyan
Write-Host "  Port:            $env:JETDRIVE_PORT" -ForegroundColor Cyan
Write-Host "  Dyno IP:        $env:DYNO_IP" -ForegroundColor Cyan
Write-Host ""
Write-Host "  API: http://localhost:5001" -ForegroundColor Cyan
Write-Host "  Debug: http://localhost:5001/api/jetdrive/hardware/live/debug" -ForegroundColor Gray
Write-Host ""
Write-Host "  Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Start the backend
python -m api.app
