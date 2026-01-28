# Quick Upload and Analysis Demo
Write-Host "Uploading test data and generating NextGen analysis..." -ForegroundColor Cyan

$testFile = "tests\data\dense_dyno_test.csv"
$backendUrl = "http://127.0.0.1:5001"

# Upload via curl (simpler than HttpClient)
Write-Host "Uploading..." -ForegroundColor Yellow
$uploadResponse = curl.exe -X POST "$backendUrl/api/analyze" -F "file=@$testFile" --silent
$uploadData = $uploadResponse | ConvertFrom-Json
$runId = $uploadData.runId

Write-Host "Upload complete! Run ID: $runId" -ForegroundColor Green
Write-Host "Waiting for analysis..." -ForegroundColor Yellow

# Wait for analysis
Start-Sleep -Seconds 15

# Generate NextGen
Write-Host "Generating NextGen analysis..." -ForegroundColor Yellow
curl.exe -X POST "$backendUrl/api/nextgen/$runId/generate?force=true" --silent | Out-Null

Write-Host "Opening results..." -ForegroundColor Green
Start-Process "http://localhost:5173/runs/$runId"

Write-Host ""
Write-Host "Done! Your browser is showing the NextGen Analysis with all Phase 1-7 features!" -ForegroundColor Cyan
