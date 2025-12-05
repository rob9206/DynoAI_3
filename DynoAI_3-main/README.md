# DynoAI

AI-powered dyno tuning toolkit for analyzing WinPEP logs and generating VE and spark correction recommendations.

## Features

- **🌐 Web Interface**: NEW - React/TypeScript frontend with 3D VE visualization
- **VE Correction Analysis**: Analyze dyno logs to generate VE table corrections
- **Adaptive Kernel Smoothing**: NEW - Two-stage kernel system that adapts smoothing based on correction magnitude
  - Preserves large corrections (>3%) with minimal smoothing
  - Smooths small corrections (<1%) aggressively
  - Coverage-weighted neighbor averaging for optimal noise reduction
- **Spark Timing Suggestions**: Generate spark advance/retard recommendations based on knock detection
- **Safe Apply/Rollback System**: Apply VE corrections with automatic clamping, hash verification, and full rollback capability
- **Diagnostics**: Detect anomalies and potential issues in tuning data

## Quick Start

### Web Application (Recommended)

The easiest way to use DynoAI is through the web interface:

```powershell
# One-command startup (starts both backend and frontend)
.\start-web.ps1
```

Then open your browser to `http://localhost:5173`

**Features:**
- Upload CSV files via drag-and-drop
- Real-time analysis progress
- Interactive 3D VE surface visualization
- Download all output files
- View manifest statistics

See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for detailed setup instructions.

### Command Line (Advanced)

#### Standard Dyno Analysis

```bash
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv your_winpep_log.csv \
  --outdir ./output \
  --base_front current_ve_front.csv \
  --base_rear current_ve_rear.csv
```

**Analysis Features:**
- Adaptive kernel smoothing (0-2 passes based on correction magnitude)
- Coverage-weighted neighbor averaging
- Automatic clamping to ±7% for production safety
- Comprehensive diagnostics and anomaly detection

#### Apply VE Corrections

The VE Operations system provides safe, reversible application of correction factors:

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

**Key Features:**
- Automatic clamping to ±7% (default, configurable)
- 4-decimal precision output
- SHA-256 hash verification for rollback safety
- Complete metadata tracking with timestamps
- Dry-run mode for preview

See [README_VE_OPERATIONS.md](README_VE_OPERATIONS.md) for complete documentation.

## Testing

```bash
# Run self-test for main toolkit
python selftest.py

# Run VE operations tests
python -m unittest test_ve_operations -v
```

## Documentation

- [docs/CLAUDE_RAILS.md](docs/CLAUDE_RAILS.md) - Claude Code team rails and workflow
- [TWO_STAGE_KERNEL_INTEGRATION.md](TWO_STAGE_KERNEL_INTEGRATION.md) - Adaptive Kernel v1.3 implementation details
- [README_VE_OPERATIONS.md](README_VE_OPERATIONS.md) - Complete VE Apply/Rollback system documentation
- [Dyno_AI_Tuner_v1_2_README.txt](Dyno_AI_Tuner_v1_2_README.txt) - Main toolkit documentation

## DynoAI Coding Agent (Minimal, Local-First)

- Generate a patch:

  ```bash
  python scripts/dynoai_make_patch.py --goal "..." --files ai_tuner_toolkit_dyno_v1_2.py
  ```

- Apply & test:

  ```bash
  python scripts/dynoai_apply_patch.py patches/<generated>.diff
  ```

- See `docs/DYNOAI_AGENT_WORKFLOW.md` for details.

