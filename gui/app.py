"""
DynoAI Main Application Window
QMainWindow with sidebar navigation and stacked pages
"""

import os
from typing import Optional, Dict

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame, QSizePolicy, QSpacerItem, QMessageBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QCursor

from gui.api.client import APIClient
from gui.styles.theme import COLORS


class NavButton(QPushButton):
    """Navigation sidebar button."""
    
    def __init__(
        self,
        text: str,
        icon: str = "",
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        self._active = False
        
        # Set text with icon
        if icon:
            self.setText(f"{icon}  {text}")
        else:
            self.setText(text)
            
        # Styling
        self.setProperty("class", "nav-item")
        self.setMinimumHeight(44)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        # Alignment
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 16px;
            }
        """)
        
    def setActive(self, active: bool) -> None:
        """Set the active state."""
        self._active = active
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class Sidebar(QFrame):
    """
    Navigation sidebar with page navigation buttons.
    """
    
    # Signals
    page_selected = pyqtSignal(str)  # page name
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.setProperty("class", "sidebar")
        self.setFixedWidth(240)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)
        
        # Logo/Title
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(8, 8, 8, 16)
        title_layout.setSpacing(12)
        
        # Logo emoji
        logo = QLabel("🔧")
        logo.setStyleSheet("font-size: 24pt;")
        title_layout.addWidget(logo)
        
        # Title text
        title_text_layout = QVBoxLayout()
        title_text_layout.setSpacing(0)
        
        title = QLabel("DynoAI")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setWeight(700)
        title.setFont(title_font)
        title_text_layout.addWidget(title)
        
        subtitle = QLabel("Tuning Intelligence")
        subtitle.setProperty("class", "muted")
        subtitle.setStyleSheet("font-size: 9pt;")
        title_text_layout.addWidget(subtitle)
        
        title_layout.addLayout(title_text_layout)
        title_layout.addStretch()
        
        layout.addWidget(title_container)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['border']};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        layout.addSpacing(12)
        
        # Navigation buttons
        self._nav_buttons: Dict[str, NavButton] = {}
        
        self._add_nav_button("dashboard", "Dashboard", "📊", layout)
        self._add_nav_button("results", "Results", "📈", layout)
        self._add_nav_button("history", "History", "📋", layout)
        
        # Spacer
        layout.addSpacing(16)
        
        # Section header - Shadow Suite: ALL CAPS, muted
        section_label = QLabel("ADVANCED")
        section_label.setProperty("class", "section")
        section_label.setStyleSheet("""
            padding-left: 16px;
        """)
        layout.addWidget(section_label)
        layout.addSpacing(4)
        
        self._add_nav_button("jetdrive", "JetDrive Live", "🎯", layout)
        
        # Push everything up
        layout.addStretch()
        
        # Status indicator at bottom
        self.status_container = QWidget()
        status_layout = QHBoxLayout(self.status_container)
        status_layout.setContentsMargins(16, 12, 16, 0)
        status_layout.setSpacing(8)
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {COLORS['error']}; font-size: 10pt;")
        status_layout.addWidget(self.status_dot)
        
        self.status_text = QLabel("API Offline")
        self.status_text.setProperty("class", "muted")
        self.status_text.setStyleSheet("font-size: 9pt;")
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()
        
        layout.addWidget(self.status_container)
        
        # Set default active
        self.setActivePage("dashboard")
        
    def _add_nav_button(
        self,
        page_id: str,
        text: str,
        icon: str,
        layout: QVBoxLayout
    ) -> None:
        """Add a navigation button."""
        btn = NavButton(text, icon)
        btn.clicked.connect(lambda: self._on_nav_clicked(page_id))
        self._nav_buttons[page_id] = btn
        layout.addWidget(btn)
        
    def _on_nav_clicked(self, page_id: str) -> None:
        """Handle navigation button click."""
        self.setActivePage(page_id)
        self.page_selected.emit(page_id)
        
    def setActivePage(self, page_id: str) -> None:
        """Set the active page."""
        for pid, btn in self._nav_buttons.items():
            btn.setActive(pid == page_id)
            
    def setApiStatus(self, online: bool, version: str = "") -> None:
        """Update the API status indicator."""
        if online:
            self.status_dot.setStyleSheet(f"color: {COLORS['success']}; font-size: 10pt;")
            text = f"API Online v{version}" if version else "API Online"
            self.status_text.setText(text)
        else:
            self.status_dot.setStyleSheet(f"color: {COLORS['error']}; font-size: 10pt;")
            self.status_text.setText("API Offline")


class MainWindow(QMainWindow):
    """
    Main application window with sidebar navigation and stacked pages.
    """
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("DynoAI - Tuning Intelligence")
        self.setMinimumSize(1200, 800)
        
        # API Client
        self.api_client = APIClient()
        self.api_client.health_checked.connect(self._on_health_checked)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.page_selected.connect(self._on_page_selected)
        main_layout.addWidget(self.sidebar)
        
        # Page stack
        self.page_stack = QStackedWidget()
        main_layout.addWidget(self.page_stack, 1)
        
        # Create pages
        self._create_pages()
        
        # Health check timer
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._check_health)
        self._health_timer.start(30000)  # Check every 30 seconds
        
        # Initial health check
        QTimer.singleShot(100, self._check_health)
        
    def _create_pages(self) -> None:
        """Create and add pages to the stack."""
        # Import pages here to avoid circular imports
        from gui.pages.dashboard import DashboardPage
        from gui.pages.results import ResultsPage
        from gui.pages.history import HistoryPage
        
        # Dashboard
        self.dashboard_page = DashboardPage(self.api_client)
        self.dashboard_page.navigate_to_results.connect(self._navigate_to_results)
        self.page_stack.addWidget(self.dashboard_page)
        
        # Results
        self.results_page = ResultsPage(self.api_client)
        self.page_stack.addWidget(self.results_page)
        
        # History
        self.history_page = HistoryPage(self.api_client)
        self.history_page.run_selected.connect(self._navigate_to_results)
        self.page_stack.addWidget(self.history_page)
        
        # JetDrive Command Center
        from gui.pages.jetdrive import JetDrivePage
        self.jetdrive_page = JetDrivePage()
        self.page_stack.addWidget(self.jetdrive_page)
        
        # Page index mapping
        self._page_indices = {
            "dashboard": 0,
            "results": 1,
            "history": 2,
            "jetdrive": 3,
        }
        
    def _on_page_selected(self, page_id: str) -> None:
        """Handle page selection from sidebar."""
        if page_id in self._page_indices:
            self.page_stack.setCurrentIndex(self._page_indices[page_id])
            
            # Refresh data when switching to certain pages
            if page_id == "history":
                self.history_page.refresh()
                
    def _navigate_to_results(self, run_id: str) -> None:
        """Navigate to results page for a specific run."""
        self.sidebar.setActivePage("results")
        self.page_stack.setCurrentIndex(self._page_indices["results"])
        self.results_page.load_run(run_id)
        
    def _check_health(self) -> None:
        """Check API health status."""
        self.api_client.check_health()
        
    def _on_health_checked(self, online: bool, version_or_error: str) -> None:
        """Handle health check result."""
        if online:
            self.sidebar.setApiStatus(True, version_or_error)
        else:
            self.sidebar.setApiStatus(False)
            
    def closeEvent(self, event) -> None:
        """Handle window close."""
        # Clean up API client
        self.api_client.cleanup()
        super().closeEvent(event)
