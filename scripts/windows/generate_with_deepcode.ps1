# PowerShell script to generate features for DynoAI_3 using DeepCode
# This runs DeepCode from its own directory to avoid config file issues

param(
    [string]$FeatureDescription = ""
)

Write-Host "`n╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          DynoAI_3 Feature Generator (via DeepCode)              ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

# Change to DeepCode directory
$DeepCodePath = "C:\Users\dawso\OneDrive\DeepCode\DeepCode"
Set-Location $DeepCodePath

Write-Host "📁 Working from DeepCode directory: $DeepCodePath" -ForegroundColor Green
Write-Host ""

# If no feature description provided, use interactive mode
if ([string]::IsNullOrWhiteSpace($FeatureDescription)) {
    Write-Host "🎯 What would you like to generate for DynoAI_3?" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Gray
    Write-Host "  - Boost pressure analyzer module" -ForegroundColor Gray
    Write-Host "  - API endpoint for transient fuel analysis" -ForegroundColor Gray
    Write-Host "  - React component for VE heatmap visualization" -ForegroundColor Gray
    Write-Host "  - Test suite for ve_math.py" -ForegroundColor Gray
    Write-Host ""
    
    $FeatureDescription = Read-Host "Enter your feature description"
}

# Build the enhanced prompt with DynoAI_3 context
$Prompt = @"
Project: DynoAI_3 - Deterministic Dyno Tuning Platform

Core Principles:
- Deterministic math (same inputs = same outputs, bit-for-bit)
- Automation-first design (headless CLI, batch processing)
- Production safety (conservative defaults, dry-run mode)
- Formal contracts (explicit schemas, units, invariants)

Technology Stack:
- Backend: Python 3.10+, Flask, pandas, numpy, scipy
- Frontend: React 18, TypeScript, Vite
- Testing: pytest, pytest-asyncio

Coding Standards:
- Type hints for all functions
- Comprehensive docstrings (Google style)
- Unit tests with 80%+ coverage
- Deterministic behavior
- Conservative error handling

Feature Request:
$FeatureDescription

Requirements:
- Follow DynoAI_3 coding standards
- Include comprehensive unit tests
- Add inline documentation
- Consider production safety
- Integrate with existing DynoAI_3 architecture

Generate production-ready code for DynoAI_3.
"@

Write-Host "🚀 Generating feature with DeepCode..." -ForegroundColor Green
Write-Host "⏱️  This may take 20-40 minutes depending on complexity" -ForegroundColor Yellow
Write-Host ""

# Run DeepCode CLI
python cli/main_cli.py --chat $Prompt

Write-Host ""
Write-Host "✅ Generation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📁 Check output in:" -ForegroundColor Cyan
Write-Host "   $DeepCodePath\deepcode_lab\papers\" -ForegroundColor White
Write-Host ""
Write-Host "🔄 Next steps:" -ForegroundColor Yellow
Write-Host "   1. Review the generated code" -ForegroundColor White
Write-Host "   2. Copy relevant files to C:\dev\dynoai_3\" -ForegroundColor White
Write-Host "   3. Run tests and integrate" -ForegroundColor White
Write-Host ""

# Return to DynoAI_3 directory
Set-Location "C:\dev\dynoai_3"

