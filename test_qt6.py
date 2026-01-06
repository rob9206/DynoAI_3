#!/usr/bin/env python3
"""
Simple Qt6 Test Application
Verifies PyQt6 installation and displays version information
"""

import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
)
from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR, Qt
from PyQt6.QtGui import QFont


class Qt6TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qt6 Test Application - DynoAI")
        self.setGeometry(100, 100, 600, 400)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Title label
        title_label = QLabel("🎉 Qt6 Successfully Installed!")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Version information
        version_text = QTextEdit()
        version_text.setReadOnly(True)
        version_info = f"""
PyQt6 Version: {PYQT_VERSION_STR}
Qt6 Version: {QT_VERSION_STR}
Python Version: {sys.version}

Installation Path: {sys.executable}

✅ PyQt6 is working correctly!
✅ Qt6 widgets are rendering properly!
✅ Ready for GUI development!

Features Available:
• Qt Widgets - Full widget toolkit
• Qt Core - Event loop, signals/slots, threading
• Qt Gui - Graphics, fonts, images
• Qt Network - HTTP, TCP/UDP sockets
• Qt Multimedia - Audio/video playback
• And many more Qt modules...
        """
        version_text.setPlainText(version_info.strip())
        layout.addWidget(version_text)
        
        # Test button
        test_button = QPushButton("Click Me to Test Events!")
        test_button.clicked.connect(self.on_button_clicked)
        layout.addWidget(test_button)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)
        
        self.click_count = 0
    
    def on_button_clicked(self):
        self.click_count += 1
        self.status_label.setText(f"✓ Button clicked {self.click_count} time(s) - Events working!")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Qt6 Test - DynoAI")
    
    window = Qt6TestWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
