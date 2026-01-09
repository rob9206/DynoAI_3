"""
IngestionHealthPanel - Real-time monitoring of data ingestion health
Port of frontend/src/components/jetdrive/IngestionHealthPanel.tsx

Displays:
- Overall health status with visual indicator
- Channel health breakdown
- Frame drop statistics
- Circuit breaker states
- Data rate metrics
"""

from typing import Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGridLayout, QPushButton, QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from gui.components.card import Card, CardHeader, CardContent, CardTitle, CardDescription
from gui.styles.theme import COLORS


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass
class ChannelHealth:
    """Health data for a single channel."""
    channel_id: str = ""
    channel_name: str = ""
    health: str = "unknown"
    samples_per_second: float = 0.0
    total_samples: int = 0
    age_seconds: float = 0.0
    last_value: float = 0.0


@dataclass
class FrameStats:
    """Frame statistics."""
    total: int = 0
    dropped: int = 0
    drop_rate: float = 0.0


@dataclass
class CircuitBreakerState:
    """Circuit breaker state."""
    state: str = "closed"  # closed, open, half_open
    failure_count: int = 0
    success_rate: float = 1.0


def get_health_color(health: str) -> str:
    """Get color for health status."""
    colors = {
        "healthy": "#22c55e",
        "warning": "#eab308",
        "critical": "#ef4444",
        "unhealthy": "#ef4444",
        "stale": "#6b7280",
        "degraded": "#f97316",
        "unknown": "#6b7280",
    }
    return colors.get(health, "#6b7280")


def get_health_bg_color(health: str) -> str:
    """Get background color for health status."""
    colors = {
        "healthy": "#22c55e20",
        "warning": "#eab30820",
        "critical": "#ef444420",
        "unhealthy": "#ef444420",
        "stale": "#6b728020",
        "degraded": "#f9731620",
        "unknown": "#6b728020",
    }
    return colors.get(health, "#6b728020")


def get_health_icon(health: str) -> str:
    """Get icon for health status."""
    icons = {
        "healthy": "✓",
        "warning": "⚠",
        "critical": "✕",
        "unhealthy": "✕",
        "stale": "⏱",
        "degraded": "⚠",
        "unknown": "?",
    }
    return icons.get(health, "?")


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds / 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


class LivePulse(QLabel):
    """Animated pulse indicator for live data."""
    
    def __init__(self, active: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._active = active
        self.setFixedSize(8, 8)
        self._update_style()
        
    def setActive(self, active: bool) -> None:
        self._active = active
        self._update_style()
        
    def _update_style(self) -> None:
        color = "#22c55e" if self._active else "#6b7280"
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)


class ChannelHealthRow(QWidget):
    """Row displaying health for a single channel."""
    
    def __init__(self, channel: ChannelHealth, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._channel = channel
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(12)
        
        # Health icon
        icon = QLabel(get_health_icon(channel.health))
        icon.setStyleSheet(f"color: {get_health_color(channel.health)}; font-size: 10pt;")
        layout.addWidget(icon)
        
        # Channel name
        name = QLabel(channel.channel_name)
        name.setStyleSheet("font-weight: 600; font-size: 10pt;")
        layout.addWidget(name)
        
        layout.addStretch()
        
        # Sample rate
        rate_color = "#22c55e" if channel.samples_per_second > 10 else "#eab308" if channel.samples_per_second > 0 else "#6b7280"
        rate = QLabel(f"{channel.samples_per_second:.1f} Hz")
        rate.setStyleSheet(f"color: {rate_color}; font-size: 9pt;")
        layout.addWidget(rate)
        
        # Age
        age_color = "#eab308" if channel.age_seconds > 5 else COLORS['muted_foreground']
        age = QLabel(f"{format_duration(channel.age_seconds)} ago")
        age.setStyleSheet(f"color: {age_color}; font-size: 9pt;")
        layout.addWidget(age)
        
        # Last value
        value = QLabel(f"{channel.last_value:.2f}")
        value.setStyleSheet("font-family: monospace; font-size: 9pt; min-width: 50px; text-align: right;")
        value.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(value)
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: transparent;
            }}
            QWidget:hover {{
                background-color: {COLORS['muted']}50;
                border-radius: 4px;
            }}
        """)


class CircuitBreakerCard(QFrame):
    """Card displaying circuit breaker state."""
    
    reset_clicked = pyqtSignal(str)
    
    def __init__(self, name: str, breaker: CircuitBreakerState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._name = name
        self._breaker = breaker
        
        # Style based on state
        state_styles = {
            "closed": ("background-color: #22c55e20; border: 1px solid #22c55e30;", "#22c55e", "🛡"),
            "open": ("background-color: #ef444420; border: 1px solid #ef444430;", "#ef4444", "📴"),
            "half_open": ("background-color: #eab30820; border: 1px solid #eab30830;", "#eab308", "📶"),
        }
        
        style, color, icon = state_styles.get(breaker.state, state_styles["closed"])
        
        self.setStyleSheet(f"""
            QFrame {{
                {style}
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"color: {color}; font-size: 14pt;")
        layout.addWidget(icon_label)
        
        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        name_label = QLabel(name)
        name_label.setStyleSheet(f"font-weight: 600; color: {color};")
        info_layout.addWidget(name_label)
        
        stats_label = QLabel(f"{breaker.failure_count} failures • {breaker.success_rate * 100:.0f}% success")
        stats_label.setStyleSheet(f"color: {color}90; font-size: 9pt;")
        info_layout.addWidget(stats_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # State badge
        badge = QLabel(breaker.state.replace("_", " ").title())
        badge.setStyleSheet(f"""
            background-color: {color}30;
            color: {color};
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 9pt;
        """)
        layout.addWidget(badge)
        
        # Reset button (only for open state)
        if breaker.state == "open":
            reset_btn = QPushButton("↺ Reset")
            reset_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {color};
                    border: 1px solid {color}50;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 9pt;
                }}
                QPushButton:hover {{
                    background-color: {color}20;
                }}
            """)
            reset_btn.clicked.connect(lambda: self.reset_clicked.emit(name))
            layout.addWidget(reset_btn)


class IngestionHealthPanel(QWidget):
    """
    Panel showing real-time data ingestion health.
    Monitors channels, frame drops, and circuit breakers.
    """
    
    # Signals
    health_updated = pyqtSignal(str)  # overall health status
    
    def __init__(
        self,
        api_url: str = "http://127.0.0.1:5001/api/jetdrive",
        poll_interval: int = 2000,
        compact: bool = False,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        self._api_url = api_url
        self._poll_interval = poll_interval
        self._compact = compact
        
        # Data
        self._overall_health = "unknown"
        self._channels: Dict[str, ChannelHealth] = {}
        self._frame_stats = FrameStats()
        self._circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self._last_update: Optional[str] = None
        self._loading = False
        
        # Network manager
        self._network_manager = QNetworkAccessManager(self)
        self._network_manager.finished.connect(self._on_request_finished)
        
        # Poll timer
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._fetch_health)
        
        self._build_ui()
        
        # Start polling
        QTimer.singleShot(100, self._fetch_health)
        self._poll_timer.start(self._poll_interval)
        
    def _build_ui(self) -> None:
        """Build the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        card = Card()
        
        # Header
        header = CardHeader()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Icon (changes with health)
        self.icon_label = QLabel("📊")
        self.icon_label.setStyleSheet(f"""
            background-color: {get_health_bg_color('unknown')};
            border-radius: 8px;
            padding: 8px;
            font-size: 16pt;
        """)
        header_layout.addWidget(self.icon_label)
        
        title_section = QVBoxLayout()
        title_section.setSpacing(2)
        
        title_row = QHBoxLayout()
        title = CardTitle("Ingestion Health")
        title_row.addWidget(title)
        
        self.live_pulse = LivePulse(False)
        title_row.addWidget(self.live_pulse)
        title_row.addStretch()
        
        title_section.addLayout(title_row)
        
        desc = CardDescription("Real-time data pipeline status")
        title_section.addWidget(desc)
        
        header_layout.addLayout(title_section)
        header_layout.addStretch()
        
        # Status badge
        self.status_badge = QLabel("Unknown")
        self.status_badge.setStyleSheet(f"""
            background-color: {get_health_bg_color('unknown')};
            color: {get_health_color('unknown')};
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
                color: {COLORS['muted_foreground']};
            }}
            QPushButton:hover {{
                background-color: {COLORS['muted']};
                border-radius: 16px;
            }}
        """)
        refresh_btn.clicked.connect(self._fetch_health)
        header_layout.addWidget(refresh_btn)
        
        header_widget = QWidget()
        header_widget.setLayout(header_layout)
        header.addWidget(header_widget)
        card.addWidget(header)
        
        # Content
        content = CardContent()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(16)
        
        # Quick stats row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
        
        # Channels stat
        self.channels_stat = self._create_stat_box("📡", "Channels", "0 / 0")
        stats_layout.addWidget(self.channels_stat)
        
        # Frames stat
        self.frames_stat = self._create_stat_box("📊", "Frames", "0.0% drop")
        stats_layout.addWidget(self.frames_stat)
        
        # Circuits stat
        self.circuits_stat = self._create_stat_box("⚡", "Circuits", "0 / 0 active")
        stats_layout.addWidget(self.circuits_stat)
        
        content_layout.addLayout(stats_layout)
        
        # No data message
        self.no_data_label = QLabel("📡 No Active Data Stream\n\nStart the hardware monitor to see ingestion health.")
        self.no_data_label.setStyleSheet(f"""
            color: {COLORS['muted_foreground']};
            padding: 24px;
            text-align: center;
        """)
        self.no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_data_label.setWordWrap(True)
        content_layout.addWidget(self.no_data_label)
        
        # Channels section (collapsible in full mode)
        self.channels_container = QWidget()
        channels_layout = QVBoxLayout(self.channels_container)
        channels_layout.setContentsMargins(0, 0, 0, 0)
        channels_layout.setSpacing(4)
        
        channels_header = QLabel("Channel Details")
        channels_header.setStyleSheet(f"font-weight: bold; color: {COLORS['text_secondary']};")
        channels_layout.addWidget(channels_header)
        
        self.channels_list = QVBoxLayout()
        channels_layout.addLayout(self.channels_list)
        
        self.channels_container.setVisible(False)
        content_layout.addWidget(self.channels_container)
        
        # Last update
        self.last_update_label = QLabel("Last updated: Never")
        self.last_update_label.setStyleSheet(f"color: {COLORS['muted_foreground']}; font-size: 9pt;")
        self.last_update_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        content_layout.addWidget(self.last_update_label)
        
        content_widget = QWidget()
        content_widget.setLayout(content_layout)
        content.addWidget(content_widget)
        card.addWidget(content)
        
        layout.addWidget(card)
        
    def _create_stat_box(self, icon: str, label: str, value: str) -> QFrame:
        """Create a stat display box."""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        # Header row
        header = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 10pt;")
        header.addWidget(icon_label)
        
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"color: {COLORS['muted_foreground']}; font-size: 9pt;")
        header.addWidget(label_widget)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Value
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        value_label.setObjectName("stat_value")
        layout.addWidget(value_label)
        
        return frame
        
    def _update_stat_value(self, frame: QFrame, value: str, color: Optional[str] = None) -> None:
        """Update a stat box value."""
        label = frame.findChild(QLabel, "stat_value")
        if label:
            label.setText(value)
            if color:
                label.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {color};")
                
    def _fetch_health(self) -> None:
        """Fetch health data from API."""
        if self._loading:
            return
            
        self._loading = True
        
        from PyQt6.QtCore import QUrl
        url = QUrl(f"{self._api_url}/ingestion/health")
        request = QNetworkRequest(url)
        self._network_manager.get(request)
        
    def _on_request_finished(self, reply: QNetworkReply) -> None:
        """Handle API response."""
        self._loading = False
        
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self._update_health_display("unknown")
            reply.deleteLater()
            return
            
        try:
            import json
            from datetime import datetime
            
            data = json.loads(bytes(reply.readAll()).decode())
            
            # Parse response
            self._overall_health = data.get("overall_health", "unknown")
            
            # Parse channels
            self._channels.clear()
            for ch_data in data.get("channels", []):
                ch = ChannelHealth(
                    channel_id=ch_data.get("channel_id", ""),
                    channel_name=ch_data.get("channel_name", ""),
                    health=ch_data.get("health", "unknown"),
                    samples_per_second=ch_data.get("samples_per_second", 0),
                    total_samples=ch_data.get("total_samples", 0),
                    age_seconds=ch_data.get("age_seconds", 0),
                    last_value=ch_data.get("last_value", 0),
                )
                self._channels[ch.channel_id] = ch
                
            # Parse frame stats
            fs = data.get("frame_stats", {})
            self._frame_stats = FrameStats(
                total=fs.get("total", 0),
                dropped=fs.get("dropped", 0),
                drop_rate=fs.get("drop_rate", 0),
            )
            
            # Parse circuit breakers
            self._circuit_breakers.clear()
            for name, cb_data in data.get("circuit_breakers", {}).items():
                self._circuit_breakers[name] = CircuitBreakerState(
                    state=cb_data.get("state", "closed"),
                    failure_count=cb_data.get("failure_count", 0),
                    success_rate=cb_data.get("success_rate", 1.0),
                )
                
            self._last_update = datetime.now().strftime("%H:%M:%S")
            self._update_health_display(self._overall_health)
            
        except Exception as e:
            print(f"Error parsing health data: {e}")
            self._update_health_display("unknown")
            
        reply.deleteLater()
        
    def _update_health_display(self, health: str) -> None:
        """Update the UI with current health data."""
        # Update status badge
        self.status_badge.setText(f"{get_health_icon(health)} {health.title()}")
        self.status_badge.setStyleSheet(f"""
            background-color: {get_health_bg_color(health)};
            color: {get_health_color(health)};
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 9pt;
            font-weight: bold;
        """)
        
        # Update icon
        self.icon_label.setStyleSheet(f"""
            background-color: {get_health_bg_color(health)};
            border-radius: 8px;
            padding: 8px;
            font-size: 16pt;
        """)
        
        # Update pulse
        self.live_pulse.setActive(health != "unknown" and len(self._channels) > 0)
        
        # Update stats
        healthy_count = sum(1 for ch in self._channels.values() if ch.health == "healthy")
        total_count = len(self._channels)
        self._update_stat_value(
            self.channels_stat,
            f"{healthy_count} / {total_count}",
            get_health_color(health)
        )
        
        drop_severity = "critical" if self._frame_stats.drop_rate > 5 else "warning" if self._frame_stats.drop_rate > 1 else "healthy"
        self._update_stat_value(
            self.frames_stat,
            f"{self._frame_stats.drop_rate:.1f}% drop",
            get_health_color(drop_severity)
        )
        
        open_circuits = sum(1 for cb in self._circuit_breakers.values() if cb.state == "open")
        total_circuits = len(self._circuit_breakers)
        circuit_color = "#ef4444" if open_circuits > 0 else "#22c55e"
        self._update_stat_value(
            self.circuits_stat,
            f"{total_circuits - open_circuits} / {total_circuits} active",
            circuit_color
        )
        
        # Show/hide no data message
        self.no_data_label.setVisible(total_count == 0)
        self.channels_container.setVisible(total_count > 0 and not self._compact)
        
        # Update channels list
        if total_count > 0:
            # Clear existing
            while self.channels_list.count():
                item = self.channels_list.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                    
            # Add channel rows sorted by health
            health_order = {"critical": 0, "unhealthy": 1, "warning": 2, "stale": 3, "healthy": 4}
            sorted_channels = sorted(
                self._channels.values(),
                key=lambda ch: health_order.get(ch.health, 5)
            )
            
            for channel in sorted_channels:
                row = ChannelHealthRow(channel)
                self.channels_list.addWidget(row)
                
        # Update last update
        if self._last_update:
            self.last_update_label.setText(f"Last updated: {self._last_update}")
            
        self.health_updated.emit(health)
        
    def get_overall_health(self) -> str:
        """Get the overall health status."""
        return self._overall_health
        
    def get_channels(self) -> Dict[str, ChannelHealth]:
        """Get channel health data."""
        return self._channels.copy()
        
    def stop_polling(self) -> None:
        """Stop the health polling timer."""
        self._poll_timer.stop()
        
    def start_polling(self) -> None:
        """Start the health polling timer."""
        self._poll_timer.start(self._poll_interval)
        
    def hideEvent(self, event) -> None:
        """Stop polling when panel is hidden."""
        super().hideEvent(event)
        self.stop_polling()
        
    def showEvent(self, event) -> None:
        """Resume polling when panel is shown."""
        super().showEvent(event)
        self.start_polling()

