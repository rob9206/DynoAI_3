---
name: Seamless Auto-Tune Wizard
overview: Create a guided, wizard-style tuning workflow that automates the entire VE correction process with clear visual steps, smart prompts, and minimal operator intervention. Integrates Phase 3 safety/apply engine with unified zone classification, coverage metrics, and dual-delta tracking.
todos:
  - id: ve-safety-core
    content: "Implement veSafety.ts: SAFETY thresholds, correction sanitization, block-condition checks (hit-gated so stale zero-hit cells cannot block)"
    status: completed
  - id: ve-zone-classifier
    content: "Implement veZones.ts: getCellZone + zone configs; single source of truth for both coverage and apply logic"
    status: completed
  - id: ve-coverage-engine
    content: "Implement veCoverage.ts: zone-weighted coverage metrics + per-zone breakdown (weightedCoveragePct, activeCoveragePct, per-zone %)"
    status: completed
  - id: ve-balance-engine
    content: "Implement veBalance.ts: correction-based cylinder balance report (systematic + localized, hit-weighted, minHits inclusion)"
    status: completed
  - id: ve-apply-engine
    content: "Implement veApply.ts: per-cell apply returning (1) numeric applied VE table and (2) per-cell metadata (confidence, clampLimit, raw/applied deltas, skipped/clamped/bounded)"
    status: completed
  - id: export-absolute-ve
    content: Ensure exports output absolute VE values; skipped cells export as base unchanged (not null/undefined)
    status: completed
  - id: wizard-core
    content: Create TuningWizard.tsx orchestrator component with step state management
    status: completed
  - id: step-indicator
    content: Create WizardStepIndicator.tsx with animated progress bar and click-to-navigate
    status: completed
  - id: zone-coverage
    content: "Create ZoneCoverageCard.tsx: zone-weighted coverage (not just raw hits), per-zone breakdown, suggestions. Output: weightedCoveragePct, cruiseCoveragePct, partThrottleCoveragePct, wotCoveragePct, edgeCoveragePct, activeCoveragePct"
    status: completed
  - id: smart-prompts
    content: "Create SmartPromptBanner.tsx: uses veCoverage + veBalance + block/warn counts for contextual prompts"
    status: completed
  - id: session-summary
    content: "Extend SessionSummaryCard.tsx: include updated/skipped/clamped/bounded counts, balance stats, coverage stats"
    status: completed
  - id: wizard-hook
    content: Create useTuningWizard.ts hook for wizard state management with auto-advance logic
    status: completed
  - id: heatmap-diff
    content: "Enhance ApplyPreviewPanel: appliedDeltaPct heatmap, rawDeltaPct overlay/toggle, per-cell markers (skipped/clamped/bounded/confidence)"
    status: completed
  - id: block-warn-ui
    content: Add standardized warning/block cards (expandable) with counts and example cells using rpm/map values
    status: pending
  - id: integrate-wizard
    content: Integrate TuningWizard into JetDriveAutoTunePage as primary view
    status: completed
  - id: auto-advance
    content: "Step 2→3: weightedCoveragePct ≥ target AND totalHits ≥ minimum, OR user click. Step 4→5: disabled if any block reason exists"
    status: completed
  - id: voice-assistant
    content: "Re-enable useAIAssistant with new events: coverage milestones, balance warnings, apply blocks, step transitions"
    status: completed
  - id: big-button-ui
    content: "Implement hero action pattern: giant progress ring, BIG BUTTON primary action, minimal text"
    status: completed
  - id: progressive-disclosure
    content: Implement 4-layer progressive disclosure (Glance → Summary → Full → Debug) with expand/collapse
    status: pending
  - id: quick-actions
    content: Add floating quick-action buttons (WOT, CRUISE, COLD) with voice guidance and auto-dismiss
    status: completed
  - id: convergence-tracker
    content: "Implement background convergence tracking: session count, oscillating cells, estimated sessions remaining"
    status: pending
  - id: session-history
    content: Add session history panel with view/export/rollback for each session plus baseline export
    status: pending
  - id: pre-apply-validation
    content: "Add background pre-apply validation: PVV parse check, range check, large delta warnings"
    status: pending
isProject: false
---

# Seamless Auto-Tune Wizard + Phase 3 Safety/Apply Engine

## Policy Decisions (Canonical Rules)

These policies are non-negotiable and must be enforced throughout the implementation:

1. **Blocks/warnings computed on raw (unclamped) deltas** - Clamping is not allowed to hide upstream data failures. If raw delta is extreme, it's a block even if applied delta is clamped.
2. **Skipped cells = "no change"** - In the applied VE table, skipped cells retain their base VE value. "Skipped" is metadata, not null numeric entries. Exports must contain numbers everywhere.
3. **Block-condition scans are hit-gated** - Only cells with `hits >= minHitsForInclusion` (typically 3, or at least 1) are considered for block conditions. Stale zero-hit cells with leftover correction values cannot block apply.
4. **Single zone classifier** - The same `getCellZone()` function and zone configs are used by both coverage calculation and apply logic. No divergence allowed.
5. **Dual-delta model** - Every cell tracks both `rawDeltaPct` (diagnostic/outlier detection) and `appliedDeltaPct` (what actually changes after clamping/bounds). UI must surface both.

---

## Current State Analysis

The existing system has all the pieces but they're disconnected:

- **TuneImport** - Manual file selection
- **LiveVETable** - Manual data collection with no guidance
- **ApplyPreviewPanel** - Manual review, no dual-delta visibility
- **Export** - Manual download, multipliers not absolute VE
- **NextGen Analysis** - Separate workflow
- **AI Voice Assistant** - Disabled
- **Phase 3 veApply/** - Exists but not integrated with wizard

---

## Proposed Solution: Unified Tuning Wizard

### Visual Design: Step Progress Bar

```
[1. SETUP] → [2. COLLECT] → [3. ANALYZE] → [4. REVIEW] → [5. APPLY]
   ✓           ●              ○              ○              ○
```

A horizontal stepper component that:

- Shows current step with animation
- Displays step status (complete/active/pending)
- Auto-advances when conditions are met
- Allows manual navigation for experienced users

---

## Step-by-Step Flow

### Step 1: SETUP (Auto-completes in ~5 seconds)

**What happens:**

1. Auto-load `pvv_template.pvv` (already implemented)
2. Auto-start simulator OR prompt for dyno connection
3. Show tune summary card (VE grid size, AFR targets)

**UI Elements:**

- Large "Start Tuning Session" button (if not auto-started)
- Tune source indicator (PVV file or preset name)
- Grid dimensions badge (27x17)
- Status: "Ready to collect data"

**Auto-advance condition:** Tune loaded AND (simulator active OR dyno connected)

---

### Step 2: COLLECT (Main data collection phase)

**What happens:**

1. LiveVETable in prominent view
2. **Zone-weighted coverage** using same classifier as Phase 3 apply logic
3. Voice feedback for rich/lean events
4. Auto-pull suggestions based on coverage gaps

**UI Elements:**

- LiveVETable (full width)
- **ZoneCoverageCard** (canonical session readiness signal):
  - Weighted Coverage: **67%** (zone-importance weighted)
  - Active Coverage: **45%** (cells with ≥3 hits / total cells)
  - Total Hits: **1,247**
- Per-zone breakdown:
  - Cruise Zone: [████████░░] 82% (weight: 0.35)
  - Part-Throttle: [██████░░░░] 64% (weight: 0.25)
  - WOT Zone: [████░░░░░░] 42% (weight: 0.25)
  - Edge Zone: [██░░░░░░░░] 18% (weight: 0.15)
- "Suggested Next Pull" prompt based on lowest-coverage zone
- Estimated session quality grade (live updating)

**Smart Prompts (from veCoverage + veBalance):**

- "Cruise zone at 82%! Focus on WOT pulls to balance coverage."
- "Cylinder balance: Front +2.1% vs Rear - acceptable range."
- "Edge cells need attention - try a cold-start pull or low-MAP sweep."

**Auto-advance condition:**

- `weightedCoveragePct >= 60` AND `totalHits >= 500`, OR
- User clicks "Proceed to Analysis"

---

### Step 3: ANALYZE (10-15 seconds)

**What happens:**

1. Run NextGen analysis pipeline
2. Generate confidence scores
3. Build cause tree hypotheses
4. Calculate correction recommendations via veApply engine

**UI Elements:**

- Animated processing indicator
- Step-by-step progress:
  - ✓ Normalizing data...
  - ✓ Classifying zones...
  - ✓ Calculating corrections...
  - ● Checking safety thresholds...
  - ○ Building apply preview...
- Live status messages

**Auto-advance condition:** Analysis complete (no user action needed)

---

### Step 4: REVIEW (Enhanced ApplyPreviewPanel)

**What happens:**

1. Show **raw vs applied** dual-delta model
2. Display warnings and blocks from safety thresholds
3. Highlight cells by status: skipped, clamped, bounded
4. Show confidence breakdown by zone

**UI Elements (Enhanced ApplyPreviewPanel):**

- **Heatmap diff tabs:**
  - "Applied Delta" tab - what will actually change (appliedDeltaPct)
  - "Raw Delta" tab - diagnostic view for outlier detection (rawDeltaPct)
- **Per-cell markers overlay:**
  - Gray = Skipped (<3 hits)
  - Yellow border = Clamped (hit confidence limit)
  - Red border = Bounded (hit VE floor/ceiling)
  - Confidence badge on hover
- **Warning/Block cards (expandable):**
  - 🛑 BLOCKED: "Grid shape mismatch (27x17 vs 12x10)"
  - 🛑 BLOCKED: "3 cells have extreme correction (>20%): [3500 RPM, 85 kPa], ..."
  - ⚠️ WARNING: "12 cells clamped to ±5% - consider another session"
  - ⚠️ WARNING: "Cylinder imbalance: Front +3.2% vs Rear systematic"
- **Summary stats:**
  - Cells to update: 312
  - Cells skipped: 89 (insufficient hits)
  - Cells clamped: 24
  - Cells bounded: 3
- **Action buttons:**
  - "Accept Corrections" (green, disabled if any blocks)
  - "Collect More Data" (gray, returns to Step 2)

**Block conditions (from veSafety, hit-gated):**

- `shape_mismatch` - Base VE grid != correction grid
- `missing_base_ve` - No base VE loaded
- `invalid_base_ve` - Base contains non-positive values
- `extreme_correction` - Any cell with hits ≥ minHits has rawDelta > ±20%
- `partial_cylinder` - One cylinder has data, other doesn't

**Auto-advance condition:** User clicks "Accept Corrections" (disabled if blocks exist)

---

### Step 5: APPLY (Final export)

**What happens:**

1. Generate **fully numeric** applied VE table (skipped cells = baseVE unchanged)
2. Export **absolute VE values** (not multipliers)
3. Save session to history with full metadata
4. Offer download and "Start New Session"

**UI Elements:**

- Success animation
- Download cards for each format:
  - [📄 PVV] Power Vision Ready - Download
  - [📊 CSV] Spreadsheet Format - Download
  - [🔧 JSON] Technical Export - Download
- **Session summary (SessionSummaryCard):**
  - Total pulls: 5
  - Data points: 2,847
  - Duration: 18 minutes
  - **Cell breakdown:**
    - Updated: 312 / 459 (68%)
    - Skipped: 89 (insufficient data)
    - Clamped: 24 (hit confidence limits)
    - Bounded: 3 (hit VE floor/ceiling)
  - **Coverage achieved:**
    - Weighted: 72%
    - Cruise: 91% | Part-Throttle: 78% | WOT: 64% | Edge: 32%
  - **Balance:**
    - Front/Rear systematic: +1.2% (good)
    - Worst cell delta: 4.8% at [4000 RPM, 75 kPa]
- "Start New Session" button
- "View Session History" link

---

## New Core Modules (Phase 3 Engine)

### A) Safety/Apply Engine (Pure Utilities)

These modules are the single source of truth for all calculations:

#### `frontend/src/utils/veSafety.ts`

```typescript
// SAFETY thresholds (configurable)
export const SAFETY = {
  extremeCorrectionThreshold: 0.20,  // 20% raw delta = block
  minHitsForInclusion: 3,            // cells with < 3 hits are skipped
  maxClampPct: { low: 0.03, medium: 0.05, high: 0.07 },
  veFloor: 15,                       // absolute VE minimum
  veCeiling: 115,                    // absolute VE maximum
};

// Block condition checks (hit-gated)
export function checkBlockConditions(
  baseVE: number[][],
  corrections: DualCylinderCorrections,
  hitCounts: DualCylinderHits,
  rpmBins: number[],
  mapBins: number[]
): BlockReason[];

// Correction sanitization
export function sanitizeCorrection(raw: number): number;
```

#### `frontend/src/utils/veZones.ts`

```typescript
// Zone classifier (single source of truth)
export type CellZone = 'cruise' | 'partThrottle' | 'wot' | 'decel' | 'edge';

export const ZONE_CONFIGS: Record<CellZone, ZoneConfig> = {
  cruise:       { minHitsTarget: 10, weight: 0.35 },
  partThrottle: { minHitsTarget: 8,  weight: 0.25 },
  wot:          { minHitsTarget: 5,  weight: 0.25 },
  decel:        { minHitsTarget: 3,  weight: 0.10 },
  edge:         { minHitsTarget: 3,  weight: 0.05 },
};

export function getCellZone(rpmIdx: number, mapIdx: number, rpmBins: number[], mapBins: number[]): CellZone;
```

#### `frontend/src/utils/veCoverage.ts`

```typescript
export interface CoverageReport {
  weightedCoveragePct: number;      // zone-importance weighted
  activeCoveragePct: number;        // cells with >= minHits / total
  totalHits: number;
  perZone: Record<CellZone, { coveragePct: number; cellCount: number; hitCount: number }>;
  suggestions: string[];            // "Focus on WOT pulls"
}

export function calculateCoverage(
  hitCounts: DualCylinderHits,
  rpmBins: number[],
  mapBins: number[]
): CoverageReport;
```

#### `frontend/src/utils/veBalance.ts`

```typescript
export interface BalanceReport {
  systematicDeltaPct: number;       // hit-weighted mean(front - rear)
  worstCellDelta: { pct: number; rpmIdx: number; mapIdx: number };
  isBalanced: boolean;              // |systematic| < 3%
  warnings: string[];
}

export function calculateBalance(
  corrections: DualCylinderCorrections,
  hitCounts: DualCylinderHits,
  rpmBins: number[],
  mapBins: number[]
): BalanceReport;
```

#### `frontend/src/utils/veApply.ts`

```typescript
export interface CellApplyResult {
  rpmIdx: number;
  mapIdx: number;
  zone: CellZone;
  hits: number;
  baseVE: number;
  rawDeltaPct: number;              // before clamping
  appliedDeltaPct: number;          // after clamping + bounds
  appliedVE: number;                // final numeric value
  status: 'updated' | 'skipped' | 'clamped' | 'bounded';
  confidence: 'low' | 'medium' | 'high';
  clampLimit: number;
}

export interface ApplyResult {
  appliedVETable: number[][];       // fully numeric, no nulls
  cellResults: CellApplyResult[];   // per-cell metadata
  summary: {
    updated: number;
    skipped: number;
    clamped: number;
    bounded: number;
  };
  blocks: BlockReason[];
  warnings: string[];
}

export function calculateApply(
  baseVE: DualCylinderVE,
  corrections: DualCylinderCorrections,
  hitCounts: DualCylinderHits,
  rpmBins: number[],
  mapBins: number[],
  boundsPreset: VEBoundsPreset
): ApplyResult;
```

### B) UI Integration Points


| Component          | Consumes                                 | Renders                                                  |
| ------------------ | ---------------------------------------- | -------------------------------------------------------- |
| ZoneCoverageCard   | veCoverage                               | Per-zone progress bars, suggestions, auto-advance signal |
| SmartPromptBanner  | veCoverage + veBalance + blocks/warns    | Contextual prompts with action buttons                   |
| ApplyPreviewPanel  | veApply result                           | Heatmap diff, cell markers, warning/block cards          |
| SessionSummaryCard | veApply summary + veCoverage + veBalance | Final stats, cell breakdown, export links                |


---

## Files to Create/Modify

### New Files (Core Engine)

- `frontend/src/utils/veSafety.ts` - Safety thresholds and block checks
- `frontend/src/utils/veZones.ts` - Zone classifier (single source)
- `frontend/src/utils/veCoverage.ts` - Coverage calculation
- `frontend/src/utils/veBalance.ts` - Cylinder balance
- `frontend/src/utils/veApply.ts` - Main apply calculation

### New Files (Wizard UI)

- `frontend/src/components/jetdrive/TuningWizard.tsx` - Main orchestrator
- `frontend/src/components/jetdrive/WizardStepIndicator.tsx` - Step progress
- `frontend/src/components/jetdrive/ZoneCoverageCard.tsx` - Coverage display
- `frontend/src/components/jetdrive/SmartPromptBanner.tsx` - Guidance prompts
- `frontend/src/components/jetdrive/SessionSummaryCard.tsx` - Results display
- `frontend/src/hooks/useTuningWizard.ts` - Wizard state management

### Modify

- `frontend/src/pages/JetDriveAutoTunePage.tsx` - Integrate wizard as primary view
- `frontend/src/components/jetdrive/ApplyPreviewPanel.tsx` - Add dual-delta heatmap, cell markers
- `frontend/src/components/jetdrive/LiveVETable.tsx` - Integrate with veZones for zone display
- `frontend/src/hooks/useAIAssistant.ts` - Add wizard voice events
- `frontend/src/utils/veExport.ts` - Ensure absolute VE exports

### Delete/Consolidate

- `frontend/src/utils/veApply/` (existing folder) - Consolidate into single veApply.ts or keep as sub-modules but ensure single zone classifier

---

## Implementation Priority

1. **Phase A: Core Engine** - veSafety, veZones, veCoverage, veBalance, veApply (foundation for everything)
2. **Phase B: Wizard Shell** - TuningWizard, StepIndicator, useTuningWizard hook
3. **Phase C: Collection UI** - ZoneCoverageCard, SmartPromptBanner integration
4. **Phase D: Review UI** - Enhanced ApplyPreviewPanel with dual-delta heatmap
5. **Phase E: Apply/Export** - SessionSummaryCard, absolute VE exports
6. **Phase F: Voice & Polish** - Re-enable voice, auto-advance fine-tuning

---

## Voice Assistant Events (useAIAssistant)

### New Events

```typescript
// Coverage milestones
'coverage_50': "Halfway there! Coverage at 50%."
'coverage_75': "Looking good! 75% coverage."
'coverage_ready': "Coverage target reached. Ready for analysis!"

// Balance warnings
'balance_warning': "Heads up - cylinder imbalance detected. Check your sensors."

// Apply blocks
'apply_blocked': "Apply disabled - {N} cells have extreme corrections."
'apply_ready': "Corrections look solid. Ready to apply!"

// Step transitions
'step_collect': "Collecting data. Run some pulls!"
'step_analyze': "Analyzing your data..."
'step_review': "Review your corrections before applying."
'step_complete': "Done! Your VE table is ready to flash."
```

---

## Auto-Advance Logic

### Step 2 → Step 3 (Collect → Analyze)

```typescript
const canAdvanceToAnalyze = 
  (coverageReport.weightedCoveragePct >= 60 && coverageReport.totalHits >= 500) ||
  userClickedProceed;
```

### Step 4 → Step 5 (Review → Apply)

```typescript
const canAdvanceToApply = 
  applyResult.blocks.length === 0 && userClickedAccept;
```

If blocks exist, "Accept Corrections" button is disabled with tooltip showing block reasons.

---

## Dyno Operator UX Design

**Design Principles:**

- Big buttons, minimal text
- Details hidden until needed (progressive disclosure)
- One primary action visible at all times
- Voice announces what text would clutter

### Primary UI Pattern: Hero Action + Status Ring

```
┌─────────────────────────────────────────────┐
│                                             │
│        ┌───────────────────────┐            │
│        │                       │            │
│        │    ███ 67% ███        │  ← Status ring (coverage)
│        │                       │            │
│        │   ┌─────────────┐     │            │
│        │   │             │     │            │
│        │   │  RUN PULL   │     │  ← BIG BUTTON (primary action)
│        │   │             │     │            │
│        │   └─────────────┘     │            │
│        │                       │            │
│        └───────────────────────┘            │
│                                             │
│    [Details ▼]              [Skip →]        │  ← Secondary actions (small)
└─────────────────────────────────────────────┘
```

### Step-Specific Layouts

**Step 2 (COLLECT) - Primary View:**

- Giant circular progress ring showing `weightedCoveragePct`
- Center: Current RPM/MAP in large font
- Bottom: Single row of zone indicators (4 small colored dots)
- BIG BUTTON: "ANALYZE" (disabled until ready, pulses when ready)
- Expand arrow reveals: VE table, zone breakdown, suggestions

**Step 4 (REVIEW) - Primary View:**

- Giant checkmark (green) or X (red) based on blocks
- Center: "312 cells ready" or "BLOCKED: 3 issues"
- BIG BUTTON: "APPLY TO TUNE" (green) or "FIX ISSUES" (orange)
- Expand arrow reveals: Heatmap diff, warnings list, cell details

**Step 5 (APPLY) - Primary View:**

- Giant checkmark animation
- Center: "TUNE READY"
- BIG BUTTON: "DOWNLOAD PVV" (auto-downloads all formats in background)
- Small: "View Details" | "New Session"

### Progressive Disclosure Layers


| Layer           | What's Visible                          | How to Access                |
| --------------- | --------------------------------------- | ---------------------------- |
| **L0: Glance**  | Progress ring, status badge, BIG BUTTON | Always visible               |
| **L1: Summary** | Zone bars, cell counts, warnings count  | Tap "Details ▼"              |
| **L2: Full**    | VE table, heatmap, per-cell markers     | Tap zone bar or "Show Table" |
| **L3: Debug**   | Raw deltas, convergence data, logs      | Settings → Debug Mode        |


### Big Button States

```typescript
type ButtonState = 
  | { state: 'waiting'; label: 'Collecting...'; style: 'gray-pulse' }
  | { state: 'ready'; label: 'ANALYZE →'; style: 'green-glow' }
  | { state: 'blocked'; label: 'FIX ISSUES'; style: 'orange' }
  | { state: 'success'; label: 'DOWNLOAD'; style: 'green' };
```

### Voice Replaces Text

Instead of showing text warnings, voice announces them:

- ❌ Don't show: "Warning: 12 cells clamped to ±5%"
- ✅ Voice says: "Heads up - 12 cells hit the correction limit"
- ✅ UI shows: Orange dot on "Details" button

---

## Multi-Session Convergence (Background Tracking)

Tracked automatically in `localStorage`, surfaces only when relevant:

### Data Model

```typescript
interface ConvergenceTracker {
  sessionCount: number;
  cellHistory: Record<string, number[]>;  // key: "rpmIdx,mapIdx", value: last N corrections
  convergedCells: number;                 // stable across 2+ sessions
  oscillatingCells: number;               // flip-flopped direction
  estimatedSessionsRemaining: number;     // 0 = converged
}
```

### When It Surfaces

- **Session 1:** Hidden (no history yet)
- **Session 2+:** Small badge on step indicator: "Session 2/~3"
- **Convergence reached:** Voice: "Looking converged! This might be your last session."
- **Oscillation detected:** Voice: "Some cells are flip-flopping - check your AFR sensors"

### UI Integration

- Step indicator shows: `[1] → [2] → [●3] → [4] → [5]` with "Session 2/3" subtitle
- Expand reveals: "42 cells converged, 8 oscillating, 409 new"
- Never blocks workflow - purely informational

---

## Quick Actions (Floating Action Buttons)

During Step 2 (COLLECT), show floating quick-action buttons:

```
                    ┌─────────┐
                    │ WOT     │  ← Tap for WOT sweep guidance
                    └─────────┘
                    ┌─────────┐
                    │ CRUISE  │  ← Tap for cruise map guidance
                    └─────────┘
                    ┌─────────┐
                    │ COLD    │  ← Tap for cold-start guidance
                    └─────────┘
```

Each button:

- Shows suggested RPM/MAP range
- Voice announces: "For WOT coverage, run pulls from 3000 to redline"
- Highlights relevant cells on VE table (if expanded)
- Auto-dismisses after 5 seconds

---

## Session History & Rollback

### History Panel (accessible from main menu)

```
┌─────────────────────────────────────────────┐
│  Session History                    [×]     │
├─────────────────────────────────────────────┤
│  ┌─────────────────────────────────────┐    │
│  │ Today, 2:45 PM                      │    │
│  │ 312 cells • 72% coverage • Session 2│    │
│  │ [View] [Export] [Rollback ↩]        │    │
│  └─────────────────────────────────────┘    │
│  ┌─────────────────────────────────────┐    │
│  │ Today, 11:30 AM                     │    │
│  │ 287 cells • 58% coverage • Session 1│    │
│  │ [View] [Export] [Rollback ↩]        │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │ ⚠ BASELINE (original tune)         │    │
│  │ [Export Baseline PVV]               │  ← Emergency revert
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

### Rollback Flow

1. Tap "Rollback ↩" on any session
2. Confirm dialog: "Revert to Session 1 corrections?"
3. Generates PVV with that session's applied VE
4. Voice: "Rollback ready. Download will start."

---

## Pre-Apply Validation (Background)

Runs automatically before Step 5, surfaces only if issues:

```typescript
interface ValidationResult {
  pvvWillParse: boolean;
  allValuesInRange: boolean;
  noNullCells: boolean;
  largeDeltaCells: number;  // cells with >10% change
}
```

- **All pass:** Silent, proceed to Apply
- **Any fail:** Block with specific message
- **Large deltas:** Warning badge (doesn't block), voice: "3 cells have big changes - double-check before flashing"

---

## Updated Implementation Priority

1. **Phase A: Core Engine** - veSafety, veZones, veCoverage, veBalance, veApply
2. **Phase B: Big Button UI** - TuningWizard with hero action pattern, progress ring
3. **Phase C: Progressive Disclosure** - Expandable details, layer system
4. **Phase D: Voice Integration** - Replace text warnings with voice
5. **Phase E: Quick Actions** - Floating action buttons for coverage guidance
6. **Phase F: Convergence & History** - Background tracking, rollback support

