"""
DynoConfigPanel - Display connected Dynoware RT configuration
Port of frontend/src/components/jetdrive/DynoConfigPanel.tsx

Shows drum specifications from the backend configuration:
- Model & serial number
- Drum 1 specs (mass, circumference, inertia)
- Network connection info
- Power calculation preview
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.components.card import (
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
)
from gui.styles.theme import COLORS


@dataclass
class DrumSpec:
    """Drum specification data."""

    serial_number: str = ""
    mass_slugs: float = 0.0
    retarder_mass_slugs: float = 0.0
    circumference_ft: float = 0.0
    num_tabs: int = 0
    radius_ft: float = 0.0
    inertia_lbft2: float = 0.0
    configured: bool = False


@dataclass
class DynoConfig:
    """Dyno configuration data."""

    model: str = "RT-150"
    serial_number: str = ""
    location: str = ""
    ip_address: str = ""
    jetdrive_port: int = 22344
    firmware_version: str = ""
    atmo_version: str = ""
    num_modules: int = 0
    drum1: Optional[DrumSpec] = None
    drum2: Optional[DrumSpec] = None


class DynoConfigPanel(QWidget):
    """
    Panel displaying Dynoware RT dyno configuration.
    Shows drum specs, network info, and connection status.
    """

    # Signals
    config_loaded = pyqtSignal(object)  # DynoConfig
    connection_status_changed = pyqtSignal(bool)

    def __init__(
        self,
        api_url: str = "http://127.0.0.1:5001/api/jetdrive",
        compact: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._api_url = api_url
        self._compact = compact
        self._config: Optional[DynoConfig] = None
        self._connected = False
        self._loading = False

        # Network manager
        self._network_manager = QNetworkAccessManager(self)
        self._network_manager.finished.connect(self._on_request_finished)

        self._build_ui()

        # Auto-fetch config on init
        QTimer.singleShot(100, self._fetch_config)

    def _build_ui(self) -> None:
        """Build the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = Card()

        # Header
        header = CardHeader()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Icon and title
        icon_label = QLabel("🎯")
        icon_label.setStyleSheet(f"""
            background-color: {COLORS["primary"]}20;
            border-radius: 8px;
            padding: 8px;
            font-size: 16pt;
        """)
        header_layout.addWidget(icon_label)

        title_section = QVBoxLayout()
        title_section.setSpacing(2)

        title = CardTitle("Dyno Configuration")
        title_section.addWidget(title)

        desc = CardDescription("Dynoware RT drum specs & network")
        title_section.addWidget(desc)

        header_layout.addLayout(title_section)
        header_layout.addStretch()

        # Status badge
        self.status_badge = QLabel("Disconnected")
        self.status_badge.setStyleSheet(f"""
            background-color: {COLORS["muted"]};
            color: {COLORS["muted_foreground"]};
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 9pt;
            font-weight: bold;
        """)
        header_layout.addWidget(self.status_badge)

        # Refresh button
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(32, 32)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                font-size: 14pt;
                color: {COLORS["muted_foreground"]};
            }}
            QPushButton:hover {{
                background-color: {COLORS["muted"]};
                border-radius: 16px;
            }}
        """)
        refresh_btn.clicked.connect(self._fetch_config)
        header_layout.addWidget(refresh_btn)

        header_widget = QWidget()
        header_widget.setLayout(header_layout)
        header.addWidget(header_widget)
        card.addWidget(header)

        # Content
        content = CardContent()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(16)

        # Loading indicator
        self.loading_label = QLabel("Loading configuration...")
        self.loading_label.setStyleSheet(
            f"color: {COLORS['muted_foreground']}; padding: 24px;"
        )
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setVisible(True)
        content_layout.addWidget(self.loading_label)

        # Config display (hidden until loaded)
        self.config_widget = QWidget()
        config_layout = QVBoxLayout(self.config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(16)

        # Model & Serial
        model_section = self._create_section("Model & Serial")
        self.model_grid = QGridLayout()
        self.model_grid.setSpacing(8)

        self._add_spec_row(self.model_grid, 0, "Model", "—", "model_label")
        self._add_spec_row(self.model_grid, 1, "Serial", "—", "serial_label")
        self._add_spec_row(self.model_grid, 2, "Location", "—", "location_label")

        model_section.addLayout(self.model_grid)
        config_layout.addWidget(self._wrap_section(model_section))

        # Network
        network_section = self._create_section("Network")
        self.network_grid = QGridLayout()
        self.network_grid.setSpacing(8)

        self._add_spec_row(self.network_grid, 0, "IP Address", "—", "ip_label")
        self._add_spec_row(self.network_grid, 1, "JetDrive Port", "—", "port_label")
        self._add_spec_row(self.network_grid, 2, "Firmware", "—", "firmware_label")

        network_section.addLayout(self.network_grid)
        config_layout.addWidget(self._wrap_section(network_section))

        # Drum 1 Specs
        drum_section = self._create_section("Drum 1 Specifications")
        self.drum_grid = QGridLayout()
        self.drum_grid.setSpacing(8)

        self._add_spec_row(self.drum_grid, 0, "Serial", "—", "drum_serial_label")
        self._add_spec_row(self.drum_grid, 1, "Mass", "—", "drum_mass_label")
        self._add_spec_row(self.drum_grid, 2, "Circumference", "—", "drum_circ_label")
        self._add_spec_row(self.drum_grid, 3, "Radius", "—", "drum_radius_label")
        self._add_spec_row(self.drum_grid, 4, "Inertia", "—", "drum_inertia_label")

        drum_section.addLayout(self.drum_grid)
        config_layout.addWidget(self._wrap_section(drum_section))

        # Power formula info
        formula_frame = QFrame()
        formula_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["primary"]}15;
                border: 1px solid {COLORS["primary"]}30;
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        formula_layout = QVBoxLayout(formula_frame)
        formula_layout.setSpacing(4)

        formula_title = QLabel("🧮 Power Calculation")
        formula_title.setStyleSheet("font-weight: bold;")
        formula_layout.addWidget(formula_title)

        formula_text = QLabel("HP = (Force × Circumference × RPM) / 33000")
        formula_text.setStyleSheet(
            f"color: {COLORS['muted_foreground']}; font-family: monospace;"
        )
        formula_layout.addWidget(formula_text)

        config_layout.addWidget(formula_frame)

        self.config_widget.setVisible(False)
        content_layout.addWidget(self.config_widget)

        content_widget = QWidget()
        content_widget.setLayout(content_layout)
        content.addWidget(content_widget)
        card.addWidget(content)

        layout.addWidget(card)

    def _create_section(self, title: str) -> QVBoxLayout:
        """Create a section layout with title."""
        layout = QVBoxLayout()
        layout.setSpacing(8)

        label = QLabel(title)
        label.setStyleSheet(
            f"font-size: 10pt; font-weight: bold; color: {COLORS['text_secondary']};"
        )
        layout.addWidget(label)

        return layout

    def _wrap_section(self, layout: QVBoxLayout) -> QFrame:
        """Wrap a section in a styled frame."""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["muted"]};
                border-radius: 8px;
                padding: 12px;
            }}
        """)

        wrapper = QVBoxLayout(frame)
        wrapper.setContentsMargins(12, 12, 12, 12)

        # Move widgets from layout to wrapper
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                wrapper.addWidget(item.widget())
            elif item.layout():
                wrapper.addLayout(item.layout())

        return frame

    def _add_spec_row(
        self, grid: QGridLayout, row: int, label: str, value: str, attr_name: str
    ) -> None:
        """Add a specification row to the grid."""
        label_widget = QLabel(label)
        label_widget.setStyleSheet(
            f"color: {COLORS['muted_foreground']}; font-size: 9pt;"
        )

        value_widget = QLabel(value)
        value_widget.setStyleSheet("font-weight: bold; font-family: monospace;")
        value_widget.setAlignment(Qt.AlignmentFlag.AlignRight)

        grid.addWidget(label_widget, row, 0)
        grid.addWidget(value_widget, row, 1)

        # Store reference
        setattr(self, attr_name, value_widget)

    def _fetch_config(self) -> None:
        """Fetch dyno configuration from API."""
        if self._loading:
            return

        self._loading = True
        self.loading_label.setText("Loading configuration...")
        self.loading_label.setVisible(True)
        self.config_widget.setVisible(False)

        from PyQt6.QtCore import QUrl

        url = QUrl(f"{self._api_url}/dyno/config")
        request = QNetworkRequest(url)
        self._network_manager.get(request)

    def _on_request_finished(self, reply: QNetworkReply) -> None:
        """Handle API response."""
        self._loading = False

        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.loading_label.setText(f"Failed to load: {reply.errorString()}")
            self._update_status(False)
            reply.deleteLater()
            return

        try:
            import json

            data = json.loads(bytes(reply.readAll()).decode())

            if data.get("success") and "config" in data:
                config_data = data["config"]
                self._config = self._parse_config(config_data)
                self._update_display()
                self._update_status(True)
            else:
                self.loading_label.setText(data.get("error", "Unknown error"))
                self._update_status(False)

        except Exception as e:
            self.loading_label.setText(f"Parse error: {str(e)}")
            self._update_status(False)

        reply.deleteLater()

    def _parse_config(self, data: Dict[str, Any]) -> DynoConfig:
        """Parse config data into DynoConfig object."""
        drum1 = None
        if "drum1" in data:
            d1 = data["drum1"]
            drum1 = DrumSpec(
                serial_number=d1.get("serial_number", ""),
                mass_slugs=d1.get("mass_slugs", 0),
                retarder_mass_slugs=d1.get("retarder_mass_slugs", 0),
                circumference_ft=d1.get("circumference_ft", 0),
                num_tabs=d1.get("num_tabs", 0),
                radius_ft=d1.get("radius_ft", 0),
                inertia_lbft2=d1.get("inertia_lbft2", 0),
                configured=d1.get("configured", False),
            )

        return DynoConfig(
            model=data.get("model", "RT-150"),
            serial_number=data.get("serial_number", ""),
            location=data.get("location", ""),
            ip_address=data.get("ip_address", ""),
            jetdrive_port=data.get("jetdrive_port", 22344),
            firmware_version=data.get("firmware_version", ""),
            atmo_version=data.get("atmo_version", ""),
            num_modules=data.get("num_modules", 0),
            drum1=drum1,
        )

    def _update_display(self) -> None:
        """Update display with config data."""
        if not self._config:
            return

        c = self._config

        # Model & Serial
        self.model_label.setText(c.model)
        self.serial_label.setText(c.serial_number or "—")
        self.location_label.setText(c.location or "—")

        # Network
        self.ip_label.setText(c.ip_address or "—")
        self.port_label.setText(str(c.jetdrive_port))
        self.firmware_label.setText(c.firmware_version or "—")

        # Drum 1
        if c.drum1:
            d = c.drum1
            self.drum_serial_label.setText(d.serial_number or "—")
            self.drum_mass_label.setText(f"{d.mass_slugs:.3f} slugs")
            self.drum_circ_label.setText(f"{d.circumference_ft:.3f} ft")
            self.drum_radius_label.setText(f"{d.radius_ft:.4f} ft")
            self.drum_inertia_label.setText(f"{d.inertia_lbft2:.2f} lb·ft²")
        else:
            self.drum_serial_label.setText("Not configured")

        self.loading_label.setVisible(False)
        self.config_widget.setVisible(True)

        self.config_loaded.emit(self._config)

    def _update_status(self, connected: bool) -> None:
        """Update connection status display."""
        self._connected = connected

        if connected:
            self.status_badge.setText("✓ Connected")
            self.status_badge.setStyleSheet(f"""
                background-color: #22c55e30;
                color: #22c55e;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 9pt;
                font-weight: bold;
            """)
        else:
            self.status_badge.setText("Disconnected")
            self.status_badge.setStyleSheet(f"""
                background-color: {COLORS["muted"]};
                color: {COLORS["muted_foreground"]};
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 9pt;
                font-weight: bold;
            """)

        self.connection_status_changed.emit(connected)

    def get_config(self) -> Optional[DynoConfig]:
        """Get the current dyno configuration."""
        return self._config

    def is_connected(self) -> bool:
        """Check if connected to dyno."""
        return self._connected

    def refresh(self) -> None:
        """Refresh the configuration."""
        self._fetch_config()

    def hideEvent(self, event) -> None:
        """Stop network requests when panel is hidden."""
        super().hideEvent(event)
        # Network requests are one-shot, no ongoing polling to stop

    def showEvent(self, event) -> None:
        """Refresh config when panel is shown."""
        super().showEvent(event)
        if self._config is None:
            self._fetch_config()
