"""
Live VE Table Widget for DynoAI PyQt6 GUI
Real-time VE table with cell tracing and highlighting
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.styles.theme import COLORS


class EnginePreset(Enum):
    """Engine type presets."""

    HARLEY_M8 = "harley_m8"
    HARLEY_TC = "harley_tc"
    SPORTBIKE_600 = "sportbike_600"
    SPORTBIKE_1000 = "sportbike_1000"
    CUSTOM = "custom"


@dataclass
class EngineConfig:
    """Configuration for engine type."""

    name: str
    rpm_bins: List[int]
    map_bins: List[int]
    max_rpm: int


# Engine presets
ENGINE_PRESETS = {
    EnginePreset.HARLEY_M8: EngineConfig(
        name="Harley M8",
        rpm_bins=[
            1000,
            1500,
            2000,
            2500,
            3000,
            3500,
            4000,
            4500,
            5000,
            5500,
            6000,
            6500,
        ],
        map_bins=[20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        max_rpm=6500,
    ),
    EnginePreset.HARLEY_TC: EngineConfig(
        name="Harley Twin Cam",
        rpm_bins=[1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000],
        map_bins=[20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        max_rpm=6000,
    ),
    EnginePreset.SPORTBIKE_600: EngineConfig(
        name="Sportbike 600cc",
        rpm_bins=[
            2000,
            3000,
            4000,
            5000,
            6000,
            7000,
            8000,
            9000,
            10000,
            11000,
            12000,
            13000,
            14000,
            15000,
        ],
        map_bins=[20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        max_rpm=15000,
    ),
    EnginePreset.SPORTBIKE_1000: EngineConfig(
        name="Sportbike 1000cc",
        rpm_bins=[
            2000,
            3000,
            4000,
            5000,
            6000,
            7000,
            8000,
            9000,
            10000,
            11000,
            12000,
            13000,
        ],
        map_bins=[20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        max_rpm=13000,
    ),
    EnginePreset.CUSTOM: EngineConfig(
        name="Custom",
        rpm_bins=[1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000],
        map_bins=[20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        max_rpm=10000,
    ),
}


class LiveVETable(QWidget):
    """
    Live VE table with cell tracing.
    Shows current cell highlighted based on live RPM/MAP.
    """

    # Signals
    cell_clicked = pyqtSignal(int, int)  # rpm_idx, map_idx
    preset_changed = pyqtSignal(str)  # preset name

    # Colors
    COLOR_LEAN = QColor("#ef4444")  # Red
    COLOR_RICH = QColor("#3b82f6")  # Blue
    COLOR_OK = QColor("#22c55e")  # Green
    COLOR_ACTIVE = QColor("#f59e0b")  # Orange/amber
    COLOR_HOVER = QColor("#4a7dff")  # Primary blue

    def __init__(
        self,
        preset: EnginePreset = EnginePreset.HARLEY_M8,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._preset = preset
        self._config = ENGINE_PRESETS[preset]
        self._current_rpm = 0
        self._current_map = 0
        self._current_afr = 14.7
        self._target_afr = 14.7
        self._is_live = False

        # VE data (corrections)
        self._ve_data: List[List[float]] = []
        self._hit_counts: List[List[int]] = []

        # Active cells
        self._active_cells: List[
            Tuple[int, int, float]
        ] = []  # (rpm_idx, map_idx, weight)

        # Build UI
        self._build_ui()

        # Initialize table
        self._init_table()

    def _build_ui(self) -> None:
        """Build the VE table UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(12)

        # Title
        title = QLabel("🎯 Live VE Table")
        title.setStyleSheet("font-size: 12pt; font-weight: 600;")
        header.addWidget(title)

        header.addStretch()

        # Engine preset selector
        preset_label = QLabel("Engine:")
        preset_label.setStyleSheet(f"color: {COLORS['muted_foreground']};")
        header.addWidget(preset_label)

        self.preset_combo = QComboBox()
        for preset in EnginePreset:
            config = ENGINE_PRESETS[preset]
            self.preset_combo.addItem(config.name, preset.value)
        self.preset_combo.setCurrentText(self._config.name)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self.preset_combo.setFixedWidth(150)
        header.addWidget(self.preset_combo)

        # Reset button
        self.reset_btn = QPushButton("↺ Reset")
        self.reset_btn.setProperty("class", "secondary")
        self.reset_btn.clicked.connect(self._reset_table)
        header.addWidget(self.reset_btn)

        layout.addLayout(header)

        # Info row (live values)
        self.info_frame = QFrame()
        self.info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["muted"]};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        info_layout = QHBoxLayout(self.info_frame)
        info_layout.setContentsMargins(12, 8, 12, 8)
        info_layout.setSpacing(24)

        # RPM
        self.rpm_label = QLabel("RPM: ---")
        self.rpm_label.setStyleSheet("font-family: monospace; font-weight: 600;")
        info_layout.addWidget(self.rpm_label)

        # MAP
        self.map_label = QLabel("MAP: --- kPa")
        self.map_label.setStyleSheet("font-family: monospace; font-weight: 600;")
        info_layout.addWidget(self.map_label)

        # AFR
        self.afr_label = QLabel("AFR: ---")
        self.afr_label.setStyleSheet("font-family: monospace; font-weight: 600;")
        info_layout.addWidget(self.afr_label)

        # Target
        self.target_label = QLabel("Target: 14.7")
        self.target_label.setStyleSheet(
            f"font-family: monospace; color: {COLORS['muted_foreground']};"
        )
        info_layout.addWidget(self.target_label)

        info_layout.addStretch()

        # Status
        self.status_label = QLabel("⏸ Offline")
        info_layout.addWidget(self.status_label)

        layout.addWidget(self.info_frame)

        # Table
        self.table = QTableWidget()
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS["card"]};
                gridline-color: {COLORS["border"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 8px;
            }}
            QTableWidget::item {{
                padding: 4px;
                text-align: center;
            }}
            QHeaderView::section {{
                background-color: {COLORS["muted"]};
                color: {COLORS["foreground"]};
                padding: 6px;
                border: none;
                font-weight: 600;
                font-size: 9pt;
            }}
        """)
        layout.addWidget(self.table, 1)

        # Legend
        legend = QHBoxLayout()
        legend.setSpacing(16)

        legend.addStretch()

        self._add_legend_item(legend, "Lean", self.COLOR_LEAN)
        self._add_legend_item(legend, "OK", self.COLOR_OK)
        self._add_legend_item(legend, "Rich", self.COLOR_RICH)
        self._add_legend_item(legend, "Active", self.COLOR_ACTIVE)

        legend.addStretch()

        layout.addLayout(legend)

    def _add_legend_item(self, layout: QHBoxLayout, text: str, color: QColor) -> None:
        """Add a legend item."""
        container = QHBoxLayout()
        container.setSpacing(4)

        swatch = QLabel()
        swatch.setFixedSize(12, 12)
        swatch.setStyleSheet(f"""
            background-color: {color.name()};
            border-radius: 2px;
        """)
        container.addWidget(swatch)

        label = QLabel(text)
        label.setStyleSheet(f"color: {COLORS['muted_foreground']}; font-size: 9pt;")
        container.addWidget(label)

        layout.addLayout(container)

    def _init_table(self) -> None:
        """Initialize the table with current config."""
        rpm_bins = self._config.rpm_bins
        map_bins = self._config.map_bins

        # Set dimensions
        self.table.setRowCount(len(map_bins))
        self.table.setColumnCount(len(rpm_bins))

        # Set headers (RPM)
        self.table.setHorizontalHeaderLabels([str(rpm) for rpm in rpm_bins])

        # Set row headers (MAP)
        self.table.setVerticalHeaderLabels([f"{m} kPa" for m in map_bins])

        # Initialize data
        self._ve_data = [[100.0 for _ in rpm_bins] for _ in map_bins]
        self._hit_counts = [[0 for _ in rpm_bins] for _ in map_bins]

        # Populate cells
        for row in range(len(map_bins)):
            for col in range(len(rpm_bins)):
                item = QTableWidgetItem("100.0")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

        # Resize columns
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Resize rows
        v_header = self.table.verticalHeader()
        v_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def _on_preset_changed(self, index: int) -> None:
        """Handle preset change."""
        preset_value = self.preset_combo.itemData(index)
        self._preset = EnginePreset(preset_value)
        self._config = ENGINE_PRESETS[self._preset]
        self._init_table()
        self.preset_changed.emit(self._config.name)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        """Handle cell click."""
        self.cell_clicked.emit(col, row)  # rpm_idx, map_idx

    def _reset_table(self) -> None:
        """Reset the table to default values."""
        for row in range(len(self._ve_data)):
            for col in range(len(self._ve_data[row])):
                self._ve_data[row][col] = 100.0
                self._hit_counts[row][col] = 0

                item = self.table.item(row, col)
                if item:
                    item.setText("100.0")
                    item.setBackground(QBrush(QColor(COLORS["card"])))

    def set_live_values(self, rpm: float, map_kpa: float, afr: float) -> None:
        """Update live values and highlight active cells."""
        self._current_rpm = rpm
        self._current_map = map_kpa
        self._current_afr = afr

        # Update labels
        self.rpm_label.setText(f"RPM: {int(rpm)}")
        self.map_label.setText(f"MAP: {int(map_kpa)} kPa")
        self.afr_label.setText(f"AFR: {afr:.1f}")

        # Calculate active cells
        self._calculate_active_cells()

        # Update table highlighting
        self._update_cell_highlighting()

    def _calculate_active_cells(self) -> None:
        """Calculate which cells are active based on current RPM/MAP."""
        rpm_bins = self._config.rpm_bins
        map_bins = self._config.map_bins

        # Find RPM bin index
        rpm_idx = 0
        for i in range(len(rpm_bins) - 1):
            if self._current_rpm >= rpm_bins[i] and self._current_rpm < rpm_bins[i + 1]:
                rpm_idx = i
                break
            if self._current_rpm >= rpm_bins[-1]:
                rpm_idx = len(rpm_bins) - 1

        # Find MAP bin index
        map_idx = 0
        for i in range(len(map_bins) - 1):
            if self._current_map >= map_bins[i] and self._current_map < map_bins[i + 1]:
                map_idx = i
                break
            if self._current_map >= map_bins[-1]:
                map_idx = len(map_bins) - 1

        # Calculate interpolation weights
        rpm_low = rpm_bins[min(rpm_idx, len(rpm_bins) - 1)]
        rpm_high = rpm_bins[min(rpm_idx + 1, len(rpm_bins) - 1)]
        map_low = map_bins[min(map_idx, len(map_bins) - 1)]
        map_high = map_bins[min(map_idx + 1, len(map_bins) - 1)]

        rpm_weight = 0
        if rpm_high != rpm_low:
            rpm_weight = max(
                0, min(1, (self._current_rpm - rpm_low) / (rpm_high - rpm_low))
            )

        map_weight = 0
        if map_high != map_low:
            map_weight = max(
                0, min(1, (self._current_map - map_low) / (map_high - map_low))
            )

        # Bilinear interpolation weights
        self._active_cells = []

        w00 = (1 - rpm_weight) * (1 - map_weight)
        w01 = (1 - rpm_weight) * map_weight
        w10 = rpm_weight * (1 - map_weight)
        w11 = rpm_weight * map_weight

        if w00 > 0.01:
            self._active_cells.append((rpm_idx, map_idx, w00))
        if w01 > 0.01 and map_idx + 1 < len(map_bins):
            self._active_cells.append((rpm_idx, map_idx + 1, w01))
        if w10 > 0.01 and rpm_idx + 1 < len(rpm_bins):
            self._active_cells.append((rpm_idx + 1, map_idx, w10))
        if w11 > 0.01 and rpm_idx + 1 < len(rpm_bins) and map_idx + 1 < len(map_bins):
            self._active_cells.append((rpm_idx + 1, map_idx + 1, w11))

    def _update_cell_highlighting(self) -> None:
        """Update cell colors based on active state and AFR error."""
        # Reset all cells first
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    # Base color from VE value
                    ve_val = self._ve_data[row][col]
                    color = self._get_ve_color(ve_val)
                    item.setBackground(QBrush(color))

        # Highlight active cells
        for rpm_idx, map_idx, weight in self._active_cells:
            item = self.table.item(map_idx, rpm_idx)
            if item:
                # Blend active color with weight
                alpha = int(255 * weight)
                active_color = QColor(self.COLOR_ACTIVE)
                active_color.setAlpha(alpha)
                item.setBackground(QBrush(active_color))

    def _get_ve_color(self, ve_value: float) -> QColor:
        """Get color for a VE value."""
        # Deviation from 100%
        deviation = ve_value - 100.0

        if abs(deviation) < 2:
            # OK - near baseline
            return QColor(COLORS["card"])
        elif deviation > 0:
            # Rich - blue tint
            intensity = min(1, deviation / 10)
            color = QColor(self.COLOR_RICH)
            color.setAlpha(int(50 + 100 * intensity))
            return color
        else:
            # Lean - red tint
            intensity = min(1, abs(deviation) / 10)
            color = QColor(self.COLOR_LEAN)
            color.setAlpha(int(50 + 100 * intensity))
            return color

    def set_live_mode(self, enabled: bool) -> None:
        """Enable or disable live mode."""
        self._is_live = enabled
        if enabled:
            self.status_label.setText("🔴 Live")
            self.status_label.setStyleSheet("color: #22c55e;")
        else:
            self.status_label.setText("⏸ Offline")
            self.status_label.setStyleSheet(f"color: {COLORS['muted_foreground']};")

    def set_ve_data(self, ve_data: List[List[float]]) -> None:
        """Set the VE correction data."""
        self._ve_data = ve_data

        # Update table cells
        for row in range(min(len(ve_data), self.table.rowCount())):
            for col in range(min(len(ve_data[row]), self.table.columnCount())):
                item = self.table.item(row, col)
                if item:
                    item.setText(f"{ve_data[row][col]:.1f}")

        self._update_cell_highlighting()

    def set_target_afr(self, target: float) -> None:
        """Set the target AFR."""
        self._target_afr = target
        self.target_label.setText(f"Target: {target:.1f}")
