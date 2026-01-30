/**
 * Cylinder Balance Checking - Detect front/rear imbalance
 *
 * Reports both raw and applied balance.
 * Warnings are based on RAW values to detect issues that clamping would mask.
 */

import { BalanceReport, DualCylinderHits } from '../../types/veApplyTypes';
import { sanitizeCorrection, SAFETY } from './veApplyValidation';

/**
 * Check cylinder balance using correction multipliers (not final VE).
 * Reports both raw and applied balance.
 * Warnings are based on RAW values to detect issues that clamping would mask.
 *
 * @param frontCorrections - Front cylinder correction multipliers
 * @param rearCorrections - Rear cylinder correction multipliers
 * @param hitCounts - Per-cylinder hit counts
 * @param rpmAxis - RPM axis values
 * @param mapAxis - MAP axis values
 * @param frontApplied - Optional applied multipliers for front (after clamping)
 * @param rearApplied - Optional applied multipliers for rear (after clamping)
 */
export function checkCylinderBalance(
  frontCorrections: number[][],
  rearCorrections: number[][],
  hitCounts: DualCylinderHits,
  rpmAxis: number[],
  mapAxis: number[],
  frontApplied?: number[][],
  rearApplied?: number[][]
): BalanceReport {
  let rawWeightedSumDiff = 0;
  let appliedWeightedSumDiff = 0;
  let totalWeight = 0;
  let rawMaxDiff = 0;
  let appliedMaxDiff = 0;
  let rawWorstCell: BalanceReport['rawWorstCell'] = null;
  let includedCellCount = 0;

  frontCorrections.forEach((row, rpmIdx) => {
    row.forEach((frontCorr, mapIdx) => {
      const frontHits = hitCounts.front[rpmIdx][mapIdx];
      const rearHits = hitCounts.rear[rpmIdx][mapIdx];
      const minHits = Math.min(frontHits, rearHits);

      // Exclude cells where either cylinder has insufficient data
      if (minHits < SAFETY.minHitsForInclusion) return;

      const rearCorr = rearCorrections[rpmIdx][mapIdx];

      // Sanitize both corrections
      const frontSafe = sanitizeCorrection(frontCorr);
      const rearSafe = sanitizeCorrection(rearCorr);

      // Skip if either is invalid
      if (frontSafe <= 0 || rearSafe <= 0) return;

      includedCellCount++;

      // Raw differential: (rear/front - 1) * 100
      // Positive = rear needs more fuel than front
      const rawDiffPct = (rearSafe / frontSafe - 1) * 100;
      const rawAbsDiff = Math.abs(rawDiffPct);

      // Use average of both cylinders' hits as weight
      const weight = (frontHits + rearHits) / 2;
      rawWeightedSumDiff += rawDiffPct * weight;
      totalWeight += weight;

      // Track worst raw cell
      if (rawAbsDiff > rawMaxDiff) {
        rawMaxDiff = rawAbsDiff;
        rawWorstCell = {
          rpm: rpmAxis[rpmIdx],
          map: mapAxis[mapIdx],
          diffPct: rawDiffPct,
        };
      }

      // Applied balance (if provided)
      if (frontApplied && rearApplied) {
        const frontApp = frontApplied[rpmIdx][mapIdx];
        const rearApp = rearApplied[rpmIdx][mapIdx];
        if (frontApp > 0 && rearApp > 0) {
          const appliedDiffPct = (rearApp / frontApp - 1) * 100;
          appliedWeightedSumDiff += appliedDiffPct * weight;
          appliedMaxDiff = Math.max(appliedMaxDiff, Math.abs(appliedDiffPct));
        }
      }
    });
  });

  const rawSystematicBiasPct =
    totalWeight > 0 ? rawWeightedSumDiff / totalWeight : 0;
  const appliedSystematicBiasPct =
    totalWeight > 0 ? appliedWeightedSumDiff / totalWeight : 0;

  const warnings: string[] = [];

  // Warnings based on RAW values (before clamping masks issues)
  if (Math.abs(rawSystematicBiasPct) > SAFETY.warnSystematicBiasPct) {
    const direction = rawSystematicBiasPct > 0 ? 'rear-rich' : 'front-rich';
    warnings.push(
      `Systematic ${direction} bias of ${rawSystematicBiasPct.toFixed(1)}% in raw corrections. ` +
        `May indicate unequal exhaust restriction, intake imbalance, or sensor drift. ` +
        `(Applied bias after clamping: ${appliedSystematicBiasPct.toFixed(1)}%)`
    );
  }

  if (rawMaxDiff > SAFETY.warnLocalizedImbalancePct && rawWorstCell) {
    warnings.push(
      `Cell [${rawWorstCell.rpm} RPM, ${rawWorstCell.map} kPa] shows ` +
        `${rawWorstCell.diffPct.toFixed(1)}% front/rear differential in raw corrections. ` +
        `Verify no localized issue (detonation, injector, gasket).`
    );
  }

  return {
    rawSystematicBiasPct,
    rawMaxLocalizedDiffPct: rawMaxDiff,
    rawWorstCell,
    appliedSystematicBiasPct,
    appliedMaxLocalizedDiffPct: appliedMaxDiff,
    warnings,
    includedCellCount,
  };
}

/**
 * Get balance summary for display
 */
export function getBalanceSummary(report: BalanceReport): {
  status: 'good' | 'warning' | 'critical';
  label: string;
  description: string;
} {
  const absBias = Math.abs(report.rawSystematicBiasPct);

  if (absBias < 1) {
    return {
      status: 'good',
      label: 'Balanced',
      description: 'Front and rear cylinders are well matched',
    };
  }

  if (absBias < SAFETY.warnSystematicBiasPct) {
    return {
      status: 'good',
      label: 'Acceptable',
      description: `Minor ${report.rawSystematicBiasPct > 0 ? 'rear-rich' : 'front-rich'} bias (${absBias.toFixed(1)}%)`,
    };
  }

  if (absBias < 5) {
    return {
      status: 'warning',
      label: 'Imbalanced',
      description: `Noticeable ${report.rawSystematicBiasPct > 0 ? 'rear-rich' : 'front-rich'} bias (${absBias.toFixed(1)}%)`,
    };
  }

  return {
    status: 'critical',
    label: 'Severe Imbalance',
    description: `Significant ${report.rawSystematicBiasPct > 0 ? 'rear-rich' : 'front-rich'} bias (${absBias.toFixed(1)}%) - investigate`,
  };
}
