"""
Tuning Configuration Widget for DynoAI PyQt6 GUI
Parameters panel matching the React TuningConfiguration component
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QDoubleSpinBox, QGridLayout
)
from PyQt6.QtCore import pyqtSignal

from gui.components.card import Card, CardHeader, CardContent, CardTitle, CardDescription
from gui.components.slider import LabeledSlider
from gui.api.client import AnalysisParams
from gui.styles.theme import COLORS


class TuningConfigWidget(QWidget):
    """
    Tuning parameters configuration panel.
    Includes smoothing, clamp, and rear cylinder bias settings.
    """
    
    # Signals
    params_changed = pyqtSignal(object)  # AnalysisParams
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Current parameters
        self._params = AnalysisParams()
        
        # Build UI
        self._build_ui()
        
    def _build_ui(self) -> None:
        """Build the configuration UI."""
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
        
        icon = QLabel("⚙️")
        icon.setStyleSheet("font-size: 14pt;")
        title_row.addWidget(icon)
        
        title = CardTitle("Tuning Configuration")
        title_row.addWidget(title)
        title_row.addStretch()
        
        title_widget = QWidget()
        title_widget.setLayout(title_row)
        header.addWidget(title_widget)
        
        card.addWidget(header)
        
        # Content
        content = CardContent()
        content.setSpacing(24)
        
        # Smoothing Intensity Slider
        self.smooth_slider = LabeledSlider(
            label="Smoothing Intensity",
            min_val=0,
            max_val=5,
            default_val=self._params.smooth_passes,
            step=1,
            suffix=" passes",
            description="Higher values blend adjacent cells more aggressively."
        )
        self.smooth_slider.value_changed.connect(self._on_smooth_changed)
        content.addWidget(self.smooth_slider)
        
        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet(f"background-color: {COLORS['border']};")
        sep1.setFixedHeight(1)
        content.addWidget(sep1)
        
        # Correction Limit (Clamp) Slider
        self.clamp_slider = LabeledSlider(
            label="Correction Limit (Clamp)",
            min_val=5.0,
            max_val=20.0,
            default_val=self._params.clamp,
            step=0.5,
            suffix="%",
            description="Maximum allowed VE change per cell."
        )
        self.clamp_slider.value_changed.connect(self._on_clamp_changed)
        content.addWidget(self.clamp_slider)
        
        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background-color: {COLORS['border']};")
        sep2.setFixedHeight(1)
        content.addWidget(sep2)
        
        # Rear Cylinder Bias Section
        bias_section = QWidget()
        bias_layout = QVBoxLayout(bias_section)
        bias_layout.setContentsMargins(0, 0, 0, 0)
        bias_layout.setSpacing(12)
        
        bias_label = QLabel("REAR CYLINDER BIAS")
        bias_label.setProperty("class", "section")
        bias_layout.addWidget(bias_label)
        
        # Bias inputs grid
        bias_grid = QGridLayout()
        bias_grid.setSpacing(16)
        
        # Fuel Bias
        fuel_label = QLabel("Fuel Bias (%)")
        fuel_label.setStyleSheet("font-size: 9pt;")
        bias_grid.addWidget(fuel_label, 0, 0)
        
        self.fuel_bias_spin = QDoubleSpinBox()
        self.fuel_bias_spin.setRange(-10.0, 10.0)
        self.fuel_bias_spin.setSingleStep(0.5)
        self.fuel_bias_spin.setValue(self._params.rear_bias)
        self.fuel_bias_spin.setDecimals(1)
        self.fuel_bias_spin.valueChanged.connect(self._on_rear_bias_changed)
        bias_grid.addWidget(self.fuel_bias_spin, 1, 0)
        
        # Spark Retard
        spark_label = QLabel("Spark Retard (deg)")
        spark_label.setStyleSheet("font-size: 9pt;")
        bias_grid.addWidget(spark_label, 0, 1)
        
        self.spark_retard_spin = QDoubleSpinBox()
        self.spark_retard_spin.setRange(0.0, 10.0)
        self.spark_retard_spin.setSingleStep(0.5)
        self.spark_retard_spin.setValue(self._params.rear_rule_deg)
        self.spark_retard_spin.setDecimals(1)
        self.spark_retard_spin.valueChanged.connect(self._on_rear_rule_changed)
        bias_grid.addWidget(self.spark_retard_spin, 1, 1)
        
        bias_layout.addLayout(bias_grid)
        content.addWidget(bias_section)
        
        card.addWidget(content)
        layout.addWidget(card)
        
    def _on_smooth_changed(self, value: float) -> None:
        """Handle smoothing slider change."""
        self._params.smooth_passes = int(value)
        self.params_changed.emit(self._params)
        
    def _on_clamp_changed(self, value: float) -> None:
        """Handle clamp slider change."""
        self._params.clamp = value
        self.params_changed.emit(self._params)
        
    def _on_rear_bias_changed(self, value: float) -> None:
        """Handle rear bias change."""
        self._params.rear_bias = value
        self.params_changed.emit(self._params)
        
    def _on_rear_rule_changed(self, value: float) -> None:
        """Handle rear rule change."""
        self._params.rear_rule_deg = value
        self.params_changed.emit(self._params)
        
    def get_params(self) -> AnalysisParams:
        """Get the current parameters."""
        return self._params
        
    def set_params(self, params: AnalysisParams) -> None:
        """Set the parameters."""
        self._params = params
        
        # Update UI
        self.smooth_slider.setValue(params.smooth_passes)
        self.clamp_slider.setValue(params.clamp)
        self.fuel_bias_spin.setValue(params.rear_bias)
        self.spark_retard_spin.setValue(params.rear_rule_deg)
        
    def setEnabled(self, enabled: bool) -> None:
        """Enable or disable the widget."""
        super().setEnabled(enabled)
        self.smooth_slider.setEnabled(enabled)
        self.clamp_slider.setEnabled(enabled)
        self.fuel_bias_spin.setEnabled(enabled)
        self.spark_retard_spin.setEnabled(enabled)

