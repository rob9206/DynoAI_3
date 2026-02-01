# Check JetDrive Status and Configuration

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " JetDrive Status Check" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[*] Checking Power Core processes..." -ForegroundColor Yellow
$powerCore = Get-Process | Where-Object { 
    $_.ProcessName -like '*Power*' -or 
    $_.ProcessName -like '*Dyno*' -or 
    $_.ProcessName -like '*Control*' -or
    $_.ProcessName -like '*WinPEP*'
}

if ($powerCore) {
    Write-Host "  [OK] Power Core is running:" -ForegroundColor Green
    $powerCore | Select-Object ProcessName, Id, StartTime | Format-Table
} else {
    Write-Host "  [WARN] Power Core doesn't appear to be running" -ForegroundColor Yellow
    Write-Host "  JetDrive only broadcasts when Power Core is active" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "[*] Checking for multicast traffic on port 22344..." -ForegroundColor Yellow
Write-Host "  Listening for 5 seconds..." -ForegroundColor Gray

# Try to detect any UDP traffic on port 22344
$listener = [System.Net.Sockets.UdpClient]::new(22344)
$listener.Client.ReceiveTimeout = 5000

$packetsReceived = 0
$startTime = Get-Date
$timeout = 5

try {
    while (((Get-Date) - $startTime).TotalSeconds -lt $timeout) {
        try {
            $endpoint = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, 0)
            $data = $listener.Receive([ref]$endpoint)
            $packetsReceived++
            Write-Host "  [OK] Received packet from $($endpoint.Address):$($endpoint.Port)" -ForegroundColor Green
        } catch {
            # Timeout or no data
            if ($_.Exception.Message -notlike "*timed out*") {
                break
            }
        }
    }
} finally {
    $listener.Close()
}

if ($packetsReceived -eq 0) {
    Write-Host "  [FAIL] No multicast packets received" -ForegroundColor Red
} else {
    Write-Host "  [OK] Received $packetsReceived packet(s)" -ForegroundColor Green
}
Write-Host ""

Write-Host "[*] Checking firewall rules for port 22344..." -ForegroundColor Yellow
$firewallRule = Get-NetFirewallRule | Where-Object { 
    $_.DisplayName -like '*JetDrive*' -or 
    $_.DisplayName -like '*22344*'
} | Select-Object DisplayName, Enabled, Direction, Action

if ($firewallRule) {
    Write-Host "  Found firewall rule(s):" -ForegroundColor Green
    $firewallRule | Format-Table
} else {
    Write-Host "  [WARN] No JetDrive firewall rule found" -ForegroundColor Yellow
    Write-Host "  You may need to add one:" -ForegroundColor Gray
    Write-Host "    New-NetFirewallRule -DisplayName 'JetDrive UDP' -Direction Inbound -Protocol UDP -LocalPort 22344 -Action Allow" -ForegroundColor Gray
}
Write-Host ""

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Recommendations" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

if ($packetsReceived -eq 0) {
    Write-Host "1. In Power Core, check for:" -ForegroundColor Yellow
    Write-Host "   - 'JetDrive Active' indicator in status bar" -ForegroundColor White
    Write-Host "   - Any error messages about JetDrive" -ForegroundColor White
    Write-Host ""
    Write-Host "2. Try clicking 'Configure Channels' in Power Core JETDRIVE settings" -ForegroundColor Yellow
    Write-Host "   - Make sure channels are enabled" -ForegroundColor White
    Write-Host ""
    Write-Host "3. Restart Power Core after changing settings" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "4. Check if there's a multicast address setting elsewhere in Power Core" -ForegroundColor Yellow
    Write-Host "   - Some versions have it in a different location" -ForegroundColor White
    Write-Host ""
}

Write-Host "5. Test discovery again:" -ForegroundColor Yellow
Write-Host "   .\scripts\test-multi-discovery.ps1" -ForegroundColor White
Write-Host ""
