# DynoAI_2 → DynoAI_3 Migration Checklist

This document tracks the migration of code from DynoAI_2 to DynoAI_3.

## Status: **READY FOR MIGRATION**

DynoAI_3 structure is prepared and ready to receive code from DynoAI_2.

---

## Directory Structure ✅

All directories have been created:

- ✅ `core/` - Core engine directory
- ✅ `core/dynoai/` - Shared utilities package
- ✅ `core/dynoai/api/` - Flask blueprints
- ✅ `core/dynoai/clients/` - API clients
- ✅ `tests/` - Test suite directory
- ✅ `tests/unit/` - Unit tests
- ✅ `tests/integration/` - Integration tests
- ✅ `tests/kernels/` - Kernel harness tests
- ✅ `experiments/` - Experimental framework
- ✅ `experiments/protos/` - Experimental kernels [MATH-CRITICAL]
- ✅ `scripts/` - Automation scripts
- ✅ `tables/` - Reference VE tables
- ✅ `web_service/` - Flask API (optional)
- ✅ `web_service/api/` - API implementation
- ✅ `templates/` - Templates directory
- ✅ `archive/` - Legacy code (read-only)

---

## Configuration Files ✅

- ✅ `requirements.txt` - Python dependencies defined
- ✅ `.gitignore` - Git ignore patterns configured
- ✅ `README.md` - Comprehensive project overview
- ✅ `.cursorrules.md` - Cursor AI configuration (already present)
- ✅ `.cursor/rules/snyk_rules.mdc` - Snyk security rules (already present)

---

## Files to Migrate from DynoAI_2

### Core Engine [MATH-CRITICAL] - PRIORITY 1
- ⏳ `core/ai_tuner_toolkit_dyno_v1_2.py` - Main CLI engine
- ⏳ `core/ve_operations.py` - VE apply/rollback with hash verification
- ⏳ `core/io_contracts.py` - Path safety & file fingerprinting

### Core Utilities - PRIORITY 2
- ⏳ `core/dynoai/api/xai_blueprint.py` - Flask blueprint for xAI
- ⏳ `core/dynoai/clients/xai_client.py` - xAI API client wrapper
- ⏳ `core/dynoai/constants.py` - Shared constants

### Test Suite - PRIORITY 1
- ⏳ `tests/selftest.py` - Smoke test
- ⏳ `tests/selftest_runner.py` - Alternative smoke test
- ⏳ `tests/acceptance_test.py` - VE operations acceptance (8 scenarios)

### Unit Tests - PRIORITY 2
- ⏳ `tests/unit/test_bin_alignment.py` - Grid mismatch detection
- ⏳ `tests/unit/test_delta_floor.py` - Delta flooring tests
- ⏳ `tests/unit/test_fingerprint.py` - Kernel fingerprint generation
- ⏳ `tests/unit/test_runner_paths.py` - Path traversal protection

### Integration Tests - PRIORITY 3
- ⏳ `tests/integration/test_xai_blueprint.py` - Flask blueprint wiring
- ⏳ `tests/integration/test_xai_client.py` - xAI API client

### Kernel Tests [MATH-CRITICAL] - PRIORITY 1
- ⏳ `tests/kernels/test_k1.py` - K1 gradient-limited kernel
- ⏳ `tests/kernels/test_k2.py` - K2 coverage-adaptive kernel
- ⏳ `tests/kernels/test_k2_fixed.py` - K2 fixed variant
- ⏳ `tests/kernels/test_k3.py` - K3 bilateral kernel

### Experimental Framework [MATH-CRITICAL] - PRIORITY 2
- ⏳ `experiments/run_experiment.py` - Kernel experiment runner
- ⏳ `experiments/protos/k1_gradient_limit_v1.py` - K1 kernel
- ⏳ `experiments/protos/k2_coverage_adaptive_v1.py` - K2 kernel
- ⏳ `experiments/protos/k3_bilateral_v1.py` - K3 kernel
- ⏳ `experiments/protos/kernel_weighted_v1.py` - Weighted kernel
- ⏳ `experiments/protos/kernel_knock_aware_v1.py` - Knock-aware kernel

### Scripts & Automation - PRIORITY 2
- ⏳ `scripts/reorganize_repo.ps1` - Repository reorganization
- ⏳ `scripts/dynoai_safety_check.ps1` - Full test suite runner
- ⏳ `scripts/upload_to_github.ps1` - GitHub upload automation
- ⏳ `scripts/pre_upload_checklist.ps1` - Pre-upload validation
- ⏳ `scripts/clean_workspace.py` - Cleanup utility
- ⏳ `scripts/cleanup_outputs.py` - Output directory cleanup

### Reference Tables & Sample Data - PRIORITY 2
- ⏳ `tables/FXDLS_Wheelie_VE_Base_Front_fixed.csv` - Front cylinder base VE (corrected)
- ⏳ `tables/FXDLS_Wheelie_VE_Base_Front.csv` - Front cylinder base VE (original)
- ⏳ `tables/FXDLS_Wheelie_Spark_Delta.csv` - Spark timing deltas
- ⏳ `tables/FXDLS_Wheelie_AFR_Targets.csv` - Target AFR by RPM/kPa
- ⏳ `tables/WinPEP_Sample.csv` - Sample dyno log
- ⏳ `tables/WinPEP_Log_Sample.csv` - Alternative sample format

### Web Service (Optional) - PRIORITY 3
- ⏳ `web_service/api/app.py` - Flask application
- ⏳ `web_service/start-web.ps1` - Server launcher
- ⏳ `web_service/test-api.ps1` - End-to-end API test
- ⏳ `web_service/test-api-only.ps1` - API-only verification

### Archive (Optional) - PRIORITY 4
- ⏳ `archive/` - Historical code and artifacts (reference only)

---

## Migration Options

### Option 1: Manual File Copy (Recommended for Review)
```bash
# From DynoAI_2 repository
cd /path/to/DynoAI_2

# Copy files to DynoAI_3
cp core/ai_tuner_toolkit_dyno_v1_2.py /home/user/DynoAI_3/core/
cp core/ve_operations.py /home/user/DynoAI_3/core/
# ... continue for each file
```

### Option 2: Use Materialization Script (If Available)
```bash
python /path/to/DynoAI_2/scripts/materialize_v3_minimal_tree.py \
    --source-root /path/to/DynoAI_2 \
    --target-root /home/user/DynoAI_3
```

### Option 3: Git Merge/Cherry-Pick
```bash
# Add DynoAI_2 as remote
git remote add dynoai2 /path/to/DynoAI_2
git fetch dynoai2

# Cherry-pick specific commits
git cherry-pick <commit-hash>
```

---

## Post-Migration Validation

After migration, run these checks:

### 1. Verify File Structure
```bash
find . -type f -name "*.py" | wc -l  # Should be 30+ Python files
```

### 2. Run Smoke Tests
```bash
python tests/selftest.py
```

### 3. Run Full Test Suite
```bash
pwsh scripts/dynoai_safety_check.ps1 -RunSelftests -RunKernels -RunPytest
```

### 4. Expected Test Results
- Selftests: 2/2 passing
- Acceptance: 8/8 passing
- Kernel harnesses: 4/4 passing
- PyTest: 15/15 passing (7 unit + 8 integration)

### 5. Verify Dependencies
```bash
pip install -r requirements.txt
python -c "import flask, pytest, requests; print('Dependencies OK')"
```

---

## Next Steps

1. **Locate DynoAI_2** - Clone or access DynoAI_2 repository
2. **Choose Migration Method** - Select Option 1, 2, or 3 above
3. **Copy Files** - Migrate files according to priority levels
4. **Validate** - Run post-migration validation checks
5. **Commit** - Create commit with migrated code
6. **Push** - Push to branch `claude/setup-go-environment-01FL2YGF7vgt5wtYH4KAzpRE`

---

## Notes

- **Math-Critical Files:** Require extra validation after migration
- **Read-Only Directories:** `archive/` and `experiments/` should not be modified
- **Dependency Compatibility:** Ensure Python 3.11+ is used
- **Test Coverage:** All 30+ tests must pass before merge is complete

---

**Legend:**
- ✅ Complete
- ⏳ Pending migration from DynoAI_2
- ❌ Missing or blocked

---

**Last Updated:** 2025-11-16
**Migration Status:** Structure ready, awaiting DynoAI_2 code transfer
