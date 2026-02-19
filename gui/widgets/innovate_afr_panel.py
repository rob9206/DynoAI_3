"""
InnovateAFRPanel - Real-time AFR display for Innovate DLG-1/LC-2 wideband
Port of frontend/src/components/jetdrive/InnovateAFRPanel.tsx

Shows dual-channel AFR gauges with connection controls
and AFR target comparison.
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from gui.components.card import (
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
)
from gui.styles.theme import COLORS


def get_afr_color(afr: float, target: float = 14.7) -> str:
    """Get color based on AFR deviation from target."""
    if target == 0:
        target = 14.7  # Safety: prevent division by zero

    deviation = abs(afr - target)
    percent = deviation / target

    if percent < 0.03:
        return "#22c55e"  # Green - within 3%
    if percent < 0.07:
        return "#84cc16"  # Lime - within 7%
    if percent < 0.10:
        return "#eab308"  # Yellow - within 10%
    if percent < 0.15:
        return "#f97316"  # Orange - within 15%
    return "#ef4444"  # Red - >15% off


def get_afr_status(afr: float, target: float = 14.7) -> Tuple[str, str]:
    """Get status text and color based on AFR deviation."""
    if target == 0:
        target = 14.7  # Safety: prevent division by zero

    deviation = afr - target
    percent = (deviation / target) * 100

    if abs(percent) < 3:
        return ("ON TARGET", "#22c55e")
    if deviation < 0:
        return (f"{abs(percent):.0f}% RICH", "#f97316")
    return (f"{percent:.0f}% LEAN", "#3b82f6")


class AFRGaugeWidget(QWidget):
    """
    Circular AFR gauge with arc display.
    Shows value, target marker, and status text.
    """

    def __init__(
        self,
        label: str = "AFR",
        target: float = 14.7,
        size: int = 140,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._label = label
        self._target = target
        self._value = 0.0
        self._connected = False
        self._size = size

        self.setFixedSize(size, size + 50)  # Extra space for label

    def setValue(self, value: float) -> None:
        """Set the AFR value."""
        self._value = value
        self.update()

    def setTarget(self, target: float) -> None:
        """Set the target AFR."""
        self._target = target
        self.update()

    def setConnected(self, connected: bool) -> None:
        """Set connection status."""
        self._connected = connected
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the gauge."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = self._size
        radius = size // 2 - 10
        center = QPointF(size // 2, size // 2)

        # Map AFR to gauge position (10-20 AFR range)
        min_afr = 10.0
        max_afr = 20.0
        normalized = max(0, min(1, (self._value - min_afr) / (max_afr - min_afr)))

        # Draw background arc (270°)
        pen = QPen(QColor("#374151"), 8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        rect = QRectF(10, 10, size - 20, size - 20)
        # Start at 135° (bottom-left), sweep 270° clockwise
        painter.drawArc(rect, 225 * 16, -270 * 16)

        # Draw value arc
        color = QColor(
            get_afr_color(self._value, self._target) if self._connected else "#6b7280"
        )
        pen = QPen(color, 8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        sweep_angle = int(-270 * normalized * 16)
        painter.drawArc(rect, 225 * 16, sweep_angle)

        # Draw target marker
        if self._connected:
            target_normalized = max(
                0, min(1, (self._target - min_afr) / (max_afr - min_afr))
            )
            target_angle = math.radians(225 - 270 * target_normalized)

            marker_x = center.x() + radius * math.cos(target_angle)
            marker_y = center.y() - radius * math.sin(target_angle)

            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.drawEllipse(QPointF(marker_x, marker_y), 4, 4)

        # Draw center value
        painter.setPen(QPen(color))

        font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        painter.setFont(font)

        value_text = f"{self._value:.1f}" if self._connected else "--.-"

        # Center text in gauge
        text_rect = QRectF(0, size // 2 - 15, size, 30)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, value_text)

        # Draw "AFR" below value
        font.setPointSize(10)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#9ca3af")))

        text_rect = QRectF(0, size // 2 + 12, size, 20)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "AFR")

        # Draw label below gauge
        font.setPointSize(11)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(QPen(QColor(COLORS["text_secondary"])))

        text_rect = QRectF(0, size + 5, size, 20)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self._label)

        # Draw status below label
        if self._connected:
            status_text, status_color = get_afr_status(self._value, self._target)
        else:
            status_text, status_color = ("NO SIGNAL", "#6b7280")

        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QPen(QColor(status_color)))

        text_rect = QRectF(0, size + 25, size, 20)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, status_text)


class InnovateAFRPanel(QWidget):
    """
    Panel for Innovate wideband AFR display.
    Shows dual-channel gauges with connection controls.
    """

    # Signals
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    afr_updated = pyqtSignal(float, float)  # channelA, channelB

    def __init__(
        self,
        api_url: str = "http://127.0.0.1:5001/api/jetdrive",
        default_port: str = "COM5",
        afr_target: float = 14.7,
        compact: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._api_url = api_url
        self._default_port = default_port
        self._target = afr_target
        self._compact = compact
        self._is_connected = False
        self._is_streaming = False

        # Channel data
        self._channel_a: float = 0.0
        self._channel_b: float = 0.0
        self._channel_a_connected = False
        self._channel_b_connected = False

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = Card()

        # Header
        header = CardHeader()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Icon and title
        icon_label = QLabel("🔥")
        icon_label.setStyleSheet(f"""
            background-color: #f9731620;
            border-radius: 8px;
            padding: 8px;
            font-size: 16pt;
        """)
        header_layout.addWidget(icon_label)

        title_section = QVBoxLayout()
        title_section.setSpacing(2)

        title = CardTitle("Innovate Wideband AFR")
        title_section.addWidget(title)

        desc = CardDescription("DLG-1 Dual Lambda Gauge")
        title_section.addWidget(desc)

        header_layout.addLayout(title_section)
        header_layout.addStretch()

        # Status badge
        self.status_badge = QLabel("Disconnected")
        self.status_badge.setStyleSheet(f"""
            background-color: #ef444430;
            color: #ef4444;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 9pt;
            font-weight: bold;
        """)
        header_layout.addWidget(self.status_badge)

        header_widget = QWidget()
        header_widget.setLayout(header_layout)
        header.addWidget(header_widget)
        card.addWidget(header)

        # Content
        content = CardContent()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(16)

        # Gauges
        gauges_layout = QHBoxLayout()
        gauges_layout.setSpacing(24)
        gauges_layout.addStretch()

        self.gauge_a = AFRGaugeWidget("Sensor A (Front)", self._target)
        gauges_layout.addWidget(self.gauge_a)

        self.gauge_b = AFRGaugeWidget("Sensor B (Rear)", self._target)
        gauges_layout.addWidget(self.gauge_b)

        gauges_layout.addStretch()
        content_layout.addLayout(gauges_layout)

        # Connection controls
        controls_frame = QFrame()
        controls_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["muted"]};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setSpacing(12)

        # Port selection row
        port_row = QHBoxLayout()

        port_label = QLabel("COM Port:")
        port_label.setStyleSheet(f"color: {COLORS['muted_foreground']};")
        port_row.addWidget(port_label)

        self.port_combo = QComboBox()
        self.port_combo.addItem(self._default_port)
        self.port_combo.setMinimumWidth(100)
        port_row.addWidget(self.port_combo)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(32, 32)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {COLORS["surface_hover"]};
            }}
        """)
        refresh_btn.clicked.connect(self._refresh_ports)
        port_row.addWidget(refresh_btn)

        port_row.addStretch()
        controls_layout.addLayout(port_row)

        # Target AFR slider
        target_row = QHBoxLayout()

        target_label = QLabel("Target AFR:")
        target_label.setStyleSheet(f"color: {COLORS['muted_foreground']};")
        target_row.addWidget(target_label)

        self.target_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_slider.setRange(100, 180)  # 10.0 - 18.0
        self.target_slider.setValue(int(self._target * 10))
        self.target_slider.valueChanged.connect(self._on_target_changed)
        self.target_slider.setMinimumWidth(150)
        target_row.addWidget(self.target_slider)

        self.target_value_label = QLabel(f"{self._target:.1f}")
        self.target_value_label.setStyleSheet(
            "font-weight: bold; font-family: monospace; min-width: 40px;"
        )
        target_row.addWidget(self.target_value_label)

        controls_layout.addLayout(target_row)

        # Connect button
        self.connect_btn = QPushButton("🔌 Connect to DLG-1")
        self.connect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS["primary"]};
                color: #1a1b26;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS["primary_hover"]};
            }}
        """)
        self.connect_btn.clicked.connect(self._toggle_connection)
        controls_layout.addWidget(self.connect_btn)

        content_layout.addWidget(controls_frame)

        content_widget = QWidget()
        content_widget.setLayout(content_layout)
        content.addWidget(content_widget)
        card.addWidget(content)

        layout.addWidget(card)

    def _on_target_changed(self, value: int) -> None:
        """Handle target slider change."""
        self._target = value / 10.0
        self.target_value_label.setText(f"{self._target:.1f}")
        self.gauge_a.setTarget(self._target)
        self.gauge_b.setTarget(self._target)

    def _refresh_ports(self) -> None:
        """Refresh available COM ports."""
        # In a real implementation, this would query available ports
        # For now, just add some common ports
        self.port_combo.clear()
        self.port_combo.addItems(["COM1", "COM2", "COM3", "COM4", "COM5", "COM6"])

    def _toggle_connection(self) -> None:
        """Toggle connection to DLG-1."""
        if self._is_connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        """Connect to the Innovate device."""
        # In a real implementation, this would call the API
        self._is_connected = True
        self._is_streaming = True
        self._channel_a_connected = True
        self._channel_b_connected = True

        self._update_status()
        self.connect_btn.setText("⏹ Disconnect")
        self.connect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #dc2626;
            }}
        """)

        self.gauge_a.setConnected(True)
        self.gauge_b.setConnected(True)

        self.connected.emit()

    def _disconnect(self) -> None:
        """Disconnect from the Innovate device."""
        self._is_connected = False
        self._is_streaming = False
        self._channel_a_connected = False
        self._channel_b_connected = False

        self._update_status()
        self.connect_btn.setText("🔌 Connect to DLG-1")
        self.connect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS["primary"]};
                color: #1a1b26;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS["primary_hover"]};
            }}
        """)

        self.gauge_a.setConnected(False)
        self.gauge_b.setConnected(False)

        self.disconnected.emit()

    def _update_status(self) -> None:
        """Update status badge."""
        if self._is_connected:
            if self._is_streaming:
                self.status_badge.setText("✓ Streaming")
                self.status_badge.setStyleSheet(f"""
                    background-color: #22c55e30;
                    color: #22c55e;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 9pt;
                    font-weight: bold;
                """)
            else:
                self.status_badge.setText("Connected")
                self.status_badge.setStyleSheet(f"""
                    background-color: {COLORS["primary"]}30;
                    color: {COLORS["primary"]};
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 9pt;
                    font-weight: bold;
                """)
        else:
            self.status_badge.setText("Disconnected")
            self.status_badge.setStyleSheet(f"""
                background-color: #ef444430;
                color: #ef4444;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 9pt;
                font-weight: bold;
            """)

    def update_afr(self, channel_a: float, channel_b: float) -> None:
        """Update AFR values from external source."""
        self._channel_a = channel_a
        self._channel_b = channel_b

        self.gauge_a.setValue(channel_a)
        self.gauge_b.setValue(channel_b)

        self.afr_updated.emit(channel_a, channel_b)

    def get_values(self) -> Tuple[float, float]:
        """Get current AFR values."""
        return (self._channel_a, self._channel_b)

    def get_target(self) -> float:
        """Get current target AFR."""
        return self._target

    def is_connected(self) -> bool:
        """Check if connected to device."""
        return self._is_connected
