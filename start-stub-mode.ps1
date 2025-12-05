# Start DynoAI with Jetstream Stub Data Mode
# This script starts both backend and frontend with stub data enabled

Write-Host "[*] Starting DynoAI in Stub Mode..." -ForegroundColor Cyan
Write-Host ""

# Set environment variables
$env:PYTHONPATH = "C:\Dev\DynoAI_3;C:\Dev\DynoAI_3\api"
$env:JETSTREAM_STUB_DATA = "true"
$env:JETSTREAM_ENABLED = "false"
$env:FLASK_APP = "api.app"

Write-Host "[+] Environment configured" -ForegroundColor Green
Write-Host "   JETSTREAM_STUB_DATA=true" -ForegroundColor Gray
Write-Host "   JETSTREAM_ENABLED=false" -ForegroundColor Gray
Write-Host ""

Write-Host "[>] Starting Flask backend on port 5100..." -ForegroundColor Yellow
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$PWD'; `$env:PYTHONPATH='C:\Dev\DynoAI_3;C:\Dev\DynoAI_3\api'; `$env:JETSTREAM_STUB_DATA='true'; `$env:JETSTREAM_ENABLED='false'; `$env:FLASK_APP='api.app'; python -m flask run --port 5100 --debug"

Start-Sleep -Seconds 5

Write-Host "[>] Starting Vite frontend..." -ForegroundColor Yellow
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$PWD\frontend'; `$env:VITE_API_BASE_URL='http://127.0.0.1:5100'; npm run dev"

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "[+] Services started!" -ForegroundColor Green
Write-Host ""
Write-Host "[*] Backend:  http://127.0.0.1:5100" -ForegroundColor Cyan
Write-Host "[*] Frontend: http://localhost:5173 (or whatever port Vite assigns)" -ForegroundColor Cyan
Write-Host ""
Write-Host "[*] Test endpoints:" -ForegroundColor Yellow
Write-Host "   Invoke-RestMethod http://127.0.0.1:5100/api/jetstream/status" -ForegroundColor Gray
Write-Host "   Invoke-RestMethod http://127.0.0.1:5100/api/jetstream/runs" -ForegroundColor Gray
Write-Host "   Invoke-RestMethod http://127.0.0.1:5100/api/ve-data/run_jetstream_demo_complete" -ForegroundColor Gray
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

