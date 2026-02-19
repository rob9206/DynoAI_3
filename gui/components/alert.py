"""
Alert Component for DynoAI PyQt6 GUI
Styled alert/notification widget
"""

from enum import Enum
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class AlertVariant(Enum):
    """Alert style variants."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class Alert(QFrame):
    """
    A styled alert/notification widget.
    """

    # Shadow Suite semantic colors
    COLORS = {
        AlertVariant.INFO: {
            "bg": "rgba(143, 163, 184, 0.1)",  # ACCENT with alpha
            "border": "rgba(143, 163, 184, 0.2)",
            "icon": "ℹ️",
            "icon_color": "#8FA3B8",  # ACCENT
        },
        AlertVariant.SUCCESS: {
            "bg": "rgba(111, 175, 138, 0.1)",  # OK with alpha
            "border": "rgba(111, 175, 138, 0.2)",
            "icon": "✓",
            "icon_color": "#6FAF8A",  # OK
        },
        AlertVariant.WARNING: {
            "bg": "rgba(199, 168, 106, 0.1)",  # WARN with alpha
            "border": "rgba(199, 168, 106, 0.2)",
            "icon": "⚠️",
            "icon_color": "#C7A86A",  # WARN
        },
        AlertVariant.ERROR: {
            "bg": "rgba(200, 107, 107, 0.1)",  # DANGER with alpha
            "border": "rgba(200, 107, 107, 0.2)",
            "icon": "✕",
            "icon_color": "#C86B6B",  # DANGER
        },
    }

    def __init__(
        self,
        variant: AlertVariant = AlertVariant.INFO,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._variant = variant
        colors = self.COLORS[variant]

        # Styling - minimal rounding for Shadow Suite
        self.setStyleSheet(f"""
            Alert {{
                background-color: {colors["bg"]};
                border: 1px solid {colors["border"]};
                border-radius: 3px;
                padding: 12px;
            }}
        """)

        # Layout
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(12)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Icon
        self.icon_label = QLabel(colors["icon"])
        self.icon_label.setStyleSheet(f"""
            font-size: 14pt;
            color: {colors["icon_color"]};
        """)
        self._layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignTop)

        # Content layout
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(4)
        self._layout.addLayout(self._content_layout, 1)

    def addWidget(self, widget: QWidget) -> None:
        """Add a widget to the alert content."""
        self._content_layout.addWidget(widget)


class AlertTitle(QLabel):
    """
    Alert title label.
    """

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)

        font = self.font()
        font.setPointSize(10)
        font.setWeight(600)
        self.setFont(font)


class AlertDescription(QLabel):
    """
    Alert description label.
    """

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)

        self.setWordWrap(True)
        self.setProperty("class", "muted")


def create_alert(
    variant: AlertVariant,
    title: str,
    description: str = "",
    parent: Optional[QWidget] = None,
) -> Alert:
    """
    Convenience function to create a complete alert with title and description.
    """
    alert = Alert(variant, parent)

    alert_title = AlertTitle(title)
    alert.addWidget(alert_title)

    if description:
        alert_desc = AlertDescription(description)
        alert.addWidget(alert_desc)

    return alert
