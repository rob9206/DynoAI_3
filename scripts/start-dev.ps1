#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start DynoAI development servers (backend first, then frontend)
.DESCRIPTION
    This script ensures the backend API starts on port 5001 before the frontend,
    preventing port conflicts.
.EXAMPLE
    .\scripts\start-dev.ps1
#>

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$WithLiveLink
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DynoAI Development Server Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Kill any existing processes on our ports
Write-Host "[*] Cleaning up existing processes..." -ForegroundColor Yellow
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Start Backend
if (-not $FrontendOnly) {
    Write-Host "[>] Starting Backend API on port 5001..." -ForegroundColor Green
    
    $backendJob = Start-Job -ScriptBlock {
        param($root)
        Set-Location $root
        $env:FLASK_APP = 'api.app'
        $env:JETSTREAM_STUB_MODE = 'true'
        python -m flask run --host=0.0.0.0 --port=5001
    } -ArgumentList $ProjectRoot
    
    # Wait for backend to be ready
    Write-Host "[*] Waiting for backend to start..." -ForegroundColor Yellow
    $maxAttempts = 30
    $attempt = 0
    $backendReady = $false
    
    while ($attempt -lt $maxAttempts -and -not $backendReady) {
        Start-Sleep -Seconds 1
        $attempt++
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:5001/api/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $backendReady = $true
                Write-Host "[+] Backend ready!" -ForegroundColor Green
            }
        } catch {
            Write-Host "    Attempt $attempt/$maxAttempts..." -ForegroundColor DarkGray
        }
    }
    
    if (-not $backendReady) {
        Write-Host "[!] Backend failed to start. Check logs." -ForegroundColor Red
        exit 1
    }
}

# Start Frontend
if (-not $BackendOnly) {
    Write-Host "[>] Starting Frontend on port 5000..." -ForegroundColor Green
    
    $frontendJob = Start-Job -ScriptBlock {
        param($root)
        Set-Location "$root\frontend"
        npm run dev
    } -ArgumentList $ProjectRoot
    
    Start-Sleep -Seconds 3
    Write-Host "[+] Frontend starting..." -ForegroundColor Green
}

# Start LiveLink WebSocket Server (optional)
if ($WithLiveLink) {
    Write-Host "[>] Starting LiveLink WebSocket server on port 5003..." -ForegroundColor Green
    
    $livelinkJob = Start-Job -ScriptBlock {
        param($root)
        Set-Location $root
        python scripts/start-livelink-ws.py --port 5003 --mode simulation
    } -ArgumentList $ProjectRoot
    
    Start-Sleep -Seconds 2
    Write-Host "[+] LiveLink server starting..." -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All services started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Frontend:  http://localhost:5000" -ForegroundColor White
Write-Host "  Backend:   http://localhost:5001" -ForegroundColor White
if ($WithLiveLink) {
    Write-Host "  LiveLink:  http://localhost:5003" -ForegroundColor White
}
Write-Host ""
Write-Host "  Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

# Keep script running and show logs
try {
    while ($true) {
        Start-Sleep -Seconds 5
        
        # Check if jobs are still running
        if (-not $FrontendOnly -and $backendJob.State -eq "Failed") {
            Write-Host "[!] Backend crashed!" -ForegroundColor Red
            Receive-Job $backendJob
        }
        if (-not $BackendOnly -and $frontendJob.State -eq "Failed") {
            Write-Host "[!] Frontend crashed!" -ForegroundColor Red
            Receive-Job $frontendJob
        }
    }
} finally {
    Write-Host "`n[*] Shutting down services..." -ForegroundColor Yellow
    Get-Job | Stop-Job -PassThru | Remove-Job
    Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "[+] Done." -ForegroundColor Green
}

