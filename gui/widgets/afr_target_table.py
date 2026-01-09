"""
AFRTargetTable - Editable 2D AFR target grid (RPM x MAP)
Port of frontend/src/components/jetdrive/AFRTargetTable.tsx

Grid structure:
- RPM: 1000-6500 (12 columns)
- MAP: 20-100 kPa (9 rows)

Includes presets for common applications:
- NA Street: 14.7 idle → 12.2 WOT
- NA Performance: 14.5 idle → 12.0 WOT
- Turbo/SC: 14.2 idle → 11.2 WOT
- E85: 13.5 idle → 10.2 WOT
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.styles.theme import COLORS

# RPM bins (1000-6500 in 500 RPM increments)
RPM_BINS = [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]

# MAP bins (load zones)
MAP_BINS = [20, 30, 40, 50, 60, 70, 80, 90, 100]

# Load zone labels
LOAD_ZONES = {
    20: "Decel",
    30: "Idle",
    40: "Lt Cruise",
    50: "Cruise",
    60: "Part",
    70: "Mid",
    80: "Heavy",
    90: "High",
    100: "WOT",
}

# Default AFR targets (MAP-based)
DEFAULT_AFR_TARGETS: Dict[int, float] = {
    20: 14.7,  # Deep vacuum / decel
    30: 14.7,  # Idle
    40: 14.5,  # Light cruise
    50: 14.0,  # Cruise
    60: 13.5,  # Part throttle
    70: 13.0,  # Mid load
    80: 12.8,  # Heavy load
    90: 12.5,  # High load
    100: 12.2,  # WOT / boost
}


class AFRPreset(Enum):
    """AFR preset configurations."""

    NA_STREET = "na_street"
    NA_PERFORMANCE = "na_performance"
    TURBO = "turbo"
    E85 = "e85"


@dataclass
class PresetConfig:
    """Configuration for an AFR preset."""

    name: str
    description: str
    icon: str
    targets: Dict[int, float]


# Preset configurations
AFR_PRESETS: Dict[AFRPreset, PresetConfig] = {
    AFRPreset.NA_STREET: PresetConfig(
        name="NA Street",
        description="Conservative for pump gas daily driver",
        icon="💧",
        targets={
            20: 14.7,
            30: 14.7,
            40: 14.5,
            50: 14.0,
            60: 13.5,
            70: 13.0,
            80: 12.8,
            90: 12.5,
            100: 12.2,
        },
    ),
    AFRPreset.NA_PERFORMANCE: PresetConfig(
        name="NA Performance",
        description="Aggressive for NA high-performance builds",
        icon="⚡",
        targets={
            20: 14.7,
            30: 14.5,
            40: 14.2,
            50: 13.8,
            60: 13.2,
            70: 12.8,
            80: 12.5,
            90: 12.3,
            100: 12.0,
        },
    ),
    AFRPreset.TURBO: PresetConfig(
        name="Turbo/SC",
        description="Richer targets for forced induction",
        icon="🔥",
        targets={
            20: 14.5,
            30: 14.2,
            40: 13.8,
            50: 13.2,
            60: 12.8,
            70: 12.3,
            80: 11.8,
            90: 11.5,
            100: 11.2,
        },
    ),
    AFRPreset.E85: PresetConfig(
        name="E85",
        description="Optimized for E85 fuel (~9.8 stoich)",
        icon="⛽",
        targets={
            20: 14.0,
            30: 13.5,
            40: 12.8,
            50: 12.0,
            60: 11.5,
            70: 11.0,
            80: 10.8,
            90: 10.5,
            100: 10.2,
        },
    ),
}


def get_afr_color(afr: float) -> str:
    """Get color based on AFR value."""
    if afr >= 14.5:
        return "#60a5fa"  # Blue - lean / stoich
    if afr >= 13.5:
        return "#4ade80"  # Green - cruise
    if afr >= 12.5:
        return "#facc15"  # Yellow - rich cruise
    if afr >= 11.5:
        return "#fb923c"  # Orange - WOT zone
    return "#f87171"  # Red - very rich (E85/turbo)


def get_afr_bg_color(afr: float) -> str:
    """Get background color based on AFR value."""
    if afr >= 14.5:
        return "#1e3a5f"  # Dark blue
    if afr >= 13.5:
        return "#14532d"  # Dark green
    if afr >= 12.5:
        return "#422006"  # Dark yellow/amber
    if afr >= 11.5:
        return "#431407"  # Dark orange
    return "#450a0a"  # Dark red


def create_default_grid() -> List[List[float]]:
    """Create default 2D grid from MAP-based targets."""
    return [
        [DEFAULT_AFR_TARGETS.get(map_kpa, 14.0) for map_kpa in MAP_BINS]
        for _ in RPM_BINS
    ]


class AFRTargetTable(QWidget):
    """
    Editable 2D AFR target table with RPM x MAP grid.
    Supports presets and cell editing.
    """

    # Signals
    grid_changed = pyqtSignal(list)  # Emits the full 2D grid
    targets_changed = pyqtSignal(dict)  # Emits MAP-averaged targets (legacy)

    def __init__(self, compact: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._compact = compact
        self._grid: List[List[float]] = create_default_grid()
        self._current_rpm: Optional[int] = None
        self._current_map: Optional[int] = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the AFR table UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header with title and presets
        header = QHBoxLayout()

        title = QLabel("AFR Target Grid (RPM × MAP)")
        title.setStyleSheet("font-size: 11pt; font-weight: 600;")
        header.addWidget(title)

        header.addStretch()

        # Preset dropdown
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("🔧 Select Preset", None)
        for preset, config in AFR_PRESETS.items():
            self.preset_combo.addItem(f"{config.icon} {config.name}", preset)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        self.preset_combo.setMinimumWidth(160)
        header.addWidget(self.preset_combo)

        # Reset button
        reset_btn = QPushButton("↺ Reset")
        reset_btn.setProperty("class", "secondary")
        reset_btn.clicked.connect(self._reset_to_default)
        reset_btn.setMaximumWidth(80)
        header.addWidget(reset_btn)

        layout.addLayout(header)

        # Create table
        self._build_table()
        layout.addWidget(self.table)

        # Help text
        help_text = QLabel("Click any cell to edit · Lower AFR = richer mixture")
        help_text.setStyleSheet(f"color: {COLORS['muted_foreground']}; font-size: 9pt;")
        layout.addWidget(help_text)

    def _build_table(self) -> None:
        """Build the AFR table widget."""
        self.table = QTableWidget()
        self.table.setRowCount(len(MAP_BINS))
        self.table.setColumnCount(len(RPM_BINS))

        # Set headers
        self.table.setHorizontalHeaderLabels([str(rpm) for rpm in RPM_BINS])

        # Set vertical headers with MAP and zone
        vertical_labels = []
        for map_kpa in MAP_BINS:
            zone = LOAD_ZONES.get(map_kpa, "")
            vertical_labels.append(f"{map_kpa}\n{zone}")
        self.table.setVerticalHeaderLabels(vertical_labels)

        # Style table
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 8px;
                gridline-color: {COLORS["border"]};
            }}
            QTableWidget::item {{
                padding: 4px;
                text-align: center;
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS["primary"]};
                color: #1a1b26;
            }}
            QHeaderView::section {{
                background-color: {COLORS["surface"]};
                color: {COLORS["text_primary"]};
                border: 1px solid {COLORS["border"]};
                padding: 6px;
                font-weight: bold;
                font-size: 10pt;
            }}
        """)

        # Configure headers
        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        h_header.setMinimumSectionSize(45)

        v_header = self.table.verticalHeader()
        v_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        v_header.setDefaultSectionSize(45)
        v_header.setMinimumWidth(70)

        # Populate cells
        self._populate_cells()

        # Connect edit signal
        self.table.cellChanged.connect(self._on_cell_changed)

    def _populate_cells(self) -> None:
        """Populate table cells with grid values."""
        self.table.blockSignals(True)

        font = QFont("Consolas", 10)
        font.setBold(True)

        for rpm_idx, rpm in enumerate(RPM_BINS):
            for map_idx, map_kpa in enumerate(MAP_BINS):
                afr = self._grid[rpm_idx][map_idx]

                item = QTableWidgetItem(f"{afr:.1f}")
                item.setFont(font)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Set colors based on AFR value
                bg_color = QColor(get_afr_bg_color(afr))
                text_color = QColor(get_afr_color(afr))

                item.setBackground(QBrush(bg_color))
                item.setForeground(QBrush(text_color))

                self.table.setItem(map_idx, rpm_idx, item)

        self.table.blockSignals(False)

    def _on_cell_changed(self, row: int, col: int) -> None:
        """Handle cell edit."""
        item = self.table.item(row, col)
        if not item:
            return

        try:
            new_value = float(item.text())

            # Validate AFR range
            if new_value < 9.0 or new_value > 16.0:
                # Show error message
                self._show_afr_validation_error(new_value)
                # Restore previous value
                self._populate_cells()
                return

            # Clamp and round
            new_value = max(9.0, min(16.0, new_value))
            new_value = round(new_value, 1)

            # Update grid
            self._grid[col][row] = new_value

            # Update cell display
            self.table.blockSignals(True)
            item.setText(f"{new_value:.1f}")

            bg_color = QColor(get_afr_bg_color(new_value))
            text_color = QColor(get_afr_color(new_value))
            item.setBackground(QBrush(bg_color))
            item.setForeground(QBrush(text_color))
            self.table.blockSignals(False)

            # Emit signals
            self.grid_changed.emit(self._grid)
            self.targets_changed.emit(self._grid_to_targets())

        except ValueError:
            # Show error message for non-numeric input
            self._show_afr_format_error(item.text())
            # Restore previous value
            self._populate_cells()

    def _show_afr_validation_error(self, value: float) -> None:
        """Show validation error dialog for out-of-range AFR value."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Invalid AFR Value")
        msg.setText(f"AFR value {value:.1f} is out of valid range.")
        msg.setInformativeText(
            "AFR values must be between 9.0 and 16.0.\n\n"
            "• 9.0-11.0: Very rich (E85, forced induction)\n"
            "• 11.0-13.0: Rich (WOT, power)\n"
            "• 13.0-14.7: Cruise (efficiency)\n"
            "• 14.7-16.0: Lean (economy, idle)"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def _show_afr_format_error(self, text: str) -> None:
        """Show format error dialog for non-numeric input."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Invalid Input Format")
        msg.setText(f"'{text}' is not a valid number.")
        msg.setInformativeText(
            "Please enter a numeric AFR value between 9.0 and 16.0.\n"
            "Examples: 12.5, 14.7, 11.0"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def _on_preset_selected(self, index: int) -> None:
        """Handle preset selection."""
        preset = self.preset_combo.currentData()
        if preset and preset in AFR_PRESETS:
            self._apply_preset(preset)
            # Reset combo to "Select Preset"
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(0)
            self.preset_combo.blockSignals(False)

    def _apply_preset(self, preset: AFRPreset) -> None:
        """Apply a preset to the grid."""
        config = AFR_PRESETS.get(preset)
        if not config:
            return

        # Create grid from preset targets
        self._grid = [
            [config.targets.get(map_kpa, 14.0) for map_kpa in MAP_BINS]
            for _ in RPM_BINS
        ]

        self._populate_cells()

        # Emit signals
        self.grid_changed.emit(self._grid)
        self.targets_changed.emit(config.targets.copy())

    def _reset_to_default(self) -> None:
        """Reset to default AFR targets."""
        self._grid = create_default_grid()
        self._populate_cells()

        # Emit signals
        self.grid_changed.emit(self._grid)
        self.targets_changed.emit(DEFAULT_AFR_TARGETS.copy())

    def _grid_to_targets(self) -> Dict[int, float]:
        """Convert 2D grid to MAP-averaged targets (legacy format)."""
        targets = {}
        if len(self._grid) == 0:
            return targets

        for map_idx, map_kpa in enumerate(MAP_BINS):
            # Average across all RPM for this MAP
            avg = sum(row[map_idx] for row in self._grid) / len(self._grid)
            targets[map_kpa] = round(avg, 1)
        return targets

    def set_active_cell(self, rpm: Optional[int], map_kpa: Optional[int]) -> None:
        """Highlight the active cell based on current RPM/MAP."""
        self._current_rpm = rpm
        self._current_map = map_kpa

        # Find closest bins
        if rpm is not None and map_kpa is not None:
            # Find closest RPM
            rpm_idx = 0
            min_rpm_diff = abs(RPM_BINS[0] - rpm)
            for idx, bin_rpm in enumerate(RPM_BINS):
                diff = abs(bin_rpm - rpm)
                if diff < min_rpm_diff:
                    min_rpm_diff = diff
                    rpm_idx = idx

            # Find closest MAP
            map_idx = 0
            min_map_diff = abs(MAP_BINS[0] - map_kpa)
            for idx, bin_map in enumerate(MAP_BINS):
                diff = abs(bin_map - map_kpa)
                if diff < min_map_diff:
                    min_map_diff = diff
                    map_idx = idx

            # Select the cell
            self.table.setCurrentCell(map_idx, rpm_idx)
        else:
            self.table.clearSelection()

    def get_grid(self) -> List[List[float]]:
        """Get the current AFR grid."""
        return [row[:] for row in self._grid]

    def set_grid(self, grid: List[List[float]]) -> None:
        """Set the AFR grid."""
        if len(grid) == len(RPM_BINS) and len(grid[0]) == len(MAP_BINS):
            self._grid = [row[:] for row in grid]
            self._populate_cells()

    def get_targets(self) -> Dict[int, float]:
        """Get the MAP-averaged targets (legacy format)."""
        return self._grid_to_targets()
