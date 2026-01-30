/**
 * VE Apply Core - Main apply calculation logic
 *
 * This is the heart of the apply workflow. It:
 * 1. Validates all inputs
 * 2. Calculates per-cell results with zone-aware clamping
 * 3. Reports coverage and balance
 * 4. Returns a complete ApplyReport
 */

import {
  ApplyCellResult,
  ApplyReport,
  VEBoundsConfig,
  VEBoundsPreset,
  DualCylinderVE,
  DualCylinderCorrections,
  DualCylinderHits,
} from '../../types/veApplyTypes';
import { getCellZone } from './zoneClassification';
import { getClampResult } from './confidenceCalculator';
import {
  sanitizeCorrection,
  checkBlockConditions,
  EPSILON,
  SAFETY,
} from './veApplyValidation';
import { checkCylinderBalance } from './cylinderBalance';
import { calculateCoverage } from './coverageCalculator';
import { applyVEBounds, VE_BOUNDS_PRESETS } from './veBounds';

/**
 * Calculate apply result for a single cell.
 * Skipped cells return baseVE unchanged with wasSkipped=true.
 *
 * @param rpm - Cell RPM value
 * @param mapKpa - Cell MAP value in kPa
 * @param baseVE - Base VE value from imported tune
 * @param rawCorrection - Correction multiplier from live data
 * @param hitCount - Number of samples for this cell
 * @param boundsConfig - VE bounds configuration
 */
export function calculateCellApply(
  rpm: number,
  mapKpa: number,
  baseVE: number,
  rawCorrection: number,
  hitCount: number,
  boundsConfig: VEBoundsConfig
): ApplyCellResult {
  // Sanitize and force 1.0 for zero-hit cells
  const correction = hitCount === 0 ? 1.0 : sanitizeCorrection(rawCorrection);

  // Get confidence and clamp
  const clampResult = getClampResult(rpm, mapKpa, hitCount);
  const { confidence, limit: clampLimit, zone } = clampResult;

  // Always compute raw delta for diagnostics
  const rawDeltaPct = (correction - 1) * 100;

  // Skip case: insufficient hits
  if (clampLimit === null) {
    return {
      rpm,
      mapKpa,
      baseVE,
      rawCorrection: correction,
      hitCount,
      zone,
      confidence,
      clampLimit,
      rawDeltaPct,
      appliedDeltaPct: 0,
      wasClamped: false,
      newVE: baseVE, // Unchanged
      wasSkipped: true,
      wasBounded: false,
      boundType: 'none',
      remainingDeltaPct: rawDeltaPct,
      sessionsToConvergeEstimate: 0,
    };
  }

  // Apply clamp
  const clampedMultiplier = Math.max(
    1 - clampLimit,
    Math.min(1 + clampLimit, correction)
  );
  const appliedDeltaPct = (clampedMultiplier - 1) * 100;
  const wasClamped = Math.abs(clampedMultiplier - correction) > EPSILON;

  // Calculate new VE
  const rawNewVE = baseVE * clampedMultiplier;

  // Apply absolute bounds
  const boundsCheck = applyVEBounds(rawNewVE, boundsConfig);

  // Convergence estimate (rough, linear approximation)
  // If we applied 5% and need 15% total, we need ~2 more sessions
  const remainingDeltaPct = rawDeltaPct - appliedDeltaPct;
  const sessionsToConvergeEstimate = wasClamped
    ? Math.ceil(Math.abs(remainingDeltaPct) / (clampLimit * 100))
    : 0;

  return {
    rpm,
    mapKpa,
    baseVE,
    rawCorrection: correction,
    hitCount,
    zone,
    confidence,
    clampLimit,
    rawDeltaPct,
    appliedDeltaPct,
    wasClamped,
    newVE: boundsCheck.boundedVE,
    wasSkipped: false,
    wasBounded: boundsCheck.wasBounded,
    boundType: boundsCheck.boundType,
    remainingDeltaPct,
    sessionsToConvergeEstimate,
  };
}

/**
 * Main apply function. Validates inputs, calculates all cells, returns full report.
 *
 * @param baseVE - Base VE tables (front and rear) from imported tune
 * @param corrections - Correction multipliers from live data
 * @param hitCounts - Per-cylinder hit counts
 * @param rpmAxis - RPM axis values
 * @param mapAxis - MAP axis values
 * @param boundsPreset - VE bounds preset to use
 */
export function calculateApply(
  baseVE: DualCylinderVE | null,
  corrections: DualCylinderCorrections,
  hitCounts: DualCylinderHits,
  rpmAxis: number[],
  mapAxis: number[],
  boundsPreset: VEBoundsPreset = 'na_harley'
): ApplyReport {
  const boundsConfig = VE_BOUNDS_PRESETS[boundsPreset];

  // Check block conditions
  const blockReasons = checkBlockConditions(
    baseVE,
    corrections,
    hitCounts,
    rpmAxis,
    mapAxis
  );

  // If blocked, return early with empty results
  if (blockReasons.length > 0 || !baseVE) {
    return {
      gridResults: { front: [], rear: [] },
      appliedVE: { front: [], rear: [] },
      balanceReport: {
        rawSystematicBiasPct: 0,
        rawMaxLocalizedDiffPct: 0,
        rawWorstCell: null,
        appliedSystematicBiasPct: 0,
        appliedMaxLocalizedDiffPct: 0,
        warnings: [],
        includedCellCount: 0,
      },
      coverageReport: {
        totalCells: 0,
        activeCells: 0,
        sufficientCells: 0,
        activeCoveragePct: 0,
        totalCoveragePct: 0,
        weightedCoveragePct: 0,
        zoneBreakdown: [],
        warnings: [],
      },
      blockReasons,
      warnings: [],
      totalCells: 0,
      skippedCells: 0,
      clampedCells: 0,
      boundedCells: 0,
    };
  }

  // Calculate all cells
  const gridResults: {
    front: ApplyCellResult[][];
    rear: ApplyCellResult[][];
  } = { front: [], rear: [] };
  const appliedVE: DualCylinderVE = {
    front: [],
    rear: [],
  };

  let totalCells = 0;
  let skippedCells = 0;
  let clampedCells = 0;
  let boundedCells = 0;

  (['front', 'rear'] as const).forEach((cylinder) => {
    gridResults[cylinder] = baseVE[cylinder].map((row, rpmIdx) =>
      row.map((base, mapIdx) => {
        const result = calculateCellApply(
          rpmAxis[rpmIdx],
          mapAxis[mapIdx],
          base,
          corrections[cylinder][rpmIdx][mapIdx],
          hitCounts[cylinder][rpmIdx][mapIdx],
          boundsConfig
        );

        totalCells++;
        if (result.wasSkipped) skippedCells++;
        if (result.wasClamped) clampedCells++;
        if (result.wasBounded) boundedCells++;

        return result;
      })
    );

    appliedVE[cylinder] = gridResults[cylinder].map((row) =>
      row.map((cell) => cell.newVE)
    );
  });

  // Calculate balance (using applied multipliers for applied balance)
  const frontAppliedMultipliers = gridResults.front.map((row) =>
    row.map((cell) => (cell.wasSkipped ? 1.0 : 1 + cell.appliedDeltaPct / 100))
  );
  const rearAppliedMultipliers = gridResults.rear.map((row) =>
    row.map((cell) => (cell.wasSkipped ? 1.0 : 1 + cell.appliedDeltaPct / 100))
  );

  const balanceReport = checkCylinderBalance(
    corrections.front,
    corrections.rear,
    hitCounts,
    rpmAxis,
    mapAxis,
    frontAppliedMultipliers,
    rearAppliedMultipliers
  );

  // Calculate coverage (use front hitCounts as representative, or combine)
  const coverageReport = calculateCoverage(hitCounts.front, rpmAxis, mapAxis);

  // Collect all warnings
  const warnings: string[] = [
    ...balanceReport.warnings,
    ...coverageReport.warnings,
  ];

  // Add high-correction warnings (limited to avoid spam)
  let highCorrectionWarnings = 0;
  const maxHighCorrectionWarnings = 5;

  (['front', 'rear'] as const).forEach((cylinder) => {
    gridResults[cylinder].forEach((row) => {
      row.forEach((cell) => {
        if (
          Math.abs(cell.rawDeltaPct) > SAFETY.warnRawDeltaPct &&
          !cell.wasSkipped &&
          highCorrectionWarnings < maxHighCorrectionWarnings
        ) {
          warnings.push(
            `${cylinder.charAt(0).toUpperCase() + cylinder.slice(1)} [${cell.rpm} RPM, ${cell.mapKpa} kPa]: ` +
              `${cell.rawDeltaPct.toFixed(1)}% correction (clamped to ${cell.appliedDeltaPct.toFixed(1)}%)`
          );
          highCorrectionWarnings++;
        }
      });
    });
  });

  if (highCorrectionWarnings >= maxHighCorrectionWarnings) {
    warnings.push(
      `... and more cells with >±${SAFETY.warnRawDeltaPct}% corrections (showing first ${maxHighCorrectionWarnings})`
    );
  }

  return {
    gridResults,
    appliedVE,
    balanceReport,
    coverageReport,
    blockReasons,
    warnings,
    totalCells,
    skippedCells,
    clampedCells,
    boundedCells,
  };
}

/**
 * Get a summary of the apply report for display
 */
export function getApplySummary(report: ApplyReport): {
  canApply: boolean;
  status: 'blocked' | 'warnings' | 'ready';
  statusColor: string;
  headline: string;
  details: string[];
} {
  if (report.blockReasons.length > 0) {
    return {
      canApply: false,
      status: 'blocked',
      statusColor: 'text-red-400',
      headline: `Blocked: ${report.blockReasons[0].message}`,
      details: report.blockReasons.map((r) => r.message),
    };
  }

  if (report.warnings.length > 0) {
    return {
      canApply: true,
      status: 'warnings',
      statusColor: 'text-yellow-400',
      headline: `Ready with ${report.warnings.length} warning(s)`,
      details: [
        `${report.totalCells - report.skippedCells} cells will be updated`,
        `${report.skippedCells} cells skipped (insufficient data)`,
        `${report.clampedCells} cells clamped`,
        ...report.warnings.slice(0, 3),
      ],
    };
  }

  return {
    canApply: true,
    status: 'ready',
    statusColor: 'text-green-400',
    headline: 'Ready to apply corrections',
    details: [
      `${report.totalCells - report.skippedCells} cells will be updated`,
      `${report.skippedCells} cells skipped (insufficient data)`,
      `Coverage: ${report.coverageReport.weightedCoveragePct.toFixed(0)}%`,
    ],
  };
}
