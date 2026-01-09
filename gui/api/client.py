"""
DynoAI API Client for PyQt6
Provides threaded HTTP communication with the Flask backend
"""

import json
from dataclasses import dataclass, field
from typing import Optional, Any, Callable, Dict, List
from enum import Enum

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer
import requests


class JobStatus(Enum):
    """Analysis job status states."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AnalysisParams:
    """Parameters for VE analysis."""
    smooth_passes: int = 2
    clamp: float = 15.0
    rear_bias: float = 0.0
    rear_rule_deg: float = 2.0
    hot_extra: float = -1.0
    decel_management: bool = False
    decel_severity: str = "medium"  # low, medium, high
    decel_rpm_min: int = 1500
    decel_rpm_max: int = 5500
    balance_cylinders: bool = False
    balance_mode: str = "equalize"  # equalize, match_front, match_rear
    balance_max_correction: float = 3.0
    
    def to_form_data(self) -> Dict[str, str]:
        """Convert to form data for multipart upload."""
        data = {
            "smoothPasses": str(self.smooth_passes),
            "clamp": str(self.clamp),
            "rearBias": str(self.rear_bias),
            "rearRuleDeg": str(self.rear_rule_deg),
            "hotExtra": str(self.hot_extra),
            "decelManagement": str(self.decel_management).lower(),
            "decelSeverity": self.decel_severity,
            "decelRpmMin": str(self.decel_rpm_min),
            "decelRpmMax": str(self.decel_rpm_max),
            "balanceCylinders": str(self.balance_cylinders).lower(),
            "balanceMode": self.balance_mode,
            "balanceMaxCorrection": str(self.balance_max_correction),
        }
        return data


@dataclass
class JobStatusResponse:
    """Response from job status endpoint."""
    run_id: str
    status: JobStatus
    progress: int
    message: str
    filename: str = ""
    error: Optional[str] = None
    manifest: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobStatusResponse":
        """Create from API response dictionary."""
        status_str = data.get("status", "queued")
        try:
            status = JobStatus(status_str)
        except ValueError:
            status = JobStatus.QUEUED
            
        return cls(
            run_id=data.get("runId", ""),
            status=status,
            progress=data.get("progress", 0),
            message=data.get("message", ""),
            filename=data.get("filename", ""),
            error=data.get("error"),
            manifest=data.get("manifest"),
        )


@dataclass
class VEData:
    """VE table data from analysis."""
    rpm: List[float] = field(default_factory=list)
    load: List[float] = field(default_factory=list)
    before: List[List[float]] = field(default_factory=list)
    after: List[List[float]] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VEData":
        """Create from API response dictionary."""
        return cls(
            rpm=data.get("rpm", []),
            load=data.get("load", []),
            before=data.get("before", []),
            after=data.get("after", []),
        )


@dataclass
class AnalysisRun:
    """Past analysis run information."""
    run_id: str
    timestamp: str
    input_file: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisRun":
        """Create from API response dictionary."""
        return cls(
            run_id=data.get("runId", ""),
            timestamp=data.get("timestamp", ""),
            input_file=data.get("inputFile", ""),
        )


class APIWorker(QObject):
    """
    Worker object for executing API calls in a separate thread.
    Emits signals when operations complete or fail.
    """
    
    # Signals
    finished = pyqtSignal(object)  # Emits result data
    error = pyqtSignal(str)        # Emits error message
    progress = pyqtSignal(int, str)  # Emits progress percentage and message
    
    def __init__(
        self,
        method: str,
        endpoint: str,
        base_url: str = "http://localhost:5001",
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: int = 300,
    ):
        super().__init__()
        self.method = method.upper()
        self.endpoint = endpoint
        self.base_url = base_url
        self.data = data
        self.files = files
        self.timeout = timeout
        self._cancelled = False
        
    def cancel(self) -> None:
        """Cancel the operation."""
        self._cancelled = True
        
    def run(self) -> None:
        """Execute the API call."""
        if self._cancelled:
            return
            
        url = f"{self.base_url}{self.endpoint}"
        
        try:
            if self.method == "GET":
                response = requests.get(url, timeout=self.timeout)
            elif self.method == "POST":
                if self.files:
                    # Multipart form data with files
                    response = requests.post(
                        url,
                        data=self.data,
                        files=self.files,
                        timeout=self.timeout,
                    )
                else:
                    # JSON data
                    response = requests.post(
                        url,
                        json=self.data,
                        timeout=self.timeout,
                    )
            else:
                self.error.emit(f"Unsupported HTTP method: {self.method}")
                return
                
            if self._cancelled:
                return
                
            response.raise_for_status()
            
            # Try to parse JSON response
            try:
                result = response.json()
            except json.JSONDecodeError:
                result = response.content
                
            self.finished.emit(result)
            
        except requests.exceptions.Timeout:
            if not self._cancelled:
                self.error.emit("Request timed out. The server may be busy.")
        except requests.exceptions.ConnectionError:
            if not self._cancelled:
                self.error.emit("Cannot connect to API server. Is the backend running?")
        except requests.exceptions.HTTPError as e:
            if not self._cancelled:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", str(e))
                except:
                    error_msg = str(e)
                self.error.emit(f"API Error: {error_msg}")
        except Exception as e:
            if not self._cancelled:
                self.error.emit(f"Unexpected error: {str(e)}")


class APIClient(QObject):
    """
    High-level API client for DynoAI backend communication.
    Manages worker threads and provides convenient methods for common operations.
    """
    
    # Signals for health status
    health_checked = pyqtSignal(bool, str)  # (is_healthy, version_or_error)
    
    # Signals for analysis
    analysis_started = pyqtSignal(str)      # run_id
    analysis_progress = pyqtSignal(int, str)  # progress, message
    analysis_completed = pyqtSignal(str, dict)  # run_id, manifest
    analysis_error = pyqtSignal(str)        # error message
    
    # Signals for data retrieval
    ve_data_received = pyqtSignal(object)   # VEData
    runs_received = pyqtSignal(list)        # List[AnalysisRun]
    diagnostics_received = pyqtSignal(dict) # diagnostics data
    
    def __init__(self, base_url: str = "http://localhost:5001", parent: Optional[QObject] = None):
        super().__init__(parent)
        self.base_url = base_url
        self._threads: List[QThread] = []
        self._workers: List[APIWorker] = []
        self._poll_timer: Optional[QTimer] = None
        self._current_run_id: Optional[str] = None
        
    def _start_worker(self, worker: APIWorker) -> QThread:
        """Start a worker in a new thread."""
        thread = QThread()
        worker.moveToThread(thread)
        
        # Connect thread lifecycle
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        
        # Clean up when done
        thread.finished.connect(lambda: self._cleanup_thread(thread, worker))
        
        # Track for cleanup
        self._threads.append(thread)
        self._workers.append(worker)
        
        thread.start()
        return thread
        
    def _cleanup_thread(self, thread: QThread, worker: APIWorker) -> None:
        """Clean up finished thread and worker."""
        if thread in self._threads:
            self._threads.remove(thread)
        if worker in self._workers:
            self._workers.remove(worker)
        thread.deleteLater()
        worker.deleteLater()
        
    def cleanup(self) -> None:
        """Clean up all threads and workers."""
        self.stop_polling()
        
        for worker in self._workers[:]:
            worker.cancel()
            
        for thread in self._threads[:]:
            thread.quit()
            thread.wait(1000)
            
    # =========================================================================
    # Health Check
    # =========================================================================
    
    def check_health(self) -> None:
        """Check API health status."""
        worker = APIWorker("GET", "/api/health", self.base_url)
        worker.finished.connect(self._on_health_success)
        worker.error.connect(self._on_health_error)
        self._start_worker(worker)
        
    def _on_health_success(self, data: Dict[str, Any]) -> None:
        """Handle successful health check."""
        version = data.get("version", "unknown")
        self.health_checked.emit(True, version)
        
    def _on_health_error(self, error: str) -> None:
        """Handle health check error."""
        self.health_checked.emit(False, error)
        
    # =========================================================================
    # Analysis
    # =========================================================================
    
    def start_analysis(self, file_path: str, params: AnalysisParams) -> None:
        """
        Upload a file and start analysis.
        
        Args:
            file_path: Path to the CSV file to analyze
            params: Analysis parameters
        """
        try:
            # Prepare file for upload
            with open(file_path, 'rb') as f:
                file_content = f.read()
                
            import os
            filename = os.path.basename(file_path)
            
            worker = APIWorker(
                "POST",
                "/api/analyze",
                self.base_url,
                data=params.to_form_data(),
                files={"file": (filename, file_content, "text/csv")},
            )
            worker.finished.connect(self._on_analysis_started)
            worker.error.connect(self._on_analysis_start_error)
            self._start_worker(worker)
            
        except Exception as e:
            self.analysis_error.emit(f"Failed to read file: {str(e)}")
            
    def _on_analysis_started(self, data: Dict[str, Any]) -> None:
        """Handle analysis start response."""
        run_id = data.get("runId", "")
        if run_id:
            self._current_run_id = run_id
            self.analysis_started.emit(run_id)
            # Start polling for status
            self._start_polling(run_id)
        else:
            self.analysis_error.emit("No run ID received from server")
            
    def _on_analysis_start_error(self, error: str) -> None:
        """Handle analysis start error."""
        self.analysis_error.emit(error)
        
    def _start_polling(self, run_id: str, interval: int = 1000) -> None:
        """Start polling for job status."""
        self.stop_polling()
        
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(lambda: self._poll_status(run_id))
        self._poll_timer.start(interval)
        
        # Initial poll
        self._poll_status(run_id)
        
    def stop_polling(self) -> None:
        """Stop status polling."""
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer.deleteLater()
            self._poll_timer = None
            
    def _poll_status(self, run_id: str) -> None:
        """Poll for job status."""
        worker = APIWorker("GET", f"/api/status/{run_id}", self.base_url, timeout=30)
        worker.finished.connect(self._on_status_received)
        worker.error.connect(self._on_status_error)
        self._start_worker(worker)
        
    def _on_status_received(self, data: Dict[str, Any]) -> None:
        """Handle status response."""
        status = JobStatusResponse.from_dict(data)
        
        # Emit progress
        self.analysis_progress.emit(status.progress, status.message)
        
        if status.status == JobStatus.COMPLETED:
            self.stop_polling()
            self.analysis_completed.emit(status.run_id, status.manifest or {})
        elif status.status == JobStatus.ERROR:
            self.stop_polling()
            self.analysis_error.emit(status.error or "Analysis failed")
            
    def _on_status_error(self, error: str) -> None:
        """Handle status poll error."""
        # Don't stop polling on transient errors, just log
        print(f"Status poll error: {error}")
        
    # =========================================================================
    # Data Retrieval
    # =========================================================================
    
    def get_ve_data(self, run_id: str) -> None:
        """Fetch VE table data for a run."""
        worker = APIWorker("GET", f"/api/ve-data/{run_id}", self.base_url)
        worker.finished.connect(self._on_ve_data_received)
        worker.error.connect(lambda e: self.analysis_error.emit(e))
        self._start_worker(worker)
        
    def _on_ve_data_received(self, data: Dict[str, Any]) -> None:
        """Handle VE data response."""
        ve_data = VEData.from_dict(data)
        self.ve_data_received.emit(ve_data)
        
    def get_runs(self) -> None:
        """Fetch list of past analysis runs."""
        worker = APIWorker("GET", "/api/runs", self.base_url)
        worker.finished.connect(self._on_runs_received)
        worker.error.connect(lambda e: print(f"Failed to get runs: {e}"))
        self._start_worker(worker)
        
    def _on_runs_received(self, data: Dict[str, Any]) -> None:
        """Handle runs list response."""
        runs_data = data.get("runs", [])
        runs = [AnalysisRun.from_dict(r) for r in runs_data]
        self.runs_received.emit(runs)
        
    def get_diagnostics(self, run_id: str) -> None:
        """Fetch diagnostics data for a run."""
        worker = APIWorker("GET", f"/api/diagnostics/{run_id}", self.base_url)
        worker.finished.connect(self._on_diagnostics_received)
        worker.error.connect(lambda e: self.analysis_error.emit(e))
        self._start_worker(worker)
        
    def _on_diagnostics_received(self, data: Dict[str, Any]) -> None:
        """Handle diagnostics response."""
        self.diagnostics_received.emit(data)
        
    def download_file(self, run_id: str, filename: str) -> None:
        """
        Download a file from a run.
        Returns the file content via signal.
        """
        worker = APIWorker("GET", f"/api/download/{run_id}/{filename}", self.base_url)
        # For file downloads, the finished signal will emit bytes
        self._start_worker(worker)
