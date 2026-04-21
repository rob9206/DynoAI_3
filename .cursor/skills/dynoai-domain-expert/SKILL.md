---
name: dynoai-domain-expert
description: Provides domain knowledge for the DynoAI dyno-tuning platform including VE math, JetDrive hardware protocols, ECU calibration concepts, and architecture ownership. Use when editing any DynoAI source file, discussing tuning logic, or when the user mentions VE tables, AFR, JetDrive, ECU calibration, cylinder balance, or zone classification.
---

# DynoAI Domain Expert

## Architecture Overview

DynoAI is a monorepo for deterministic dyno tuning of Harley-Davidson motorcycles (V-twin engines). It consists of:

| Layer | Stack | Root |
|-------|-------|------|
| REST API | Flask 3.0, SQLAlchemy, Flasgger | `api/` |
| Frontend | React 19, TypeScript, Vite, Tailwind, Radix/shadcn | `frontend/` |
| Core Library | Python, NumPy, Pandas | `dynoai/` |
| Desktop GUI | PyQt6 | `gui/` |
| Scripts/CLI | Python, PowerShell, Batch | `scripts/` |

Version single source: `dynoai/version.py`

## Key File Ownership Map

| Responsibility | Owner Files |
|---|---|
| VE correction math | `dynoai/core/ve_math.py` |
| Auto-tune pipeline | `api/services/autotune_workflow.py` |
| VE apply workflow (frontend) | `frontend/src/utils/veApply/veApplyCore.ts` |
| Zone classification | `frontend/src/utils/veApply/zoneClassification.ts` |
| Cylinder balance | `frontend/src/utils/veApply/cylinderBalance.ts` |
| Confidence/clamp | `frontend/src/utils/veApply/confidenceCalculator.ts` |
| Coverage metrics | `frontend/src/utils/veApply/coverageCalculator.ts` |
| VE bounds enforcement | `frontend/src/utils/veApply/veBounds.ts` |
| Safety validation | `frontend/src/utils/veApply/veApplyValidation.ts` |
| Flask app + blueprint registration | `api/app.py` |
| Custom exceptions | `api/errors.py` |
| Centralized config | `api/config.py` |
| Calibration library ingestion/blending | `dynoai_v3/calibration_library.py`, `api/services/calibration_library_service.py`, `api/routes/calibration_library.py` |
| Auth (API key) | `api/auth.py` |
| Rate limiting | `api/rate_limit.py` |
| Shared TS types | `frontend/src/types/veApplyTypes.ts`, `frontend/src/lib/types.ts` |
| Axios client | `frontend/src/lib/api.ts` |
| Route definitions | `frontend/src/App.tsx` |

## Core Concepts

### VE (Volumetric Efficiency) Tables

A 2D grid indexed by RPM (rows) and MAP/kPa (columns). Each cell holds a VE percentage representing how much of the theoretical cylinder volume actually fills with air. The ECU uses VE to calculate fuel injection pulse width.

**Correction math (v2.0.0, default):**
```
VE_correction = AFR_measured / AFR_target
```
A correction of 1.077 means +7.7% more fuel needed. Legacy v1.0.0 used `1 + (AFR_error * 0.07)`.

**AFR targets vary by MAP:**
```
20-30 kPa: 14.7 (stoich)    70 kPa: 13.0
40 kPa: 14.5                80 kPa: 12.8
50 kPa: 14.0                90 kPa: 12.5
60 kPa: 13.5               100 kPa: 12.2
```

### Zones

Every VE cell belongs to a zone based on its RPM and MAP coordinates:

| Zone | MAP (kPa) | RPM | Weight | Typical riding |
|------|-----------|-----|--------|----------------|
| cruise | 31-69 | 1200-5500 | 5 | ~70% of miles |
| partThrottle | 70-94 | 1200-5500 | 4 | Roll-on accel |
| wot | 95+ | 1200-5500 | 2 | Full power pulls |
| decel | <=30 | 1200-5500 | 1 | Engine braking |
| edge | any | <1200 or >5500 | 1 | Idle/redline |

Zone determines confidence thresholds and coverage weighting.

### Confidence and Clamping

Hit count (number of data samples in a cell) determines confidence:

| Confidence | Clamp limit | Meaning |
|---|---|---|
| high | +/-7% | Trustworthy data |
| medium | +/-5% | Some uncertainty |
| low | +/-3% | Uncertain, conservative |
| skip | null | Below minHits, preserve base VE |

Each zone has its own `minHits`, `mediumHits`, `highHits` thresholds (e.g., cruise needs 100 hits for high confidence).

### Cylinder Balance (V-Twin Specific)

Front and rear cylinders are analyzed separately. Key metrics:
- **Systematic bias**: weighted average of `(rear/front - 1) * 100`. Positive = rear needs more fuel.
- **Localized imbalance**: max absolute difference across cells.
- Warnings at >2% systematic bias or >5% localized imbalance.
- Both cylinders must have >= 3 hits per cell for inclusion.

### VE Bounds Presets

| Preset | Range | Enforcement | Use case |
|---|---|---|---|
| na_harley | 15-115% | enforce | Stock/mild cams |
| stage_1 | 15-120% | enforce | Stage 1 cams |
| stage_2 | 15-125% | enforce | Stage 2+ cams |
| boosted | 10-200% | warn only | Turbo/supercharged |
| custom | 0-999% | warn only | No enforcement |

### Coverage

Zone-weighted metric: `sum(sufficientCells * weight) / sum(totalCells * weight)`. Grades: A (>=90%), B (>=75%), C (>=60%), D (>=40%), F (<40%). Warns if cruise zone < 60%.

### V3 Calibration Library

The v3 calibration library is a **reference tune corpus** (PVV-derived), separate from the template library:

- **Calibration library** (`data/calibration_library/`): imported real-world PVV calibrations used for blend seeding.
- **Template library** (`data/v3_templates/`): completed-session templates automatically saved by v3 finalize.

Storage pattern (calibration library):
- `index.json` with metadata, engine family, and relative file paths.
- Per-family directories (e.g., `tc_110/`) containing calibration JSON files.

Session seed priority for v3 initialization:
1. User PVV import (`initial_ve_table`)
2. Calibration library blend (top-N similarity matches)
3. Template library nearest match
4. Static/default surrogate prior

Similarity scoring for calibration matching reuses template-library hardware weights (`_compute_similarity`) and blends with squared weights (`similarity^2`) to emphasize closer matches.

## Safety Constraints (CRITICAL)

1. **Deterministic math only** -- no ML/AI in the VE correction path. Corrections use pure arithmetic.
2. **Bounded adjustments** -- default max correction +/-15% per session. Extreme corrections (>+/-25%) block the apply entirely.
3. **Dual-cylinder requirement** -- both front and rear data required; partial data blocks apply.
4. **VE bounds enforcement** -- physical limits prevent impossible VE values.
5. **Zero-hit cells untouched** -- cells with no data always get correction = 1.0 (no change).
6. **Convergence over perfection** -- large errors are corrected incrementally across multiple sessions rather than in one step.

## JetDrive Hardware Integration

JetDrive is Dynojet's real-time data acquisition hardware for dynos.

**Discovery protocol:**
- UDP multicast on port `22344`
- Primary group: `224.0.2.10`
- Alternatives: `239.255.60.60`, `224.0.0.1`, `239.192.0.1`
- Packets: up to 4096 bytes UDP datagrams

**Auto-tune pipeline:**
1. Import log (Power Vision CSV, JetDrive CSV, or DataFrame)
2. Filter signals (lowpass RC=500ms, outlier rejection at 2 sigma)
3. Bin data into RPM x MAP grid (11 RPM x 9 MAP = 99 cells)
4. Calculate AFR error per cell vs targets
5. Convert to VE corrections with clamping
6. Export: PVV XML, TuneLab script, CSV grids, manifest.json

## Error Handling Patterns

All Flask routes use `api/errors.py`:
- `@with_error_handling` decorator catches exceptions
- Custom classes: `ValidationError` (400), `NotFoundError` (404), `AnalysisError` (500), `JetDriveError` (502), etc.
- Standardized JSON responses with request ID tracking

## Additional Resources

For architecture details and file ownership, see [architecture-map.md](architecture-map.md).
