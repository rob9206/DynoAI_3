# Copy Jetstream files from DynoAI_3-main to current directory

Write-Host "Copying Jetstream integration files..." -ForegroundColor Cyan

# Create directories
New-Item -ItemType Directory -Path ".\api\jetstream" -Force | Out-Null
New-Item -ItemType Directory -Path ".\api\routes" -Force | Out-Null
New-Item -ItemType Directory -Path ".\api\services" -Force | Out-Null

# Copy Jetstream files
Write-Host "Copying api/jetstream/..." -ForegroundColor Yellow
Copy-Item ".\DynoAI_3-main\api\jetstream\*" -Destination ".\api\jetstream\" -Recurse -Force

# Copy routes
Write-Host "Copying api/routes/..." -ForegroundColor Yellow
Copy-Item ".\DynoAI_3-main\api\routes\*" -Destination ".\api\routes\" -Recurse -Force

# Copy services
Write-Host "Copying api/services/..." -ForegroundColor Yellow
Copy-Item ".\DynoAI_3-main\api\services\*" -Destination ".\api\services\" -Recurse -Force

# Copy documentation
Write-Host "Copying documentation..." -ForegroundColor Yellow
Copy-Item ".\DynoAI_3-main\JETSTREAM_STUB_TEST_RESULTS.md" -Destination "." -Force -ErrorAction SilentlyContinue
Copy-Item ".\DynoAI_3-main\QUICK_START_STUB_MODE.md" -Destination "." -Force -ErrorAction SilentlyContinue
Copy-Item ".\DynoAI_3-main\STUB_DATA_TESTING_SUMMARY.md" -Destination "." -Force -ErrorAction SilentlyContinue
Copy-Item ".\DynoAI_3-main\start-stub-mode.ps1" -Destination "." -Force -ErrorAction SilentlyContinue

# Verify
Write-Host "`nVerification:" -ForegroundColor Green
Write-Host "  api/jetstream: $(Test-Path '.\api\jetstream')" -ForegroundColor $(if (Test-Path '.\api\jetstream') { 'Green' } else { 'Red' })
Write-Host "  api/routes: $(Test-Path '.\api\routes')" -ForegroundColor $(if (Test-Path '.\api\routes') { 'Green' } else { 'Red' })
Write-Host "  api/services: $(Test-Path '.\api\services')" -ForegroundColor $(if (Test-Path '.\api\services') { 'Green' } else { 'Red' })

Write-Host "`nFile counts:" -ForegroundColor Green
Write-Host "  Jetstream files: $((Get-ChildItem '.\api\jetstream' -File).Count)"
Write-Host "  Route files: $((Get-ChildItem '.\api\routes' -Recurse -File).Count)"
Write-Host "  Service files: $((Get-ChildItem '.\api\services' -Recurse -File).Count)"

Write-Host "`nDone! Jetstream integration copied successfully." -ForegroundColor Green
Write-Host "You can now restart the backend to use Jetstream features." -ForegroundColor Cyan

