#!/usr/bin/env pwsh
# ======================================================================
# DynoAI Quick Restart Script (PowerShell)
# Stops all services and restarts WITHOUT reinstalling dependencies
# Use this for faster restarts when dependencies are already installed
# ======================================================================

$ErrorActionPreference = "SilentlyContinue"

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host "  DynoAI Quick Restart (No Dependency Install)" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host ""

# Step 1: Stop all services
Write-Host "[1/5] Stopping all running services..." -ForegroundColor Cyan
Write-Host ""

Write-Host "  [*] Stopping Python/Flask processes..." -ForegroundColor Gray
Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

Write-Host "  [*] Stopping Node/Vite processes..." -ForegroundColor Gray
Get-Process node* -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

Write-Host "  [*] Freeing up ports 5001 and 5173..." -ForegroundColor Gray
# Use netstat for faster, more reliable port checking
function Kill-ProcessOnPort {
    param([int]$Port)
    try {
        $connections = netstat -ano | Select-String ":$Port\s" | ForEach-Object {
            if ($_ -match '\s+(\d+)\s*$') {
                $matches[1]
            }
        }
        $connections | ForEach-Object {
            $pid = $_
            if ($pid -and $pid -ne '0') {
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
        }
    }
    catch {
        # Fallback: try Get-NetTCPConnection with timeout
        $job = Start-Job -ScriptBlock {
            param($p)
            Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | 
            Select-Object -ExpandProperty OwningProcess -Unique
        } -ArgumentList $Port
        
        if (Wait-Job $job -Timeout 2) {
            $pids = Receive-Job $job
            Remove-Job $job -Force
            $pids | ForEach-Object {
                if ($_ -and $_ -ne 0) {
                    Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
                }
            }
        }
        else {
            Stop-Job $job -Force
            Remove-Job $job -Force
        }
    }
}

Kill-ProcessOnPort -Port 5001
Kill-ProcessOnPort -Port 5173

Start-Sleep -Seconds 1
Write-Host "  [+] All services stopped" -ForegroundColor Green
Write-Host ""

# Step 2: Clear Python cache
Write-Host "[2/5] Clearing Python cache..." -ForegroundColor Cyan
Write-Host "  [*] Removing __pycache__ directories..." -ForegroundColor Gray
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "  [*] Removing .pyc files..." -ForegroundColor Gray
Get-ChildItem -Path . -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "  [+] Python cache cleared" -ForegroundColor Green
Write-Host ""

# Step 3: Clear Flask logs
Write-Host "[3/5] Clearing Flask logs..." -ForegroundColor Cyan
if (Test-Path "flask_debug.log") {
    Remove-Item "flask_debug.log" -Force -ErrorAction SilentlyContinue
    Write-Host "  [+] Flask logs cleared" -ForegroundColor Green
}
else {
    Write-Host "  [*] No Flask logs to clear" -ForegroundColor Gray
}
Write-Host ""

# Step 4: Clear Vite cache
Write-Host "[4/5] Clearing Vite cache..." -ForegroundColor Cyan
if (Test-Path "frontend\node_modules\.vite") {
    Remove-Item "frontend\node_modules\.vite" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  [+] Vite cache cleared" -ForegroundColor Green
}
else {
    Write-Host "  [*] No Vite cache to clear" -ForegroundColor Gray
}
Write-Host ""

# Step 5: Wait for system to settle
Write-Host "[5/5] Waiting for system to settle..." -ForegroundColor Cyan
Start-Sleep -Seconds 2
Write-Host "  [+] Ready to restart" -ForegroundColor Green
Write-Host ""

Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host "  Cleanup Complete - Starting Services" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host ""

# Check Python
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Python not found. Please install Python 3.8 or higher." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check Node
$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Node.js not found. Please install Node.js 18 or higher." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "  Starting Services (Quick Mode)" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""

# Start Flask backend in a new window
Write-Host "[*] Starting Flask backend on http://localhost:5001" -ForegroundColor Yellow
$projectRoot = (Get-Location).Path
$backend = Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { `$Host.UI.RawUI.WindowTitle='DynoAI Backend (Quick)'; Set-Location '$projectRoot'; python -m api.app }" -PassThru

# Wait for backend to initialize
Write-Host "[*] Waiting for backend to initialize..." -ForegroundColor Gray
Start-Sleep -Seconds 3

# Start Vite frontend in a new window
Write-Host "[*] Starting Vite frontend on http://localhost:5173" -ForegroundColor Yellow
Push-Location frontend
$frontend = Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { `$Host.UI.RawUI.WindowTitle='DynoAI Frontend (Quick)'; npm run dev }" -PassThru
Pop-Location

# Wait for frontend to initialize
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "  DynoAI is Running! (Quick Start)" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend API:  http://localhost:5001" -ForegroundColor Cyan
Write-Host "  Frontend UI:  http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Note: This quick restart skips dependency installation" -ForegroundColor Yellow
Write-Host "  If you have issues, run: .\restart-clean.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Close the terminal windows to stop the servers" -ForegroundColor Gray
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""

# Keep script running and handle Ctrl+C
Write-Host "Press Ctrl+C to stop all services and exit..." -ForegroundColor Cyan
Write-Host ""

try {
    while ($true) {
        Start-Sleep -Seconds 1
        
        # Check if processes are still running
        if ($backend -and $backend.HasExited) {
            Write-Host "[!] Backend process has stopped unexpectedly" -ForegroundColor Red
            break
        }
        if ($frontend -and $frontend.HasExited) {
            Write-Host "[!] Frontend process has stopped unexpectedly" -ForegroundColor Red
            break
        }
    }
}
finally {
    Write-Host ""
    Write-Host "[*] Stopping all services..." -ForegroundColor Yellow
    
    # Stop backend
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
        Write-Host "  [+] Backend stopped" -ForegroundColor Gray
    }
    
    # Stop frontend
    if ($frontend -and -not $frontend.HasExited) {
        Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
        Write-Host "  [+] Frontend stopped" -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "[*] Goodbye!" -ForegroundColor Cyan
}

