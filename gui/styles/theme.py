"""
DynoAI Shadow Suite Theme
Minimalist, high-contrast industrial precision UI theme for engineering software.
All color tokens and styling rules centralized here.
"""

from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication

# ============================================================================
# DESIGN TOKENS - Shadow Suite
# ============================================================================


class ShadowTokens:
    """Design tokens for Shadow Suite theme - DO NOT MODIFY without approval."""

    # Backgrounds
    BG0 = "#0B0D10"  # Main background
    BG1 = "#0F1216"  # Panel background
    BG2 = "#131820"  # Raised/hover background

    # Structure
    BORDER = "#2A313B"  # Borders, dividers

    # Typography
    TEXT = "#D7DCE3"  # Primary text (off-white)
    MUTED = "#9AA5B1"  # Secondary/muted text

    # Accent (steel - use sparingly)
    ACCENT = "#8FA3B8"  # Primary accent for focus, selection

    # Conditional State Colors (use ONLY for their semantic meaning)
    OK = "#6FAF8A"  # Active/running/armed states only
    WARN = "#C7A86A"  # Warnings, AFR lean context only
    DANGER = "#C86B6B"  # Abort, destructive actions only

    # Typography scale
    FONT_SIZE_BASE = 12  # Base font size (px equivalent)
    FONT_SIZE_SMALL = 10  # Small text
    FONT_SIZE_LARGE = 14  # Large text
    FONT_SIZE_H1 = 20  # Headers
    FONT_SIZE_H2 = 16  # Sub-headers

    # Spacing rhythm (6px base unit)
    SPACING_XS = 6
    SPACING_SM = 12
    SPACING_MD = 18
    SPACING_LG = 24

    # Borders & Radius
    BORDER_WIDTH = 1
    BORDER_RADIUS = 3  # Minimal rounding


# Dictionary for backward compatibility
COLORS = {
    "background": ShadowTokens.BG0,
    "surface": ShadowTokens.BG1,
    "surface_hover": ShadowTokens.BG2,
    "border": ShadowTokens.BORDER,
    "foreground": ShadowTokens.TEXT,
    "text_primary": ShadowTokens.TEXT,
    "text_secondary": ShadowTokens.MUTED,
    "muted_foreground": ShadowTokens.MUTED,
    "primary": ShadowTokens.ACCENT,
    "primary_hover": ShadowTokens.BG2,
    "accent": ShadowTokens.ACCENT,
    "success": ShadowTokens.OK,
    "warning": ShadowTokens.WARN,
    "error": ShadowTokens.DANGER,
    "card": ShadowTokens.BG1,
    "muted": ShadowTokens.BG2,
}

# ============================================================================
# SHADOW SUITE STYLESHEET
# ============================================================================


def build_stylesheet() -> str:
    """
    Build the complete Shadow Suite QSS stylesheet.
    Rules are organized by component type.
    """
    T = ShadowTokens  # Shorthand

    return f"""
    /* ========================================================================
       BASE & LAYOUT
       ======================================================================== */
    
    QMainWindow {{
        background-color: {T.BG0};
    }}
    
    QWidget {{
        background-color: {T.BG0};
        color: {T.TEXT};
        font-family: 'Segoe UI', 'Inter', -apple-system, system-ui, sans-serif;
        font-size: {T.FONT_SIZE_BASE}pt;
    }}
    
    QFrame, QWidget#content_widget {{
        background-color: {T.BG0};
        border: none;
    }}
    
    /* ========================================================================
       CARDS & PANELS
       ======================================================================== */
    
    QFrame[class="card"] {{
        background-color: {T.BG1};
        border: {T.BORDER_WIDTH}px solid {T.BORDER};
        border-radius: {T.BORDER_RADIUS}px;
    }}
    
    QFrame[class="panel"] {{
        background-color: {T.BG1};
        border: {T.BORDER_WIDTH}px solid {T.BORDER};
        border-radius: {T.BORDER_RADIUS}px;
    }}
    
    /* ========================================================================
       TYPOGRAPHY
       ======================================================================== */
    
    QLabel {{
        color: {T.TEXT};
        background-color: transparent;
    }}
    
    /* Section headers - ALL CAPS, letter-spaced, muted */
    QLabel[class="section"] {{
        font-size: {T.FONT_SIZE_SMALL}pt;
        font-weight: 600;
        color: {T.MUTED};
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}
    
    QLabel[class="h1"] {{
        font-size: {T.FONT_SIZE_H1}pt;
        font-weight: 700;
        color: {T.TEXT};
    }}
    
    QLabel[class="h2"] {{
        font-size: {T.FONT_SIZE_H2}pt;
        font-weight: 600;
        color: {T.TEXT};
    }}
    
    QLabel[class="subtitle"] {{
        font-size: {T.FONT_SIZE_LARGE}pt;
        font-weight: 600;
        color: {T.TEXT};
    }}
    
    QLabel[class="muted"] {{
        color: {T.MUTED};
    }}
    
    QLabel[class="description"] {{
        font-size: {T.FONT_SIZE_SMALL}pt;
        color: {T.MUTED};
    }}
    
    /* Value labels - brighter and larger than labels */
    QLabel[class="value"] {{
        font-size: {T.FONT_SIZE_LARGE}pt;
        font-weight: 600;
        color: {T.TEXT};
        font-family: 'Consolas', 'Courier New', monospace;
    }}
    
    /* ========================================================================
       BUTTONS
       ======================================================================== */
    
    /* Default button: neutral, flat, bordered */
    QPushButton {{
        background-color: transparent;
        color: {T.TEXT};
        border: {T.BORDER_WIDTH}px solid {T.BORDER};
        border-radius: {T.BORDER_RADIUS}px;
        padding: 8px 16px;
        font-weight: 500;
        font-size: {T.FONT_SIZE_BASE}pt;
    }}
    
    QPushButton:hover {{
        border-color: {T.ACCENT};
        background-color: {T.BG2};
    }}
    
    QPushButton:pressed {{
        background-color: {T.BG1};
    }}
    
    QPushButton:disabled {{
        color: {T.MUTED};
        border-color: {T.BORDER};
        background-color: transparent;
    }}
    
    /* Primary button: ACCENT border/text, subtle */
    QPushButton[variant="primary"] {{
        background-color: transparent;
        color: {T.ACCENT};
        border: {T.BORDER_WIDTH}px solid {T.ACCENT};
    }}
    
    QPushButton[variant="primary"]:hover {{
        background-color: {T.BG2};
        border-color: {T.ACCENT};
    }}
    
    QPushButton[variant="primary"]:pressed {{
        background-color: {T.BG1};
    }}
    
    QPushButton[variant="primary"]:disabled {{
        color: {T.MUTED};
        border-color: {T.BORDER};
    }}
    
    /* Secondary button: same as default */
    QPushButton[variant="secondary"] {{
        background-color: transparent;
        color: {T.TEXT};
        border: {T.BORDER_WIDTH}px solid {T.BORDER};
    }}
    
    QPushButton[variant="secondary"]:hover {{
        background-color: {T.BG2};
        border-color: {T.ACCENT};
    }}
    
    /* Ghost button: no border */
    QPushButton[variant="ghost"] {{
        background-color: transparent;
        color: {T.TEXT};
        border: none;
    }}
    
    QPushButton[variant="ghost"]:hover {{
        background-color: {T.BG2};
    }}
    
    /* Danger button: DANGER border, only for destructive actions */
    QPushButton[variant="danger"] {{
        background-color: transparent;
        color: {T.DANGER};
        border: {T.BORDER_WIDTH}px solid {T.DANGER};
    }}
    
    QPushButton[variant="danger"]:hover {{
        background-color: rgba(200, 107, 107, 0.1);
        border-color: {T.DANGER};
    }}
    
    QPushButton[variant="danger"]:pressed {{
        background-color: rgba(200, 107, 107, 0.2);
    }}
    
    /* State button: OK color, only when active/running/armed */
    QPushButton[variant="state"] {{
        background-color: transparent;
        color: {T.OK};
        border: {T.BORDER_WIDTH}px solid {T.OK};
    }}
    
    QPushButton[variant="state"]:hover {{
        background-color: rgba(111, 175, 138, 0.1);
        border-color: {T.OK};
    }}
    
    /* ========================================================================
       INPUTS
       ======================================================================== */
    
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {T.BG1};
        color: {T.TEXT};
        border: {T.BORDER_WIDTH}px solid {T.BORDER};
        border-radius: {T.BORDER_RADIUS}px;
        padding: 6px;
    }}
    
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {T.ACCENT};
    }}
    
    QComboBox {{
        background-color: {T.BG1};
        color: {T.TEXT};
        border: {T.BORDER_WIDTH}px solid {T.BORDER};
        border-radius: {T.BORDER_RADIUS}px;
        padding: 6px;
    }}
    
    QComboBox:hover {{
        border-color: {T.ACCENT};
    }}
    
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {T.BG1};
        color: {T.TEXT};
        border: {T.BORDER_WIDTH}px solid {T.BORDER};
        selection-background-color: {T.BG2};
        selection-color: {T.ACCENT};
    }}
    
    /* ========================================================================
       SCROLLBARS
       ======================================================================== */
    
    QScrollBar:vertical {{
        border: none;
        background: {T.BG0};
        width: 10px;
        margin: 0px;
    }}
    
    QScrollBar::handle:vertical {{
        background: {T.BORDER};
        min-height: 20px;
        border-radius: 5px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background: {T.MUTED};
    }}
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}
    
    QScrollBar:horizontal {{
        border: none;
        background: {T.BG0};
        height: 10px;
        margin: 0px;
    }}
    
    QScrollBar::handle:horizontal {{
        background: {T.BORDER};
        min-width: 20px;
        border-radius: 5px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background: {T.MUTED};
    }}
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    
    /* ========================================================================
       SIDEBAR & NAVIGATION
       ======================================================================== */
    
    QWidget[class="sidebar"] {{
        background-color: {T.BG1};
        border-right: {T.BORDER_WIDTH}px solid {T.BORDER};
    }}
    
    /* Nav buttons: subtle, no heavy styling */
    QPushButton[class="nav-item"] {{
        text-align: left;
        padding: 12px 16px;
        background-color: transparent;
        color: {T.MUTED};
        border: none;
        border-radius: {T.BORDER_RADIUS}px;
        margin: 0 8px;
    }}
    
    QPushButton[class="nav-item"]:hover {{
        background-color: {T.BG2};
        color: {T.TEXT};
    }}
    
    QPushButton[class="nav-item"][active="true"] {{
        background-color: {T.BG2};
        color: {T.ACCENT};
        border-left: 2px solid {T.ACCENT};
    }}
    
    /* ========================================================================
       DROP ZONE (File Upload)
       ======================================================================== */
    
    QFrame[class="drop-zone"] {{
        background-color: {T.BG1};
        border: 2px dashed {T.BORDER};
        border-radius: {T.BORDER_RADIUS}px;
    }}
    
    QFrame[class="drop-zone"]:hover {{
        border-color: {T.ACCENT};
        background-color: {T.BG2};
    }}
    
    QFrame[class="drop-zone-active"] {{
        background-color: {T.BG2};
        border: 2px dashed {T.ACCENT};
        border-radius: {T.BORDER_RADIUS}px;
    }}
    
    /* ========================================================================
       PROGRESS BAR
       ======================================================================== */
    
    QProgressBar {{
        border: none;
        background-color: {T.BG2};
        border-radius: 2px;
        text-align: center;
        color: {T.TEXT};
    }}
    
    QProgressBar::chunk {{
        background-color: {T.ACCENT};
        border-radius: 2px;
    }}
    
    /* ========================================================================
       TABLES
       ======================================================================== */
    
    QTableWidget, QTableView {{
        background-color: {T.BG1};
        alternate-background-color: {T.BG0};
        color: {T.TEXT};
        border: {T.BORDER_WIDTH}px solid {T.BORDER};
        gridline-color: {T.BORDER};
        selection-background-color: rgba(143, 163, 184, 0.2);
        selection-color: {T.TEXT};
    }}
    
    QTableWidget::item, QTableView::item {{
        padding: 6px;
    }}
    
    QHeaderView::section {{
        background-color: {T.BG1};
        color: {T.MUTED};
        border: none;
        border-bottom: {T.BORDER_WIDTH}px solid {T.BORDER};
        padding: 8px;
        font-size: {T.FONT_SIZE_SMALL}pt;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}
    
    /* ========================================================================
       TABS
       ======================================================================== */
    
    QTabWidget::pane {{
        border: {T.BORDER_WIDTH}px solid {T.BORDER};
        border-radius: {T.BORDER_RADIUS}px;
        background-color: {T.BG1};
    }}
    
    QTabBar::tab {{
        background-color: transparent;
        color: {T.MUTED};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 8px 16px;
        margin-right: 4px;
    }}
    
    QTabBar::tab:hover {{
        color: {T.TEXT};
        background-color: {T.BG2};
    }}
    
    QTabBar::tab:selected {{
        color: {T.TEXT};
        border-bottom: 2px solid {T.ACCENT};
    }}
    
    /* ========================================================================
       TOOLTIPS
       ======================================================================== */
    
    QToolTip {{
        background-color: {T.BG1};
        color: {T.TEXT};
        border: {T.BORDER_WIDTH}px solid {T.BORDER};
        padding: 4px 8px;
        border-radius: {T.BORDER_RADIUS}px;
    }}
    
    /* ========================================================================
       MESSAGE BOXES
       ======================================================================== */
    
    QMessageBox {{
        background-color: {T.BG1};
    }}
    
    QMessageBox QLabel {{
        color: {T.TEXT};
    }}
    
    QMessageBox QPushButton {{
        min-width: 80px;
    }}
    """


def get_stylesheet() -> str:
    """Get the Shadow Suite stylesheet (for backward compatibility)."""
    return build_stylesheet()


# ============================================================================
# THEME APPLICATION
# ============================================================================


def apply_theme(app: QApplication) -> None:
    """
    Apply the Shadow Suite theme to the application.
    Sets Fusion style, base font, palette, and stylesheet.
    """
    # Use Fusion style for consistent cross-platform appearance
    app.setStyle("Fusion")

    # Set base font
    base_font = QFont("Segoe UI", ShadowTokens.FONT_SIZE_BASE)
    app.setFont(base_font)

    # Set palette for native components and dialogs
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(ShadowTokens.BG0))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(ShadowTokens.TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(ShadowTokens.BG1))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(ShadowTokens.BG2))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(ShadowTokens.BG1))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(ShadowTokens.TEXT))
    palette.setColor(QPalette.ColorRole.Text, QColor(ShadowTokens.TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(ShadowTokens.BG1))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(ShadowTokens.TEXT))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(ShadowTokens.TEXT))
    palette.setColor(QPalette.ColorRole.Link, QColor(ShadowTokens.ACCENT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ShadowTokens.ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(ShadowTokens.BG0))

    app.setPalette(palette)

    # Apply stylesheet
    app.setStyleSheet(build_stylesheet())


# Alias for backward compatibility
def apply_dark_theme(app: QApplication) -> None:
    """Backward compatibility alias for apply_theme."""
    apply_theme(app)


# Export tokens for direct access if needed
class Colors:
    """Backward compatibility class."""

    BACKGROUND = ShadowTokens.BG0
    SURFACE = ShadowTokens.BG1
    SURFACE_HOVER = ShadowTokens.BG2
    TEXT_PRIMARY = ShadowTokens.TEXT
    TEXT_SECONDARY = ShadowTokens.MUTED
    TEXT_MUTED = ShadowTokens.MUTED
    PRIMARY = ShadowTokens.ACCENT
    PRIMARY_HOVER = ShadowTokens.BG2
    ACCENT = ShadowTokens.ACCENT
    SUCCESS = ShadowTokens.OK
    ERROR = ShadowTokens.DANGER
    WARNING = ShadowTokens.WARN
    BORDER = ShadowTokens.BORDER
