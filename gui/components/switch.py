"""
Toggle Switch Component for DynoAI PyQt6 GUI
Custom styled toggle switch widget
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QCheckBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QRect, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen


class ToggleSwitch(QWidget):
    """
    A styled toggle switch widget.
    Custom painted to match modern UI design.
    """
    
    # Signals
    toggled = pyqtSignal(bool)
    
    # Shadow Suite colors
    COLOR_OFF = QColor("#2A313B")       # BORDER
    COLOR_ON = QColor("#8FA3B8")        # ACCENT
    COLOR_HANDLE = QColor("#D7DCE3")    # TEXT
    COLOR_OFF_HOVER = QColor("#353b60")
    COLOR_ON_HOVER = QColor("#9AAFBE")
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        initial_state: bool = False
    ):
        super().__init__(parent)
        
        self._checked = initial_state
        self._handle_position = 1.0 if initial_state else 0.0
        self._hover = False
        
        # Size
        self.setFixedSize(44, 24)
        
        # Animation
        self._animation = QPropertyAnimation(self, b"handle_position")
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Cursor
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
    @property
    def handle_position(self) -> float:
        """Get handle position (0.0 to 1.0)."""
        return self._handle_position
        
    @handle_position.setter
    def handle_position(self, value: float) -> None:
        """Set handle position."""
        self._handle_position = value
        self.update()
        
    def isChecked(self) -> bool:
        """Get the current state."""
        return self._checked
        
    def setChecked(self, checked: bool) -> None:
        """Set the checked state."""
        if self._checked != checked:
            self._checked = checked
            self._animate_toggle()
            self.toggled.emit(checked)
            
    def toggle(self) -> None:
        """Toggle the switch state."""
        self.setChecked(not self._checked)
        
    def _animate_toggle(self) -> None:
        """Animate the toggle transition."""
        self._animation.stop()
        self._animation.setStartValue(self._handle_position)
        self._animation.setEndValue(1.0 if self._checked else 0.0)
        self._animation.start()
        
    def paintEvent(self, event) -> None:
        """Paint the toggle switch."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Dimensions
        width = self.width()
        height = self.height()
        handle_radius = height // 2 - 2
        track_radius = height // 2
        
        # Track color
        if self._hover:
            track_color = self.COLOR_ON_HOVER if self._checked else self.COLOR_OFF_HOVER
        else:
            track_color = self.COLOR_ON if self._checked else self.COLOR_OFF
            
        # Draw track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(0, 0, width, height, track_radius, track_radius)
        
        # Calculate handle position
        handle_travel = width - height
        handle_x = 2 + (handle_travel * self._handle_position)
        handle_y = 2
        
        # Draw handle
        painter.setBrush(QBrush(self.COLOR_HANDLE))
        painter.drawEllipse(
            int(handle_x), handle_y,
            handle_radius * 2, handle_radius * 2
        )
        
    def mousePressEvent(self, event) -> None:
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
            
    def enterEvent(self, event) -> None:
        """Handle mouse enter."""
        self._hover = True
        self.update()
        
    def leaveEvent(self, event) -> None:
        """Handle mouse leave."""
        self._hover = False
        self.update()


class LabeledSwitch(QWidget):
    """
    A toggle switch with label and optional description.
    """
    
    # Signals
    toggled = pyqtSignal(bool)
    
    def __init__(
        self,
        label: str,
        description: str = "",
        initial_state: bool = False,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Text container
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        
        # Label
        self.label = QLabel(label)
        font = self.label.font()
        font.setPointSize(10)
        font.setWeight(600)
        self.label.setFont(font)
        text_layout.addWidget(self.label)
        
        # Description
        if description:
            self.description = QLabel(description)
            self.description.setProperty("class", "description")
            self.description.setWordWrap(True)
            text_layout.addWidget(self.description)
            
        layout.addLayout(text_layout)
        layout.addStretch()
        
        # Switch
        self.switch = ToggleSwitch(initial_state=initial_state)
        self.switch.toggled.connect(self._on_toggled)
        layout.addWidget(self.switch)
        
    def _on_toggled(self, checked: bool) -> None:
        """Handle switch toggle."""
        self.toggled.emit(checked)
        
    def isChecked(self) -> bool:
        """Get the current state."""
        return self.switch.isChecked()
        
    def setChecked(self, checked: bool) -> None:
        """Set the checked state."""
        self.switch.setChecked(checked)

