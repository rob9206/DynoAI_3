# DynoAI v3

**Intelligent Dyno Tuning System for Harley-Davidson ECM Calibration**

DynoAI transforms WinPEP dyno logs into production-ready VE correction tables with AI-powered smoothing, safety-enforced clamping, and hash-verified rollback capabilities.

---

## Quick Start

### Prerequisites
- Python 3.11 or higher
- WinPEP dyno log (CSV format)
- Base VE tables (optional, for absolute output)

### Installation

```bash
# Clone the repository
git clone https://github.com/rob9206/DynoAI_3.git
cd DynoAI_3

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

```bash
# Analyze dyno log and generate VE corrections
python core/ai_tuner_toolkit_dyno_v1_2.py \
    --csv tables/WinPEP_Sample.csv \
    --outdir outputs/run1

# Apply VE corrections to base table
python -c "from core.ve_operations import VEApply; \
VEApply().apply(
    base_ve_path='tables/FXDLS_Wheelie_VE_Base_Front.csv',
    factor_path='outputs/run1/VE_Correction_Delta_DYNO.csv',
    output_path='outputs/run1/VE_Front_Updated.csv',
    max_adjust_pct=7.0
)"
```

### Expected Outputs

- `VE_Correction_Delta_DYNO.csv` - Percentage corrections (±7% default)
- `Diagnostics_Report.txt` - Comprehensive analysis summary
- `Spark_Adjust_Suggestion_*.csv` - Timing recommendations
- `Coverage_*.csv` - Data quality heatmaps
- `manifest.json` - Run metadata with fingerprint

---

## Project Structure

```
DynoAI_3/
├── core/                   # Core engine [MATH-CRITICAL]
│   ├── ai_tuner_toolkit_dyno_v1_2.py   # Main CLI engine
│   ├── ve_operations.py                 # VE apply/rollback with hash verification
│   ├── io_contracts.py                  # Path safety & file fingerprinting
│   └── dynoai/                          # Shared utilities
│       ├── api/                         # Flask blueprints
│       └── clients/                     # API clients (xAI)
├── tests/                  # Comprehensive test suite
│   ├── selftest.py                      # Smoke test (synthetic CSV)
│   ├── acceptance_test.py               # VE operations (8 scenarios)
│   ├── unit/                            # PyTest unit tests (7 tests)
│   ├── integration/                     # PyTest integration tests (8 tests)
│   └── kernels/                         # Kernel harness tests (4 tests)
├── experiments/            # Experimental smoothing kernels [MATH-CRITICAL]
│   ├── run_experiment.py                # Kernel experiment runner
│   └── protos/                          # Experimental kernel implementations
├── scripts/                # Automation & maintenance
│   ├── dynoai_safety_check.ps1          # Full test suite runner
│   ├── clean_workspace.py               # Cleanup utility
│   └── ...
├── tables/                 # Reference VE tables & sample data
├── web_service/            # Flask REST API (optional)
├── docs/                   # Documentation
│   ├── DYNOAI_ARCHITECTURE_OVERVIEW.md  # System architecture
│   └── DYNOAI_SAFETY_RULES.md           # Safety policies
└── README.md               # This file
```

---

## Safety Features

### Clamping Enforcement
- **Default:** ±7% corrections (multipliers: 0.93 to 1.07)
- **Maximum:** ±15% (configurable, not recommended)
- Applied before VE table multiplication

### Hash Verification
- SHA-256 fingerprinting of all VE operations
- Rollback blocked if base table modified
- Complete audit trail in metadata

### Path Safety
- All file operations validated by `io_contracts.py`
- Prevents path traversal outside repository
- Output directories must be within repo root

### Test Coverage
- **Expected:** 30+ tests (selftests, acceptance, unit, integration, kernels)
- **CI/CD:** Runs on every push/PR
- **Invariants:** Clamping, coverage, bin alignment

---

## Testing

### Quick Smoke Test
```bash
python tests/selftest.py
```

### Full Regression Suite
```bash
# PowerShell (recommended)
pwsh scripts/dynoai_safety_check.ps1 -RunSelftests -RunKernels -RunPytest

# Or run individually
python tests/selftest.py
python tests/acceptance_test.py
python -m pytest tests/unit tests/integration -v
python tests/kernels/test_k1.py
python tests/kernels/test_k2.py
python tests/kernels/test_k3.py
```

### Expected Results
- Selftests: 2/2 passing
- Acceptance: 8/8 passing
- Kernel harnesses: 4/4 passing
- PyTest: 15/15 passing (7 unit + 8 integration)

---

## Development Workflow

1. **Collect dyno data** (WinPEP CSV log)
2. **Run DynoAI engine** to generate corrections
3. **Review diagnostics** and coverage reports
4. **Apply VE corrections** to base tables
5. **Flash to ECM** (external tool, e.g., TunerPro)
6. **Test on dyno** to verify AFR targets
7. **Rollback if needed** using hash-verified metadata

---

## Key Algorithms

### AFR Error → VE Correction
```
VE_correction = 1.0 + ((afr_cmd - afr_meas) / afr_cmd) * gain
```

### Multi-Pass Smoothing
- Configurable kernel (K1 gradient-limited, K2 coverage-adaptive, K3 bilateral)
- Default: 2 passes
- Experimental kernels in `experiments/protos/`

### Coverage-Weighted Averaging
- Bins with more measurements weighted higher
- Gradient limiting prevents sharp transitions
- Hot/cold compensation for thermal effects

---

## CLI Reference

```bash
python core/ai_tuner_toolkit_dyno_v1_2.py \
    --csv <path-to-winpep-log.csv> \
    --outdir <output-directory> \
    [--base_front <front-ve-table.csv>] \
    [--base_rear <rear-ve-table.csv>] \
    [--clamp_pct <1-15>] \
    [--smoothing_passes <1-5>] \
    [--kernel <baseline|k1|k2|k3>] \
    [--dry-run]
```

**Key Flags:**
- `--csv`: WinPEP dyno log (required)
- `--outdir`: Output directory (required)
- `--clamp_pct`: Clamping limit (default: 7.0, max: 15.0)
- `--smoothing_passes`: Smoothing iterations (default: 2)
- `--dry-run`: Validate inputs without execution

---

## Configuration

### Cursor AI Model Selection
See `.cursorrules.md` for automatic model selection:
- **Sonnet 4.5 Max**: Math-critical files, refactoring, safety operations
- **Sonnet 4**: Normal development, tests, documentation
- **Haiku**: Trivial edits, typos, formatting

### Security Scanning
Snyk rules configured in `.cursor/rules/snyk_rules.mdc`

---

## Troubleshooting

### Import Errors
```bash
# Ensure you're in the repo root
cd /path/to/DynoAI_3

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Test Failures
```bash
# Run individual tests to isolate failures
python tests/selftest.py
python -m pytest tests/unit/test_bin_alignment.py -v

# Check test logs
cat outputs/test_*/Diagnostics_Report.txt
```

### VE Rollback Hash Mismatch
```
ERROR: Hash mismatch - base table may have been modified
```
**Solution:** Ensure base VE table hasn't been manually edited. Use original base table or create new correction.

---

## Contributing

### Before Committing
1. Run full test suite: `pwsh scripts/dynoai_safety_check.ps1 -RunSelftests -RunKernels -RunPytest`
2. Ensure all tests pass (30+ tests)
3. Update documentation if behavior changed
4. Follow safety rules in `docs/DYNOAI_SAFETY_RULES.md`

### Math-Critical Changes
Changes to `core/ai_tuner_toolkit_dyno_v1_2.py`, `core/ve_operations.py`, `core/io_contracts.py`, or `experiments/protos/*.py` require:
- Design document
- Validation plan with before/after comparisons
- Maintainer approval
- Extended review period (3-7 days minimum)

---

## Version History

- **v3.0.0** (2025-11-16) - Minimal production-focused repository
  - Documentation-first initialization
  - Core structure defined
  - Ready for DynoAI_2 code migration

---

## Documentation

- **Architecture:** `docs/DYNOAI_ARCHITECTURE_OVERVIEW.md`
- **Safety Rules:** `docs/DYNOAI_SAFETY_RULES.md`
- **Cursor AI Config:** `.cursorrules.md`

---

## License

**Proprietary - Internal Use Only**

---

## Support

For issues, questions, or contributions:
- **Security Issues:** Contact repository maintainers immediately
- **Math Questions:** Require maintainer approval before changes
- **General Questions:** Open an issue with detailed context

---

**DynoAI v3** - Precision tuning with safety-first engineering.
