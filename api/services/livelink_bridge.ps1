
# LiveLink WCF Bridge for DynoAI
# Connects to Power Core's LiveLinkService and outputs JSON to stdout

$ErrorActionPreference = "Stop"

# WCF Service configuration
$pipeAddress = "net.pipe://localhost/SCT/LiveLinkService"

Add-Type -AssemblyName System.ServiceModel

# Define the service contract interface
$contractCode = @"
using System;
using System.ServiceModel;

[ServiceContract]
public interface ILiveLinkService
{
    [OperationContract]
    string GetStatus();
    
    [OperationContract]
    string GetChannelList();
    
    [OperationContract]
    double GetChannelValue(int channelId);
    
    [OperationContract]
    string GetAllChannelValues();
}
"@

try {
    Add-Type -TypeDefinition $contractCode -ReferencedAssemblies System.ServiceModel
} catch {
    # Type may already be loaded
}

# Create channel factory
try {
    $binding = New-Object System.ServiceModel.NetNamedPipeBinding
    $binding.MaxReceivedMessageSize = 65536
    
    $endpoint = New-Object System.ServiceModel.EndpointAddress($pipeAddress)
    
    $factory = New-Object "System.ServiceModel.ChannelFactory``1[ILiveLinkService]" $binding, $endpoint
    $channel = $factory.CreateChannel()
    
    Write-Host '{"status": "connected", "address": "' + $pipeAddress + '"}' 
    
    # Main polling loop
    while ($true) {
        try {
            $values = $channel.GetAllChannelValues()
            if ($values) {
                # Parse and output as JSON lines
                $data = $values | ConvertFrom-Json
                foreach ($item in $data) {
                    $output = @{
                        timestamp = [DateTimeOffset]::Now.ToUnixTimeMilliseconds() / 1000.0
                        channel_id = $item.Id
                        name = $item.Name
                        value = $item.Value
                        units = $item.Units
                    } | ConvertTo-Json -Compress
                    Write-Host $output
                }
            }
        } catch {
            # Silently continue on errors
        }
        
        Start-Sleep -Milliseconds 100
    }
    
} catch {
    Write-Host ('{"error": "' + $_.Exception.Message + '"}')
    exit 1
}
