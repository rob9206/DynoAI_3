# Quick script to reconnect Innovate DLG-1
Write-Host "Reconnecting Innovate DLG-1..." -ForegroundColor Cyan

# Disconnect first
try {
    Invoke-RestMethod -Uri "http://localhost:5001/api/jetdrive/innovate/disconnect" -Method POST -ErrorAction SilentlyContinue | Out-Null
    Write-Host "Disconnected" -ForegroundColor Yellow
    Start-Sleep -Seconds 1
} catch {}

# Connect
Write-Host "Connecting to COM5..." -ForegroundColor Cyan
$body = '{"port":"COM5","device_type":"DLG-1"}'
$result = Invoke-RestMethod -Uri "http://localhost:5001/api/jetdrive/innovate/connect" -Method POST -ContentType "application/json" -Body $body

if ($result.success) {
    Write-Host "Connected!" -ForegroundColor Green
    Start-Sleep -Seconds 3
    
    # Check status
    $status = Invoke-RestMethod -Uri "http://localhost:5001/api/jetdrive/innovate/status" -Method GET
    Write-Host "Streaming: $($status.streaming)" -ForegroundColor White
    Write-Host "Has Samples: $($status.has_samples)" -ForegroundColor White
    
    if ($status.samples.channel_1) {
        Write-Host "Channel 1: AFR=$($status.samples.channel_1.afr)" -ForegroundColor Cyan
    }
    if ($status.samples.channel_2) {
        Write-Host "Channel 2: AFR=$($status.samples.channel_2.afr)" -ForegroundColor Green
    }
} else {
    Write-Host "Failed: $($result.error)" -ForegroundColor Red
}
