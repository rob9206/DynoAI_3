/**
 * VE Apply Validation - Block conditions and input sanitization
 *
 * This module provides safety checks that must pass before applying corrections.
 * Blocking conditions prevent the apply operation entirely.
 */

import {
  CorrectionMultiplier,
  BlockReason,
  SafetyThresholds,
  DualCylinderVE,
  DualCylinderHits,
  DualCylinderCorrections,
} from '../../types/veApplyTypes';

export const EPSILON = 1e-6;

/**
 * Default safety thresholds
 */
export const SAFETY: SafetyThresholds = {
  blockRawDeltaPct: 25,
  warnRawDeltaPct: 10,
  warnSystematicBiasPct: 2,
  warnLocalizedImbalancePct: 5,
  minHitsForInclusion: 3,
  warnCoveragePct: 50,
};

/**
 * Validate a correction value.
 * Returns null if invalid (NaN, Infinity, ≤0).
 */
export function validateCorrection(
  value: unknown
): CorrectionMultiplier | null {
  if (typeof value !== 'number') return null;
  if (!Number.isFinite(value)) return null;
  if (value <= 0) return null;
  return value;
}

/**
 * Sanitize a correction value, defaulting to 1.0 if invalid.
 * Logs a warning for invalid values.
 */
export function sanitizeCorrection(value: unknown): CorrectionMultiplier {
  const valid = validateCorrection(value);
  if (valid === null) {
    console.warn(`Invalid correction value: ${value}, treating as 1.0`);
    return 1.0;
  }
  return valid;
}

/**
 * Check if a cell has meaningful correction data.
 * Must have minimum hits AND non-unity correction.
 */
export function hasActiveCorrection(
  correction: number,
  hitCount: number,
  minHits: number = SAFETY.minHitsForInclusion
): boolean {
  if (hitCount < minHits) return false;
  const sanitized = sanitizeCorrection(correction);
  return Math.abs(sanitized - 1.0) > EPSILON;
}

/**
 * Check all block conditions before apply.
 * Returns array of blocking reasons (empty = OK to proceed).
 */
export function checkBlockConditions(
  baseVE: DualCylinderVE | null,
  corrections: DualCylinderCorrections,
  hitCounts: DualCylinderHits,
  rpmAxis: number[],
  mapAxis: number[]
): BlockReason[] {
  const blocks: BlockReason[] = [];

  // 1. Missing base VE
  if (!baseVE) {
    blocks.push({
      type: 'missing_base',
      message:
        'Import a base VE table (PVV or preset) before applying corrections.',
    });
    return blocks;
  }

  // 2. Empty grid check
  if (baseVE.front.length === 0 || baseVE.front[0]?.length === 0) {
    blocks.push({
      type: 'empty_grid',
      message: 'Base VE grid is empty. Import a valid tune file.',
    });
    return blocks;
  }

  // 3. Shape mismatch (all grids must match)
  const expectedRows = baseVE.front.length;
  const expectedCols = baseVE.front[0].length;

  const grids = [
    { name: 'baseVE.front', grid: baseVE.front },
    { name: 'baseVE.rear', grid: baseVE.rear },
    { name: 'corrections.front', grid: corrections.front },
    { name: 'corrections.rear', grid: corrections.rear },
    { name: 'hitCounts.front', grid: hitCounts.front },
    { name: 'hitCounts.rear', grid: hitCounts.rear },
  ];

  const mismatches = grids.filter(
    ({ grid }) =>
      grid.length !== expectedRows || grid[0]?.length !== expectedCols
  );

  if (mismatches.length > 0) {
    blocks.push({
      type: 'shape_mismatch',
      message:
        `Grid dimensions must be ${expectedRows}x${expectedCols}. ` +
        `Mismatched: ${mismatches.map((m) => m.name).join(', ')}`,
    });
    return blocks; // Can't proceed with other checks
  }

  // 4. Invalid base VE values (check both cylinders)
  const invalidBaseCells: Array<{
    rpm: number;
    map: number;
    value: number;
    cylinder: string;
  }> = [];

  (['front', 'rear'] as const).forEach((cylinder) => {
    baseVE[cylinder].forEach((row, rpmIdx) => {
      row.forEach((val, mapIdx) => {
        if (!Number.isFinite(val) || val <= 0) {
          invalidBaseCells.push({
            rpm: rpmAxis[rpmIdx],
            map: mapAxis[mapIdx],
            value: val,
            cylinder,
          });
        }
      });
    });
  });

  if (invalidBaseCells.length > 0) {
    blocks.push({
      type: 'invalid_base_ve',
      message: `Base VE contains ${invalidBaseCells.length} invalid cells (zero, negative, or NaN).`,
      cells: invalidBaseCells.slice(0, 10).map((c) => ({
        rpm: c.rpm,
        map: c.map,
        value: c.value,
      })),
    });
  }

  // 5. Partial cylinder data (only check cells with sufficient hits)
  let frontActiveCount = 0;
  let rearActiveCount = 0;

  corrections.front.forEach((row, rpmIdx) => {
    row.forEach((corr, mapIdx) => {
      if (hasActiveCorrection(corr, hitCounts.front[rpmIdx][mapIdx])) {
        frontActiveCount++;
      }
    });
  });

  corrections.rear.forEach((row, rpmIdx) => {
    row.forEach((corr, mapIdx) => {
      if (hasActiveCorrection(corr, hitCounts.rear[rpmIdx][mapIdx])) {
        rearActiveCount++;
      }
    });
  });

  const hasFront = frontActiveCount > 0;
  const hasRear = rearActiveCount > 0;

  if (hasFront !== hasRear) {
    blocks.push({
      type: 'partial_cylinder',
      message:
        `Both cylinders required. Active cells: front=${frontActiveCount}, rear=${rearActiveCount}. ` +
        `Ensure data collection captures both cylinders.`,
    });
  }

  // 6. Extreme corrections (only check cells with sufficient hits)
  const extremeCells: Array<{
    rpm: number;
    map: number;
    value: number;
    cylinder: string;
  }> = [];

  (['front', 'rear'] as const).forEach((cylinder) => {
    corrections[cylinder].forEach((row, rpmIdx) => {
      row.forEach((corr, mapIdx) => {
        const hits = hitCounts[cylinder][rpmIdx][mapIdx];

        // Only check cells with meaningful data
        if (hits < SAFETY.minHitsForInclusion) return;

        const sanitized = sanitizeCorrection(corr);
        const rawDeltaPct = Math.abs((sanitized - 1) * 100);

        if (rawDeltaPct > SAFETY.blockRawDeltaPct) {
          extremeCells.push({
            rpm: rpmAxis[rpmIdx],
            map: mapAxis[mapIdx],
            value: rawDeltaPct,
            cylinder,
          });
        }
      });
    });
  });

  if (extremeCells.length > 0) {
    blocks.push({
      type: 'extreme_correction',
      message:
        `${extremeCells.length} cells exceed ±${SAFETY.blockRawDeltaPct}% correction. ` +
        `This usually indicates wrong base tune, sensor error, or hardware change.`,
      cells: extremeCells.slice(0, 10).map((c) => ({
        rpm: c.rpm,
        map: c.map,
        value: c.value,
      })),
    });
  }

  return blocks;
}

/**
 * Get human-readable description for a block reason type
 */
export function getBlockReasonDescription(type: BlockReason['type']): string {
  switch (type) {
    case 'extreme_correction':
      return 'Extreme corrections detected - check sensor data or base tune';
    case 'missing_base':
      return 'No base VE table loaded - import a PVV file or select a preset';
    case 'shape_mismatch':
      return 'Grid dimensions do not match - reload data';
    case 'partial_cylinder':
      return 'Missing data for one cylinder - collect more samples';
    case 'invalid_base_ve':
      return 'Base VE contains invalid values - check imported file';
    case 'empty_grid':
      return 'Empty grid - import a valid tune file';
    default:
      return 'Unknown validation error';
  }
}
