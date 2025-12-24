#!/usr/bin/env pwsh
# ======================================================================
# DynoAI Clean Restart Script (PowerShell)
# Stops all services, clears caches, and restarts everything fresh
# ======================================================================

$ErrorActionPreference = "SilentlyContinue"

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host "  DynoAI Clean Restart" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host ""

# Step 1: Stop all services
Write-Host "[1/6] Stopping all running services..." -ForegroundColor Cyan
Write-Host ""

Write-Host "  [*] Stopping Python/Flask processes..." -ForegroundColor Gray
Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

Write-Host "  [*] Stopping Node/Vite processes..." -ForegroundColor Gray
Get-Process node* -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

Write-Host "  [*] Freeing up ports 5001 and 5173..." -ForegroundColor Gray
# Kill processes on port 5001 (Flask)
$port5001 = Get-NetTCPConnection -LocalPort 5001 -ErrorAction SilentlyContinue
if ($port5001) {
    $port5001 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

# Kill processes on port 5173 (Vite)
$port5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
if ($port5173) {
    $port5173 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

Start-Sleep -Seconds 1
Write-Host "  [+] All services stopped" -ForegroundColor Green
Write-Host ""

# Step 2: Clear Python cache
Write-Host "[2/6] Clearing Python cache..." -ForegroundColor Cyan
Write-Host "  [*] Removing __pycache__ directories..." -ForegroundColor Gray
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "  [*] Removing .pyc files..." -ForegroundColor Gray
Get-ChildItem -Path . -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "  [+] Python cache cleared" -ForegroundColor Green
Write-Host ""

# Step 3: Clear Flask logs
Write-Host "[3/6] Clearing Flask logs..." -ForegroundColor Cyan
if (Test-Path "flask_debug.log") {
    Remove-Item "flask_debug.log" -Force -ErrorAction SilentlyContinue
    Write-Host "  [+] Flask logs cleared" -ForegroundColor Green
}
else {
    Write-Host "  [*] No Flask logs to clear" -ForegroundColor Gray
}

if (Test-Path "logs") {
    Get-ChildItem -Path "logs" -Filter "*.log" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "  [+] Application logs cleared" -ForegroundColor Green
}
Write-Host ""

# Step 4: Clear Vite cache
Write-Host "[4/6] Clearing Vite cache..." -ForegroundColor Cyan
if (Test-Path "frontend\node_modules\.vite") {
    Remove-Item "frontend\node_modules\.vite" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  [+] Vite cache cleared" -ForegroundColor Green
}
else {
    Write-Host "  [*] No Vite cache to clear" -ForegroundColor Gray
}
Write-Host ""

# Step 5: Clear temporary files
Write-Host "[5/6] Clearing temporary files..." -ForegroundColor Cyan
if (Test-Path "test_output") {
    Write-Host "  [*] Clearing test_output..." -ForegroundColor Gray
    Remove-Item "test_output" -Recurse -Force -ErrorAction SilentlyContinue
}
if (Test-Path ".pytest_cache") {
    Write-Host "  [*] Clearing pytest cache..." -ForegroundColor Gray
    Remove-Item ".pytest_cache" -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "  [+] Temporary files cleared" -ForegroundColor Green
Write-Host ""

# Step 6: Wait for system to settle
Write-Host "[6/6] Waiting for system to settle..." -ForegroundColor Cyan
Start-Sleep -Seconds 2
Write-Host "  [+] Ready to restart" -ForegroundColor Green
Write-Host ""

Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host "  Cleanup Complete!" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "Starting DynoAI services..." -ForegroundColor Cyan
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

# Install Python dependencies
Write-Host "[*] Checking Python dependencies..." -ForegroundColor Yellow
pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] Some dependencies failed to install, but continuing..." -ForegroundColor Yellow
    Write-Host "[*] If the app doesn't work, try: pip install -r requirements.txt" -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

# Install Node dependencies
Write-Host "[*] Checking Node dependencies..." -ForegroundColor Yellow
Push-Location frontend
npm install --silent
$npmExitCode = $LASTEXITCODE
Pop-Location

if ($npmExitCode -ne 0) {
    Write-Host "[WARNING] Some Node dependencies failed to install, but continuing..." -ForegroundColor Yellow
    Write-Host "[*] If the app doesn't work, try: cd frontend && npm install" -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "  Dependencies Ready - Starting Services" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""

# Start Flask backend in a new window
Write-Host "[*] Starting Flask backend on http://localhost:5001" -ForegroundColor Yellow
$backend = Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { `$Host.UI.RawUI.WindowTitle='DynoAI Backend (Clean)'; python api\app.py }" -PassThru

# Wait for backend to initialize
Write-Host "[*] Waiting for backend to initialize..." -ForegroundColor Gray
Start-Sleep -Seconds 4

# Start Vite frontend in a new window
Write-Host "[*] Starting Vite frontend on http://localhost:5173" -ForegroundColor Yellow
Push-Location frontend
$frontend = Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { `$Host.UI.RawUI.WindowTitle='DynoAI Frontend (Clean)'; npm run dev }" -PassThru
Pop-Location

# Wait for frontend to initialize
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "  DynoAI is Running! (Clean Start)" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend API:  http://localhost:5001" -ForegroundColor Cyan
Write-Host "  Frontend UI:  http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Performance Tips:" -ForegroundColor Yellow
Write-Host "  - Close any unnecessary browser tabs" -ForegroundColor Gray
Write-Host "  - Check Task Manager for memory usage" -ForegroundColor Gray
Write-Host "  - If issues persist, run this script again" -ForegroundColor Gray
Write-Host ""
Write-Host "  Close the terminal windows to stop the servers" -ForegroundColor Yellow
Write-Host "  Or run this script again for another clean restart" -ForegroundColor Yellow
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

}
}

