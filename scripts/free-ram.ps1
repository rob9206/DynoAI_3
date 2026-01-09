# Script to help free up RAM by stopping unnecessary services

Write-Host "=== RAM Usage Before ===" -ForegroundColor Cyan
$totalRAM = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB
$freeRAM = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
$usedRAM = $totalRAM - ($freeRAM / 1024)
Write-Host "Total RAM: $([math]::Round($totalRAM, 2)) GB" -ForegroundColor Yellow
Write-Host "Used RAM: $([math]::Round($usedRAM, 2)) GB" -ForegroundColor Yellow
Write-Host "Free RAM: $([math]::Round($freeRAM / 1024, 2)) GB" -ForegroundColor Green
Write-Host ""

# Check for Docker Desktop
$dockerProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
if ($dockerProcess) {
    Write-Host "Docker Desktop is running ($([math]::Round(($dockerProcess | Measure-Object WorkingSet64 -Sum).Sum / 1MB, 2)) MB)" -ForegroundColor Yellow
    $stopDocker = Read-Host "Stop Docker Desktop? (y/n)"
    if ($stopDocker -eq 'y') {
        Stop-Process -Name "Docker Desktop" -Force -ErrorAction SilentlyContinue
        Stop-Process -Name "com.docker.backend" -Force -ErrorAction SilentlyContinue
        Write-Host "Docker Desktop stopped." -ForegroundColor Green
    }
}

# Check for WSL2
$wslProcess = Get-Process -Name "vmmemWSL" -ErrorAction SilentlyContinue
if ($wslProcess) {
    $wslMem = [math]::Round(($wslProcess | Measure-Object WorkingSet64 -Sum).Sum / 1MB, 2)
    Write-Host "WSL2 is running ($wslMem MB)" -ForegroundColor Yellow
    Write-Host "To stop WSL2, run: wsl --shutdown" -ForegroundColor Cyan
    $stopWSL = Read-Host "Shutdown WSL2? (y/n)"
    if ($stopWSL -eq 'y') {
        wsl --shutdown
        Write-Host "WSL2 shutdown." -ForegroundColor Green
    }
}

# Check for OneDrive
$oneDriveProcess = Get-Process -Name "OneDrive" -ErrorAction SilentlyContinue
if ($oneDriveProcess) {
    $oneDriveMem = [math]::Round(($oneDriveProcess | Measure-Object WorkingSet64 -Sum).Sum / 1MB, 2)
    Write-Host "OneDrive is running ($oneDriveMem MB)" -ForegroundColor Yellow
    Write-Host "You can pause OneDrive syncing from the system tray icon" -ForegroundColor Cyan
}

# Check for browser processes
$browsers = Get-Process | Where-Object {$_.ProcessName -like "*chrome*" -or $_.ProcessName -like "*msedge*" -or $_.ProcessName -like "*firefox*"} | Group-Object ProcessName
if ($browsers) {
    Write-Host "`nBrowser processes found:" -ForegroundColor Yellow
    foreach ($browser in $browsers) {
        $mem = [math]::Round(($browser.Group | Measure-Object WorkingSet64 -Sum).Sum / 1MB, 2)
        Write-Host "  $($browser.Name): $mem MB ($($browser.Count) processes)" -ForegroundColor Yellow
    }
}

Write-Host "`n=== RAM Usage After ===" -ForegroundColor Cyan
Start-Sleep -Seconds 2
$freeRAMAfter = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
$usedRAMAfter = $totalRAM - ($freeRAMAfter / 1024)
Write-Host "Used RAM: $([math]::Round($usedRAMAfter, 2)) GB" -ForegroundColor Yellow
Write-Host "Free RAM: $([math]::Round($freeRAMAfter / 1024, 2)) GB" -ForegroundColor Green
$freed = ($usedRAM - $usedRAMAfter) * 1024
if ($freed -gt 0) {
    Write-Host "Freed: $([math]::Round($freed, 2)) MB" -ForegroundColor Green
}
