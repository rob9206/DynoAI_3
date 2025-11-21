#!/usr/bin/env python3
"""Quick validation script for experiment runner."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT / "experiments"))

print("=" * 60)
print("DynoAI Experiment Runner - Quick Validation")
print("=" * 60)

# Test 1: Import kernel registry
try:
    from kernel_registry import REGISTRY, resolve_kernel

    print("[OK] Test 1 PASSED: kernel_registry imported successfully")
    print(f"  Found {len(REGISTRY)} kernels: {', '.join(REGISTRY.keys())}")
except Exception as e:
    print(f"[FAIL] Test 1 FAILED: {e}")
    sys.exit(1)

# Test 2: Resolve a kernel
try:
    kernel_fn, defaults, mod_path, func_name = resolve_kernel("k3")
    print(f"[OK] Test 2 PASSED: Resolved k3 -> {mod_path}::{func_name}")
    print(f"  Defaults: {defaults}")
except Exception as e:
    print(f"[FAIL] Test 2 FAILED: {e}")
    sys.exit(1)

# Test 3: Import run_experiment
try:
    from run_experiment import _resolve_under_root, _strip_quote_num

    print("[OK] Test 3 PASSED: run_experiment functions imported")
except Exception as e:
    print(f"[FAIL] Test 3 FAILED: {e}")
    sys.exit(1)

# Test 4: Path validation
try:
    test_path = Path("experiments/test")
    resolved = _resolve_under_root(test_path)
    assert str(resolved).startswith(str(ROOT))
    print("[OK] Test 4 PASSED: Path validation works")
    print(f"  {test_path} -> {resolved}")
except Exception as e:
    print(f"[FAIL] Test 4 FAILED: {e}")
    sys.exit(1)

# Test 5: Traversal protection
try:
    from run_experiment import _resolve_under_root

    traversal_path = Path("experiments/../../../etc/passwd")
    try:
        _resolve_under_root(traversal_path)
        print("[FAIL] Test 5 FAILED: Traversal should have been rejected")
        sys.exit(1)
    except (RuntimeError, ValueError) as e:
        if "escapes repo root" in str(e):
            print("[OK] Test 5 PASSED: Traversal attack blocked")
        else:
            raise
except Exception as e:
    print(f"[FAIL] Test 5 FAILED: {e}")
    sys.exit(1)

# Test 6: Quote sanitization
try:
    assert _strip_quote_num('"123.45"') == "123.45"
    assert _strip_quote_num("123.45") == "123.45"
    assert _strip_quote_num('""456.78""') == "456.78"
    print("[OK] Test 6 PASSED: Quote sanitization works")
except Exception as e:
    print(f"[FAIL] Test 6 FAILED: {e}")
    sys.exit(1)

# Test 7: Check for sample CSV (archive or experiments)
try:
    # Try archive first (DynoAI_2), then experiments (DynoAI_3)
    csv_candidates = [
        ROOT / "archive" / "FXDLS_Wheelie_Spark_Delta-1.csv",
        ROOT / "experiments" / "FXDLS_Wheelie_Spark_Delta-1.csv",
    ]
    csv_path = None
    for candidate in csv_candidates:
        if candidate.exists():
            csv_path = candidate
            break
    
    if csv_path:
        print(f"[OK] Test 7 PASSED: Sample CSV exists ({csv_path.stat().st_size} bytes)")
    else:
        print("[WARN] Test 7 SKIPPED: No sample CSV found (non-critical)")
except Exception as e:
    print(f"[FAIL] Test 7 FAILED: {e}")
    sys.exit(1)

print("=" * 60)
print("ALL TESTS PASSED [OK]")
print("=" * 60)
print("\nNext steps:")
print(
    "1. Run dry-run: python experiments/run_experiment.py --idea-id k3 --csv archive/FXDLS_Wheelie_Spark_Delta-1.csv --outdir experiments/test --dry-run"
)
print(
    "2. Run actual experiment: python experiments/run_experiment.py --idea-id k3 --csv archive/FXDLS_Wheelie_Spark_Delta-1.csv --outdir experiments/k3_test"
)
print("3. Check output: experiments/k3_test/kernel_fingerprint.txt")
