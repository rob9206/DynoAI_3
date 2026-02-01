# DynoAI PyQt6 Migration Plan

## Executive Summary

This document outlines the comprehensive plan to migrate DynoAI's frontend from a React/TypeScript web application to a native PyQt6 desktop application. The migration will provide better integration with local hardware (JetDrive dyno), improved real-time performance, and a more streamlined deployment for tuning shop environments.

---

## 1. Current Architecture Analysis

### 1.1 Technology Stack (React Frontend)
| Component | Technology |
|-----------|------------|
| Framework | React 19 + TypeScript |
| Build Tool | Vite |
| Styling | Tailwind CSS 4.x |
| State Management | React Query (TanStack) |
| Routing | React Router 7.x |
| Charts | Recharts, D3.js |
| 3D Visualization | Three.js |
| Real-time | Polling (React Query) |
| UI Components | Radix UI primitives |
| Animations | Framer Motion |
| HTTP Client | Axios |

### 1.2 Pages Inventory

| Page | File | Complexity | Key Features |
|------|------|------------|--------------|
| **JetDrive Command Center** | `JetDriveAutoTunePage.tsx` | ⭐⭐⭐⭐⭐ | Live gauges, VE table, run detection, AFR targets, audio capture, hardware monitoring |
| **Dashboard** | `Dashboard.tsx` | ⭐⭐⭐ | File upload, analysis config, progress tracking |
| **Results** | `Results.tsx` | ⭐⭐⭐⭐ | VE heatmap, 3D surface, diagnostics, session replay |
| **Jetstream Live Feed** | `JetstreamPage.tsx` | ⭐⭐⭐ | Real-time data stream, run cards |
| **Run Detail** | `RunDetailPage.tsx` | ⭐⭐⭐ | Individual run analysis |
| **Time Machine** | `TimeMachinePage.tsx` | ⭐⭐⭐ | Timeline diff view, rollback |
| **History** | `History.tsx` | ⭐⭐ | Run list, filtering |
| **Tuning Wizards** | `TuningWizardsPage.tsx` | ⭐⭐⭐ | Guided tuning workflows |
| **VE Heatmap Demo** | `VEHeatmapDemo.tsx` | ⭐⭐ | Visualization playground |

### 1.3 Component Categories

#### Core UI Components (47 files in `/components/ui/`)
- Buttons, Cards, Inputs, Labels
- Tabs, Accordions, Dialogs, Sheets
- Selects, Sliders, Switches, Progress
- Tooltips, Badges, Alerts
- Tables, Scroll Areas

#### Domain-Specific Components

**JetDrive Components** (`/components/jetdrive/`):
- `JetDriveLiveDashboard.tsx` - Real-time gauge dashboard
- `LiveVETable.tsx` - Editable VE correction grid
- `AFRTargetTable.tsx` - Target AFR configuration
- `AudioCapturePanel.tsx` - Knock detection recording
- `AudioWaveform.tsx` - Waveform visualization
- `HardwareTab.tsx` - Hardware connection management
- `IngestionHealthPanel.tsx` - Data pipeline status
- `InnovateAFRPanel.tsx` - Wideband sensor display
- `RunComparisonChart.tsx` - Multi-run overlay
- `SessionReplayPanel.tsx` - Tuning decision playback
- `StageConfigPanel.tsx` - Stage tuning setup
- `VirtualECUPanel.tsx` - Simulation controls

**Visualization Components** (`/components/results/`):
- `VEHeatmap.tsx` - Color-coded correction grid
- `VEHeatmapLegend.tsx` - Color scale legend
- `DiagnosticsDetail.tsx` - Anomaly analysis
- `MetricCard.tsx` - Summary statistics

**LiveLink Components** (`/components/livelink/`):
- `LiveLinkGauge.tsx` - Radial gauge widget
- `LiveLinkChart.tsx` - Real-time line chart

### 1.4 Hooks (State & Data Management)

| Hook | Purpose | PyQt6 Equivalent |
|------|---------|------------------|
| `useJetDriveLive` | Real-time dyno data polling | QTimer + QThread worker |
| `useAudioCapture` | Browser audio recording | QAudioInput / sounddevice |
| `useVEData` | VE table data fetching | API client + signals |
| `useTimeline` | Diff/rollback history | Model + signals |
| `useDiagnostics` | Anomaly data loading | API client |
| `useIngestionHealth` | Data pipeline status | QTimer polling |
| `useJetstreamProgress` | Async job progress | QThread + signals |

### 1.5 API Integration

**Base URL**: `http://localhost:5001/api/`

**Key Endpoints**:
- `/analyze` - File upload & analysis
- `/status/{runId}` - Job status polling
- `/ve-data/{runId}` - VE correction data
- `/diagnostics/{runId}` - Anomaly report
- `/jetdrive/*` - Hardware communication
- `/runs/*` - Run management
- `/powercore/*` - Power Vision integration

---

## 2. PyQt6 Architecture Design

### 2.1 Application Structure

```
gui/
├── __init__.py
├── main.py                    # Entry point
├── app.py                     # QMainWindow
├── requirements.txt
│
├── api/                       # Backend communication
│   ├── __init__.py
│   ├── client.py             # HTTP client (requests/aiohttp)
│   ├── models.py             # Pydantic data models
│   └── workers.py            # QThread workers for async ops
│
├── styles/                    # Theming
│   ├── __init__.py
│   ├── theme.py              # Dark theme stylesheet
│   └── colors.py             # Color constants
│
├── components/                # Reusable widgets
│   ├── __init__.py
│   ├── cards.py              # Card container widgets
│   ├── buttons.py            # Styled buttons
│   ├── inputs.py             # Text inputs, spinboxes
│   ├── gauges.py             # Radial/linear gauges
│   ├── progress.py           # Progress bars
│   └── tables.py             # Styled table widgets
│
├── widgets/                   # Complex custom widgets
│   ├── __init__.py
│   ├── ve_heatmap.py         # VE correction grid
│   ├── ve_surface_3d.py      # 3D surface (pyqtgraph)
│   ├── live_chart.py         # Real-time line chart
│   ├── audio_waveform.py     # Audio visualization
│   ├── needle_gauge.py       # Analog-style gauge
│   └── afr_table.py          # AFR target editor
│
├── pages/                     # Main page widgets
│   ├── __init__.py
│   ├── jetdrive_page.py      # Command Center
│   ├── dashboard_page.py     # File upload/analysis
│   ├── results_page.py       # Analysis results
│   ├── history_page.py       # Run history
│   ├── jetstream_page.py     # Live feed
│   └── wizards_page.py       # Tuning wizards
│
├── dialogs/                   # Modal dialogs
│   ├── __init__.py
│   ├── settings_dialog.py
│   ├── export_dialog.py
│   └── confirmation_dialog.py
│
└── assets/                    # Static resources
    ├── icon.png
    ├── icons/                # SVG/PNG icons
    └── fonts/                # Custom fonts
```

### 2.2 Main Window Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  QMainWindow                                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Header Bar (QWidget)                                 │  │
│  │  [Logo] [DynoAI v1.2] ─── [Nav Buttons] ─── [Settings]│  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  QStackedWidget (Page Container)                      │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  Current Page Widget                            │  │  │
│  │  │  (JetDrivePage / DashboardPage / ResultsPage)   │  │  │
│  │  │                                                 │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Status Bar (QStatusBar)                              │  │
│  │  [API: Online] [Version] [Hardware Status]            │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Signal/Slot Patterns

**Global Signals (Application-wide events)**:
```python
class AppSignals(QObject):
    # Navigation
    page_changed = pyqtSignal(str)
    
    # API Status
    api_connected = pyqtSignal(bool)
    api_error = pyqtSignal(str)
    
    # JetDrive Hardware
    hardware_connected = pyqtSignal(bool)
    channel_data_received = pyqtSignal(dict)
    run_detected = pyqtSignal(str)
    capture_started = pyqtSignal()
    capture_stopped = pyqtSignal()
    
    # Analysis
    analysis_started = pyqtSignal(str)  # run_id
    analysis_progress = pyqtSignal(int, str)  # progress, message
    analysis_completed = pyqtSignal(str)  # run_id
    analysis_error = pyqtSignal(str)
    
    # Toast notifications
    show_toast = pyqtSignal(str, str)  # message, type
```

### 2.4 Threading Model

```
Main Thread (UI)
    │
    ├── QTimer (100ms) ─── Health Check Worker
    │
    ├── QTimer (500ms) ─── JetDrive Polling Worker
    │
    └── QThreadPool
            ├── API Request Workers
            ├── File Upload Worker
            └── Analysis Worker
```

---

## 3. Component Mapping

### 3.1 React → PyQt6 UI Components

| React Component | PyQt6 Widget | Notes |
|-----------------|--------------|-------|
| `<Button>` | `QPushButton` | Custom stylesheet |
| `<Card>` | `QFrame` | Custom CardWidget class |
| `<Input>` | `QLineEdit` | Styled |
| `<Label>` | `QLabel` | |
| `<Tabs>` | `QTabWidget` | |
| `<Select>` | `QComboBox` | |
| `<Slider>` | `QSlider` | |
| `<Switch>` | `QCheckBox` | Toggle style |
| `<Progress>` | `QProgressBar` | |
| `<Badge>` | `QLabel` | Custom badge class |
| `<Dialog>` | `QDialog` | |
| `<Sheet>` | `QDockWidget` / `QDialog` | Side panel |
| `<Tooltip>` | `QToolTip` | |
| `<ScrollArea>` | `QScrollArea` | |
| `<Table>` | `QTableWidget` | Custom delegates |

### 3.2 Custom Widget Requirements

| Widget | Description | Library |
|--------|-------------|---------|
| `VEHeatmapWidget` | Color-coded 2D grid with tooltips | QTableWidget + custom delegates |
| `VESurface3DWidget` | 3D surface visualization | pyqtgraph GLViewWidget |
| `NeedleGaugeWidget` | Half-circle analog gauge | QPainter custom drawing |
| `LiveChartWidget` | Real-time scrolling line chart | pyqtgraph PlotWidget |
| `AudioWaveformWidget` | Audio waveform display | pyqtgraph or matplotlib |
| `AFRTargetTableWidget` | Editable AFR target grid | QTableWidget |

---

## 4. Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Priority: Critical** | **Effort: Medium**

- [ ] Project structure and build system
- [ ] Dark theme stylesheet
- [ ] Main window with navigation
- [ ] Basic UI components (Card, Button, Input)
- [ ] API client with threading
- [ ] Toast notification system
- [ ] Application settings persistence

**Deliverable**: Working app shell with navigation

### Phase 2: Dashboard & File Analysis (Week 2-3)
**Priority: High** | **Effort: Medium**

- [ ] File upload widget (drag & drop)
- [ ] Analysis configuration panel
- [ ] Progress tracking with worker thread
- [ ] Tuning parameters form
- [ ] Advanced features toggles

**Deliverable**: Can upload files and run analysis

### Phase 3: Results & Visualization (Week 3-4)
**Priority: High** | **Effort: High**

- [ ] VE Heatmap widget with color gradients
- [ ] Heatmap legend
- [ ] 3D VE Surface visualization
- [ ] Results page with tabs
- [ ] File download functionality
- [ ] Diagnostics panel
- [ ] Session replay viewer

**Deliverable**: Full results viewing experience

### Phase 4: JetDrive Live Dashboard (Week 4-6)
**Priority: High** | **Effort: Very High**

- [ ] Hardware connection management
- [ ] Needle gauge widgets
- [ ] Live chart widget
- [ ] Live VE table (editable)
- [ ] AFR target configuration
- [ ] Run detection logic
- [ ] Channel presets
- [ ] Real-time data polling

**Deliverable**: Live dyno monitoring

### Phase 5: Audio & Advanced Features (Week 6-7)
**Priority: Medium** | **Effort: High**

- [ ] Audio capture with sounddevice
- [ ] Waveform visualization
- [ ] Innovate wideband panel
- [ ] Run comparison charts
- [ ] Power opportunities panel

**Deliverable**: Full audio and comparison features

### Phase 6: Secondary Pages (Week 7-8)
**Priority: Medium** | **Effort: Medium**

- [ ] History page with filtering
- [ ] Jetstream live feed
- [ ] Time Machine (timeline/diff)
- [ ] Tuning wizards

**Deliverable**: Complete application

### Phase 7: Polish & Optimization (Week 8-9)
**Priority: Low** | **Effort: Medium**

- [ ] Performance optimization
- [ ] Memory profiling
- [ ] Error handling refinement
- [ ] Keyboard shortcuts
- [ ] Accessibility improvements
- [ ] Installer/packaging

---

## 5. Technical Considerations

### 5.1 Real-Time Data Handling

**Challenge**: React uses useEffect + intervals; PyQt6 needs proper threading.

**Solution**:
```python
class JetDrivePoller(QThread):
    data_received = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, api_url: str, interval_ms: int = 500):
        super().__init__()
        self.api_url = api_url
        self.interval = interval_ms / 1000
        self._running = True
    
    def run(self):
        while self._running:
            try:
                response = requests.get(f"{self.api_url}/live", timeout=2)
                self.data_received.emit(response.json())
            except Exception as e:
                self.error_occurred.emit(str(e))
            time.sleep(self.interval)
    
    def stop(self):
        self._running = False
```

### 5.2 VE Heatmap Implementation

**Challenge**: Complex color mapping, tooltips, cell interaction.

**Solution**: Custom `QTableWidget` with `QStyledItemDelegate`:
```python
class VEHeatmapDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        value = index.data(Qt.ItemDataRole.UserRole)
        color = self.get_color_for_value(value)
        painter.fillRect(option.rect, color)
        # Draw text with contrasting color
        text_color = self.get_text_color(color)
        painter.setPen(text_color)
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, f"{value:+.1f}%")
```

### 5.3 3D Visualization

**Option A**: pyqtgraph (Recommended)
- Native Qt integration
- Good performance
- Simpler API than raw OpenGL

**Option B**: matplotlib + FigureCanvas
- More familiar API
- Slower for large datasets

```python
from pyqtgraph.opengl import GLViewWidget, GLSurfacePlotItem

class VESurface3D(GLViewWidget):
    def __init__(self):
        super().__init__()
        self.surface = GLSurfacePlotItem(computeNormals=False)
        self.addItem(self.surface)
    
    def set_data(self, z_data: np.ndarray, x_data: np.ndarray, y_data: np.ndarray):
        self.surface.setData(x=x_data, y=y_data, z=z_data)
```

### 5.4 Audio Capture

**Library**: `sounddevice` (cross-platform)

```python
import sounddevice as sd
import numpy as np

class AudioCapture(QObject):
    waveform_updated = pyqtSignal(np.ndarray)
    recording_finished = pyqtSignal(np.ndarray, int)
    
    def __init__(self, sample_rate=44100):
        super().__init__()
        self.sample_rate = sample_rate
        self.recording = []
    
    def start_recording(self, duration: float):
        def callback(indata, frames, time, status):
            self.recording.append(indata.copy())
            self.waveform_updated.emit(indata[:, 0])
        
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            callback=callback
        )
        self.stream.start()
```

### 5.5 Theming

**Dark Theme Palette** (matching current React theme):
```python
COLORS = {
    'background': '#09090b',      # zinc-950
    'card': '#18181b',            # zinc-900
    'card_hover': '#27272a',      # zinc-800
    'border': '#27272a',          # zinc-800
    'text': '#fafafa',            # zinc-50
    'text_muted': '#a1a1aa',      # zinc-400
    'primary': '#f97316',         # orange-500
    'primary_hover': '#ea580c',   # orange-600
    'success': '#22c55e',         # green-500
    'warning': '#f59e0b',         # amber-500
    'error': '#ef4444',           # red-500
    'accent': '#3b82f6',          # blue-500
}
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| 3D visualization performance | Medium | High | Use pyqtgraph; fallback to 2D only |
| Audio capture cross-platform | Low | Medium | sounddevice is well-tested |
| Real-time update lag | Medium | Medium | Optimize polling; use signals |
| Theme inconsistency | Low | Low | Create comprehensive stylesheet |
| Memory leaks | Medium | High | Proper cleanup; profiling |

---

## 7. Testing Strategy

### Unit Tests
- API client mocking
- Widget state management
- Color calculation functions

### Integration Tests
- Page navigation
- API communication
- File upload workflow

### Manual Testing Checklist
- [ ] Hardware connection flow
- [ ] Real-time gauge updates
- [ ] VE table editing
- [ ] File analysis end-to-end
- [ ] Theme consistency
- [ ] Window resizing
- [ ] Error handling

---

## 8. Migration Checklist

### Pre-Migration
- [ ] Document all API endpoints used
- [ ] Export color palette
- [ ] List all icons used
- [ ] Identify browser-specific features to replace

### During Migration
- [ ] Maintain feature parity log
- [ ] Track React patterns → PyQt6 patterns
- [ ] Note any API changes needed

### Post-Migration
- [ ] Performance comparison
- [ ] User acceptance testing
- [ ] Documentation update
- [ ] Deprecate React frontend

---

## 9. Dependencies

### Required Python Packages
```
PyQt6>=6.6.0
PyQt6-Charts>=6.6.0
requests>=2.31.0
numpy>=1.24.0
pandas>=2.0.0
pyqtgraph>=0.13.3
sounddevice>=0.4.6
scipy>=1.11.0
pydantic>=2.0.0
```

### Optional (for enhanced features)
```
matplotlib>=3.7.0          # Fallback charts
PyQt6-WebEngine>=6.6.0     # Embedded web content
aiohttp>=3.9.0             # Async HTTP
```

---

## 10. Timeline Summary

| Phase | Duration | Milestone |
|-------|----------|-----------|
| Phase 1 | Week 1-2 | App shell with navigation |
| Phase 2 | Week 2-3 | File upload & analysis |
| Phase 3 | Week 3-4 | Results visualization |
| Phase 4 | Week 4-6 | Live JetDrive dashboard |
| Phase 5 | Week 6-7 | Audio & advanced features |
| Phase 6 | Week 7-8 | Secondary pages |
| Phase 7 | Week 8-9 | Polish & packaging |

**Total Estimated Duration**: 8-9 weeks

---

## Appendix A: Icon Mapping

| React (Lucide) | PyQt6 Alternative |
|----------------|-------------------|
| `<Gauge>` | Custom SVG or QIcon |
| `<Play>`, `<Square>` | Standard icons |
| `<Download>` | QStyle.StandardPixmap |
| `<Settings2>` | Custom SVG |
| `<Activity>` | Custom SVG |
| `<Flame>` | Custom SVG |

Recommendation: Use [Phosphor Icons](https://phosphoricons.com/) SVG files or create custom icon set.

---

## Appendix B: Sample Widget Code

### CardWidget
```python
class CardWidget(QFrame):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet("""
            QFrame#card {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
            layout.addWidget(title_label)
        
        self.content_layout = QVBoxLayout()
        layout.addLayout(self.content_layout)
```

---

*Document Version: 1.0*  
*Last Updated: December 31, 2024*  
*Author: DynoAI Development Team*

