#!/usr/bin/env pwsh
# DynoAI Web Application Startup Script
# Starts both Flask API backend and React frontend

Write-Host "[*] Starting DynoAI Web Application..." -ForegroundColor Cyan

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "[-] Virtual environment not found. Please run: python -m venv .venv" -ForegroundColor Red
    exit 1
}

# Activate virtual environment
Write-Host "[>] Activating Python virtual environment..." -ForegroundColor Yellow
& .venv\Scripts\Activate.ps1

# Install API dependencies if needed
Write-Host "[>] Installing API dependencies..." -ForegroundColor Yellow
pip install -q -r api\requirements.txt

# Check if frontend dependencies are installed
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "[>] Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    Pop-Location
}

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host "  DynoAI Web Application" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend API:  http://localhost:5001" -ForegroundColor Cyan
Write-Host "  Frontend UI:  http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Press Ctrl+C to stop all servers" -ForegroundColor Yellow
Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host ""

# Start backend in background
Write-Host "[>] Starting Flask API backend..." -ForegroundColor Yellow
$backend = Start-Process python -ArgumentList "api\app.py" -PassThru -NoNewWindow

# Wait a moment for backend to start
Start-Sleep -Seconds 2

# Start frontend in background
Write-Host "[>] Starting React frontend..." -ForegroundColor Yellow
Push-Location frontend
$frontend = Start-Process npm -ArgumentList "run dev" -PassThru -NoNewWindow
Pop-Location

# Wait for user to stop
Write-Host ""
Write-Host "[+] Both servers are running!" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop..." -ForegroundColor Yellow

# Handle Ctrl+C
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host ""
    Write-Host "[*] Stopping servers..." -ForegroundColor Yellow
    
    # Stop backend
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force
        Write-Host "  [+] Backend stopped" -ForegroundColor Gray
    }
    
    # Stop frontend
    if ($frontend -and -not $frontend.HasExited) {
        Stop-Process -Id $frontend.Id -Force
        Write-Host "  [+] Frontend stopped" -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "[*] Goodbye!" -ForegroundColor Cyan
}
