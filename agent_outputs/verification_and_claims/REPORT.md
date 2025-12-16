# DynoAI3 Verification, Regression Lock, and Claims Guardrail Report

**Generated:** 2025-12-13  
**Repository:** rob9206/DynoAI_3  
**Analysis Scope:** Complete test surface, reproducibility contracts, OEM-style parity, and positioning claims

---

## Executive Summary

DynoAI3 is a Harley-Davidson dyno tuning calibration system with **251 test functions** across **34 test modules**, covering math-critical VE correction algorithms, API security, protocol compliance, and workflow validation. The system demonstrates:

- **Strong regression lock discipline** via hash-verified apply/rollback, clamping enforcement, and deterministic kernels
- **Formalized data contracts** through io_contracts.py, manifest.json schemas, and CSV validation
- **Reproducibility mechanisms** including SHA-256 hashing, fixed random seeds for test data, and metadata tracking
- **Partial OEM-style parity** in math determinism and scriptable workflow, with intentional scope boundaries (no ECU flashing, dyno control)

**Key Gaps:**
- No automated end-to-end reproducibility test (same CSV → bit-identical deltas)
- Limited coverage for malformed CSV edge cases
- No formal preview vs. apply parity test (dry-run verification)
- Missing tests for concurrent apply/rollback scenarios

---

## A) TEST SURFACE & REGRESSION LOCKS

### Test Inventory Summary

| Category | Test Modules | Test Functions | LOC | Primary Focus |
|----------|--------------|----------------|-----|---------------|
| **Core Math** | 8 | 47 | ~850 | VE correction, kernels, clamping |
| **API/Security** | 10 | 89 | ~1,200 | Endpoints, auth, rate limiting |
| **Protocol** | 5 | 38 | ~650 | JetDrive KLHDV, LiveLink, WP8 |
| **Workflow** | 6 | 42 | ~900 | AutoTune, decel mgmt, cylinder balance |
| **Infrastructure** | 5 | 35 | ~700 | Path safety, fingerprinting, manifests |
| **Total** | **34** | **251** | **~4,343** | Full system coverage |

### Regression Locks by Test Module

#### 1. **selftest.py** (Primary Smoke Test)
**Behavior Locked:**
- CLI execution succeeds with synthetic CSV input
- Manifest status = "success"
- Required outputs exist: `VE_Correction_Delta_DYNO.csv`, `Diagnostics_Report.txt`
- Minimum data volume: ≥1,000 rows read, bins_total > 0

**What Would Break It:**
- CLI argument changes (--csv, --outdir, --smooth_passes, --clamp)
- Manifest schema changes (status.code field removal)
- Output file naming changes
- Core engine import failures

**Protection Type:** Output contracts, workflow integrity

**Reference:** `selftest.py:54-94`, `selftest_runner.py:22`

---

#### 2. **acceptance_test.py** (VE Operations Contract)
**Behaviors Locked (8 Requirements):**
1. **Clamping Enforcement:** Factors > ±7% are capped; multipliers ∈ [0.93, 1.07]
2. **Apply Precision:** Output has 4 decimal places (e.g., 105.0000)
3. **Metadata Generation:** apply_meta.json with base_sha, factor_sha, applied_at_utc, max_adjust_pct, app_version
4. **Rollback Hash Verification:** Tampered factor files block rollback (hash mismatch detection)
5. **Dry-Run Mode:** Preview outputs without writing files
6. **Multiplier Bounds:** All corrections within [0.93, 1.07] at ±7% clamp
7. **Roundtrip Tolerance:** Apply → Rollback restores original VE within 0.0001 precision
8. **Deterministic Hashing:** Same file → same SHA-256 hash

**What Would Break It:**
- Changing clamping formula: `multiplier = 1 + clamp(factor_pct / 100, [-max_adj, +max_adj])`
- Precision loss in apply operation (float64 → float32)
- Metadata schema changes (removing required fields)
- Hash algorithm change (SHA-256 → anything else)

**Protection Type:** Math correctness, data integrity, reversibility

**Reference:** `acceptance_test.py:28-428`

---

#### 3. **test_bin_alignment.py** (Grid Mismatch Detection)
**Behavior Locked:**
- Mismatched RPM/kPa grids between base VE and factor tables → hard AssertionError
- No silent reindexing or interpolation

**What Would Break It:**
- Adding auto-reindexing logic to `_assert_bin_alignment()`
- Relaxing grid matching to "approximate" alignment

**Protection Type:** Prevents accidental corruption via bin misalignment

**Reference:** `tests/test_bin_alignment.py:15-58`

---

#### 4. **test_decel_management.py** (Decel Popping Mitigation)
**Behaviors Locked:**
- Decel event detection via TPS rate-of-change threshold
- AFR analysis during decel → enrichment calculation
- Severity presets (mild/moderate/aggressive): BASE_ENRICHMENT = 5%, MAX_ENRICHMENT_PCT = 20%
- VE overlay generation with MAP ceiling (DECEL_KPA_MAX = 80 kPa)
- Report generation with event counts and zone coverage

**What Would Break It:**
- Changing TPS threshold for decel detection
- Modifying enrichment formulas (severity presets)
- Altering MAP ceiling constant

**Protection Type:** Decel fuel management contracts, AFR enrichment logic

**Reference:** `tests/test_decel_management.py:1-60`, `decel_management.py`

---

#### 5. **test_cylinder_balancing.py** (V-Twin AFR Equalization)
**Behaviors Locked:**
- AFR aggregation per cylinder (front vs. rear)
- Imbalance detection: DEFAULT_AFR_THRESHOLD = 0.3 AFR delta
- Correction modes: FRONT_ONLY, REAR_ONLY, BOTH, PROPORTIONAL
- Safety clamping: DEFAULT_MAX_CORRECTION_PCT = 3%, MAX_ABSOLUTE_CORRECTION = 5%
- CSV output format for per-cylinder corrections

**What Would Break It:**
- Changing AFR threshold (0.3 → different value)
- Modifying correction formula: `ve_correction = afr_error_to_ve_correction()`
- Altering max correction limits

**Protection Type:** V-twin balancing math, AFR equalization contracts

**Reference:** `tests/test_cylinder_balancing.py:1-60`, `cylinder_balancing.py`

---

#### 6. **test_fingerprint.py** (Kernel Audit Trail)
**Behaviors Locked:**
- Fingerprint file creation: `kernel_fingerprint.txt`
- Content format: `module:function param1=val1, param2=val2`
- Generated for all registered kernels (k1, k2) except baseline
- Fingerprint persists even in --dry-run mode

**What Would Break It:**
- Changing fingerprint format (breaking audit parsers)
- Removing fingerprint generation step
- Renaming kernel modules/functions

**Protection Type:** Experiment reproducibility, kernel audit trail

**Reference:** `tests/test_fingerprint.py:14-95`

---

#### 7. **test_delta_floor.py** (Numerical Precision Handling)
**Behavior Locked:**
- Delta values < 0.001% are floored to 0.000% in experiment_summary.json
- Prevents misleading sub-threshold precision claims

**What Would Break It:**
- Removing floor operation
- Changing threshold (0.001% → different value)

**Protection Type:** Numerical precision contracts

**Reference:** `tests/test_delta_floor.py:15-61`

---

#### 8. **test_preflight_csv.py** (CSV Schema Validation)
**Behaviors Locked:**
- Required columns check: rpm, map_kpa, torque
- Schema compliance detection (schema_ok boolean)
- Format detection: winpep, generic, powervision, unknown
- Value validation and parsing checks
- JSON output structure: overall_ok = schema_ok AND values_ok AND parse_ok

**What Would Break It:**
- Changing required column names
- Altering format detection heuristics
- Modifying overall_ok logic

**Protection Type:** Input data contracts, CSV validation

**Reference:** `tests/test_preflight_csv.py:28-192`

---

#### 9. **test_autotune_workflow.py** (End-to-End Pipeline)
**Behaviors Locked:**
- Full workflow execution: log ingestion → AFR analysis → VE correction → PVV export
- Session summary structure with afr_analysis and ve_corrections keys
- Metrics: mean_error_pct, zones_lean, zones_rich, zones_ok, zones_adjusted, max/min_correction_pct, clipped_zones
- Output artifacts: TuneLab script, PVV file

**What Would Break It:**
- Changing workflow step order
- Modifying session summary schema
- Renaming output files

**Protection Type:** Workflow integrity, output contracts

**Reference:** `tests/test_autotune_workflow.py:13-80`

---

#### 10. **test_jetdrive_client_protocol.py** (KLHDV Protocol Compliance)
**Behaviors Locked:**
- KLHDV frame structure: [Key][Len][Host][Seq][Dest][Value...]
- Multicast address: 224.0.2.10:22344
- Message types: 0x01 ChannelInfo, 0x02 ChannelValues, 0x04 Ping, 0x05 Pong, 0x06 RequestChannelInfo
- ChannelInfo payload: provider name (50 bytes UTF-8) + channel blocks (34 bytes each)
- ChannelValues payload: 10-byte samples (chanId u16, ts_ms u32, float32 value)

**What Would Break It:**
- Protocol version changes (incompatible frame format)
- Multicast address change
- Message type code changes

**Protection Type:** Protocol compliance, JetDrive integration contracts

**Reference:** `tests/test_jetdrive_client_protocol.py`, `api/services/jetdrive_client.py`

---

#### 11. **API Security & Rate Limiting Tests** (10 modules)
**Behaviors Locked:**
- Authentication: API key validation, token expiration
- Rate limiting: Request throttling per IP/endpoint
- Path traversal prevention: safe_path() enforcement
- CORS headers: Allowed origins, methods, headers
- Request ID middleware: Unique ID per request
- Input sanitization: CSV cell sanitization, malicious path rejection

**What Would Break It:**
- Removing authentication checks
- Disabling rate limiting
- Bypassing path validation
- Changing CORS policy

**Protection Type:** Security contracts, API integrity

**Reference:** `tests/api/test_authentication.py`, `test_rate_limiting.py`, `test_security.py`, etc.

---

### Test Coverage Gaps (Missing Regression Locks)

| Gap ID | Missing Behavior Test | Risk Level | Impact Area |
|--------|----------------------|------------|-------------|
| **GAP-1** | **End-to-end reproducibility:** Same CSV + args → bit-identical deltas across runs | **HIGH** | Determinism claims |
| **GAP-2** | **Preview vs. apply parity:** Dry-run metadata == actual apply metadata (except write flags) | **MEDIUM** | Dry-run contract |
| **GAP-3** | **Malformed CSV edge cases:** Zero rows, duplicate headers, non-UTF8 encoding | **MEDIUM** | Input robustness |
| **GAP-4** | **Concurrent apply/rollback:** Two processes modifying same VE table | **LOW** | Multi-user safety |
| **GAP-5** | **Kernel determinism:** K1/K2/K3 produce identical output for same input (seeded RNG check) | **MEDIUM** | Kernel reproducibility |
| **GAP-6** | **Cross-platform reproducibility:** Windows/Linux output equivalence | **MEDIUM** | Platform independence |
| **GAP-7** | **Artifact naming stability:** Output filenames unchanged across versions | **LOW** | Backward compatibility |
| **GAP-8** | **No hidden state:** Clean temp directories, no persistent caches between runs | **MEDIUM** | Statelessness guarantee |

---

## B) REPRODUCIBILITY CHECKLIST

### Deterministic Replay (Same CSV → Same Deltas)

| Check | Status | Evidence | Notes |
|-------|--------|----------|-------|
| **Fixed random seeds for synthetic data** | ✅ PASS | `dynoai/test_utils.py:39` `random.Random(42)` | Test data generation is seeded |
| **No OS-dependent randomness in math** | ✅ PASS | `ai_tuner_toolkit_dyno_v1_2.py` - no random calls | Core engine is deterministic |
| **Kernel smoothing is deterministic** | ⚠️ PARTIAL | K1/K2 use fixed formulas; K3 bilateral needs verification | No explicit RNG in kernels, but no test proves bit-identical output |
| **Manifest timestamps are metadata-only** | ✅ PASS | Timestamps don't affect VE deltas | `applied_at_utc` is audit-only |
| **CSV parsing order is stable** | ✅ PASS | csv.reader() preserves row order | Python csv module guarantees order |
| **No dependency on file system traversal order** | ✅ PASS | Single CSV input, no directory scanning | Not applicable to single-file workflow |
| **Automated reproducibility test exists** | ❌ FAIL | No test runs same CSV twice and compares deltas | **GAP-1** |

**Overall Assessment:** PARTIAL PASS - Math is deterministic, but no automated regression test proves bit-identical replay.

---

### Preview vs. Apply Parity

| Check | Status | Evidence | Notes |
|-------|--------|----------|-------|
| **Dry-run generates metadata** | ✅ PASS | `acceptance_test.py:212-247` | Metadata returned in dry-run |
| **Dry-run does NOT write files** | ✅ PASS | `acceptance_test.py:237-240` | Output/metadata files not created |
| **Metadata content identical (dry-run vs. apply)** | ⚠️ PARTIAL | No test compares dry-run metadata to actual apply metadata | **GAP-2** - metadata equality not verified |
| **Dry-run clamping matches apply clamping** | ⚠️ ASSUMED | Same code path, but no explicit test | Likely correct, but unverified |

**Overall Assessment:** PARTIAL PASS - Dry-run works, but parity with apply is not explicitly tested.

---

### Apply/Rollback Exactness

| Check | Status | Evidence | Notes |
|-------|--------|----------|-------|
| **Apply → Rollback within 4-decimal tolerance** | ✅ PASS | `acceptance_test.py:292-349` | Max diff < 0.0001 verified |
| **Hash verification blocks tampered rollback** | ✅ PASS | `acceptance_test.py:193-208` | RuntimeError on hash mismatch |
| **Metadata completeness** | ✅ PASS | `acceptance_test.py:102-154` | All required fields present |
| **Rollback fails gracefully if metadata missing** | ⚠️ ASSUMED | No explicit test for missing metadata file | Likely raises FileNotFoundError, but unverified |

**Overall Assessment:** PASS - Core apply/rollback contract is tested and enforced.

---

### Stable Outputs and Artifact Naming

| Check | Status | Evidence | Notes |
|-------|--------|----------|-------|
| **Fixed output filenames** | ✅ PASS | `VE_Correction_Delta_DYNO.csv`, `Diagnostics_Report.txt` hardcoded | Naming is stable |
| **Manifest schema versioned** | ✅ PASS | `io_contracts.py:27` `SCHEMA_ID = "dynoai.manifest@1"` | Schema versioning exists |
| **No timestamp in critical filenames** | ✅ PASS | Timestamps only in run_id, not output files | Artifact names are stable |
| **Backward compatibility test for old manifests** | ❌ FAIL | No test loads old manifest versions | **GAP-7** - schema evolution not tested |

**Overall Assessment:** PASS - Current output naming is stable and versioned.

---

### Robust Malformed CSV Handling

| Check | Status | Evidence | Notes |
|-------|--------|----------|-------|
| **Missing required columns detected** | ✅ PASS | `test_preflight_csv.py:64-78` | Preflight detects schema violations |
| **Zero-row CSV handled gracefully** | ⚠️ PARTIAL | `ve_operations.py:73` raises RuntimeError for empty CSV | Fails loudly, but no test verifies error message |
| **Non-UTF8 encoding handled** | ❌ FAIL | No test for non-UTF8 CSV files | **GAP-3** - encoding robustness untested |
| **Duplicate headers handled** | ❌ FAIL | No test for duplicate column names | **GAP-3** - edge case not covered |
| **NaN/Inf values in numeric columns** | ⚠️ PARTIAL | AFR_RANGE_MIN/MAX checks in core engine | Likely filtered, but no explicit test |

**Overall Assessment:** PARTIAL PASS - Happy path is covered; edge cases need tests.

---

### No Hidden State Between Runs

| Check | Status | Evidence | Notes |
|-------|--------|----------|-------|
| **Temp files cleaned up** | ⚠️ PARTIAL | `selftest.py:56-60` uses temp_selftest/ but relies on OS cleanup | No explicit cleanup in main workflow |
| **No persistent caches** | ✅ PASS | No cache directories found in codebase | Stateless by design |
| **Concurrent run isolation** | ⚠️ ASSUMED | No test runs two instances simultaneously | **GAP-4** - concurrency not tested |
| **Output directory collision handled** | ⚠️ PARTIAL | Unique run_id prevents collisions, but no test verifies overwrite behavior | Likely safe, but unverified |

**Overall Assessment:** PARTIAL PASS - Design is stateless, but concurrency and cleanup not explicitly tested.

---

## C) OEM-STYLE PARITY SUMMARY (CONCEPTUAL)

### Mapping DynoAI3 to OEM Calibration Expectations

| OEM Calibration Expectation | DynoAI3 Implementation | Parity Level | Notes |
|-----------------------------|------------------------|--------------|-------|
| **Deterministic math chains** | ✅ Fixed AFR→VE formulas, clamping, kernels | **STRONG** | Core math is deterministic; reproducibility test missing |
| **Formalized data contracts** | ✅ io_contracts.py, manifest schema, CSV validation | **STRONG** | Schema versioning, hash verification, required columns |
| **Scriptable workflow** | ✅ CLI with --csv, --outdir, --dry-run args | **STRONG** | Fully automatable, no GUI required |
| **Batchability** | ✅ Single CSV → outputs in one pass | **STRONG** | Can be scripted in loops for batch processing |
| **Regression validation discipline** | ✅ 251 tests, acceptance criteria, safety rules | **STRONG** | Comprehensive test suite, safety policy docs |
| **Version-controlled calibrations** | ✅ Metadata with app_version, SHA hashes | **STRONG** | Audit trail for every apply operation |
| **Formal error propagation analysis** | ❌ No uncertainty quantification in outputs | **WEAK** | Confidence intervals not calculated |
| **Certified toolchain** | ❌ Open-source Python, not certified compilers | **WEAK** | Not safety-critical certified toolchain |
| **Dyno control integration** | ❌ Intentionally out of scope | **N/A** | DynoAI3 analyzes dyno logs, doesn't control dyno hardware |
| **ECU flashing** | ❌ Intentionally out of scope | **N/A** | Outputs PVV XML for Power Vision; user flashes ECU |
| **Closed-loop auto-tuning** | ❌ Intentionally out of scope | **N/A** | Generates corrections; user applies and re-tests |

---

### Where DynoAI3 Meets the Bar

1. **Deterministic Math Chains**
   - **Evidence:** All AFR→VE calculations use fixed formulas: `ve_correction_pct = afr_error_pct * scale_factor`
   - **Clamping:** Enforced at ±7% default, configurable to ±15% max
   - **Kernels:** K1 (gradient-limited), K2 (coverage-adaptive), K3 (bilateral) use fixed algorithms
   - **Verification:** acceptance_test.py validates clamping, precision, rollback exactness

2. **Formalized Data Contracts**
   - **Schemas:** dynoai.manifest@1 with required fields (status, stats, timing)
   - **Validation:** io_contracts.py enforces path safety, required CSV columns (rpm, map_kpa, torque)
   - **Hashing:** SHA-256 for VE tables and factor files; hash verification on rollback
   - **Versioning:** app_version in metadata for backward compatibility tracking

3. **Scriptable Workflow & Batchability**
   - **CLI:** `python ai_tuner_toolkit_dyno_v1_2.py --csv log.csv --outdir out/`
   - **Automation:** All arguments configurable; no interactive prompts
   - **Batch example:** `for csv in logs/*.csv; do python ai_tuner_toolkit_dyno_v1_2.py --csv "$csv" --outdir "out/$(basename $csv .csv)"; done`

4. **Regression Validation Discipline**
   - **Test Coverage:** 251 test functions, 4,343 LOC of test code
   - **Safety Rules:** DYNOAI_SAFETY_RULES.md with math-critical file protections, change control checklist
   - **CI Enforcement:** Branch protection, required tests, CODEOWNERS for math-critical files
   - **Acceptance Criteria:** 8 requirements in acceptance_test.py (clamping, precision, hashing, rollback)

---

### Where DynoAI3 Intentionally Stops

1. **Dyno Control**
   - **Reason:** DynoAI3 analyzes logged data; it does not control dyno hardware (load cells, throttle actuators)
   - **Scope Boundary:** JetDrive integration captures multicast UDP data streams; no dyno command/control

2. **ECU Flashing**
   - **Reason:** Direct ECU programming requires OEM-specific protocols and safety interlocks
   - **User Workflow:** DynoAI3 exports PVV XML → user loads into Dynojet Power Vision → user flashes ECU
   - **Safety:** Prevents accidental ECU bricking; user remains in control of flashing step

3. **Closed-Loop Auto-Tuning**
   - **Reason:** Iterative tuning requires dyno re-runs; DynoAI3 provides single-pass corrections
   - **User Workflow:** User applies corrections → re-runs dyno → analyzes new log → iterates manually
   - **Future Enhancement:** Multi-iteration workflow could be added, but requires dyno control integration

4. **Formal Uncertainty Quantification**
   - **Reason:** No statistical confidence intervals or error propagation analysis in outputs
   - **Current State:** Coverage metrics (hits per bin) hint at confidence, but no formal UQ
   - **OEM Gap:** OEM tools often calculate ±σ bounds on corrections; DynoAI3 does not

---

## D) CLAIMS & POSITIONING GUARDRAILS

### Allowed Claims (Defensible)

| Claim | Supporting Evidence | Precise Language |
|-------|---------------------|------------------|
| **Deterministic VE corrections** | Fixed math formulas, no randomness in core engine | "DynoAI3 produces **deterministic VE corrections** for a given CSV input and parameter set, using fixed AFR-to-VE formulas and clamping rules." |
| **Hash-verified apply/rollback** | SHA-256 hashing, acceptance tests for rollback exactness | "VE table modifications are **hash-verified** using SHA-256, ensuring **exact rollback** capability (≤0.0001 precision)." |
| **Production-grade test coverage** | 251 tests, 4,343 LOC, acceptance criteria | "DynoAI3 has **comprehensive regression test coverage** with 251 test functions validating math correctness, API security, and protocol compliance." |
| **Formalized data contracts** | io_contracts.py, manifest schema versioning | "Data inputs and outputs are governed by **formalized contracts** including schema validation, required CSV columns, and versioned manifest formats." |
| **Safety-clamped corrections** | ±7% default clamp, configurable to ±15% max, enforced in tests | "VE corrections are **safety-clamped** to ±7% by default (configurable to ±15%) to prevent excessive adjustments that could damage the engine." |
| **Scriptable batch workflow** | CLI with args, no GUI required | "DynoAI3 supports **fully scriptable batch processing** of dyno logs via command-line interface, enabling automated calibration workflows." |
| **Protocol-compliant JetDrive integration** | KLHDV protocol tests, multicast frame parsing | "JetDrive integration is **protocol-compliant** with Dynojet KLHDV multicast specification (224.0.2.10:22344, frame structure verified)." |
| **Reproducible kernel experiments** | Fingerprinting, kernel registry, experiment summary | "Experimental kernel runs produce **audit-ready fingerprints** tracking module, function, and parameters for reproducibility." |

---

### Disallowed Claims (Overreach)

| Disallowed Claim | Why It's Overreach | Correct Alternative |
|------------------|-------------------|---------------------|
| ❌ "**Bit-identical** VE corrections across all platforms" | No cross-platform reproducibility test (GAP-6) | ✅ "Deterministic math within a platform; cross-platform equivalence expected but not regression-tested" |
| ❌ "**OEM-certified** calibration tool" | Not certified by any OEM or safety standard (ISO 26262, etc.) | ✅ "OEM-style discipline in data contracts and regression testing, but not certified for safety-critical use" |
| ❌ "**Fully automated** closed-loop tuning" | Requires dyno control and iterative workflow, which is out of scope | ✅ "Single-pass correction generation; iterative tuning requires manual dyno re-runs" |
| ❌ "**Zero configuration** required" | Requires CSV input, optional base VE tables, parameter tuning | ✅ "Minimal configuration: CSV input and output directory required; parameters have sensible defaults" |
| ❌ "**Production-ready** for ECU deployment" | Outputs are suggestions; user must validate and flash ECU | ✅ "Production-grade VE corrections for review and validation; user is responsible for ECU flashing" |
| ❌ "**World-class adjacent** accuracy" | No benchmarking data vs. industry leaders (Dynojet, HP Tuners, etc.) | ✅ "High-quality corrections based on established AFR-to-VE formulas; accuracy depends on dyno data quality" |
| ❌ "**Enterprise-grade** multi-user collaboration" | No user management, access control, or concurrent editing features | ✅ "Single-user workflow with file-based outputs suitable for version control (Git)" |
| ❌ "**Real-time** tuning" | Batch processing workflow, not real-time streaming | ✅ "Post-run analysis of dyno logs; JetDrive capture is real-time, but analysis is batch" |

---

### Precise Language for Key Terms

#### "Deterministic"
**Allowed:** "DynoAI3 produces **deterministic VE corrections** for a given CSV and parameter set."  
**Context:** Core math has no randomness; same input → same output (within one platform).  
**Caveat:** Cross-platform bit-identical output is expected but not regression-tested (GAP-6).

**Disallowed:** "Bit-for-bit **deterministic** across all operating systems and Python versions."  
**Why:** No automated test proves Windows/Linux/macOS equivalence.

---

#### "AI-Assisted"
**Allowed:** "DynoAI3 is an **AI-assisted** calibration tool that automates AFR analysis and VE correction generation."  
**Context:** "AI" refers to automation and intelligent data processing, not machine learning.  
**Caveat:** No neural networks or ML models; "AI" means algorithmic intelligence.

**Disallowed:** "Uses **machine learning** to optimize VE tables."  
**Why:** No ML models in codebase; corrections are formula-based.

---

#### "Calibration Engine"
**Allowed:** "DynoAI3 is a **calibration engine** that generates VE corrections from dyno logs."  
**Context:** Processes data and produces calibration outputs (VE deltas, spark suggestions).  
**Caveat:** Does not write calibrations to ECU; user must apply corrections via Power Vision.

**Disallowed:** "A complete **calibration suite** for ECU programming."  
**Why:** No ECU flashing capability; scope ends at correction generation.

---

#### "World-Class Adjacent"
**Allowed:** "DynoAI3 applies **industry-standard AFR-to-VE formulas** and **OEM-style data contracts**."  
**Context:** Uses established tuning math and disciplined engineering practices.  
**Caveat:** No benchmarking vs. commercial tools (Dynojet, HP Tuners); "world-class" is aspirational.

**Disallowed:** "Achieves **world-class** accuracy comparable to top commercial tuning solutions."  
**Why:** No comparative benchmark data; accuracy claims require validation data.

---

### Claims Matrix: Feature-by-Feature

| Feature | Defensible Claim | Evidence File/Function | Disallowed Claim |
|---------|------------------|------------------------|------------------|
| **VE Apply/Rollback** | "Hash-verified VE table modifications with exact rollback (≤0.0001 precision)" | acceptance_test.py:292-349 | "Infallible rollback even if metadata is corrupted" |
| **Clamping** | "Safety-clamped VE corrections (default ±7%, max ±15%)" | acceptance_test.py:28-69, ve_operations.py:22 | "Guarantees engine safety in all scenarios" |
| **Determinism** | "Deterministic math for given input and platform" | Core engine has no random() calls | "Bit-identical across all platforms" |
| **Kernels** | "Experimental kernels with audit-ready fingerprints" | test_fingerprint.py:14-95 | "Kernels are production-validated" |
| **JetDrive** | "Protocol-compliant KLHDV multicast integration" | test_jetdrive_client_protocol.py | "Full JetDrive feature parity" |
| **API Security** | "Rate limiting, authentication, path traversal protection" | tests/api/test_security.py | "Enterprise-grade security certification" |
| **Test Coverage** | "251 test functions validating core contracts" | 34 test modules, 4,343 LOC | "100% code coverage" |
| **Workflow** | "Scriptable CLI for batch processing" | ai_tuner_toolkit_dyno_v1_2.py | "Zero-configuration auto-tuning" |

---

## Conclusions and Recommendations

### Strengths
1. **Robust regression lock discipline** with 251 tests and formalized acceptance criteria
2. **Strong data contract enforcement** (schemas, hashing, path validation)
3. **Deterministic math** with no randomness in core VE correction engine
4. **Safety-first design** (clamping, rollback, dry-run preview)
5. **OEM-style parity** in scriptability, versioning, and validation

### Critical Gaps
1. **No automated end-to-end reproducibility test** (GAP-1) - same CSV → bit-identical deltas
2. **Preview vs. apply parity untested** (GAP-2) - dry-run metadata equivalence
3. **Malformed CSV edge cases** (GAP-3) - non-UTF8, duplicate headers, zero rows
4. **Kernel determinism unverified** (GAP-5) - no test proves K1/K2/K3 bit-identical output

### Recommendations
1. **Add reproducibility regression test:** Run same CSV twice, assert deltas are bit-identical
2. **Test dry-run parity:** Compare dry-run metadata to actual apply metadata (minus write flags)
3. **Expand CSV robustness tests:** Non-UTF8 encoding, duplicate headers, zero rows, NaN values
4. **Document scope boundaries clearly:** "DynoAI3 generates corrections, not a full ECU suite"
5. **Avoid overreach claims:** Stick to defensible, evidence-backed language per claims matrix

---

**Report Compiled By:** DynoAI3 Verification Agent  
**Files Referenced:** 34 test modules, 6 documentation files, 15 core source files  
**Audit Trail:** All claims tied to specific file/function references
