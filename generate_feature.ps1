# Simple PowerShell script to generate features for DynoAI_3 using DeepCode
param(
    [string]$Feature = ""
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DynoAI_3 Feature Generator" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get feature description if not provided
if ([string]::IsNullOrWhiteSpace($Feature)) {
    Write-Host "What would you like to generate?" -ForegroundColor Yellow
    Write-Host ""
    $Feature = Read-Host "Feature description"
}

Write-Host ""
Write-Host "Generating: $Feature" -ForegroundColor Green
Write-Host ""

# Change to DeepCode directory
$DeepCodePath = "C:\Users\dawso\OneDrive\DeepCode\DeepCode"
Push-Location $DeepCodePath

# Build the prompt
$Context = "Project: DynoAI_3 - Deterministic Dyno Tuning Platform. "
$Context += "Use Python 3.10+ with type hints, comprehensive docstrings, and unit tests. "
$Context += "Follow deterministic math principles. "
$Context += "Feature Request: $Feature"

Write-Host "Running DeepCode..." -ForegroundColor Green
Write-Host ""

# Run DeepCode
python cli/main_cli.py --chat $Context

Write-Host ""
Write-Host "Done! Check output in:" -ForegroundColor Green
Write-Host "$DeepCodePath\deepcode_lab\papers\" -ForegroundColor White
Write-Host ""

# Return to original directory
Pop-Location

