# DynoAI3 Automation and Scripting Guide

**Version:** 1.0.0  
**Last Updated:** 2025-12-13

---

## Overview

DynoAI3 is designed as an **automation-first** system, following the philosophy of world-class OEM calibration tools like ETAS INCA and Vector CANape. This document provides comprehensive guidance for automating DynoAI3 workflows.

---

## Table of Contents

1. [Philosophy](#philosophy)
2. [Headless CLI Operations](#headless-cli-operations)
3. [Batch Processing](#batch-processing)
4. [CI/CD Integration](#cicd-integration)
5. [Function-Level APIs](#function-level-apis)
6. [Deterministic Replay](#deterministic-replay)
7. [Workflow Examples](#workflow-examples)
8. [Error Handling](#error-handling)
9. [Best Practices](#best-practices)

---

## Philosophy

### Why Automation Matters

World-class calibration systems prioritize automation because it enables:

- **Repeatability** - Eliminate human error in repetitive tasks
- **Scale** - Process hundreds or thousands of runs
- **Regression Testing** - Validate that changes don't break existing behavior
- **Historical Analysis** - Re-run old data with current algorithms
- **Continuous Integration** - Automated validation in development pipelines

### Automation vs. UI

DynoAI3 treats CLI and automation as **first-class citizens**, not afterthoughts:

- Core math has **no UI dependencies**
- All features accessible via command line
- Function-level APIs for programmatic use
- Deterministic operation enables scripting

This aligns with ETAS INCA (COM + MATLAB), Vector CANape (API/COM/MATLAB), and other professional tools.

---

## Headless CLI Operations

### Core Analysis Pipeline

The main analysis tool runs completely headless:

```bash
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv path/to/dyno_log.csv \
  --outdir ./runs/run_001 \
  --base_front tables/base_ve_front.csv \
  --base_rear tables/base_ve_rear.csv \
  --clamp 7.0 \
  --smooth-passes 2
```

**Parameters:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--csv` | Required | - | Input WinPEP CSV file |
| `--outdir` | Required | - | Output directory for results |
| `--base_front` | Optional | - | Base VE table for front cylinder |
| `--base_rear` | Optional | - | Base VE table for rear cylinder |
| `--clamp` | Optional | 7.0 | Maximum correction percentage (±) |
| `--smooth-passes` | Optional | 2 | Smoothing kernel passes |

**Exit Codes:**

- `0` - Success
- `1` - Invalid arguments
- `2` - File not found
- `3` - Invalid CSV format
- `4` - Validation error

### VE Apply/Rollback CLI

Apply corrections with hash verification:

```bash
# Dry-run (preview without committing)
python ve_operations.py apply \
  --base base_ve.csv \
  --factor correction_factors.csv \
  --output ve_updated.csv \
  --dry-run \
  --max-adjust-pct 7.0

# Apply corrections (commit)
python ve_operations.py apply \
  --base base_ve.csv \
  --factor correction_factors.csv \
  --output ve_updated.csv \
  --max-adjust-pct 7.0

# Rollback corrections
python ve_operations.py rollback \
  --current ve_updated.csv \
  --metadata ve_updated_meta.json \
  --output ve_restored.csv
```

**Parameters:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--base` | Required | - | Base VE table |
| `--factor` | Required | - | Correction factor table |
| `--output` | Required | - | Output VE table path |
| `--dry-run` | Optional | False | Preview without writing output |
| `--max-adjust-pct` | Optional | 7.0 | Maximum adjustment percentage |
| `--current` | Required (rollback) | - | Current VE table to rollback |
| `--metadata` | Required (rollback) | - | Apply metadata JSON file |

**Exit Codes:**

- `0` - Success
- `1` - Invalid arguments
- `2` - File not found
- `3` - Hash verification failed
- `4` - Invalid metadata

---

## Batch Processing

### Process Multiple Runs

```bash
#!/bin/bash
# Process all CSV files in logs/ directory

for log in logs/*.csv; do
  run_id=$(basename "$log" .csv)
  echo "Processing run: $run_id"
  
  python ai_tuner_toolkit_dyno_v1_2.py \
    --csv "$log" \
    --outdir "./runs/$run_id" \
    --base_front tables/base_ve_front.csv \
    --base_rear tables/base_ve_rear.csv \
    --clamp 7.0
  
  if [ $? -eq 0 ]; then
    echo "✓ $run_id completed successfully"
  else
    echo "✗ $run_id failed"
    exit 1
  fi
done

echo "All runs processed"
```

### Parallel Processing

```bash
#!/bin/bash
# Process runs in parallel (4 concurrent jobs)

find logs/ -name "*.csv" | \
  parallel -j 4 --bar \
    'python ai_tuner_toolkit_dyno_v1_2.py \
       --csv {} \
       --outdir "./runs/{/.}" \
       --clamp 7.0'
```

### Sequential Apply Pipeline

```bash
#!/bin/bash
# Analyze → Apply → Verify pipeline

# Step 1: Analyze dyno data
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv dyno_run_001.csv \
  --outdir ./runs/run_001 \
  --clamp 7.0

# Step 2: Apply corrections (dry-run first)
python ve_operations.py apply \
  --base tables/current_ve.csv \
  --factor runs/run_001/VE_Correction_Delta_DYNO.csv \
  --output tables/ve_updated.csv \
  --dry-run

# Step 3: Review dry-run, then commit
read -p "Apply corrections? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  python ve_operations.py apply \
    --base tables/current_ve.csv \
    --factor runs/run_001/VE_Correction_Delta_DYNO.csv \
    --output tables/ve_updated.csv
  
  echo "✓ Corrections applied"
  echo "  Metadata: tables/ve_updated_meta.json"
fi
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: DynoAI Regression Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test-determinism:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run acceptance tests
      run: |
        python acceptance_test.py
    
    - name: Test determinism with golden file
      run: |
        # Run analysis on known-good CSV
        python ai_tuner_toolkit_dyno_v1_2.py \
          --csv tests/fixtures/golden_run.csv \
          --outdir ./test_output \
          --clamp 7.0
        
        # Compare manifest against golden
        python scripts/compare_manifests.py \
          test_output/manifest.json \
          tests/fixtures/golden_manifest.json
        
        # Verify SHA-256 hashes match
        python scripts/verify_hashes.py test_output/
    
    - name: Test apply/rollback symmetry
      run: |
        python tests/test_apply_rollback_symmetry.py
    
    - name: Upload artifacts
      if: failure()
      uses: actions/upload-artifact@v3
      with:
        name: test-results
        path: test_output/
```

### Jenkins Pipeline Example

```groovy
pipeline {
  agent any
  
  stages {
    stage('Setup') {
      steps {
        sh 'pip install -r requirements.txt'
      }
    }
    
    stage('Regression Tests') {
      steps {
        sh 'python acceptance_test.py'
        sh 'python selftest.py'
      }
    }
    
    stage('Batch Analysis') {
      steps {
        sh '''
          for log in test_data/*.csv; do
            run_id=$(basename "$log" .csv)
            python ai_tuner_toolkit_dyno_v1_2.py \
              --csv "$log" \
              --outdir "./jenkins_runs/$run_id" \
              --clamp 7.0 || exit 1
          done
        '''
      }
    }
    
    stage('Validate Determinism') {
      steps {
        sh 'python scripts/validate_determinism.py jenkins_runs/'
      }
    }
  }
  
  post {
    always {
      archiveArtifacts artifacts: 'jenkins_runs/**/*', fingerprint: true
    }
  }
}
```

---

## Function-Level APIs

### Programmatic Use in Python

DynoAI3 can be imported and used as a library:

```python
from pathlib import Path
from ai_tuner_toolkit_dyno_v1_2 import (
    parse_winpep_log,
    bin_afr_measurements,
    kernel_smooth,
    write_matrix_csv
)
from ve_operations import VEApply, VERollback, read_ve_table

# Example: Programmatic analysis
def analyze_dyno_run(csv_path: Path, output_dir: Path, clamp_pct: float = 7.0):
    """Run deterministic dyno analysis."""
    
    # Parse input data
    df = parse_winpep_log(csv_path)
    
    # Bin AFR measurements
    afr_grid = bin_afr_measurements(df, rpm_bins, kpa_bins)
    
    # Apply kernel smoothing
    smoothed_grid = kernel_smooth(afr_grid, passes=2)
    
    # Write output
    output_path = output_dir / "VE_Correction_Delta_DYNO.csv"
    write_matrix_csv(output_path, rpm_bins, kpa_bins, smoothed_grid)
    
    return output_path

# Example: Programmatic apply/rollback
def apply_corrections(base_path: Path, factor_path: Path, output_path: Path):
    """Apply corrections with verification."""
    
    applier = VEApply(max_adjust_pct=7.0)
    applier.apply(base_path, factor_path, output_path)
    
    # Verify apply/rollback symmetry
    meta_path = Path(str(output_path).replace('.csv', '_meta.json'))
    roller = VERollback()
    restored_path = output_path.parent / "verified_restore.csv"
    roller.rollback(output_path, meta_path, restored_path)
    
    # Compare base and restored
    _, _, base_grid = read_ve_table(base_path)
    _, _, restored_grid = read_ve_table(restored_path)
    
    assert base_grid == restored_grid, "Apply/rollback symmetry broken!"
    
    return output_path
```

### Integration with MATLAB/Octave

```matlab
% MATLAB script for batch DynoAI processing

function results = process_dyno_runs(log_dir, output_dir)
    % Get all CSV files
    log_files = dir(fullfile(log_dir, '*.csv'));
    results = struct();
    
    for i = 1:length(log_files)
        log_path = fullfile(log_dir, log_files(i).name);
        [~, run_id, ~] = fileparts(log_files(i).name);
        run_output_dir = fullfile(output_dir, run_id);
        
        % Call DynoAI via Python
        cmd = sprintf(['python ai_tuner_toolkit_dyno_v1_2.py ' ...
                      '--csv "%s" ' ...
                      '--outdir "%s" ' ...
                      '--clamp 7.0'], ...
                      log_path, run_output_dir);
        
        [status, output] = system(cmd);
        
        results.(run_id).status = status;
        results.(run_id).output = output;
        
        if status == 0
            % Load manifest
            manifest_path = fullfile(run_output_dir, 'manifest.json');
            manifest = jsondecode(fileread(manifest_path));
            results.(run_id).manifest = manifest;
        end
    end
end
```

---

## Deterministic Replay

### Golden File Testing

```python
"""Test that analysis results are deterministic."""
import json
from pathlib import Path
import subprocess

def test_deterministic_analysis():
    """Run analysis twice and verify identical results."""
    
    input_csv = Path("tests/fixtures/golden_run.csv")
    
    # Run 1
    output1 = Path("test_output/run1")
    subprocess.run([
        "python", "ai_tuner_toolkit_dyno_v1_2.py",
        "--csv", str(input_csv),
        "--outdir", str(output1),
        "--clamp", "7.0"
    ], check=True)
    
    # Run 2
    output2 = Path("test_output/run2")
    subprocess.run([
        "python", "ai_tuner_toolkit_dyno_v1_2.py",
        "--csv", str(input_csv),
        "--outdir", str(output2),
        "--clamp", "7.0"
    ], check=True)
    
    # Compare manifests
    manifest1 = json.loads((output1 / "manifest.json").read_text())
    manifest2 = json.loads((output2 / "manifest.json").read_text())
    
    # Remove timestamps (allowed to differ)
    del manifest1['timestamp_utc']
    del manifest2['timestamp_utc']
    
    assert manifest1 == manifest2, "Manifests differ between runs!"
    
    # Compare VE correction outputs
    ve1 = (output1 / "VE_Correction_Delta_DYNO.csv").read_text()
    ve2 = (output2 / "VE_Correction_Delta_DYNO.csv").read_text()
    
    assert ve1 == ve2, "VE corrections differ between runs!"
    
    print("✓ Determinism verified")
```

### Historical Comparison

```bash
#!/bin/bash
# Compare current results against historical baseline

BASELINE_DIR="baselines/v1.0.0"
CURRENT_DIR="test_output"

# Run current analysis
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv tests/fixtures/test_run.csv \
  --outdir "$CURRENT_DIR" \
  --clamp 7.0

# Compare outputs
for file in VE_Correction_Delta_DYNO.csv Diagnostics_Report.txt; do
  diff "$BASELINE_DIR/$file" "$CURRENT_DIR/$file"
  if [ $? -ne 0 ]; then
    echo "✗ $file differs from baseline"
    exit 1
  fi
done

echo "✓ All outputs match baseline"
```

---

## Workflow Examples

### Workflow 1: Weekly Batch Analysis

```bash
#!/bin/bash
# Process all dyno runs from the past week

WEEK_AGO=$(date -d '7 days ago' +%Y%m%d)
TODAY=$(date +%Y%m%d)

echo "Processing dyno runs from $WEEK_AGO to $TODAY"

# Find recent logs
find logs/ -name "*.csv" -newermt "$WEEK_AGO" | while read log; do
  run_id=$(basename "$log" .csv)
  
  echo "Processing $run_id..."
  
  python ai_tuner_toolkit_dyno_v1_2.py \
    --csv "$log" \
    --outdir "./runs/$run_id" \
    --base_front tables/base_ve_front.csv \
    --base_rear tables/base_ve_rear.csv \
    --clamp 7.0
  
  # Generate summary report
  python scripts/generate_summary.py "./runs/$run_id"
done

# Create weekly report
python scripts/weekly_report.py \
  --start "$WEEK_AGO" \
  --end "$TODAY" \
  --output "reports/weekly_$(date +%Y%m%d).html"
```

### Workflow 2: Incremental Tuning

```bash
#!/bin/bash
# Multi-iteration tuning workflow

ITERATION=0
MAX_ITERATIONS=5
CURRENT_VE="tables/base_ve.csv"

while [ $ITERATION -lt $MAX_ITERATIONS ]; do
  echo "=== Iteration $ITERATION ==="
  
  # Run dyno pull
  echo "Waiting for dyno run..."
  # (In real use, wait for new CSV file)
  
  # Analyze
  python ai_tuner_toolkit_dyno_v1_2.py \
    --csv "logs/iteration_$ITERATION.csv" \
    --outdir "./iterations/iter_$ITERATION" \
    --clamp 7.0
  
  # Check if corrections are small enough
  MAX_CORRECTION=$(python scripts/get_max_correction.py \
    "./iterations/iter_$ITERATION/VE_Correction_Delta_DYNO.csv")
  
  echo "Max correction: $MAX_CORRECTION%"
  
  if [ $(echo "$MAX_CORRECTION < 1.0" | bc) -eq 1 ]; then
    echo "✓ Tuning converged!"
    break
  fi
  
  # Apply corrections
  NEXT_VE="tables/ve_iter_$ITERATION.csv"
  python ve_operations.py apply \
    --base "$CURRENT_VE" \
    --factor "./iterations/iter_$ITERATION/VE_Correction_Delta_DYNO.csv" \
    --output "$NEXT_VE" \
    --max-adjust-pct 7.0
  
  CURRENT_VE="$NEXT_VE"
  ITERATION=$((ITERATION + 1))
done

echo "Final VE table: $CURRENT_VE"
```

### Workflow 3: A/B Testing

```bash
#!/bin/bash
# Compare results from two different parameter sets

# Test configuration A (conservative)
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv test_run.csv \
  --outdir ./results/config_a \
  --clamp 5.0 \
  --smooth-passes 3

# Test configuration B (aggressive)
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv test_run.csv \
  --outdir ./results/config_b \
  --clamp 10.0 \
  --smooth-passes 1

# Compare results
python scripts/compare_configs.py \
  ./results/config_a/manifest.json \
  ./results/config_b/manifest.json \
  --output ./results/comparison.html
```

---

## Error Handling

### Robust Script Template

```bash
#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Configuration
LOG_FILE="automation.log"
ERROR_DIR="errors"

# Logging function
log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Error handler
handle_error() {
  local run_id=$1
  local exit_code=$2
  
  log "ERROR: Run $run_id failed with exit code $exit_code"
  
  # Save error state
  mkdir -p "$ERROR_DIR"
  cp "runs/$run_id/"* "$ERROR_DIR/$run_id/" 2>/dev/null || true
  
  # Optionally send alert
  # python scripts/send_alert.py "$run_id" "$exit_code"
}

# Main processing loop
for log in logs/*.csv; do
  run_id=$(basename "$log" .csv)
  log "Processing $run_id"
  
  if python ai_tuner_toolkit_dyno_v1_2.py \
       --csv "$log" \
       --outdir "./runs/$run_id" \
       --clamp 7.0 \
       2>&1 | tee -a "$LOG_FILE"; then
    log "✓ $run_id completed successfully"
  else
    handle_error "$run_id" $?
    # Continue processing other runs
  fi
done

log "Batch processing complete"
```

---

## Best Practices

### 1. Always Use Absolute Paths

```bash
# Good
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv "$(pwd)/logs/run_001.csv" \
  --outdir "$(pwd)/runs/run_001"

# Bad (relative paths can break in cron jobs)
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv logs/run_001.csv \
  --outdir runs/run_001
```

### 2. Validate Inputs Before Processing

```bash
# Check file exists and is readable
if [ ! -r "$CSV_FILE" ]; then
  echo "Error: Cannot read $CSV_FILE"
  exit 2
fi

# Check file is not empty
if [ ! -s "$CSV_FILE" ]; then
  echo "Error: $CSV_FILE is empty"
  exit 3
fi

# Proceed with processing
python ai_tuner_toolkit_dyno_v1_2.py --csv "$CSV_FILE" ...
```

### 3. Use Dry-Run Before Applying

```bash
# Always dry-run first
python ve_operations.py apply \
  --base "$BASE_VE" \
  --factor "$CORRECTIONS" \
  --output "$OUTPUT_VE" \
  --dry-run

# Check exit code before committing
if [ $? -eq 0 ]; then
  python ve_operations.py apply \
    --base "$BASE_VE" \
    --factor "$CORRECTIONS" \
    --output "$OUTPUT_VE"
fi
```

### 4. Preserve Audit Trail

```bash
# Log all operations with timestamps
{
  echo "Run ID: $RUN_ID"
  echo "Timestamp: $(date -Iseconds)"
  echo "Input CSV: $CSV_FILE"
  echo "SHA-256: $(sha256sum "$CSV_FILE")"
  echo "Parameters: --clamp 7.0 --smooth-passes 2"
  echo "---"
} > "runs/$RUN_ID/audit.log"

# Run analysis
python ai_tuner_toolkit_dyno_v1_2.py ... >> "runs/$RUN_ID/audit.log" 2>&1
```

### 5. Test Determinism Regularly

```bash
# Run same analysis twice
python ai_tuner_toolkit_dyno_v1_2.py --csv test.csv --outdir out1
python ai_tuner_toolkit_dyno_v1_2.py --csv test.csv --outdir out2

# Compare (excluding timestamps)
diff <(jq 'del(.timestamp_utc)' out1/manifest.json) \
     <(jq 'del(.timestamp_utc)' out2/manifest.json)

if [ $? -ne 0 ]; then
  echo "CRITICAL: Determinism broken!"
  exit 1
fi
```

### 6. Version Control Outputs

```bash
# Track analysis results in Git
cd runs/
git add run_$RUN_ID/
git commit -m "Analysis results for run $RUN_ID"
git tag -a "run-$RUN_ID" -m "Completed $(date)"
git push --tags
```

---

## Summary

DynoAI3's automation capabilities align it with world-class OEM calibration systems:

✅ **Headless operation** - No UI dependencies for core functionality  
✅ **Deterministic execution** - Enables reliable automation  
✅ **Function-level APIs** - Programmatic access to all features  
✅ **Batch processing** - Process multiple runs efficiently  
✅ **CI/CD ready** - Integrate with automated testing pipelines  
✅ **Audit trail** - Full traceability of all operations  

By treating automation as a first-class feature, DynoAI3 enables workflows that scale from single dyno pulls to large-scale regression testing and continuous validation.

---

**Document Version:** 1.0.0  
**Last Updated:** 2025-12-13  
**See Also:** 
- [DETERMINISTIC_MATH_SPECIFICATION.md](DETERMINISTIC_MATH_SPECIFICATION.md)
- [KERNEL_SPECIFICATION.md](KERNEL_SPECIFICATION.md)
