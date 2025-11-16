# Quick Reference: Fixes Needed for Migration Checklist

## CRITICAL FIXES (Do these first)

### Issue 1: Experimental Framework Priority Inconsistency
**File:** `MIGRATION_CHECKLIST.md`  
**Line:** 77  
**Current:**
```markdown
### Experimental Framework [MATH-CRITICAL] - PRIORITY 2
```

**Fix Option A (Promote to PRIORITY 1):**
```markdown
### Experimental Framework [MATH-CRITICAL] - PRIORITY 1
```

**Fix Option B (Add explanation why it's Priority 2):**
```markdown
### Experimental Framework [MATH-CRITICAL] - PRIORITY 2
> Experimental kernels are math-critical but priority 2 because the core engine 
> (priority 1) functions independently. Experimental kernels enable advanced 
> features but aren't required for baseline dyno tuning operation.
```

**Rationale:** Kernel Tests (line 71) are [MATH-CRITICAL] + PRIORITY 1. If 
Experimental Framework is also MATH-CRITICAL, it should be PRIORITY 1 OR the 
document should explain why not.

---

### Issue 2: Clarify Test Count (PyTest Section)
**File:** `MIGRATION_CHECKLIST.md`  
**Line:** 163-167  
**Current:**
```markdown
### 4. Expected Test Results
- Selftests: 2/2 passing
- Acceptance: 8/8 passing
- Kernel harnesses: 4/4 passing
- PyTest: 15/15 passing (7 unit + 8 integration)
```

**Issue:** Lists 6 test FILES but claims 15 tests. Unclear if this means:
- 15 test cases/methods across 6 files? OR
- 15 separate test files?

**Fix:**
```markdown
### 4. Expected Test Results
- Selftests: 2/2 passing (2 files)
- Acceptance: 8/8 passing (1 file with 8 test cases)
- Kernel harnesses: 4/4 passing (4 files)
- PyTest: 15 test cases passing across 6 files:
  - 4 unit test files (~7 test cases)
  - 2 integration test files (~8 test cases)
```

**Alternative Fix (if you want to verify actual counts in DynoAI_2):**
```bash
# Add this validation step to line 151:
python -m pytest tests/unit tests/integration --collect-only -q
# Expected output: 15 test cases (specific breakdown TBD)
```

---

### Issue 3: Add Missing Documentation Files
**File:** `MIGRATION_CHECKLIST.md`  
**Location:** After line 41 (after "Configuration Files" section)  

**Add new section:**
```markdown
### Documentation Files - PRIORITY 2

- ⏳ `docs/DYNOAI_CORE_REFERENCE.md` - Core engine API reference with examples
- ⏳ `docs/DYNOAI_SAFETY_RULES.md` - Safety invariants and design constraints
- ⏳ `.github/workflows/dynoai-ci.yml` - GitHub Actions CI/CD pipeline
- ⏳ `CHANGELOG.md` - Version history and breaking changes
```

**Why these files matter:**
- `DYNOAI_CORE_REFERENCE.md` - Referenced in architecture section 17, line 651
- `DYNOAI_SAFETY_RULES.md` - Referenced in architecture section 17, line 652
- `.github/workflows/dynoai-ci.yml` - Referenced in architecture section 11, line 450
- `CHANGELOG.md` - Referenced in architecture section 15, line 541

---

## MEDIUM PRIORITY FIXES (Do these for completeness)

### Issue 4: Document Cursor AI Rules in Architecture
**File:** `docs/DYNOAI_ARCHITECTURE_OVERVIEW.md`  
**Location:** Section 10 (Security Architecture), after line 427  

**Add subsection:**
```markdown
### Cursor AI Configuration

- `.cursorrules.md` - Guidelines for Cursor AI editor integration
- `.cursor/rules/snyk_rules.mdc` - Snyk security scanning rules for IDE
```

**Note:** These files already exist in DynoAI_3 but should be documented.

---

### Issue 5: Enhance Validation Steps
**File:** `MIGRATION_CHECKLIST.md`  
**Location:** After line 172 (after dependencies check)  

**Add new validation steps:**
```markdown
### 6. Verify Core Module Imports
```bash
python -c "from core.ve_operations import VEApply, VERollback; print('VE ops OK')"
python -c "from core.io_contracts import compute_sha256; print('Path safety OK')"
python -c "from experiments.run_experiment import main; print('Experiments OK')"
```

### 7. Run Selftest with Verbose Output
```bash
python tests/selftest.py -v  # Should complete without errors
```

### 8. Verify Test Framework is Working
```bash
python -m pytest tests/ --collect-only -q
# Should list all available tests
```
```

---

## LOW PRIORITY FIXES (Nice-to-have)

### Issue 6: Add Test Method Breakdown Table
**File:** `MIGRATION_CHECKLIST.md`  
**Location:** Before line 163 (Post-Migration Validation section)  

**Add reference table:**
```markdown
### Test File Breakdown (for reference)

| Category | File | Expected Test Cases |
|----------|------|---|
| Unit | test_bin_alignment.py | ~2 |
| Unit | test_delta_floor.py | ~2 |
| Unit | test_fingerprint.py | ~2 |
| Unit | test_runner_paths.py | ~1 |
| Integration | test_xai_blueprint.py | ~4 |
| Integration | test_xai_client.py | ~4 |
| Kernels | test_k1.py | 1 |
| Kernels | test_k2.py | 1 |
| Kernels | test_k2_fixed.py | 1 |
| Kernels | test_k3.py | 1 |

**Total:** 19 test cases across 10 files

**Note:** Actual counts TBD after migration from DynoAI_2
```

---

## Implementation Order

1. **Do these first (blocks migration decision):**
   - Fix Issue 1 (Priority inconsistency)
   - Fix Issue 2 (Test count clarity)
   - Fix Issue 3 (Add missing files)

2. **Do these before starting migration:**
   - Fix Issue 4 (Document Cursor rules)
   - Fix Issue 5 (Enhanced validation)

3. **Do these after successful migration:**
   - Fix Issue 6 (Add test breakdown table) - with actual counts from DynoAI_2

---

## Files to Update

| File | Issues | Severity |
|------|--------|----------|
| `MIGRATION_CHECKLIST.md` | 1, 2, 3, 5, 6 | CRITICAL |
| `DYNOAI_ARCHITECTURE_OVERVIEW.md` | 4 | MEDIUM |

---

## Verification Checklist

After applying fixes:

- [ ] All [MATH-CRITICAL] items have consistent priority assignment
- [ ] Test count clearly states "X test cases across Y test files"
- [ ] All 4 missing documentation files listed in checklist
- [ ] Cursor AI rules documented in architecture
- [ ] Enhanced validation steps added
- [ ] Both documents cross-reference each other correctly
- [ ] No conflicting information between two documents

---

**Last Updated:** 2025-11-16

