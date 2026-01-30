/**
 * Engine Presets - Default VE and AFR tables for common engine types
 * 
 * These serve as fallback values when no PVV file is available.
 * Based on typical factory tunes for each engine type.
 */

export interface EnginePresetData {
    name: string;
    description: string;
    rpmBins: number[];
    mapBins: number[];
    maxRpm: number;
    
    // Default VE table (Front cylinder, used for both if rear not specified)
    veTableFront: number[][];
    veTableRear?: number[][];  // Optional separate rear cylinder table
    
    // Default AFR targets by MAP (kPa -> AFR)
    afrTargets: Record<number, number>;
}

/**
 * Harley-Davidson Milwaukee-Eight (M8) Engine
 * 107/114/117/131 cubic inch variants
 */
const HARLEY_M8: EnginePresetData = {
    name: 'Harley M8',
    description: 'Milwaukee-Eight 107/114/117/131',
    rpmBins: [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500],
    mapBins: [20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
    maxRpm: 6500,
    
    // Typical M8 VE values (as percentages)
    veTableFront: [
        // MAP:  20    30    40    50    60    70    80    90   100   110
        [70,  72,  75,  78,  80,  82,  84,  86,  88,  90],  // 1000 RPM
        [72,  74,  77,  80,  83,  85,  87,  89,  91,  93],  // 1500 RPM
        [74,  76,  79,  82,  85,  88,  90,  92,  94,  96],  // 2000 RPM
        [76,  78,  81,  84,  87,  90,  92,  94,  96,  98],  // 2500 RPM
        [78,  80,  83,  86,  89,  92,  94,  96,  98, 100],  // 3000 RPM
        [80,  82,  85,  88,  91,  94,  96,  98, 100, 102],  // 3500 RPM
        [82,  84,  87,  90,  93,  96,  98, 100, 102, 104],  // 4000 RPM
        [84,  86,  89,  92,  95,  98, 100, 102, 104, 106],  // 4500 RPM
        [85,  87,  90,  93,  96,  99, 101, 103, 105, 107],  // 5000 RPM
        [86,  88,  91,  94,  97, 100, 102, 104, 106, 108],  // 5500 RPM
        [87,  89,  92,  95,  98, 101, 103, 105, 107, 109],  // 6000 RPM
        [88,  90,  93,  96,  99, 102, 104, 106, 108, 110],  // 6500 RPM
    ],
    
    // AFR targets - stoich at cruise, rich at WOT
    afrTargets: {
        20: 14.7,   // Light load - stoich
        30: 14.7,   // Cruise - stoich
        40: 14.5,   // Part throttle
        50: 14.0,   // Mid load
        60: 13.5,   // Higher load
        70: 13.0,   // Moderate power
        80: 12.8,   // Power
        90: 12.5,   // High power
        100: 12.2,  // WOT - rich for cooling
        110: 12.0,  // Boost/overrun
    },
};

/**
 * Harley-Davidson Twin Cam Engine
 * 88/96/103/110 cubic inch variants
 */
const HARLEY_TC: EnginePresetData = {
    name: 'Harley Twin Cam',
    description: 'Twin Cam 88/96/103/110',
    rpmBins: [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000],
    mapBins: [20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
    maxRpm: 6000,
    
    veTableFront: [
        // MAP:  20    30    40    50    60    70    80    90   100   110
        [68,  70,  73,  76,  79,  81,  83,  85,  87,  89],  // 1000 RPM
        [70,  72,  75,  78,  81,  83,  85,  87,  89,  91],  // 1500 RPM
        [72,  74,  77,  80,  83,  86,  88,  90,  92,  94],  // 2000 RPM
        [74,  76,  79,  82,  85,  88,  90,  92,  94,  96],  // 2500 RPM
        [76,  78,  81,  84,  87,  90,  92,  94,  96,  98],  // 3000 RPM
        [78,  80,  83,  86,  89,  92,  94,  96,  98, 100],  // 3500 RPM
        [80,  82,  85,  88,  91,  94,  96,  98, 100, 102],  // 4000 RPM
        [81,  83,  86,  89,  92,  95,  97,  99, 101, 103],  // 4500 RPM
        [82,  84,  87,  90,  93,  96,  98, 100, 102, 104],  // 5000 RPM
        [83,  85,  88,  91,  94,  97,  99, 101, 103, 105],  // 5500 RPM
        [84,  86,  89,  92,  95,  98, 100, 102, 104, 106],  // 6000 RPM
    ],
    
    afrTargets: {
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
    },
};

/**
 * 600cc Sportbike (generic)
 * Honda CBR600, Yamaha R6, Kawasaki ZX-6R, Suzuki GSX-R600
 */
const SPORTBIKE_600: EnginePresetData = {
    name: 'Sportbike 600cc',
    description: 'High-revving 600cc inline-4',
    rpmBins: [2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000],
    mapBins: [20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
    maxRpm: 15000,
    
    veTableFront: [
        // MAP:  20    30    40    50    60    70    80    90   100   110
        [65,  68,  72,  76,  80,  83,  86,  88,  90,  92],  // 2000 RPM
        [68,  71,  75,  79,  83,  86,  89,  91,  93,  95],  // 3000 RPM
        [71,  74,  78,  82,  86,  89,  92,  94,  96,  98],  // 4000 RPM
        [74,  77,  81,  85,  89,  92,  95,  97,  99, 101],  // 5000 RPM
        [77,  80,  84,  88,  92,  95,  98, 100, 102, 104],  // 6000 RPM
        [80,  83,  87,  91,  95,  98, 101, 103, 105, 107],  // 7000 RPM
        [82,  85,  89,  93,  97, 100, 103, 105, 107, 109],  // 8000 RPM
        [84,  87,  91,  95,  99, 102, 105, 107, 109, 111],  // 9000 RPM
        [86,  89,  93,  97, 101, 104, 107, 109, 111, 113],  // 10000 RPM
        [87,  90,  94,  98, 102, 105, 108, 110, 112, 114],  // 11000 RPM
        [88,  91,  95,  99, 103, 106, 109, 111, 113, 115],  // 12000 RPM
        [89,  92,  96, 100, 104, 107, 110, 112, 114, 116],  // 13000 RPM
        [90,  93,  97, 101, 105, 108, 111, 113, 115, 117],  // 14000 RPM
        [91,  94,  98, 102, 106, 109, 112, 114, 116, 118],  // 15000 RPM
    ],
    
    afrTargets: {
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
    },
};

/**
 * 1000cc Sportbike (generic)
 * Honda CBR1000, Yamaha R1, Kawasaki ZX-10R, Suzuki GSX-R1000
 */
const SPORTBIKE_1000: EnginePresetData = {
    name: 'Sportbike 1000cc',
    description: 'High-power 1000cc inline-4',
    rpmBins: [2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000],
    mapBins: [20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
    maxRpm: 13000,
    
    veTableFront: [
        // MAP:  20    30    40    50    60    70    80    90   100   110
        [68,  71,  75,  79,  83,  86,  89,  91,  93,  95],  // 2000 RPM
        [71,  74,  78,  82,  86,  89,  92,  94,  96,  98],  // 3000 RPM
        [74,  77,  81,  85,  89,  92,  95,  97,  99, 101],  // 4000 RPM
        [77,  80,  84,  88,  92,  95,  98, 100, 102, 104],  // 5000 RPM
        [80,  83,  87,  91,  95,  98, 101, 103, 105, 107],  // 6000 RPM
        [82,  85,  89,  93,  97, 100, 103, 105, 107, 109],  // 7000 RPM
        [84,  87,  91,  95,  99, 102, 105, 107, 109, 111],  // 8000 RPM
        [86,  89,  93,  97, 101, 104, 107, 109, 111, 113],  // 9000 RPM
        [87,  90,  94,  98, 102, 105, 108, 110, 112, 114],  // 10000 RPM
        [88,  91,  95,  99, 103, 106, 109, 111, 113, 115],  // 11000 RPM
        [89,  92,  96, 100, 104, 107, 110, 112, 114, 116],  // 12000 RPM
        [90,  93,  97, 101, 105, 108, 111, 113, 115, 117],  // 13000 RPM
    ],
    
    afrTargets: {
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
    },
};

/**
 * All available engine presets
 */
export const ENGINE_PRESETS: Record<string, EnginePresetData> = {
    harley_m8: HARLEY_M8,
    harley_tc: HARLEY_TC,
    sportbike_600: SPORTBIKE_600,
    sportbike_1000: SPORTBIKE_1000,
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
