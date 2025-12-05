# DynoAI Safety Rules

_Last updated: 2025-11-13_

These rules protect DynoAI's math-correctness, calibration integrity, and customer safety. Every change must honor these policies.

---

## 1. Math-Critical Assets (Do Not Modify Without Approval)

### Core Engine Files
```
core/ai_tuner_toolkit_dyno_v1_2.py    [MATH-CRITICAL]
core/ve_operations.py                  [MATH-CRITICAL]
core/io_contracts.py                   [MATH-CRITICAL]
```

**Responsibilities:**
- `ai_tuner_toolkit_dyno_v1_2.py`: Main CLI engine, AFR analysis, VE correction generation, smoothing kernel orchestration, clamping enforcement
- `ve_operations.py`: VE table apply/rollback with SHA-256 verification, metadata generation, factor clamping
- `io_contracts.py`: Path traversal protection, file hashing, canonical naming, repo boundary enforcement

### Experimental Kernels
```
experiments/protos/k1_gradient_limit_v1.py        [MATH-CRITICAL]
experiments/protos/k2_coverage_adaptive_v1.py     [MATH-CRITICAL]
experiments/protos/k3_bilateral_v1.py             [MATH-CRITICAL]
experiments/protos/kernel_weighted_v1.py          [MATH-CRITICAL]
experiments/protos/kernel_knock_aware_v1.py       [MATH-CRITICAL]
```

**Responsibilities:**
- K1: Gradient-limited smoothing (prevents excessive local changes)
- K2: Coverage-adaptive clamping (tighter limits in low-coverage areas)
- K3: Bilateral edge-preserving filter (maintains sharp transitions)
- Weighted: Coverage-weighted smoothing
- Knock-aware: Knock event sensitivity

### Test Harnesses (Semantics Locked)
```
tests/selftest.py                     [TEST HARNESS - SEMANTICS FIXED]
tests/selftest_runner.py              [TEST HARNESS - SEMANTICS FIXED]
tests/acceptance_test.py              [TEST HARNESS - SEMANTICS FIXED]
tests/kernels/test_k1.py              [TEST HARNESS - SEMANTICS FIXED]
tests/kernels/test_k2.py              [TEST HARNESS - SEMANTICS FIXED]
tests/kernels/test_k2_fixed.py        [TEST HARNESS - SEMANTICS FIXED]
tests/kernels/test_k3.py              [TEST HARNESS - SEMANTICS FIXED]
```

> **Policy:** Changes to the above require:
> - Maintainer approval
> - Design document explaining the change
> - Validation plan with before/after output comparisons
> - Full regression test evidence
> - Extended review period (3-7 days minimum)

---

## 2. Allowed Modifications

### Import Path Updates (After Reorganization)
✅ **Allowed:** Updating `import` statements to reflect new file locations  
❌ **Not Allowed:** Changing imported symbols or function signatures

### Documentation and Comments
✅ **Allowed:** Adding docstrings, clarifying comments, updating README  
❌ **Not Allowed:** Removing safety warnings or critical usage notes

### Formatting (Extreme Caution)
✅ **Allowed:** Consistent whitespace, line breaks (with full test validation)  
❌ **Not Allowed:** Reformatting that changes line numbers referenced in docs

### Performance Optimizations
✅ **Allowed:** If exact output is preserved (requires proof via regression tests)  
❌ **Not Allowed:** Optimizations that change numerical precision or algorithm behavior

---

## 3. Required Safety Tests

### Test Execution Order

Run in this sequence after any change:

```bash
# 1. Selftests (smoke tests)
python tests/selftest.py
python tests/selftest_runner.py

# 2. VE operations acceptance
python tests/acceptance_test.py

# 3. Kernel harnesses
python tests/kernels/test_k1.py
python tests/kernels/test_k2.py
python tests/kernels/test_k2_fixed.py
python tests/kernels/test_k3.py

# 4. PyTest suites
python -m pytest tests/unit -v
python -m pytest tests/integration -v

# Or use the comprehensive safety check
pwsh scripts/dynoai_safety_check.ps1 -RunSelftests -RunKernels -RunPytest
```

### Test Invariants

| Test | Must Verify |
| --- | --- |
| `selftest.py` | CLI runs, generates manifest, produces VE_Correction_Delta and Diagnostics |
| `acceptance_test.py` | Clamping enforced, metadata complete, hash verification works, rollback succeeds |
| Kernel harnesses | Kernel imports work, execution succeeds, output dimensions correct |
| Unit tests | Bin alignment checked, delta flooring applied, fingerprints generated, path validation works |
| Integration tests | xAI client functions, Flask blueprint registers, API endpoints respond |

**Rule:** All tests must pass before merging. No exceptions.

---

## 4. Data Format Invariants

### VE Tables (`*.csv`)
- **Format:** First column `RPM`, subsequent columns numeric kPa values
- **Precision:** 4 decimals enforced by `VEApply`
- **Bin Alignment:** RPM/kPa grids must match exactly (no implicit reindexing)
- **Validation:** Use `read_ve_table()` from `ve_operations.py`

### Factor Tables (`VE_Correction_Delta_*.csv`)
- **Format:** Percentage values (`+/-XX.XXXX`)
- **Grid:** Must match base VE table dimensions exactly
- **Clamping:** Default ±7%, max ±15% enforced before apply

### Manifest (`manifest.json`)
- **Required Fields:**
  - `status.code` (must be `"success"` for completed runs)
  - `stats.rows_read` (must be ≥ 1000)
  - `stats.bins_total` (must be > 0)
  - `timing.start`, `timing.end`
- **Optional Fields:**
  - `apply.allowed` (present when VE apply executed)
  - `outputs[]` (list of generated files)

### Diagnostics (`Diagnostics_Report.txt`)
- **Must Include:**
  - Summary totals (rows read, bins covered, corrections applied)
  - Clamping notes (how many corrections clamped)
  - Coverage metrics (front/rear cylinder coverage)
  - Warnings (low coverage, missing data, etc.)

### Kernel Fingerprint (`kernel_fingerprint.txt`)
- **Format:** `module=<name>`, `function=<name>`, `params=<dict>`
- **Purpose:** Audit trail for experimental kernel usage
- **Generated By:** `experiments/run_experiment.py` (even in `--dry-run`)

---

## 5. Dependency Safety

### Python Dependencies (`requirements.txt`)
- **Pin versions** for reproducibility
- **Security review** required for new packages
- **Prefer stdlib** or existing dependencies over adding new ones
- **Run `pip check`** before committing dependency changes
- **Run Snyk scan** to detect vulnerabilities

### External Services
- **xAI API:** Use `XAI_API_KEY` environment variable, never commit
- **Snyk:** Use `SNYK_TOKEN` secret in GitHub Actions
- **No hardcoded secrets** in source code or test fixtures

---

## 6. Path Safety Rules

### Output Directory Validation
- All output paths must resolve within repository root
- Use `io_contracts.py` helpers for path validation
- Exception: `--dry-run` mode allows temp directories for testing

### CSV Input Validation
- Reject paths with `..` traversal attempts
- Verify file exists before processing
- Check for minimum required columns

### Table File Protection
- Base VE tables in `tables/` are reference data
- Never overwrite base tables without backup
- Use `VEApply` with metadata for all modifications

---

## 7. Clamping and Safety Limits

### VE Correction Clamping
- **Default:** ±7% (multipliers in [0.93, 1.07])
- **Range:** ±1% to ±15% (configurable via `--clamp` or `max_adjust_pct`)
- **Enforcement:** Applied before VE table multiplication
- **Rationale:** Prevents excessive corrections that could damage engine

### Spark Timing Limits
- **Typical Range:** -5° to +10° from baseline
- **Safety:** Conservative suggestions, always verify with experienced tuner
- **Output:** Suggestions only, not auto-applied

### Coverage Thresholds
- **Low Coverage Warning:** < 10 hits per bin
- **No Correction:** Bins with 0 hits
- **High Confidence:** ≥ 50 hits per bin

---

## 8. Change Control Checklist

Before merging any PR:

- [ ] No math-critical files modified (or approved if modified)
- [ ] All safety tests pass (attach logs to PR)
- [ ] Documentation updated to reflect changes
- [ ] `.gitignore` prevents artifacts from being committed
- [ ] No secrets or credentials in tracked files
- [ ] Import paths correct after any file moves
- [ ] Linter warnings addressed (or documented as acceptable)
- [ ] Maintainer review completed for core/experiments changes

---

## 9. Rollback Procedures

### Code Rollback
```bash
# Revert last commit
git revert HEAD
git push origin main

# Revert specific commit
git revert <commit-hash>
git push origin main
```

### VE Table Rollback
```python
from pathlib import Path
from core.ve_operations import VERollback

VERollback().rollback(
    current_ve_path=Path("tables/VE_Front_Updated.csv"),
    metadata_path=Path("tables/VE_Front_Updated_meta.json"),
    output_path=Path("tables/VE_Front_Restored.csv"),
)
```

**Requirements:**
- Metadata file must exist and be unmodified
- SHA-256 hashes must match
- Factor table must be available at original path

---

## 10. Emergency Contacts

### Security Issues
- **DO NOT** open public issues
- Email: [security-contact@example.com]
- See `SECURITY.md` for full reporting process

### Math-Critical Code Questions
- Open a Discussion (not an Issue)
- Tag: `@maintainer-username`
- Include: test evidence, output comparisons, design rationale

---

## Enforcement

These rules are enforced by:
- **CODEOWNERS:** Math-critical files require maintainer approval
- **Branch Protection:** PRs required, status checks must pass
- **CI Workflows:** Automated test execution on every push/PR
- **Code Review:** Manual verification of safety checklist

Violations of these rules may result in:
- PR rejection
- Request for additional testing
- Escalation to maintainers for design review

---

**Remember:** When in doubt, ask. Safety first, always. 🏍️

