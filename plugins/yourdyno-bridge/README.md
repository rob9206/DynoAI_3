# DynoAI Bridge Plugin for YourDyno

A YourDyno plugin that streams live dyno data to DynoAI via TCP for real-time VE auto-tuning.

## How It Works

```
YourDyno UnaVision
  └─ DynoAIBridge.dll (this plugin)
       ├─ Receives OnDynoDataReceived events from YourDyno
       ├─ Maps OneProcessedSample to JSON (RPM, HP, torque, AFR, MAP, etc.)
       └─ TCP server on localhost:9877 → JSON-lines to DynoAI backend
```

The plugin implements YourDyno's `IDataIOProvider` interface via MEF. When YourDyno loads it, the plugin:

1. Subscribes to `DynoDataConnection.OnDynoDataReceived` for push-based live data
2. Starts a TCP server on `localhost:9877`
3. Converts each `OneProcessedSample` into a JSON object and streams it to connected DynoAI clients
4. Scans other plugins for AFR/MAP data (from CAN readers, wideband plugins, etc.)

## Building

### Prerequisites

- Visual Studio 2022+ or `dotnet` CLI with .NET Framework 4.8.1 targeting pack
- YourDyno UnaVision installed

### Setup

```powershell
# 1. Copy required DLLs from YourDyno
.\setup-libs.ps1

# 2. Open in Visual Studio and build, or use CLI:
dotnet build -c Release
```

### Install

```powershell
# Copy built DLL to YourDyno plugin directory (may need admin)
.\install-plugin.ps1

# Or manually:
copy DynoAIBridge\bin\Release\net481\DynoAIBridge.dll C:\ProgramData\YourDynoPlugins\
```

Restart YourDyno after installing.

## Configuration

In YourDyno, click the **DynoAI Bridge Settings...** menu entry to configure:

| Setting | Default | Description |
|---------|---------|-------------|
| TCP Port | 9877 | Port for DynoAI connection |
| AFR Front (aux index) | -1 | Aux input carrying front cylinder AFR (-1 = auto) |
| AFR Rear (aux index) | -1 | Aux input carrying rear cylinder AFR (-1 = auto) |
| MAP kPa (aux index) | -1 | Aux input carrying MAP sensor (-1 = auto) |
| TPS (aux index) | -1 | Aux input carrying throttle position (-1 = auto) |
| IAT (aux index) | -1 | Aux input carrying intake air temp (-1 = auto) |
| Engine Temp (aux index) | -1 | Aux input carrying engine temp (-1 = auto) |
| Auto-detect from plugins | true | Scan other YourDyno plugins for AFR/MAP |
| Max sample rate | 0 | Rate limit in Hz (0 = use YourDyno's native rate) |

Configuration is saved to `%AppData%\DynoAIBridge\config.json`.

## JSON Protocol

Each line sent over TCP is a complete JSON object:

```json
{
  "ts": 1234.567,
  "elapsed": 45.2,
  "engine_rpm": 3500.0,
  "roller_rpm": 1200.0,
  "engine_hp": 85.3,
  "wheel_hp": 72.5,
  "engine_torque_ftlb": 92.1,
  "wheel_torque_ftlb": 78.4,
  "engine_torque_nm": 124.9,
  "wheel_torque_nm": 106.3,
  "engine_kw": 63.6,
  "wheel_kw": 54.1,
  "afr_front": 13.2,
  "afr_rear": 12.8,
  "map_kpa": 65.0,
  "egt": [650.0, 680.0],
  "aux": [0.5, 1.2, 13.2, 12.8],
  "ambient_temp_f": 72.0,
  "ambient_pressure_inhg": 29.92,
  "ambient_humidity": 45.0,
  "is_logging": true,
  "dyno_connected": true,
  "dyno_type": "Ultimate"
}
```

The first line after connection is a handshake:

```json
{"type":"hello","plugin":"DynoAIBridge","version":"1.0.0","port":9877}
```

## Data Sources for AFR and MAP

YourDyno natively provides RPM, torque, and power. AFR and MAP (required for VE correction) come from:

1. **Auxiliary inputs** (`aux[]`) - wideband O2 sensor or MAP sensor connected to YourDyno's aux channels
2. **Other plugins** - CAN bus reader, OBD plugin, or wideband plugin that provides named channels
3. **Parallel capture** - DynoAI can also capture AFR directly from Innovate serial sensors

Configure the aux channel mapping in the settings dialog, or enable auto-detection to let the plugin scan other plugins for matching channel names.
