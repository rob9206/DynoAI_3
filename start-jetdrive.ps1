#!/usr/bin/env pwsh
# DynoAI + Dynoware RT-150 Quick Start
# Supports custom IP address via parameter

param(
    [string]$DynoIP = "239.255.60.60"  # Default, override with -DynoIP parameter
)

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " DynoAI + Dynoware RT-150" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to script directory
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Test connectivity
Write-Host "[*] Testing Dynoware RT-150 at $DynoIP..." -ForegroundColor Yellow
$pingResult = ping -n 1 -w 1000 $DynoIP 2>&1
if ($pingResult -match "Reply from $DynoIP") {
    Write-Host "  [OK] Dynoware reachable at $DynoIP" -ForegroundColor Green
}
else {
    Write-Host "  [!] Cannot reach $DynoIP" -ForegroundColor Red
    Write-Host "      Checking if it might be on a different IP..." -ForegroundColor Yellow
}
Write-Host ""

# Check Python
Write-Host "[*] Checking Python..." -ForegroundColor Yellow
$pythonCheck = python --version 2>&1
Write-Host "  [OK] $pythonCheck" -ForegroundColor Green
Write-Host ""

# Create venv if needed
if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "  [OK] Created" -ForegroundColor Green
}
else {
    Write-Host "[*] Virtual environment exists" -ForegroundColor Green
}
Write-Host ""

# Activate
Write-Host "[*] Activating environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
Write-Host "  [OK] Activated" -ForegroundColor Green
Write-Host ""

# Install deps
Write-Host "[*] Installing dependencies (may take a minute)..." -ForegroundColor Yellow
python -m pip install --quiet --upgrade pip 2>&1 | Out-Null
pip install --quiet -r api\requirements.txt 2>&1 | Out-Null
Write-Host "  [OK] Installed" -ForegroundColor Green
Write-Host ""

# Configure environment
Write-Host "[*] Setting up configuration..." -ForegroundColor Yellow

$env:DYNOAI_HOST = "0.0.0.0"
$env:DYNOAI_PORT = "5001"
$env:DYNOAI_DEBUG = "false"
$env:LOG_LEVEL = "INFO"

# Dynoware RT-150 settings
$env:DYNO_MODEL = "Dynoware RT-150"
$env:DYNO_SERIAL = "RT00220413"
$env:DYNO_LOCATION = "Dawson Dynamics"
$env:DYNO_IP = $DynoIP  # Use parameter value
$env:DYNO_JETDRIVE_PORT = "22344"

# JetDrive network configuration - bind to your computer's IP
$env:JETDRIVE_IFACE = "192.168.1.86"  # Your computer's IP address
$env:JETDRIVE_MCAST_GROUP = "239.255.60.60"  # Multicast group
$env:JETDRIVE_PORT = "22344"

# Drum 1 settings
$env:DYNO_DRUM1_SERIAL = "1000588"
$env:DYNO_DRUM1_MASS_SLUGS = "14.121"
$env:DYNO_DRUM1_RETARDER_MASS_SLUGS = "0.0"
$env:DYNO_DRUM1_CIRCUMFERENCE_FT = "4.673"
$env:DYNO_DRUM1_TABS = "1"

# Firmware
$env:DYNO_FIRMWARE = "2.1.7034.17067"
$env:DYNO_ATMO_VERSION = "1.1"
$env:DYNO_NUM_MODULES = "4"

# Storage
$env:DYNOAI_UPLOAD_DIR = "uploads"
$env:DYNOAI_OUTPUT_DIR = "outputs"
$env:DYNOAI_RUNS_DIR = "runs"
$env:DYNOAI_CORS_ORIGINS = "*"

# Rate limiting - use memory storage (no Redis required)
$env:RATE_LIMIT_STORAGE = "memory://"

# Jetstream
$env:JETSTREAM_ENABLED = "false"
$env:JETSTREAM_STUB_MODE = "false"

Write-Host "  [OK] Configured" -ForegroundColor Green
Write-Host ""

Write-Host "======================================" -ForegroundColor Green
Write-Host " Starting DynoAI" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Dyno IP:         $DynoIP" -ForegroundColor Cyan
Write-Host "  Your IP:         $env:JETDRIVE_IFACE" -ForegroundColor Cyan
Write-Host "  JetDrive Port:   22344 (UDP multicast)" -ForegroundColor Cyan
Write-Host "  Multicast Group: $env:JETDRIVE_MCAST_GROUP" -ForegroundColor Cyan
Write-Host "  API Server:      http://localhost:5001" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Test endpoints:" -ForegroundColor Yellow
Write-Host "    http://localhost:5001/api/health" -ForegroundColor Gray
Write-Host "    http://localhost:5001/api/jetdrive/diagnostics" -ForegroundColor Gray
Write-Host "    http://localhost:5001/api/jetdrive/hardware/heartbeat" -ForegroundColor Gray
Write-Host ""
Write-Host "  Note: JetDrive uses UDP multicast - IP is for reference" -ForegroundColor Gray
Write-Host "        The dyno will be auto-discovered on the network" -ForegroundColor Gray
Write-Host ""
Write-Host "  Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host ""

# Start API server
python -m api.app
