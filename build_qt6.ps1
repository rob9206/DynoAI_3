# Build script for DynoAI Qt6 Desktop Application

Write-Host "Building DynoAI Qt6 Desktop Application..." -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
Write-Host "[1/4] Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Install/update dependencies
Write-Host "[2/4] Installing dependencies..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Clean previous builds
Write-Host "[3/4] Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}

# Build the executable
Write-Host "[4/4] Building executable with PyInstaller..." -ForegroundColor Yellow
pyinstaller dynoai_qt6.spec

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Build successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Executable location: .\dist\DynoAI.exe" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To run the application:" -ForegroundColor Yellow
    Write-Host "  .\dist\DynoAI.exe" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "❌ Build failed!" -ForegroundColor Red
    Write-Host "Check the output above for errors." -ForegroundColor Red
    Write-Host ""
    exit 1
}
