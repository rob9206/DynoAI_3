# Test Multi-Discovery Endpoint
# This script tests the new multi-discovery endpoint

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Testing Multi-Discovery Endpoint" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Set environment variables
$env:JETDRIVE_IFACE = "192.168.1.86"
$env:JETDRIVE_MCAST_GROUP = "239.255.60.60"
$env:JETDRIVE_PORT = "22344"

Write-Host "[*] Waiting for backend to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host "[*] Testing multi-discovery endpoint..." -ForegroundColor Yellow
Write-Host ""

try {
    $response = Invoke-RestMethod -Uri "http://localhost:5001/api/jetdrive/hardware/discover/multi?timeout=5" -TimeoutSec 15
    
    Write-Host "Results:" -ForegroundColor Green
    Write-Host ""
    
    # Display results for each multicast address
    foreach ($mcastGroup in $response.results.PSObject.Properties.Name) {
        $result = $response.results.$mcastGroup
        Write-Host "Multicast Address: $mcastGroup" -ForegroundColor Cyan
        Write-Host "  Success: $($result.success)" -ForegroundColor $(if ($result.success) { "Green" } else { "Red" })
        Write-Host "  Providers Found: $($result.providers_found)" -ForegroundColor White
        
        if ($result.providers.Count -gt 0) {
            Write-Host "  Providers:" -ForegroundColor Yellow
            foreach ($provider in $result.providers) {
                Write-Host "    - $($provider.name) (ID: $($provider.provider_id_hex), Host: $($provider.host))" -ForegroundColor White
                Write-Host "      Channels: $($provider.channel_count)" -ForegroundColor Gray
            }
        }
        
        if ($result.error) {
            Write-Host "  Error: $($result.error)" -ForegroundColor Red
        }
        Write-Host ""
    }
    
    # Display recommendation
    if ($response.recommendation.best_address) {
        Write-Host "======================================" -ForegroundColor Green
        Write-Host " Recommendation" -ForegroundColor Green
        Write-Host "======================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Best Multicast Address: $($response.recommendation.best_address)" -ForegroundColor Green
        Write-Host "Providers Found: $($response.recommendation.providers_found)" -ForegroundColor Green
        Write-Host ""
        Write-Host $response.recommendation.message -ForegroundColor Yellow
        Write-Host ""
    } else {
        Write-Host "======================================" -ForegroundColor Yellow
        Write-Host " No Providers Found" -ForegroundColor Yellow
        Write-Host "======================================" -ForegroundColor Yellow
        Write-Host ""
        Write-Host $response.recommendation.message -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Troubleshooting:" -ForegroundColor Cyan
        Write-Host "  1. Check Power Core is configured to broadcast to 239.255.60.60:22344" -ForegroundColor White
        Write-Host "  2. Verify JetDrive is enabled in Power Core software" -ForegroundColor White
        Write-Host "  3. Ensure both devices are on the same network" -ForegroundColor White
        Write-Host "  4. Check Windows Firewall allows UDP port 22344" -ForegroundColor White
        Write-Host ""
    }
    
} catch {
    Write-Host "Error connecting to backend:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure the backend is running:" -ForegroundColor Yellow
    Write-Host "  python -m api.app" -ForegroundColor White
    Write-Host ""
    exit 1
}
