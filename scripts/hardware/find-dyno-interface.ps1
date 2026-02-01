# Find which network interface is connected to the DynoWare RT-150
# The dyno is at 169.254.187.108

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Finding Dyno Network Interface" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

$dynoIP = "169.254.187.108"

Write-Host "[*] Testing connectivity to dyno at $dynoIP..." -ForegroundColor Yellow
Write-Host ""

# Get all network interfaces
$interfaces = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { 
    $_.IPAddress -like "169.254.*"
} | Sort-Object InterfaceIndex

Write-Host "Available 169.254.x.x (link-local) interfaces:" -ForegroundColor Cyan
Write-Host ""

foreach ($iface in $interfaces) {
    $ip = $iface.IPAddress
    $name = $iface.InterfaceAlias
    $index = $iface.InterfaceIndex
    
    Write-Host "  [$index] $name - $ip" -ForegroundColor White
    
    # Check if this interface can reach the dyno
    try {
        $route = Get-NetRoute -DestinationPrefix "$dynoIP/32" -ErrorAction SilentlyContinue
        if ($route) {
            $routeInterface = Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
            if ($routeInterface -and $routeInterface.IPAddress -eq $ip) {
                Write-Host "    [MATCH] This interface has a route to the dyno!" -ForegroundColor Green
            }
        }
    } catch {
        # Ignore errors
    }
}

Write-Host ""
Write-Host "[*] Checking ARP table for dyno MAC address..." -ForegroundColor Yellow
Write-Host ""

# Check ARP table
$arp = arp -a | Select-String $dynoIP
if ($arp) {
    Write-Host "  Found in ARP table:" -ForegroundColor Green
    Write-Host "  $arp" -ForegroundColor White
    Write-Host ""
    Write-Host "  This means the dyno is on the same network segment as one of your interfaces." -ForegroundColor Cyan
} else {
    Write-Host "  Not found in ARP table (may need to ping first)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Recommendation" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "In Power Core JETDRIVE settings, try selecting:" -ForegroundColor Yellow
Write-Host "  1. 'Local Area Connection\* 8 (169.254.9.7)' - if this is the direct connection" -ForegroundColor White
Write-Host "  2. 'Local Area Connection\* 10 (169.254.202.160)' - if this is the direct connection" -ForegroundColor White
Write-Host ""
Write-Host "Since the dyno is at 169.254.187.108, it's likely on the same link-local network" -ForegroundColor Cyan
Write-Host "as one of these Local Area Connection interfaces." -ForegroundColor Cyan
Write-Host ""
Write-Host "Try each one and test with:" -ForegroundColor Yellow
Write-Host "  .\scripts\test-multi-discovery.ps1" -ForegroundColor White
Write-Host ""
