# JetDrive Live Data Logger
# Logs all channel data to a CSV file

$apiUrl = "http://localhost:5001/api/jetdrive/hardware/live/data"
$outputFile = "jetdrive_log_$(Get-Date -Format 'yyyyMMdd_HHmmss').csv"

Write-Host "Starting JetDrive data logger..." -ForegroundColor Green
Write-Host "Output file: $outputFile" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop logging" -ForegroundColor Yellow
Write-Host ""

# Create CSV header
$header = $true

try {
    while ($true) {
        try {
            # Get live data
            $response = Invoke-RestMethod -Uri $apiUrl -Method Get
            
            if ($response.channel_count -gt 0) {
                $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
                
                # Create a row with timestamp and all channel values
                $row = [PSCustomObject]@{
                    Timestamp = $timestamp
                }
                
                # Add each channel value
                foreach ($channelName in $response.channels.PSObject.Properties.Name) {
                    $channel = $response.channels.$channelName
                    $row | Add-Member -NotePropertyName $channelName -NotePropertyValue $channel.value
                }
                
                # Write to CSV
                if ($header) {
                    $row | Export-Csv -Path $outputFile -NoTypeInformation
                    $header = $false
                    Write-Host "Logging started - $($response.channel_count) channels" -ForegroundColor Green
                } else {
                    $row | Export-Csv -Path $outputFile -NoTypeInformation -Append
                }
                
                # Display current values
                Write-Host "`r[$timestamp] Channels: $($response.channel_count) | " -NoNewline -ForegroundColor Gray
                
                # Show key channels if available
                $keyChannels = @('Power', 'Torque', 'Digital RPM 1', 'Engine Speed', 'Speed')
                $displayValues = @()
                foreach ($key in $keyChannels) {
                    if ($response.channels.$key) {
                        $value = [math]::Round($response.channels.$key.value, 1)
                        $displayValues += "$key=$value"
                    }
                }
                if ($displayValues.Count -gt 0) {
                    Write-Host ($displayValues -join " | ") -NoNewline -ForegroundColor Cyan
                }
                
            } else {
                Write-Host "`r[$(Get-Date -Format 'HH:mm:ss')] Waiting for data..." -NoNewline -ForegroundColor Yellow
            }
            
        } catch {
            Write-Host "`r[$(Get-Date -Format 'HH:mm:ss')] Error: $($_.Exception.Message)" -NoNewline -ForegroundColor Red
        }
        
        # Wait before next poll (250ms for smooth updates)
        Start-Sleep -Milliseconds 250
    }
} finally {
    Write-Host "`n`nLogging stopped." -ForegroundColor Green
    Write-Host "Data saved to: $outputFile" -ForegroundColor Cyan
    
    # Show summary
    if (Test-Path $outputFile) {
        $lines = (Get-Content $outputFile).Count - 1
        Write-Host "Total samples logged: $lines" -ForegroundColor Green
    }
}

