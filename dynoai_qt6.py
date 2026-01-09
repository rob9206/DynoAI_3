#!/usr/bin/env python3
"""
DynoAI Qt6 Desktop Application
Professional native desktop application for dyno tuning analysis
"""

import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QSettings, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# Import our backend services
from api.services.autotune_workflow import AutoTuneWorkflow, DataSource


class DynoAIMainWindow(QMainWindow):
    """Main application window for DynoAI"""

    def __init__(self):
        super().__init__()
        self.workflow = AutoTuneWorkflow()
        self.settings = QSettings("DynoAI", "DynoAI Desktop")

        self.setWindowTitle("DynoAI - Professional Dyno Tuning Analysis")
        self.setGeometry(100, 100, 1400, 900)

        # Initialize UI components
        self._init_ui()
        self._create_menu_bar()
        self._create_status_bar()

        # Restore window state
        self._restore_settings()

    def _init_ui(self):
        """Initialize the main UI layout"""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget for different sections
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        main_layout.addWidget(self.tab_widget)

        # Add tabs
        self._create_analysis_tab()
        self._create_jetdrive_tab()
        self._create_results_tab()
        self._create_settings_tab()

    def _create_analysis_tab(self):
        """Create the analysis tab for CSV file analysis"""
        from dynoai.gui.analysis_tab import AnalysisTab

        analysis_tab = AnalysisTab(self.workflow)
        self.tab_widget.addTab(analysis_tab, "📊 Analysis")

    def _create_jetdrive_tab(self):
        """Create the JetDrive live data tab"""
        from dynoai.gui.jetdrive_tab import JetDriveTab

        jetdrive_tab = JetDriveTab(self.workflow)
        self.tab_widget.addTab(jetdrive_tab, "🔧 JetDrive")

    def _create_results_tab(self):
        """Create the results browser tab"""
        from dynoai.gui.results_tab import ResultsTab

        results_tab = ResultsTab(self.workflow)
        self.tab_widget.addTab(results_tab, "📈 Results")

    def _create_settings_tab(self):
        """Create the settings tab"""
        from dynoai.gui.settings_tab import SettingsTab

        settings_tab = SettingsTab()
        self.tab_widget.addTab(settings_tab, "⚙️ Settings")

    def _create_menu_bar(self):
        """Create the application menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open CSV...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_csv_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        simulator_action = QAction("Start &Simulator", self)
        simulator_action.triggered.connect(self._start_simulator)
        tools_menu.addAction(simulator_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About DynoAI", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        docs_action = QAction("&Documentation", self)
        docs_action.triggered.connect(self._show_docs)
        help_menu.addAction(docs_action)

    def _create_status_bar(self):
        """Create the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Add permanent widgets to status bar
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        # Add progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _open_csv_file(self):
        """Open a CSV file for analysis"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Dyno Log CSV",
            str(Path.home()),
            "CSV Files (*.csv);;All Files (*.*)",
        )

        if file_path:
            # Switch to analysis tab and load file
            self.tab_widget.setCurrentIndex(0)
            # Trigger file load in analysis tab
            analysis_tab = self.tab_widget.widget(0)
            if hasattr(analysis_tab, "load_file"):
                analysis_tab.load_file(file_path)

    def _start_simulator(self):
        """Start the dyno simulator"""
        # Switch to JetDrive tab
        self.tab_widget.setCurrentIndex(1)
        # Trigger simulator start
        jetdrive_tab = self.tab_widget.widget(1)
        if hasattr(jetdrive_tab, "start_simulator"):
            jetdrive_tab.start_simulator()

    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About DynoAI",
            "<h2>DynoAI Desktop v1.3.0</h2>"
            "<p><b>Professional Dyno Tuning Analysis</b></p>"
            "<p>Advanced VE correction calculation and analysis for motorcycle tuning.</p>"
            "<p>© 2024-2025 DynoAI Project</p>"
            "<p>Built with PyQt6 and Python</p>",
        )

    def _show_docs(self):
        """Open documentation"""
        import webbrowser

        docs_path = Path(__file__).parent / "docs" / "README.md"
        if docs_path.exists():
            webbrowser.open(docs_path.as_uri())
        else:
            QMessageBox.information(
                self,
                "Documentation",
                "Documentation not found. Please visit the GitHub repository.",
            )

    def _restore_settings(self):
        """Restore window settings from previous session"""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

        last_tab = self.settings.value("lastTab", 0, type=int)
        self.tab_widget.setCurrentIndex(last_tab)

    def closeEvent(self, event):
        """Save settings on close"""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.setValue("lastTab", self.tab_widget.currentIndex())
        event.accept()

    def set_status(self, message: str, timeout: int = 0):
        """Set status bar message"""
        self.status_bar.showMessage(message, timeout)

    def show_progress(self, show: bool = True):
        """Show or hide progress bar"""
        self.progress_bar.setVisible(show)

    def set_progress(self, value: int):
        """Set progress bar value (0-100)"""
        self.progress_bar.setValue(value)


def main():
    """Main entry point for Qt6 application"""
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("DynoAI")
    app.setOrganizationName("DynoAI")
    app.setOrganizationDomain("dynoai.app")

    # Set application style
    app.setStyle("Fusion")

    # Create and show main window
    window = DynoAIMainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
