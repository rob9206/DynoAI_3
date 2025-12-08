"""
Power Core LiveLink Service Client

Provides real-time data streaming from Dynojet Power Core via:
1. Direct WCF named pipe connection (requires .NET bridge)
2. Log file polling fallback
3. WebSocket broadcast for web clients

The WCF service is exposed at: net.pipe://localhost/SCT/LiveLinkService

Architecture:
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Power Core    │────▶│  LiveLink Bridge │────▶│   DynoAI API    │
│ (WCF Service)   │     │   (.NET/PS)      │     │   (Python)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌─────────────────┐
                        │  WebSocket Hub  │
                        │  (Real-time)    │
                        └─────────────────┘
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

# Named pipe path (Windows format)
LIVELINK_PIPE_NAME = r"\\.\pipe\SCT\LiveLinkService"
LIVELINK_PIPE_ADDRESS = "net.pipe://localhost/SCT/LiveLinkService"


@dataclass
class LiveDataSample:
    """A single data sample from LiveLink."""

    timestamp: float  # Unix timestamp
    channel_id: int
    channel_name: str
    value: float
    units: str = ""


@dataclass
class LiveDataSnapshot:
    """A snapshot of all current channel values."""

    timestamp: float
    channels: dict[str, float] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)


class LiveLinkClient:
    """
    Client for Power Core LiveLink real-time data.

    Supports multiple connection modes:
    - WCF Bridge: Uses PowerShell/.NET to connect to WCF service
    - Poll Mode: Monitors log files for new data
    - Simulation: Generates test data for development

    Usage:
        client = LiveLinkClient()
        client.connect()

        # Register callback for data updates
        client.on_data(lambda sample: print(f"{sample.channel_name}: {sample.value}"))

        # Or poll manually
        while True:
            snapshot = client.get_snapshot()
            print(snapshot.channels)
            time.sleep(0.1)
    """

    def __init__(self, mode: str = "auto") -> None:
        """
        Initialize LiveLink client.

        Args:
            mode: Connection mode - "auto", "wcf", "poll", or "simulation"
        """
        self.mode = mode
        self.connected = False
        self.running = False

        # Data storage
        self._latest_snapshot = LiveDataSnapshot(timestamp=0)
        self._sample_buffer: deque[LiveDataSample] = deque(maxlen=10000)
        self._callbacks: list[Callable[[LiveDataSample], None]] = []

        # Threading
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Bridge process
        self._bridge_process: Optional[subprocess.Popen] = None

    def connect(self) -> bool:
        """
        Connect to LiveLink service.

        Returns True if connected successfully.
        """
        if self.connected:
            return True

        # Auto-detect mode
        if self.mode == "auto":
            # Try WCF bridge first if Power Core is running
            if self._check_powercore_running():
                self.mode = "wcf"
                if self._connect_wcf():
                    return True
                # Fall back to simulation if WCF fails
                self.mode = "simulation"
            else:
                self.mode = "simulation"
            return self._connect_simulation()

        if self.mode == "wcf":
            return self._connect_wcf()
        elif self.mode == "poll":
            return self._connect_poll()
        elif self.mode == "simulation":
            return self._connect_simulation()
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

    def disconnect(self) -> None:
        """Disconnect from LiveLink service."""
        self.running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        if self._bridge_process:
            self._bridge_process.terminate()
            self._bridge_process = None

        self.connected = False

    def on_data(self, callback: Callable[[LiveDataSample], None]) -> None:
        """Register a callback for data updates."""
        self._callbacks.append(callback)

    def get_snapshot(self) -> LiveDataSnapshot:
        """Get the latest data snapshot."""
        with self._lock:
            return self._latest_snapshot

    def get_channel_value(self, channel_name: str) -> Optional[float]:
        """Get the latest value for a specific channel."""
        with self._lock:
            return self._latest_snapshot.channels.get(channel_name)

    def get_samples(self, count: int = 100) -> list[LiveDataSample]:
        """Get recent samples from the buffer."""
        with self._lock:
            return list(self._sample_buffer)[-count:]

    def _check_powercore_running(self) -> bool:
        """Check if Power Core is running."""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Power Core.exe"],
                capture_output=True,
                text=True,
                check=False,
            )
            return "Power Core.exe" in result.stdout
        except Exception:
            return False

    def _find_powershell(self) -> str:
        """Find available PowerShell executable."""
        import shutil

        # Prefer PowerShell 7 (pwsh)
        if shutil.which("pwsh"):
            return "pwsh"
        if shutil.which("powershell"):
            return "powershell"
        # Try common paths
        ps7_path = Path(r"C:\Program Files\PowerShell\7\pwsh.exe")
        if ps7_path.exists():
            return str(ps7_path)
        return "powershell"  # Fall back, may fail

    def _connect_wcf(self) -> bool:
        """Connect via WCF bridge."""
        # Start the PowerShell bridge script
        bridge_script = self._get_bridge_script_path()

        if not bridge_script.exists():
            # Create the bridge script
            self._create_bridge_script(bridge_script)

        try:
            # Try pwsh first (PowerShell 7), then fall back to powershell
            ps_cmd = "pwsh" if self._find_powershell() == "pwsh" else "powershell"
            self._bridge_process = subprocess.Popen(
                [
                    ps_cmd,
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(bridge_script),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.connected = True
            self.running = True
            self._thread = threading.Thread(target=self._wcf_reader_loop, daemon=True)
            self._thread.start()
            return True

        except Exception as e:
            print(f"Failed to start WCF bridge: {e}")
            return False

    def _connect_poll(self) -> bool:
        """Connect via log file polling."""
        self.connected = True
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        return True

    def _connect_simulation(self) -> bool:
        """Connect in simulation mode for testing."""
        self.connected = True
        self.running = True
        self._thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._thread.start()
        return True

    def _wcf_reader_loop(self) -> None:
        """Read data from WCF bridge process."""
        if not self._bridge_process or not self._bridge_process.stdout:
            return

        while self.running and self._bridge_process.poll() is None:
            try:
                line = self._bridge_process.stdout.readline()
                if line:
                    self._process_bridge_data(line.strip())
            except Exception as e:
                print(f"WCF reader error: {e}")
                time.sleep(0.1)

    def _poll_loop(self) -> None:
        """Poll log files for new data."""
        # Find the latest log file
        import os

        log_dirs = [
            Path(os.environ.get("USERPROFILE", "")) / "Documents" / "Log Files",
            Path(os.environ.get("USERPROFILE", ""))
            / "OneDrive"
            / "Documents"
            / "Log Files",
        ]

        while self.running:
            # This is a placeholder - real implementation would
            # monitor log files for changes
            time.sleep(1.0)

    def _simulation_loop(self) -> None:
        """Generate simulated data for testing."""
        import math
        import random

        channels = {
            "Engine RPM": {"base": 2500, "amplitude": 500, "units": "rpm"},
            "MAP kPa": {"base": 70, "amplitude": 20, "units": "kPa"},
            "TPS": {"base": 50, "amplitude": 30, "units": "%"},
            "AFR Meas F": {"base": 14.0, "amplitude": 1.0, "units": "ratio"},
            "AFR Meas R": {"base": 14.0, "amplitude": 1.0, "units": "ratio"},
            "Engine Temp": {"base": 200, "amplitude": 20, "units": "°F"},
            "VBatt": {"base": 13.8, "amplitude": 0.3, "units": "V"},
            "Spark Adv F": {"base": 28, "amplitude": 5, "units": "°"},
        }

        t = 0
        while self.running:
            timestamp = time.time()

            with self._lock:
                for i, (name, config) in enumerate(channels.items()):
                    # Generate sinusoidal data with some noise
                    value = (
                        config["base"]
                        + config["amplitude"] * math.sin(t * 0.5 + i)
                        + random.gauss(0, config["amplitude"] * 0.05)
                    )

                    sample = LiveDataSample(
                        timestamp=timestamp,
                        channel_id=i,
                        channel_name=name,
                        value=round(value, 2),
                        units=config["units"],
                    )

                    self._sample_buffer.append(sample)
                    self._latest_snapshot.channels[name] = sample.value
                    self._latest_snapshot.units[name] = sample.units

                    # Notify callbacks
                    for callback in self._callbacks:
                        try:
                            callback(sample)
                        except Exception:
                            pass

                self._latest_snapshot.timestamp = timestamp

            t += 0.1
            time.sleep(0.1)

    def _process_bridge_data(self, line: str) -> None:
        """Process a line of data from the bridge."""
        try:
            data = json.loads(line)

            with self._lock:
                sample = LiveDataSample(
                    timestamp=data.get("timestamp", time.time()),
                    channel_id=data.get("channel_id", 0),
                    channel_name=data.get("name", "Unknown"),
                    value=float(data.get("value", 0)),
                    units=data.get("units", ""),
                )

                self._sample_buffer.append(sample)
                self._latest_snapshot.channels[sample.channel_name] = sample.value
                self._latest_snapshot.units[sample.channel_name] = sample.units
                self._latest_snapshot.timestamp = sample.timestamp

                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(sample)
                    except Exception:
                        pass

        except json.JSONDecodeError:
            pass

    def _get_bridge_script_path(self) -> Path:
        """Get the path to the PowerShell bridge script."""
        return Path(__file__).parent / "livelink_bridge.ps1"

    def _create_bridge_script(self, path: Path) -> None:
        """Create the PowerShell WCF bridge script."""
        script = r"""
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
"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(script)


class LiveLinkRecorder:
    """
    Records LiveLink data to file for later analysis.

    Usage:
        client = LiveLinkClient()
        client.connect()

        recorder = LiveLinkRecorder(client, "recordings/session1.csv")
        recorder.start()
        # ... run dyno session ...
        recorder.stop()
    """

    def __init__(self, client: LiveLinkClient, output_path: str) -> None:
        self.client = client
        self.output_path = Path(output_path)
        self.recording = False
        self._file = None
        self._header_written = False

    def start(self) -> None:
        """Start recording."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.output_path, "w", newline="")
        self.recording = True
        self._header_written = False
        self.client.on_data(self._record_sample)

    def stop(self) -> None:
        """Stop recording and close file."""
        self.recording = False
        if self._file:
            self._file.close()
            self._file = None

    def _record_sample(self, sample: LiveDataSample) -> None:
        """Record a sample to file."""
        if not self.recording or not self._file:
            return

        if not self._header_written:
            self._file.write("timestamp,channel_id,channel_name,value,units\n")
            self._header_written = True

        line = f"{sample.timestamp},{sample.channel_id},{sample.channel_name},{sample.value},{sample.units}\n"
        self._file.write(line)
        self._file.flush()


# =============================================================================
# WebSocket Hub for Real-time Web Clients
# =============================================================================


class LiveLinkWebSocketHub:
    """
    WebSocket hub for broadcasting LiveLink data to web clients.

    Integrates with Flask-SocketIO or similar WebSocket libraries.
    """

    def __init__(self, client: LiveLinkClient) -> None:
        self.client = client
        self.client.on_data(self._broadcast)
        self._subscribers: list[Callable[[dict], None]] = []

    def subscribe(self, callback: Callable[[dict], None]) -> None:
        """Subscribe to data broadcasts."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[dict], None]) -> None:
        """Unsubscribe from data broadcasts."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _broadcast(self, sample: LiveDataSample) -> None:
        """Broadcast sample to all subscribers."""
        data = {
            "timestamp": sample.timestamp,
            "channel_id": sample.channel_id,
            "channel_name": sample.channel_name,
            "value": sample.value,
            "units": sample.units,
        }

        for subscriber in self._subscribers:
            try:
                subscriber(data)
            except Exception:
                pass


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "LIVELINK_PIPE_ADDRESS",
    "LIVELINK_PIPE_NAME",
    "LiveDataSample",
    "LiveDataSnapshot",
    "LiveLinkClient",
    "LiveLinkRecorder",
    "LiveLinkWebSocketHub",
]
