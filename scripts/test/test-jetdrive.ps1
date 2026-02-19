#!/usr/bin/env pwsh
# Test JetDrive connection and monitor

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " JetDrive Connection Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$apiBase = "http://localhost:5001/api/jetdrive"

# Test 1: Health check
Write-Host "[1] Testing API health..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:5001/api/health" -Method GET -TimeoutSec 5
    Write-Host "  [OK] API is responding" -ForegroundColor Green
}
catch {
    Write-Host "  [FAIL] API not responding: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Test 2: JetDrive diagnostics
Write-Host "[2] Testing JetDrive diagnostics..." -ForegroundColor Yellow
try {
    $diag = Invoke-RestMethod -Uri "$apiBase/diagnostics" -Method GET -TimeoutSec 5
    Write-Host "  [OK] JetDrive endpoint responding" -ForegroundColor Green
    Write-Host "      Port: $($diag.config.port)" -ForegroundColor Gray
    Write-Host "      Multicast: $($diag.config.multicast_group)" -ForegroundColor Gray
}
catch {
    Write-Host "  [FAIL] Diagnostics failed: $_" -ForegroundColor Red
}
Write-Host ""

# Test 3: Hardware heartbeat
Write-Host "[3] Testing hardware heartbeat..." -ForegroundColor Yellow
try {
    $heartbeat = Invoke-RestMethod -Uri "$apiBase/hardware/heartbeat" -Method GET -TimeoutSec 5
    if ($heartbeat.ok) {
        Write-Host "  [OK] Found $($heartbeat.count) provider(s)" -ForegroundColor Green
        foreach ($provider in $heartbeat.providers) {
            Write-Host "      - $($provider.name) at $($provider.host):$($provider.port)" -ForegroundColor Cyan
            Write-Host "        ID: $($provider.id)" -ForegroundColor Gray
        }
    }
    else {
        Write-Host "  [!] No providers found (dyno may be off or not broadcasting)" -ForegroundColor Yellow
        Write-Host "      Error: $($heartbeat.error)" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "  [FAIL] Heartbeat failed: $_" -ForegroundColor Red
}
Write-Host ""

# Test 4: Start monitor
Write-Host "[4] Starting hardware monitor..." -ForegroundColor Yellow
try {
    $startResult = Invoke-RestMethod -Uri "$apiBase/hardware/monitor/start" -Method POST -TimeoutSec 5
    Write-Host "  [OK] Monitor status: $($startResult.status)" -ForegroundColor Green
    
    # Wait a moment for monitor to run
    Write-Host "  Waiting 5 seconds for monitor data..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
    
    # Check monitor status
    $monitorStatus = Invoke-RestMethod -Uri "$apiBase/hardware/monitor/status" -Method GET -TimeoutSec 5
    Write-Host "  [OK] Monitor running: $($monitorStatus.running)" -ForegroundColor Green
    Write-Host "      Last check: $($monitorStatus.last_check)" -ForegroundColor Gray
    Write-Host "      Connected: $($monitorStatus.connected)" -ForegroundColor $(if ($monitorStatus.connected) { "Green" } else { "Yellow" })
    Write-Host "      Providers: $($monitorStatus.providers.Count)" -ForegroundColor Gray
    
    if ($monitorStatus.providers.Count -gt 0) {
        Write-Host ""
        Write-Host "  Detected providers:" -ForegroundColor Cyan
        foreach ($p in $monitorStatus.providers) {
            Write-Host "    - $($p.name) ($($p.host))" -ForegroundColor White
            Write-Host "      ID: $($p.provider_id)" -ForegroundColor Gray
            Write-Host "      Channels: $($p.channel_count)" -ForegroundColor Gray
        }
    }
}
catch {
    Write-Host "  [FAIL] Monitor failed: $_" -ForegroundColor Red
    Write-Host "      Error details: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host " Test Complete" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
