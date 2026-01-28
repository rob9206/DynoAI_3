# DynoAI Executable Build Script
# Builds a standalone Windows executable

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  DynoAI Executable Build Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
Write-Host "[1/4] Activating virtual environment..." -ForegroundColor Yellow
$venvPath = "$PSScriptRoot\.venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    . $venvPath
} else {
    Write-Host "ERROR: Virtual environment not found!" -ForegroundColor Red
    exit 1
}

# Build React frontend
Write-Host "[2/4] Building React frontend..." -ForegroundColor Yellow
$env:PATH = "C:\Program Files\nodejs;" + $env:PATH
Set-Location "$PSScriptRoot\frontend"
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Frontend build failed!" -ForegroundColor Red
    exit 1
}
Set-Location $PSScriptRoot

# Clean previous build
Write-Host "[3/4] Cleaning previous build..." -ForegroundColor Yellow
if (Test-Path "$PSScriptRoot\build") {
    Remove-Item -Recurse -Force "$PSScriptRoot\build"
}
if (Test-Path "$PSScriptRoot\dist") {
    Remove-Item -Recurse -Force "$PSScriptRoot\dist"
}

# Build executable
Write-Host "[4/4] Building executable with PyInstaller..." -ForegroundColor Yellow
pyinstaller --clean dynoai.spec

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  BUILD SUCCESSFUL!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Executable location:" -ForegroundColor Cyan
    Write-Host "  $PSScriptRoot\dist\DynoAI.exe" -ForegroundColor White
    Write-Host ""
    Write-Host "To run:" -ForegroundColor Cyan
    Write-Host "  .\dist\DynoAI.exe" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "BUILD FAILED!" -ForegroundColor Red
    exit 1
}
