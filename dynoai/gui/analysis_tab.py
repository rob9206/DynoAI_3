"""
Analysis Tab - CSV File Upload and Analysis
"""

from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QTextEdit,
    QGroupBox,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from api.services.autotune_workflow import AutoTuneWorkflow, DataSource


class AnalysisWorker(QThread):
    """Background worker for running analysis"""
    
    progress = pyqtSignal(int, str)  # progress %, message
    finished = pyqtSignal(dict)  # results
    error = pyqtSignal(str)  # error message
    
    def __init__(self, workflow: AutoTuneWorkflow, csv_path: str, run_id: str):
        super().__init__()
        self.workflow = workflow
        self.csv_path = csv_path
        self.run_id = run_id
    
    def run(self):
        """Run the analysis in background"""
        try:
            self.progress.emit(10, "Loading CSV file...")
            
            # Determine output directory
            output_dir = Path("runs") / self.run_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            self.progress.emit(30, "Running analysis...")
            
            # Run the workflow
            session = self.workflow.run_full_workflow(
                log_path=self.csv_path,
                output_dir=str(output_dir),
                data_source=DataSource.POWER_VISION
            )
            
            if session.status == "error":
                self.error.emit(f"Analysis failed: {', '.join(session.errors)}")
                return
            
            self.progress.emit(80, "Generating summary...")
            
            # Get session summary
            summary = self.workflow.get_session_summary(session)
            
            self.progress.emit(100, "Complete!")
            self.finished.emit(summary)
            
        except Exception as e:
            self.error.emit(f"Error during analysis: {str(e)}")


class AnalysisTab(QWidget):
    """Tab for uploading and analyzing CSV files"""
    
    def __init__(self, workflow: AutoTuneWorkflow):
        super().__init__()
        self.workflow = workflow
        self.current_file: Optional[str] = None
        self.worker: Optional[AnalysisWorker] = None
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("CSV File Analysis")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # File selection group
        file_group = QGroupBox("Select File")
        file_layout = QHBoxLayout(file_group)
        
        self.file_label = QLabel("No file selected")
        file_layout.addWidget(self.file_label, 1)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        
        layout.addWidget(file_group)
        
        # Analysis controls
        controls_layout = QHBoxLayout()
        
        self.analyze_btn = QPushButton("🚀 Run Analysis")
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setMinimumHeight(40)
        self.analyze_btn.clicked.connect(self._run_analysis)
        controls_layout.addWidget(self.analyze_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_analysis)
        controls_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(controls_layout)
        
        # Progress
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("Ready")
        progress_layout.addWidget(self.progress_label)
        
        layout.addWidget(progress_group)
        
        # Results
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(300)
        results_layout.addWidget(self.results_text)
        
        layout.addWidget(results_group, 1)
    
    def _browse_file(self):
        """Browse for CSV file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Dyno Log CSV",
            str(Path.home()),
            "CSV Files (*.csv);;All Files (*.*)"
        )
        
        if file_path:
            self.load_file(file_path)
    
    def load_file(self, file_path: str):
        """Load a CSV file"""
        self.current_file = file_path
        self.file_label.setText(Path(file_path).name)
        self.analyze_btn.setEnabled(True)
        self.results_text.clear()
        self.progress_bar.setValue(0)
        self.progress_label.setText("File loaded - ready to analyze")
    
    def _run_analysis(self):
        """Start the analysis"""
        if not self.current_file:
            return
        
        # Generate run ID
        from datetime import datetime
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Disable controls
        self.analyze_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        
        # Create and start worker
        self.worker = AnalysisWorker(self.workflow, self.current_file, run_id)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()
    
    def _cancel_analysis(self):
        """Cancel the analysis"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
            self._reset_ui()
            self.progress_label.setText("Analysis cancelled")
    
    def _on_progress(self, value: int, message: str):
        """Handle progress updates"""
        self.progress_bar.setValue(value)
        self.progress_label.setText(message)
    
    def _on_finished(self, results: dict):
        """Handle analysis completion"""
        self._reset_ui()
        
        # Display results
        output = []
        output.append("=" * 60)
        output.append("ANALYSIS COMPLETE")
        output.append("=" * 60)
        output.append("")
        
        if "session_id" in results:
            output.append(f"Session ID: {results['session_id']}")
        
        if "run_summary" in results:
            summary = results["run_summary"]
            output.append(f"Samples: {summary.get('total_samples', 'N/A')}")
            output.append(f"Peak HP: {summary.get('peak_hp', 'N/A'):.1f}")
            output.append(f"Peak Torque: {summary.get('peak_tq', 'N/A'):.1f}")
        
        output.append("")
        output.append("VE corrections calculated successfully!")
        output.append("")
        output.append("Check the 'Results' tab to view detailed analysis.")
        
        self.results_text.setPlainText("\n".join(output))
    
    def _on_error(self, error_msg: str):
        """Handle analysis error"""
        self._reset_ui()
        self.results_text.setPlainText(f"ERROR:\n{error_msg}")
        self.progress_label.setText("Analysis failed")
    
    def _reset_ui(self):
        """Reset UI after analysis"""
        self.analyze_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
