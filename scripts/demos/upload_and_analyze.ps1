# Upload Test Data and Generate NextGen Analysis Demo
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  Uploading Test Data & Generating NextGen Analysis" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

$backendUrl = "http://127.0.0.1:5001"
$frontendUrl = "http://localhost:5173"
$testFile = "tests\data\dense_dyno_test.csv"

# Check if test file exists
if (-not (Test-Path $testFile)) {
    Write-Host "[ERROR] Test file not found: $testFile" -ForegroundColor Red
    exit 1
}

Write-Host "[1/4] Uploading test data..." -ForegroundColor Yellow
Write-Host "      File: $testFile" -ForegroundColor Gray
Write-Host "      Size: $((Get-Item $testFile).Length / 1KB) KB" -ForegroundColor Gray

try {
    # Upload file
    $fileBytes = [System.IO.File]::ReadAllBytes((Resolve-Path $testFile))
    $fileContent = [System.Net.Http.ByteArrayContent]::new($fileBytes)
    $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("text/csv")
    
    $multipartContent = [System.Net.Http.MultipartFormDataContent]::new()
    $multipartContent.Add($fileContent, "file", "dense_dyno_test.csv")
    
    $httpClient = [System.Net.Http.HttpClient]::new()
    $response = $httpClient.PostAsync("$backendUrl/api/analyze", $multipartContent).Result
    
    if ($response.IsSuccessStatusCode) {
        $result = $response.Content.ReadAsStringAsync().Result | ConvertFrom-Json
        $runId = $result.runId
        Write-Host "      [OK] Upload successful! Run ID: $runId" -ForegroundColor Green
    } else {
        Write-Host "      [ERROR] Upload failed: $($response.StatusCode)" -ForegroundColor Red
        exit 1
    }
    
    $httpClient.Dispose()
} catch {
    Write-Host "      [ERROR] Upload failed: $_" -ForegroundColor Red
    exit 1
}

# Wait for analysis to complete
Write-Host ""
Write-Host "[2/4] Waiting for analysis to complete..." -ForegroundColor Yellow

$maxWait = 60
$elapsed = 0
$completed = $false

while ($elapsed -lt $maxWait -and -not $completed) {
    Start-Sleep -Seconds 2
    $elapsed += 2
    
    try {
        $statusResponse = Invoke-WebRequest -Uri "$backendUrl/api/status/$runId" -UseBasicParsing
        $status = $statusResponse.Content | ConvertFrom-Json
        
        if ($status.status -eq "completed") {
            $completed = $true
            Write-Host "      [OK] Analysis completed!" -ForegroundColor Green
        } elseif ($status.status -eq "error") {
            Write-Host "      [ERROR] Analysis failed: $($status.error)" -ForegroundColor Red
            exit 1
        } else {
            Write-Host "      Progress: $($status.status)..." -ForegroundColor Gray
        }
    } catch {
        Write-Host "      Waiting..." -ForegroundColor Gray
    }
}

if (-not $completed) {
    Write-Host "      [WARNING] Analysis taking longer than expected..." -ForegroundColor Yellow
    Write-Host "      The analysis is still running. You can check it in the UI." -ForegroundColor Yellow
}

# Generate NextGen Analysis
Write-Host ""
Write-Host "[3/4] Generating NextGen Analysis..." -ForegroundColor Yellow
Write-Host "      This includes:" -ForegroundColor Gray
Write-Host "        - Mode detection (7 driving modes)" -ForegroundColor Gray
Write-Host "        - Surface building (spark, AFR error, coverage)" -ForegroundColor Gray
Write-Host "        - Spark valley detection" -ForegroundColor Gray
Write-Host "        - Cause tree hypotheses" -ForegroundColor Gray
Write-Host "        - Coverage gap analysis" -ForegroundColor Gray
Write-Host "        - Predictive test planning (Phase 7)" -ForegroundColor Gray

try {
    $nextgenResponse = Invoke-WebRequest -Uri "$backendUrl/api/nextgen/$runId/generate?force=true" -Method POST -UseBasicParsing -TimeoutSec 60
    
    if ($nextgenResponse.StatusCode -eq 200) {
        Write-Host "      [OK] NextGen Analysis generated!" -ForegroundColor Green
    } else {
        Write-Host "      [WARNING] NextGen generation returned: $($nextgenResponse.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "      [WARNING] NextGen generation issue (may still work in UI)" -ForegroundColor Yellow
}

# Open browser
Write-Host ""
Write-Host "[4/4] Opening results in browser..." -ForegroundColor Yellow
$url = "$frontendUrl/runs/$runId"
Start-Process $url
Write-Host "      [OK] Browser opened to: $url" -ForegroundColor Green

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  ✓ Demo Complete!" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your browser is showing the NextGen Analysis results." -ForegroundColor White
Write-Host ""
Write-Host "What you will see:" -ForegroundColor Yellow
Write-Host "  • Mode Summary - Distribution of driving conditions"
Write-Host "  • Coverage Gaps - Missing regions with priorities"
Write-Host "  • Spark Valley - Timing anomalies with confidence"
Write-Host "  • Cause Tree - Diagnostic hypotheses ranked by confidence"
Write-Host "  • Test Planner Constraints - Configure your preferences"
Write-Host "  • Cell Target Heatmap - Visual priority map (Phase 7)"
Write-Host "  • Next Test Plan - Efficiency-scored suggestions (Phase 7)"
Write-Host ""
Write-Host "Analysis files saved to:" -ForegroundColor Yellow
Write-Host "  runs\$runId\NextGenAnalysis.json" -ForegroundColor Gray
Write-Host ""
