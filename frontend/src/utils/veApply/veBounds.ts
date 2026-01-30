/**
 * VE Bounds - Tune-type specific VE limits
 *
 * Different engine configurations have different valid VE ranges.
 * These bounds prevent applying corrections that would result in
 * physically unrealistic VE values.
 */

import {
  VEBoundsConfig,
  VEBoundsPreset,
  BoundsCheckResult,
} from '../../types/veApplyTypes';

/**
 * VE bounds presets for different tune types
 *
 * | Preset | Min | Max | Mode | Use Case |
 * |--------|-----|-----|------|----------|
 * | na_harley | 15% | 115% | Enforce | Stock/mild cams |
 * | stage_1 | 15% | 120% | Enforce | Stage 1 cams |
 * | stage_2 | 15% | 125% | Enforce | Stage 2+ cams |
 * | boosted | 10% | 200% | Warn only | Turbo/supercharged |
 * | custom | 0% | 999% | Warn only | No enforcement |
 */
export const VE_BOUNDS_PRESETS: Record<VEBoundsPreset, VEBoundsConfig> = {
  na_harley: { min: 15, max: 115, warnOnly: false },
  stage_1: { min: 15, max: 120, warnOnly: false },
  stage_2: { min: 15, max: 125, warnOnly: false },
  boosted: { min: 10, max: 200, warnOnly: true }, // Warn only, don't clamp
  custom: { min: 0, max: 999, warnOnly: true }, // No enforcement
};

/**
 * Apply VE bounds to a calculated VE value
 *
 * @param ve - The calculated VE value to check
 * @param config - The bounds configuration to apply
 * @returns BoundsCheckResult with original, bounded values and metadata
 */
export function applyVEBounds(
  ve: number,
  config: VEBoundsConfig
): BoundsCheckResult {
  const belowMin = ve < config.min;
  const aboveMax = ve > config.max;

  if (!belowMin && !aboveMax) {
    return {
      originalVE: ve,
      boundedVE: ve,
      wasBounded: false,
      boundType: 'none',
    };
  }

  // If warnOnly, don't actually clamp
  if (config.warnOnly) {
    return {
      originalVE: ve,
      boundedVE: ve,
      wasBounded: false,
      boundType: belowMin ? 'floor' : 'ceiling',
    };
  }

  return {
    originalVE: ve,
    boundedVE: belowMin ? config.min : config.max,
    wasBounded: true,
    boundType: belowMin ? 'floor' : 'ceiling',
  };
}

/**
 * Get display info for a bounds preset
 */
export function getBoundsPresetInfo(preset: VEBoundsPreset): {
  name: string;
  description: string;
  range: string;
} {
  switch (preset) {
    case 'na_harley':
      return {
        name: 'NA Harley',
        description: 'Stock or mild cam naturally aspirated',
        range: '15-115%',
      };
    case 'stage_1':
      return {
        name: 'Stage 1',
        description: 'Stage 1 cam, intake, exhaust',
        range: '15-120%',
      };
    case 'stage_2':
      return {
        name: 'Stage 2+',
        description: 'Stage 2 or higher cams',
        range: '15-125%',
      };
    case 'boosted':
      return {
        name: 'Boosted',
        description: 'Turbo or supercharged (warn only)',
        range: '10-200%',
      };
    case 'custom':
      return {
        name: 'Custom',
        description: 'No bounds enforcement',
        range: 'Unlimited',
      };
  }
}

/**
 * Count how many cells would be bounded by a given config
 */
export function countBoundedCells(
  veGrid: number[][],
  config: VEBoundsConfig
): { floor: number; ceiling: number; total: number } {
  let floor = 0;
  let ceiling = 0;

  veGrid.forEach((row) => {
    row.forEach((ve) => {
      if (ve < config.min) floor++;
      if (ve > config.max) ceiling++;
    });
  });

  return { floor, ceiling, total: floor + ceiling };
}
