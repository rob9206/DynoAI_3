param(
    [string]$OutputDir = "public_export",
    [string]$PublicRemoteUrl = ""
)

$ErrorActionPreference = "Stop"

function Remove-IfExists([string]$Path) {
    if (Test-Path $Path) {
        Remove-Item -Force -Recurse $Path
    }
}

function Replace-InFiles([string[]]$Globs, [hashtable]$Replacements) {
    $files = Get-ChildItem -Recurse -File -Path "." -Include $Globs -ErrorAction SilentlyContinue
    foreach ($f in $files) {
        $text = Get-Content -Raw -LiteralPath $f.FullName
        $newText = $text
        foreach ($k in $Replacements.Keys) {
            $newText = $newText -replace [regex]::Escape($k), $Replacements[$k]
        }
        if ($newText -ne $text) {
            Set-Content -LiteralPath $f.FullName -Value $newText -NoNewline
        }
    }
}

# Ensure we are at repo root
$repoRoot = (git rev-parse --show-toplevel) 2>$null
if (-not $repoRoot) { throw "Not in a git repository." }
Set-Location $repoRoot

# Create output dir
if (Test-Path $OutputDir) {
    Write-Host "Removing existing output: $OutputDir"
    Remove-IfExists $OutputDir
}
New-Item -ItemType Directory -Path $OutputDir | Out-Null

Write-Host "Exporting current HEAD to $OutputDir ..."
# Use git archive to export tracked files only (no .git)
# Prefer zip + Expand-Archive (works on Windows PowerShell without tar)
$zipPath = Join-Path $repoRoot ".public_export_temp.zip"
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
git archive --format=zip -o $zipPath HEAD
Expand-Archive -Path $zipPath -DestinationPath $OutputDir -Force
Remove-Item -Force $zipPath

# Sanity: ensure something was exported
if (-not (Get-ChildItem -Path $OutputDir -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1)) {
    throw "Export failed: $OutputDir is empty."
}

Set-Location $OutputDir

Write-Host "Removing non-public-safe artifacts/configs ..."
$removePaths = @(
    "dynoai.db",
    "agent_outputs",
    "deepcode_generated",
    "deepcode_lab",
    "mcp_agent.secrets.yaml",
    "mcp_agent.config.yaml",
    "jetdrive_log_20251218_225651.csv",
    "jetdrive_log_20251218_230024.csv"
)
foreach ($p in $removePaths) { Remove-IfExists $p }

# Remove any other jetdrive logs if present
Get-ChildItem -File -Filter "jetdrive_log_*.csv" -ErrorAction SilentlyContinue | ForEach-Object { Remove-Item -Force $_.FullName }

Write-Host "Redacting site-specific identifiers (serial/IP/location) in exported sources ..."
$replacements = @{
    "RT00220413"      = "RT00000000"
    "192.168.1.115"   = "192.168.0.100"
    "Dawson Dynamics" = "YOUR_SHOP_NAME"
}
Replace-InFiles @("*.py", "*.md", "*.txt", "*.json", "*.ts", "*.tsx", "*.ps1", "*.bat", "*.yml", "*.yaml") $replacements

# Make dyno env template generic if present
if (Test-Path "config/dyno-env-template.txt") {
    (Get-Content "config/dyno-env-template.txt") |
    ForEach-Object {
        $_ -replace "DYNO_SERIAL=.*", "DYNO_SERIAL=RT00000000" `
            -replace "DYNO_LOCATION=.*", "DYNO_LOCATION=YOUR_SHOP_NAME" `
            -replace "DYNO_IP=.*", "DYNO_IP=192.168.0.100"
    } | Set-Content "config/dyno-env-template.txt" -NoNewline
}

Write-Host "Initializing standalone public git repo in $OutputDir ..."
git init | Out-Null
# Ensure branch name is "main" for modern hosts
try {
    git checkout -b main | Out-Null
}
catch {
    git branch -M main | Out-Null
}
git add -A
git commit -m "Initial public release (sanitized export)" | Out-Null

if ($PublicRemoteUrl -ne "") {
    Write-Host "Adding remote origin: $PublicRemoteUrl"
    git remote add origin $PublicRemoteUrl
    Write-Host "Ready to push: git push -u origin main"
}

Write-Host ""
Write-Host "Done."
Write-Host "Public repo export at: $repoRoot\\$OutputDir"

