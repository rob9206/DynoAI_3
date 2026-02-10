/**
 * Engine Presets - Default VE and AFR tables for common engine types
 * 
 * These serve as fallback values when no PVV file is available.
 * Based on typical factory tunes for each engine type.
 */

// Grid-only configuration for LiveVETable (no VE/AFR data)
export type EnginePreset = 'harley_m8' | 'harley_tc' | 'harley_revmax_1250' | 'harley_revmax_975' | 'sportbike_600' | 'sportbike_1000' | 'custom';

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
    veTableRear?: number[][];  // Optional separate rear cylinder table
    
    // Default AFR targets by MAP (kPa -> AFR)
    afrTargets: Record<number, number>;
}

// Rounded integer form of PVV ECU MAP bins (17 columns)
const PVV_MAP_BINS: number[] = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 85, 95, 105];

/**
 * Harley-Davidson Milwaukee-Eight (M8) Engine
 * 107/114/117/131 cubic inch variants
 */
const HARLEY_M8: EnginePresetData = {
    name: 'Harley M8',
    description: 'Milwaukee-Eight 107/114/117/131',
    rpmBins: [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500],
    mapBins: [...PVV_MAP_BINS],
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
    mapBins: [...PVV_MAP_BINS],
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
 * Harley-Davidson Revolution Max 1250 (Sportster S / Pan America)
 * Liquid-cooled DOHC V-twin, 1252 cc, redline 9500
 */
const HARLEY_REVMAX_1250: EnginePresetData = {
    name: 'Harley RevMax 1250',
    description: 'Revolution Max 1250 (Sportster S / Pan America)',
    rpmBins: [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000],
    mapBins: [...PVV_MAP_BINS],
    maxRpm: 9500,
    veTableFront: [
        [72, 74, 77, 80, 83, 86, 88, 90, 92, 94],
        [74, 76, 79, 82, 85, 88, 91, 93, 95, 97],
        [76, 78, 81, 84, 87, 90, 93, 95, 97, 99],
        [78, 80, 83, 86, 89, 92, 95, 97, 99, 101],
        [80, 82, 85, 88, 91, 94, 97, 99, 101, 103],
        [82, 84, 87, 90, 93, 96, 99, 101, 103, 105],
        [84, 86, 89, 92, 95, 98, 101, 103, 105, 107],
        [85, 87, 90, 93, 96, 99, 102, 104, 106, 108],
        [86, 88, 91, 94, 97, 100, 103, 105, 107, 109],
    ],
    afrTargets: {
        20: 14.7, 30: 14.7, 40: 14.5, 50: 14.0, 60: 13.5, 70: 13.0, 80: 12.6, 90: 12.3, 100: 12.2, 110: 12.0,
    },
};

/**
 * Harley-Davidson Revolution Max 975T (Nightster)
 * Liquid-cooled DOHC V-twin, 975 cc, redline 9000
 */
const HARLEY_REVMAX_975: EnginePresetData = {
    name: 'Harley RevMax 975',
    description: 'Revolution Max 975T (Nightster)',
    rpmBins: [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000],
    mapBins: [...PVV_MAP_BINS],
    maxRpm: 9000,
    veTableFront: [
        [71, 73, 76, 79, 82, 85, 87, 89, 91, 93],
        [73, 75, 78, 81, 84, 87, 90, 92, 94, 96],
        [75, 77, 80, 83, 86, 89, 92, 94, 96, 98],
        [77, 79, 82, 85, 88, 91, 94, 96, 98, 100],
        [79, 81, 84, 87, 90, 93, 96, 98, 100, 102],
        [81, 83, 86, 89, 92, 95, 98, 100, 102, 104],
        [82, 84, 87, 90, 93, 96, 99, 101, 103, 105],
        [83, 85, 88, 91, 94, 97, 100, 102, 104, 106],
    ],
    afrTargets: {
        20: 14.7, 30: 14.7, 40: 14.5, 50: 14.0, 60: 13.5, 70: 13.0, 80: 12.6, 90: 12.3, 100: 12.2, 110: 12.0,
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
    mapBins: [...PVV_MAP_BINS],
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
    mapBins: [...PVV_MAP_BINS],
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
        name: 'Harley M8',
        rpmBins: HARLEY_M8.rpmBins,
        mapBins: HARLEY_M8.mapBins,
        maxRpm: HARLEY_M8.maxRpm,
    },
    harley_tc: {
        name: 'Harley Twin Cam',
        rpmBins: HARLEY_TC.rpmBins,
        mapBins: HARLEY_TC.mapBins,
        maxRpm: HARLEY_TC.maxRpm,
    },
    harley_revmax_1250: {
        name: 'Harley RevMax 1250',
        rpmBins: HARLEY_REVMAX_1250.rpmBins,
        mapBins: HARLEY_REVMAX_1250.mapBins,
        maxRpm: HARLEY_REVMAX_1250.maxRpm,
    },
    harley_revmax_975: {
        name: 'Harley RevMax 975',
        rpmBins: HARLEY_REVMAX_975.rpmBins,
        mapBins: HARLEY_REVMAX_975.mapBins,
        maxRpm: HARLEY_REVMAX_975.maxRpm,
    },
    sportbike_600: {
        name: 'Sportbike 600cc',
        rpmBins: SPORTBIKE_600.rpmBins,
        mapBins: SPORTBIKE_600.mapBins,
        maxRpm: SPORTBIKE_600.maxRpm,
    },
    sportbike_1000: {
        name: 'Sportbike 1000cc',
        rpmBins: SPORTBIKE_1000.rpmBins,
        mapBins: SPORTBIKE_1000.mapBins,
        maxRpm: SPORTBIKE_1000.maxRpm,
    },
    custom: {
        name: 'Custom',
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
import type { BikeConfig, EngineType } from '../types/bikeConfig';

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
        make: 'Harley-Davidson',
        engineType: 'v-twin',
        cylinders: 2,
        displacementUnit: 'ci',
        defaultDisplacement: 114,
    },
    harley_tc: {
        make: 'Harley-Davidson',
        engineType: 'v-twin',
        cylinders: 2,
        displacementUnit: 'ci',
        defaultDisplacement: 103,
    },
    harley_revmax_1250: {
        make: 'Harley-Davidson',
        engineType: 'v-twin',
        cylinders: 2,
        displacementUnit: 'cc',
        defaultDisplacement: 1250,
    },
    harley_revmax_975: {
        make: 'Harley-Davidson',
        engineType: 'v-twin',
        cylinders: 2,
        displacementUnit: 'cc',
        defaultDisplacement: 975,
    },
    sportbike_600: {
        make: 'Honda',
        engineType: 'inline-4',
        cylinders: 4,
        displacementUnit: 'cc',
        defaultDisplacement: 600,
    },
    sportbike_1000: {
        make: 'Honda',
        engineType: 'inline-4',
        cylinders: 4,
        displacementUnit: 'cc',
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
    if (config.engineType === 'v-twin') {
        if (config.make.toLowerCase().includes('harley')) {
            // Check displacement to differentiate M8 vs TC
            const ciDisplacement = config.displacementUnit === 'ci' 
                ? config.displacement 
                : config.displacement / 16.387;
            
            // M8 engines are typically 107+ ci
            return ciDisplacement >= 107 ? 'harley_m8' : 'harley_tc';
        }
    }
    
    if (config.engineType === 'inline-4') {
        const ccDisplacement = config.displacementUnit === 'cc'
            ? config.displacement
            : config.displacement * 16.387;
        
        return ccDisplacement <= 750 ? 'sportbike_600' : 'sportbike_1000';
    }
    
    // Default fallback
    return 'harley_m8';
}
