"""
Slider Components for DynoAI PyQt6 GUI
Styled slider with label and value display
"""

from typing import Optional, Union

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class LabeledSlider(QWidget):
    """
    A slider widget with label, description, and value display.
    Matches the React TuningConfiguration slider style.
    """

    # Signals
    value_changed = pyqtSignal(float)

    def __init__(
        self,
        label: str,
        min_val: float,
        max_val: float,
        default_val: float = 0,
        step: float = 1,
        suffix: str = "",
        description: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._min_val = min_val
        self._max_val = max_val
        self._step = step
        self._suffix = suffix
        self._multiplier = 1 / step if step < 1 else 1

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header row (label + value)
        header = QHBoxLayout()
        header.setSpacing(8)

        # Label
        self.label = QLabel(label)
        font = self.label.font()
        font.setPointSize(10)
        font.setWeight(600)
        self.label.setFont(font)
        header.addWidget(self.label)

        header.addStretch()

        # Value display - Shadow Suite value class
        self.value_label = QLabel()
        self.value_label.setProperty("class", "value")
        self.value_label.setStyleSheet("""
            background-color: rgba(19, 24, 32, 0.8);
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 9pt;
        """)
        header.addWidget(self.value_label)

        layout.addLayout(header)

        # Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(int(min_val * self._multiplier))
        self.slider.setMaximum(int(max_val * self._multiplier))
        self.slider.setSingleStep(int(step * self._multiplier))
        self.slider.setValue(int(default_val * self._multiplier))
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

        # Description
        if description:
            self.description = QLabel(description)
            self.description.setProperty("class", "description")
            self.description.setWordWrap(True)
            layout.addWidget(self.description)

        # Update initial value display
        self._update_value_display(default_val)

    def _on_slider_changed(self, value: int) -> None:
        """Handle slider value change."""
        actual_value = value / self._multiplier
        self._update_value_display(actual_value)
        self.value_changed.emit(actual_value)

    def _update_value_display(self, value: float) -> None:
        """Update the value display label."""
        if self._step >= 1:
            display = f"{int(value)}{self._suffix}"
        else:
            # Determine decimal places from step
            decimals = len(str(self._step).split(".")[-1])
            display = f"{value:.{decimals}f}{self._suffix}"
        self.value_label.setText(display)

    def value(self) -> float:
        """Get the current slider value."""
        return self.slider.value() / self._multiplier

    def setValue(self, value: float) -> None:
        """Set the slider value."""
        self.slider.setValue(int(value * self._multiplier))

    def setEnabled(self, enabled: bool) -> None:
        """Enable or disable the slider."""
        super().setEnabled(enabled)
        self.slider.setEnabled(enabled)
        self.label.setEnabled(enabled)
        self.value_label.setEnabled(enabled)
        if hasattr(self, "description"):
            self.description.setEnabled(enabled)


class RangeSlider(QWidget):
    """
    A double-ended range slider for min/max value selection.
    """

    # Signals
    range_changed = pyqtSignal(float, float)  # min, max

    def __init__(
        self,
        label: str,
        min_val: float,
        max_val: float,
        default_min: float,
        default_max: float,
        step: float = 1,
        suffix: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._min_val = min_val
        self._max_val = max_val
        self._step = step
        self._suffix = suffix

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Label
        self.label = QLabel(label)
        font = self.label.font()
        font.setPointSize(10)
        font.setWeight(600)
        self.label.setFont(font)
        layout.addWidget(self.label)

        # Min slider row
        min_row = QHBoxLayout()
        min_row.setSpacing(8)

        min_label = QLabel("Min:")
        min_label.setFixedWidth(40)
        min_row.addWidget(min_label)

        self.min_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_slider.setMinimum(int(min_val))
        self.min_slider.setMaximum(int(max_val))
        self.min_slider.setValue(int(default_min))
        self.min_slider.valueChanged.connect(self._on_min_changed)
        min_row.addWidget(self.min_slider)

        self.min_value_label = QLabel(f"{int(default_min)}{suffix}")
        self.min_value_label.setFixedWidth(60)
        self.min_value_label.setStyleSheet("""
            background-color: #252a40;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: monospace;
        """)
        min_row.addWidget(self.min_value_label)

        layout.addLayout(min_row)

        # Max slider row
        max_row = QHBoxLayout()
        max_row.setSpacing(8)

        max_label = QLabel("Max:")
        max_label.setFixedWidth(40)
        max_row.addWidget(max_label)

        self.max_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_slider.setMinimum(int(min_val))
        self.max_slider.setMaximum(int(max_val))
        self.max_slider.setValue(int(default_max))
        self.max_slider.valueChanged.connect(self._on_max_changed)
        max_row.addWidget(self.max_slider)

        self.max_value_label = QLabel(f"{int(default_max)}{suffix}")
        self.max_value_label.setFixedWidth(60)
        self.max_value_label.setStyleSheet("""
            background-color: #252a40;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: monospace;
        """)
        max_row.addWidget(self.max_value_label)

        layout.addLayout(max_row)

    def _on_min_changed(self, value: int) -> None:
        """Handle min slider change."""
        # Ensure min doesn't exceed max
        if value > self.max_slider.value():
            self.min_slider.setValue(self.max_slider.value())
            return
        self.min_value_label.setText(f"{value}{self._suffix}")
        self.range_changed.emit(float(value), float(self.max_slider.value()))

    def _on_max_changed(self, value: int) -> None:
        """Handle max slider change."""
        # Ensure max doesn't go below min
        if value < self.min_slider.value():
            self.max_slider.setValue(self.min_slider.value())
            return
        self.max_value_label.setText(f"{value}{self._suffix}")
        self.range_changed.emit(float(self.min_slider.value()), float(value))

    def values(self) -> tuple[float, float]:
        """Get the current range values."""
        return (float(self.min_slider.value()), float(self.max_slider.value()))

    def setValues(self, min_val: float, max_val: float) -> None:
        """Set the range values."""
        self.min_slider.setValue(int(min_val))
        self.max_slider.setValue(int(max_val))
