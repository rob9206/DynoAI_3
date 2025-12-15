"""
PDF Report Template Configuration

This module defines the layout, styles, and formatting for DynoAI PDF reports.
The template is designed to create professional, branded reports suitable for
customer delivery and insurance documentation.
"""

from typing import Dict, Any

# Page layout constants (in points, 1 inch = 72 points)
PAGE_WIDTH = 612  # 8.5 inches
PAGE_HEIGHT = 792  # 11 inches
MARGIN_LEFT = 72  # 1 inch
MARGIN_RIGHT = 72  # 1 inch
MARGIN_TOP = 72  # 1 inch
MARGIN_BOTTOM = 72  # 1 inch

# Content area
CONTENT_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
CONTENT_HEIGHT = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

# Colors (RGB tuples)
COLOR_PRIMARY = (0.1, 0.2, 0.4)  # Dark blue for headers
COLOR_SECONDARY = (0.4, 0.5, 0.6)  # Medium gray for subheadings
COLOR_TEXT = (0.0, 0.0, 0.0)  # Black for body text
COLOR_ACCENT = (0.8, 0.3, 0.1)  # Orange for warnings/highlights
COLOR_SUCCESS = (0.2, 0.6, 0.2)  # Green for positive indicators
COLOR_WARNING = (0.9, 0.6, 0.0)  # Amber for warnings

# Font sizes
FONT_SIZE_TITLE = 20
FONT_SIZE_HEADING = 16
FONT_SIZE_SUBHEADING = 12
FONT_SIZE_BODY = 10
FONT_SIZE_SMALL = 8
FONT_SIZE_FOOTER = 8

# Spacing
LINE_SPACING = 14
SECTION_SPACING = 20
PARAGRAPH_SPACING = 10

# Table styling
TABLE_HEADER_COLOR = (0.9, 0.9, 0.9)  # Light gray
TABLE_BORDER_COLOR = (0.5, 0.5, 0.5)  # Medium gray
TABLE_ROW_ALT_COLOR = (0.97, 0.97, 0.97)  # Very light gray

# Default disclaimer text (can be overridden)
DEFAULT_DISCLAIMER = """
DISCLAIMER: This report is generated based on dyno data analysis and represents
suggested VE table corrections and spark advance adjustments. All recommendations
should be validated and tested incrementally. The operator assumes all responsibility
for implementing these changes. Always monitor for knock, excessive heat, and improper
air-fuel ratios when testing modifications. This analysis is provided for professional
tuning purposes only.
"""

# Default shop info (can be overridden via config)
DEFAULT_SHOP_INFO: Dict[str, Any] = {
    "name": "DynoAI Tuning",
    "address": "",
    "phone": "",
    "email": "",
    "website": "https://github.com/rob9206/DynoAI_3",
    "logo_path": None,  # Path to logo image file if available
}


def get_confidence_color(score: float) -> tuple:
    """
    Get color based on confidence score.
    
    Args:
        score: Confidence score (0-100)
        
    Returns:
        RGB color tuple
    """
    if score >= 90:
        return COLOR_SUCCESS
    elif score >= 75:
        return (0.5, 0.7, 0.3)  # Yellow-green
    elif score >= 60:
        return COLOR_WARNING
    else:
        return COLOR_ACCENT


def get_grade_color(grade: str) -> tuple:
    """
    Get color based on letter grade.
    
    Args:
        grade: Letter grade (A+, A, B+, B, C+, C, D, F)
        
    Returns:
        RGB color tuple
    """
    if grade.startswith('A'):
        return COLOR_SUCCESS
    elif grade.startswith('B'):
        return (0.5, 0.7, 0.3)
    elif grade.startswith('C'):
        return COLOR_WARNING
    else:
        return COLOR_ACCENT
