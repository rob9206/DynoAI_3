#!/usr/bin/env python3
"""
Shadow Suite Theme Visual Test
Displays all components in the Shadow Suite theme for visual verification.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt

from gui.styles.theme import apply_theme, ShadowTokens
from gui.components.card import Card, CardHeader, CardContent, CardTitle, CardDescription
from gui.components.button import Button, ButtonVariant, ButtonSize, ActionButton
from gui.components.progress import ProgressWidget, StepProgressWidget
from gui.components.alert import create_alert, AlertVariant
from gui.components.slider import LabeledSlider
from gui.components.switch import LabeledSwitch


class ThemeShowcase(QMainWindow):
    """Visual showcase of Shadow Suite theme components."""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Shadow Suite Theme - Visual Test")
        self.setMinimumSize(1200, 900)
        
        # Main scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        # Content widget
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)
        
        # =====================================================================
        # Header
        # =====================================================================
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setSpacing(4)
        
        title = QLabel("Shadow Suite Theme")
        title.setProperty("class", "h1")
        header_layout.addWidget(title)
        
        subtitle = QLabel("Minimalist, high-contrast, industrial precision UI")
        subtitle.setProperty("class", "muted")
        header_layout.addWidget(subtitle)
        
        layout.addWidget(header)
        
        # =====================================================================
        # Color Tokens Card
        # =====================================================================
        colors_card = Card()
        
        colors_header = CardHeader()
        colors_title = CardTitle("Design Tokens")
        colors_header.addWidget(colors_title)
        colors_desc = CardDescription("Shadow Suite color palette")
        colors_header.addWidget(colors_desc)
        colors_card.addWidget(colors_header)
        
        colors_content = CardContent()
        colors_grid = QHBoxLayout()
        colors_grid.setSpacing(12)
        
        tokens = [
            ("BG0", ShadowTokens.BG0, "Main background"),
            ("BG1", ShadowTokens.BG1, "Panel"),
            ("BG2", ShadowTokens.BG2, "Hover"),
            ("BORDER", ShadowTokens.BORDER, "Borders"),
            ("TEXT", ShadowTokens.TEXT, "Primary text"),
            ("MUTED", ShadowTokens.MUTED, "Muted text"),
            ("ACCENT", ShadowTokens.ACCENT, "Accent"),
            ("OK", ShadowTokens.OK, "Active"),
            ("WARN", ShadowTokens.WARN, "Warning"),
            ("DANGER", ShadowTokens.DANGER, "Danger"),
        ]
        
        for name, color, desc in tokens:
            token_widget = QFrame()
            token_widget.setProperty("class", "panel")
            token_layout = QVBoxLayout(token_widget)
            token_layout.setContentsMargins(12, 12, 12, 12)
            token_layout.setSpacing(4)
            
            color_box = QLabel()
            color_box.setFixedSize(60, 40)
            color_box.setStyleSheet(f"background-color: {color}; border: 1px solid {ShadowTokens.BORDER};")
            token_layout.addWidget(color_box, alignment=Qt.AlignmentFlag.AlignCenter)
            
            name_label = QLabel(name)
            name_label.setProperty("class", "section")
            name_label.setStyleSheet("font-size: 8pt;")
            token_layout.addWidget(name_label, alignment=Qt.AlignmentFlag.AlignCenter)
            
            desc_label = QLabel(desc)
            desc_label.setProperty("class", "muted")
            desc_label.setStyleSheet("font-size: 7pt;")
            token_layout.addWidget(desc_label, alignment=Qt.AlignmentFlag.AlignCenter)
            
            colors_grid.addWidget(token_widget)
        
        colors_content.addLayout(colors_grid)
        colors_card.addWidget(colors_content)
        layout.addWidget(colors_card)
        
        # =====================================================================
        # Buttons Card
        # =====================================================================
        buttons_card = Card()
        
        buttons_header = CardHeader()
        buttons_title = CardTitle("Buttons")
        buttons_header.addWidget(buttons_title)
        buttons_desc = CardDescription("All button variants with proper semantic usage")
        buttons_header.addWidget(buttons_desc)
        buttons_card.addWidget(buttons_header)
        
        buttons_content = CardContent()
        
        # Button rows
        default_row = QHBoxLayout()
        default_row.setSpacing(12)
        default_row.addWidget(QLabel("Default:"))
        default_row.addWidget(Button("Neutral", ButtonVariant.DEFAULT))
        default_row.addWidget(Button("Disabled", ButtonVariant.DEFAULT))
        default_row.children()[-1].setEnabled(False)
        default_row.addStretch()
        buttons_content.addLayout(default_row)
        
        primary_row = QHBoxLayout()
        primary_row.setSpacing(12)
        primary_row.addWidget(QLabel("Primary:"))
        primary_row.addWidget(Button("Accent Border", ButtonVariant.PRIMARY))
        primary_row.addStretch()
        buttons_content.addLayout(primary_row)
        
        state_row = QHBoxLayout()
        state_row.setSpacing(12)
        state_row.addWidget(QLabel("State (active):"))
        btn_state = Button("Running", ButtonVariant.DEFAULT)
        btn_state.setProperty("variant", "state")
        btn_state.style().polish(btn_state)
        state_row.addWidget(btn_state)
        state_row.addStretch()
        buttons_content.addLayout(state_row)
        
        danger_row = QHBoxLayout()
        danger_row.setSpacing(12)
        danger_row.addWidget(QLabel("Danger:"))
        danger_row.addWidget(Button("Abort", ButtonVariant.DANGER))
        danger_row.addStretch()
        buttons_content.addLayout(danger_row)
        
        ghost_row = QHBoxLayout()
        ghost_row.setSpacing(12)
        ghost_row.addWidget(QLabel("Ghost:"))
        ghost_row.addWidget(Button("Borderless", ButtonVariant.GHOST))
        ghost_row.addStretch()
        buttons_content.addLayout(ghost_row)
        
        action_row = QHBoxLayout()
        action_row.setSpacing(12)
        action_row.addWidget(QLabel("Action:"))
        action_row.addWidget(ActionButton("Start Analysis", "▶️"))
        action_row.addStretch()
        buttons_content.addLayout(action_row)
        
        buttons_card.addWidget(buttons_content)
        layout.addWidget(buttons_card)
        
        # =====================================================================
        # Progress Card
        # =====================================================================
        progress_card = Card()
        
        progress_header = CardHeader()
        progress_title = CardTitle("Progress Indicators")
        progress_header.addWidget(progress_title)
        progress_card.addWidget(progress_header)
        
        progress_content = CardContent()
        
        prog_widget = ProgressWidget()
        prog_widget.setProgress(65, "Analyzing VE tables...")
        progress_content.addWidget(prog_widget)
        
        step_widget = StepProgressWidget()
        step_widget.setProgress(65)
        progress_content.addWidget(step_widget)
        
        progress_card.addWidget(progress_content)
        layout.addWidget(progress_card)
        
        # =====================================================================
        # Alerts Card
        # =====================================================================
        alerts_card = Card()
        
        alerts_header = CardHeader()
        alerts_title = CardTitle("Alerts")
        alerts_header.addWidget(alerts_title)
        alerts_card.addWidget(alerts_header)
        
        alerts_content = CardContent()
        
        alerts_content.addWidget(create_alert(
            AlertVariant.INFO,
            "Information",
            "This is an informational message using the ACCENT color."
        ))
        
        alerts_content.addWidget(create_alert(
            AlertVariant.SUCCESS,
            "Success",
            "Operation completed successfully using the OK color."
        ))
        
        alerts_content.addWidget(create_alert(
            AlertVariant.WARNING,
            "Warning",
            "Caution: AFR lean condition detected using WARN color."
        ))
        
        alerts_content.addWidget(create_alert(
            AlertVariant.ERROR,
            "Error",
            "Operation failed. Abort signal using DANGER color."
        ))
        
        alerts_card.addWidget(alerts_content)
        layout.addWidget(alerts_card)
        
        # =====================================================================
        # Controls Card
        # =====================================================================
        controls_card = Card()
        
        controls_header = CardHeader()
        controls_title = CardTitle("Controls")
        controls_header.addWidget(controls_title)
        controls_card.addWidget(controls_header)
        
        controls_content = CardContent()
        
        slider = LabeledSlider(
            label="Smoothing Intensity",
            min_val=0,
            max_val=5,
            default_val=3,
            step=1,
            suffix=" passes",
            description="Higher values blend adjacent cells more aggressively."
        )
        controls_content.addWidget(slider)
        
        switch = LabeledSwitch(
            label="Decel Fuel Management",
            description="Automatically eliminate exhaust popping during deceleration"
        )
        controls_content.addWidget(switch)
        
        controls_card.addWidget(controls_content)
        layout.addWidget(controls_card)
        
        # =====================================================================
        # Typography Card
        # =====================================================================
        typo_card = Card()
        
        typo_header = CardHeader()
        typo_title = CardTitle("Typography")
        typo_header.addWidget(typo_title)
        typo_card.addWidget(typo_header)
        
        typo_content = CardContent()
        
        h1 = QLabel("Heading 1")
        h1.setProperty("class", "h1")
        typo_content.addWidget(h1)
        
        h2 = QLabel("Heading 2")
        h2.setProperty("class", "h2")
        typo_content.addWidget(h2)
        
        section = QLabel("SECTION HEADER")
        section.setProperty("class", "section")
        typo_content.addWidget(section)
        
        body = QLabel("Body text - regular paragraph text appears like this.")
        typo_content.addWidget(body)
        
        muted = QLabel("Muted text - secondary information appears muted.")
        muted.setProperty("class", "muted")
        typo_content.addWidget(muted)
        
        value = QLabel("145.3 HP")
        value.setProperty("class", "value")
        typo_content.addWidget(value)
        
        typo_card.addWidget(typo_content)
        layout.addWidget(typo_card)
        
        layout.addStretch()
        
        # Set content
        scroll.setWidget(content)
        self.setCentralWidget(scroll)


def main():
    """Run the theme showcase."""
    app = QApplication(sys.argv)
    app.setApplicationName("Shadow Suite Theme Test")
    
    # Apply Shadow Suite theme
    apply_theme(app)
    
    # Show showcase
    window = ThemeShowcase()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

