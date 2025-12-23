# DynoAI3 Test Matrix: Behaviors Locked → Risks If Changed

**Purpose:** Comprehensive mapping of test modules to behaviors they lock, what changes would break them, and what domain they protect (math, contracts, determinism, outputs).

---

## Legend

**Protection Domains:**
- 🔢 **MATH** - Numerical algorithms, AFR→VE formulas, clamping logic
- 📋 **CONTRACT** - Data schemas, required fields, manifest structure
- 🔁 **DETERMINISM** - Reproducibility, hash verification, stable outputs
- 📤 **OUTPUT** - File generation, naming conventions, format compliance
- 🔒 **SECURITY** - Authentication, path safety, input validation

---

## Core Math & Algorithm Tests

### 1. `acceptance_test.py` (VE Apply/Rollback)
**LOC:** ~435 | **Test Functions:** 8

| Test Function | Behavior Locked | Change That Would Break It | Domain |
|---------------|-----------------|----------------------------|--------|
| `test_requirement_1_clamping()` | Factors > ±7% are capped to [0.93, 1.07] multipliers | Changing clamp formula: `multiplier = 1 + clamp(factor/100, [-max, +max])` | 🔢 MATH |
| `test_requirement_2_apply_with_precision()` | VE output has 4 decimal places (e.g., 105.0000) | Reducing precision to 2 decimals or removing f-string formatting | 🔢 MATH, 📤 OUTPUT |
| `test_requirement_3_metadata()` | Metadata has base_sha, factor_sha, applied_at_utc, max_adjust_pct, app_version | Removing any required field from metadata dict | 📋 CONTRACT |
| `test_requirement_4_rollback()` | Hash verification blocks rollback if factor file is tampered | Removing hash check in `VERollback.rollback()` | 🔁 DETERMINISM |
| `test_requirement_5_dry_run()` | Dry-run returns metadata but writes NO files | Accidentally writing files in dry-run mode | 📋 CONTRACT |
| `test_requirement_6_multiplier_bounds()` | All multipliers ∈ [0.93, 1.07] at ±7% clamp | Allowing multipliers outside this range (e.g., 1.15) | 🔢 MATH |
| `test_requirement_7_roundtrip_tolerance()` | Apply → Rollback restores original VE within 0.0001 | Precision loss (e.g., float32 instead of float64) | 🔢 MATH, 🔁 DETERMINISM |
| `test_requirement_8_deterministic_hashes()` | SHA-256 hash is same for same file across runs | Changing hash algorithm (e.g., SHA-256 → MD5) | 🔁 DETERMINISM |

**What This Test Suite Protects:**
- ✅ VE correction math correctness (clamping, precision)
- ✅ Apply/rollback reversibility contract
- ✅ Metadata completeness for audit trail
- ✅ Hash-based tamper detection

**Critical Risk if Tests Removed:**
- User could apply unclamped corrections (e.g., +50%) → engine damage
- Rollback could silently fail → user thinks they restored but didn't
- Precision loss could accumulate across multiple apply/rollback cycles

---

### 2. `selftest.py` (Smoke Test)
**LOC:** ~98 | **Test Functions:** 1 (implicit in main())

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| CLI executes successfully with synthetic CSV | Removing any required CLI arg (--csv, --outdir) | 📤 OUTPUT |
| Manifest status = "success" | Changing status field name or removing it | 📋 CONTRACT |
| Required outputs exist: VE_Correction_Delta_DYNO.csv, Diagnostics_Report.txt | Renaming output files or changing generation logic | 📤 OUTPUT |
| Minimum data volume: rows_read ≥ 1000, bins_total > 0 | Lowering thresholds or removing volume checks | 📋 CONTRACT |
| No import errors | Moving/renaming core modules (ai_tuner_toolkit, io_contracts) | 📤 OUTPUT |

**What This Test Protects:**
- ✅ Basic workflow integrity (can run end-to-end)
- ✅ Manifest schema compliance
- ✅ Expected outputs are generated

**Critical Risk if Test Removed:**
- Silent regressions in CLI argument parsing
- Manifest schema drift (breaking downstream tools)
- Missing critical outputs (user gets no VE corrections)

---

### 3. `test_bin_alignment.py` (Grid Mismatch Detection)
**LOC:** ~60 | **Test Functions:** 1

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| Mismatched RPM/kPa grids → AssertionError | Adding auto-reindexing or interpolation logic | 🔢 MATH |
| No silent grid mismatch tolerance | Relaxing grid matching to "approximate" alignment | 🔢 MATH |

**What This Test Protects:**
- ✅ Prevents VE table corruption via bin misalignment
- ✅ Enforces exact grid matching requirement

**Critical Risk if Test Removed:**
- User could apply corrections to wrong bins (e.g., 2000 RPM correction → 2500 RPM bin)
- Silent data corruption with no error message

---

### 4. `test_decel_management.py` (Decel Popping Mitigation)
**LOC:** ~900 (estimated) | **Test Functions:** ~15

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| Decel event detection via TPS rate-of-change | Changing TPS threshold (e.g., -5%/s → -10%/s) | 🔢 MATH |
| Enrichment calculation with severity presets (BASE_ENRICHMENT = 5%) | Modifying enrichment formulas or preset values | 🔢 MATH |
| MAP ceiling for decel zone (DECEL_KPA_MAX = 80 kPa) | Changing MAP ceiling constant | 🔢 MATH |
| Report generation with event counts and zone coverage | Changing report format or removing fields | 📋 CONTRACT, 📤 OUTPUT |

**What This Test Protects:**
- ✅ Decel fuel enrichment math correctness
- ✅ TPS-based event detection logic
- ✅ Report structure and metrics

**Critical Risk if Test Removed:**
- Incorrect decel enrichment → backfiring/popping continues
- False positive decel detection → over-enrichment in normal operation

---

### 5. `test_cylinder_balancing.py` (V-Twin AFR Equalization)
**LOC:** ~900 (estimated) | **Test Functions:** ~15

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| AFR imbalance threshold (DEFAULT_AFR_THRESHOLD = 0.3) | Changing threshold to be too sensitive or too lenient | 🔢 MATH |
| Correction modes: FRONT_ONLY, REAR_ONLY, BOTH, PROPORTIONAL | Removing or renaming correction modes | 📋 CONTRACT |
| Max correction limits (DEFAULT_MAX_CORRECTION_PCT = 3%, MAX = 5%) | Increasing max limits to unsafe values | 🔢 MATH |
| CSV output format for per-cylinder corrections | Changing CSV header names or structure | 📤 OUTPUT |

**What This Test Protects:**
- ✅ V-twin cylinder balancing math
- ✅ AFR equalization logic
- ✅ Safety limits on per-cylinder adjustments

**Critical Risk if Test Removed:**
- Excessive correction to one cylinder → imbalance worsens
- Incorrect AFR threshold → false positives or missed imbalances

---

## Reproducibility & Determinism Tests

### 6. `test_fingerprint.py` (Kernel Audit Trail)
**LOC:** ~100 | **Test Functions:** 2

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| Fingerprint file created: kernel_fingerprint.txt | Removing fingerprint generation step | 🔁 DETERMINISM, 📤 OUTPUT |
| Fingerprint format: `module:function param1=val1, param2=val2` | Changing format (breaking audit parsers) | 📋 CONTRACT |
| Fingerprints generated for k1, k2 (not baseline) | Removing fingerprint logic for kernels | 🔁 DETERMINISM |

**What This Test Protects:**
- ✅ Experiment reproducibility (can replay kernel with exact params)
- ✅ Audit trail for kernel usage

**Critical Risk if Test Removed:**
- No way to reproduce experimental kernel runs
- Loss of audit trail for which kernel/params were used

---

### 7. `test_delta_floor.py` (Numerical Precision)
**LOC:** ~66 | **Test Functions:** 1

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| Delta values < 0.001% → floored to 0.000% in summary | Removing floor operation | 🔢 MATH, 📋 CONTRACT |

**What This Test Protects:**
- ✅ Prevents misleading sub-threshold precision claims
- ✅ Consistent numerical reporting

**Critical Risk if Test Removed:**
- Users might see "0.0005% average delta" and think there's meaningful signal when it's noise

---

## Input/Output Contract Tests

### 8. `test_preflight_csv.py` (CSV Schema Validation)
**LOC:** ~196 | **Test Functions:** 7

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| Required columns: rpm, map_kpa, torque | Changing required column names or removing requirement | 📋 CONTRACT |
| Schema compliance detection (schema_ok boolean) | Removing schema_ok field from output | 📋 CONTRACT |
| Format detection: winpep, generic, powervision, unknown | Changing format detection heuristics | 📋 CONTRACT |
| JSON output structure: overall_ok = schema_ok AND values_ok AND parse_ok | Changing overall_ok logic (e.g., removing parse_ok) | 📋 CONTRACT |

**What This Test Protects:**
- ✅ CSV input validation before processing
- ✅ Early error detection for malformed data
- ✅ Format auto-detection

**Critical Risk if Test Removed:**
- Invalid CSV files processed silently → garbage outputs
- No early feedback on data quality issues

---

### 9. `test_runner_paths.py` (Path Safety)
**LOC:** ~150 (estimated) | **Test Functions:** ~5

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| Path traversal blocked (e.g., `../../etc/passwd`) | Removing safe_path() validation | 🔒 SECURITY |
| Output paths must be within repo root | Disabling repo boundary enforcement | 🔒 SECURITY |

**What This Test Protects:**
- ✅ Prevents directory traversal attacks
- ✅ Ensures outputs stay in controlled locations

**Critical Risk if Test Removed:**
- Attacker could read/write files outside repo (e.g., /etc/passwd)

---

## Workflow & Integration Tests

### 10. `test_autotune_workflow.py` (End-to-End Pipeline)
**LOC:** ~80 | **Test Functions:** 1

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| Workflow steps: log → AFR analysis → VE correction → PVV export | Changing step order or removing a step | 📤 OUTPUT |
| Session summary structure (afr_analysis, ve_corrections keys) | Removing or renaming summary keys | 📋 CONTRACT |
| Metrics: mean_error_pct, zones_lean, zones_rich, zones_ok, etc. | Changing metric names or calculation logic | 📋 CONTRACT, 🔢 MATH |
| Output artifacts: TuneLab script, PVV file | Renaming output files or changing formats | 📤 OUTPUT |

**What This Test Protects:**
- ✅ Full workflow integrity (all steps execute)
- ✅ Session summary contract
- ✅ Output artifact generation

**Critical Risk if Test Removed:**
- Workflow step regression (e.g., PVV export silently breaks)
- Session summary schema drift

---

### 11. `test_jetdrive_client_protocol.py` (KLHDV Protocol)
**LOC:** ~650 (estimated) | **Test Functions:** ~10

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| KLHDV frame structure: [Key][Len][Host][Seq][Dest][Value...] | Changing frame parsing logic | 📋 CONTRACT |
| Multicast address: 224.0.2.10:22344 | Changing multicast group or port | 📋 CONTRACT |
| Message types: 0x01 ChannelInfo, 0x02 ChannelValues, etc. | Changing message type codes | 📋 CONTRACT |
| ChannelInfo payload structure (50-byte provider name, 34-byte channels) | Changing payload parsing | 📋 CONTRACT |

**What This Test Protects:**
- ✅ JetDrive protocol compliance
- ✅ Correct parsing of multicast frames
- ✅ Channel metadata handling

**Critical Risk if Test Removed:**
- Silent protocol version mismatch → garbled data
- Incompatibility with JetDrive hardware

---

## API Security & Infrastructure Tests

### 12. `tests/api/test_security.py` (Path Traversal, Input Sanitization)
**LOC:** ~300 (estimated) | **Test Functions:** ~8

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| Path traversal blocked in API endpoints | Removing safe_path() checks | 🔒 SECURITY |
| Malicious CSV cell sanitization | Disabling sanitize_csv_cell() | 🔒 SECURITY |
| Reject paths with `..` or absolute paths | Allowing unsafe path patterns | 🔒 SECURITY |

**What This Test Protects:**
- ✅ Prevents directory traversal attacks via API
- ✅ CSV injection prevention

**Critical Risk if Test Removed:**
- Attacker could read arbitrary files via API
- CSV injection could execute formulas in Excel

---

### 13. `tests/api/test_authentication.py` (API Key Validation)
**LOC:** ~450 (estimated) | **Test Functions:** ~12

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| API key required for protected endpoints | Removing authentication middleware | 🔒 SECURITY |
| Token expiration enforced | Disabling token expiry check | 🔒 SECURITY |
| Invalid keys rejected with 401 | Changing HTTP status code | 📋 CONTRACT |

**What This Test Protects:**
- ✅ API authentication enforcement
- ✅ Unauthorized access prevention

**Critical Risk if Test Removed:**
- Anyone could access API without credentials
- Token-based attacks (replay, hijacking)

---

### 14. `tests/api/test_rate_limiting.py` (Request Throttling)
**LOC:** ~150 (estimated) | **Test Functions:** ~5

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| Rate limits enforced per IP/endpoint | Disabling rate limiter | 🔒 SECURITY |
| 429 status code returned when limit exceeded | Changing status code | 📋 CONTRACT |

**What This Test Protects:**
- ✅ Denial-of-service prevention
- ✅ API abuse mitigation

**Critical Risk if Test Removed:**
- Attacker could flood API with requests
- Server overload → downtime

---

### 15. `tests/api/test_request_id_middleware.py` (Request Tracking)
**LOC:** ~150 (estimated) | **Test Functions:** ~5

| Behavior Locked | Change That Would Break It | Domain |
|-----------------|----------------------------|--------|
| Unique request ID per API call | Removing request ID middleware | 📋 CONTRACT |
| Request ID in response headers | Changing header name or removing | 📋 CONTRACT |

**What This Test Protects:**
- ✅ Request traceability for debugging
- ✅ Log correlation across services

**Critical Risk if Test Removed:**
- Difficult to trace specific requests in logs
- No correlation between client and server logs

---

## Summary Statistics

| Protection Domain | Test Modules | Test Functions | Critical Risk Level |
|-------------------|--------------|----------------|---------------------|
| 🔢 **MATH** | 8 | ~80 | **CRITICAL** - Engine damage if broken |
| 📋 **CONTRACT** | 15 | ~100 | **HIGH** - Data corruption, schema drift |
| 🔁 **DETERMINISM** | 4 | ~20 | **HIGH** - Reproducibility loss, audit trail loss |
| 📤 **OUTPUT** | 10 | ~40 | **MEDIUM** - Workflow breakage, missing artifacts |
| 🔒 **SECURITY** | 7 | ~35 | **CRITICAL** - Security vulnerabilities |

**Total Coverage:** 34 modules, 251 test functions, ~4,343 LOC

---

## Critical Test Dependency Graph

```
                    ┌─────────────────┐
                    │  selftest.py    │ ← Smoke test (must pass first)
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
    ┌──────────────────┐          ┌──────────────────┐
    │ acceptance_test  │          │ test_preflight   │
    │ (Apply/Rollback) │          │ (CSV Validation) │
    └─────────┬────────┘          └────────┬─────────┘
              │                            │
              └──────────┬─────────────────┘
                         ▼
              ┌──────────────────────┐
              │  Core Math Tests     │
              │ (decel, cylinder,    │
              │  bin_alignment)      │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Protocol Tests      │
              │ (JetDrive, LiveLink) │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  API Security Tests  │
              │ (auth, rate limit)   │
              └──────────────────────┘
```

**Test Execution Order (Recommended):**
1. `selftest.py` - Smoke test (basic workflow)
2. `acceptance_test.py` - Core contracts
3. `test_preflight_csv.py` - Input validation
4. Math tests (decel, cylinder, bin_alignment)
5. Protocol tests (JetDrive, LiveLink)
6. API tests (security, auth, rate limiting)

---

## High-Impact Tests (DO NOT REMOVE)

| Test Module | Impact if Removed | Protected Behavior |
|-------------|-------------------|-------------------|
| `acceptance_test.py` | **CRITICAL** - User could apply unclamped corrections → engine damage | VE apply/rollback math, clamping, hash verification |
| `test_bin_alignment.py` | **CRITICAL** - Silent VE table corruption | Grid mismatch detection |
| `tests/api/test_security.py` | **CRITICAL** - Directory traversal, CSV injection | Path safety, input sanitization |
| `selftest.py` | **HIGH** - No smoke test for basic workflow | CLI execution, manifest generation |
| `test_decel_management.py` | **HIGH** - Incorrect decel enrichment | Decel event detection, enrichment math |
| `test_fingerprint.py` | **MEDIUM** - Loss of experiment reproducibility | Kernel audit trail |

**Total High/Critical Tests:** 6 modules protecting most critical behaviors

---

**Compiled By:** DynoAI3 Verification Agent  
**Last Updated:** 2025-12-13  
**Source:** Analysis of 34 test modules, 251 test functions, 4,343 LOC
