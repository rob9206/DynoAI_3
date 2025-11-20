# Experiment Runner: Kernel Registry & Safety Checks

## Overview

The DynoAI experiment runner has been upgraded with a centralized kernel registry, hardened path validation, and comprehensive safety checks. This ensures reproducible, auditable experiments with zero-config kernel resolution.

## Key Features

### 1. Kernel Registry (`experiments/kernel_registry.py`)

Centralized mapping of `idea-id` → `(module, function, defaults)` for all experimental kernels:

- **baseline** / **kernel_weighted_v1**: Weighted neighbor smoothing
- **kernel_knock_aware_v1**: Knock-gated adaptive smoothing
- **k1** / **k1_gradient_limit_v1**: Gradient-limited smoothing (K1)
- **k2** / **k2_coverage_adaptive_v1**: Coverage-adaptive clamping (K2)
- **k3** / **k3_bilateral_v1**: Bilateral median+mean filtering (K3)

**Usage:**
```python
from experiments.kernel_registry import resolve_kernel

kernel_fn, defaults, module_path, func_name = resolve_kernel("k3")
# Returns: (<callable>, {"passes": 2, "sigma": 0.75}, "experiments.protos.k3_bilateral_v1", "kernel_smooth")
```

### 2. Path Validation & Safety

**Auto-creation**: Output directories created automatically with `mkdir(parents=True, exist_ok=True)`

**Traversal protection**: All paths validated against repo root
```python
_resolve_under_root(Path("../../evil"))  # ValueError: Path escapes repo root
```

**Atomic operations**: Fingerprints and summaries written atomically

### 3. Kernel Fingerprinting

Every run writes `kernel_fingerprint.txt`:
```
module=experiments.protos.k3_bilateral_v1
function=kernel_smooth
params={"passes": 2, "sigma": 0.75}
```

Enables:
- No-op detection (compare fingerprints to skip redundant runs)
- Reproducibility audit trail
- Parameter tracking across experiments

### 4. Safety Checks

#### Bin Alignment
Hard-fails if RPM/kPa grids mismatch (no silent reindexing):
```python
_assert_bin_alignment(rpm_new, kpa_new, rpm_base, kpa_base)
# AssertionError: RPM/kPa grid mismatch; no implicit reindex allowed
```

#### Delta Floor
Values < 0.001% reported as 0.000% (noise suppression):
```python
delta = 0.0007  # Raw delta
reported = 0.0 if delta < 1e-3 else delta  # → 0.0
```

#### CSV Quote Sanitization
Strips leading quotes from sanitized numeric cells:
```python
_strip_quote_num(" '1.23")  # → "1.23"
```

### 5. Dry-Run Mode

Test experiment setup without running the full toolkit pipeline:

```bash
python experiments/run_experiment.py \
  --idea-id k2_coverage_adaptive_v1 \
  --csv experiments/outputs/coverage_skew.csv \
  --outdir experiments/k2_test \
  --dry-run
```

Writes:
- `kernel_fingerprint.txt`
- `experiment_summary.json` (status: "DRY_RUN")

## CLI Reference

### Required Arguments
- `--idea-id <str>`: Kernel identifier from registry (e.g., `k3`, `baseline`)
- `--csv <path>`: Input dyno CSV file
- `--outdir <path>`: Output directory (auto-created, must be under repo root)

### Optional Arguments
- `--smooth_passes <int>`: Override kernel default smoothing passes
- `--clamp <float>`: Override kernel default clamp limit (%)
- `--rear_bias <float>`: Rear cylinder bias (default: 0.0)
- `--rear_rule_deg <float>`: Rear spark retard rule (default: 2.0)
- `--hot_extra <float>`: Hot IAT spark retard (default: -1.0)
- `--dry-run`: Skip toolkit execution, write summary only

## Example Workflows

### Quick Validation
```bash
# Dry-run to verify kernel resolution and path safety
python experiments/run_experiment.py \
  --idea-id k3 \
  --csv archive/FXDLS_Wheelie_Spark_Delta-1.csv \
  --outdir experiments/k3_validate \
  --dry-run
```

### Full Experiment Run
```bash
# Run K2 kernel with coverage-adaptive clamping
python experiments/run_experiment.py \
  --idea-id k2_coverage_adaptive_v1 \
  --csv experiments/outputs/coverage_skew.csv \
  --outdir experiments/k2_coverage_skew_test \
  --smooth_passes 3 \
  --clamp 10.0
```

### Baseline Comparison
```bash
# Run baseline, then K3, compare delta
python experiments/run_experiment.py \
  --idea-id baseline \
  --csv data.csv \
  --outdir experiments/baseline

python experiments/run_experiment.py \
  --idea-id k3 \
  --csv data.csv \
  --outdir experiments/k3_vs_baseline
# Delta auto-computed if experiments/baseline/VE_Correction_Delta_DYNO.csv exists
```

## Test Suite

### Path Validation (`tests/test_runner_paths.py`)
- ✓ Output directory auto-creation
- ✓ Traversal attempt rejection
- ✓ Invalid idea-id rejection

### Fingerprinting (`tests/test_fingerprint.py`)
- ✓ Fingerprint content validation
- ✓ All registered kernels generate fingerprints

### Bin Alignment (`tests/test_bin_alignment.py`)
- ✓ Mismatched grids trigger hard failure

### Delta Floor (`tests/test_delta_floor.py`)
- ✓ Sub-0.001% deltas floored to 0.000%

**Run tests:**
```bash
pytest tests/test_runner_paths.py -v
pytest tests/test_fingerprint.py -v
pytest tests/test_bin_alignment.py -v
pytest tests/test_delta_floor.py -v
```

## Output Structure

After a successful run, `<outdir>/` contains:

```
<outdir>/
├── kernel_fingerprint.txt       # Module/function/params
├── experiment_summary.json      # Metrics, duration, status
├── manifest.json                # Toolkit manifest (if not dry-run)
├── VE_Correction_Delta_DYNO.csv # VE correction factors
├── Diagnostics_Report.txt       # Errors/warnings
└── ... (other toolkit outputs)
```

## Troubleshooting

### Import Errors
```
ModuleNotFoundError: No module named 'experiments.kernel_registry'
```
**Solution:** Run from repo root, ensure `sys.path` includes experiments directory.

### Path Traversal Errors
```
ValueError: Path escapes repo root: /some/path/outside
```
**Solution:** Use relative paths under repo root or absolute paths within repo.

### Unknown Kernel
```
ValueError: Unknown idea-id 'xyz'. Known: baseline, k1, k2, k3, ...
```
**Solution:** Check `experiments/kernel_registry.py` for valid `idea-id` values.

### Bin Alignment Failure
```
AssertionError: RPM/kPa grid mismatch; no implicit reindex allowed
```
**Solution:** Ensure baseline and experimental runs use identical dyno CSV files or regenerate baseline.

## Migration from Old Runner

Old syntax (manual module names):
```bash
python experiments/run_experiment.py --idea-id k3_bilateral_v1 ...
```

New syntax (short aliases or full names):
```bash
python experiments/run_experiment.py --idea-id k3 ...  # Short alias
# OR
python experiments/run_experiment.py --idea-id k3_bilateral_v1 ...  # Full name
```

Both work - registry handles resolution automatically.

## Future Enhancements

- [ ] Parallel experiment execution
- [ ] Automatic baseline regeneration on CSV changes
- [ ] Kernel parameter sweep automation
- [ ] Delta heatmap visualization
- [ ] Experiment result caching

## References

- Kernel implementations: `experiments/protos/`
- Registry source: `experiments/kernel_registry.py`
- Runner source: `experiments/run_experiment.py`
- Test suite: `tests/test_*.py`
