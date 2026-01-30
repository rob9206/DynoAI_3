---
name: Phase 3 Apply Workflow
overview: Implement a complete VE correction apply workflow with dual-cylinder support, confidence-based clamping, preview/confirm UI, and Power Vision export - incorporating all documented tuning methods.
todos:
  - id: p3-ve-apply-utils
    content: Create veApply.ts with confidence-based clamping and apply calculation logic
    status: pending
  - id: p3-preview-panel
    content: Create ApplyPreviewPanel.tsx with before/after comparison and warnings
    status: completed
  - id: p3-confidence-indicator
    content: Create ConfidenceIndicator.tsx component for per-cell badges
    status: pending
  - id: p3-session-service
    content: Create tuningSession.ts for localStorage session management
    status: completed
  - id: p3-absolute-export
    content: Extend veExport.ts to export absolute VE values (not just deltas)
    status: completed
  - id: p3-integrate-page
    content: Integrate apply workflow into JetDriveAutoTunePage
    status: completed
isProject: false
---

# Phase 3: VE Correction Apply Workflow (v3)

## Overview

Build a complete workflow to apply live VE corrections to base VE tables, with:

- Zone-aware confidence thresholds (cruise vs WOT vs edge)
- Tighter clamps for low-confidence data (inch toward correct)
- Skip cells with insufficient samples (<3 hits)
- Dual raw/applied tracking for diagnostics
- Cylinder balance checking on raw corrections
- Cell-weighted zone coverage metrics
- Configurable VE bounds per tune type
- **Per-cylinder hitCounts** for accurate confidence per cylinder

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUTS                                         │
├─────────────────┬─────────────────┬─────────────────┬──────────────────────┤
│ Live Corrections│ Base VE Tables  │ Hit Counts      │ RPM/MAP Axes         │
│ Front + Rear    │ from PVV Import │ Front + Rear    │ for Zone Detection   │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬───────────┘
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VALIDATION LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ • Shape mismatch check (all 6 grids must match)                             │
│ • Missing base VE check                                                     │
│ • Invalid base VE check (≤0, NaN, Inf)                                      │
│ • Partial cylinder check (active cells only, ≥3 hits)                       │
│ • Extreme correction block (>±25% raw, cells with ≥3 hits only)            │
└────────┬────────────────────────────────────────────────────────────────────┘
         │ PASS
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CALCULATION LAYER                                    │
├─────────────────┬─────────────────┬─────────────────┬──────────────────────┤
│ Zone Classifier │ Confidence Calc │ Balance Check   │ Coverage Calc        │
│ RPM+MAP → Zone  │ Hits → Clamp    │ Front vs Rear   │ Cell-Weighted        │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬───────────┘
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          APPLY CORE                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ Per-cell: sanitize → zone → clamp → multiply → bound → result               │
│ • Skip cells with <3 hits (newVE = baseVE, wasSkipped = true)              │
│ • Track both rawDeltaPct and appliedDeltaPct                                │
│ • Apply VE bounds (configurable per tune type)                              │
└────────┬────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           UI LAYER                                          │
├─────────────────┬─────────────────┬─────────────────┬──────────────────────┤
│ ApplyPreview    │ ConfidenceBadge │ Warnings Panel  │ Export Modal         │
│ Before/After    │ H/M/L/— badges  │ Block + Warn    │ PVV/CSV/JSON         │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬───────────┘
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            OUTPUTS                                          │
├─────────────────┬─────────────────┬─────────────────┬──────────────────────┤
│ Updated PVV     │ Rollback Meta   │ Session State   │ Diagnostic Report    │
│ Absolute VE     │ SHA-256 Hashes  │ localStorage    │ Raw vs Applied       │
└─────────────────┴─────────────────┴─────────────────┴──────────────────────┘
```

---

## File Structure

```
frontend/src/
├── types/
│   └── veApplyTypes.ts           # All interfaces and types
├── utils/
│   └── veApply/
│       ├── index.ts              # Public exports
│       ├── zoneClassification.ts # Zone detection and configs
│       ├── confidenceCalculator.ts
│       ├── veApplyValidation.ts  # Block conditions, sanitization
│       ├── cylinderBalance.ts    # Balance checking
│       ├── coverageCalculator.ts # Zone-weighted coverage
│       ├── veBounds.ts           # VE floor/ceiling per tune type
│       └── veApplyCore.ts        # Main apply logic
├── components/jetdrive/
│   ├── ApplyPreviewPanel.tsx
│   ├── ConfidenceBadge.tsx
│   └── ApplyWarningsPanel.tsx
└── services/
    └── tuningSession.ts          # localStorage management
```

---

## Key Design Decisions

### 1. Inverted Clamping (Safety-First)

**Low confidence = TIGHT clamp** - "inch toward correct"


| Confidence | Clamp Limit | Rationale                                  |
| ---------- | ----------- | ------------------------------------------ |
| High       | ±7%         | Data is trustworthy, allow larger changes  |
| Medium     | ±5%         | Some uncertainty, moderate changes         |
| Low        | ±3%         | Uncertain data, small conservative changes |
| Skip       | —           | <3 hits, preserve base VE entirely         |


### 2. Zone-Aware Hit Thresholds

Different zones have different achievable hit counts:


| Zone                      | High | Medium | Min | Weight |
| ------------------------- | ---- | ------ | --- | ------ |
| Cruise (31-69 kPa)        | 100  | 20     | 3   | 5      |
| Part-Throttle (70-94 kPa) | 80   | 15     | 3   | 4      |
| WOT (95+ kPa)             | 30   | 10     | 3   | 2      |
| Decel (≤30 kPa)           | 50   | 15     | 3   | 1      |
| Edge (<1200 or >5500 RPM) | 30   | 10     | 3   | 1      |


### 3. Per-Cylinder Hit Counts

Track `hitCounts: { front: number[][]; rear: number[][] }` separately because:

- Sensors may have different valid reading rates
- One cylinder may have sensor issues
- Balance checking needs per-cylinder confidence

### 4. Raw vs Applied Tracking

Every cell tracks both:

- `rawDeltaPct`: What the AFR data says needs to happen
- `appliedDeltaPct`: What we're actually changing (after clamping)

Balance warnings use **raw** values so clamping doesn't mask underlying issues.

### 5. VE Bounds Per Tune Type


| Preset    | Min | Max  | Mode      |
| --------- | --- | ---- | --------- |
| NA Harley | 15% | 115% | Enforce   |
| Stage 1   | 15% | 120% | Enforce   |
| Stage 2   | 15% | 125% | Enforce   |
| Boosted   | 10% | 200% | Warn only |
| Custom    | —   | —    | Warn only |


---

## Threshold Reference


| Check               | Threshold            | Applies To         | Action           |
| ------------------- | -------------------- | ------------------ | ---------------- |
| Extreme correction  | >±25% raw            | Cells with ≥3 hits | **Block**        |
| Missing base VE     | —                    | —                  | **Block**        |
| Empty grid          | 0 rows/cols          | Any grid           | **Block**        |
| Shape mismatch      | —                    | All 6 grids        | **Block**        |
| Partial cylinder    | —                    | Active cells only  | **Block**        |
| Invalid base VE     | ≤0, NaN, Inf         | Any base cell      | **Block**        |
| High correction     | >±10% raw            | Any cell           | **Warn**         |
| Systematic bias     | >±2% raw             | Weighted avg diff  | **Warn**         |
| Localized imbalance | >±5% raw             | Any cell diff      | **Warn**         |
| Low coverage        | <50% weighted        | Cell-weighted      | **Warn**         |
| Low cruise coverage | <60%                 | Cruise zone        | **Warn**         |
| VE floor            | <15% (configurable)  | Final VE           | Clamp/warn       |
| VE ceiling          | >115% (configurable) | Final VE           | Clamp/warn       |
| Zero hits           | 0                    | Any cell           | Force corr = 1.0 |
| Low hits            | <3                   | Any cell           | **Skip**         |


---

## UI Badge Reference


| Badge | Color  | Cruise/PT Hits | WOT/Decel/Edge Hits | Clamp |
| ----- | ------ | -------------- | ------------------- | ----- |
| **H** | Green  | ≥100 / ≥80     | ≥30 / ≥50 / ≥30     | ±7%   |
| **M** | Blue   | ≥20 / ≥15      | ≥10 / ≥15 / ≥10     | ±5%   |
| **L** | Yellow | ≥3             | ≥3                  | ±3%   |
| **—** | Gray   | <3             | <3                  | Skip  |


---

## Export Formats

### Power Vision PVV (Absolute VE)

```xml
<Item name="VE (MAP based/Front Cyl)" units="%">
  <Columns units="Kilopascals">30,40,50,60,70,80,90,100,105</Columns>
  <Rows units="RPMx1000">
    <Row label="1.5">
      <Cell value="85.2" />  <!-- Actual VE, not delta -->
      <Cell value="87.1" />
    </Row>
  </Rows>
</Item>
```

### CSV with Metadata

```csv
# DynoAI VE Export
# Session: abc123
# Timestamp: 2025-01-30T12:00:00Z
# Source: MY24_FXLRS_STAGE1.pvv
# Base Hash: sha256:a1b2c3...
# Applied Hash: sha256:d4e5f6...
# Bounds: na_harley (15-115%)
#
RPM,MAP,Front_Base,Front_Applied,Front_Delta%,Rear_Base,Rear_Applied,Rear_Delta%,FrontHits,RearHits,Confidence
1500,30,72.5,72.5,0.0,73.1,73.1,0.0,2,1,skip
1500,40,78.3,80.2,2.4,79.0,80.8,2.3,45,42,medium
```

### JSON Session Bundle

```json
{
  "sessionId": "abc123",
  "timestamp": "2025-01-30T12:00:00Z",
  "enginePreset": "stage_1",
  "veBoundsPreset": "na_harley",
  "sourceFile": "MY24_FXLRS_STAGE1.pvv",
  "rpmAxis": [1500, 2000, 2500],
  "mapAxis": [30, 40, 50],
  "baseVE": {
    "front": [[72.5, 78.3], [75.0, 80.1]],
    "rear": [[73.1, 79.0], [76.2, 81.3]]
  },
  "corrections": {
    "front": [[1.0, 1.024], [1.015, 1.032]],
    "rear": [[1.0, 1.023], [1.018, 1.029]]
  },
  "hitCounts": {
    "front": [[2, 45], [38, 92]],
    "rear": [[1, 42], [35, 88]]
  },
  "appliedVE": {
    "front": [[72.5, 80.2], [76.1, 82.7]],
    "rear": [[73.1, 80.8], [77.6convergence, 83.7]]
  },
  "hashes": {
    "base": "sha256:a1b2c3...",
    "applied": "sha256:d4e5f6..."
  }
}
```

---

## Testing Scenarios

1. **Happy path**: 100% coverage, all high confidence, no warnings
2. **Low coverage**: <50% weighted coverage, cruise zone warnings
3. **Extreme corrections**: >25% raw delta triggers block
4. **Partial cylinder**: Front data only triggers block
5. **Shape mismatch**: Mismatched grid dimensions trigger block
6. **Cylinder imbalance**: >2% systematic bias triggers warning
7. **Clamping behavior**: Verify low-confidence cells get ±3% clamp
8. **Skip behavior**: Verify <3 hit cells preserve baseVE
9. **VE bounds**: Verify floor/ceiling enforcement per preset
10. **Convergence messaging**: Verify "~N sessions" estimate accuracy
11. **Per-cylinder hitCounts**: Verify front/rear tracked independently

