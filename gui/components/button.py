"""
Button Components for DynoAI PyQt6 GUI
Styled button widgets matching the React shadcn/ui button component
"""

from enum import Enum
from typing import Callable, Optional

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QCursor, QIcon
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class ButtonVariant(Enum):
    """Button style variants matching Shadow Suite theme."""

    DEFAULT = "default"  # Neutral bordered
    PRIMARY = "primary"  # ACCENT bordered (use sparingly)
    SECONDARY = "secondary"  # Same as default
    GHOST = "ghost"  # No border
    DANGER = "danger"  # DANGER bordered (destructive only)
    STATE = "state"  # OK bordered (active/running only)


class ButtonSize(Enum):
    """Button size variants."""

    DEFAULT = "default"
    SMALL = "small"
    LARGE = "large"
    ICON = "icon"


class Button(QPushButton):
    """
    Styled button widget with variant support.
    """

    def __init__(
        self,
        text: str = "",
        variant: ButtonVariant = ButtonVariant.DEFAULT,
        size: ButtonSize = ButtonSize.DEFAULT,
        icon: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)

        self._variant = variant
        self._size = size

        # Apply variant as property for Shadow Suite theme
        self.setProperty("variant", variant.value)

        # Apply size styling
        self._apply_size()

        # Set icon if provided (emoji)
        if icon:
            self.setText(f"{icon}  {text}" if text else icon)

        # Cursor
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def _apply_size(self) -> None:
        """Apply size-specific styling."""
        if self._size == ButtonSize.SMALL:
            self.setMinimumHeight(28)
            font = self.font()
            font.setPointSize(9)
            self.setFont(font)
            self.setStyleSheet(self.styleSheet() + "padding: 4px 12px;")
        elif self._size == ButtonSize.LARGE:
            self.setMinimumHeight(44)
            font = self.font()
            font.setPointSize(12)
            self.setFont(font)
            self.setStyleSheet(self.styleSheet() + "padding: 12px 24px;")
        elif self._size == ButtonSize.ICON:
            self.setFixedSize(36, 36)
            self.setStyleSheet(self.styleSheet() + "padding: 0px;")
        else:
            self.setMinimumHeight(36)

    def setVariant(self, variant: ButtonVariant) -> None:
        """Change the button variant."""
        self._variant = variant
        self.setProperty("variant", variant.value)
        self.style().unpolish(self)
        self.style().polish(self)


class IconButton(QPushButton):
    """
    Icon-only button widget.
    """

    def __init__(
        self,
        icon: str,
        tooltip: str = "",
        variant: ButtonVariant = ButtonVariant.GHOST,
        size: int = 36,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(icon, parent)

        self.setProperty("variant", variant.value)
        self.setFixedSize(size, size)
        self.setToolTip(tooltip)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Center the icon
        font = self.font()
        font.setPointSize(12)
        self.setFont(font)


class ActionButton(QPushButton):
    """
    Large action button with icon and text, used for primary actions.
    Default to primary variant for Shadow Suite theme.
    """

    def __init__(
        self,
        text: str,
        icon: str = "",
        variant: ButtonVariant = ButtonVariant.PRIMARY,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        # Set variant
        self.setProperty("variant", variant.value)

        # Layout for icon + text
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        # Set text with icon
        if icon:
            self.setText(f"{icon}  {text}")
        else:
            self.setText(text)

        # Styling
        self.setMinimumHeight(56)
        font = self.font()
        font.setPointSize(13)
        font.setWeight(600)
        self.setFont(font)

        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
