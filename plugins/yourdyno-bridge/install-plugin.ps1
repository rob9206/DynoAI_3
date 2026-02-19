# install-plugin.ps1
# Copies the built DynoAIBridge.dll to YourDyno's plugin directory.
# Must be run as Administrator (or with write access to ProgramData).
#
# Usage: .\install-plugin.ps1

$ErrorActionPreference = "Stop"

$pluginDir = "C:\ProgramData\YourDynoPlugins"
$buildOutput = Join-Path $PSScriptRoot "DynoAIBridge\bin\Release\DynoAIBridge.dll"

# Also check common build output locations
$altPaths = @(
    (Join-Path $PSScriptRoot "DynoAIBridge\bin\Release\net481\DynoAIBridge.dll"),
    (Join-Path $PSScriptRoot "DynoAIBridge\bin\Debug\DynoAIBridge.dll"),
    (Join-Path $PSScriptRoot "DynoAIBridge\bin\Debug\net481\DynoAIBridge.dll")
)

$dllPath = $null
if (Test-Path $buildOutput) {
    $dllPath = $buildOutput
} else {
    foreach ($alt in $altPaths) {
        if (Test-Path $alt) {
            $dllPath = $alt
            break
        }
    }
}

if (-not $dllPath) {
    Write-Error "Build output not found. Build the solution first in Visual Studio (Release mode)."
    Write-Host "Expected at: $buildOutput"
    exit 1
}

# Create plugin directory if needed
if (-not (Test-Path $pluginDir)) {
    New-Item -ItemType Directory -Path $pluginDir | Out-Null
    Write-Host "Created: $pluginDir"
}

# Copy the plugin
$dest = Join-Path $pluginDir "DynoAIBridge.dll"
Copy-Item $dllPath $dest -Force
Write-Host "Installed: $dest"
Write-Host ""
Write-Host "Plugin installed successfully!"
Write-Host "Restart YourDyno to load the DynoAI Bridge plugin."
Write-Host ""
Write-Host "DynoAI Bridge will:"
Write-Host "  - Appear in YourDyno's menu bar (DynoAI Bridge Settings...)"
Write-Host "  - Listen on TCP port 9877 for DynoAI connections"
Write-Host "  - Stream live dyno data as JSON to DynoAI"
