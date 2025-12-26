#!/usr/bin/env pwsh
# Start DynoAI with Jetstream stub mode
# This script will show all output in the current terminal

Write-Host "[*] Starting DynoAI Backend with Jetstream Stub Mode..." -ForegroundColor Cyan
Write-Host ""

# Navigate to correct directory
Set-Location C:\Dev\DynoAI_3

# Set environment variables
$env:PYTHONPATH = "C:\Dev\DynoAI_3;C:\Dev\DynoAI_3\api"
$env:JETSTREAM_STUB_DATA = "true"
$env:JETSTREAM_ENABLED = "false"

Write-Host "[+] Environment configured:" -ForegroundColor Green
Write-Host "   Working Directory: $(Get-Location)" -ForegroundColor Gray
Write-Host "   PYTHONPATH: $env:PYTHONPATH" -ForegroundColor Gray
Write-Host "   JETSTREAM_STUB_DATA: $env:JETSTREAM_STUB_DATA" -ForegroundColor Gray
Write-Host "   JETSTREAM_ENABLED: $env:JETSTREAM_ENABLED" -ForegroundColor Gray
Write-Host ""

Write-Host "[>] Starting Flask API backend on http://localhost:5001..." -ForegroundColor Yellow
Write-Host ""

# Run Python with full output
python api\app.py

