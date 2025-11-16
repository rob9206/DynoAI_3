# Test Suite

Comprehensive test coverage for DynoAI v3.

## Expected Test Structure

### Smoke Tests
- `selftest.py` - Smoke test with synthetic CSV → full pipeline
- `selftest_runner.py` - Alternative smoke test harness
- `acceptance_test.py` - VE operations acceptance testing (8 scenarios)

### Unit Tests (`unit/`)
- `test_bin_alignment.py` - Grid mismatch detection
- `test_delta_floor.py` - Delta flooring (<0.001% → 0.000%)
- `test_fingerprint.py` - Kernel fingerprint generation
- `test_runner_paths.py` - Path traversal protection

### Integration Tests (`integration/`)
- `test_xai_blueprint.py` - Flask blueprint wiring
- `test_xai_client.py` - xAI API client integration

### Kernel Harness Tests (`kernels/`)
- `test_k1.py` - K1 gradient-limited kernel
- `test_k2.py` - K2 coverage-adaptive kernel
- `test_k2_fixed.py` - K2 fixed variant
- `test_k3.py` - K3 bilateral kernel

## Running Tests

### Quick Smoke Test
```bash
python tests/selftest.py
```

### Full Test Suite
```bash
pwsh scripts/dynoai_safety_check.ps1 -RunSelftests -RunKernels -RunPytest
```

### Expected Results
- Selftests: 2/2 passing
- Acceptance: 8/8 passing
- Kernel harnesses: 4/4 passing
- PyTest: 15/15 passing (7 unit + 8 integration)

## Test Policies

- All tests must pass before committing
- Never weaken assertions to "make tests pass"
- Add test coverage for new features
- Validate safety invariants (clamping, coverage, bin alignment)
