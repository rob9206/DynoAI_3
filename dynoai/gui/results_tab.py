"""
Results Tab - View Analysis Results and VE Grids
"""

from pathlib import Path
import json
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QSplitter,
    QTextEdit,
    QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from api.services.autotune_workflow import AutoTuneWorkflow


class ResultsTab(QWidget):
    """Tab for browsing and viewing analysis results"""
    
    def __init__(self, workflow: AutoTuneWorkflow):
        super().__init__()
        self.workflow = workflow
        self.runs_dir = Path("runs")
        
        self._init_ui()
        self._load_runs_list()
    
    def _init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Analysis Results")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Create splitter for list and details
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - runs list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        list_label = QLabel("Available Runs")
        list_label_font = QFont()
        list_label_font.setBold(True)
        list_label.setFont(list_label_font)
        left_layout.addWidget(list_label)
        
        self.runs_list = QListWidget()
        self.runs_list.currentItemChanged.connect(self._on_run_selected)
        left_layout.addWidget(self.runs_list)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._load_runs_list)
        left_layout.addWidget(refresh_btn)
        
        splitter.addWidget(left_widget)
        
        # Right side - run details
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Summary
        summary_group = QGroupBox("Run Summary")
        summary_layout = QVBoxLayout(summary_group)
        
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(150)
        summary_layout.addWidget(self.summary_text)
        
        right_layout.addWidget(summary_group)
        
        # VE Grid
        grid_group = QGroupBox("VE Correction Grid")
        grid_layout = QVBoxLayout(grid_group)
        
        self.ve_table = QTableWidget()
        self.ve_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        grid_layout.addWidget(self.ve_table)
        
        right_layout.addWidget(grid_group, 1)
        
        # Export buttons
        export_layout = QHBoxLayout()
        
        export_pvv_btn = QPushButton("📄 Export PVV")
        export_pvv_btn.clicked.connect(self._export_pvv)
        export_layout.addWidget(export_pvv_btn)
        
        export_text_btn = QPushButton("📝 Export Text")
        export_text_btn.clicked.connect(self._export_text)
        export_layout.addWidget(export_text_btn)
        
        export_csv_btn = QPushButton("📊 Export CSV")
        export_csv_btn.clicked.connect(self._export_csv)
        export_layout.addWidget(export_csv_btn)
        
        right_layout.addLayout(export_layout)
        
        splitter.addWidget(right_widget)
        
        # Set initial sizes (30% list, 70% details)
        splitter.setSizes([300, 700])
        
        layout.addWidget(splitter, 1)
    
    def _load_runs_list(self):
        """Load list of available runs"""
        self.runs_list.clear()
        
        if not self.runs_dir.exists():
            return
        
        # Find all run directories with manifest.json
        runs = []
        for run_dir in self.runs_dir.iterdir():
            if run_dir.is_dir():
                manifest_file = run_dir / "manifest.json"
                if manifest_file.exists():
                    try:
                        with open(manifest_file) as f:
                            manifest = json.load(f)
                        runs.append((run_dir.name, manifest))
                    except Exception:
                        pass
        
        # Sort by timestamp (newest first)
        runs.sort(key=lambda x: x[1].get("timestamp", ""), reverse=True)
        
        # Add to list
        for run_id, manifest in runs:
            timestamp = manifest.get("timestamp", "Unknown")
            peak_hp = manifest.get("analysis", {}).get("peak_hp", 0)
            item_text = f"{run_id} | {timestamp} | {peak_hp:.1f} HP"
            self.runs_list.addItem(item_text)
            # Store run_id as item data
            item = self.runs_list.item(self.runs_list.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, run_id)
    
    def _on_run_selected(self, current, previous):
        """Handle run selection"""
        if not current:
            return
        
        run_id = current.data(Qt.ItemDataRole.UserRole)
        self._load_run_details(run_id)
    
    def _load_run_details(self, run_id: str):
        """Load and display run details"""
        run_dir = self.runs_dir / run_id
        manifest_file = run_dir / "manifest.json"
        
        if not manifest_file.exists():
            return
        
        try:
            with open(manifest_file) as f:
                manifest = json.load(f)
            
            # Display summary
            summary_lines = []
            summary_lines.append(f"Run ID: {run_id}")
            summary_lines.append(f"Timestamp: {manifest.get('timestamp', 'N/A')}")
            summary_lines.append("")
            
            analysis = manifest.get("analysis", {})
            summary_lines.append(f"Peak HP: {analysis.get('peak_hp', 0):.1f}")
            summary_lines.append(f"Peak Torque: {analysis.get('peak_tq', 0):.1f} ft-lb")
            summary_lines.append(f"Total Samples: {analysis.get('total_samples', 0)}")
            
            self.summary_text.setPlainText("\n".join(summary_lines))
            
            # Display VE grid
            self._load_ve_grid(run_dir)
            
        except Exception as e:
            self.summary_text.setPlainText(f"Error loading run: {str(e)}")
    
    def _load_ve_grid(self, run_dir: Path):
        """Load and display VE correction grid"""
        ve_file = run_dir / "VE_Corrections_2D.csv"
        
        if not ve_file.exists():
            self.ve_table.clear()
            self.ve_table.setRowCount(0)
            self.ve_table.setColumnCount(0)
            return
        
        try:
            with open(ve_file) as f:
                lines = f.readlines()
            
            if not lines:
                return
            
            # Parse header (MAP values)
            header = lines[0].strip().split(',')
            map_values = header[1:]  # Skip "RPM" column
            
            # Setup table
            self.ve_table.setRowCount(len(lines) - 1)
            self.ve_table.setColumnCount(len(map_values) + 1)
            
            # Set headers
            self.ve_table.setHorizontalHeaderLabels(["RPM"] + map_values)
            
            # Populate data
            for row_idx, line in enumerate(lines[1:]):
                parts = line.strip().split(',')
                if not parts:
                    continue
                
                # RPM column
                rpm_item = QTableWidgetItem(parts[0])
                rpm_item.setFont(QFont("", -1, QFont.Weight.Bold))
                self.ve_table.setItem(row_idx, 0, rpm_item)
                
                # VE correction values
                for col_idx, value in enumerate(parts[1:], 1):
                    try:
                        ve_value = float(value)
                        item = QTableWidgetItem(f"{ve_value:.1f}%")
                        
                        # Color code based on correction magnitude
                        if abs(ve_value) < 2:
                            item.setBackground(QColor(200, 255, 200))  # Green - good
                        elif abs(ve_value) < 5:
                            item.setBackground(QColor(255, 255, 200))  # Yellow - moderate
                        else:
                            item.setBackground(QColor(255, 200, 200))  # Red - significant
                        
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        self.ve_table.setItem(row_idx, col_idx, item)
                    except ValueError:
                        pass
            
            # Resize columns
            self.ve_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            
        except Exception as e:
            self.summary_text.append(f"\n\nError loading VE grid: {str(e)}")
    
    def _export_pvv(self):
        """Export to PVV format"""
        # TODO: Implement PVV export
        pass
    
    def _export_text(self):
        """Export to text format"""
        # TODO: Implement text export
        pass
    
    def _export_csv(self):
        """Export to CSV format"""
        # TODO: Implement CSV export
        pass
