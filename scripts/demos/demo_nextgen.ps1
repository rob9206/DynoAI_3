# DynoAI NextGen Analysis Demo
# Opens the system in your browser to see all Phase 1-7 features

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  DynoAI NextGen Analysis Demo" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

$backendUrl = "http://localhost:5001"
$frontendUrl = "http://localhost:5173"

# Check if servers are running
Write-Host "[1/2] Checking servers..." -ForegroundColor Yellow

try {
    $health = Invoke-WebRequest -Uri "$backendUrl/api/health" -TimeoutSec 5 -UseBasicParsing
    Write-Host "      [OK] Backend running at $backendUrl" -ForegroundColor Green
} catch {
    Write-Host "      [ERROR] Backend not reachable" -ForegroundColor Red
    Write-Host "      Please start: python -m api.app" -ForegroundColor Yellow
    exit 1
}

try {
    $frontend = Invoke-WebRequest -Uri $frontendUrl -TimeoutSec 5 -UseBasicParsing
    Write-Host "      [OK] Frontend running at $frontendUrl" -ForegroundColor Green
} catch {
    Write-Host "      [ERROR] Frontend not reachable" -ForegroundColor Red
    Write-Host "      Please start: cd frontend && npm run dev" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "[2/2] Opening browser..." -ForegroundColor Yellow

# Open the main dashboard
Start-Process $frontendUrl

Write-Host "      [OK] Browser opened!" -ForegroundColor Green

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  DynoAI NextGen System is LIVE!" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your browser is now showing the DynoAI NextGen UI." -ForegroundColor White
Write-Host ""
Write-Host "Quick Tour:" -ForegroundColor Yellow
Write-Host "  1. Main Dashboard - Upload CSV files or view existing runs"
Write-Host "  2. JetDrive Tab - Live capture, preflight checks, mapping confidence"
Write-Host "  3. Runs List - Click any run to see NextGen Analysis"
Write-Host ""
Write-Host "NextGen Features (Phases 1-7):" -ForegroundColor Yellow
Write-Host "  [OK] Phase 1-2: JetDrive Preflight & Mapping" -ForegroundColor Green
Write-Host "  [OK] Phase 3: Live Capture Pipeline" -ForegroundColor Green
Write-Host "  [OK] Phase 4: Real-Time Analysis Overlay" -ForegroundColor Green
Write-Host "  [OK] Phase 6: Auto-Mapping with Confidence" -ForegroundColor Green
Write-Host "  [OK] Phase 7: Predictive Test Planning" -ForegroundColor Green
Write-Host ""
Write-Host "To test with sample data:" -ForegroundColor Yellow
Write-Host "  1. Click 'Upload' or 'Analyze' in the UI"
Write-Host "  2. Select: tests\data\dense_dyno_test.csv"
Write-Host "  3. Click 'Generate NextGen Analysis'"
Write-Host "  4. Explore all the results!"
Write-Host ""
Write-Host "Enjoy exploring the system!" -ForegroundColor Cyan
Write-Host ""
