"""
Card Component for DynoAI PyQt6 GUI
Styled card container matching the React shadcn/ui card component
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy
)

class Card(QFrame):
    """
    A styled card container widget.
    Provides a bordered, rounded container for content.
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setProperty("class", "card")
        
        # Main layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        
        # Size policy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
    def addWidget(self, widget: QWidget) -> None:
        """Add a widget to the card."""
        self._layout.addWidget(widget)
        
    def addLayout(self, layout) -> None:
        """Add a layout to the card."""
        self._layout.addLayout(layout)
        
    def setSpacing(self, spacing: int) -> None:
        """Set spacing between card sections."""
        self._layout.setSpacing(spacing)


class CardHeader(QFrame):
    """
    Card header section with title and optional description.
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 16)
        self._layout.setSpacing(4)
        
    def addWidget(self, widget: QWidget) -> None:
        """Add a widget to the header."""
        self._layout.addWidget(widget)
        

class CardContent(QFrame):
    """
    Card content section.
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 0, 24, 24)
        self._layout.setSpacing(16)
        
    def addWidget(self, widget: QWidget) -> None:
        """Add a widget to the content area."""
        self._layout.addWidget(widget)
        
    def addLayout(self, layout) -> None:
        """Add a layout to the content area."""
        self._layout.addLayout(layout)
        
    def setSpacing(self, spacing: int) -> None:
        """Set spacing between content items."""
        self._layout.setSpacing(spacing)


class CardTitle(QLabel):
    """
    Card title label with icon support.
    """
    
    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setProperty("class", "subtitle")
        
        # Style
        font = self.font()
        font.setPointSize(12)
        font.setWeight(600)
        self.setFont(font)
        
    def setIcon(self, icon_text: str) -> None:
        """Set an icon (emoji or text) before the title."""
        current_text = self.text()
        # Remove existing icon if present
        if current_text and current_text[0] not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz':
            current_text = current_text.split(' ', 1)[-1] if ' ' in current_text else current_text
        self.setText(f"{icon_text} {current_text}")


class CardDescription(QLabel):
    """
    Card description label for secondary text.
    """
    
    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setProperty("class", "description")
        self.setWordWrap(True)
        
        # Style
        font = self.font()
        font.setPointSize(9)
        self.setFont(font)


class CardWithHeader(Card):
    """
    Convenience class for a card with header, title, and content areas.
    """
    
    def __init__(
        self,
        title: str = "",
        description: str = "",
        icon: str = "",
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        # Header
        self.header = CardHeader()
        
        # Title row (icon + title)
        self.title_layout = QHBoxLayout()
        self.title_layout.setContentsMargins(0, 0, 0, 0)
        self.title_layout.setSpacing(8)
        
        # Icon label (if provided)
        if icon:
            self.icon_label = QLabel(icon)
            self.icon_label.setStyleSheet("font-size: 16pt;")
            self.title_layout.addWidget(self.icon_label)
        
        # Title
        self.title_label = CardTitle(title)
        self.title_layout.addWidget(self.title_label)
        self.title_layout.addStretch()
        
        title_widget = QWidget()
        title_widget.setLayout(self.title_layout)
        self.header.addWidget(title_widget)
        
        # Description
        if description:
            self.description_label = CardDescription(description)
            self.header.addWidget(self.description_label)
        
        self.addWidget(self.header)
        
        # Content area
        self.content = CardContent()
        self.addWidget(self.content)
        
    def addContentWidget(self, widget: QWidget) -> None:
        """Add a widget to the card's content area."""
        self.content.addWidget(widget)
        
    def addContentLayout(self, layout) -> None:
        """Add a layout to the card's content area."""
        self.content.addLayout(layout)
