/**
 * Zone Classification - Categorize VE table cells by operating region
 *
 * Different zones have different achievable hit counts and importance weights.
 * This affects confidence thresholds and coverage calculations.
 */

import { CellZone, ZoneConfig } from '../../types/veApplyTypes';

/**
 * Zone definitions:
 * - cruise:       31-69 kPa, 1200-5500 RPM (steady-state riding, ~70% of miles)
 * - partThrottle: 70-94 kPa, 1200-5500 RPM (roll-on acceleration)
 * - wot:          95+ kPa, 1200-5500 RPM (full power pulls)
 * - decel:        ≤30 kPa, 1200-5500 RPM (engine braking, fuel cut)
 * - edge:         <1200 or >5500 RPM, any MAP (idle, redline)
 */
export function getCellZone(rpm: number, mapKpa: number): CellZone {
  // RPM extremes are always edge
  if (rpm >= 5500 || rpm <= 1200) return 'edge';

  // MAP-based zones for normal RPM range
  if (mapKpa <= 30) return 'decel';
  if (mapKpa >= 95) return 'wot';
  if (mapKpa >= 70) return 'partThrottle';
  return 'cruise';
}

/**
 * Hit count thresholds per zone.
 * WOT/decel/edge have lower thresholds because they're harder to hit.
 */
export const ZONE_CONFIGS: Record<CellZone, ZoneConfig> = {
  cruise: { highHits: 100, mediumHits: 20, minHits: 3 },
  partThrottle: { highHits: 80, mediumHits: 15, minHits: 3 },
  wot: { highHits: 30, mediumHits: 10, minHits: 3 },
  decel: { highHits: 50, mediumHits: 15, minHits: 3 },
  edge: { highHits: 30, mediumHits: 10, minHits: 3 },
};

/**
 * Zone weights for coverage calculation.
 * Higher weight = more important to have good coverage.
 */
export const ZONE_WEIGHTS: Record<CellZone, number> = {
  cruise: 5, // Most riding time, fuel economy, heat
  partThrottle: 4, // Acceleration feel, responsiveness
  wot: 2, // Peak power, but brief duration
  decel: 1, // Transient, often fuel-cut anyway
  edge: 1, // Rarely reached in normal riding
};

/**
 * Get zone display info for UI
 */
export function getZoneDisplayInfo(zone: CellZone): {
  label: string;
  description: string;
  color: string;
} {
  switch (zone) {
    case 'cruise':
      return {
        label: 'Cruise',
        description: '31-69 kPa, steady-state (~70% of riding)',
        color: 'green',
      };
    case 'partThrottle':
      return {
        label: 'Part Throttle',
        description: '70-94 kPa, roll-on acceleration',
        color: 'blue',
      };
    case 'wot':
      return {
        label: 'WOT',
        description: '95+ kPa, full power',
        color: 'red',
      };
    case 'decel':
      return {
        label: 'Decel',
        description: '≤30 kPa, engine braking',
        color: 'purple',
      };
    case 'edge':
      return {
        label: 'Edge',
        description: '<1200 or >5500 RPM',
        color: 'gray',
      };
  }
}

/**
 * Classify all cells in a grid by zone
 */
export function classifyGrid(
  rpmAxis: number[],
  mapAxis: number[]
): CellZone[][] {
  return rpmAxis.map((rpm) => mapAxis.map((map) => getCellZone(rpm, map)));
}
