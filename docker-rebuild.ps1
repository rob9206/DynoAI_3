#!/usr/bin/env pwsh
# DynoAI Docker Container Fix and Restart Script
# This script rebuilds and restarts the DynoAI API container

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DynoAI Docker Container Rebuild Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Function to check if Docker is running
function Test-DockerRunning {
    try {
        docker ps | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

# Check if Docker is running
if (-not (Test-DockerRunning)) {
    Write-Host "ERROR: Docker is not running or not accessible" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 1: Stop containers
Write-Host "[1/5] Stopping containers..." -ForegroundColor Yellow
docker-compose down
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to stop containers" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "SUCCESS: Containers stopped" -ForegroundColor Green
Write-Host ""

# Step 2: Rebuild API container
Write-Host "[2/5] Rebuilding API container (no cache)..." -ForegroundColor Yellow
Write-Host "This may take a few minutes..." -ForegroundColor Gray
docker-compose build --no-cache api
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to rebuild API container" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "SUCCESS: API container rebuilt" -ForegroundColor Green
Write-Host ""

# Step 3: Start services
Write-Host "[3/5] Starting services..." -ForegroundColor Yellow
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start services" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "SUCCESS: Services started" -ForegroundColor Green
Write-Host ""

# Step 4: Wait for initialization
Write-Host "[4/5] Waiting for services to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
Write-Host ""

# Step 5: Check status
Write-Host "[5/5] Checking container status..." -ForegroundColor Yellow
docker-compose ps
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Container rebuild complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Check logs: docker-compose logs -f api" -ForegroundColor White
Write-Host "  2. Test health: curl http://localhost:5001/api/health/ready" -ForegroundColor White
Write-Host "  3. Open admin: http://localhost:5001/admin" -ForegroundColor White
Write-Host "  4. API docs: http://localhost:5001/api/docs" -ForegroundColor White
Write-Host ""

# Offer to show logs
$showLogs = Read-Host "Would you like to view API logs? (y/n)"
if ($showLogs -eq "y" -or $showLogs -eq "Y") {
    Write-Host ""
    Write-Host "Showing API logs (press Ctrl+C to exit)..." -ForegroundColor Yellow
    Write-Host ""
    docker-compose logs -f api
}
