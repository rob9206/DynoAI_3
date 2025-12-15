# DynoAI3 Claims & Positioning Guardrails

**Purpose:** Define allowed vs. disallowed marketing/technical claims with precise language tied to evidence.

**Principle:** Every claim must be **defensible** with file/function references or test evidence.

---

## Claims Matrix: Allowed vs. Disallowed

### 1. Determinism

| ✅ **ALLOWED** | ❌ **DISALLOWED** | Precise Language | Evidence |
|---------------|------------------|------------------|----------|
| "Deterministic VE corrections for a given CSV and parameter set" | "Bit-for-bit identical VE corrections across all operating systems and Python versions" | "DynoAI3 produces **deterministic VE corrections** for a given CSV input and parameter set, using fixed AFR-to-VE formulas and clamping rules with no randomness in the core engine." | `ai_tuner_toolkit_dyno_v1_2.py` - no random() calls; `acceptance_test.py:352-379` - deterministic hashing |
| "Fixed random seeds for reproducible test data" | "Guarantees bit-identical results on Windows/Linux/macOS" | "Test data generation uses **fixed random seeds** (seed=42) to ensure reproducible synthetic datasets." | `dynoai/test_utils.py:39,63` - Random(42) |
| "Deterministic math within a platform" | "Cross-platform bit-identical output guaranteed" | "Math is deterministic within a platform; cross-platform equivalence is **expected** but not regression-tested." | No cross-platform test exists (GAP-6) |

**Rationale for Disallowances:**
- No automated test proves Windows/Linux/macOS produce bit-identical VE deltas (GAP-6)
- Floating-point arithmetic can vary across architectures (x86 vs ARM)
- Python version differences (3.10 vs 3.11) could affect rounding

**Allowed Context:**
- Single-platform reproducibility (Windows → Windows, same Python version)
- Same CSV + same args → same VE deltas on same machine

---

### 2. AI-Assisted

| ✅ **ALLOWED** | ❌ **DISALLOWED** | Precise Language | Evidence |
|---------------|------------------|------------------|----------|
| "AI-assisted calibration tool that automates AFR analysis and VE correction generation" | "Uses machine learning to optimize VE tables" | "DynoAI3 is an **AI-assisted** calibration tool that automates AFR analysis and VE correction generation. 'AI' refers to algorithmic intelligence and automation, not machine learning." | `ai_tuner_toolkit_dyno_v1_2.py` - automated workflow |
| "Intelligent data processing and adaptive kernels" | "Neural network-powered tuning" | "DynoAI3 uses **intelligent algorithms** including adaptive kernel smoothing (K2: coverage-adaptive) to process dyno data." | `experiments/protos/k2_coverage_adaptive_v1.py` |
| "Automated AFR binning and correction factor calculation" | "AI learns your engine's optimal tune" | "DynoAI3 **automates** AFR-to-VE correction generation using established tuning formulas; it does not use machine learning or learn from data." | Core engine is formula-based, not ML-based |

**Rationale for Disallowances:**
- No neural networks, decision trees, or ML models in codebase
- "AI" often implies machine learning in modern context; must clarify as algorithmic intelligence
- No training data, no model fitting, no gradient descent

**Allowed Context:**
- "AI" = Algorithmic Intelligence (automation, smart algorithms)
- Adaptive kernels adjust to data characteristics (coverage, gradients) but don't "learn"

---

### 3. Calibration Engine

| ✅ **ALLOWED** | ❌ **DISALLOWED** | Precise Language | Evidence |
|---------------|------------------|------------------|----------|
| "Calibration engine that generates VE corrections from dyno logs" | "Complete calibration suite for ECU programming" | "DynoAI3 is a **calibration engine** that generates VE correction factors and spark timing suggestions from dyno logs. It does not write calibrations to the ECU; users apply corrections via Power Vision." | `ai_tuner_toolkit_dyno_v1_2.py` - outputs VE deltas; no ECU flashing code |
| "Generates PVV XML export for Power Vision integration" | "Direct ECU flashing capability" | "DynoAI3 **exports corrections** in Power Vision PVV XML format; users load the PVV file into Power Vision software and flash the ECU via Power Vision's toolchain." | Output: PVV XML file, not ECU binary |
| "Single-pass correction generation" | "Fully automated closed-loop tuning" | "DynoAI3 provides **single-pass VE correction generation**; iterative tuning requires manual dyno re-runs and repeated analysis." | One CSV input → one set of corrections; no multi-iteration loop |

**Rationale for Disallowances:**
- Scope intentionally stops at correction generation (no dyno control, no ECU flashing)
- "Calibration suite" implies end-to-end workflow including ECU programming
- Closed-loop tuning requires dyno control integration (out of scope)

**Allowed Context:**
- DynoAI3 is ONE component in a tuning workflow (data analysis + correction generation)
- User workflow: Dyno run → DynoAI3 analysis → Power Vision flashing → re-test

---

### 4. World-Class Adjacent

| ✅ **ALLOWED** | ❌ **DISALLOWED** | Precise Language | Evidence |
|---------------|------------------|------------------|----------|
| "Industry-standard AFR-to-VE formulas" | "World-class accuracy comparable to Dynojet or HP Tuners" | "DynoAI3 applies **industry-standard AFR-to-VE formulas** used in professional tuning; accuracy depends on dyno data quality and user validation." | `ai_tuner_toolkit_dyno_v1_2.py` - standard formulas |
| "OEM-style data contracts and regression testing" | "OEM-certified calibration tool" | "DynoAI3 follows **OEM-style discipline** in data contracts, schema versioning, and regression testing; it is not certified for safety-critical use by any OEM or standards body." | `docs/DYNOAI_SAFETY_RULES.md`, 251 tests |
| "Production-grade test coverage (251 test functions)" | "Enterprise-grade software quality assurance" | "DynoAI3 has **production-grade test coverage** with 251 test functions validating math correctness, API security, and protocol compliance." | 34 test modules, 4,343 LOC |
| "Professional-quality VE corrections for review and validation" | "Guaranteed optimal tune" | "DynoAI3 generates **high-quality VE corrections** based on established tuning principles; users are responsible for validating corrections and dyno re-testing before street use." | Output is suggestion, not guarantee |

**Rationale for Disallowances:**
- No benchmarking data vs. commercial tools (Dynojet, HP Tuners, EFI Live)
- Not certified by ISO 26262, SAE, or any OEM safety standard
- "World-class" is aspirational, not proven with comparative data
- "Enterprise-grade" implies commercial support, SLA, multi-user features (not present)

**Allowed Context:**
- "Professional-quality" = high standards in code quality, testing, documentation
- "OEM-style discipline" = uses practices similar to OEM calibration workflows
- Accuracy depends on input data quality (garbage in, garbage out)

---

### 5. Safety & Clamping

| ✅ **ALLOWED** | ❌ **DISALLOWED** | Precise Language | Evidence |
|---------------|------------------|------------------|----------|
| "Safety-clamped VE corrections (default ±7%, configurable to ±15%)" | "Guarantees engine safety in all scenarios" | "VE corrections are **safety-clamped** to ±7% by default (configurable to ±15% max) to prevent excessive adjustments that could damage the engine. Users must validate corrections via dyno testing before street use." | `acceptance_test.py:28-69`, `ve_operations.py:22` - DEFAULT_MAX_ADJUST_PCT |
| "Enforces multiplier bounds [0.93, 1.07] at ±7% clamp" | "Eliminates all tuning risks" | "Clamping enforces **multiplier bounds [0.93, 1.07]** at the default ±7% limit; users can increase to ±15% for aggressive tuning (use with caution)." | `acceptance_test.py:251-288` - multiplier bounds test |
| "Rollback capability with hash verification" | "Infallible rollback even if metadata is corrupted" | "VE table modifications include **hash-verified rollback** using SHA-256; rollback fails gracefully if metadata or factor files are tampered with." | `acceptance_test.py:159-208` - hash verification test |

**Rationale for Disallowances:**
- Clamping reduces risk but doesn't eliminate all tuning hazards (user error, bad dyno data)
- "Guarantees safety" implies liability; DynoAI3 provides tools, not guarantees
- Rollback depends on intact metadata; if user deletes metadata, rollback is impossible

**Allowed Context:**
- Safety features are **mitigations**, not guarantees
- User responsibility: validate corrections, dyno re-test, monitor AFR during street testing

---

### 6. Testing & Quality

| ✅ **ALLOWED** | ❌ **DISALLOWED** | Precise Language | Evidence |
|---------------|------------------|------------------|----------|
| "Comprehensive regression test coverage (251 test functions)" | "100% code coverage" | "DynoAI3 has **comprehensive regression test coverage** with 251 test functions validating core math, API security, protocol compliance, and workflow integrity." | 34 test modules, 4,343 LOC |
| "Formalized acceptance criteria (8 requirements)" | "Fully validated and verified for production" | "VE apply/rollback system meets **8 formalized acceptance criteria** including clamping enforcement, hash verification, and roundtrip exactness." | `acceptance_test.py:382-428` - acceptance criteria |
| "Hash-verified VE table modifications (SHA-256)" | "Cryptographically secure tamper-proofing" | "VE table modifications use **SHA-256 hashing** to detect tampering; rollback is blocked if hash verification fails." | `acceptance_test.py:352-379`, `ve_operations.py:38-44` |
| "Versioned manifest schema (dynoai.manifest@1)" | "Guaranteed backward compatibility forever" | "Manifest outputs use **versioned schema** (dynoai.manifest@1) to track format changes; future versions would increment schema ID (e.g., @2)." | `io_contracts.py:27` - SCHEMA_ID |

**Rationale for Disallowances:**
- Code coverage is not measured/reported (no pytest-cov results)
- "Fully validated" implies exhaustive testing (impossible for complex software)
- SHA-256 is for integrity, not encryption (not "cryptographically secure" in crypto sense)
- Backward compatibility requires migration logic (not yet implemented)

**Allowed Context:**
- Test coverage is broad and comprehensive, not exhaustive
- Acceptance criteria are met per test evidence
- Hashing detects accidental/intentional tampering, not a security feature

---

### 7. Protocol Compliance

| ✅ **ALLOWED** | ❌ **DISALLOWED** | Precise Language | Evidence |
|---------------|------------------|------------------|----------|
| "Protocol-compliant KLHDV multicast integration (224.0.2.10:22344)" | "Full JetDrive feature parity" | "JetDrive integration is **protocol-compliant** with Dynojet KLHDV multicast specification; implements frame parsing for ChannelInfo, ChannelValues, Ping/Pong messages." | `test_jetdrive_client_protocol.py`, `api/services/jetdrive_client.py` |
| "Parses JetDrive multicast frames (Key-Len-Host-Seq-Dest-Value)" | "Supports all JetDrive hardware features" | "DynoAI3 **parses KLHDV frames** including ChannelInfo (0x01) and ChannelValues (0x02); does not implement advanced features like bi-directional streaming or dyno control." | Frame structure verified in tests |
| "Real-time data capture from JetDrive providers" | "Direct dyno control integration" | "DynoAI3 captures **real-time dyno data** via KLHDV multicast; it does not control dyno hardware (load cells, throttle actuators)." | Capture-only, no command/control |

**Rationale for Disallowances:**
- Implements core KLHDV protocol, not all JetDrive features (e.g., no re-streaming)
- "Feature parity" implies 1:1 with JetDrive SDK (not the case)
- Dyno control is intentionally out of scope (safety + complexity)

**Allowed Context:**
- KLHDV protocol compliance for data capture
- Subset of JetDrive features (capture, parse, convert to CSV)

---

### 8. Workflow & Automation

| ✅ **ALLOWED** | ❌ **DISALLOWED** | Precise Language | Evidence |
|---------------|------------------|------------------|----------|
| "Scriptable CLI for batch processing" | "Zero-configuration auto-tuning" | "DynoAI3 supports **fully scriptable batch processing** via command-line interface; users specify CSV input, output directory, and optional parameters (clamping, smoothing passes)." | `ai_tuner_toolkit_dyno_v1_2.py` - CLI args |
| "Minimal configuration required (CSV + output directory)" | "No learning curve; instant results" | "DynoAI3 requires **minimal configuration**: CSV input path and output directory are required; parameters have sensible defaults but may need tuning for specific engines." | Default clamp=7%, smooth_passes=2 |
| "Automated AFR analysis and VE correction pipeline" | "Real-time tuning" | "DynoAI3 automates **post-run analysis** of dyno logs; JetDrive capture is real-time, but analysis is batch processing after the run completes." | Workflow is post-run, not real-time streaming |

**Rationale for Disallowances:**
- Requires CSV input (not zero-configuration)
- Users must understand AFR targets, clamping limits, VE table structure (learning curve exists)
- Real-time tuning implies instant feedback during dyno run (not supported)

**Allowed Context:**
- Scriptable automation for batch workflows
- Post-run analysis (not live tuning during dyno run)

---

## Precise Language Templates

### Template 1: Feature Claim
**Pattern:** "DynoAI3 [ACTION] [FEATURE] using [METHOD]; [LIMITATION/CONTEXT]."

**Examples:**
- "DynoAI3 **generates VE corrections** using industry-standard AFR-to-VE formulas; accuracy depends on dyno data quality."
- "DynoAI3 **enforces safety clamping** at ±7% by default (configurable to ±15%); users must validate corrections via dyno re-testing."
- "DynoAI3 **exports PVV XML** for Power Vision integration; users load the file into Power Vision and flash the ECU via Power Vision's toolchain."

---

### Template 2: Capability Claim
**Pattern:** "DynoAI3 is capable of [CAPABILITY], but does not [OUT-OF-SCOPE]."

**Examples:**
- "DynoAI3 is capable of **parsing KLHDV multicast frames** from JetDrive, but does not control dyno hardware."
- "DynoAI3 is capable of **generating VE correction factors**, but does not write calibrations directly to the ECU."
- "DynoAI3 is capable of **automated batch processing**, but does not provide real-time tuning during dyno runs."

---

### Template 3: Quality/Discipline Claim
**Pattern:** "DynoAI3 follows [STANDARD/PRACTICE] with [EVIDENCE]; it is not [CERTIFICATION/GUARANTEE]."

**Examples:**
- "DynoAI3 follows **OEM-style discipline** in data contracts and regression testing; it is not certified for safety-critical use."
- "DynoAI3 has **comprehensive test coverage** (251 test functions); code coverage percentage is not measured."
- "DynoAI3 uses **SHA-256 hashing** for integrity verification; it is not a cryptographic security feature."

---

## Claims by Audience

### For Tuners (Technical Users)
**Allowed:**
- "Deterministic VE corrections using fixed AFR-to-VE formulas"
- "Safety-clamped to ±7% default, configurable to ±15%"
- "Hash-verified apply/rollback with exact restoration (≤0.0001 precision)"
- "Scriptable CLI for batch processing of dyno logs"
- "Protocol-compliant JetDrive KLHDV integration"

**Disallowed:**
- "Bit-for-bit identical across all platforms" → Use: "Deterministic within a platform"
- "Guarantees engine safety" → Use: "Provides safety mitigations via clamping"
- "Real-time tuning" → Use: "Post-run analysis of dyno logs"

---

### For Developers (Contributors/Maintainers)
**Allowed:**
- "Production-grade test coverage (251 test functions, 4,343 LOC)"
- "Formalized data contracts (io_contracts.py, manifest schema versioning)"
- "Math-critical files protected by CODEOWNERS and branch protection"
- "Reproducible kernel experiments with fingerprinting"

**Disallowed:**
- "100% code coverage" → Use: "Comprehensive test coverage"
- "Fully validated" → Use: "Meets formalized acceptance criteria"
- "Enterprise-grade" → Use: "Production-grade"

---

### For Business/Marketing
**Allowed:**
- "AI-assisted calibration tool (algorithmic intelligence, not ML)"
- "Industry-standard tuning formulas with OEM-style data discipline"
- "Professional-quality VE corrections for Harley-Davidson motorcycles"
- "Open-source with MIT license"

**Disallowed:**
- "World-class accuracy" → Use: "High-quality corrections based on established tuning principles"
- "OEM-certified" → Use: "OEM-style discipline in engineering practices"
- "Enterprise solution" → Use: "Professional-grade tool for individual tuners"

---

## Red Flags: Claims to Avoid Entirely

| ❌ **NEVER CLAIM** | Why It's Dangerous | Safe Alternative |
|-------------------|-------------------|------------------|
| "Guarantees engine safety" | Liability risk; implies warranty | "Provides safety mitigations via clamping; user validation required" |
| "Certified by [OEM/Standard]" | False certification claim | "Follows OEM-style discipline; not certified" |
| "Bit-for-bit reproducible everywhere" | Impossible across platforms/versions | "Deterministic math within a platform" |
| "100% accurate" | Impossible claim; depends on input data | "High-quality corrections based on established formulas" |
| "Zero risk of engine damage" | Legal liability | "Clamped corrections reduce risk; dyno re-testing required" |
| "Machine learning-powered" | No ML models in codebase | "AI-assisted (algorithmic intelligence)" |
| "Real-time tuning" | Not live; post-run analysis | "Post-run analysis with automated workflow" |
| "Direct ECU flashing" | Out of scope; legal/safety risk | "Exports PVV XML for Power Vision flashing" |

---

## Evidence Mapping: Claims → Source Files

| Claim | Evidence File/Function | Test Evidence |
|-------|------------------------|---------------|
| "Deterministic VE corrections" | `ai_tuner_toolkit_dyno_v1_2.py` - no random() calls | `acceptance_test.py:352-379` |
| "Safety clamping ±7%" | `ve_operations.py:22` - DEFAULT_MAX_ADJUST_PCT | `acceptance_test.py:28-69` |
| "Hash-verified rollback" | `ve_operations.py:38-44,276-281` - SHA-256 | `acceptance_test.py:159-208` |
| "251 test functions" | 34 test modules, grep -r "def test_" | 4,343 LOC in tests/ |
| "KLHDV protocol compliance" | `api/services/jetdrive_client.py` | `test_jetdrive_client_protocol.py` |
| "Formalized data contracts" | `io_contracts.py:27` - SCHEMA_ID | `test_preflight_csv.py` |
| "Scriptable CLI" | `ai_tuner_toolkit_dyno_v1_2.py` - argparse | Runs in batch scripts |
| "OEM-style discipline" | `docs/DYNOAI_SAFETY_RULES.md` | Branch protection, CODEOWNERS |

---

## Claim Checklist Before Release

**Before making ANY public claim, verify:**
- [ ] Is there a test that proves this claim? (Reference test file/function)
- [ ] Does the claim include appropriate limitations/context?
- [ ] Have we avoided red-flag words (guarantee, certified, 100%, zero-risk)?
- [ ] Is the claim defensible in a technical review or legal dispute?
- [ ] Does the claim match the intended audience (tuner/developer/business)?
- [ ] Have we used precise language from the templates above?

---

**Compiled By:** DynoAI3 Verification Agent  
**Purpose:** Prevent overreach in marketing/technical claims; maintain credibility  
**Review:** All claims tied to specific evidence (file/function references)
