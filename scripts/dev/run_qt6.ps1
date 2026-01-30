# Quick start script for DynoAI Qt6 Desktop Application

Write-Host "Starting DynoAI Qt6..." -ForegroundColor Cyan

# Activate virtual environment if it exists
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
}

# Run the application
python dynoai_qt6.py
