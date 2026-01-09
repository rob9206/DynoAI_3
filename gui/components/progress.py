"""
Progress Components for DynoAI PyQt6 GUI
Progress bar and step indicator widgets
"""

from typing import Optional, List, Tuple
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal


class StepStatus(Enum):
    """Step completion status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"


class ProgressWidget(QWidget):
    """
    Progress indicator with message and percentage display.
    Matches the React analysis progress UI.
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Header row (message + percentage)
        header = QHBoxLayout()
        header.setSpacing(8)
        
        self.message_label = QLabel("Initializing...")
        self.message_label.setProperty("class", "muted")
        self.message_label.setStyleSheet("font-weight: 500;")
        header.addWidget(self.message_label)
        
        header.addStretch()
        
        self.percentage_label = QLabel("0%")
        self.percentage_label.setProperty("class", "value")
        self.percentage_label.setStyleSheet("""
            font-weight: 600;
        """)
        header.addWidget(self.percentage_label)
        
        layout.addLayout(header)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(12)
        layout.addWidget(self.progress_bar)
        
    def setProgress(self, value: int, message: str = "") -> None:
        """Update progress value and message."""
        self.progress_bar.setValue(value)
        self.percentage_label.setText(f"{value}%")
        if message:
            self.message_label.setText(message)
            
    def reset(self) -> None:
        """Reset to initial state."""
        self.progress_bar.setValue(0)
        self.percentage_label.setText("0%")
        self.message_label.setText("Initializing...")


class StepIndicator(QFrame):
    """
    A single step indicator (icon + label).
    """
    
    ICONS = {
        StepStatus.PENDING: "○",
        StepStatus.IN_PROGRESS: "◐",
        StepStatus.COMPLETED: "✓",
        StepStatus.ERROR: "✕",
    }
    
    COLORS = {
        StepStatus.PENDING: "#666",
        StepStatus.IN_PROGRESS: "#8FA3B8",  # Shadow Suite ACCENT
        StepStatus.COMPLETED: "#6FAF8A",    # Shadow Suite OK
        StepStatus.ERROR: "#C86B6B",        # Shadow Suite DANGER
    }
    
    def __init__(
        self,
        label: str,
        status: StepStatus = StepStatus.PENDING,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        self._status = status
        self._label_text = label
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Icon
        self.icon_label = QLabel(self.ICONS[status])
        self.icon_label.setStyleSheet(f"""
            font-size: 16pt;
            color: {self.COLORS[status]};
        """)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)
        
        # Label
        self.text_label = QLabel(label)
        self.text_label.setStyleSheet("""
            font-size: 9pt;
            font-weight: 500;
        """)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.text_label)
        
        # Initial styling
        self._update_style()
        
    def setStatus(self, status: StepStatus) -> None:
        """Update the step status."""
        self._status = status
        self.icon_label.setText(self.ICONS[status])
        self._update_style()
        
    def _update_style(self) -> None:
        """Update styling based on status."""
        color = self.COLORS[self._status]
        
        # Update icon color
        self.icon_label.setStyleSheet(f"""
            font-size: 16pt;
            color: {color};
        """)
        
        # Update frame background
        if self._status == StepStatus.PENDING:
            bg = "rgba(100, 100, 100, 0.1)"
            border = "transparent"
        else:
            bg = f"rgba({self._hex_to_rgb(color)}, 0.1)"
            border = f"rgba({self._hex_to_rgb(color)}, 0.2)"
            
        self.setStyleSheet(f"""
            StepIndicator {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """)
        
    @staticmethod
    def _hex_to_rgb(hex_color: str) -> str:
        """Convert hex color to RGB string."""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"{r}, {g}, {b}"


class StepProgressWidget(QWidget):
    """
    Multi-step progress indicator showing Upload, Analysis, Report steps.
    """
    
    def __init__(
        self,
        steps: List[str] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        if steps is None:
            steps = ["Upload", "Analysis", "Report"]
            
        self._steps = steps
        self._indicators: List[StepIndicator] = []
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Create step indicators
        for step_name in steps:
            indicator = StepIndicator(step_name)
            indicator.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._indicators.append(indicator)
            layout.addWidget(indicator)
            
    def setProgress(self, progress: int) -> None:
        """
        Update step indicators based on overall progress.
        0-10: Upload in progress
        10-99: Analysis in progress
        100: All complete
        """
        num_steps = len(self._indicators)
        
        if progress == 0:
            # All pending
            for indicator in self._indicators:
                indicator.setStatus(StepStatus.PENDING)
        elif progress < 10:
            # Upload in progress
            self._indicators[0].setStatus(StepStatus.IN_PROGRESS)
            for indicator in self._indicators[1:]:
                indicator.setStatus(StepStatus.PENDING)
        elif progress < 100:
            # Upload complete, analysis in progress
            self._indicators[0].setStatus(StepStatus.COMPLETED)
            self._indicators[1].setStatus(StepStatus.IN_PROGRESS)
            if len(self._indicators) > 2:
                for indicator in self._indicators[2:]:
                    indicator.setStatus(StepStatus.PENDING)
        else:
            # All complete
            for indicator in self._indicators:
                indicator.setStatus(StepStatus.COMPLETED)
                
    def setError(self, step_index: int = -1) -> None:
        """Mark a step as errored."""
        if 0 <= step_index < len(self._indicators):
            self._indicators[step_index].setStatus(StepStatus.ERROR)
        elif step_index == -1:
            # Mark last non-pending step as error
            for i in range(len(self._indicators) - 1, -1, -1):
                if self._indicators[i]._status != StepStatus.PENDING:
                    self._indicators[i].setStatus(StepStatus.ERROR)
                    break
                    
    def reset(self) -> None:
        """Reset all steps to pending."""
        for indicator in self._indicators:
            indicator.setStatus(StepStatus.PENDING)

