/**
 * Confidence Calculator - Zone-aware hit thresholds and clamp limits
 *
 * CRITICAL DESIGN DECISION:
 * Lower confidence = TIGHTER clamp (inch toward correct)
 *
 * This is the safer approach - if we're uncertain about the data,
 * we make smaller changes to avoid overcorrection.
 */

import { Confidence, ClampResult, CellZone } from '../../types/veApplyTypes';
import { getCellZone, ZONE_CONFIGS } from './zoneClassification';

/**
 * Clamp limits by confidence tier.
 * IMPORTANT: Lower confidence = TIGHTER clamp (inch toward correct).
 *
 * | Confidence | Clamp | Rationale |
 * |------------|-------|-----------|
 * | High       | ±7%   | Data is trustworthy, allow larger changes |
 * | Medium     | ±5%   | Some uncertainty, moderate changes |
 * | Low        | ±3%   | Uncertain data, small conservative changes |
 * | Skip       | —     | <minHits, preserve base VE entirely |
 */
export const CLAMP_LIMITS: Record<Exclude<Confidence, 'skip'>, number> = {
  high: 0.07, // ±7%
  medium: 0.05, // ±5%
  low: 0.03, // ±3%
};

/**
 * Determine confidence level and clamp limit for a cell.
 * Returns null limit for skip (insufficient hits).
 *
 * @param rpm - Cell RPM value
 * @param mapKpa - Cell MAP value in kPa
 * @param hitCount - Number of samples accumulated for this cell
 * @returns ClampResult with confidence level, clamp limit, and zone
 */
export function getClampResult(
  rpm: number,
  mapKpa: number,
  hitCount: number
): ClampResult {
  const zone = getCellZone(rpm, mapKpa);
  const config = ZONE_CONFIGS[zone];

  if (hitCount < config.minHits) {
    return { confidence: 'skip', limit: null, zone };
  }
  if (hitCount >= config.highHits) {
    return { confidence: 'high', limit: CLAMP_LIMITS.high, zone };
  }
  if (hitCount >= config.mediumHits) {
    return { confidence: 'medium', limit: CLAMP_LIMITS.medium, zone };
  }
  return { confidence: 'low', limit: CLAMP_LIMITS.low, zone };
}

/**
 * Get human-readable badge for confidence level.
 * Used by ConfidenceBadge component.
 */
export function getConfidenceBadge(confidence: Confidence): {
  label: string;
  color: string;
  bgColor: string;
  description: string;
} {
  switch (confidence) {
    case 'high':
      return {
        label: 'H',
        color: 'text-green-400',
        bgColor: 'bg-green-500/20',
        description: 'High confidence (±7% clamp)',
      };
    case 'medium':
      return {
        label: 'M',
        color: 'text-blue-400',
        bgColor: 'bg-blue-500/20',
        description: 'Medium confidence (±5% clamp)',
      };
    case 'low':
      return {
        label: 'L',
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-500/20',
        description: 'Low confidence (±3% clamp)',
      };
    case 'skip':
      return {
        label: '—',
        color: 'text-zinc-500',
        bgColor: 'bg-zinc-500/10',
        description: 'Skipped (<3 hits)',
      };
  }
}

/**
 * Get confidence for a cell without the full ClampResult
 * Useful for quick UI rendering
 */
export function getConfidenceLevel(
  rpm: number,
  mapKpa: number,
  hitCount: number
): Confidence {
  return getClampResult(rpm, mapKpa, hitCount).confidence;
}

/**
 * Calculate confidence distribution across a grid
 */
export function getConfidenceDistribution(
  hitCounts: number[][],
  rpmAxis: number[],
  mapAxis: number[]
): Record<Confidence, number> {
  const distribution: Record<Confidence, number> = {
    high: 0,
    medium: 0,
    low: 0,
    skip: 0,
  };

  hitCounts.forEach((row, rpmIdx) => {
    row.forEach((hits, mapIdx) => {
      const confidence = getConfidenceLevel(
        rpmAxis[rpmIdx],
        mapAxis[mapIdx],
        hits
      );
      distribution[confidence]++;
    });
  });

  return distribution;
}
