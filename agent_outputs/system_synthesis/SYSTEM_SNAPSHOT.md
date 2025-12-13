# DynoAI3 System Snapshot

**Document Version:** 1.0  
**Generated:** 2025-12-13  
**Schema:** dynoai.system_snapshot@1  
**Purpose:** Unified, audit-ready reference for DynoAI3 architecture, invariants, contracts, and reproducibility status

---

## Executive Summary

DynoAI3 is an intelligent dyno tuning system that transforms WinPEP logs into production-ready VE correction tables for Harley-Davidson ECM calibration. The system prioritizes **safety**, **reproducibility**, and **extensibility** through rigorous mathematical controls, comprehensive testing, and formal IO contracts.

**Core Capabilities:**
- AFR error analysis and VE correction generation (±7% to ±15% clamped)
- Multi-pass adaptive kernel smoothing (K1/K2/K3 experimental frameworks)
- JetDrive/JetStream live data capture via KLHDV multicast protocol
- Power Vision/Power Core ECM integration with PVV XML export
- Hash-verified VE table apply/rollback operations
- Web-based analysis interface with REST API

---

## 1. Architecture and Data Flow

### 1.1 System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        DynoAI3 System                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │  Input Sources   │         │  Base VE Tables  │             │
│  │  - WinPEP CSV    │         │  - tables/*.csv  │             │
│  │  - JetDrive KLHDV│         └────────┬─────────┘             │
│  │  - Power Vision  │                  │                        │
│  └────────┬─────────┘                  │                        │
│           │                            │                        │
│           └───────────┬────────────────┘                        │
│                       ▼                                         │
│         ┌──────────────────────────────┐                       │
│         │    Core Analysis Engine      │                       │
│         │  ai_tuner_toolkit_dyno_v1_2  │                       │
│         │  - AFR binning & correction  │                       │
│         │  - Kernel smoothing (K1-K3)  │                       │
│         │  - Clamping enforcement      │                       │
│         └──────────┬───────────────────┘                       │
│                    │                                            │
│         ┌──────────┴───────────┐                               │
│         ▼                      ▼                                │
│  ┌─────────────┐      ┌─────────────────┐                     │
│  │  Outputs    │      │  VE Operations  │                     │
│  │  - Deltas   │      │  - Apply/Rollback│                    │
│  │  - Spark    │      │  - SHA-256 verify│                    │
│  │  - Manifest │      │  - Metadata gen  │                    │
│  └─────────────┘      └─────────────────┘                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow Sequence

**Standard Workflow:**
1. **Data Acquisition** → WinPEP CSV log or JetDrive live capture
2. **Analysis** → Core engine bins AFR by RPM/kPa grid (11×9 = 99 cells)
3. **Correction** → Calculate VE factors from AFR error with adaptive smoothing
4. **Clamping** → Enforce safety limits (default ±7%, max ±15%)
5. **Output** → Generate VE_Correction_Delta_DYNO.csv, diagnostics, spark suggestions
6. **Apply** → Multiply base VE tables with corrections (hash-verified)
7. **Export** → PVV XML for Power Vision or CSV for manual ECM flash
8. **Rollback** → Revert to base VE if needed (metadata-driven)

### 1.3 JetDrive Integration (KLHDV Protocol)

**Transport:** UDP multicast `224.0.2.10:22344`

**Frame Structure:** `[Key][Len][Host][Seq][Dest][Value...]`

**Key Messages:**
- `0x01` ChannelInfo: Provider name (50B UTF-8) + N channel blocks (34B: chanId u16, vendor byte, channelName 30B, unit byte)
- `0x02` ChannelValues: Repeated 10-byte samples (chanId u16, ts_ms u32, float32 value)
- `0x04/0x05` Ping/Pong: Heartbeat mechanism
- `0x06` RequestChannelInfo: Discovery broadcast to ALL_HOSTS

**Components:**
- `api/services/jetdrive_client.py`: Multicast join, ChannelInfo parsing, ChannelValues subscription
- `synthetic/winpep8_cli.py`: Provider discovery, run collection, CSV synthesis

**Constraints:**
- Tuning math and clamping rules remain unchanged
- Behavior is deterministic for given input stream
- Restreaming onto JetDrive is experimental/guarded

---

## 2. Non-Negotiable Invariants

### 2.1 Math-Critical Asset Protection

**Files Under Strict Control:**
- `ai_tuner_toolkit_dyno_v1_2.py` - Core engine, AFR analysis, smoothing orchestration
- `ve_operations.py` - Apply/rollback with SHA-256 verification
- `io_contracts.py` - Path traversal protection, file hashing, boundary enforcement
- `experiments/protos/k*.py` - Experimental kernels (K1 gradient-limit, K2 coverage-adaptive, K3 bilateral)

**Change Requirements:**
- Maintainer approval mandatory
- Design document with validation plan
- Before/after output comparisons
- Full regression test evidence
- Extended review period (3-7 days minimum)

### 2.2 Safety Limits (Physical Engine Protection)

**VE Correction Clamping:**
- Default: ±7% (multipliers in [0.93, 1.07])
- Configurable range: ±1% to ±15%
- Enforced before VE table multiplication
- Rationale: Prevents excessive fueling that could damage engine

**Spark Timing Limits:**
- Typical range: -5° to +10° from baseline
- Output: Suggestions only, not auto-applied
- Requires experienced tuner verification

**Coverage Thresholds:**
- Low coverage warning: < 10 hits per bin
- No correction applied: 0 hits per bin
- High confidence: ≥ 50 hits per bin

### 2.3 Data Format Invariants

**VE Tables (`*.csv`):**
- Format: First column `RPM`, subsequent columns numeric kPa values
- Precision: 4 decimals enforced by VEApply
- Bin alignment: RPM/kPa grids must match exactly (no implicit reindexing)

**Factor Tables (`VE_Correction_Delta_*.csv`):**
- Format: Percentage values (`+/-XX.XXXX`)
- Grid dimensions must match base VE tables exactly
- Clamping applied before VE multiplication

**Manifest (`manifest.json`):**
- Required fields: `status.code`, `stats.rows_read` (≥1000), `stats.bins_total` (>0), `timing.start/end`
- Optional fields: `apply.allowed`, `outputs[]` array
- Schema: `dynoai.manifest@1`

### 2.4 Test Invariants (Semantics Locked)

**Test Harnesses (Cannot Modify Semantics):**
- `selftest.py` - CLI smoke test, manifest generation, VE delta output
- `selftest_runner.py` - Legacy smoke test (alternative harness)
- `acceptance_test.py` - VE operations validation and scenarios

**Note:** Documentation references experimental kernel harnesses (`tests/kernels/test_k1.py`, `test_k2.py`, etc.) as planned infrastructure. These are not yet implemented. Current experimental kernel validation uses `tests/test_fingerprint.py` and the `experiments/` framework.

**Execution Order:**
1. Selftests (smoke tests: selftest.py, selftest_runner.py)
2. Acceptance tests (VE operations: acceptance_test.py)
3. Unit tests (PyTest: tests/test_*.py)
4. Integration tests (PyTest: tests/test_autotune_workflow.py, tests/test_jetdrive_*.py)
5. API tests (PyTest: tests/api/test_*.py)

**Pass Criteria:** All tests must pass before merge. No exceptions.

---

## 3. Formal Contracts and IO Rules

### 3.1 Path Safety Contract (`io_contracts.py`)

**Function:** `safe_path(path: str, allow_parent_dir: bool = False) -> Path`

**Guarantees:**
- Resolves symlinks and relative components (e.g., `..`)
- Validates path is within project root (unless `allow_parent_dir=True`)
- Raises `ValueError` for traversal attempts outside allowed directory
- Prevents directory traversal attacks

**Enforcement:**
- All file operations must use `safe_path()` validation
- Output directories constrained to repo root
- Exception: `--dry-run` mode allows temp directories for testing

### 3.2 Hash Verification Contract

**Function:** `file_sha256(path: str, bufsize: int = 65536) -> str`

**Guarantees:**
- Deterministic SHA-256 hash computation
- 64KB buffer size (optimal for most filesystems)
- Consistent across platforms (Windows/Linux/macOS)

**Usage:**
- VE table metadata stores `base_sha` and `factor_sha`
- Rollback blocked if current file hash ≠ metadata hash
- Prevents rollback of tampered files

### 3.3 Manifest Contract

**Schema ID:** `dynoai.manifest@1`

**Required Fields:**
```json
{
  "status": {
    "code": "success",  // Must be "success" for completed runs
    "message": "string"
  },
  "stats": {
    "rows_read": 1234,  // Must be ≥ 1000
    "bins_total": 99,   // Must be > 0
    "bins_covered": 85
  },
  "timing": {
    "start": "2025-11-20T10:30:00.123Z",
    "end": "2025-11-20T10:30:15.456Z"
  }
}
```

**Optional Fields:**
- `apply.allowed`: Present when VE apply executed
- `outputs[]`: Array of generated files with paths and hashes
- `kernel.fingerprint`: Experimental kernel metadata

**Atomic Write:** Uses `write_json_atomic()` with temp file + rename

### 3.4 CSV Schema Contract

**Function:** `csv_schema_check(path: str) -> Dict[str, Any]`

**Required Columns:** `rpm`, `map_kpa`, `torque`

**Returns:**
```python
{
  "path": str,
  "size_bytes": int,
  "sha256": str,
  "dialect": {"sep": ",", "encoding": "utf-8", "newline": "auto"},
  "required_columns_present": bool,
  "missing_columns": list
}
```

**Validation:**
- File existence checked before processing
- Rejects malformed CSV with clear error messages
- Verifies minimum required columns

### 3.5 VE Apply Contract

**Class:** `VEApply`

**Signature:** `apply(base_ve_path, factor_path, output_path, max_adjust_pct=7.0, dry_run=False)`

**Preconditions:**
- Base VE table exists and is valid CSV
- Factor table exists and matches base dimensions exactly
- `max_adjust_pct` in range [1.0, 15.0]
- Output path is safe (within repo root)

**Postconditions:**
- Output VE table has 4-decimal precision
- Clamping enforced: factors in [1-max_adjust_pct/100, 1+max_adjust_pct/100]
- Metadata file generated: `{output_path}_meta.json` with `base_sha`, `factor_sha`, `applied_at_utc`, `max_adjust_pct`
- Dry-run mode: No files written, validation only

**Invariants:**
- Grid dimensions preserved (RPM bins and kPa columns unchanged)
- Bin alignment validated (no implicit reindexing)
- SHA-256 hashes computed for audit trail

### 3.6 VE Rollback Contract

**Class:** `VERollback`

**Signature:** `rollback(current_ve_path, metadata_path, output_path)`

**Preconditions:**
- Metadata file exists and is valid JSON
- Current VE table exists
- Metadata contains `base_sha`, `factor_sha`, `max_adjust_pct`
- Factor table available at original path

**Postconditions:**
- Output table matches original base table exactly
- SHA-256 hash of output matches `base_sha` from metadata
- Rollback blocked if hashes don't match (prevents tampering)

**Guarantees:**
- Exact reversal of VE apply operation
- No data loss or precision errors
- Audit trail maintained in metadata

---

## 4. Test Locks and Reproducibility Status

### 4.1 Test Coverage Summary

**Total Test Files:** 29 (including conftest.py files)

**Test Categories:**
- API Tests: 11 files (health, security, authentication, rate limiting, endpoints)
- Core Logic Tests: 10 files (bin alignment, delta floor, fingerprint, runner paths, file handling)
- Integration Tests: 6 files (JetDrive, autotune workflow, decel management, cylinder balancing, livelink)
- Agent Tests: 1 file (orchestrator, make_patch)
- Configuration: 2 conftest.py files (test setup and fixtures)

### 4.2 Test Execution Matrix

| Test Suite | Files | Purpose | Pass Criteria |
|------------|-------|---------|---------------|
| Selftests | `selftest.py`, `selftest_runner.py` | Smoke test, CLI runs, manifest generated | Files execute successfully |
| Acceptance | `acceptance_test.py` | VE operations validation | Validation tests pass |
| Unit Tests | `tests/test_*.py` | Bin alignment, delta flooring, fingerprints, path validation | All passing |
| Integration Tests | `tests/test_autotune*.py`, `tests/test_jetdrive*.py`, etc. | End-to-end workflows | All passing |
| API Tests | `tests/api/test_*.py` | REST endpoints, middleware, security | All passing |

**Note:** Documentation references kernel harness tests (`tests/kernels/test_k*.py`) that are planned but not yet implemented. Current kernel validation is handled through `tests/test_fingerprint.py` and experimental framework tests.

### 4.3 Reproducibility Guarantees

**Deterministic Outputs (Given Same Inputs):**
- AFR binning: Deterministic grid assignment (RPM/kPa tolerance: ±50 RPM, ±5 kPa)
- VE correction calculation: Floating-point deterministic (platform-independent)
- Kernel smoothing: Deterministic for baseline, K1, K2, K3 kernels
- Hash computation: SHA-256 deterministic across platforms

**Non-Deterministic Elements:**
- Run IDs: Generated with UTC timestamp + random 6-char suffix
- Manifest timestamps: Recorded at runtime (`utc_now_iso()`)
- JetDrive sample timestamps: Real-time multicast packet arrival

**Reproducibility Enforcement:**
- Kernel fingerprints logged: `module=<name>`, `function=<name>`, `params=<dict>`
- Metadata stores: Input hashes, CLI flags, kernel parameters
- `--dry-run` mode: Validation without side effects

### 4.4 Regression Test Evidence

**Required Before Merge:**
- All selftests pass (selftest.py, selftest_runner.py)
- Acceptance tests pass (acceptance_test.py for VE operations)
- All PyTest suites pass (unit + integration + API tests)
- No new linter errors introduced

**Automated Enforcement:**
- Branch protection: PRs required, status checks mandatory
- CI workflows: Automated test execution on every push/PR
- CODEOWNERS: Math-critical files require maintainer approval

**Planned Infrastructure:**
- Experimental kernel harnesses (tests/kernels/test_k*.py) referenced in documentation but not yet implemented
- When implemented, will validate K1/K2/K3 kernel imports and execution

### 4.5 Known Test Limitations

**Areas Without Coverage:**
- Power Vision PVV XML parsing (legacy format variations)
- JetDrive multicast on networks without IGMP snooping support
- Windows-specific encoding edge cases (emoji in filenames)

**Acceptable Gaps:**
- External services (xAI API, Dynojet hardware) are mocked in tests
- Database migrations (Alembic) tested manually, not in CI

---

## 5. Claim-Safe Positioning Language

### 5.1 Supported Use Cases

**Claim:** DynoAI3 **is designed for** dyno tuning of Harley-Davidson motorcycles using WinPEP logs or JetDrive live data capture.

**Claim:** DynoAI3 **provides** VE correction analysis with configurable safety clamping (±7% default, ±15% maximum).

**Claim:** DynoAI3 **integrates with** Dynojet Power Vision and Power Core systems via PVV XML export and CSV import.

**Claim:** DynoAI3 **implements** hash-verified VE table apply/rollback operations for audit trails.

**Claim:** DynoAI3 **supports** experimental kernel frameworks (K1/K2/K3) for research without modifying core math.

### 5.2 Limitations and Disclaimers

**Disclaimer:** DynoAI3 **does not** auto-flash ECM calibrations. Corrections must be manually applied via external tools (TunerPro, Power Vision, etc.).

**Disclaimer:** DynoAI3 **assumes** accurate AFR sensor calibration. Sensor errors propagate to VE corrections.

**Disclaimer:** DynoAI3 **requires** experienced tuner oversight. Spark timing suggestions are advisory only.

**Disclaimer:** DynoAI3 **clamping limits** prevent excessive corrections but do not guarantee engine safety. Dyno testing and street validation are mandatory.

**Disclaimer:** JetDrive restreaming (publishing corrected values back to multicast) is **experimental** and not recommended for production use.

### 5.3 Safety Warnings

**⚠️ Critical:** Always backup base VE tables before applying corrections.

**⚠️ Critical:** Test on dyno before street use. Do not flash corrections without validation.

**⚠️ Critical:** Clamping limits are configurable but exceeding ±7% requires expert judgment.

**⚠️ Critical:** Hash verification prevents tampered rollbacks. Do not modify metadata files manually.

**⚠️ Critical:** Low coverage bins (< 10 hits) may produce unreliable corrections. Review diagnostics report.

### 5.4 Supported Platforms

**Operating Systems:**
- Windows 10/11 (primary development target)
- Linux (Ubuntu 20.04+, Debian 11+)
- macOS (Intel and Apple Silicon)

**Python Versions:**
- Python 3.10+ (required for type hints and match/case statements)

**Dependencies:**
- Core: Flask, pandas, numpy, scipy
- Optional: Node.js 18+ for frontend (React/TypeScript)

### 5.5 Interoperability Claims

**Claim:** DynoAI3 **reads** WinPEP CSV logs exported from Dynojet WinPEP software.

**Claim:** DynoAI3 **reads** Power Vision CSV logs with AFR columns (afr_meas_f/r, afr_cmd_f/r).

**Claim:** DynoAI3 **exports** PVV XML compatible with Power Vision Tune Manager.

**Claim:** DynoAI3 **captures** JetDrive KLHDV multicast packets (protocol mirrors JetDriveSharp reference implementation).

**Limitation:** DynoAI3 **does not** read proprietary binary formats (e.g., Dynojet .dyno files, TunerPro .xdf).

### 5.6 Performance Claims

**Claim:** DynoAI3 **processes** typical dyno logs (5,000-20,000 rows) in under 10 seconds on modern hardware.

**Claim:** DynoAI3 **supports** real-time JetDrive capture (50-100 samples/sec) with < 100ms latency.

**Claim:** DynoAI3 **generates** outputs atomically (manifest write uses temp file + rename for crash safety).

**Limitation:** DynoAI3 **does not** guarantee real-time performance on underpowered systems (< 2 CPU cores, < 4GB RAM).

---

## 6. API Surface and Contracts

### 6.1 Core API Endpoints

**Base URL:** `http://{HOST}:{PORT}/api` (default: `http://localhost:5000/api`)

| Endpoint | Method | Purpose | Contract |
|----------|--------|---------|----------|
| `/health` | GET | System health check | Returns `{"status": "healthy"}` on success |
| `/analyze` | POST | Upload CSV and run analysis | Accepts multipart/form-data with `csv` file |
| `/ve-data/<run_id>` | GET | Retrieve VE correction data | Returns JSON with delta grid |
| `/download/<run_id>/<filename>` | GET | Download output files | Streams CSV/JSON/TXT files |
| `/status/<run_id>` | GET | Get run status | Returns manifest and status metadata |
| `/runs` | GET | List all runs | Returns array of run metadata |
| `/diagnostics/<run_id>` | GET | Get diagnostics report | Returns diagnostics text |
| `/coverage/<run_id>` | GET | Get coverage maps | Returns coverage data |
| `/apply` | POST | Apply VE corrections | VE table apply operation |
| `/rollback` | POST | Rollback VE corrections | VE table rollback operation |

**JetDrive Endpoints** (prefix: `/api/jetdrive/`):

| Endpoint | Method | Purpose | Contract |
|----------|--------|---------|----------|
| `/status` | GET | Check JetDrive system status | Returns provider list and connection state |
| `/analyze` | POST | Run analysis on uploaded CSV | Accepts multipart/form-data with `csv` file |
| `/analyze-unified` | POST | Run unified workflow analysis | Unified analysis with autotune workflow |
| `/run/<run_id>` | GET | Get run details | Returns manifest + outputs metadata |
| `/run/<run_id>/pvv` | GET | Download PVV XML | Streams Power Vision XML export |
| `/run/<run_id>/report` | GET | Get run report | Returns comprehensive run report |
| `/upload` | POST | Upload dyno data | Upload and process CSV file |
| `/hardware/diagnostics` | GET | Run hardware diagnostics | Tests network and multicast |
| `/hardware/discover` | GET | Discover JetDrive providers | Scans network for providers |
| `/hardware/monitor/start` | POST | Start connection monitor | Begins continuous health checks |
| `/hardware/monitor/stop` | POST | Stop connection monitor | Stops health checks |
| `/hardware/monitor/status` | GET | Get monitor status | Returns monitor state |
| `/hardware/live/start` | POST | Start live data capture | Begins JetDrive capture |
| `/hardware/live/stop` | POST | Stop live data capture | Stops capture |
| `/hardware/live/data` | GET | Get live data stream | Returns captured samples |

### 6.2 Authentication and Rate Limiting

**Authentication:**
- Optional API key via `API_KEY` environment variable
- Header: `X-API-Key: <key>`
- Anonymous access allowed if `API_KEY` not set

**Rate Limiting:**
- Configurable via `RATE_LIMIT_ENABLED` environment variable
- Default: 100 requests/minute per IP
- Header: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

### 6.3 Error Handling Contract

**Standard Error Response:**
```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "request_id": "uuid-v4",
  "timestamp": "2025-11-20T10:30:00.123Z"
}
```

**HTTP Status Codes:**
- `200 OK`: Success
- `400 Bad Request`: Invalid input (missing columns, malformed CSV)
- `404 Not Found`: Run ID or file not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Uncaught exceptions (logged with stack trace)

---

## 7. Deployment and Configuration

### 7.1 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `JETDRIVE_MCAST_GROUP` | `224.0.2.10` | JetDrive multicast group |
| `JETDRIVE_PORT` | `22344` | JetDrive UDP port |
| `JETDRIVE_IFACE` | `0.0.0.0` | Network interface for multicast |
| `RATE_LIMIT_ENABLED` | `true` | Enable API rate limiting |
| `API_KEY` | (none) | Optional API authentication key |
| `XAI_API_KEY` | (none) | xAI Grok API key for chat proxy |

### 7.2 Recommended Deployment

**Local CLI (Primary Use Case):**
```bash
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv your_log.csv \
  --outdir ./outputs/run1 \
  --base_front tables/VE_Base_Front.csv \
  --base_rear tables/VE_Base_Rear.csv
```

**Web Application (Optional):**
```powershell
# Start backend (Terminal 1)
python -c "from api.app import app; app.run(host='127.0.0.1', port=5000)"

# Start frontend (Terminal 2)
cd frontend && npm run dev
```

**Docker (Future):**
- `Dockerfile` present in repo
- Not production-ready (no multi-stage build, no health checks)

---

## 8. Change Control and Governance

### 8.1 Allowed Modifications

**✅ Permitted:**
- Documentation updates (README, CHANGELOG, inline comments)
- Import path fixes after file reorganization
- Performance optimizations **if exact output preserved** (requires regression test proof)
- New API endpoints (following existing patterns)
- New test coverage (unit, integration, API)

**❌ Forbidden Without Approval:**
- Changes to math-critical files (ai_tuner_toolkit, ve_operations, io_contracts, kernels)
- Weakening test assertions to "make tests pass"
- Skipping safety tests (selftests, kernel harnesses, pytest)
- Committing secrets, API keys, or credentials
- Modifying tuning algorithms or clamping limits

### 8.2 Pre-Merge Checklist

- [ ] No math-critical files modified (or approved if modified)
- [ ] All safety tests pass (selftests + acceptance + kernels + pytest)
- [ ] Documentation updated to reflect changes
- [ ] `.gitignore` prevents artifacts from being committed
- [ ] No secrets or credentials in tracked files
- [ ] Import paths correct after any file moves
- [ ] Linter warnings addressed (or documented as acceptable)
- [ ] Maintainer review completed for core/experiments changes

### 8.3 Rollback Procedures

**Code Rollback:**
```bash
git revert <commit-hash>
git push origin main
```

**VE Table Rollback:**
```python
from pathlib import Path
from ve_operations import VERollback

VERollback().rollback(
    current_ve_path=Path("tables/VE_Front_Updated.csv"),
    metadata_path=Path("tables/VE_Front_Updated_meta.json"),
    output_path=Path("tables/VE_Front_Restored.csv")
)
```

**Requirements:**
- Metadata file must exist and be unmodified
- SHA-256 hashes must match
- Factor table must be available at original path

---

## 9. Audit Trail and Compliance

### 9.1 Traceability

**Run Provenance:**
- Every analysis generates unique run ID: `YYYY-MM-DDTHH-MM-SSZ-<6char>`
- Manifest stores: input CSV hash, CLI flags, kernel fingerprint, timing data
- Metadata files link: base VE hash, factor hash, apply timestamp

**Hash Chain:**
```
Input CSV (SHA-256)
    ↓
VE Correction Delta (SHA-256)
    ↓
Base VE Table (SHA-256) + Factor (SHA-256)
    ↓
Updated VE Table (SHA-256) ← Stored in metadata
    ↓
Rollback validates: Current file hash == Metadata hash
```

### 9.2 Security Audit Points

**Path Traversal Protection:**
- All file operations validated by `io_contracts.safe_path()`
- Rejects `..` in paths, validates within repo root
- Exception: `--dry-run` allows temp dirs for testing

**Hash Verification:**
- SHA-256 used for all file integrity checks
- Metadata stores hashes for audit trail
- Rollback blocked if hashes don't match

**Input Validation:**
- CSV schema checked before processing
- Bin alignment validated (no implicit reindexing)
- Idea-id validated against known kernels

### 9.3 Compliance Considerations

**Data Privacy:**
- No telemetry or analytics collection
- No network calls except optional xAI chat proxy
- All data processing is local

**Licensing:**
- MIT License (permissive open source)
- No proprietary dependencies

**Safety:**
- Clamping limits documented and enforced
- Rollback mechanism for error recovery
- Clear warnings in documentation

---

## 10. Appendix: Key File Locations

### 10.1 Core Engine
- `ai_tuner_toolkit_dyno_v1_2.py` - Main CLI engine
- `ve_operations.py` - VE table apply/rollback
- `io_contracts.py` - Path safety and file hashing

### 10.2 API Components
- `api/app.py` - Flask application entry point
- `api/routes/jetdrive.py` - JetDrive auto-tune endpoints
- `api/routes/powercore.py` - Power Core integration
- `api/services/autotune_workflow.py` - Unified analysis engine
- `api/services/jetdrive_client.py` - KLHDV protocol client

### 10.3 Experimental Kernels
- `experiments/protos/k1_gradient_limit_v1.py` - Gradient-limited smoothing
- `experiments/protos/k2_coverage_adaptive_v1.py` - Coverage-adaptive clamping
- `experiments/protos/k3_bilateral_v1.py` - Bilateral edge-preserving filter

### 10.4 Test Suites
- `selftest.py` - Smoke test harness (root directory)
- `selftest_runner.py` - Alternative smoke test harness (root directory)
- `acceptance_test.py` - VE operations acceptance (root directory)
- `tests/api/` - REST API endpoint tests
- `tests/test_*.py` - Unit and integration tests

**Note:** Experimental kernel harness tests referenced in documentation (`tests/kernels/`) are planned but not yet implemented.

### 10.5 Documentation
- `docs/DYNOAI_ARCHITECTURE_OVERVIEW.md` - System architecture
- `docs/DYNOAI_SAFETY_RULES.md` - Safety policies
- `README.md` - Quick start and overview

---

## Document Metadata

**Generated By:** System Synthesis Agent  
**Source Documents:**
- `docs/DYNOAI_ARCHITECTURE_OVERVIEW.md`
- `docs/DYNOAI_SAFETY_RULES.md`
- `io_contracts.py`
- `README.md`
- `.cursorrules.md`
- `tests/` directory structure

**Verification Status:**
- All documented invariants derived from existing codebase
- All test counts validated against actual test files
- All API endpoints cross-referenced with `api/routes/` modules
- All file locations verified in repository

**Update Policy:**
- Regenerate after major architecture changes
- Regenerate after test harness modifications
- Regenerate after safety policy updates
- Version increment on schema changes

**Schema Version:** `dynoai.system_snapshot@1`

---

**End of System Snapshot**
