"""
JetDrive API Client for DynoAI PyQt6 GUI
Handles live data polling from the JetDrive dyno
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer
import requests


class ConnectionStatus(Enum):
    """JetDrive connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class JetDriveChannel:
    """A JetDrive data channel."""
    name: str
    value: float
    units: str = ""
    timestamp: float = 0


@dataclass
class JetDriveSample:
    """A sample of JetDrive data."""
    timestamp: float
    rpm: float = 0
    torque: float = 0
    horsepower: float = 0
    map_kpa: float = 0
    afr_front: float = 14.7
    afr_rear: float = 14.7
    temperature: float = 0
    humidity: float = 0
    pressure: float = 0
    channels: Dict[str, float] = field(default_factory=dict)


@dataclass
class RunInfo:
    """Information about a detected run."""
    run_id: str
    timestamp: str
    peak_hp: float
    peak_tq: float
    status: str
    source: str = "unknown"
    notes: str = ""


class JetDriveWorker(QObject):
    """
    Worker for polling JetDrive data in a separate thread.
    """
    
    # Signals
    data_received = pyqtSignal(object)  # JetDriveSample
    error = pyqtSignal(str)
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    
    def __init__(
        self,
        api_url: str = "http://127.0.0.1:5001/api/jetdrive",
        poll_interval: int = 100,  # ms
    ):
        super().__init__()
        self.api_url = api_url
        self.poll_interval = poll_interval
        self._running = False
        self._timer: Optional[QTimer] = None
        
    def start(self) -> None:
        """Start polling."""
        self._running = True
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll)
        self._timer.start(self.poll_interval)
        self.connected.emit()
        
    def stop(self) -> None:
        """Stop polling."""
        self._running = False
        if self._timer:
            self._timer.stop()
            self._timer = None
        self.disconnected.emit()
        
    def _poll(self) -> None:
        """Poll for new data."""
        if not self._running:
            return
            
        try:
            response = requests.get(f"{self.api_url}/live", timeout=1)
            response.raise_for_status()
            data = response.json()
            
            # Parse into sample
            sample = self._parse_sample(data)
            self.data_received.emit(sample)
            
        except requests.exceptions.Timeout:
            pass  # Ignore timeouts, will retry
        except requests.exceptions.ConnectionError:
            self.error.emit("Cannot connect to JetDrive API")
        except Exception as e:
            self.error.emit(str(e))
            
    def _parse_sample(self, data: Dict[str, Any]) -> JetDriveSample:
        """Parse API response into a sample."""
        channels = data.get("channels", {})
        
        return JetDriveSample(
            timestamp=data.get("timestamp", 0),
            rpm=channels.get("Digital RPM 1", 0),
            torque=channels.get("Torque", 0),
            horsepower=channels.get("Horsepower", 0),
            map_kpa=channels.get("MAP kPa", 0),
            afr_front=channels.get("Air/Fuel Ratio 1", 14.7),
            afr_rear=channels.get("Air/Fuel Ratio 2", 14.7),
            temperature=channels.get("Temperature 1", 0),
            humidity=channels.get("Humidity", 0),
            pressure=channels.get("Pressure", 0),
            channels=channels,
        )


class JetDriveClient(QObject):
    """
    High-level JetDrive client for PyQt6.
    Manages polling, run detection, and data history.
    """
    
    # Signals
    status_changed = pyqtSignal(object)  # ConnectionStatus
    sample_received = pyqtSignal(object)  # JetDriveSample
    run_detected = pyqtSignal(object)  # RunInfo
    run_completed = pyqtSignal(object)  # RunInfo
    error = pyqtSignal(str)
    
    # Run detection thresholds
    RUN_START_RPM = 2500
    RUN_START_HP = 20
    RUN_END_RPM = 1500
    MIN_RUN_DURATION = 2.0  # seconds
    
    def __init__(
        self,
        api_url: str = "http://127.0.0.1:5001/api/jetdrive",
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        
        self.api_url = api_url
        self._status = ConnectionStatus.DISCONNECTED
        self._worker: Optional[JetDriveWorker] = None
        self._thread: Optional[QThread] = None
        
        # Data history
        self._history: List[JetDriveSample] = []
        self._max_history = 1000
        
        # Run detection state
        self._in_run = False
        self._run_start_time = 0
        self._current_run_id: Optional[str] = None
        self._peak_hp = 0
        self._peak_tq = 0
        
        # Latest sample
        self._latest_sample: Optional[JetDriveSample] = None
        
    @property
    def status(self) -> ConnectionStatus:
        """Get current connection status."""
        return self._status
        
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._status == ConnectionStatus.CONNECTED
        
    @property
    def latest_sample(self) -> Optional[JetDriveSample]:
        """Get the latest data sample."""
        return self._latest_sample
        
    def connect(self) -> None:
        """Connect to JetDrive and start polling."""
        if self._status == ConnectionStatus.CONNECTED:
            return
            
        self._status = ConnectionStatus.CONNECTING
        self.status_changed.emit(self._status)
        
        # Create worker and thread
        self._worker = JetDriveWorker(self.api_url)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        
        # Connect signals
        self._thread.started.connect(self._worker.start)
        self._worker.data_received.connect(self._on_data_received)
        self._worker.error.connect(self._on_error)
        self._worker.connected.connect(self._on_connected)
        self._worker.disconnected.connect(self._on_disconnected)
        
        # Start
        self._thread.start()
        
    def disconnect(self) -> None:
        """Disconnect from JetDrive."""
        if self._worker:
            self._worker.stop()
            
        if self._thread:
            self._thread.quit()
            self._thread.wait(1000)
            self._thread = None
            
        self._worker = None
        self._status = ConnectionStatus.DISCONNECTED
        self.status_changed.emit(self._status)
        
    def _on_connected(self) -> None:
        """Handle connection established."""
        self._status = ConnectionStatus.CONNECTED
        self.status_changed.emit(self._status)
        
    def _on_disconnected(self) -> None:
        """Handle disconnection."""
        self._status = ConnectionStatus.DISCONNECTED
        self.status_changed.emit(self._status)
        
    def _on_error(self, error: str) -> None:
        """Handle error."""
        self._status = ConnectionStatus.ERROR
        self.status_changed.emit(self._status)
        self.error.emit(error)
        
    def _on_data_received(self, sample: JetDriveSample) -> None:
        """Handle new data sample."""
        self._latest_sample = sample
        
        # Add to history
        self._history.append(sample)
        if len(self._history) > self._max_history:
            self._history.pop(0)
            
        # Emit signal
        self.sample_received.emit(sample)
        
        # Run detection
        self._detect_run(sample)
        
    def _detect_run(self, sample: JetDriveSample) -> None:
        """Detect run start/end based on RPM and HP."""
        if not self._in_run:
            # Check for run start
            if sample.rpm >= self.RUN_START_RPM and sample.horsepower >= self.RUN_START_HP:
                self._in_run = True
                self._run_start_time = sample.timestamp
                self._peak_hp = sample.horsepower
                self._peak_tq = sample.torque
                
                # Generate run ID
                import uuid
                self._current_run_id = str(uuid.uuid4())[:8]
                
                run_info = RunInfo(
                    run_id=self._current_run_id,
                    timestamp=str(sample.timestamp),
                    peak_hp=self._peak_hp,
                    peak_tq=self._peak_tq,
                    status="capturing",
                )
                self.run_detected.emit(run_info)
        else:
            # Update peaks
            if sample.horsepower > self._peak_hp:
                self._peak_hp = sample.horsepower
            if sample.torque > self._peak_tq:
                self._peak_tq = sample.torque
                
            # Check for run end
            if sample.rpm < self.RUN_END_RPM:
                duration = sample.timestamp - self._run_start_time
                
                if duration >= self.MIN_RUN_DURATION:
                    # Valid run completed
                    run_info = RunInfo(
                        run_id=self._current_run_id or "unknown",
                        timestamp=str(self._run_start_time),
                        peak_hp=self._peak_hp,
                        peak_tq=self._peak_tq,
                        status="completed",
                    )
                    self.run_completed.emit(run_info)
                    
                self._in_run = False
                self._current_run_id = None
                
    def get_history(self, count: int = 100) -> List[JetDriveSample]:
        """Get recent data history."""
        return self._history[-count:]
        
    def clear_history(self) -> None:
        """Clear data history."""
        self._history.clear()
        
    def get_runs(self) -> None:
        """Fetch list of past runs from API."""
        try:
            response = requests.get(f"{self.api_url}/runs", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            runs = []
            for r in data.get("runs", []):
                runs.append(RunInfo(
                    run_id=r.get("run_id", ""),
                    timestamp=r.get("timestamp", ""),
                    peak_hp=r.get("peak_hp", 0),
                    peak_tq=r.get("peak_tq", 0),
                    status=r.get("status", "unknown"),
                    source=r.get("source", "unknown"),
                ))
            return runs
            
        except Exception as e:
            self.error.emit(f"Failed to get runs: {e}")
            return []
            
    def check_health(self) -> Dict[str, Any]:
        """Check JetDrive hardware health."""
        try:
            response = requests.get(f"{self.api_url}/hardware/health", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}

