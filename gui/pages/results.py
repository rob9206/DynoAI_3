"""
Results Page for DynoAI PyQt6 GUI
Analysis results display with VE heatmap and download options
"""

from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QTabWidget, QGridLayout,
    QSizePolicy, QSpacerItem, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
import os

from gui.api.client import APIClient, VEData
from gui.components.card import Card, CardHeader, CardContent, CardTitle, CardDescription
from gui.components.button import Button, ButtonVariant, ButtonSize
from gui.components.alert import Alert, AlertTitle, AlertDescription, AlertVariant, create_alert
from gui.styles.theme import COLORS


class MetricCard(QFrame):
    """Small metric display card."""
    
    def __init__(
        self,
        label: str,
        value: str,
        icon: str = "",
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        self.setProperty("class", "panel")
        self.setStyleSheet(f"""
            QFrame {{
                padding: 16px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        
        # Label row
        label_row = QHBoxLayout()
        label_row.setSpacing(8)
        
        if icon:
            icon_label = QLabel(icon)
            label_row.addWidget(icon_label)
            
        label_widget = QLabel(label)
        label_widget.setProperty("class", "section")
        label_row.addWidget(label_widget)
        label_row.addStretch()
        
        layout.addLayout(label_row)
        
        # Value
        self.value_label = QLabel(value)
        self.value_label.setProperty("class", "value")
        self.value_label.setStyleSheet("""
            font-size: 18pt;
        """)
        layout.addWidget(self.value_label)
        
    def setValue(self, value: str) -> None:
        """Update the displayed value."""
        self.value_label.setText(value)


class ResultsPage(QWidget):
    """
    Results page displaying analysis output.
    Shows VE heatmap, metrics, and download options.
    """
    
    def __init__(self, api_client: APIClient, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.api_client = api_client
        self._current_run_id: Optional[str] = None
        self._manifest: Optional[Dict[str, Any]] = None
        
        # Connect API signals
        self.api_client.ve_data_received.connect(self._on_ve_data_received)
        self.api_client.diagnostics_received.connect(self._on_diagnostics_received)
        
        # Build UI
        self._build_ui()
        
    def _build_ui(self) -> None:
        """Build the results UI."""
        # Main scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(24, 24, 24, 24)
        scroll_layout.setSpacing(24)
        
        # =====================================================================
        # Header
        # =====================================================================
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title section
        title_section = QVBoxLayout()
        title_section.setSpacing(4)
        
        title = QLabel("Analysis Results")
        title.setStyleSheet("font-size: 24pt; font-weight: 700;")
        title_section.addWidget(title)
        
        self.run_info_label = QLabel("No analysis loaded")
        self.run_info_label.setStyleSheet(f"color: {COLORS['muted_foreground']};")
        title_section.addWidget(self.run_info_label)
        
        header_layout.addLayout(title_section)
        header_layout.addStretch()
        
        # Download buttons
        btn_section = QHBoxLayout()
        btn_section.setSpacing(12)
        
        self.download_csv_btn = Button("Download CSV", ButtonVariant.SECONDARY, icon="📥")
        self.download_csv_btn.clicked.connect(self._download_csv)
        self.download_csv_btn.setEnabled(False)
        btn_section.addWidget(self.download_csv_btn)
        
        self.download_report_btn = Button("Download Report", ButtonVariant.DEFAULT, icon="📄")
        self.download_report_btn.clicked.connect(self._download_report)
        self.download_report_btn.setEnabled(False)
        btn_section.addWidget(self.download_report_btn)
        
        header_layout.addLayout(btn_section)
        
        scroll_layout.addWidget(header)
        
        # =====================================================================
        # Metrics Row
        # =====================================================================
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(16)
        
        self.rows_metric = MetricCard("Rows Processed", "-", "📊")
        metrics_layout.addWidget(self.rows_metric)
        
        self.corrections_metric = MetricCard("Corrections Applied", "-", "✏️")
        metrics_layout.addWidget(self.corrections_metric)
        
        self.avg_correction_metric = MetricCard("Avg Correction", "-", "📈")
        metrics_layout.addWidget(self.avg_correction_metric)
        
        self.max_correction_metric = MetricCard("Max Correction", "-", "⚡")
        metrics_layout.addWidget(self.max_correction_metric)
        
        scroll_layout.addLayout(metrics_layout)
        
        # =====================================================================
        # VE Heatmap Card
        # =====================================================================
        heatmap_card = Card()
        
        heatmap_header = CardHeader()
        
        heatmap_title_row = QHBoxLayout()
        heatmap_title_row.setSpacing(8)
        heatmap_icon = QLabel("🔥")
        heatmap_icon.setStyleSheet("font-size: 14pt;")
        heatmap_title_row.addWidget(heatmap_icon)
        heatmap_title = CardTitle("VE Table Corrections")
        heatmap_title_row.addWidget(heatmap_title)
        heatmap_title_row.addStretch()
        
        # View toggle
        self.view_before_btn = Button("Before", ButtonVariant.GHOST, ButtonSize.SMALL)
        self.view_before_btn.clicked.connect(lambda: self._set_heatmap_view("before"))
        heatmap_title_row.addWidget(self.view_before_btn)
        
        self.view_after_btn = Button("After", ButtonVariant.SECONDARY, ButtonSize.SMALL)
        self.view_after_btn.clicked.connect(lambda: self._set_heatmap_view("after"))
        heatmap_title_row.addWidget(self.view_after_btn)
        
        self.view_diff_btn = Button("Diff", ButtonVariant.GHOST, ButtonSize.SMALL)
        self.view_diff_btn.clicked.connect(lambda: self._set_heatmap_view("diff"))
        heatmap_title_row.addWidget(self.view_diff_btn)
        
        heatmap_title_widget = QWidget()
        heatmap_title_widget.setLayout(heatmap_title_row)
        heatmap_header.addWidget(heatmap_title_widget)
        
        heatmap_card.addWidget(heatmap_header)
        
        heatmap_content = CardContent()
        
        # Placeholder for heatmap (will be replaced with VEHeatmapWidget)
        self.heatmap_container = QFrame()
        self.heatmap_container.setMinimumHeight(400)
        self.heatmap_container.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['muted']};
                border-radius: 8px;
            }}
        """)
        
        heatmap_placeholder_layout = QVBoxLayout(self.heatmap_container)
        heatmap_placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.heatmap_placeholder_label = QLabel("No data loaded")
        self.heatmap_placeholder_label.setStyleSheet(f"color: {COLORS['muted_foreground']};")
        heatmap_placeholder_layout.addWidget(
            self.heatmap_placeholder_label,
            alignment=Qt.AlignmentFlag.AlignCenter
        )
        
        heatmap_content.addWidget(self.heatmap_container)
        heatmap_card.addWidget(heatmap_content)
        
        scroll_layout.addWidget(heatmap_card)
        
        # =====================================================================
        # Diagnostics Card
        # =====================================================================
        diagnostics_card = Card()
        
        diag_header = CardHeader()
        
        diag_title_row = QHBoxLayout()
        diag_title_row.setSpacing(8)
        diag_icon = QLabel("🔍")
        diag_icon.setStyleSheet("font-size: 14pt;")
        diag_title_row.addWidget(diag_icon)
        diag_title = CardTitle("Diagnostics & Anomalies")
        diag_title_row.addWidget(diag_title)
        diag_title_row.addStretch()
        
        diag_title_widget = QWidget()
        diag_title_widget.setLayout(diag_title_row)
        diag_header.addWidget(diag_title_widget)
        
        diagnostics_card.addWidget(diag_header)
        
        diag_content = CardContent()
        
        self.diagnostics_container = QFrame()
        self.diagnostics_container.setMinimumHeight(150)
        
        diag_layout = QVBoxLayout(self.diagnostics_container)
        
        self.diagnostics_label = QLabel("No diagnostics available")
        self.diagnostics_label.setStyleSheet(f"color: {COLORS['muted_foreground']};")
        self.diagnostics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        diag_layout.addWidget(self.diagnostics_label)
        
        diag_content.addWidget(self.diagnostics_container)
        diagnostics_card.addWidget(diag_content)
        
        scroll_layout.addWidget(diagnostics_card)
        
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Current heatmap view
        self._current_view = "after"
        self._ve_data: Optional[VEData] = None
        
    def load_run(self, run_id: str) -> None:
        """Load results for a specific run."""
        self._current_run_id = run_id
        self.run_info_label.setText(f"Run ID: {run_id}")
        
        # Enable download buttons
        self.download_csv_btn.setEnabled(True)
        self.download_report_btn.setEnabled(True)
        
        # Fetch data
        self.api_client.get_ve_data(run_id)
        self.api_client.get_diagnostics(run_id)
        
        # Update heatmap placeholder
        self.heatmap_placeholder_label.setText("Loading VE data...")
        
    def _on_ve_data_received(self, ve_data: VEData) -> None:
        """Handle VE data received."""
        self._ve_data = ve_data
        
        # Update placeholder with basic info for now
        # In Phase 2, this will be replaced with actual VEHeatmapWidget
        rpm_count = len(ve_data.rpm) if ve_data.rpm else 0
        load_count = len(ve_data.load) if ve_data.load else 0
        
        self.heatmap_placeholder_label.setText(
            f"VE Data loaded: {rpm_count} RPM points × {load_count} Load points\n\n"
            "Full heatmap visualization available in VE Heatmap widget.\n"
            "(Implementation in gui/widgets/ve_heatmap.py)"
        )
        
        # Try to import and use actual heatmap widget
        try:
            from gui.widgets.ve_heatmap import VEHeatmapWidget
            
            # Clear container
            for i in reversed(range(self.heatmap_container.layout().count())):
                self.heatmap_container.layout().itemAt(i).widget().setParent(None)
                
            # Add heatmap widget
            self.heatmap_widget = VEHeatmapWidget()
            self.heatmap_widget.set_data(ve_data)
            self.heatmap_container.layout().addWidget(self.heatmap_widget)
        except ImportError:
            pass
            
    def _on_diagnostics_received(self, data: Dict[str, Any]) -> None:
        """Handle diagnostics data received."""
        # Parse and display diagnostics
        anomalies = data.get("anomalies", {}).get("anomalies", [])
        
        if anomalies:
            # Clear container
            for i in reversed(range(self.diagnostics_container.layout().count())):
                widget = self.diagnostics_container.layout().itemAt(i).widget()
                if widget:
                    widget.setParent(None)
                    
            # Add anomaly alerts
            for anomaly in anomalies[:5]:  # Show first 5
                anomaly_type = anomaly.get("type", "Unknown")
                explanation = anomaly.get("explanation", "No details")
                score = anomaly.get("score", 0)
                
                variant = AlertVariant.WARNING if score > 0.5 else AlertVariant.INFO
                alert = create_alert(variant, anomaly_type, explanation)
                self.diagnostics_container.layout().addWidget(alert)
        else:
            self.diagnostics_label.setText("✓ No anomalies detected")
            self.diagnostics_label.setStyleSheet(f"color: {COLORS['success']};")
            
    def _set_heatmap_view(self, view: str) -> None:
        """Set the heatmap view mode."""
        self._current_view = view
        
        # Update button states
        self.view_before_btn.setVariant(
            ButtonVariant.SECONDARY if view == "before" else ButtonVariant.GHOST
        )
        self.view_after_btn.setVariant(
            ButtonVariant.SECONDARY if view == "after" else ButtonVariant.GHOST
        )
        self.view_diff_btn.setVariant(
            ButtonVariant.SECONDARY if view == "diff" else ButtonVariant.GHOST
        )
        
        # Update heatmap if widget exists
        if hasattr(self, 'heatmap_widget'):
            self.heatmap_widget.set_view_mode(view)
            
    def _download_csv(self) -> None:
        """Download the corrected CSV file."""
        if not self._current_run_id:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Corrected VE Table",
            f"ve_corrected_{self._current_run_id}.csv",
            "CSV Files (*.csv)"
        )
        
        if file_path:
            # Download via API (simplified - actual implementation would use API)
            print(f"Would download CSV to: {file_path}")
            
    def _download_report(self) -> None:
        """Download the analysis report."""
        if not self._current_run_id:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Analysis Report",
            f"report_{self._current_run_id}.pdf",
            "PDF Files (*.pdf)"
        )
        
        if file_path:
            # Download via API (simplified - actual implementation would use API)
            print(f"Would download report to: {file_path}")
            
    def _update_metrics(self, manifest: Dict[str, Any]) -> None:
        """Update metrics display from manifest."""
        self.rows_metric.setValue(str(manifest.get("rowsProcessed", "-")))
        self.corrections_metric.setValue(str(manifest.get("correctionsApplied", "-")))
        
        metrics = manifest.get("analysisMetrics", {})
        avg = metrics.get("avgCorrection", 0)
        max_val = metrics.get("maxCorrection", 0)
        
        self.avg_correction_metric.setValue(f"{avg:.2f}%")
        self.max_correction_metric.setValue(f"{max_val:.2f}%")
