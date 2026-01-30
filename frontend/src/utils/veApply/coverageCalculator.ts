/**
 * Coverage Calculator - Zone-weighted cell coverage metrics
 *
 * Uses cell-weighted formula: sum(sufficientCells * weight) / sum(totalCells * weight)
 * Zones with higher importance (cruise, partThrottle) have higher weights.
 */

import { CellZone, CoverageReport } from '../../types/veApplyTypes';
import { getCellZone, ZONE_WEIGHTS } from './zoneClassification';
import { SAFETY } from './veApplyValidation';

/**
 * Calculate zone-weighted cell coverage.
 * Uses cell-weighted formula: sum(sufficientCells * weight) / sum(totalCells * weight)
 *
 * @param hitCounts - 2D array of hit counts [rpmIdx][mapIdx]
 * @param rpmAxis - RPM axis values
 * @param mapAxis - MAP axis values
 */
export function calculateCoverage(
  hitCounts: number[][],
  rpmAxis: number[],
  mapAxis: number[]
): CoverageReport {
  const zoneCounts: Record<CellZone, { total: number; sufficient: number }> = {
    cruise: { total: 0, sufficient: 0 },
    partThrottle: { total: 0, sufficient: 0 },
    wot: { total: 0, sufficient: 0 },
    decel: { total: 0, sufficient: 0 },
    edge: { total: 0, sufficient: 0 },
  };

  let totalCells = 0;
  let activeCells = 0;
  let sufficientCells = 0;

  hitCounts.forEach((row, rpmIdx) => {
    row.forEach((hits, mapIdx) => {
      const rpm = rpmAxis[rpmIdx];
      const map = mapAxis[mapIdx];
      const zone = getCellZone(rpm, map);

      totalCells++;
      zoneCounts[zone].total++;

      if (hits >= 1) activeCells++;
      if (hits >= SAFETY.minHitsForInclusion) {
        sufficientCells++;
        zoneCounts[zone].sufficient++;
      }
    });
  });

  // Cell-weighted coverage
  let weightedNumerator = 0;
  let weightedDenominator = 0;

  const zoneBreakdown = (Object.keys(ZONE_WEIGHTS) as CellZone[]).map(
    (zone) => {
      const { total, sufficient } = zoneCounts[zone];
      const weight = ZONE_WEIGHTS[zone];
      const coveragePct = total > 0 ? (sufficient / total) * 100 : 100;

      weightedNumerator += sufficient * weight;
      weightedDenominator += total * weight;

      return {
        zone,
        totalCells: total,
        sufficientCells: sufficient,
        coveragePct,
        weight,
      };
    }
  );

  const activeCoveragePct =
    activeCells > 0 ? (sufficientCells / activeCells) * 100 : 0;
  const totalCoveragePct =
    totalCells > 0 ? (sufficientCells / totalCells) * 100 : 0;
  const weightedCoveragePct =
    weightedDenominator > 0
      ? (weightedNumerator / weightedDenominator) * 100
      : 0;

  const warnings: string[] = [];

  if (weightedCoveragePct < SAFETY.warnCoveragePct) {
    warnings.push(
      `Zone-weighted coverage is ${weightedCoveragePct.toFixed(0)}% ` +
        `(target: ≥${SAFETY.warnCoveragePct}%). Focus on cruise and part-throttle zones.`
    );
  }

  const cruiseZone = zoneBreakdown.find((z) => z.zone === 'cruise');
  if (cruiseZone && cruiseZone.coveragePct < 60) {
    warnings.push(
      `Cruise zone coverage is ${cruiseZone.coveragePct.toFixed(0)}%. ` +
        `This zone represents ~70% of typical riding—prioritize it.`
    );
  }

  return {
    totalCells,
    activeCells,
    sufficientCells,
    activeCoveragePct,
    totalCoveragePct,
    weightedCoveragePct,
    zoneBreakdown,
    warnings,
  };
}

/**
 * Calculate combined coverage for both cylinders
 * Uses minimum hits between front and rear for each cell
 */
export function calculateDualCylinderCoverage(
  frontHitCounts: number[][],
  rearHitCounts: number[][],
  rpmAxis: number[],
  mapAxis: number[]
): CoverageReport {
  // Create combined hit counts using minimum of both cylinders
  const combinedHitCounts = frontHitCounts.map((row, rpmIdx) =>
    row.map((frontHits, mapIdx) => {
      const rearHits = rearHitCounts[rpmIdx]?.[mapIdx] ?? 0;
      return Math.min(frontHits, rearHits);
    })
  );

  return calculateCoverage(combinedHitCounts, rpmAxis, mapAxis);
}

/**
 * Get coverage grade (A-F) based on weighted percentage
 */
export function getCoverageGrade(weightedCoveragePct: number): {
  grade: string;
  color: string;
  description: string;
} {
  if (weightedCoveragePct >= 90) {
    return {
      grade: 'A',
      color: 'text-green-400',
      description: 'Excellent coverage - ready for final apply',
    };
  }
  if (weightedCoveragePct >= 75) {
    return {
      grade: 'B',
      color: 'text-blue-400',
      description: 'Good coverage - suitable for apply',
    };
  }
  if (weightedCoveragePct >= 50) {
    return {
      grade: 'C',
      color: 'text-yellow-400',
      description: 'Moderate coverage - more data recommended',
    };
  }
  if (weightedCoveragePct >= 25) {
    return {
      grade: 'D',
      color: 'text-orange-400',
      description: 'Low coverage - collect more samples',
    };
  }
  return {
    grade: 'F',
    color: 'text-red-400',
    description: 'Insufficient coverage - continue data collection',
  };
}
