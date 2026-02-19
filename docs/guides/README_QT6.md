# DynoAI Qt6 Desktop Application

## Overview

DynoAI Qt6 is a professional native desktop application for motorcycle dyno tuning analysis. Built with PyQt6, it provides a reliable, fast, and user-friendly interface for VE correction calculation and analysis.

## Features

### ✅ Completed Features

- **📊 Analysis Tab**: Upload and analyze CSV files from dyno runs
  - Background processing with progress tracking
  - Real-time status updates
  - Automatic VE correction calculation
  
- **🔧 JetDrive Tab**: Live data monitoring and simulator
  - Real-time gauges for RPM, HP, Torque, AFR, MAP, TPS
  - Dyno simulator for testing without hardware
  - Trigger dyno pulls and capture data
  
- **📈 Results Tab**: Browse and view analysis results
  - List of all completed runs
  - Run summary with key metrics
  - VE correction grid visualization with color coding
  - Export to PVV, Text, and CSV formats
  
- **⚙️ Settings Tab**: Configure application settings
  - Analysis parameters (smooth passes, clamping)
  - JetDrive/DynowareRT connection settings
  - Output directory configuration
  - Persistent settings storage

### 🎨 Professional UI

- Clean, modern interface with tabbed navigation
- Dark mode support (Fusion style)
- Color-coded VE grid (green=good, yellow=moderate, red=significant)
- Responsive gauges and real-time updates
- Menu bar with File, Tools, and Help menus
- Status bar with progress indicator

## Installation

### Requirements

- Python 3.10 or newer
- Windows 10/11 (tested), Linux/macOS (untested but should work)

### Setup

1. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```powershell
   python dynoai_qt6.py
   ```

## Building Standalone Executable

Build a standalone `.exe` that doesn't require Python installation:

```powershell
.\build_qt6.ps1
```

The executable will be created at `dist\DynoAI.exe`.

### Manual Build

If you prefer to build manually:

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install PyInstaller
pip install pyinstaller

# Build
pyinstaller dynoai_qt6.spec
```

## Usage

### Quick Start

1. **Launch the application**
   - Run `python dynoai_qt6.py` (development)
   - Or run `dist\DynoAI.exe` (standalone build)

2. **Analyze a CSV file**
   - Go to the **Analysis** tab
   - Click **Browse...** and select your dyno log CSV
   - Click **🚀 Run Analysis**
   - Wait for completion (progress bar shows status)
   - View results in the **Results** tab

3. **Test with Simulator**
   - Go to the **JetDrive** tab
   - Click **▶️ Start Simulator**
   - Click **🚀 Trigger Pull** to simulate a dyno run
   - Watch live gauges update in real-time

4. **View Results**
   - Go to the **Results** tab
   - Select a run from the list
   - View run summary and VE correction grid
   - Export results as needed

### Settings

Configure the application in the **Settings** tab:

- **Smooth Passes**: Number of smoothing passes (0-10)
- **Correction Clamp**: Maximum correction percentage (0-30%)
- **DynowareRT IP**: IP address of JetDrive hardware
- **TCP Port**: Port for JetDrive connection
- **Output Directory**: Where to save analysis results

Click **💾 Save Settings** to persist changes.

## Architecture

### Main Components

- **`dynoai_qt6.py`**: Main application entry point and window
- **`dynoai/gui/`**: GUI components (tabs)
  - `analysis_tab.py`: CSV upload and analysis
  - `jetdrive_tab.py`: Live monitoring and simulator
  - `results_tab.py`: Results browser and VE grid viewer
  - `settings_tab.py`: Application settings

### Backend Integration

The Qt6 UI integrates with the existing DynoAI backend:

- **`api/services/autotune_workflow.py`**: Analysis engine
- **`api/services/dyno_simulator.py`**: Dyno simulator
- **`dynoai/core/ve_math.py`**: VE calculation math

### Threading Model

- Main UI runs on Qt event loop (non-blocking)
- Analysis runs in `AnalysisWorker` (QThread)
- Simulator updates on QTimer (50ms = 20Hz)
- All UI updates are thread-safe via signals/slots

## Advantages Over Web UI

### ✅ Reliability

- **No browser dependencies**: Doesn't require Chrome, network, or localhost
- **Native application**: Runs as a proper desktop app
- **Direct hardware access**: Better integration with JetDrive hardware
- **Offline capable**: Works without internet connection

### ✅ Performance

- **Faster startup**: No web server initialization
- **Lower memory**: No browser overhead
- **Native rendering**: Hardware-accelerated Qt widgets
- **Better threading**: Direct access to OS threading

### ✅ User Experience

- **System integration**: Taskbar, system tray, file associations
- **Native dialogs**: File pickers, message boxes
- **Keyboard shortcuts**: Ctrl+O, Ctrl+Q, etc.
- **Window management**: Remembers size, position, last tab

## Troubleshooting

### PyQt6 Import Error

If you get `ModuleNotFoundError: No module named 'PyQt6'`:

```powershell
pip install PyQt6
```

### Simulator Not Starting

If the simulator fails to start:

1. Check Settings tab for correct IP/port
2. Ensure no firewall blocking
3. Check terminal for error messages

### Analysis Fails

If analysis fails:

1. Check CSV file format (must have required columns)
2. View error message in Analysis tab
3. Check `runs/` directory permissions

## Development

### Adding New Features

1. **New Tab**: Create in `dynoai/gui/new_tab.py`
2. **Update Main Window**: Add tab in `dynoai_qt6.py`
3. **Update Spec**: Add imports to `dynoai_qt6.spec`

### Testing

Test the Qt6 installation:

```powershell
python test_qt6.py
```

## License

Same as main DynoAI project.

## Support

For issues or questions:
- Check this README
- Review code comments
- Open an issue on GitHub

---

**Built with ❤️ using PyQt6 and Python**
