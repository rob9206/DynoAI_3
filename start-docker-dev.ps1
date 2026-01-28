#!/usr/bin/env pwsh
# DynoAI Docker Setup Validation Script
# Validates that Docker environment is correctly configured before migration

param(
    [switch]$Fix,
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  DynoAI Docker Setup Validator" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

$script:issues = @()
$script:warnings = @()
$script:passed = @()

function Test-Requirement {
    param(
        [string]$Name,
        [scriptblock]$Test,
        [string]$SuccessMessage,
        [string]$FailureMessage,
        [scriptblock]$Fix = $null,
        [switch]$IsWarning
    )
    
    Write-Host "`nChecking: $Name..." -ForegroundColor Yellow -NoNewline
    
    $result = & $Test
    
    if ($result) {
        Write-Host " [OK]" -ForegroundColor Green
        if ($Verbose) { Write-Host "  $SuccessMessage" -ForegroundColor Gray }
        $script:passed += $Name
        return $true
    } else {
        if ($IsWarning) {
            Write-Host " [WARN]" -ForegroundColor Yellow
            Write-Host "  WARNING: $FailureMessage" -ForegroundColor Yellow
            $script:warnings += $FailureMessage
        } else {
            Write-Host " [FAIL]" -ForegroundColor Red
            Write-Host "  ERROR: $FailureMessage" -ForegroundColor Red
            $script:issues += $FailureMessage
        }
        
        if ($Fix -and $FixParam) {
            Write-Host "  Attempting fix..." -ForegroundColor Cyan
            & $Fix
        }
        
        return $false
    }
}

# =============================================================================
# Docker Installation
# =============================================================================

Test-Requirement -Name "Docker Installed" -Test {
    try {
        $null = Get-Command docker -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
} -SuccessMessage "Docker CLI is available" `
  -FailureMessage "Docker is not installed. Install from https://www.docker.com/products/docker-desktop"

Test-Requirement -Name "Docker Running" -Test {
    try {
        docker info 2>&1 | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
} -SuccessMessage "Docker daemon is running" `
  -FailureMessage "Docker is not running. Start Docker Desktop."

Test-Requirement -Name "Docker Compose" -Test {
    try {
        docker-compose --version 2>&1 | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
} -SuccessMessage "Docker Compose is available" `
  -FailureMessage "Docker Compose is not installed."

# =============================================================================
# Docker Configuration
# =============================================================================

Test-Requirement -Name "Docker Resources" -Test {
    try {
        $info = docker info --format '{{json .}}' | ConvertFrom-Json
        $memGB = [math]::Round($info.MemTotal / 1GB, 1)
        
        if ($Verbose) {
            Write-Host "`n  Memory: $memGB GB" -ForegroundColor Gray
            Write-Host "  CPUs: $($info.NCPU)" -ForegroundColor Gray
        }
        
        return $memGB -ge 4 -and $info.NCPU -ge 2
    } catch {
        return $false
    }
} -SuccessMessage "Sufficient resources allocated" `
  -FailureMessage "Docker needs at least 4GB RAM and 2 CPUs. Adjust in Docker Desktop settings."

# =============================================================================
# Files and Directories
# =============================================================================

Test-Requirement -Name "Dockerfile Exists" -Test {
    Test-Path "Dockerfile"
} -SuccessMessage "Main Dockerfile found" `
  -FailureMessage "Dockerfile not found in project root"

Test-Requirement -Name "Frontend Dockerfile" -Test {
    Test-Path "frontend/Dockerfile"
} -SuccessMessage "Frontend Dockerfile found" `
  -FailureMessage "frontend/Dockerfile not found"

Test-Requirement -Name "docker-compose.yml" -Test {
    Test-Path "docker-compose.yml"
} -SuccessMessage "Main compose file found" `
  -FailureMessage "docker-compose.yml not found"

Test-Requirement -Name "Environment File" -Test {
    Test-Path ".env"
} -SuccessMessage ".env file exists" `
  -FailureMessage ".env file not found" `
  -IsWarning `
  -Fix {
    if (Test-Path "config/env.example") {
        Copy-Item "config/env.example" ".env"
    Write-Host "  [OK] Created .env from config/env.example" -ForegroundColor Green
    }
}

Test-Requirement -Name ".dockerignore" -Test {
    Test-Path ".dockerignore"
} -SuccessMessage ".dockerignore found (faster builds)" `
  -FailureMessage ".dockerignore not found (builds may be slow)" `
  -IsWarning

# =============================================================================
# Network Configuration
# =============================================================================

Test-Requirement -Name "Port 5001 Available" -Test {
    $port5001 = Get-NetTCPConnection -LocalPort 5001 -ErrorAction SilentlyContinue
    return $null -eq $port5001
} -SuccessMessage "Port 5001 is available for API" `
  -FailureMessage "Port 5001 is in use. Stop other services or change API_PORT in .env" `
  -IsWarning

Test-Requirement -Name "Port 80 Available" -Test {
    $port80 = Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue
    return $null -eq $port80
} -SuccessMessage "Port 80 is available for frontend" `
  -FailureMessage "Port 80 is in use. Stop other services or change FRONTEND_PORT in .env" `
  -IsWarning

Test-Requirement -Name "Port 6379 Available" -Test {
    $port6379 = Get-NetTCPConnection -LocalPort 6379 -ErrorAction SilentlyContinue
    return $null -eq $port6379
} -SuccessMessage "Port 6379 is available for Redis" `
  -FailureMessage "Port 6379 is in use. Stop Redis or change REDIS_PORT in .env" `
  -IsWarning

# =============================================================================
# JetDrive Configuration (if enabled)
# =============================================================================

if (Test-Path ".env") {
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match "JETDRIVE_ENABLED=true") {
        
        Test-Requirement -Name "Port 22344 Available (JetDrive)" -Test {
            # UDP ports don't show in Get-NetTCPConnection, check if bindable
            try {
                $udp = New-Object System.Net.Sockets.UdpClient
                $udp.Client.SetSocketOption([System.Net.Sockets.SocketOptionLevel]::Socket, 
                                           [System.Net.Sockets.SocketOptionName]::ReuseAddress, $true)
                $udp.Client.Bind([System.Net.IPEndPoint]::new([System.Net.IPAddress]::Any, 22344))
                $udp.Close()
                return $true
            } catch {
                return $false
            }
        } -SuccessMessage "UDP port 22344 is available for JetDrive" `
          -FailureMessage "UDP port 22344 may be in use"
        
        Test-Requirement -Name "Dynoware Reachable" -Test {
            Test-Connection -ComputerName "192.168.1.115" -Count 1 -Quiet -ErrorAction SilentlyContinue
        } -SuccessMessage "Dynoware RT-150 is reachable" `
          -FailureMessage "Cannot reach Dynoware at 192.168.1.115. Check network connection." `
          -IsWarning
    }
}

# =============================================================================
# Python and Node (for local development fallback)
# =============================================================================

Test-Requirement -Name "Python Available (Fallback)" -Test {
    try {
        python --version 2>&1 | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
} -SuccessMessage "Python is available for native fallback" `
  -FailureMessage "Python not found (needed for native fallback)" `
  -IsWarning

Test-Requirement -Name "Node Available (Fallback)" -Test {
    try {
        node --version 2>&1 | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
} -SuccessMessage "Node.js is available for native fallback" `
  -FailureMessage "Node.js not found (needed for native fallback)" `
  -IsWarning

# =============================================================================
# Disk Space
# =============================================================================

Test-Requirement -Name "Disk Space" -Test {
    $drive = (Get-Location).Drive
    $freeGB = [math]::Round((Get-PSDrive $drive.Name).Free / 1GB, 1)
    
    if ($Verbose) {
        Write-Host "`n  Free space: $freeGB GB" -ForegroundColor Gray
    }
    
    return $freeGB -ge 10
} -SuccessMessage "Sufficient disk space available" `
  -FailureMessage "Less than 10GB free disk space. Docker images need space."

# =============================================================================
# Summary
# =============================================================================

Write-Host "`n" -NoNewline
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Validation Summary" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

Write-Host "`nPassed: $($script:passed.Count)" -ForegroundColor Green
if ($script:warnings.Count -gt 0) {
    Write-Host "Warnings: $($script:warnings.Count)" -ForegroundColor Yellow
}
if ($script:issues.Count -gt 0) {
    Write-Host "Errors: $($script:issues.Count)" -ForegroundColor Red
}

if ($script:issues.Count -gt 0) {
    Write-Host "`nCritical issues found:" -ForegroundColor Red
    $script:issues | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host "`nPlease resolve these issues before running Docker." -ForegroundColor Yellow
    exit 1
}

if ($script:warnings.Count -gt 0) {
    Write-Host "`nWarnings:" -ForegroundColor Yellow
    $script:warnings | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    Write-Host "`nThese issues may not prevent Docker from running." -ForegroundColor Gray
}

Write-Host ""
Write-Host "✅ Docker environment is ready!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "  1. Review .env file and customize settings" -ForegroundColor Green
Write-Host "  2. Start in development mode:" -ForegroundColor Green
Write-Host "     .\start-docker-dev.ps1 -Build" -ForegroundColor Green
Write-Host ""
Write-Host "  3. Or start in production mode:" -ForegroundColor Green
Write-Host "     .\start-docker-prod.ps1 -Build" -ForegroundColor Green
Write-Host ""
Write-Host "Documentation:" -ForegroundColor Green
Write-Host "  - Quick start: DOCKER_QUICKSTART.md" -ForegroundColor Green
Write-Host "  - Full guide: DOCKER_MIGRATION.md" -ForegroundColor Green
Write-Host ""

exit 0
