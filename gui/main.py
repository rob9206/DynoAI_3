#!/usr/bin/env python3
"""
DynoAI GUI - Main Entry Point
Launch the PyQt6 desktop application
"""

import os
import sys

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QFont, QFontDatabase, QIcon
from PyQt6.QtWidgets import QApplication

from gui.app import MainWindow
from gui.styles.theme import apply_theme

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    """Main application entry point."""
    # Enable High DPI scaling (Handled automatically in PyQt6, but keeping for reference if needed)
    # QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("DynoAI")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Dawson Dynamics")
    app.setOrganizationDomain("dawsondynamics.com")

    # Set application icon
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Load custom fonts
    fonts_dir = os.path.join(os.path.dirname(__file__), "assets", "fonts")
    if os.path.exists(fonts_dir):
        for font_file in os.listdir(fonts_dir):
            if font_file.endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(os.path.join(fonts_dir, font_file))

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Apply Shadow Suite theme
    apply_theme(app)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
