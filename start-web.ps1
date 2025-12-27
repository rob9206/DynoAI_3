#!/usr/bin/env pwsh
# DynoAI Web Application Startup Script
# Starts both Flask API backend and React frontend

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
if (-not $Root) {
    # Fallback for unusual invocation contexts
    $Root = (Get-Location).Path
}

Set-Location $Root

Write-Host "[*] Starting DynoAI Web Application..." -ForegroundColor Cyan

function Test-LocalPortListening {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        return ($null -ne $conns -and $conns.Count -gt 0)
    }
    catch {
        # Fallback for environments where Get-NetTCPConnection isn't available/reliable
        $matches = netstat -ano | Select-String -Pattern (":$Port\s")
        return ($null -ne $matches -and $matches.Count -gt 0)
    }
}

# Check if Python is available
python --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[-] Python not found in PATH (even after venv activation). Please install Python 3.10+." -ForegroundColor Red
    exit 1
}

# Ensure virtual environment exists (auto-create for a smoother first run)
if (-not (Test-Path (Join-Path $Root ".venv"))) {
    Write-Host "[>] Virtual environment not found; creating .venv..." -ForegroundColor Yellow
    python -m venv .venv
}

# Activate virtual environment
Write-Host "[>] Activating Python virtual environment..." -ForegroundColor Yellow
& (Join-Path $Root ".venv\Scripts\Activate.ps1")

# Check if Node is available
node --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[-] Node.js not found in PATH. Please install Node 18+." -ForegroundColor Red
    exit 1
}

# Install API dependencies if needed
Write-Host "[>] Installing API dependencies..." -ForegroundColor Yellow
python -m pip install -q -r api\requirements.txt

# Check if frontend dependencies are installed
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "[>] Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    Pop-Location
}

# Ensure logs folder exists (handy when a process exits immediately)
$logsDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

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
$backend = $null
if (Test-LocalPortListening -Port 5001) {
    Write-Host "[i] Backend already listening on port 5001; skipping backend startup." -ForegroundColor Gray
}
else {
    $backendOut = Join-Path $logsDir "backend.stdout.log"
    $backendErr = Join-Path $logsDir "backend.stderr.log"
    $backend = Start-Process `
        -FilePath "python" `
        -ArgumentList @("-m", "api.app") `
        -WorkingDirectory $Root `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr `
        -PassThru `
        -NoNewWindow
}

# Wait a moment for backend to start
Start-Sleep -Seconds 2

# Start frontend in background
Write-Host "[>] Starting React frontend..." -ForegroundColor Yellow
$frontend = $null
if (Test-LocalPortListening -Port 5173) {
    Write-Host "[i] Frontend already listening on port 5173; skipping frontend startup." -ForegroundColor Gray
}
else {
    $frontendOut = Join-Path $logsDir "frontend.stdout.log"
    $frontendErr = Join-Path $logsDir "frontend.stderr.log"
    $frontend = Start-Process `
        -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev") `
        -WorkingDirectory (Join-Path $Root "frontend") `
        -RedirectStandardOutput $frontendOut `
        -RedirectStandardError $frontendErr `
        -PassThru `
        -NoNewWindow
}

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
