# Clean restart script for DynoAI Qt6
# This ensures no cached bytecode is used

Write-Host "Cleaning Python cache..." -ForegroundColor Yellow
Get-ChildItem -Path . -Include "__pycache__","*.pyc" -Recurse -Force | Remove-Item -Recurse -Force

Write-Host "Killing any running Python processes..." -ForegroundColor Yellow
taskkill /F /IM python.exe 2>$null

Start-Sleep -Seconds 1

Write-Host "Starting DynoAI Qt6..." -ForegroundColor Green
python -B dynoai_qt6.py

Write-Host "Application closed." -ForegroundColor Cyan
