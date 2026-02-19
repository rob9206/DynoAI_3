/**
 * VE Apply Module - Phase 3 VE Correction Apply Workflow
 *
 * This module provides the complete VE correction apply workflow with:
 * - Zone-aware confidence thresholds
 * - Tighter clamps for low-confidence data
 * - Skip cells with insufficient samples
 * - Dual raw/applied tracking for diagnostics
 * - Cylinder balance checking
 * - Cell-weighted zone coverage metrics
 * - Configurable VE bounds per tune type
 */

// Types
export type {
  CorrectionMultiplier,
  CellZone,
  ZoneConfig,
  Confidence,
  ClampResult,
  SafetyThresholds,
  VEBoundsConfig,
  VEBoundsPreset,
  BoundsCheckResult,
  BlockReasonType,
  BlockReason,
  BalanceReport,
  ZoneCoverageBreakdown,
  CoverageReport,
  ApplyCellResult,
  ApplyGridResult,
  ApplyReport,
  DualCylinderGrid,
  DualCylinderVE,
  DualCylinderHits,
  DualCylinderCorrections,
  TuningSession,
  ApplyExportData,
} from '../../types/veApplyTypes';

// Zone Classification
export {
  getCellZone,
  ZONE_CONFIGS,
  ZONE_WEIGHTS,
  getZoneDisplayInfo,
  classifyGrid,
} from './zoneClassification';

// Confidence Calculator
export {
  CLAMP_LIMITS,
  getClampResult,
  getConfidenceBadge,
  getConfidenceLevel,
  getConfidenceDistribution,
} from './confidenceCalculator';

// Validation
export {
  EPSILON,
  SAFETY,
  validateCorrection,
  sanitizeCorrection,
  hasActiveCorrection,
  checkBlockConditions,
  getBlockReasonDescription,
} from './veApplyValidation';

// Cylinder Balance
export {
  checkCylinderBalance,
  getBalanceSummary,
} from './cylinderBalance';

// Coverage Calculator
export {
  calculateCoverage,
  calculateDualCylinderCoverage,
  getCoverageGrade,
} from './coverageCalculator';

// VE Bounds
export {
  VE_BOUNDS_PRESETS,
  applyVEBounds,
  getBoundsPresetInfo,
  countBoundedCells,
} from './veBounds';

// Apply Core
export {
  calculateCellApply,
  calculateApply,
  getApplySummary,
} from './veApplyCore';
