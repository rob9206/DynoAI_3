# Auto-Configure JetDrive Network Interface
# This script detects your computer's IP address and sets JETDRIVE_IFACE automatically

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " JetDrive Auto-Configuration" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to project root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

# Get your IP address
Write-Host "[*] Detecting network interface..." -ForegroundColor Yellow

# Try to get the primary network interface (not loopback, not link-local, not Docker)
$interfaces = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { 
    $_.IPAddress -notlike "127.*" -and 
    $_.IPAddress -notlike "169.254.*" -and
    $_.IPAddress -notlike "172.17.*" -and
    $_.IPAddress -notlike "172.18.*" -and
    $_.IPAddress -notlike "172.19.*" -and
    $_.IPAddress -notlike "172.20.*" -and
    $_.IPAddress -notlike "172.21.*" -and
    $_.IPAddress -notlike "172.22.*" -and
    $_.IPAddress -notlike "172.23.*" -and
    $_.IPAddress -notlike "172.24.*" -and
    $_.IPAddress -notlike "172.25.*" -and
    $_.IPAddress -notlike "172.26.*" -and
    $_.IPAddress -notlike "172.27.*" -and
    $_.IPAddress -notlike "172.28.*" -and
    $_.IPAddress -notlike "172.29.*" -and
    $_.IPAddress -notlike "172.30.*" -and
    $_.IPAddress -notlike "172.31.*"
} | Sort-Object -Property InterfaceIndex

if (-not $interfaces) {
    Write-Host "  [ERROR] Could not detect network interface" -ForegroundColor Red
    Write-Host "  Please set JETDRIVE_IFACE manually" -ForegroundColor Yellow
    exit 1
}

# Show all available interfaces
Write-Host ""
Write-Host "Available network interfaces:" -ForegroundColor Cyan
$interfaceList = @()
foreach ($iface in $interfaces) {
    $info = [PSCustomObject]@{
        Index = $iface.InterfaceIndex
        IP = $iface.IPAddress
        Name = $iface.InterfaceAlias
    }
    $interfaceList += $info
    Write-Host "  [$($iface.InterfaceIndex)] $($iface.IPAddress) - $($iface.InterfaceAlias)" -ForegroundColor White
}

# Select the first non-loopback interface (usually the primary)
$selectedInterface = $interfaces[0]
$selectedIP = $selectedInterface.IPAddress

Write-Host ""
Write-Host "[*] Selected interface: $selectedIP ($($selectedInterface.InterfaceAlias))" -ForegroundColor Green
Write-Host ""

# Set environment variables
Write-Host "[*] Setting environment variables..." -ForegroundColor Yellow
$env:JETDRIVE_IFACE = $selectedIP
$env:JETDRIVE_MCAST_GROUP = "239.255.60.60"
$env:JETDRIVE_PORT = "22344"
$env:DYNO_IP = "239.255.60.60"

Write-Host "  JETDRIVE_IFACE = $env:JETDRIVE_IFACE" -ForegroundColor Cyan
Write-Host "  JETDRIVE_MCAST_GROUP = $env:JETDRIVE_MCAST_GROUP" -ForegroundColor Cyan
Write-Host "  JETDRIVE_PORT = $env:JETDRIVE_PORT" -ForegroundColor Cyan
Write-Host "  DYNO_IP = $env:DYNO_IP" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "[WARN] Virtual environment not found. Run start-jetdrive.ps1 first." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Configuration saved to environment variables for this session." -ForegroundColor Green
    Write-Host "To make permanent, add these to your .env file or set them in PowerShell profile." -ForegroundColor Gray
    exit 0
}

# Activate virtual environment
Write-Host "[*] Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
Write-Host "  [OK] Activated" -ForegroundColor Green
Write-Host ""

Write-Host "======================================" -ForegroundColor Green
Write-Host " Configuration Complete" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
Write-Host "Network Interface: $selectedIP" -ForegroundColor Cyan
Write-Host "Multicast Group:   $env:JETDRIVE_MCAST_GROUP" -ForegroundColor Cyan
Write-Host "Port:              $env:JETDRIVE_PORT" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Verify Power Core is configured to broadcast to $env:JETDRIVE_MCAST_GROUP:$env:JETDRIVE_PORT" -ForegroundColor White
Write-Host "  2. Ensure JetDrive is enabled in Power Core software" -ForegroundColor White
Write-Host "  3. Test discovery: curl http://localhost:5001/api/jetdrive/hardware/discover/multi" -ForegroundColor White
Write-Host "  4. Start the backend: python -m api.app" -ForegroundColor White
Write-Host ""
