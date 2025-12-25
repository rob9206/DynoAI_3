# DynoAI3

**A deterministic, automation-first, post-processing calibration engine for dyno data.**

> Current release: **v1.2.1** — defined once in `dynoai/version.py` and used across code, builds, and docs.

DynoAI3 is a world-class dyno tuning toolkit for Harley-Davidson motorcycles with provable math, explicit boundaries, and OEM-inspired discipline. Analyze dyno logs, generate VE corrections, and integrate with Dynojet Power Vision and Power Core systems—all with deterministic, reproducible results.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![React](https://img.shields.io/badge/react-18-blue.svg)

## What Makes DynoAI3 World-Class

✅ **Deterministic Math** - Same inputs always produce same outputs, bit-for-bit  
✅ **Provable Apply/Rollback** - Exact mathematical inverses with SHA-256 verification  
✅ **Automation-First** - Headless CLI, batch processing, CI-ready workflows  
✅ **Formal Contracts** - Explicit schemas, units, and invariants  
✅ **Math Versioning** - Stable algorithms with version freeze guarantees  
✅ **Production Safety** - Conservative defaults, dry-run mode, rollback protection

## Features

### 🔊 Audio Engine (NEW!)
- **Real-time engine sound synthesis** synchronized with dyno pulls
- **Realistic audio generation** based on RPM, load, and cylinder count
- **Exhaust effects** including deceleration crackle and harmonics
- **Auto-start** during dyno captures for immersive experience
 

### Core Features

### 🎯 Deterministic Core Engine
- **VE Correction Analysis** - Deterministic AFR-to-VE conversion with provable math
- **Three-Kernel System** - K1 (gradient-limited smoothing), K2 (coverage-weighted), K3 (spark logic)
- **Apply/Rollback Symmetry** - Exact mathematical inverses verified by acceptance tests
- **Math Versioning** - Algorithm stability with version freeze guarantees (currently v1.0.0)
- **2D Grid Analysis** - RPM × MAP zone-based analysis (11×9 grid = 99 cells)
- **Conservative Clamping** - Default ±7% limit for production safety

### 🔌 JetDrive Integration
- **Live Data Capture** - Real-time dyno data via KLHDV multicast protocol
- **Auto-Tune Workflow** - Automated capture → analysis → correction pipeline
- **Hardware Testing** - Built-in diagnostics for network and multicast connectivity
- **Provider Discovery** - Automatic detection of Dynojet systems on network

### 📊 Power Vision Support
- **PVV XML Export** - Direct export to Power Vision tune file format
- **Log Import** - Parse Power Vision CSV logs for analysis
- **Tune File Parsing** - Read existing PVV files for reference

### 🛠️ Advanced Features
- **Decel Fuel Management** - Automated deceleration popping elimination
- **Cylinder Balancing** - Per-cylinder AFR equalization for V-twins
- **SHA-256 Verification** - Hash-verified corrections with audit trail
- **Dry-Run Mode** - Preview changes before committing
- **Formal Contracts** - Explicit CSV schemas with validation

## Versioning

- Single source of truth: `dynoai/version.py`
- The Python package, API responses, metrics, Docker images, and docs consume that version at runtime/build time.
- Validate that the importable version matches package metadata:

```powershell
pip install -e .
python -c "import dynoai; print(dynoai.__version__)"
python -c "import importlib.metadata as m; print(m.version('dynoai'))"
```

## Quick Start

### Web Application (Recommended)

```powershell
# Start both backend and frontend
.\start-web.ps1
```

Open your browser to `http://localhost:5173`

**Or start manually:**

```powershell
# Terminal 1: Backend API
cd C:\Dev\DynoAI_3
$env:PYTHONPATH="."
python -c "from api.app import app; app.run(host='127.0.0.1', port=5000)"

# Terminal 2: Frontend
cd C:\Dev\DynoAI_3\frontend
npm run dev
```

### JetDrive Auto-Tune

The JetDrive page provides a complete auto-tuning workflow:

1. **Navigate to JetDrive** tab in the web UI
2. **Run Simulation** or upload a CSV from a real dyno run
3. **View Results** - 2D VE correction grid, AFR analysis, diagnostics
4. **Export** - Download results in multiple formats:
   - **PVV XML** for Power Vision/Power Core import
   - **Text Export** for sharing with AI assistants (ChatGPT, Claude, etc.)
   - **CSV** for manual analysis

### Text Export for AI Analysis

Export comprehensive analysis reports as human-readable text files perfect for sharing with AI assistants:
- Complete performance summary (HP, TQ, samples)
- VE correction grid with all RPM/MAP zones
- AFR error analysis and zone distribution
- Hit count data and diagnostics

See [TEXT_EXPORT_GUIDE.md](docs/TEXT_EXPORT_GUIDE.md) for details.

### Hardware Testing

Before connecting to real Dynojet hardware:

1. Go to **JetDrive → Hardware** tab
2. Click **Run Diagnostics** to verify:
   - Network interfaces detected
   - Multicast support working
   - Port 22344 available
3. Click **Discover** to scan for providers on network
4. Use **Start Monitor** for continuous connection health checks

### Command Line Tools

#### JetDrive Auto-Tune Script

```bash
# Simulate a dyno run (no hardware needed)
python scripts/jetdrive_autotune.py --simulate --run-id test_run

# Analyze existing CSV
python scripts/jetdrive_autotune.py --csv runs/my_run/data.csv --run-id my_analysis

# Live capture from JetDrive (requires hardware)
python scripts/jetdrive_autotune.py --live --duration 60 --run-id dyno_pull
```

#### Standard Analysis

```bash
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv your_winpep_log.csv \
  --outdir ./output \
  --base_front current_ve_front.csv \
  --base_rear current_ve_rear.csv
```

#### VE Operations (Apply/Rollback)

```bash
# Preview corrections (dry-run)
python ve_operations.py apply \
  --base base_ve.csv \
  --factor correction_factors.csv \
  --output ve_updated.csv \
  --dry-run

# Apply corrections
python ve_operations.py apply \
  --base base_ve.csv \
  --factor correction_factors.csv \
  --output ve_updated.csv

# Rollback if needed
python ve_operations.py rollback \
  --current ve_updated.csv \
  --metadata ve_updated_meta.json \
  --output ve_restored.csv
```

## Architecture

```
DynoAI_3/
├── api/                    # Flask REST API
│   ├── app.py             # Main application
│   ├── routes/            # API endpoints
│   │   ├── jetdrive.py    # JetDrive auto-tune API
│   │   ├── powercore.py   # Power Core integration
│   │   └── ...
│   └── services/          # Business logic
│       ├── jetdrive_client.py    # KLHDV protocol
│       ├── autotune_workflow.py  # Unified analysis engine
│       └── ...
├── frontend/              # React/TypeScript UI
│   └── src/
│       ├── pages/
│       │   └── JetDriveAutoTunePage.tsx
│       └── components/
├── scripts/               # CLI tools
│   ├── jetdrive_autotune.py      # Full auto-tune CLI
│   ├── jetdrive_hardware_test.py # Hardware diagnostics
│   └── ...
├── docs/                  # Documentation
└── tests/                 # Test suite
```

## API Endpoints

### JetDrive Auto-Tune

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jetdrive/status` | GET | Check JetDrive system status |
| `/api/jetdrive/analyze` | POST | Run analysis on uploaded CSV |
| `/api/jetdrive/analyze-unified` | POST | Run unified workflow analysis |
| `/api/jetdrive/runs/<id>` | GET | Get run details and results |
| `/api/jetdrive/runs/<id>/pvv` | GET | Download PVV XML export |
| `/api/jetdrive/runs/<id>/export-text` | GET | Download comprehensive text export for AI analysis |
| `/api/jetdrive/runs/<id>/report` | GET | Download diagnostics report |
| `/api/jetdrive/hardware/diagnostics` | GET | Run hardware diagnostics |
| `/api/jetdrive/hardware/discover` | GET | Discover JetDrive providers |

### Core Analysis

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analyze` | POST | Analyze uploaded dyno log |
| `/api/ve-data/<run_id>` | GET | Get VE correction data |
| `/api/download/<run_id>/<file>` | GET | Download output files |
| `/api/health` | GET | System health check |

## Configuration

### Environment Setup

DynoAI uses environment variables for configuration. Three template files are provided:

```bash
# Development (local)
cp .env.example .env

# Staging/Testing
cp .env.staging.example .env

# Production
cp .env.production.example .env
```

**Key Configuration Sections:**

1. **Server Settings** - Host, port, debug mode
2. **Security** - API authentication, secrets
3. **Rate Limiting** - API throttling controls
4. **Storage** - Upload/output directories
5. **Database** - SQLite (dev) or PostgreSQL (prod)
6. **Integrations** - JetDrive, Jetstream, xAI (Grok)
7. **Features** - Enable/disable features
8. **Performance** - Workers, threads, limits

### Required Environment Variables

**For Development:**
```bash
# Minimum required - defaults work for local development
DYNOAI_DEBUG=true
```

**For Production:**
```bash
# Generate a secure secret key
python -c "import secrets; print(secrets.token_hex(32))"

# Required settings
API_AUTH_ENABLED=true
API_KEYS=your_generated_api_key
SECRET_KEY=your_generated_secret
DYNOAI_CORS_ORIGINS=https://yourdomain.com
RATE_LIMIT_STORAGE=redis://redis:6379
DATABASE_URL=postgresql://user:pass@postgres:5432/dynoai
```

### Environment Variables Reference

See `.env.example` for complete documentation of all available environment variables.

**Commonly Used:**

```bash
# JetDrive Network
JETDRIVE_MCAST_GROUP=224.0.2.10  # Multicast group
JETDRIVE_PORT=22344              # UDP port
JETDRIVE_IFACE=0.0.0.0           # Network interface

# API Settings
API_AUTH_ENABLED=true            # Enable API key authentication
RATE_LIMIT_ENABLED=true          # Enable rate limiting
LOG_LEVEL=INFO                   # Logging level (DEBUG, INFO, WARNING, ERROR)

# Feature Flags
FEATURE_VIRTUAL_ECU=true         # Enable virtual ECU simulation
FEATURE_CLOSED_LOOP=true         # Enable closed-loop tuning
```

### AFR Targets (MAP-based)

| MAP Range | Target AFR | Use Case |
|-----------|------------|----------|
| < 50 kPa | 14.7 | Cruise/light load |
| 50-70 kPa | 13.8 | Part throttle |
| 70-85 kPa | 13.2 | Acceleration |
| > 85 kPa | 12.2 | WOT/power |

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run VE math verification suite (comprehensive)
pytest tests/test_ve_math_verification.py -v

# Run specific test modules
pytest tests/api/ -v                    # API tests
pytest tests/test_autotune_workflow.py  # Workflow tests
pytest tests/test_jetdrive_client_protocol.py  # Protocol tests

# Run with coverage
pytest --cov=api --cov=scripts tests/
```

### VE Math Verification
A comprehensive test suite verifies all VE tuning math is deterministic and consistent:
- **25 tests** covering apply/rollback operations, clamping, precision, and kernel behavior
- **Inverse property**: apply → rollback → exact original (verified ±0.001)
- **Determinism**: same input → bit-identical output
- See `docs/VE_MATH_VERIFICATION_REPORT.md` for full verification report

## Documentation

- [VE_MATH_VERIFICATION_REPORT.md](docs/VE_MATH_VERIFICATION_REPORT.md) - Complete math verification report
- [VE_MATH_VERIFICATION_QUICKREF.md](docs/VE_MATH_VERIFICATION_QUICKREF.md) - Quick reference guide
- [JETDRIVE_HARDWARE_TESTING.md](docs/JETDRIVE_HARDWARE_TESTING.md) - Hardware setup guide
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Web app setup
- [README_VE_OPERATIONS.md](README_VE_OPERATIONS.md) - VE apply/rollback system
- [TWO_STAGE_KERNEL_INTEGRATION.md](TWO_STAGE_KERNEL_INTEGRATION.md) - Adaptive kernel details
### Core Specifications
- **[DETERMINISTIC_MATH_SPECIFICATION.md](docs/DETERMINISTIC_MATH_SPECIFICATION.md)** - Complete mathematical specification and world-class positioning
- **[KERNEL_SPECIFICATION.md](docs/KERNEL_SPECIFICATION.md)** - Detailed kernel algorithms (K1, K2, K3) with frozen parameters
- **[DYNOAI_ARCHITECTURE_OVERVIEW.md](docs/DYNOAI_ARCHITECTURE_OVERVIEW.md)** - System architecture and design
- **[README_VE_OPERATIONS.md](README_VE_OPERATIONS.md)** - VE apply/rollback system documentation

### Integration Guides
- **[JETDRIVE_HARDWARE_TESTING.md](docs/JETDRIVE_HARDWARE_TESTING.md)** - Hardware setup and testing
- **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)** - Web application setup
- **[TWO_STAGE_KERNEL_INTEGRATION.md](TWO_STAGE_KERNEL_INTEGRATION.md)** - Adaptive kernel implementation details

### Testing
- **[TESTING.md](docs/TESTING.md)** - Test suite documentation
- **acceptance_test.py** - Formal acceptance tests validating all requirements
- **selftest.py** - Kernel and system validation tests

## Explicit Boundaries

### What DynoAI3 IS
✅ Deterministic post-processing VE calibration engine  
✅ Dyno data analyzer (CSV input)  
✅ VE correction factor generator  
✅ Spark timing suggestion system  
✅ Apply/rollback with hash verification  
✅ Automation-first with headless CLI  
✅ Batch processing and CI-ready  

### What DynoAI3 is NOT
❌ **NOT a dyno controller** - Does not control dynamometers  
❌ **NOT an ECU communication tool** - Does not flash or read ECUs directly  
❌ **NOT real-time** - Post-processing only, not closed-loop  
❌ **NOT adaptive** - No learning across runs, deterministic only  
❌ **NOT ML-based** - Core math is deterministic despite the "AI" name  

These boundaries are intentional and allow DynoAI3 to excel in its specific domain with world-class reliability.

## Comparison with OEM Systems

| System | Deterministic Math | Automation | Formal Contracts | Domain |
|--------|-------------------|------------|------------------|---------|
| ETAS INCA | High | High (COM + MATLAB) | ASAM A2L/MDF | ECU calibration |
| Vector CANape | High | High (API/COM/MATLAB) | ASAM A2L/MDF | ECU calibration |
| MoTeC M1 | High (strategy-dependent) | In-ECU scripting | Package-defined | Motorsport ECU |
| HP Tuners | Medium–High | Low–Medium | Tool-specific | Aftermarket tuning |
| **DynoAI3** | **High (test-proven)** | **High (headless, batch)** | **High (dyno-domain)** | **Dyno post-processing** |

**DynoAI3 achieves world-class status through discipline, not novelty.**

## Requirements

- Python 3.10+
- Node.js 18+ (for frontend)
- Network with multicast support (for JetDrive)

### Python Dependencies

```bash
pip install -r requirements.txt
```

Key packages: Flask, pandas, numpy, scipy

### Frontend Dependencies

```bash
cd frontend
npm install
```

## Safety Notes

⚠️ **Always make backups before applying corrections to your ECU**

- VE corrections are clamped to ±7% by default for safety
- Use dry-run mode to preview changes before applying
- The rollback system maintains full history with hash verification
- Test on a dyno before street use

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest tests/ -v`
4. Submit a pull request

## Support

- Issues: [GitHub Issues](https://github.com/rob9206/DynoAI_3/issues)
- Documentation: See `/docs` folder
