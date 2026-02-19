"""
History Page for DynoAI PyQt6 GUI
List of past analysis runs
"""

from datetime import datetime
from typing import List, Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.api.client import AnalysisRun, APIClient
from gui.components.button import Button, ButtonSize, ButtonVariant
from gui.components.card import (
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
)
from gui.styles.theme import COLORS


class RunListItem(QFrame):
    """
    List item widget for a single analysis run.
    """

    clicked = pyqtSignal(str)  # run_id

    def __init__(self, run: AnalysisRun, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._run = run

        # Styling - Shadow Suite panel
        self.setProperty("class", "panel")
        self.setStyleSheet(f"""
            RunListItem:hover {{
                background-color: {COLORS["muted"]};
                border-color: {COLORS["primary"]};
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # Icon
        icon = QLabel("📊")
        icon.setStyleSheet("font-size: 20pt;")
        layout.addWidget(icon)

        # Info section
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        # Filename
        filename = QLabel(run.input_file)
        filename.setStyleSheet("font-weight: 600; font-size: 11pt;")
        info_layout.addWidget(filename)

        # Run ID and timestamp
        try:
            dt = datetime.fromisoformat(run.timestamp.replace("Z", "+00:00"))
            time_str = dt.strftime("%b %d, %Y at %I:%M %p")
        except:
            time_str = run.timestamp

        meta = QLabel(f"ID: {run.run_id[:8]}...  •  {time_str}")
        meta.setProperty("class", "muted")
        meta.setStyleSheet("font-size: 9pt;")
        info_layout.addWidget(meta)

        layout.addLayout(info_layout, 1)

        # View button
        view_btn = Button("View", ButtonVariant.SECONDARY, ButtonSize.SMALL)
        view_btn.clicked.connect(lambda: self.clicked.emit(run.run_id))
        layout.addWidget(view_btn)

    def mousePressEvent(self, event) -> None:
        """Handle mouse click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._run.run_id)
        super().mousePressEvent(event)


class HistoryPage(QWidget):
    """
    History page showing list of past analysis runs.
    """

    # Signals
    run_selected = pyqtSignal(str)  # run_id

    def __init__(self, api_client: APIClient, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.api_client = api_client
        self._runs: List[AnalysisRun] = []

        # Connect API signals
        self.api_client.runs_received.connect(self._on_runs_received)

        # Build UI
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the history UI."""
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

        title = QLabel("Analysis History")
        title.setStyleSheet("font-size: 24pt; font-weight: 700;")
        title_section.addWidget(title)

        self.count_label = QLabel("Loading...")
        self.count_label.setStyleSheet(f"color: {COLORS['muted_foreground']};")
        title_section.addWidget(self.count_label)

        header_layout.addLayout(title_section)
        header_layout.addStretch()

        # Refresh button
        self.refresh_btn = Button("Refresh", ButtonVariant.SECONDARY, icon="🔄")
        self.refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(self.refresh_btn)

        scroll_layout.addWidget(header)

        # =====================================================================
        # Runs List
        # =====================================================================
        self.runs_container = QVBoxLayout()
        self.runs_container.setSpacing(12)

        # Loading placeholder
        self.loading_label = QLabel("Loading analysis history...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet(
            f"color: {COLORS['muted_foreground']}; padding: 48px;"
        )
        self.runs_container.addWidget(self.loading_label)

        # Empty state
        self.empty_state = QFrame()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(16)

        empty_icon = QLabel("📋")
        empty_icon.setStyleSheet("font-size: 48pt;")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)

        empty_title = QLabel("No Analysis History")
        empty_title.setStyleSheet("font-size: 16pt; font-weight: 600;")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)

        empty_desc = QLabel(
            "Run your first analysis from the Dashboard to see results here."
        )
        empty_desc.setStyleSheet(f"color: {COLORS['muted_foreground']};")
        empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_desc)

        self.empty_state.setVisible(False)
        self.runs_container.addWidget(self.empty_state)

        scroll_layout.addLayout(self.runs_container)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def refresh(self) -> None:
        """Refresh the runs list."""
        self.loading_label.setVisible(True)
        self.empty_state.setVisible(False)
        self.count_label.setText("Loading...")

        # Clear existing run items
        self._clear_run_items()

        # Fetch runs
        self.api_client.get_runs()

    def _clear_run_items(self) -> None:
        """Clear all run list items."""
        for i in reversed(range(self.runs_container.count())):
            item = self.runs_container.itemAt(i)
            widget = item.widget()
            if widget and isinstance(widget, RunListItem):
                widget.setParent(None)
                widget.deleteLater()

    def _on_runs_received(self, runs: List[AnalysisRun]) -> None:
        """Handle runs list received."""
        self._runs = runs
        self.loading_label.setVisible(False)

        # Clear existing items
        self._clear_run_items()

        if not runs:
            self.empty_state.setVisible(True)
            self.count_label.setText("0 analyses")
            return

        self.empty_state.setVisible(False)
        self.count_label.setText(
            f"{len(runs)} analysis run{'s' if len(runs) != 1 else ''}"
        )

        # Add run items
        for run in runs:
            item = RunListItem(run)
            item.clicked.connect(self._on_run_clicked)
            # Insert before the stretch
            self.runs_container.insertWidget(self.runs_container.count() - 1, item)

    def _on_run_clicked(self, run_id: str) -> None:
        """Handle run item click."""
        self.run_selected.emit(run_id)
