"""
JetDrive Tab - Live Data Monitoring and Simulator
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGroupBox,
    QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor

from api.services.autotune_workflow import AutoTuneWorkflow


class GaugeWidget(QWidget):
    """Simple gauge display widget"""
    
    def __init__(self, label: str, units: str, parent=None):
        super().__init__(parent)
        self.value = 0.0
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Label
        label_widget = QLabel(label)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label_widget)
        
        # Value
        self.value_label = QLabel("0.0")
        value_font = QFont()
        value_font.setPointSize(24)
        value_font.setBold(True)
        self.value_label.setFont(value_font)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)
        
        # Units
        units_label = QLabel(units)
        units_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(units_label)
        
        # Style
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 48))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        self.setPalette(palette)
    
    def set_value(self, value: float, decimals: int = 1):
        """Update the gauge value"""
        self.value = value
        # Simple approach: use % formatting which always works
        if decimals == 0:
            text = "%d" % int(value)
        elif decimals == 1:
            text = "%.1f" % value
        elif decimals == 2:
            text = "%.2f" % value
        else:
            text = "%.3f" % value
        self.value_label.setText(text)


class JetDriveTab(QWidget):
    """Tab for JetDrive live monitoring and simulator"""
    
    def __init__(self, workflow: AutoTuneWorkflow):
        super().__init__()
        self.workflow = workflow
        self.simulator_running = False
        
        self._init_ui()
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_gauges)
        self.update_timer.setInterval(50)  # 20Hz update rate
    
    def _init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("JetDrive Live Dashboard")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Controls
        controls_group = QGroupBox("Simulator Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        self.start_btn = QPushButton("▶️ Start Simulator")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self.start_simulator)
        controls_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹️ Stop Simulator")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_simulator)
        controls_layout.addWidget(self.stop_btn)
        
        self.pull_btn = QPushButton("🚀 Trigger Pull")
        self.pull_btn.setMinimumHeight(40)
        self.pull_btn.setEnabled(False)
        self.pull_btn.clicked.connect(self._trigger_pull)
        controls_layout.addWidget(self.pull_btn)
        
        layout.addWidget(controls_group)
        
        # Live gauges
        gauges_group = QGroupBox("Live Data")
        gauges_layout = QGridLayout(gauges_group)
        gauges_layout.setSpacing(10)
        
        self.rpm_gauge = GaugeWidget("Engine RPM", "RPM")
        gauges_layout.addWidget(self.rpm_gauge, 0, 0)
        
        self.hp_gauge = GaugeWidget("Horsepower", "HP")
        gauges_layout.addWidget(self.hp_gauge, 0, 1)
        
        self.tq_gauge = GaugeWidget("Torque", "ft-lb")
        gauges_layout.addWidget(self.tq_gauge, 0, 2)
        
        self.afr_gauge = GaugeWidget("AFR", "AFR")
        gauges_layout.addWidget(self.afr_gauge, 1, 0)
        
        self.map_gauge = GaugeWidget("MAP", "kPa")
        gauges_layout.addWidget(self.map_gauge, 1, 1)
        
        self.tps_gauge = GaugeWidget("Throttle", "%")
        gauges_layout.addWidget(self.tps_gauge, 1, 2)
        
        layout.addWidget(gauges_group, 1)
        
        # Status
        self.status_label = QLabel("Simulator stopped - Click 'Start Simulator' to begin")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
    
    def start_simulator(self):
        """Start the simulator"""
        try:
            # Import simulator here to avoid loading it if not needed
            from api.services.dyno_simulator import get_simulator
            
            self.simulator = get_simulator()
            self.simulator.start()
            
            self.simulator_running = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.pull_btn.setEnabled(True)
            
            # Start update timer
            self.update_timer.start()
            
            self.status_label.setText("✅ Simulator running - Ready for pulls")
            
        except Exception as e:
            self.status_label.setText(f"❌ Failed to start simulator: {str(e)}")
    
    def stop_simulator(self):
        """Stop the simulator"""
        if self.simulator_running:
            self.update_timer.stop()
            
            try:
                self.simulator.stop()
            except Exception:
                pass
            
            self.simulator_running = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.pull_btn.setEnabled(False)
            
            self.status_label.setText("Simulator stopped")
            
            # Reset gauges
            self.rpm_gauge.set_value(0)
            self.hp_gauge.set_value(0)
            self.tq_gauge.set_value(0)
            self.afr_gauge.set_value(0)
            self.map_gauge.set_value(0)
            self.tps_gauge.set_value(0)
    
    def _trigger_pull(self):
        """Trigger a dyno pull"""
        if self.simulator_running:
            try:
                self.simulator.trigger_pull()
                self.status_label.setText("🚀 Pull in progress...")
            except Exception as e:
                self.status_label.setText(f"❌ Pull failed: {str(e)}")
    
    def _update_gauges(self):
        """Update gauge values from simulator"""
        if not self.simulator_running:
            return
        
        try:
            # Get current channels from simulator
            channels = self.simulator.get_channels()
            
            # Extract values - handle both direct values and nested dicts
            def get_value(data, key, default=0):
                val = data.get(key, default)
                # If it's a dict with 'value' key, extract it
                if isinstance(val, dict) and 'value' in val:
                    return val['value']
                return val if isinstance(val, (int, float)) else default
            
            # Update gauges (using actual channel names from simulator)
            self.rpm_gauge.set_value(get_value(channels, 'Engine RPM', 0), 0)
            self.hp_gauge.set_value(get_value(channels, 'Horsepower', 0), 1)
            self.tq_gauge.set_value(get_value(channels, 'Torque', 0), 1)
            
            # Use average of front/rear AFR
            afr_f = get_value(channels, 'AFR Meas F', 14.7)
            afr_r = get_value(channels, 'AFR Meas R', 14.7)
            afr_avg = (afr_f + afr_r) / 2
            self.afr_gauge.set_value(afr_avg, 2)
            
            self.map_gauge.set_value(get_value(channels, 'MAP kPa', 0), 1)
            self.tps_gauge.set_value(get_value(channels, 'TPS', 0), 1)
            
            # Update status based on simulator state
            sim_state = self.simulator.get_state()
            if sim_state.value == 'pull':
                self.status_label.setText("🚀 Pull in progress...")
            elif sim_state.value == 'idle':
                self.status_label.setText("✅ Simulator running - Ready for pulls")
            elif sim_state.value == 'decel':
                self.status_label.setText("🔽 Decelerating...")
            elif sim_state.value == 'cooldown':
                self.status_label.setText("❄️ Cooling down...")
                
        except Exception as e:
            self.status_label.setText(f"⚠️ Update error: {str(e)}")
