$ErrorActionPreference = "Stop"

$bundle = "fatboy_min_bundle.zip"
if (!(Test-Path $bundle)) {
  throw "Bundle not found: $bundle"
}

git fetch origin
git checkout main
git pull --ff-only

Expand-Archive -Path $bundle -DestinationPath "." -Force
Write-Host "Extracted $bundle" -ForegroundColor Green

Write-Host "Verify imported paths:" -ForegroundColor Cyan
$checks = @(
  "docs/sessions/DAI-2026-0510-RT-FATBOY",
  "vehicles/doodledyna/profile.json",
  "vehicles/doodledyna/sessions/20260421_233219"
)
foreach ($c in $checks) {
  Write-Host (" - {0}: {1}" -f $c, (Test-Path $c))
}
