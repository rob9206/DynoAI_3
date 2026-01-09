"""
VE Heatmap Widget for DynoAI PyQt6 GUI
Interactive heatmap visualization using pyqtgraph
"""

from typing import List, Optional

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

try:
    import pyqtgraph as pg
    from pyqtgraph import ColorMap

    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

from gui.api.client import VEData
from gui.styles.theme import COLORS


class VEHeatmapWidget(QWidget):
    """
    VE Table heatmap visualization widget.
    Displays before/after/diff views of VE corrections.
    """

    # Signals
    cell_hovered = pyqtSignal(int, int, float)  # rpm_idx, load_idx, value
    cell_clicked = pyqtSignal(int, int)  # rpm_idx, load_idx

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._ve_data: Optional[VEData] = None
        self._view_mode = "after"  # before, after, diff

        # Build UI
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the heatmap UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        if not HAS_PYQTGRAPH:
            # Fallback when pyqtgraph not available
            fallback = QLabel(
                "pyqtgraph not installed.\nInstall with: pip install pyqtgraph"
            )
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fallback.setStyleSheet(
                f"color: {COLORS['muted_foreground']}; padding: 48px;"
            )
            layout.addWidget(fallback)
            return

        # Configure pyqtgraph
        pg.setConfigOptions(
            antialias=True, background=COLORS["card"], foreground=COLORS["foreground"]
        )

        # Create plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setMinimumHeight(350)

        # Configure axes
        self.plot_widget.setLabel("bottom", "RPM")
        self.plot_widget.setLabel("left", "Load (kPa)")

        # Create image item for heatmap
        self.heatmap_item = pg.ImageItem()
        self.plot_widget.addItem(self.heatmap_item)

        # Create colormap (blue-white-red for diff, viridis for values)
        self._diff_colormap = self._create_diff_colormap()
        self._value_colormap = self._create_value_colormap()

        # Color bar
        self.colorbar = pg.ColorBarItem(
            values=(0, 100), colorMap=self._value_colormap, orientation="right"
        )
        self.colorbar.setImageItem(self.heatmap_item)

        layout.addWidget(self.plot_widget)

        # Info bar
        info_bar = QHBoxLayout()
        info_bar.setSpacing(16)

        self.hover_info = QLabel("Hover over cells for details")
        self.hover_info.setStyleSheet(
            f"color: {COLORS['muted_foreground']}; font-size: 9pt;"
        )
        info_bar.addWidget(self.hover_info)

        info_bar.addStretch()

        # Stats
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            f"color: {COLORS['muted_foreground']}; font-size: 9pt;"
        )
        info_bar.addWidget(self.stats_label)

        layout.addLayout(info_bar)

        # Connect mouse events
        self.heatmap_item.hoverEvent = self._on_hover

    def _create_diff_colormap(self) -> "ColorMap":
        """Create blue-white-red colormap for diff view."""
        if not HAS_PYQTGRAPH:
            return None

        positions = [0.0, 0.5, 1.0]
        colors = [
            (59, 130, 246, 255),  # Blue (negative)
            (255, 255, 255, 255),  # White (zero)
            (239, 68, 68, 255),  # Red (positive)
        ]
        return ColorMap(positions, colors)

    def _create_value_colormap(self) -> "ColorMap":
        """Create colormap for absolute values."""
        if not HAS_PYQTGRAPH:
            return None

        # Custom colormap similar to viridis but with DynoAI theme colors
        positions = [0.0, 0.25, 0.5, 0.75, 1.0]
        colors = [
            (26, 29, 46, 255),  # Dark blue (low)
            (59, 130, 246, 255),  # Blue
            (34, 197, 94, 255),  # Green
            (245, 158, 11, 255),  # Orange
            (239, 68, 68, 255),  # Red (high)
        ]
        return ColorMap(positions, colors)

    def set_data(self, ve_data: VEData) -> None:
        """Set the VE data to display."""
        self._ve_data = ve_data
        self._update_display()

    def set_view_mode(self, mode: str) -> None:
        """Set the view mode: before, after, or diff."""
        if mode in ("before", "after", "diff"):
            self._view_mode = mode
            self._update_display()

    def _update_display(self) -> None:
        """Update the heatmap display."""
        if not HAS_PYQTGRAPH or not self._ve_data:
            return

        # Get data based on view mode
        if self._view_mode == "before":
            data = np.array(self._ve_data.before) if self._ve_data.before else None
            colormap = self._value_colormap
            title = "VE Table (Before)"
        elif self._view_mode == "after":
            data = np.array(self._ve_data.after) if self._ve_data.after else None
            colormap = self._value_colormap
            title = "VE Table (After)"
        else:  # diff
            if self._ve_data.before and self._ve_data.after:
                before = np.array(self._ve_data.before)
                after = np.array(self._ve_data.after)
                data = after - before
                colormap = self._diff_colormap
                title = "VE Corrections (Diff)"
            else:
                data = None
                colormap = self._diff_colormap
                title = "VE Corrections (Diff)"

        if data is None:
            return

        # Transpose for correct orientation (RPM on x, Load on y)
        data = data.T

        # Set image data
        self.heatmap_item.setImage(data)

        # Set colormap
        self.heatmap_item.setColorMap(colormap)

        # Set axis scales based on actual RPM/Load values
        if self._ve_data.rpm and self._ve_data.load:
            rpm = self._ve_data.rpm
            load = self._ve_data.load

            # Calculate scales
            rpm_scale = (rpm[-1] - rpm[0]) / len(rpm) if len(rpm) > 1 else 1
            load_scale = (load[-1] - load[0]) / len(load) if len(load) > 1 else 1

            # Set transform
            self.heatmap_item.setRect(
                rpm[0], load[0], rpm[-1] - rpm[0], load[-1] - load[0]
            )

        # Update colorbar range
        if self._view_mode == "diff":
            max_abs = max(abs(data.min()), abs(data.max()), 1)
            self.colorbar.setLevels((-max_abs, max_abs))
        else:
            self.colorbar.setLevels((data.min(), data.max()))

        # Update stats
        self._update_stats(data)

    def _update_stats(self, data: np.ndarray) -> None:
        """Update statistics display."""
        if data is None:
            self.stats_label.setText("")
            return

        min_val = data.min()
        max_val = data.max()
        avg_val = data.mean()

        if self._view_mode == "diff":
            self.stats_label.setText(
                f"Min: {min_val:+.2f}%  |  Max: {max_val:+.2f}%  |  Avg: {avg_val:+.2f}%"
            )
        else:
            self.stats_label.setText(
                f"Min: {min_val:.1f}  |  Max: {max_val:.1f}  |  Avg: {avg_val:.1f}"
            )

    def _on_hover(self, event) -> None:
        """Handle mouse hover over heatmap."""
        if not HAS_PYQTGRAPH or not self._ve_data:
            return

        if event.isExit():
            self.hover_info.setText("Hover over cells for details")
            return

        # Get position
        pos = event.pos()

        # Map to data coordinates
        if self._ve_data.rpm and self._ve_data.load:
            rpm = self._ve_data.rpm
            load = self._ve_data.load

            # Find nearest cell
            rpm_idx = min(range(len(rpm)), key=lambda i: abs(rpm[i] - pos.x()))
            load_idx = min(range(len(load)), key=lambda i: abs(load[i] - pos.y()))

            # Get value
            if self._view_mode == "before" and self._ve_data.before:
                value = self._ve_data.before[load_idx][rpm_idx]
                self.hover_info.setText(
                    f"RPM: {rpm[rpm_idx]:.0f}  |  Load: {load[load_idx]:.0f} kPa  |  VE: {value:.1f}"
                )
            elif self._view_mode == "after" and self._ve_data.after:
                value = self._ve_data.after[load_idx][rpm_idx]
                self.hover_info.setText(
                    f"RPM: {rpm[rpm_idx]:.0f}  |  Load: {load[load_idx]:.0f} kPa  |  VE: {value:.1f}"
                )
            elif (
                self._view_mode == "diff"
                and self._ve_data.before
                and self._ve_data.after
            ):
                before_val = self._ve_data.before[load_idx][rpm_idx]
                after_val = self._ve_data.after[load_idx][rpm_idx]
                diff = after_val - before_val
                self.hover_info.setText(
                    f"RPM: {rpm[rpm_idx]:.0f}  |  Load: {load[load_idx]:.0f} kPa  |  "
                    f"Before: {before_val:.1f}  →  After: {after_val:.1f}  ({diff:+.2f}%)"
                )

            # Emit signal
            self.cell_hovered.emit(rpm_idx, load_idx, 0)


class VEHeatmapFallback(QWidget):
    """
    Fallback heatmap widget using basic Qt painting.
    Used when pyqtgraph is not available.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._ve_data: Optional[VEData] = None
        self._view_mode = "after"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Simple text display
        self.info_label = QLabel("VE Data will be displayed here")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet(f"""
            color: {COLORS["muted_foreground"]};
            padding: 48px;
            background-color: {COLORS["muted"]};
            border-radius: 8px;
        """)
        layout.addWidget(self.info_label)

    def set_data(self, ve_data: VEData) -> None:
        """Set the VE data to display."""
        self._ve_data = ve_data
        self._update_display()

    def set_view_mode(self, mode: str) -> None:
        """Set the view mode."""
        self._view_mode = mode
        self._update_display()

    def _update_display(self) -> None:
        """Update the display."""
        if not self._ve_data:
            self.info_label.setText("No VE data loaded")
            return

        rpm_count = len(self._ve_data.rpm) if self._ve_data.rpm else 0
        load_count = len(self._ve_data.load) if self._ve_data.load else 0

        # Calculate basic stats
        if self._view_mode == "diff" and self._ve_data.before and self._ve_data.after:
            before = np.array(self._ve_data.before)
            after = np.array(self._ve_data.after)
            diff = after - before

            self.info_label.setText(
                f"VE Corrections\n\n"
                f"Grid: {rpm_count} RPM × {load_count} Load points\n"
                f"Min Change: {diff.min():+.2f}%\n"
                f"Max Change: {diff.max():+.2f}%\n"
                f"Avg Change: {diff.mean():+.2f}%\n\n"
                f"Install pyqtgraph for interactive heatmap visualization"
            )
        elif self._view_mode == "after" and self._ve_data.after:
            after = np.array(self._ve_data.after)

            self.info_label.setText(
                f"VE Table (After Corrections)\n\n"
                f"Grid: {rpm_count} RPM × {load_count} Load points\n"
                f"Min VE: {after.min():.1f}\n"
                f"Max VE: {after.max():.1f}\n"
                f"Avg VE: {after.mean():.1f}\n\n"
                f"Install pyqtgraph for interactive heatmap visualization"
            )
        elif self._view_mode == "before" and self._ve_data.before:
            before = np.array(self._ve_data.before)

            self.info_label.setText(
                f"VE Table (Before Corrections)\n\n"
                f"Grid: {rpm_count} RPM × {load_count} Load points\n"
                f"Min VE: {before.min():.1f}\n"
                f"Max VE: {before.max():.1f}\n"
                f"Avg VE: {before.mean():.1f}\n\n"
                f"Install pyqtgraph for interactive heatmap visualization"
            )
