# setup-libs.ps1
# Copies required DLLs from YourDyno install directory to the local lib/ folder
# for building the DynoAI Bridge plugin.
#
# Usage: .\setup-libs.ps1 [-YourDynoPath "C:\Program Files (x86)\YourDyno UnaVision"]

param(
    [string]$YourDynoPath = "C:\Program Files (x86)\YourDyno UnaVision"
)

$ErrorActionPreference = "Stop"

$libDir = Join-Path $PSScriptRoot "lib"

if (-not (Test-Path $YourDynoPath)) {
    Write-Error "YourDyno not found at: $YourDynoPath"
    Write-Host "Specify the install path: .\setup-libs.ps1 -YourDynoPath 'C:\path\to\YourDyno'"
    exit 1
}

# Create lib directory
if (-not (Test-Path $libDir)) {
    New-Item -ItemType Directory -Path $libDir | Out-Null
    Write-Host "Created lib/ directory"
}

# DLLs we need to reference for building
$requiredDlls = @(
    "PluginContracts.dll",
    "DynoDataConnection.dll",
    "Newtonsoft.Json.dll"
)

$copied = 0
foreach ($dll in $requiredDlls) {
    $src = Join-Path $YourDynoPath $dll
    $dst = Join-Path $libDir $dll

    if (-not (Test-Path $src)) {
        Write-Warning "NOT FOUND: $src"
        continue
    }

    Copy-Item $src $dst -Force
    $copied++
    Write-Host "  Copied: $dll"
}

Write-Host ""
Write-Host "Setup complete. $copied of $($requiredDlls.Count) DLLs copied to lib/"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Open DynoAIBridge.sln in Visual Studio"
Write-Host "  2. Build in Release mode"
Write-Host "  3. Copy bin\Release\DynoAIBridge.dll to %ProgramData%\YourDynoPlugins\"
Write-Host "  4. Restart YourDyno"
