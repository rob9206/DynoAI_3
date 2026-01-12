"""
JetDrive Command Center Page for DynoAI PyQt6 GUI
Real-time dyno interface with live gauges, VE table, and hardware panels
"""

from enum import Enum
from typing import List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui.api.jetdrive_client import (
    ConnectionStatus,
    JetDriveClient,
    JetDriveSample,
    RunInfo,
)
from gui.components.button import Button, ButtonSize, ButtonVariant
from gui.components.card import Card, CardContent, CardHeader, CardTitle
from gui.styles.theme import COLORS
from gui.widgets.afr_target_table import AFRTargetTable
from gui.widgets.dyno_config_panel import DynoConfigPanel
from gui.widgets.ingestion_health_panel import IngestionHealthPanel
from gui.widgets.innovate_afr_panel import InnovateAFRPanel
from gui.widgets.live_gauge import CompactGauge, GaugeConfig, NeedleGauge
from gui.widgets.live_ve_table import EnginePreset, LiveVETable


class WorkflowState(Enum):
    """Workflow states for the JetDrive page."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    MONITORING = "monitoring"
    RUN_DETECTED = "run_detected"
    CAPTURING = "capturing"
    COMPLETE = "complete"


class JetDrivePage(QWidget):
    """
    JetDrive Command Center page.
    Shows live gauges, VE table with cell tracing, and run detection.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # JetDrive client
        self.client = JetDriveClient()
        self.client.status_changed.connect(self._on_status_changed)
        self.client.sample_received.connect(self._on_sample_received)
        self.client.run_detected.connect(self._on_run_detected)
        self.client.run_completed.connect(self._on_run_completed)
        self.client.error.connect(self._on_error)

        # State
        self._workflow_state = WorkflowState.DISCONNECTED
        self._runs: List[RunInfo] = []

        # Build UI
        self._build_ui()

        # Connect hardware panel signals after UI is built
        self._connect_panel_signals()

    def _build_ui(self) -> None:
        """Build the JetDrive page UI."""
        # Main layout with scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(24, 24, 24, 24)
        scroll_layout.setSpacing(24)

        # =====================================================================
        # Header
        # =====================================================================
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Title section
        title_section = QVBoxLayout()
        title_section.setSpacing(4)

        title = QLabel("🎯 JetDrive Command Center")
        title.setStyleSheet("font-size: 24pt; font-weight: 700;")
        title_section.addWidget(title)

        self.status_label = QLabel("Disconnected from dyno")
        self.status_label.setStyleSheet(f"color: {COLORS['muted_foreground']};")
        title_section.addWidget(self.status_label)

        header_layout.addLayout(title_section)
        header_layout.addStretch()

        # Connection controls
        btn_section = QHBoxLayout()
        btn_section.setSpacing(12)

        self.connect_btn = Button("Connect", ButtonVariant.DEFAULT, icon="📡")
        self.connect_btn.clicked.connect(self._toggle_connection)
        btn_section.addWidget(self.connect_btn)

        self.settings_btn = Button("Settings", ButtonVariant.SECONDARY, icon="⚙️")
        btn_section.addWidget(self.settings_btn)

        header_layout.addLayout(btn_section)

        scroll_layout.addWidget(header)

        # =====================================================================
        # Tab Widget for different views
        # =====================================================================
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: transparent;
            }}
            QTabBar::tab {{
                background-color: {COLORS["surface"]};
                color: {COLORS["text_secondary"]};
                border: 1px solid {COLORS["border"]};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 20px;
                margin-right: 4px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS["primary"]}20;
                color: {COLORS["primary"]};
                border-color: {COLORS["primary"]}50;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {COLORS["surface_hover"]};
            }}
        """)

        # =====================================================================
        # Tab 1: Live Dashboard
        # =====================================================================
        live_tab = QWidget()
        live_layout = QVBoxLayout(live_tab)
        live_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side - Gauges and info
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(16)

        # Primary gauges (HP, Torque, RPM)
        gauges_card = Card()
        gauges_header = CardHeader()
        gauges_title = CardTitle("Live Readings")
        gauges_header.addWidget(gauges_title)
        gauges_card.addWidget(gauges_header)

        gauges_content = CardContent()

        # Gauge grid
        gauge_grid = QGridLayout()
        gauge_grid.setSpacing(16)

        # RPM Gauge
        self.rpm_gauge = NeedleGauge(
            GaugeConfig(
                label="RPM",
                units="rpm",
                min_val=0,
                max_val=7000,
                warning=5500,
                critical=6500,
                decimals=0,
                color="#22d3ee",  # Cyan
            )
        )
        gauge_grid.addWidget(self.rpm_gauge, 0, 0)

        # HP Gauge
        self.hp_gauge = NeedleGauge(
            GaugeConfig(
                label="Horsepower",
                units="HP",
                min_val=0,
                max_val=200,
                decimals=1,
                color="#a855f7",  # Purple
            )
        )
        gauge_grid.addWidget(self.hp_gauge, 0, 1)

        # Torque Gauge
        self.torque_gauge = NeedleGauge(
            GaugeConfig(
                label="Torque",
                units="ft-lb",
                min_val=0,
                max_val=200,
                decimals=1,
                color="#f59e0b",  # Amber
            )
        )
        gauge_grid.addWidget(self.torque_gauge, 1, 0)

        # AFR Gauge
        self.afr_gauge = NeedleGauge(
            GaugeConfig(
                label="AFR",
                units=":1",
                min_val=10,
                max_val=18,
                warning=15.0,
                critical=16.0,
                decimals=1,
                color="#22c55e",  # Green
            )
        )
        gauge_grid.addWidget(self.afr_gauge, 1, 1)

        gauges_content.addLayout(gauge_grid)
        gauges_card.addWidget(gauges_content)

        left_layout.addWidget(gauges_card)

        # Secondary readings
        secondary_card = Card()
        secondary_header = CardHeader()
        secondary_title = CardTitle("Atmospheric")
        secondary_header.addWidget(secondary_title)
        secondary_card.addWidget(secondary_header)

        secondary_content = CardContent()
        secondary_grid = QHBoxLayout()
        secondary_grid.setSpacing(12)

        self.temp_gauge = CompactGauge("Temperature", "°C", 0, 50, "#ef4444")
        secondary_grid.addWidget(self.temp_gauge)

        self.humidity_gauge = CompactGauge("Humidity", "%", 0, 100, "#3b82f6")
        secondary_grid.addWidget(self.humidity_gauge)

        self.pressure_gauge = CompactGauge("Pressure", "kPa", 90, 110, "#22c55e")
        secondary_grid.addWidget(self.pressure_gauge)

        secondary_content.addLayout(secondary_grid)
        secondary_card.addWidget(secondary_content)

        left_layout.addWidget(secondary_card)

        # Run history
        runs_card = Card()
        runs_header = CardHeader()

        runs_title_row = QHBoxLayout()
        runs_title = CardTitle("Recent Runs")
        runs_title_row.addWidget(runs_title)
        runs_title_row.addStretch()

        self.runs_count_label = QLabel("0 runs")
        self.runs_count_label.setStyleSheet(
            f"color: {COLORS['muted_foreground']}; font-size: 9pt;"
        )
        runs_title_row.addWidget(self.runs_count_label)

        runs_title_widget = QWidget()
        runs_title_widget.setLayout(runs_title_row)
        runs_header.addWidget(runs_title_widget)
        runs_card.addWidget(runs_header)

        runs_content = CardContent()

        self.runs_container = QVBoxLayout()
        self.runs_container.setSpacing(8)

        # Placeholder
        self.no_runs_label = QLabel("No runs recorded yet")
        self.no_runs_label.setStyleSheet(
            f"color: {COLORS['muted_foreground']}; padding: 24px;"
        )
        self.no_runs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.runs_container.addWidget(self.no_runs_label)

        runs_content.addLayout(self.runs_container)
        runs_card.addWidget(runs_content)

        left_layout.addWidget(runs_card)
        left_layout.addStretch()

        splitter.addWidget(left_widget)

        # Right side - VE Table
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.ve_table = LiveVETable(EnginePreset.HARLEY_M8)
        right_layout.addWidget(self.ve_table)

        splitter.addWidget(right_widget)

        # Set splitter sizes (40% left, 60% right)
        splitter.setSizes([400, 600])

        live_layout.addWidget(splitter)
        self.tab_widget.addTab(live_tab, "📊 Live Dashboard")

        # =====================================================================
        # Tab 2: Hardware & Instrumentation
        # =====================================================================
        hardware_tab = QWidget()
        hardware_layout = QHBoxLayout(hardware_tab)
        hardware_layout.setContentsMargins(0, 16, 0, 0)
        hardware_layout.setSpacing(16)

        # Left column
        hw_left = QVBoxLayout()
        hw_left.setSpacing(16)

        # Dyno Config Panel
        self.dyno_config_panel = DynoConfigPanel()
        hw_left.addWidget(self.dyno_config_panel)

        # Ingestion Health Panel
        self.ingestion_panel = IngestionHealthPanel()
        hw_left.addWidget(self.ingestion_panel)

        hw_left.addStretch()

        hw_left_widget = QWidget()
        hw_left_widget.setLayout(hw_left)
        hardware_layout.addWidget(hw_left_widget)

        # Right column
        hw_right = QVBoxLayout()
        hw_right.setSpacing(16)

        # Innovate AFR Panel
        self.innovate_panel = InnovateAFRPanel()
        hw_right.addWidget(self.innovate_panel)

        hw_right.addStretch()

        hw_right_widget = QWidget()
        hw_right_widget.setLayout(hw_right)
        hardware_layout.addWidget(hw_right_widget)

        self.tab_widget.addTab(hardware_tab, "🔧 Hardware")

        # =====================================================================
        # Tab 3: AFR Targets
        # =====================================================================
        afr_tab = QWidget()
        afr_layout = QVBoxLayout(afr_tab)
        afr_layout.setContentsMargins(0, 16, 0, 0)
        afr_layout.setSpacing(16)

        # AFR Target Table
        afr_card = Card()
        afr_header = CardHeader()
        afr_title = CardTitle("🔥 AFR Target Configuration")
        afr_header.addWidget(afr_title)
        afr_card.addWidget(afr_header)

        afr_content = CardContent()
        self.afr_table = AFRTargetTable()
        afr_content.addWidget(self.afr_table)
        afr_card.addWidget(afr_content)

        afr_layout.addWidget(afr_card)
        afr_layout.addStretch()

        self.tab_widget.addTab(afr_tab, "🎯 AFR Targets")

        scroll_layout.addWidget(self.tab_widget, 1)

        scroll.setWidget(scroll_content)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _toggle_connection(self) -> None:
        """Toggle connection to JetDrive."""
        if self.client.is_connected:
            self.client.disconnect()
            self.connect_btn.setText("📡 Connect")
            self._workflow_state = WorkflowState.DISCONNECTED
        else:
            self.client.connect()
            self.connect_btn.setText("⏹ Disconnect")
            self._workflow_state = WorkflowState.CONNECTING

    def _on_status_changed(self, status: ConnectionStatus) -> None:
        """Handle connection status change."""
        if status == ConnectionStatus.CONNECTED:
            self.status_label.setText("🟢 Connected to dyno")
            self.status_label.setStyleSheet("color: #22c55e;")
            self._workflow_state = WorkflowState.IDLE
            self.ve_table.set_live_mode(True)
        elif status == ConnectionStatus.DISCONNECTED:
            self.status_label.setText("Disconnected from dyno")
            self.status_label.setStyleSheet(f"color: {COLORS['muted_foreground']};")
            self._workflow_state = WorkflowState.DISCONNECTED
            self.ve_table.set_live_mode(False)
            self.connect_btn.setText("📡 Connect")
        elif status == ConnectionStatus.ERROR:
            self.status_label.setText("🔴 Connection error")
            self.status_label.setStyleSheet("color: #ef4444;")

    def _on_sample_received(self, sample: JetDriveSample) -> None:
        """Handle new data sample."""
        # Update gauges
        self.rpm_gauge.setValue(sample.rpm)
        self.hp_gauge.setValue(sample.horsepower)
        self.torque_gauge.setValue(sample.torque)
        self.afr_gauge.setValue(sample.afr_front)

        # Update secondary
        self.temp_gauge.setValue(sample.temperature)
        self.humidity_gauge.setValue(sample.humidity)
        self.pressure_gauge.setValue(sample.pressure)

        # Store for AFR correlation
        self._store_live_values(sample.rpm, sample.map_kpa)

        # Update VE table
        self.ve_table.set_live_values(sample.rpm, sample.map_kpa, sample.afr_front)

    def _on_run_detected(self, run: RunInfo) -> None:
        """Handle run detection."""
        self._workflow_state = WorkflowState.CAPTURING
        self.status_label.setText(f"🔴 Capturing run... Peak: {run.peak_hp:.1f} HP")

    def _on_run_completed(self, run: RunInfo) -> None:
        """Handle run completion."""
        self._workflow_state = WorkflowState.COMPLETE
        self.status_label.setText(
            f"✅ Run complete! Peak: {run.peak_hp:.1f} HP / {run.peak_tq:.1f} ft-lb"
        )

        # Add to runs list
        self._runs.insert(0, run)
        self._update_runs_list()

        # Reset to idle after delay
        QTimer.singleShot(3000, self._reset_to_idle)

    def _reset_to_idle(self) -> None:
        """Reset to idle state."""
        if self.client.is_connected:
            self._workflow_state = WorkflowState.IDLE
            self.status_label.setText("🟢 Connected - Waiting for run")

    def _on_error(self, error: str) -> None:
        """Handle error."""
        self.status_label.setText(f"⚠️ Error: {error}")
        self.status_label.setStyleSheet("color: #f59e0b;")

    def _update_runs_list(self) -> None:
        """Update the runs list display."""
        # Clear existing
        while self.runs_container.count() > 0:
            item = self.runs_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._runs:
            self.no_runs_label = QLabel("No runs recorded yet")
            self.no_runs_label.setStyleSheet(
                f"color: {COLORS['muted_foreground']}; padding: 24px;"
            )
            self.no_runs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.runs_container.addWidget(self.no_runs_label)
            self.runs_count_label.setText("0 runs")
            return

        self.runs_count_label.setText(
            f"{len(self._runs)} run{'s' if len(self._runs) != 1 else ''}"
        )

        # Add run items (max 5)
        for run in self._runs[:5]:
            run_frame = QFrame()
            run_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS["muted"]};
                    border-radius: 6px;
                    padding: 8px;
                }}
            """)

            run_layout = QHBoxLayout(run_frame)
            run_layout.setContentsMargins(12, 8, 12, 8)
            run_layout.setSpacing(16)

            # Icon
            icon = QLabel("🏁")
            run_layout.addWidget(icon)

            # Info
            info = QLabel(f"Peak: {run.peak_hp:.1f} HP / {run.peak_tq:.1f} ft-lb")
            info.setStyleSheet("font-weight: 600;")
            run_layout.addWidget(info)

            run_layout.addStretch()

            # ID
            id_label = QLabel(f"#{run.run_id}")
            id_label.setStyleSheet(
                f"color: {COLORS['muted_foreground']}; font-size: 9pt;"
            )
            run_layout.addWidget(id_label)

            self.runs_container.addWidget(run_frame)

    def showEvent(self, event) -> None:
        """Handle show event."""
        super().showEvent(event)
        # Resume polling for hardware panels when page is visible
        if hasattr(self, "ingestion_panel"):
            self.ingestion_panel.start_polling()

    def hideEvent(self, event) -> None:
        """Handle hide event."""
        super().hideEvent(event)
        # Stop polling for hardware panels when page is not visible
        if hasattr(self, "ingestion_panel"):
            self.ingestion_panel.stop_polling()

    def _connect_panel_signals(self) -> None:
        """Connect signals from hardware panels to integrate with live data."""
        # Innovate AFR panel -> update gauges
        self.innovate_panel.afr_updated.connect(self._on_innovate_afr_updated)

        # AFR Target Table -> notify VE table of target changes
        self.afr_table.grid_changed.connect(self._on_afr_targets_changed)
        self.afr_table.targets_changed.connect(self._on_afr_targets_changed_legacy)

        # Dyno Config panel -> update status
        self.dyno_config_panel.config_loaded.connect(self._on_dyno_config_loaded)
        self.dyno_config_panel.connection_status_changed.connect(
            self._on_dyno_connection_changed
        )

        # Ingestion Health panel -> monitor data pipeline
        self.ingestion_panel.health_updated.connect(self._on_ingestion_health_updated)

    def _on_innovate_afr_updated(self, channel_a: float, channel_b: float) -> None:
        """Handle Innovate AFR updates from wideband."""
        # Update primary AFR gauge with average of both channels
        avg_afr = (channel_a + channel_b) / 2.0
        self.afr_gauge.setValue(avg_afr)

        # Update VE table with AFR data (use front cylinder for tracing)
        if hasattr(self, "_last_rpm") and hasattr(self, "_last_map"):
            self.ve_table.set_live_values(self._last_rpm, self._last_map, channel_a)

    def _on_afr_targets_changed(self, grid: List[List[float]]) -> None:
        """Handle AFR target grid changes."""
        # Could send to VE table or backend for closed-loop tuning
        # For now, just log the change
        print(f"AFR targets updated: {len(grid)}x{len(grid[0])} grid")

    def _on_afr_targets_changed_legacy(self, targets: dict) -> None:
        """Handle legacy MAP-based AFR target changes."""
        print(f"AFR targets updated (legacy format): {len(targets)} MAP bins")

    def _on_dyno_config_loaded(self, config) -> None:
        """Handle dyno configuration loaded."""
        if config:
            self.status_label.setText(
                f"🔧 Dyno: {config.model} (SN: {config.serial_number})"
            )

    def _on_dyno_connection_changed(self, connected: bool) -> None:
        """Handle dyno connection status change."""
        if connected:
            print("✓ Dyno hardware connected")
        else:
            print("✗ Dyno hardware disconnected")

    def _on_ingestion_health_updated(self, health: str) -> None:
        """Handle ingestion health status updates."""
        # Could display health indicator in main status
        if health in ["critical", "unhealthy"]:
            print(f"⚠️ Data ingestion health: {health}")

    def _store_live_values(self, rpm: float, map_kpa: float) -> None:
        """Store last known RPM/MAP for AFR correlation."""
        self._last_rpm = rpm
        self._last_map = map_kpa
