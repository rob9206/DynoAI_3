"""
Settings Tab - Application Configuration
"""

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SettingsTab(QWidget):
    """Tab for application settings"""

    def __init__(self):
        super().__init__()
        self.settings = QSettings("DynoAI", "DynoAI Desktop")

        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Settings")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Analysis settings
        analysis_group = QGroupBox("Analysis Settings")
        analysis_layout = QFormLayout(analysis_group)

        self.smooth_passes_spin = QSpinBox()
        self.smooth_passes_spin.setRange(0, 10)
        self.smooth_passes_spin.setValue(2)
        analysis_layout.addRow("Smooth Passes:", self.smooth_passes_spin)

        self.clamp_spin = QDoubleSpinBox()
        self.clamp_spin.setRange(0.0, 30.0)
        self.clamp_spin.setValue(15.0)
        self.clamp_spin.setSuffix("%")
        analysis_layout.addRow("Correction Clamp:", self.clamp_spin)

        layout.addWidget(analysis_group)

        # JetDrive settings
        jetdrive_group = QGroupBox("JetDrive Settings")
        jetdrive_layout = QFormLayout(jetdrive_group)

        self.jetdrive_ip = QLineEdit()
        self.jetdrive_ip.setText("192.168.1.115")
        jetdrive_layout.addRow("DynowareRT IP:", self.jetdrive_ip)

        self.jetdrive_port = QSpinBox()
        self.jetdrive_port.setRange(1, 65535)
        self.jetdrive_port.setValue(63391)
        jetdrive_layout.addRow("TCP Port:", self.jetdrive_port)

        layout.addWidget(jetdrive_group)

        # Paths settings
        paths_group = QGroupBox("Directories")
        paths_layout = QFormLayout(paths_group)

        output_layout = QVBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setText("runs")
        output_layout.addWidget(self.output_dir_edit)

        browse_output_btn = QPushButton("Browse...")
        browse_output_btn.clicked.connect(self._browse_output_dir)
        output_layout.addWidget(browse_output_btn)

        paths_layout.addRow("Output Directory:", output_layout)

        layout.addWidget(paths_group)

        # Save button
        save_btn = QPushButton("💾 Save Settings")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

        # Add spacer
        layout.addStretch()

    def _load_settings(self):
        """Load settings from QSettings"""
        self.smooth_passes_spin.setValue(
            self.settings.value("analysis/smooth_passes", 2, type=int)
        )
        self.clamp_spin.setValue(
            self.settings.value("analysis/clamp", 15.0, type=float)
        )
        self.jetdrive_ip.setText(self.settings.value("jetdrive/ip", "192.168.1.115"))
        self.jetdrive_port.setValue(
            self.settings.value("jetdrive/port", 63391, type=int)
        )
        self.output_dir_edit.setText(self.settings.value("paths/output_dir", "runs"))

    def _save_settings(self):
        """Save settings to QSettings"""
        self.settings.setValue(
            "analysis/smooth_passes", self.smooth_passes_spin.value()
        )
        self.settings.setValue("analysis/clamp", self.clamp_spin.value())
        self.settings.setValue("jetdrive/ip", self.jetdrive_ip.text())
        self.settings.setValue("jetdrive/port", self.jetdrive_port.value())
        self.settings.setValue("paths/output_dir", self.output_dir_edit.text())

        # Show confirmation
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.information(
            self, "Settings Saved", "Settings have been saved successfully."
        )

    def _browse_output_dir(self):
        """Browse for output directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self.output_dir_edit.text()
        )

        if dir_path:
            self.output_dir_edit.setText(dir_path)
