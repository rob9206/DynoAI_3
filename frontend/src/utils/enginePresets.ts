/**
 * Engine Presets - Default VE and AFR tables for common engine types.
 *
 * Presets are fallback values when no PVV file is available.
 * All VE tables are normalized to the 17-column PVV MAP bin layout.
 */

// Grid-only configuration for LiveVETable (no VE/AFR data)
export type EnginePreset =
  | "harley_m8"
  | "harley_tc"
  | "harley_tc_110"
  | "harley_revmax_1250"
  | "harley_revmax_975"
  | "sportbike_600"
  | "sportbike_1000"
  | "custom";

export interface EngineConfig {
  name: string;
  rpmBins: number[];
  mapBins: number[];
  maxRpm: number;
}

// Full preset data with VE tables and AFR targets
export interface EnginePresetData {
  name: string;
  description: string;
  rpmBins: number[];
  mapBins: number[];
  maxRpm: number;

  // Default VE table (Front cylinder, used for both if rear not specified)
  veTableFront: number[][];
  veTableRear?: number[][]; // Optional separate rear cylinder table

  // Default AFR targets by MAP (kPa -> AFR)
  afrTargets: Record<number, number>;
}

// Rounded integer form of PVV ECU MAP bins (17 columns)
const PVV_MAP_BINS: number[] = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 85, 95, 105];
const LEGACY_MAP_BINS: number[] = [20, 30, 40, 50, 60, 70, 80, 90, 100, 110];

function interpolateLegacyValue(sourceX: number[], sourceY: number[], targetX: number): number {
  if (targetX <= sourceX[0]) return sourceY[0];
  if (targetX >= sourceX[sourceX.length - 1]) return sourceY[sourceY.length - 1];

  for (let i = 0; i < sourceX.length - 1; i++) {
    const x0 = sourceX[i];
    const x1 = sourceX[i + 1];
    if (targetX >= x0 && targetX <= x1) {
      const t = (targetX - x0) / (x1 - x0);
      return sourceY[i] + (sourceY[i + 1] - sourceY[i]) * t;
    }
  }
  return sourceY[sourceY.length - 1];
}

function expandLegacyVETable(legacyRows: number[][]): number[][] {
  return legacyRows.map((row) =>
    PVV_MAP_BINS.map((mapBin) => Number(interpolateLegacyValue(LEGACY_MAP_BINS, row, mapBin).toFixed(1)))
  );
}

function expandLegacyAfrTargets(legacyTargets: Record<number, number>): Record<number, number> {
  const values = LEGACY_MAP_BINS.map((bin) => legacyTargets[bin]);
  return PVV_MAP_BINS.reduce<Record<number, number>>((acc, bin) => {
    acc[bin] = Number(interpolateLegacyValue(LEGACY_MAP_BINS, values, bin).toFixed(2));
    return acc;
  }, {});
}

/**
 * Harley-Davidson Milwaukee-Eight (M8) Engine
 * 107/114/117/131 cubic inch variants
 */
const HARLEY_M8: EnginePresetData = {
  name: "Harley M8",
  description: "Milwaukee-Eight 107/114/117/131",
  rpmBins: [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500],
  mapBins: [...PVV_MAP_BINS],
  maxRpm: 6500,
  veTableFront: expandLegacyVETable([
    [70, 72, 75, 78, 80, 82, 84, 86, 88, 90],
    [72, 74, 77, 80, 83, 85, 87, 89, 91, 93],
    [74, 76, 79, 82, 85, 88, 90, 92, 94, 96],
    [76, 78, 81, 84, 87, 90, 92, 94, 96, 98],
    [78, 80, 83, 86, 89, 92, 94, 96, 98, 100],
    [80, 82, 85, 88, 91, 94, 96, 98, 100, 102],
    [82, 84, 87, 90, 93, 96, 98, 100, 102, 104],
    [84, 86, 89, 92, 95, 98, 100, 102, 104, 106],
    [85, 87, 90, 93, 96, 99, 101, 103, 105, 107],
    [86, 88, 91, 94, 97, 100, 102, 104, 106, 108],
    [87, 89, 92, 95, 98, 101, 103, 105, 107, 109],
    [88, 90, 93, 96, 99, 102, 104, 106, 108, 110],
  ]),
  afrTargets: expandLegacyAfrTargets({
    20: 14.7,
    30: 14.7,
    40: 14.5,
    50: 14.0,
    60: 13.5,
    70: 13.0,
    80: 12.8,
    90: 12.5,
    100: 12.2,
    110: 12.0,
  }),
};

/**
 * Harley-Davidson Twin Cam (stock/mild) engine preset
 * Intended for 88/96/103 and conservative 110 baselines.
 */
const HARLEY_TC: EnginePresetData = {
  name: "Harley Twin Cam",
  description: "Twin Cam 88/96/103 (conservative baseline)",
  rpmBins: [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000],
  mapBins: [...PVV_MAP_BINS],
  maxRpm: 6000,
  veTableFront: expandLegacyVETable([
    [68, 70, 73, 76, 79, 81, 83, 85, 87, 89],
    [70, 72, 75, 78, 81, 83, 85, 87, 89, 91],
    [72, 74, 77, 80, 83, 86, 88, 90, 92, 94],
    [74, 76, 79, 82, 85, 88, 90, 92, 94, 96],
    [76, 78, 81, 84, 87, 90, 92, 94, 96, 98],
    [78, 80, 83, 86, 89, 92, 94, 96, 98, 100],
    [80, 82, 85, 88, 91, 94, 96, 98, 100, 102],
    [81, 83, 86, 89, 92, 95, 97, 99, 101, 103],
    [82, 84, 87, 90, 93, 96, 98, 100, 102, 104],
    [83, 85, 88, 91, 94, 97, 99, 101, 103, 105],
    [84, 86, 89, 92, 95, 98, 100, 102, 104, 106],
  ]),
  afrTargets: expandLegacyAfrTargets({
    20: 14.7,
    30: 14.7,
    40: 14.5,
    50: 14.0,
    60: 13.5,
    70: 13.0,
    80: 12.8,
    90: 12.5,
    100: 12.3,
    110: 12.0,
  }),
};

/**
 * Harley-Davidson Twin Cam 110 (FXDLS/SE 110)
 * Real-world seeded MAP VE data from 16D110002401 calibration.
 */
const HARLEY_TC_110: EnginePresetData = {
  name: "Harley Twin Cam 110",
  description: "Twin Cam 110 (real calibration baseline)",
  rpmBins: [750, 1000, 1125, 1250, 1500, 1750, 2000, 2250, 2500, 2750, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000],
  mapBins: [...PVV_MAP_BINS],
  maxRpm: 8000,
  veTableFront: [
    [70.0, 70.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 82.5],
    [70.5, 70.5, 80.0, 85.5, 80.0, 88.5, 87.5, 88.5, 85.5, 85.0, 87.5, 86.0, 87.5, 83.0, 83.0, 83.0, 83.0],
    [72.5, 72.5, 80.0, 82.0, 83.0, 83.0, 82.0, 83.0, 83.0, 82.0, 84.0, 82.5, 85.0, 84.0, 86.0, 83.0, 85.5],
    [76.0, 75.5, 82.5, 81.0, 85.5, 87.0, 86.5, 86.0, 87.5, 87.0, 87.5, 88.5, 89.5, 89.5, 88.0, 92.5, 95.0],
    [81.5, 80.5, 85.5, 82.5, 88.5, 90.0, 91.5, 94.0, 96.5, 97.0, 98.0, 98.5, 98.5, 98.5, 98.0, 105.0, 108.0],
    [83.0, 82.0, 87.5, 98.0, 100.0, 104.5, 106.5, 108.5, 108.5, 106.5, 108.0, 106.5, 108.0, 107.5, 108.0, 109.5, 113.0],
    [78.5, 78.5, 95.0, 102.5, 105.0, 110.5, 112.5, 108.0, 107.0, 107.0, 104.0, 103.0, 102.5, 101.0, 97.5, 94.0, 96.5],
    [80.5, 80.5, 90.5, 94.0, 96.0, 97.0, 98.0, 92.0, 92.5, 89.0, 89.5, 88.5, 86.5, 83.5, 82.0, 85.0, 87.5],
    [83.5, 84.0, 93.5, 95.5, 94.5, 93.5, 93.5, 92.5, 90.0, 88.0, 87.5, 86.5, 86.0, 85.5, 86.5, 92.0, 95.0],
    [81.0, 81.0, 95.0, 96.0, 100.0, 100.0, 101.0, 102.0, 97.0, 98.0, 96.0, 96.0, 94.0, 95.5, 93.5, 101.5, 104.5],
    [75.5, 75.5, 85.0, 95.0, 98.0, 102.5, 108.5, 110.0, 110.0, 110.0, 107.5, 106.0, 103.5, 102.0, 101.0, 113.0, 116.5],
    [73.0, 73.0, 97.5, 106.0, 116.5, 119.5, 125.5, 119.5, 117.5, 117.5, 112.0, 109.5, 106.5, 104.5, 103.5, 110.5, 114.0],
    [71.5, 72.0, 74.0, 81.0, 104.5, 114.0, 122.5, 123.5, 118.5, 116.5, 109.5, 107.5, 103.5, 100.5, 101.5, 111.5, 115.0],
    [71.0, 71.5, 68.0, 73.0, 84.5, 96.5, 104.0, 110.0, 107.5, 104.5, 101.5, 98.0, 95.5, 94.0, 95.5, 103.5, 106.5],
    [71.0, 71.5, 68.5, 76.0, 84.5, 90.5, 98.5, 106.5, 102.0, 100.0, 98.0, 94.5, 93.0, 91.0, 91.0, 96.0, 98.5],
    [71.0, 71.0, 73.0, 78.0, 82.5, 95.5, 97.0, 101.0, 98.5, 96.5, 94.0, 92.5, 92.5, 91.5, 91.0, 92.5, 95.5],
    [71.0, 71.0, 71.5, 78.0, 82.0, 89.0, 92.5, 96.5, 92.5, 91.5, 88.0, 86.5, 86.0, 84.0, 82.5, 86.0, 88.5],
    [71.0, 71.0, 71.5, 72.5, 74.0, 90.0, 90.0, 90.0, 90.0, 90.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0],
    [71.0, 71.0, 71.5, 72.5, 74.0, 90.0, 90.0, 90.0, 90.0, 90.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0],
    [71.0, 71.0, 71.5, 72.5, 74.0, 90.0, 90.0, 90.0, 90.0, 90.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0],
    [71.0, 71.0, 71.5, 72.5, 74.0, 90.0, 90.0, 90.0, 90.0, 90.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0],
  ],
  veTableRear: [
    [70.0, 69.5, 69.5, 80.0, 80.0, 80.0, 90.0, 90.0, 90.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 82.5],
    [70.0, 69.5, 68.5, 85.5, 84.0, 89.5, 91.5, 92.0, 90.0, 89.5, 89.5, 85.0, 83.0, 84.0, 84.0, 84.0, 84.0],
    [72.0, 71.5, 68.5, 82.5, 86.5, 89.5, 88.5, 87.0, 88.0, 86.5, 85.0, 82.5, 85.5, 84.5, 84.5, 84.5, 87.0],
    [76.0, 74.5, 82.5, 82.0, 86.5, 86.5, 86.0, 86.0, 86.0, 85.0, 85.0, 85.0, 86.5, 87.5, 86.5, 97.0, 99.5],
    [81.5, 80.5, 88.0, 87.5, 94.5, 93.5, 94.0, 96.0, 98.0, 100.5, 105.0, 102.5, 102.0, 105.5, 108.5, 118.5, 122.0],
    [83.5, 82.5, 91.5, 103.5, 106.0, 107.0, 107.0, 107.5, 110.0, 109.5, 110.5, 110.0, 107.5, 107.0, 106.5, 116.0, 119.5],
    [77.5, 78.5, 95.5, 109.5, 108.0, 111.5, 109.0, 110.5, 110.0, 110.5, 105.0, 102.0, 101.0, 100.5, 97.0, 100.5, 103.5],
    [80.5, 81.0, 91.5, 99.0, 101.0, 101.5, 99.5, 97.5, 102.0, 99.0, 95.5, 92.5, 90.5, 88.5, 84.5, 88.5, 91.0],
    [84.5, 84.0, 93.5, 93.0, 94.5, 93.5, 93.0, 94.0, 93.5, 90.5, 88.0, 86.0, 85.0, 84.5, 85.5, 93.5, 96.5],
    [81.0, 81.0, 102.5, 106.0, 105.5, 103.0, 99.5, 102.0, 96.5, 99.0, 96.0, 94.0, 91.5, 93.0, 92.5, 99.5, 102.5],
    [75.5, 75.5, 94.5, 103.0, 114.0, 109.0, 108.0, 108.5, 110.5, 109.5, 104.0, 102.5, 98.5, 97.0, 97.5, 103.5, 106.5],
    [73.0, 73.0, 98.0, 105.0, 112.5, 113.0, 117.5, 119.5, 120.5, 118.0, 115.0, 109.5, 105.5, 106.0, 106.0, 110.5, 114.0],
    [71.5, 72.0, 75.0, 84.0, 98.5, 105.0, 113.0, 121.0, 117.0, 119.5, 113.5, 108.5, 106.0, 105.0, 105.5, 113.0, 116.5],
    [71.0, 71.5, 70.0, 75.0, 84.5, 94.5, 96.5, 106.5, 110.5, 108.0, 103.5, 100.5, 97.5, 97.5, 99.5, 108.0, 111.0],
    [71.0, 71.5, 67.5, 73.5, 80.5, 89.0, 93.5, 101.5, 103.5, 101.0, 97.0, 94.0, 93.0, 93.5, 96.0, 102.5, 105.5],
    [71.0, 71.0, 69.5, 73.0, 82.5, 91.0, 92.5, 102.0, 101.0, 96.0, 94.0, 94.0, 93.5, 93.5, 97.5, 101.0, 104.0],
    [71.0, 71.0, 71.5, 70.0, 73.5, 82.0, 91.5, 94.0, 95.5, 92.5, 88.5, 85.5, 85.0, 85.5, 85.0, 90.0, 92.5],
    [71.0, 71.0, 71.5, 72.5, 74.0, 80.0, 90.0, 90.0, 90.0, 90.0, 80.0, 80.0, 80.0, 80.0, 80.0, 90.0, 90.0],
    [71.0, 71.0, 71.5, 72.5, 74.0, 80.0, 90.0, 90.0, 90.0, 90.0, 80.0, 80.0, 80.0, 80.0, 80.0, 90.0, 90.0],
    [71.0, 71.0, 71.5, 72.5, 74.0, 80.0, 90.0, 90.0, 90.0, 90.0, 80.0, 80.0, 80.0, 80.0, 80.0, 90.0, 90.0],
    [71.0, 71.0, 71.5, 72.5, 74.0, 80.0, 90.0, 90.0, 90.0, 90.0, 80.0, 80.0, 80.0, 80.0, 80.0, 90.0, 90.0],
  ],
  afrTargets: {
    10: 14.29,
    15: 14.29,
    20: 14.29,
    25: 14.29,
    30: 14.37,
    35: 14.37,
    40: 14.37,
    45: 14.37,
    50: 14.37,
    55: 14.37,
    60: 14.37,
    65: 14.37,
    70: 14.37,
    75: 14.39,
    85: 13.08,
    95: 12.88,
    105: 12.88,
  },
};

/**
 * Harley-Davidson Revolution Max 1250 (Sportster S / Pan America)
 */
const HARLEY_REVMAX_1250: EnginePresetData = {
  name: "Harley RevMax 1250",
  description: "Revolution Max 1250 (Sportster S / Pan America)",
  rpmBins: [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000],
  mapBins: [...PVV_MAP_BINS],
  maxRpm: 9500,
  veTableFront: expandLegacyVETable([
    [72, 74, 77, 80, 83, 86, 88, 90, 92, 94],
    [74, 76, 79, 82, 85, 88, 91, 93, 95, 97],
    [76, 78, 81, 84, 87, 90, 93, 95, 97, 99],
    [78, 80, 83, 86, 89, 92, 95, 97, 99, 101],
    [80, 82, 85, 88, 91, 94, 97, 99, 101, 103],
    [82, 84, 87, 90, 93, 96, 99, 101, 103, 105],
    [84, 86, 89, 92, 95, 98, 101, 103, 105, 107],
    [85, 87, 90, 93, 96, 99, 102, 104, 106, 108],
    [86, 88, 91, 94, 97, 100, 103, 105, 107, 109],
  ]),
  afrTargets: expandLegacyAfrTargets({
    20: 14.7,
    30: 14.7,
    40: 14.5,
    50: 14.0,
    60: 13.5,
    70: 13.0,
    80: 12.6,
    90: 12.3,
    100: 12.2,
    110: 12.0,
  }),
};

/**
 * Harley-Davidson Revolution Max 975T (Nightster)
 */
const HARLEY_REVMAX_975: EnginePresetData = {
  name: "Harley RevMax 975",
  description: "Revolution Max 975T (Nightster)",
  rpmBins: [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000],
  mapBins: [...PVV_MAP_BINS],
  maxRpm: 9000,
  veTableFront: expandLegacyVETable([
    [71, 73, 76, 79, 82, 85, 87, 89, 91, 93],
    [73, 75, 78, 81, 84, 87, 90, 92, 94, 96],
    [75, 77, 80, 83, 86, 89, 92, 94, 96, 98],
    [77, 79, 82, 85, 88, 91, 94, 96, 98, 100],
    [79, 81, 84, 87, 90, 93, 96, 98, 100, 102],
    [81, 83, 86, 89, 92, 95, 98, 100, 102, 104],
    [82, 84, 87, 90, 93, 96, 99, 101, 103, 105],
    [83, 85, 88, 91, 94, 97, 100, 102, 104, 106],
  ]),
  afrTargets: expandLegacyAfrTargets({
    20: 14.7,
    30: 14.7,
    40: 14.5,
    50: 14.0,
    60: 13.5,
    70: 13.0,
    80: 12.6,
    90: 12.3,
    100: 12.2,
    110: 12.0,
  }),
};

/**
 * 600cc sportbike (generic)
 */
const SPORTBIKE_600: EnginePresetData = {
  name: "Sportbike 600cc",
  description: "High-revving 600cc inline-4",
  rpmBins: [2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000],
  mapBins: [...PVV_MAP_BINS],
  maxRpm: 15000,
  veTableFront: expandLegacyVETable([
    [65, 68, 72, 76, 80, 83, 86, 88, 90, 92],
    [68, 71, 75, 79, 83, 86, 89, 91, 93, 95],
    [71, 74, 78, 82, 86, 89, 92, 94, 96, 98],
    [74, 77, 81, 85, 89, 92, 95, 97, 99, 101],
    [77, 80, 84, 88, 92, 95, 98, 100, 102, 104],
    [80, 83, 87, 91, 95, 98, 101, 103, 105, 107],
    [82, 85, 89, 93, 97, 100, 103, 105, 107, 109],
    [84, 87, 91, 95, 99, 102, 105, 107, 109, 111],
    [86, 89, 93, 97, 101, 104, 107, 109, 111, 113],
    [87, 90, 94, 98, 102, 105, 108, 110, 112, 114],
    [88, 91, 95, 99, 103, 106, 109, 111, 113, 115],
    [89, 92, 96, 100, 104, 107, 110, 112, 114, 116],
    [90, 93, 97, 101, 105, 108, 111, 113, 115, 117],
    [91, 94, 98, 102, 106, 109, 112, 114, 116, 118],
  ]),
  afrTargets: expandLegacyAfrTargets({
    20: 14.7,
    30: 14.7,
    40: 14.5,
    50: 14.2,
    60: 13.8,
    70: 13.4,
    80: 13.0,
    90: 12.6,
    100: 12.2,
    110: 11.8,
  }),
};

/**
 * 1000cc sportbike (generic)
 */
const SPORTBIKE_1000: EnginePresetData = {
  name: "Sportbike 1000cc",
  description: "High-power 1000cc inline-4",
  rpmBins: [2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000],
  mapBins: [...PVV_MAP_BINS],
  maxRpm: 13000,
  veTableFront: expandLegacyVETable([
    [68, 71, 75, 79, 83, 86, 89, 91, 93, 95],
    [71, 74, 78, 82, 86, 89, 92, 94, 96, 98],
    [74, 77, 81, 85, 89, 92, 95, 97, 99, 101],
    [77, 80, 84, 88, 92, 95, 98, 100, 102, 104],
    [80, 83, 87, 91, 95, 98, 101, 103, 105, 107],
    [82, 85, 89, 93, 97, 100, 103, 105, 107, 109],
    [84, 87, 91, 95, 99, 102, 105, 107, 109, 111],
    [86, 89, 93, 97, 101, 104, 107, 109, 111, 113],
    [87, 90, 94, 98, 102, 105, 108, 110, 112, 114],
    [88, 91, 95, 99, 103, 106, 109, 111, 113, 115],
    [89, 92, 96, 100, 104, 107, 110, 112, 114, 116],
    [90, 93, 97, 101, 105, 108, 111, 113, 115, 117],
  ]),
  afrTargets: expandLegacyAfrTargets({
    20: 14.7,
    30: 14.7,
    40: 14.5,
    50: 14.0,
    60: 13.5,
    70: 13.0,
    80: 12.6,
    90: 12.3,
    100: 12.0,
    110: 11.7,
  }),
};

/**
 * All available engine presets
 */
export const ENGINE_PRESETS: Record<string, EnginePresetData> = {
  harley_m8: HARLEY_M8,
  harley_tc: HARLEY_TC,
  harley_tc_110: HARLEY_TC_110,
  harley_revmax_1250: HARLEY_REVMAX_1250,
  harley_revmax_975: HARLEY_REVMAX_975,
  sportbike_600: SPORTBIKE_600,
  sportbike_1000: SPORTBIKE_1000,
};

/**
 * Grid-only engine configurations (for LiveVETable)
 * Extracted from full presets for components that only need bins/maxRpm
 */
export const ENGINE_GRID_CONFIGS: Record<EnginePreset, EngineConfig> = {
  harley_m8: {
    name: "Harley M8",
    rpmBins: HARLEY_M8.rpmBins,
    mapBins: HARLEY_M8.mapBins,
    maxRpm: HARLEY_M8.maxRpm,
  },
  harley_tc: {
    name: "Harley Twin Cam",
    rpmBins: HARLEY_TC.rpmBins,
    mapBins: HARLEY_TC.mapBins,
    maxRpm: HARLEY_TC.maxRpm,
  },
  harley_tc_110: {
    name: "Harley Twin Cam 110",
    rpmBins: HARLEY_TC_110.rpmBins,
    mapBins: HARLEY_TC_110.mapBins,
    maxRpm: HARLEY_TC_110.maxRpm,
  },
  harley_revmax_1250: {
    name: "Harley RevMax 1250",
    rpmBins: HARLEY_REVMAX_1250.rpmBins,
    mapBins: HARLEY_REVMAX_1250.mapBins,
    maxRpm: HARLEY_REVMAX_1250.maxRpm,
  },
  harley_revmax_975: {
    name: "Harley RevMax 975",
    rpmBins: HARLEY_REVMAX_975.rpmBins,
    mapBins: HARLEY_REVMAX_975.mapBins,
    maxRpm: HARLEY_REVMAX_975.maxRpm,
  },
  sportbike_600: {
    name: "Sportbike 600cc",
    rpmBins: SPORTBIKE_600.rpmBins,
    mapBins: SPORTBIKE_600.mapBins,
    maxRpm: SPORTBIKE_600.maxRpm,
  },
  sportbike_1000: {
    name: "Sportbike 1000cc",
    rpmBins: SPORTBIKE_1000.rpmBins,
    mapBins: SPORTBIKE_1000.mapBins,
    maxRpm: SPORTBIKE_1000.maxRpm,
  },
  custom: {
    name: "Custom",
    rpmBins: [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000],
    mapBins: [...PVV_MAP_BINS],
    maxRpm: 10000,
  },
};

/**
 * Get preset by key
 */
export function getEnginePreset(key: string): EnginePresetData | undefined {
    return ENGINE_PRESETS[key];
}

/**
 * Get default AFR targets for a preset
 */
export function getPresetAfrTargets(presetKey: string): Record<number, number> {
    const preset = ENGINE_PRESETS[presetKey];
    return preset?.afrTargets ?? HARLEY_M8.afrTargets;
}

/**
 * Get default VE table for a preset
 */
export function getPresetVeTable(presetKey: string, cylinder: 'front' | 'rear' = 'front'): number[][] {
    const preset = ENGINE_PRESETS[presetKey];
    if (!preset) return HARLEY_M8.veTableFront;
    
    if (cylinder === 'rear' && preset.veTableRear) {
        return preset.veTableRear;
    }
    return preset.veTableFront;
}

/**
 * List all available presets for UI dropdown
 */
export function listEnginePresets(): { key: string; name: string; description: string }[] {
    return Object.entries(ENGINE_PRESETS).map(([key, preset]) => ({
        key,
        name: preset.name,
        description: preset.description,
    }));
}

/**
 * BikeConfig type import for preset conversion
 */
import type { BikeConfig, EngineType } from "../types/bikeConfig";

/**
 * Preset to bike configuration mapping
 * Maps engine preset keys to bike configuration defaults
 */
interface PresetBikeMapping {
    make: string;
    engineType: EngineType;
    cylinders: number;
    displacementUnit: 'cc' | 'ci';
    defaultDisplacement: number;
}

const PRESET_BIKE_MAPPINGS: Record<string, PresetBikeMapping> = {
  harley_m8: {
    make: "Harley-Davidson",
    engineType: "v-twin",
    cylinders: 2,
    displacementUnit: "ci",
    defaultDisplacement: 114,
  },
  harley_tc: {
    make: "Harley-Davidson",
    engineType: "v-twin",
    cylinders: 2,
    displacementUnit: "ci",
    defaultDisplacement: 103,
  },
  harley_tc_110: {
    make: "Harley-Davidson",
    engineType: "v-twin",
    cylinders: 2,
    displacementUnit: "ci",
    defaultDisplacement: 110,
  },
  harley_revmax_1250: {
    make: "Harley-Davidson",
    engineType: "v-twin",
    cylinders: 2,
    displacementUnit: "cc",
    defaultDisplacement: 1250,
  },
  harley_revmax_975: {
    make: "Harley-Davidson",
    engineType: "v-twin",
    cylinders: 2,
    displacementUnit: "cc",
    defaultDisplacement: 975,
  },
  sportbike_600: {
    make: "Honda",
    engineType: "inline-4",
    cylinders: 4,
    displacementUnit: "cc",
    defaultDisplacement: 600,
  },
  sportbike_1000: {
    make: "Honda",
    engineType: "inline-4",
    cylinders: 4,
    displacementUnit: "cc",
    defaultDisplacement: 1000,
  },
};

/**
 * Convert an engine preset to a BikeConfig object
 * 
 * @param presetKey - The engine preset key (e.g., 'harley_m8')
 * @returns BikeConfig object with preset defaults, or undefined if preset not found
 */
export function bikeConfigFromPreset(presetKey: string): BikeConfig | undefined {
    const preset = ENGINE_PRESETS[presetKey];
    const mapping = PRESET_BIKE_MAPPINGS[presetKey];
    
    if (!preset || !mapping) {
        return undefined;
    }

    const minRpm = Math.min(...preset.rpmBins);
    const maxRpm = preset.maxRpm;
    const minMap = Math.min(...preset.mapBins);
    const maxMap = Math.max(...preset.mapBins);

    return {
        make: mapping.make,
        model: '',
        year: new Date().getFullYear(),
        displacement: mapping.defaultDisplacement,
        displacementUnit: mapping.displacementUnit,
        engineType: mapping.engineType,
        cylinders: mapping.cylinders,
        rpmRange: { min: minRpm, max: maxRpm },
        mapRange: { min: minMap, max: maxMap },
        customRpmBins: preset.rpmBins,
        customMapBins: preset.mapBins,
    };
}

/**
 * Get the best matching preset key for a given bike configuration
 * 
 * @param config - BikeConfig to match
 * @returns The best matching preset key, or 'harley_m8' as default
 */
export function getPresetForBikeConfig(config: BikeConfig): string {
  // Match by engine type and displacement
  if (config.engineType === "v-twin") {
    if (config.make.toLowerCase().includes("harley")) {
      const ciDisplacement =
        config.displacementUnit === "ci"
          ? config.displacement
          : config.displacement / 16.387;

      // Newer large-displacement M8s.
      if (ciDisplacement >= 111) {
        return "harley_m8";
      }

      // 107-110ci can be either M8 or Twin Cam depending on year.
      if (ciDisplacement >= 107) {
        return config.year <= 2017 ? "harley_tc_110" : "harley_m8";
      }

      return "harley_tc";
    }
  }

  if (config.engineType === "inline-4") {
    const ccDisplacement =
      config.displacementUnit === "cc"
        ? config.displacement
        : config.displacement * 16.387;
    return ccDisplacement <= 750 ? "sportbike_600" : "sportbike_1000";
  }

  // Default fallback
  return "harley_m8";
}
