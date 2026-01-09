# Test Network Connectivity to DynoWare RT-150
# This script tests if we can reach the dyno hardware

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Network Connectivity Test" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# IP addresses to test (from config and common addresses)
$dynoIPs = @(
    "169.254.187.108",  # Original link-local IP from config
    "192.168.1.115",   # Common dyno IP from Docker config
    "192.168.1.100",   # Common alternative
    "192.168.1.50"     # Another common alternative
)

Write-Host "[*] Testing connectivity to potential DynoWare RT-150 IPs..." -ForegroundColor Yellow
Write-Host ""

$reachableIPs = @()

foreach ($ip in $dynoIPs) {
    Write-Host "Testing $ip..." -ForegroundColor White
    try {
        $result = Test-Connection -ComputerName $ip -Count 2 -ErrorAction Stop
        Write-Host "  [OK] $ip is reachable" -ForegroundColor Green
        foreach ($ping in $result) {
            Write-Host "    Response time: $($ping.ResponseTime)ms" -ForegroundColor Gray
        }
        $reachableIPs += $ip
    } catch {
        Write-Host "  [FAIL] $ip is not reachable" -ForegroundColor Red
    }
    Write-Host ""
}

# Also check for devices on the local network
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Network Scan" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[*] Scanning local network for devices..." -ForegroundColor Yellow
Write-Host ""

# Get our IP and subnet
$ourIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { 
    $_.IPAddress -notlike "127.*" -and 
    $_.IPAddress -notlike "169.254.*" -and
    $_.IPAddress -notlike "172.*"
} | Select-Object -First 1).IPAddress

if ($ourIP) {
    $subnet = $ourIP -replace "\.\d+$", ""
    Write-Host "Your IP: $ourIP" -ForegroundColor Cyan
    Write-Host "Scanning subnet: $subnet.0/24" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Note: This is a quick scan. For full network discovery, use:" -ForegroundColor Yellow
    Write-Host "  Get-NetNeighbor -AddressFamily IPv4 | Where-Object State -eq 'Reachable'" -ForegroundColor Gray
    Write-Host ""
    
    # Quick scan of common dyno IPs in our subnet
    $subnetIPs = @(
        "$subnet.100",
        "$subnet.101",
        "$subnet.102",
        "$subnet.103",
        "$subnet.104",
        "$subnet.105",
        "$subnet.115",
        "$subnet.150",
        "$subnet.200"
    )
    
    Write-Host "Quick scan of common IPs in your subnet:" -ForegroundColor Yellow
    foreach ($ip in $subnetIPs) {
        if ($ip -ne $ourIP) {
            try {
                $result = Test-Connection -ComputerName $ip -Count 1 -TimeoutSeconds 1 -ErrorAction SilentlyContinue
                if ($result) {
                    Write-Host "  [OK] $ip is reachable" -ForegroundColor Green
                    $reachableIPs += $ip
                }
            } catch {
                # Silently continue
            }
        }
    }
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Summary" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

if ($reachableIPs.Count -gt 0) {
    Write-Host "[OK] Found $($reachableIPs.Count) reachable IP(s):" -ForegroundColor Green
    foreach ($ip in $reachableIPs) {
        Write-Host "  - $ip" -ForegroundColor White
    }
    Write-Host ""
    Write-Host "If one of these is your DynoWare RT-150, update the config:" -ForegroundColor Yellow
    Write-Host "  config/dynoware_rt150.json" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "[WARN] No reachable IPs found" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "This could mean:" -ForegroundColor Yellow
    Write-Host "  1. The dyno is not powered on" -ForegroundColor White
    Write-Host "  2. The dyno is on a different network/subnet" -ForegroundColor White
    Write-Host "  3. The dyno IP address is different from expected" -ForegroundColor White
    Write-Host "  4. Firewall is blocking ICMP (ping) packets" -ForegroundColor White
    Write-Host ""
    Write-Host "Note: Even if ping fails, multicast UDP may still work." -ForegroundColor Cyan
    Write-Host "The multicast address (239.255.60.60) doesn't require direct IP connectivity." -ForegroundColor Cyan
    Write-Host ""
}
