$ErrorActionPreference = "Stop"

$bundle = "fatboy_min_bundle.zip"
if (Test-Path $bundle) { Remove-Item $bundle -Force }

# Minimal Fatboy export set.
$paths = @(
  "docs/sessions/DAI-2026-0510-RT-FATBOY",
  "vehicles/doodledyna/profile.json",
  "vehicles/doodledyna/sessions/20260421_233219"
)

$existing = @()
foreach ($p in $paths) {
  if (Test-Path $p) { $existing += $p }
}

if ($existing.Count -eq 0) {
  throw "No minimal Fatboy paths found to export."
}

Compress-Archive -Path $existing -DestinationPath $bundle -Force
Write-Host "Created $bundle with:" -ForegroundColor Green
$existing | ForEach-Object { Write-Host " - $_" }
