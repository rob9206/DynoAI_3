# DynoAI3 Test Coverage Gaps & Missing Behaviors

**Purpose:** Evidence-based identification of missing tests, ambiguous behaviors, and untested edge cases.

**Methodology:** Code inspection + test coverage analysis + gap prioritization by risk level.

---

## Gap Severity Levels

- 🔴 **CRITICAL** - Missing test could lead to engine damage, data loss, or security breach
- 🟠 **HIGH** - Missing test could cause incorrect tuning results or workflow failures
- 🟡 **MEDIUM** - Missing test could cause user confusion or reproducibility issues
- 🟢 **LOW** - Nice-to-have test for edge cases or improved error messages

---

## Critical Gaps (🔴 Immediate Attention Required)

### GAP-1: End-to-End Reproducibility Test
**Severity:** 🔴 **CRITICAL**  
**Category:** Determinism  
**Missing Behavior:** No test verifies that running the same CSV twice produces bit-identical VE deltas.

**Current State:**
- Core math has no randomness (evidence: no random() calls in `ai_tuner_toolkit_dyno_v1_2.py`)
- Test data generation uses fixed seeds (evidence: `dynoai/test_utils.py:39`)
- **BUT:** No automated test actually runs same CSV twice and asserts equality

**Impact if Not Addressed:**
- Silent non-determinism could creep in (e.g., dict iteration order changes in Python 3.7+)
- Reproducibility claims are based on code inspection, not regression test
- Users might get different results on different runs without knowing why

**Evidence of Gap:**
- `selftest.py` runs once per invocation
- `acceptance_test.py` tests apply/rollback math, not end-to-end determinism
- No test function named `test_reproducibility()` or `test_determinism()`

**Recommended Test:**
```python
def test_end_to_end_determinism():
    """Verify same CSV produces identical VE deltas across two runs."""
    csv_path = Path("tables/WinPEP_Log_Sample.csv")
    
    # Run 1
    outdir1 = tmp_path / "run1"
    subprocess.run([
        sys.executable, "ai_tuner_toolkit_dyno_v1_2.py",
        "--csv", str(csv_path),
        "--outdir", str(outdir1),
        "--clamp", "7",
        "--smooth_passes", "2"
    ], check=True)
    deltas1 = read_ve_deltas(outdir1 / "VE_Correction_Delta_DYNO.csv")
    
    # Run 2 (fresh temp directory, same parameters)
    outdir2 = tmp_path / "run2"
    subprocess.run([
        sys.executable, "ai_tuner_toolkit_dyno_v1_2.py",
        "--csv", str(csv_path),
        "--outdir", str(outdir2),
        "--clamp", "7",
        "--smooth_passes", "2"
    ], check=True)
    deltas2 = read_ve_deltas(outdir2 / "VE_Correction_Delta_DYNO.csv")
    
    # Assert bit-identical
    assert deltas1 == deltas2, "VE deltas not reproducible"
```

**Files to Modify:**
- Create `tests/test_reproducibility.py`
- Add to CI workflow as regression gate

**Priority:** **IMMEDIATE** (critical for determinism claims in CLAIMS.md)

---

### GAP-2: Preview vs. Apply Metadata Parity
**Severity:** 🟠 **HIGH**  
**Category:** Contracts  
**Missing Behavior:** No test verifies dry-run metadata equals actual apply metadata (except write flags).

**Current State:**
- Dry-run generates metadata: `acceptance_test.py:212-247`
- Dry-run does NOT write files: `acceptance_test.py:237-240`
- **BUT:** No test compares dry-run metadata to apply metadata for equality

**Impact if Not Addressed:**
- Dry-run preview could diverge from actual apply (misleading user)
- User might see different clamping or corrections in preview vs. apply
- Trust in dry-run mode is undermined

**Evidence of Gap:**
- `test_requirement_5_dry_run()` tests file non-existence, not metadata content
- No assertion comparing `metadata_dry["base_sha"]` to `metadata_apply["base_sha"]`

**Recommended Test:**
```python
def test_dry_run_apply_metadata_parity():
    """Verify dry-run metadata matches apply metadata (except file writes)."""
    # Dry-run
    metadata_dry = VEApply().apply(
        base_path, factor_path, output_path,
        metadata_path=metadata_path, dry_run=True
    )
    
    # Actual apply
    metadata_apply = VEApply().apply(
        base_path, factor_path, output_path,
        metadata_path=metadata_path, dry_run=False
    )
    
    # Compare critical fields
    assert metadata_dry["base_sha"] == metadata_apply["base_sha"]
    assert metadata_dry["factor_sha"] == metadata_apply["factor_sha"]
    assert metadata_dry["max_adjust_pct"] == metadata_apply["max_adjust_pct"]
    assert metadata_dry["app_version"] == metadata_apply["app_version"]
    
    # Verify applied_at_utc is within 1 second (timestamps may differ slightly)
    dry_time = datetime.fromisoformat(metadata_dry["applied_at_utc"].replace("Z", "+00:00"))
    apply_time = datetime.fromisoformat(metadata_apply["applied_at_utc"].replace("Z", "+00:00"))
    assert abs((dry_time - apply_time).total_seconds()) < 1.0
```

**Files to Modify:**
- Add to `acceptance_test.py` as `test_requirement_9_dry_run_parity()`

**Priority:** **HIGH** (affects user trust in dry-run mode)

---

## High-Priority Gaps (🟠 Address Soon)

### GAP-3: Malformed CSV Edge Cases
**Severity:** 🟠 **HIGH**  
**Category:** Input Validation  
**Missing Behaviors:**
1. Non-UTF8 encoding (e.g., ISO-8859-1, Windows-1252)
2. Duplicate column headers (e.g., "rpm,rpm,map_kpa,torque")
3. Zero-row CSV (headers only, no data)
4. NaN/Inf values in numeric columns

**Current State:**
- Preflight detects missing columns: `test_preflight_csv.py:64-78`
- VE operations raise error for empty CSV: `ve_operations.py:73`
- **BUT:** No tests for non-UTF8, duplicate headers, NaN/Inf

**Impact if Not Addressed:**
1. **Non-UTF8:** UnicodeDecodeError crashes workflow (no graceful fallback)
2. **Duplicate headers:** csv.DictReader silently overwrites first column with second
3. **Zero rows:** Error message untested (unclear user feedback)
4. **NaN/Inf:** Could propagate into VE corrections → invalid output

**Evidence of Gap:**
- No test creates CSV with encoding='ISO-8859-1'
- No test creates CSV with duplicate column names
- No test verifies error message for zero-row CSV
- No test creates CSV with NaN or Inf values

**Recommended Tests:**
```python
def test_non_utf8_csv():
    """Verify non-UTF8 CSV is handled gracefully."""
    # Create CSV with ISO-8859-1 encoding (e.g., ° symbol)
    csv_path = tmp_path / "non_utf8.csv"
    with open(csv_path, "w", encoding="iso-8859-1") as f:
        f.write("rpm,map_kpa,torque,temp_°F\n")
        f.write("2000,50,100,180\n")
    
    # Should either auto-detect encoding or provide clear error
    with pytest.raises(UnicodeDecodeError):
        result = process_csv(csv_path)
    # OR: If encoding auto-detection is added, verify it works
    # result = process_csv(csv_path, encoding="auto")
    # assert result["overall_ok"] == True

def test_duplicate_headers():
    """Verify duplicate column names are detected."""
    csv_path = tmp_path / "dup_headers.csv"
    with open(csv_path, "w") as f:
        f.write("rpm,rpm,map_kpa,torque\n")
        f.write("2000,2500,50,100\n")
    
    result = preflight_csv.run_preflight(csv_path)
    assert not result["schema_ok"], "Duplicate headers should fail schema check"

def test_zero_row_csv():
    """Verify zero-row CSV raises clear error."""
    csv_path = tmp_path / "zero_rows.csv"
    with open(csv_path, "w") as f:
        f.write("rpm,map_kpa,torque\n")  # Headers only
    
    with pytest.raises(RuntimeError, match="empty|no rows"):
        process_csv(csv_path)

def test_nan_inf_values():
    """Verify NaN/Inf values are filtered or rejected."""
    csv_path = tmp_path / "nan_inf.csv"
    with open(csv_path, "w") as f:
        f.write("rpm,map_kpa,torque\n")
        f.write("2000,50,NaN\n")
        f.write("3000,60,Inf\n")
    
    result = process_csv(csv_path)
    # Should either filter rows or raise clear error
    assert "rows_filtered" in result or "invalid numeric" in str(result.get("errors", ""))
```

**Files to Modify:**
- Add encoding parameter to all `open()` calls in `io_contracts.py`, `ve_operations.py`
- Add duplicate header check in `preflight_csv.py`
- Add NaN/Inf filtering in core engine CSV parsing
- Create `tests/test_malformed_csv.py` with all 4 tests above

**Priority:** **HIGH** (real-world CSVs often have encoding issues)

---

### GAP-4: Concurrent Apply/Rollback Safety
**Severity:** 🟡 **MEDIUM**  
**Category:** Statelessness  
**Missing Behavior:** No test verifies two processes can run simultaneously without interference.

**Current State:**
- Each run uses unique run_id (timestamp + random suffix)
- Separate output directories prevent file collisions
- **BUT:** No test actually runs two instances in parallel

**Impact if Not Addressed:**
- Race conditions in file I/O could cause crashes
- Global state corruption (if any exists)
- Unpredictable failures in multi-user environments

**Evidence of Gap:**
- No test uses `multiprocessing.Pool()` or `subprocess.Popen()` to run parallel instances
- No documentation on multi-user safety or concurrent run limitations

**Recommended Test:**
```python
def test_concurrent_runs():
    """Verify two simultaneous runs don't interfere."""
    import multiprocessing
    
    def run_analysis(csv_path, outdir):
        result = subprocess.run([
            sys.executable, "ai_tuner_toolkit_dyno_v1_2.py",
            "--csv", str(csv_path),
            "--outdir", str(outdir)
        ], capture_output=True, text=True)
        return result.returncode
    
    # Run two analyses in parallel
    csv1 = "test_data1.csv"
    csv2 = "test_data2.csv"
    outdir1 = tmp_path / "run1"
    outdir2 = tmp_path / "run2"
    
    with multiprocessing.Pool(2) as pool:
        results = pool.starmap(run_analysis, [(csv1, outdir1), (csv2, outdir2)])
    
    # Both should succeed
    assert all(r == 0 for r in results), "Concurrent runs failed"
    
    # Verify outputs are independent
    assert (outdir1 / "VE_Correction_Delta_DYNO.csv").exists()
    assert (outdir2 / "VE_Correction_Delta_DYNO.csv").exists()
```

**Files to Modify:**
- Create `tests/test_concurrency.py`

**Priority:** **MEDIUM** (most users run one instance at a time)

---

### GAP-5: Kernel Determinism Verification
**Severity:** 🟡 **MEDIUM**  
**Category:** Determinism  
**Missing Behavior:** No test verifies K1/K2/K3 kernels produce identical output for same input.

**Current State:**
- Kernel code has no random() calls (evidence: code inspection)
- Fingerprinting captures kernel params: `test_fingerprint.py`
- **BUT:** No test runs same kernel twice and asserts bit-identical output

**Impact if Not Addressed:**
- Future kernel changes could introduce randomness without detection
- Kernel reproducibility claims are based on code inspection, not tests

**Evidence of Gap:**
- No test function like `test_kernel_reproducibility()`
- Fingerprinting tests verify file creation, not output equality

**Recommended Test:**
```python
def test_kernel_determinism():
    """Verify kernels produce identical output for same input."""
    csv_path = "tables/WinPEP_Log_Sample.csv"
    
    for kernel_id in ["k1", "k2"]:
        # Run 1
        outdir1 = tmp_path / f"{kernel_id}_run1"
        subprocess.run([
            sys.executable, "experiments/run_experiment.py",
            "--idea-id", kernel_id,
            "--csv", str(csv_path),
            "--outdir", str(outdir1)
        ], check=True)
        deltas1 = read_ve_deltas(outdir1 / "VE_Correction_Delta_DYNO.csv")
        
        # Run 2
        outdir2 = tmp_path / f"{kernel_id}_run2"
        subprocess.run([
            sys.executable, "experiments/run_experiment.py",
            "--idea-id", kernel_id,
            "--csv", str(csv_path),
            "--outdir", str(outdir2)
        ], check=True)
        deltas2 = read_ve_deltas(outdir2 / "VE_Correction_Delta_DYNO.csv")
        
        assert deltas1 == deltas2, f"Kernel {kernel_id} not deterministic"
```

**Files to Modify:**
- Add to `tests/test_fingerprint.py` or create `tests/test_kernel_determinism.py`

**Priority:** **MEDIUM** (kernels are experimental, not production-default)

---

### GAP-6: Cross-Platform Reproducibility
**Severity:** 🟡 **MEDIUM**  
**Category:** Determinism  
**Missing Behavior:** No test verifies Windows/Linux/macOS produce bit-identical VE deltas.

**Current State:**
- Math is deterministic within a platform (evidence: no random() calls)
- **BUT:** No CI pipeline tests cross-platform equivalence

**Impact if Not Addressed:**
- Floating-point arithmetic could differ (x86 vs ARM)
- Python version differences (3.10 vs 3.11) could affect rounding
- Users might get different results on different OSes

**Evidence of Gap:**
- CI workflow (if exists) likely runs on single OS (typically Linux)
- No test matrix for Windows/Linux/macOS in GitHub Actions

**Recommended CI Enhancement:**
```yaml
# .github/workflows/test.yml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest, macos-latest]
    python-version: ['3.10', '3.11', '3.12']
```

**Recommended Test:**
```python
@pytest.mark.skipif(sys.platform != "linux", reason="Cross-platform test")
def test_cross_platform_reproducibility():
    """Compare outputs from different platforms (requires artifact sharing)."""
    # This test would require CI artifact sharing between jobs
    # Run on Linux, save deltas as artifact
    # Run on Windows, load Linux artifact, compare
    pass
```

**Files to Modify:**
- Update `.github/workflows/*.yml` to test multiple OS
- Add cross-platform comparison test (requires CI artifact sharing)

**Priority:** **MEDIUM** (nice-to-have; most users stick to one platform)

---

## Medium-Priority Gaps (🟡 Address When Feasible)

### GAP-7: Artifact Naming Stability (Backward Compatibility)
**Severity:** 🟡 **MEDIUM**  
**Category:** Contracts  
**Missing Behavior:** No test verifies old manifest versions can be loaded.

**Current State:**
- Manifest schema versioning exists: `io_contracts.py:27` - `SCHEMA_ID = "dynoai.manifest@1"`
- **BUT:** No test creates old schema manifest and attempts to load it

**Impact if Not Addressed:**
- Future schema changes could break old manifests
- Users can't read old run data after upgrading

**Recommended Test:**
```python
def test_manifest_backward_compatibility():
    """Verify old manifest versions can be parsed."""
    # Create mock manifest@1
    old_manifest = {
        "schema_id": "dynoai.manifest@1",
        "status": {"code": "success"},
        "stats": {"rows_read": 1000, "bins_total": 99},
        # ... old schema fields
    }
    
    # Should parse without error (or migrate to new schema)
    parsed = parse_manifest(old_manifest)
    assert parsed["status"]["code"] == "success"
```

**Files to Modify:**
- Add to `tests/test_manifest.py` (create if doesn't exist)
- Implement schema migration logic in `io_contracts.py`

**Priority:** **MEDIUM** (important for long-term maintainability)

---

### GAP-8: No Hidden State Verification
**Severity:** 🟡 **MEDIUM**  
**Category:** Statelessness  
**Missing Behaviors:**
1. Temp files are cleaned up after run
2. No global variables persist state across runs
3. Output directory overwrite behavior is tested

**Current State:**
- Temp directories created but cleanup relies on OS: `selftest.py:56-60`
- Unique run_id prevents collisions
- **BUT:** No explicit cleanup tests or overwrite behavior tests

**Recommended Tests:**
```python
def test_temp_cleanup():
    """Verify temp files are cleaned up after run."""
    before_files = set(Path("temp_selftest").glob("*"))
    
    # Run selftest
    subprocess.run([sys.executable, "selftest.py"], check=True)
    
    after_files = set(Path("temp_selftest").glob("*"))
    
    # Should be same (or fewer) files after run
    # (Note: This might need adjustment based on actual cleanup behavior)
    assert len(after_files) <= len(before_files) + 1  # Allow one new run dir

def test_output_overwrite_behavior():
    """Verify --outdir overwrite behavior is predictable."""
    outdir = tmp_path / "output"
    
    # Run 1
    subprocess.run([
        sys.executable, "ai_tuner_toolkit_dyno_v1_2.py",
        "--csv", "test_data.csv",
        "--outdir", str(outdir)
    ], check=True)
    
    manifest1 = json.load(open(outdir / "manifest.json"))
    
    # Run 2 (same outdir)
    subprocess.run([
        sys.executable, "ai_tuner_toolkit_dyno_v1_2.py",
        "--csv", "test_data.csv",
        "--outdir", str(outdir)
    ], check=True)
    
    manifest2 = json.load(open(outdir / "manifest.json"))
    
    # Verify second run overwrote first (or document intended behavior)
    assert manifest2["timing"]["start"] != manifest1["timing"]["start"]
```

**Files to Modify:**
- Create `tests/test_statelessness.py`
- Add explicit cleanup in selftest.py (try/finally)

**Priority:** **MEDIUM** (mostly works, but untested)

---

## Low-Priority Gaps (🟢 Nice-to-Have)

### GAP-9: Rollback Missing Metadata File
**Severity:** 🟢 **LOW**  
**Category:** Error Handling  
**Missing Behavior:** No test verifies rollback fails gracefully if metadata file is missing.

**Current State:**
- Rollback opens metadata file: `ve_operations.py:270-274`
- Likely raises FileNotFoundError if missing
- **BUT:** No explicit test for this scenario

**Recommended Test:**
```python
def test_rollback_missing_metadata():
    """Verify rollback fails gracefully if metadata is missing."""
    # Create updated VE file but no metadata
    updated_path = tmp_path / "updated.csv"
    missing_metadata_path = tmp_path / "missing_meta.json"
    
    with pytest.raises(FileNotFoundError, match="metadata"):
        VERollback().rollback(updated_path, missing_metadata_path, tmp_path / "restored.csv")
```

**Files to Modify:**
- Add to `acceptance_test.py` or `tests/test_ve_operations.py`

**Priority:** **LOW** (error message likely clear enough)

---

### GAP-10: Large CSV Performance Test
**Severity:** 🟢 **LOW**  
**Category:** Performance  
**Missing Behavior:** No test verifies performance with very large CSV files (e.g., 100k+ rows).

**Current State:**
- Selftest uses synthetic CSV with 1000+ rows
- Real dyno logs can be 10k-100k rows
- **BUT:** No performance benchmark or timeout test

**Recommended Test:**
```python
def test_large_csv_performance():
    """Verify analysis completes in reasonable time for large CSV."""
    large_csv = generate_synthetic_csv(num_rows=100000)
    
    start_time = time.time()
    subprocess.run([
        sys.executable, "ai_tuner_toolkit_dyno_v1_2.py",
        "--csv", str(large_csv),
        "--outdir", str(tmp_path / "output")
    ], check=True, timeout=300)  # 5-minute timeout
    elapsed = time.time() - start_time
    
    # Should complete in under 5 minutes
    assert elapsed < 300, f"Large CSV took {elapsed:.1f}s (too slow)"
```

**Files to Modify:**
- Create `tests/test_performance.py`

**Priority:** **LOW** (performance is acceptable for typical dyno logs)

---

### GAP-11: API Rate Limit Edge Cases
**Severity:** 🟢 **LOW**  
**Category:** API Security  
**Missing Behaviors:**
1. Rate limit reset after time window
2. Rate limit applies per-endpoint vs. global
3. Burst allowance (if any)

**Current State:**
- Rate limiting tested: `tests/api/test_rate_limiting.py`
- **BUT:** Edge cases like reset timing and burst allowance not tested

**Recommended Tests:**
```python
def test_rate_limit_reset():
    """Verify rate limit resets after time window."""
    # Hit rate limit
    for _ in range(100):
        response = client.get("/api/health")
    assert response.status_code == 429  # Too Many Requests
    
    # Wait for reset window
    time.sleep(60)
    
    # Should allow requests again
    response = client.get("/api/health")
    assert response.status_code == 200

def test_rate_limit_per_endpoint():
    """Verify rate limits are per-endpoint, not global."""
    # Hit limit on /api/health
    for _ in range(100):
        client.get("/api/health")
    
    # Should still allow /api/analyze
    response = client.post("/api/analyze", ...)
    assert response.status_code != 429
```

**Files to Modify:**
- Add to `tests/api/test_rate_limiting.py`

**Priority:** **LOW** (basic rate limiting works; edge cases rarely matter)

---

## Gap Summary by Category

| Category | Critical (🔴) | High (🟠) | Medium (🟡) | Low (🟢) | Total |
|----------|--------------|----------|------------|---------|-------|
| **Determinism** | 1 | 0 | 2 | 0 | 3 |
| **Contracts** | 0 | 1 | 1 | 0 | 2 |
| **Input Validation** | 0 | 1 | 0 | 0 | 1 |
| **Statelessness** | 0 | 0 | 2 | 0 | 2 |
| **Error Handling** | 0 | 0 | 0 | 1 | 1 |
| **Performance** | 0 | 0 | 0 | 1 | 1 |
| **API Security** | 0 | 0 | 0 | 1 | 1 |
| **TOTAL** | **1** | **2** | **5** | **3** | **11** |

---

## Recommended Action Plan

### Phase 1: Critical Gaps (Immediate)
1. **GAP-1: End-to-end reproducibility test** → Add `test_end_to_end_determinism()`
2. **GAP-2: Preview vs. apply metadata parity** → Add `test_dry_run_apply_metadata_parity()`

**Estimated Effort:** 2-4 hours  
**Impact:** Closes critical determinism gap, enables confident reproducibility claims

---

### Phase 2: High-Priority Gaps (Next Sprint)
3. **GAP-3: Malformed CSV edge cases** → Add `tests/test_malformed_csv.py` with 4 tests
4. **GAP-4: Concurrent apply/rollback** → Add `tests/test_concurrency.py`
5. **GAP-5: Kernel determinism** → Add `test_kernel_determinism()` to fingerprint tests

**Estimated Effort:** 4-8 hours  
**Impact:** Improves robustness and multi-user safety

---

### Phase 3: Medium-Priority Gaps (Future)
6. **GAP-6: Cross-platform reproducibility** → Add OS matrix to CI
7. **GAP-7: Backward compatibility** → Add `test_manifest_backward_compatibility()`
8. **GAP-8: Statelessness verification** → Add cleanup and overwrite tests

**Estimated Effort:** 6-10 hours  
**Impact:** Long-term maintainability and platform independence

---

### Phase 4: Low-Priority Gaps (Optional)
9. **GAP-9:** Rollback missing metadata
10. **GAP-10:** Large CSV performance
11. **GAP-11:** API rate limit edge cases

**Estimated Effort:** 2-4 hours  
**Impact:** Polish and edge case coverage

---

**Total Identified Gaps:** 11  
**Total Estimated Effort (All Phases):** 14-26 hours  
**Highest Priority:** GAP-1 (reproducibility) and GAP-2 (dry-run parity)

---

**Compiled By:** DynoAI3 Verification Agent  
**Evidence Sources:** Code inspection + test coverage analysis  
**Last Updated:** 2025-12-13
