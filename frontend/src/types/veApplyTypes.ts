/**
 * VE Apply Types - Phase 3 VE Correction Apply Workflow
 *
 * This module defines all TypeScript interfaces and types for the VE correction
 * apply workflow, including zones, confidence levels, safety thresholds, and results.
 */

// =============================================================================
// CORRECTION SEMANTICS
// =============================================================================

/**
 * Corrections are multiplicative factors where:
 * - 1.000 = no change needed
 * - 1.077 = cell needs +7.7% more fuel
 * - 0.923 = cell needs -7.7% less fuel
 *
 * Values are session-aggregated (not per-sample deltas).
 * A percent-delta representation (+7.7) is INVALID input.
 */
export type CorrectionMultiplier = number;

// =============================================================================
// ZONES
// =============================================================================

/**
 * Operating zones for the VE table, each with different hit thresholds.
 * - cruise:       31-69 kPa, 1200-5500 RPM (steady-state riding, ~70% of miles)
 * - partThrottle: 70-94 kPa, 1200-5500 RPM (roll-on acceleration)
 * - wot:          95+ kPa, 1200-5500 RPM (full power pulls)
 * - decel:        ≤30 kPa, 1200-5500 RPM (engine braking, fuel cut)
 * - edge:         <1200 or >5500 RPM, any MAP (idle, redline)
 */
export type CellZone = 'cruise' | 'partThrottle' | 'wot' | 'decel' | 'edge';

export interface ZoneConfig {
  highHits: number;
  mediumHits: number;
  minHits: number;
}

// =============================================================================
// CONFIDENCE
// =============================================================================

/**
 * Confidence levels determine clamp limits.
 * IMPORTANT: Lower confidence = TIGHTER clamp (inch toward correct).
 */
export type Confidence = 'high' | 'medium' | 'low' | 'skip';

export interface ClampResult {
  confidence: Confidence;
  limit: number | null; // null = skip
  zone: CellZone;
}

// =============================================================================
// SAFETY THRESHOLDS
// =============================================================================

export interface SafetyThresholds {
  // Pre-apply blocking (raw deltas)
  blockRawDeltaPct: number;

  // Warnings (user can proceed)
  warnRawDeltaPct: number;
  warnSystematicBiasPct: number;
  warnLocalizedImbalancePct: number;

  // Coverage
  minHitsForInclusion: number;
  warnCoveragePct: number;
}

// =============================================================================
// VE BOUNDS
// =============================================================================

export interface VEBoundsConfig {
  min: number;
  max: number;
  warnOnly: boolean; // If true, warn but don't clamp
}

export type VEBoundsPreset =
  | 'na_harley'
  | 'stage_1'
  | 'stage_2'
  | 'boosted'
  | 'custom';

export interface BoundsCheckResult {
  originalVE: number;
  boundedVE: number;
  wasBounded: boolean;
  boundType: 'none' | 'floor' | 'ceiling';
}

// =============================================================================
// BLOCK CONDITIONS
// =============================================================================

export type BlockReasonType =
  | 'extreme_correction'
  | 'missing_base'
  | 'shape_mismatch'
  | 'partial_cylinder'
  | 'invalid_base_ve'
  | 'empty_grid';

export interface BlockReason {
  type: BlockReasonType;
  message: string;
  cells?: Array<{ rpm: number; map: number; value: number }>;
}

// =============================================================================
// BALANCE CHECKING
// =============================================================================

export interface BalanceReport {
  // Raw balance (before clamping) - used for warnings
  rawSystematicBiasPct: number;
  rawMaxLocalizedDiffPct: number;
  rawWorstCell: { rpm: number; map: number; diffPct: number } | null;

  // Applied balance (after clamping) - what will be exported
  appliedSystematicBiasPct: number;
  appliedMaxLocalizedDiffPct: number;

  warnings: string[];
  includedCellCount: number;
}

// =============================================================================
// COVERAGE
// =============================================================================

export interface ZoneCoverageBreakdown {
  zone: CellZone;
  totalCells: number;
  sufficientCells: number;
  coveragePct: number;
  weight: number;
}

export interface CoverageReport {
  totalCells: number;
  activeCells: number; // ≥1 hit
  sufficientCells: number; // ≥minHits

  activeCoveragePct: number; // sufficientCells / activeCells
  totalCoveragePct: number; // sufficientCells / totalCells
  weightedCoveragePct: number; // Cell-weighted by zone importance

  zoneBreakdown: ZoneCoverageBreakdown[];
  warnings: string[];
}

// =============================================================================
// APPLY RESULT (PER-CELL)
// =============================================================================

export interface ApplyCellResult {
  // Input
  rpm: number;
  mapKpa: number;
  baseVE: number;
  rawCorrection: number;
  hitCount: number;

  // Confidence
  zone: CellZone;
  confidence: Confidence;
  clampLimit: number | null;

  // Deltas (always computed for diagnostics)
  rawDeltaPct: number;
  appliedDeltaPct: number;
  wasClamped: boolean;

  // Output (never null - skipped cells get baseVE)
  newVE: number;
  wasSkipped: boolean;
  wasBounded: boolean;
  boundType: 'none' | 'floor' | 'ceiling';

  // Convergence (rough linear estimate)
  remainingDeltaPct: number;
  sessionsToConvergeEstimate: number;
}

// =============================================================================
// FULL APPLY RESULT
// =============================================================================

export interface ApplyGridResult {
  front: ApplyCellResult[][];
  rear: ApplyCellResult[][];
}

export interface ApplyReport {
  // Results
  gridResults: ApplyGridResult;
  appliedVE: { front: number[][]; rear: number[][] };

  // Diagnostics
  balanceReport: BalanceReport;
  coverageReport: CoverageReport;

  // Safety
  blockReasons: BlockReason[];
  warnings: string[];

  // Summary stats
  totalCells: number;
  skippedCells: number;
  clampedCells: number;
  boundedCells: number;
}

// =============================================================================
// DUAL-CYLINDER DATA STRUCTURES
// =============================================================================

export interface DualCylinderGrid<T> {
  front: T[][];
  rear: T[][];
}

export type DualCylinderVE = DualCylinderGrid<number>;
export type DualCylinderHits = DualCylinderGrid<number>;
export type DualCylinderCorrections = DualCylinderGrid<number>;

// =============================================================================
// SESSION
// =============================================================================

export interface TuningSession {
  id: string;
  createdAt: string;
  lastModified: string;
  enginePreset: string;
  veBoundsPreset: VEBoundsPreset;
  sourceFile?: string;

  baseVE: DualCylinderVE;
  corrections: DualCylinderCorrections;
  hitCounts: DualCylinderHits;
  afrTargets: Record<number, number>;

  rpmAxis: number[];
  mapAxis: number[];

  status: 'collecting' | 'ready_to_apply' | 'applied';

  // Rollback support
  hashes?: {
    base: string;
    applied: string;
  };
}

// =============================================================================
// EXPORT DATA
// =============================================================================

export interface ApplyExportData {
  sessionId: string;
  timestamp: string;
  enginePreset: string;
  veBoundsPreset: VEBoundsPreset;
  sourceFile?: string;

  rpmAxis: number[];
  mapAxis: number[];

  baseVE: DualCylinderVE;
  corrections: DualCylinderCorrections;
  hitCounts: DualCylinderHits;
  appliedVE: DualCylinderVE;

  hashes?: {
    base: string;
    applied: string;
  };
}
