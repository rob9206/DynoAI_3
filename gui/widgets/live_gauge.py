"""
Live Gauge Widget for DynoAI PyQt6 GUI
Needle-style circular gauge for real-time data display
"""

import math
from typing import Optional, Tuple
from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QLinearGradient, QRadialGradient, QPaintEvent
)

from gui.styles.theme import COLORS


@dataclass
class GaugeConfig:
    """Configuration for a gauge."""
    label: str
    units: str
    min_val: float = 0
    max_val: float = 100
    warning: Optional[float] = None
    critical: Optional[float] = None
    decimals: int = 0
    color: str = "#22d3ee"  # Cyan


class NeedleGauge(QWidget):
    """
    Needle-style half-circle gauge with tick marks.
    Used for RPM, HP, Torque, AFR display.
    """
    
    # Signals
    value_changed = pyqtSignal(float)
    
    # Default colors
    COLOR_BACKGROUND = QColor("#18181b")  # zinc-900
    COLOR_ARC_BG = QColor(63, 63, 70, 128)  # zinc-600 with alpha
    COLOR_TICK = QColor("#52525b")  # zinc-600
    COLOR_WARNING = QColor("#f59e0b")  # amber
    COLOR_CRITICAL = QColor("#ef4444")  # red
    COLOR_TEXT = QColor("#fafafa")  # zinc-50
    COLOR_LABEL = QColor("#71717a")  # zinc-500
    
    def __init__(
        self,
        config: GaugeConfig,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        self.config = config
        self._value = config.min_val
        self._target_value = config.min_val
        self._color = QColor(config.color)
        
        # Animation
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate_needle)
        self._animation_timer.setInterval(16)  # ~60fps
        
        # Size
        self.setMinimumSize(140, 100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
    def setValue(self, value: float) -> None:
        """Set the gauge value with animation."""
        self._target_value = max(self.config.min_val, min(self.config.max_val, value))
        if not self._animation_timer.isActive():
            self._animation_timer.start()
            
    def setValueImmediate(self, value: float) -> None:
        """Set value immediately without animation."""
        self._value = max(self.config.min_val, min(self.config.max_val, value))
        self._target_value = self._value
        self.update()
        
    def value(self) -> float:
        """Get current value."""
        return self._value
        
    def _animate_needle(self) -> None:
        """Animate needle movement."""
        diff = self._target_value - self._value
        if abs(diff) < 0.1:
            self._value = self._target_value
            self._animation_timer.stop()
        else:
            # Smooth easing
            self._value += diff * 0.2
        self.update()
        
    def _get_display_color(self) -> QColor:
        """Get color based on value and thresholds."""
        if self.config.critical and self._value >= self.config.critical:
            return self.COLOR_CRITICAL
        if self.config.warning and self._value >= self.config.warning:
            return self.COLOR_WARNING
        return self._color
        
    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the gauge."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate dimensions
        width = self.width()
        height = self.height()
        
        # Gauge center and radius
        cx = width / 2
        cy = height * 0.65
        radius = min(width / 2 - 10, height * 0.5)
        inner_radius = radius * 0.85
        
        # Calculate percentage and angle
        range_val = self.config.max_val - self.config.min_val
        percentage = (self._value - self.config.min_val) / range_val if range_val > 0 else 0
        percentage = max(0, min(1, percentage))
        
        # Angle: -180 (left) to 0 (right) for half circle
        needle_angle = -180 + percentage * 180
        
        # Draw arc background
        arc_rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
        painter.setPen(QPen(self.COLOR_ARC_BG, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(arc_rect, 180 * 16, -180 * 16)
        
        # Draw colored arc based on value
        display_color = self._get_display_color()
        painter.setPen(QPen(display_color, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        span_angle = int(-percentage * 180 * 16)
        painter.drawArc(arc_rect, 180 * 16, span_angle)
        
        # Draw tick marks
        segments = 5
        for i in range(segments + 1):
            angle = -180 + (i / segments) * 180
            rad = math.radians(angle)
            
            x1 = cx + math.cos(rad) * inner_radius
            y1 = cy + math.sin(rad) * inner_radius
            x2 = cx + math.cos(rad) * radius
            y2 = cy + math.sin(rad) * radius
            
            # Color based on threshold
            tick_color = self.COLOR_TICK
            if self.config.warning:
                warning_segment = (self.config.warning - self.config.min_val) / range_val * segments
                if i >= warning_segment:
                    tick_color = self.COLOR_WARNING
            if self.config.critical:
                critical_segment = (self.config.critical - self.config.min_val) / range_val * segments
                if i >= critical_segment:
                    tick_color = self.COLOR_CRITICAL
                    
            painter.setPen(QPen(tick_color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            
        # Draw needle
        needle_length = radius * 0.75
        needle_rad = math.radians(needle_angle)
        
        needle_tip_x = cx + math.cos(needle_rad) * needle_length
        needle_tip_y = cy + math.sin(needle_rad) * needle_length
        
        # Needle triangle
        needle_path = QPainterPath()
        needle_path.moveTo(cx - 3, cy)
        needle_path.lineTo(needle_tip_x, needle_tip_y)
        needle_path.lineTo(cx + 3, cy)
        needle_path.closeSubpath()
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(display_color))
        painter.drawPath(needle_path)
        
        # Center dot
        painter.setBrush(QBrush(QColor("#27272a")))
        painter.drawEllipse(QPointF(cx, cy), 6, 6)
        
        # Draw value text
        value_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        painter.setFont(value_font)
        painter.setPen(display_color)
        
        if self.config.decimals == 0:
            value_text = f"{int(self._value)}"
        else:
            value_text = f"{self._value:.{self.config.decimals}f}"
            
        value_rect = QRectF(0, cy + 5, width, 25)
        painter.drawText(value_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, value_text)
        
        # Draw label and units
        label_font = QFont("Segoe UI", 8)
        label_font.setCapitalization(QFont.Capitalization.AllUppercase)
        painter.setFont(label_font)
        painter.setPen(self.COLOR_LABEL)
        
        label_text = f"{self.config.label} ({self.config.units})"
        label_rect = QRectF(0, 5, width, 20)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label_text)


class CompactGauge(QWidget):
    """
    Compact gauge with label, value, and progress bar.
    Used for secondary readings.
    """
    
    def __init__(
        self,
        label: str,
        units: str,
        min_val: float = 0,
        max_val: float = 100,
        color: str = "#22d3ee",
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        self.label = label
        self.units = units
        self.min_val = min_val
        self.max_val = max_val
        self._value = min_val
        self._color = QColor(color)
        
        self.setMinimumSize(100, 60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
    def setValue(self, value: float) -> None:
        """Set the gauge value."""
        self._value = max(self.min_val, min(self.max_val, value))
        self.update()
        
    def value(self) -> float:
        """Get current value."""
        return self._value
        
    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the compact gauge."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#18181b")))
        painter.drawRoundedRect(0, 0, width, height, 8, 8)
        
        # Label
        label_font = QFont("Segoe UI", 8)
        painter.setFont(label_font)
        painter.setPen(QColor("#71717a"))
        painter.drawText(QRectF(8, 4, width - 16, 16), Qt.AlignmentFlag.AlignLeft, self.label)
        
        # Value
        value_font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        painter.setFont(value_font)
        painter.setPen(self._color)
        value_text = f"{self._value:.1f} {self.units}"
        painter.drawText(QRectF(8, 18, width - 16, 22), Qt.AlignmentFlag.AlignLeft, value_text)
        
        # Progress bar
        bar_y = height - 10
        bar_height = 4
        bar_width = width - 16
        
        # Bar background
        painter.setBrush(QBrush(QColor(63, 63, 70, 128)))
        painter.drawRoundedRect(QRectF(8, bar_y, bar_width, bar_height), 2, 2)
        
        # Bar fill
        range_val = self.max_val - self.min_val
        percentage = (self._value - self.min_val) / range_val if range_val > 0 else 0
        fill_width = bar_width * max(0, min(1, percentage))
        
        painter.setBrush(QBrush(self._color))
        painter.drawRoundedRect(QRectF(8, bar_y, fill_width, bar_height), 2, 2)


class GaugeCluster(QWidget):
    """
    A cluster of gauges for displaying multiple values.
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._gauges: dict[str, NeedleGauge] = {}
        
    def addGauge(self, key: str, config: GaugeConfig) -> NeedleGauge:
        """Add a gauge to the cluster."""
        gauge = NeedleGauge(config)
        self._gauges[key] = gauge
        return gauge
        
    def setValues(self, values: dict[str, float]) -> None:
        """Update multiple gauge values at once."""
        for key, value in values.items():
            if key in self._gauges:
                self._gauges[key].setValue(value)
                
    def getGauge(self, key: str) -> Optional[NeedleGauge]:
        """Get a gauge by key."""
        return self._gauges.get(key)

