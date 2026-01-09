# Test JetDrive Multicast Connection
# This script helps diagnose why DynoWare RT-150 data isn't being received

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " JetDrive Multicast Diagnostic Test" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check current configuration
$mcastGroup = $env:JETDRIVE_MCAST_GROUP
if (-not $mcastGroup) {
    $mcastGroup = "224.0.2.10"
    Write-Host "[INFO] Using default multicast group: $mcastGroup" -ForegroundColor Yellow
} else {
    Write-Host "[INFO] Using multicast group from env: $mcastGroup" -ForegroundColor Yellow
}

$port = $env:JETDRIVE_PORT
if (-not $port) {
    $port = "22344"
}

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Multicast Group: $mcastGroup" -ForegroundColor White
Write-Host "  Port: $port" -ForegroundColor White
Write-Host ""

# Check network interfaces
Write-Host "Network Interfaces:" -ForegroundColor Cyan
$interfaces = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }
foreach ($iface in $interfaces) {
    Write-Host "  - $($iface.IPAddress) ($($iface.InterfaceAlias))" -ForegroundColor White
}
Write-Host ""

# Check firewall
Write-Host "Firewall Check:" -ForegroundColor Cyan
$firewallRule = Get-NetFirewallRule -DisplayName "*JetDrive*" -ErrorAction SilentlyContinue
if ($firewallRule) {
    Write-Host "  [OK] Firewall rule found for JetDrive" -ForegroundColor Green
} else {
    Write-Host "  [WARN] No firewall rule found. You may need to add one:" -ForegroundColor Yellow
    Write-Host "    New-NetFirewallRule -DisplayName 'JetDrive UDP' -Direction Inbound -Protocol UDP -LocalPort $port -Action Allow" -ForegroundColor Gray
}
Write-Host ""

# Test multicast group (try both common ones)
Write-Host "Testing Multicast Groups:" -ForegroundColor Cyan
$testGroups = @("224.0.2.10", "239.255.60.60")
foreach ($group in $testGroups) {
    Write-Host "  Testing $group:$port..." -ForegroundColor White
    try {
        $result = Test-NetConnection -ComputerName $group -Port $port -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
        if ($result.TcpTestSucceeded -or $result.PingSucceeded) {
            Write-Host "    [OK] Connection test passed" -ForegroundColor Green
        } else {
            Write-Host "    [INFO] Connection test inconclusive (this is normal for multicast)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "    [INFO] Connection test inconclusive (this is normal for multicast)" -ForegroundColor Yellow
    }
}
Write-Host ""

# Check if DynoWare RT-150 is reachable
$dynoIP = $env:DYNO_IP
if (-not $dynoIP) {
    $dynoIP = "239.255.60.60"  # From config
    Write-Host "[INFO] Using default DynoWare IP: $dynoIP" -ForegroundColor Yellow
}

Write-Host "Testing DynoWare RT-150 Connection:" -ForegroundColor Cyan
Write-Host "  IP: $dynoIP" -ForegroundColor White
try {
    $ping = Test-Connection -ComputerName $dynoIP -Count 2 -Quiet
    if ($ping) {
        Write-Host "  [OK] DynoWare RT-150 is reachable" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Cannot reach DynoWare RT-150 at $dynoIP" -ForegroundColor Red
        Write-Host "    Check:" -ForegroundColor Yellow
        Write-Host "    1. DynoWare RT-150 is powered on" -ForegroundColor Gray
        Write-Host "    2. Both devices are on the same network" -ForegroundColor Gray
        Write-Host "    3. Network cable is connected" -ForegroundColor Gray
    }
} catch {
    Write-Host "  [ERROR] Cannot ping DynoWare RT-150: $_" -ForegroundColor Red
}
Write-Host ""

# Recommendations
Write-Host "Recommendations:" -ForegroundColor Cyan
Write-Host "  1. Verify the multicast group in Power Core settings matches: $mcastGroup" -ForegroundColor White
Write-Host "  2. Try setting JETDRIVE_IFACE to your computer's IP address (not 0.0.0.0)" -ForegroundColor White
Write-Host "  3. Ensure JetDrive is enabled in Power Core software" -ForegroundColor White
Write-Host "  4. Check that Power Core is running and shows 'JetDrive Active'" -ForegroundColor White
Write-Host "  5. Try both multicast groups:" -ForegroundColor White
Write-Host "     - 224.0.2.10 (default)" -ForegroundColor Gray
Write-Host "     - 239.255.60.60 (Docker config)" -ForegroundColor Gray
Write-Host ""

Write-Host "To test with a specific interface, set:" -ForegroundColor Yellow
Write-Host "  `$env:JETDRIVE_IFACE = 'YOUR_IP_ADDRESS'" -ForegroundColor Gray
Write-Host "  `$env:JETDRIVE_MCAST_GROUP = '224.0.2.10'  # or '239.255.60.60'" -ForegroundColor Gray
Write-Host ""
