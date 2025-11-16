# Experimental Framework [MATH-CRITICAL]

Research and development environment for new smoothing kernels.

## Expected Files

### Experiment Runner
- `run_experiment.py` - Kernel experiment runner with monkey-patching

### Experimental Kernels (`protos/`)
- `k1_gradient_limit_v1.py` - K1 gradient-limited smoothing
- `k2_coverage_adaptive_v1.py` - K2 coverage-adaptive smoothing
- `k3_bilateral_v1.py` - K3 bilateral smoothing
- `kernel_weighted_v1.py` - Weighted kernel
- `kernel_knock_aware_v1.py` - Knock-aware kernel

## Running Experiments

### Baseline (No Kernel Patching)
```bash
python experiments/run_experiment.py \
    --idea-id baseline \
    --csv tables/WinPEP_Sample.csv \
    --outdir experiments/baseline_test
```

### With Experimental Kernel
```bash
python experiments/run_experiment.py \
    --idea-id k2_coverage_adaptive_v1 \
    --csv tables/WinPEP_Sample.csv \
    --outdir experiments/k2_test
```

### Dry-Run Validation
```bash
python experiments/run_experiment.py \
    --idea-id k1 \
    --csv tables/WinPEP_Sample.csv \
    --outdir experiments/k1_dryrun \
    --dry-run
```

## Safety Notice

All experimental kernels are **MATH-CRITICAL**. Changes require:
- Validation against baseline
- Test harness in `tests/kernels/`
- Maintainer approval before promotion to core

This directory is **read-only by default** unless explicitly instructed.

See `docs/DYNOAI_SAFETY_RULES.md` for complete policies.
