"""
Advanced Features Widget for DynoAI PyQt6 GUI
Decel fuel management and cylinder balancing controls
"""

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.api.client import AnalysisParams
from gui.components.card import (
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
)
from gui.components.switch import LabeledSwitch
from gui.styles.theme import COLORS


class AdvancedFeaturesWidget(QWidget):
    """
    Advanced tuning features panel.
    Includes Decel Fuel Management and Per-Cylinder Auto-Balancing.
    """

    # Signals
    params_changed = pyqtSignal(object)  # AnalysisParams

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Current parameters (reference from parent)
        self._params: Optional[AnalysisParams] = None

        # Build UI
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the advanced features UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Card container
        card = Card()

        # Header
        header = CardHeader()

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        icon = QLabel("✨")
        icon.setStyleSheet("font-size: 14pt;")
        title_row.addWidget(icon)

        title = CardTitle("Advanced Features")
        title_row.addWidget(title)
        title_row.addStretch()

        title_widget = QWidget()
        title_widget.setLayout(title_row)
        header.addWidget(title_widget)

        desc = CardDescription("Enable AI-powered tuning enhancements")
        header.addWidget(desc)

        card.addWidget(header)

        # Content
        content = CardContent()
        content.setSpacing(24)

        # =====================================================================
        # Decel Fuel Management Section
        # =====================================================================
        decel_section = QWidget()
        decel_layout = QVBoxLayout(decel_section)
        decel_layout.setContentsMargins(0, 0, 0, 0)
        decel_layout.setSpacing(12)

        # Toggle switch
        self.decel_switch = LabeledSwitch(
            label="Decel Fuel Management",
            description="Automatically eliminate exhaust popping during deceleration",
        )
        self.decel_switch.toggled.connect(self._on_decel_toggled)
        decel_layout.addWidget(self.decel_switch)

        # Options container (initially hidden) - Shadow Suite WARN accent
        self.decel_options = QFrame()
        self.decel_options.setStyleSheet(f"""
            QFrame {{
                border-left: 2px solid rgba(199, 168, 106, 0.3);
                padding-left: 16px;
                margin-left: 8px;
            }}
        """)
        self.decel_options.setVisible(False)

        decel_options_layout = QGridLayout(self.decel_options)
        decel_options_layout.setContentsMargins(16, 8, 0, 8)
        decel_options_layout.setSpacing(12)

        # Severity
        severity_label = QLabel("Severity")
        severity_label.setStyleSheet("font-size: 9pt;")
        decel_options_layout.addWidget(severity_label, 0, 0)

        self.decel_severity = QComboBox()
        self.decel_severity.addItems(["Low", "Medium", "High"])
        self.decel_severity.setCurrentText("Medium")
        self.decel_severity.currentTextChanged.connect(self._on_decel_severity_changed)
        decel_options_layout.addWidget(self.decel_severity, 1, 0)

        # Min RPM
        min_rpm_label = QLabel("Min RPM")
        min_rpm_label.setStyleSheet("font-size: 9pt;")
        decel_options_layout.addWidget(min_rpm_label, 0, 1)

        self.decel_rpm_min = QSpinBox()
        self.decel_rpm_min.setRange(0, 10000)
        self.decel_rpm_min.setSingleStep(100)
        self.decel_rpm_min.setValue(1500)
        self.decel_rpm_min.valueChanged.connect(self._on_decel_rpm_min_changed)
        decel_options_layout.addWidget(self.decel_rpm_min, 1, 1)

        # Max RPM
        max_rpm_label = QLabel("Max RPM")
        max_rpm_label.setStyleSheet("font-size: 9pt;")
        decel_options_layout.addWidget(max_rpm_label, 0, 2)

        self.decel_rpm_max = QSpinBox()
        self.decel_rpm_max.setRange(0, 10000)
        self.decel_rpm_max.setSingleStep(100)
        self.decel_rpm_max.setValue(5500)
        self.decel_rpm_max.valueChanged.connect(self._on_decel_rpm_max_changed)
        decel_options_layout.addWidget(self.decel_rpm_max, 1, 2)

        decel_layout.addWidget(self.decel_options)
        content.addWidget(decel_section)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['border']};")
        sep.setFixedHeight(1)
        content.addWidget(sep)

        # =====================================================================
        # Per-Cylinder Auto-Balancing Section
        # =====================================================================
        balance_section = QWidget()
        balance_layout = QVBoxLayout(balance_section)
        balance_layout.setContentsMargins(0, 0, 0, 0)
        balance_layout.setSpacing(12)

        # Toggle switch with icon
        balance_header = QHBoxLayout()
        balance_header.setSpacing(8)

        balance_icon = QLabel("📊")
        balance_icon.setStyleSheet("font-size: 12pt; color: #3b82f6;")
        balance_header.addWidget(balance_icon)

        self.balance_switch = LabeledSwitch(
            label="Per-Cylinder Auto-Balancing",
            description="Automatically equalize AFR between front and rear cylinders",
        )
        self.balance_switch.toggled.connect(self._on_balance_toggled)
        balance_layout.addWidget(self.balance_switch)

        # Options container (initially hidden)
        self.balance_options = QFrame()
        self.balance_options.setStyleSheet(f"""
            QFrame {{
                border-left: 2px solid rgba(59, 130, 246, 0.3);
                padding-left: 16px;
                margin-left: 8px;
            }}
        """)
        self.balance_options.setVisible(False)

        balance_options_layout = QGridLayout(self.balance_options)
        balance_options_layout.setContentsMargins(16, 8, 0, 8)
        balance_options_layout.setSpacing(12)

        # Balance Mode
        mode_label = QLabel("Balance Mode")
        mode_label.setStyleSheet("font-size: 9pt;")
        balance_options_layout.addWidget(mode_label, 0, 0)

        self.balance_mode = QComboBox()
        self.balance_mode.addItem("Equalize (Both toward average)", "equalize")
        self.balance_mode.addItem("Match Front (Rear to front)", "match_front")
        self.balance_mode.addItem("Match Rear (Front to rear)", "match_rear")
        self.balance_mode.currentIndexChanged.connect(self._on_balance_mode_changed)
        balance_options_layout.addWidget(self.balance_mode, 1, 0)

        # Max Correction
        correction_label = QLabel("Max Correction (%)")
        correction_label.setStyleSheet("font-size: 9pt;")
        balance_options_layout.addWidget(correction_label, 0, 1)

        self.balance_max_correction = QDoubleSpinBox()
        self.balance_max_correction.setRange(1.0, 5.0)
        self.balance_max_correction.setSingleStep(0.5)
        self.balance_max_correction.setValue(3.0)
        self.balance_max_correction.setDecimals(1)
        self.balance_max_correction.valueChanged.connect(
            self._on_balance_correction_changed
        )
        balance_options_layout.addWidget(self.balance_max_correction, 1, 1)

        balance_layout.addWidget(self.balance_options)
        content.addWidget(balance_section)

        card.addWidget(content)
        layout.addWidget(card)

    def set_params_reference(self, params: AnalysisParams) -> None:
        """Set reference to the params object to modify."""
        self._params = params

        # Update UI from params
        self.decel_switch.setChecked(params.decel_management)
        self.decel_options.setVisible(params.decel_management)
        self.decel_severity.setCurrentText(params.decel_severity.capitalize())
        self.decel_rpm_min.setValue(params.decel_rpm_min)
        self.decel_rpm_max.setValue(params.decel_rpm_max)

        self.balance_switch.setChecked(params.balance_cylinders)
        self.balance_options.setVisible(params.balance_cylinders)

        # Find and set balance mode
        for i in range(self.balance_mode.count()):
            if self.balance_mode.itemData(i) == params.balance_mode:
                self.balance_mode.setCurrentIndex(i)
                break

        self.balance_max_correction.setValue(params.balance_max_correction)

    def _emit_params_changed(self) -> None:
        """Emit params changed signal if we have a reference."""
        if self._params:
            self.params_changed.emit(self._params)

    # =========================================================================
    # Decel handlers
    # =========================================================================

    def _on_decel_toggled(self, checked: bool) -> None:
        """Handle decel management toggle."""
        self.decel_options.setVisible(checked)
        if self._params:
            self._params.decel_management = checked
            self._emit_params_changed()

    def _on_decel_severity_changed(self, text: str) -> None:
        """Handle severity change."""
        if self._params:
            self._params.decel_severity = text.lower()
            self._emit_params_changed()

    def _on_decel_rpm_min_changed(self, value: int) -> None:
        """Handle min RPM change."""
        if self._params:
            self._params.decel_rpm_min = value
            self._emit_params_changed()

    def _on_decel_rpm_max_changed(self, value: int) -> None:
        """Handle max RPM change."""
        if self._params:
            self._params.decel_rpm_max = value
            self._emit_params_changed()

    # =========================================================================
    # Balance handlers
    # =========================================================================

    def _on_balance_toggled(self, checked: bool) -> None:
        """Handle balance toggle."""
        self.balance_options.setVisible(checked)
        if self._params:
            self._params.balance_cylinders = checked
            self._emit_params_changed()

    def _on_balance_mode_changed(self, index: int) -> None:
        """Handle balance mode change."""
        if self._params:
            self._params.balance_mode = self.balance_mode.itemData(index)
            self._emit_params_changed()

    def _on_balance_correction_changed(self, value: float) -> None:
        """Handle max correction change."""
        if self._params:
            self._params.balance_max_correction = value
            self._emit_params_changed()

    def setEnabled(self, enabled: bool) -> None:
        """Enable or disable the widget."""
        super().setEnabled(enabled)
        self.decel_switch.setEnabled(enabled)
        self.balance_switch.setEnabled(enabled)
        # Options are controlled by switches
