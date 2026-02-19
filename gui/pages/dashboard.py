"""
Dashboard Page for DynoAI PyQt6 GUI
Main analysis workflow page with file upload and configuration
"""

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from gui.api.client import AnalysisParams, APIClient
from gui.components.alert import (
    Alert,
    AlertDescription,
    AlertTitle,
    AlertVariant,
    create_alert,
)
from gui.components.button import ActionButton, Button, ButtonSize, ButtonVariant
from gui.components.card import (
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
)
from gui.components.file_upload import FileUploadWidget
from gui.components.progress import ProgressWidget, StepProgressWidget
from gui.styles.theme import COLORS
from gui.widgets.advanced_features import AdvancedFeaturesWidget
from gui.widgets.tuning_config import TuningConfigWidget


class DashboardPage(QWidget):
    """
    Dashboard page with file upload, analysis configuration, and progress tracking.
    """

    # Signals
    navigate_to_results = pyqtSignal(str)  # run_id

    def __init__(self, api_client: APIClient, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.api_client = api_client
        self._current_file: Optional[str] = None
        self._is_analyzing = False
        self._current_run_id: Optional[str] = None

        # Analysis parameters
        self._params = AnalysisParams()

        # Connect API signals
        self.api_client.analysis_started.connect(self._on_analysis_started)
        self.api_client.analysis_progress.connect(self._on_analysis_progress)
        self.api_client.analysis_completed.connect(self._on_analysis_completed)
        self.api_client.analysis_error.connect(self._on_analysis_error)

        # Build UI
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the dashboard UI."""
        # Main scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Scroll content
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

        title = QLabel("Control Center")
        title.setStyleSheet("""
            font-size: 24pt;
            font-weight: 700;
        """)
        title_section.addWidget(title)

        subtitle = QLabel("System Ready. Waiting for log data.")
        subtitle.setProperty("class", "muted")
        title_section.addWidget(subtitle)

        header_layout.addLayout(title_section)
        header_layout.addStretch()

        # Status indicators
        status_section = QHBoxLayout()
        status_section.setSpacing(12)

        # Engine status
        engine_status = QFrame()
        engine_status.setProperty("class", "panel")
        engine_status.setStyleSheet(f"""
            QFrame {{
                padding: 8px 12px;
            }}
        """)
        engine_layout = QHBoxLayout(engine_status)
        engine_layout.setContentsMargins(12, 6, 12, 6)
        engine_layout.setSpacing(8)

        engine_icon = QLabel("📊")
        engine_layout.addWidget(engine_icon)

        engine_text = QLabel("Engine: Idle")
        engine_text.setStyleSheet("font-weight: 500;")
        engine_layout.addWidget(engine_text)

        status_section.addWidget(engine_status)

        # Date
        from datetime import datetime

        date_status = QFrame()
        date_status.setProperty("class", "panel")
        date_status.setStyleSheet(f"""
            QFrame {{
                padding: 8px 12px;
            }}
        """)
        date_layout = QHBoxLayout(date_status)
        date_layout.setContentsMargins(12, 6, 12, 6)
        date_layout.setSpacing(8)

        date_icon = QLabel("🕐")
        date_layout.addWidget(date_icon)

        date_text = QLabel(datetime.now().strftime("%B %d, %Y"))
        date_text.setStyleSheet("font-weight: 500;")
        date_layout.addWidget(date_text)

        status_section.addWidget(date_status)

        header_layout.addLayout(status_section)

        scroll_layout.addWidget(header)

        # =====================================================================
        # Main Content Grid
        # =====================================================================
        content_grid = QHBoxLayout()
        content_grid.setSpacing(24)

        # Left column (2/3 width)
        left_column = QVBoxLayout()
        left_column.setSpacing(24)

        # File Upload Card
        upload_card = Card()

        upload_header = CardHeader()

        upload_title_row = QHBoxLayout()
        upload_title_row.setSpacing(8)
        upload_icon = QLabel("📄")
        upload_icon.setStyleSheet("font-size: 14pt;")
        upload_title_row.addWidget(upload_icon)
        upload_title = CardTitle("Log File Import")
        upload_title_row.addWidget(upload_title)
        upload_title_row.addStretch()

        upload_title_widget = QWidget()
        upload_title_widget.setLayout(upload_title_row)
        upload_header.addWidget(upload_title_widget)

        upload_desc = CardDescription(
            "Select a WinPEP, PowerVision, or Generic CSV log file."
        )
        upload_header.addWidget(upload_desc)

        upload_card.addWidget(upload_header)

        upload_content = CardContent()
        upload_content.setSpacing(16)

        # File upload widget
        self.file_upload = FileUploadWidget()
        self.file_upload.file_selected.connect(self._on_file_selected)
        self.file_upload.file_cleared.connect(self._on_file_cleared)
        upload_content.addWidget(self.file_upload)

        # Start Analysis button container
        self.start_button_container = QWidget()
        start_btn_layout = QVBoxLayout(self.start_button_container)
        start_btn_layout.setContentsMargins(0, 0, 0, 0)
        start_btn_layout.setSpacing(8)

        self.start_button = ActionButton("Start Analysis", "▶️")
        self.start_button.clicked.connect(self._start_analysis)
        self.start_button.setEnabled(False)
        start_btn_layout.addWidget(self.start_button)

        self.start_hint = QLabel("Process using current configuration")
        self.start_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.start_hint.setProperty("class", "muted")
        self.start_hint.setStyleSheet("font-size: 9pt;")
        start_btn_layout.addWidget(self.start_hint)

        self.start_button_container.setVisible(False)
        upload_content.addWidget(self.start_button_container)

        # Progress section (initially hidden)
        self.progress_section = QWidget()
        progress_layout = QVBoxLayout(self.progress_section)
        progress_layout.setContentsMargins(0, 16, 0, 0)
        progress_layout.setSpacing(16)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['border']};")
        sep.setFixedHeight(1)
        progress_layout.addWidget(sep)

        # Progress widget
        self.progress_widget = ProgressWidget()
        progress_layout.addWidget(self.progress_widget)

        # Step indicators
        self.step_progress = StepProgressWidget()
        progress_layout.addWidget(self.step_progress)

        self.progress_section.setVisible(False)
        upload_content.addWidget(self.progress_section)

        upload_card.addWidget(upload_content)
        left_column.addWidget(upload_card)

        # Advanced Features Card (hidden during analysis)
        self.advanced_features = AdvancedFeaturesWidget()
        self.advanced_features.set_params_reference(self._params)
        left_column.addWidget(self.advanced_features)

        # Operator Note (shown when no file selected)
        self.operator_note = create_alert(
            AlertVariant.INFO,
            "Operator Note",
            "Ensure log files contain RPM, MAP (kPa), and Torque/HP channels. For best results, log at 20Hz or higher.",
        )
        left_column.addWidget(self.operator_note)

        # API Offline Alert (hidden by default)
        self.api_offline_alert = create_alert(
            AlertVariant.ERROR,
            "API Offline",
            "Cannot connect to the DynoAI backend server. The API may not be running.\n\n"
            "Quick Fix (Local): Run restart-quick.bat from the project root.",
        )
        self.api_offline_alert.setVisible(False)
        left_column.addWidget(self.api_offline_alert)

        left_column.addStretch()

        # Right column (1/3 width) - Tuning Configuration
        right_column = QVBoxLayout()
        right_column.setSpacing(24)

        self.tuning_config = TuningConfigWidget()
        self.tuning_config.params_changed.connect(self._on_params_changed)
        right_column.addWidget(self.tuning_config)

        right_column.addStretch()

        # Add columns to grid
        left_widget = QWidget()
        left_widget.setLayout(left_column)
        left_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        right_widget = QWidget()
        right_widget.setLayout(right_column)
        right_widget.setFixedWidth(350)

        content_grid.addWidget(left_widget, 2)
        content_grid.addWidget(right_widget, 1)

        scroll_layout.addLayout(content_grid)

        scroll.setWidget(scroll_content)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    # =========================================================================
    # File Selection
    # =========================================================================

    def _on_file_selected(self, file_path: str) -> None:
        """Handle file selection."""
        self._current_file = file_path
        self.start_button.setEnabled(True)
        self.start_button_container.setVisible(True)
        self.operator_note.setVisible(False)

    def _on_file_cleared(self) -> None:
        """Handle file cleared."""
        self._current_file = None
        self.start_button.setEnabled(False)
        self.start_button_container.setVisible(False)
        self.operator_note.setVisible(True)

    # =========================================================================
    # Analysis
    # =========================================================================

    def _start_analysis(self) -> None:
        """Start the analysis process."""
        if not self._current_file:
            return

        self._is_analyzing = True

        # Update UI
        self.start_button_container.setVisible(False)
        self.progress_section.setVisible(True)
        self.advanced_features.setVisible(False)
        self.tuning_config.setEnabled(False)

        # Reset progress
        self.progress_widget.reset()
        self.step_progress.reset()

        # Get merged params from tuning config
        config_params = self.tuning_config.get_params()
        self._params.smooth_passes = config_params.smooth_passes
        self._params.clamp = config_params.clamp
        self._params.rear_bias = config_params.rear_bias
        self._params.rear_rule_deg = config_params.rear_rule_deg

        # Start analysis via API
        self.api_client.start_analysis(self._current_file, self._params)

    def _on_analysis_started(self, run_id: str) -> None:
        """Handle analysis started."""
        self._current_run_id = run_id
        self.progress_widget.setProgress(5, "Uploading file...")
        self.step_progress.setProgress(5)

    def _on_analysis_progress(self, progress: int, message: str) -> None:
        """Handle analysis progress update."""
        self.progress_widget.setProgress(progress, message)
        self.step_progress.setProgress(progress)

    def _on_analysis_completed(self, run_id: str, manifest: dict) -> None:
        """Handle analysis completion."""
        self._is_analyzing = False
        self.progress_widget.setProgress(100, "Analysis complete!")
        self.step_progress.setProgress(100)

        # Navigate to results after a short delay
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(1000, lambda: self._go_to_results(run_id))

    def _on_analysis_error(self, error: str) -> None:
        """Handle analysis error."""
        self._is_analyzing = False

        # Update progress to show error
        self.progress_widget.setProgress(0, f"Error: {error}")
        self.step_progress.setError()

        # Re-enable UI
        self.start_button_container.setVisible(True)
        self.progress_section.setVisible(False)
        self.advanced_features.setVisible(True)
        self.tuning_config.setEnabled(True)

    def _go_to_results(self, run_id: str) -> None:
        """Navigate to results page."""
        # Reset UI for next analysis
        self.progress_section.setVisible(False)
        self.advanced_features.setVisible(True)
        self.tuning_config.setEnabled(True)
        self.file_upload.clear_file()

        # Emit signal to navigate
        self.navigate_to_results.emit(run_id)

    # =========================================================================
    # Configuration
    # =========================================================================

    def _on_params_changed(self, params: AnalysisParams) -> None:
        """Handle params change from tuning config."""
        self._params.smooth_passes = params.smooth_passes
        self._params.clamp = params.clamp
        self._params.rear_bias = params.rear_bias
        self._params.rear_rule_deg = params.rear_rule_deg

    def set_api_status(self, online: bool) -> None:
        """Update UI based on API status."""
        self.api_offline_alert.setVisible(not online)
        self.start_button.setEnabled(online and self._current_file is not None)
