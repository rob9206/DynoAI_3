/**
 * PVV Parser - Extract VE and AFR tables from Power Vision XML files
 * 
 * Power Vision exports tune data as .pvv files (XML format).
 * This parser extracts:
 * - VE (MAP based/Front Cyl) - Front cylinder volumetric efficiency table
 * - VE (MAP based/Rear Cyl) - Rear cylinder volumetric efficiency table
 * - Air-Fuel Ratio - Target AFR table
 * 
 * Tables are 2D grids with:
 * - Columns: MAP bins (Kilopascals)
 * - Rows: RPM bins (RPMx1000)
 */

export interface PVVTable {
    name: string;
    units: string;
    columnUnits: string;
    rowUnits: string;
    columns: number[];      // MAP bins (normalized to kPa)
    rows: number[];         // RPM bins (in actual RPM, not x1000)
    values: number[][];     // [rowIdx][colIdx]
    /** Original column values before unit normalization (e.g. inHg). */
    originalColumns?: number[];
    /** The detected source unit for columns before normalization. */
    sourceColumnUnit?: 'kpa' | 'inhg' | 'unknown';
}

/** Engine family values we can infer from PVV displacement (for V3 session config). */
export const PVV_ENGINE_FAMILY_MAP: Record<number, string> = {
    107: "m8_107",
    110: "m8_107",  // common alias / rounded
    114: "m8_114",
    117: "m8_117",
    131: "m8_131",
    59: "revmax_975",   // 59.5 ci
    60: "revmax_975",
    76: "revmax_1250",  // 76.4 ci
    77: "revmax_1250",
    975: "revmax_975",   // PVV may report cc (Nightster)
    1250: "revmax_1250", // PVV may report cc (Sportster S / Pan America)
    1252: "revmax_1250",
};

export interface ParsedPVV {
    sourceFile?: string;
    veFront?: PVVTable;
    veRear?: PVVTable;
    afrTarget?: PVVTable;
    warmupEnrichment?: PVVTable;
    engineTempEntryF?: number;
    engineTempExitF?: number;
    entryTimeS?: number;
    /** Engine displacement from PVV "Engine Displacement" item (CID). */
    engineDisplacementCid?: number;
    /** Calibration/part number from PVV "Calibration ID" item (ASCII). */
    calibrationId?: string;
    /** Suggested V3 engine_family from displacement, if known. */
    inferredEngineFamily?: string;
    allTables: Map<string, PVVTable>;
    parseErrors: string[];
    /** Structured validation warnings by category */
    validationWarnings?: {
        grid?: string[];
        values?: string[];
        bins?: string[];
        quality?: string[];
        comparison?: string[];
    };
    /** Table selection scores for debugging */
    tableScores?: Map<string, number>;
}

// Validation result interfaces
interface GridValidation {
    isValid: boolean;
    warnings: string[];
}

interface ValueValidation {
    isValid: boolean;
    warnings: string[];
    outliers: Array<{rpm: number, map: number, value: number}>;
}

interface BinValidation {
    isValid: boolean;
    warnings: string[];
    duplicates: number[];
}

interface QualityCheck {
    hasNaN: boolean;
    hasInfinity: boolean;
    hasNegative: boolean;
    zeroPercent: number;
    warnings: string[];
}

interface VECandidate {
    table: PVVTable;
    score: number;
    reasons: string[];
}

// ============================================================================
// Validation Functions
// ============================================================================

/**
 * Validate grid dimensions for a PVV table
 */
function validateGridDimensions(table: PVVTable): GridValidation {
    const warnings: string[] = [];
    const rows = table.rows.length;
    const cols = table.columns.length;
    
    // Check minimum grid size
    if (rows < 5 || cols < 5) {
        warnings.push(`Grid too small: ${rows}×${cols}. Minimum recommended: 5×5`);
    }
    
    // Check maximum grid size
    if (rows > 50 || cols > 50) {
        warnings.push(`Grid unusually large: ${rows}×${cols}. May cause performance issues.`);
    }
    
    // Check if rectangular
    const allRowsSameLength = table.values.every(row => row.length === cols);
    if (!allRowsSameLength) {
        warnings.push(`Grid is not rectangular. Some rows have inconsistent column counts.`);
    }
    
    // Common Harley ECU patterns (17 MAP bins × 21 RPM bins is typical)
    const isCommonPattern = (rows === 21 && cols === 17) || 
                           (rows === 27 && cols === 17) ||
                           (rows === 13 && cols === 13);
    if (!isCommonPattern && rows > 10 && cols > 10) {
        warnings.push(`Uncommon grid size: ${rows}×${cols}. Expected patterns: 21×17, 27×17, or 13×13`);
    }
    
    return { isValid: warnings.length === 0, warnings };
}

/**
 * Validate VE values are within reasonable range
 */
function validateVEValues(table: PVVTable): ValueValidation {
    const warnings: string[] = [];
    const outliers: Array<{rpm: number, map: number, value: number}> = [];
    
    // Based on gp_surrogate.py: VE range 35-135% is reasonable
    const MIN_VE = 35;
    const MAX_VE = 135;
    const WARN_MIN_VE = 50;  // Warn below this
    const WARN_MAX_VE = 120; // Warn above this
    
    let minVE = Infinity;
    let maxVE = -Infinity;
    let invalidCount = 0;
    
    table.values.forEach((row, rIdx) => {
        row.forEach((value, cIdx) => {
            if (!Number.isFinite(value)) {
                invalidCount++;
                return;
            }
            
            minVE = Math.min(minVE, value);
            maxVE = Math.max(maxVE, value);
            
            // Track extreme outliers
            if (value < MIN_VE || value > MAX_VE) {
                outliers.push({
                    rpm: table.rows[rIdx],
                    map: table.columns[cIdx],
                    value
                });
            }
        });
    });
    
    if (invalidCount > 0) {
        warnings.push(`Found ${invalidCount} invalid/NaN VE values`);
    }
    
    if (minVE < WARN_MIN_VE) {
        warnings.push(`Unusually low VE values detected (min: ${minVE.toFixed(1)}%). Normal range: 50-120%`);
    }
    
    if (maxVE > WARN_MAX_VE) {
        warnings.push(`Unusually high VE values detected (max: ${maxVE.toFixed(1)}%). Normal range: 50-120%`);
    }
    
    if (outliers.length > 0) {
        warnings.push(`${outliers.length} VE values outside safe range (35-135%). May indicate data corruption.`);
    }
    
    return { isValid: warnings.length === 0, warnings, outliers };
}

/**
 * Validate AFR values are within reasonable range
 */
function validateAFRValues(table: PVVTable): ValueValidation {
    const warnings: string[] = [];
    const outliers: Array<{rpm: number, map: number, value: number}> = [];
    
    // Based on physics_constraints.py: AFR 11.0-16.0 is reasonable, 12.2-13.2 for WOT
    const MIN_AFR = 11.0;
    const MAX_AFR = 16.0;
    const WARN_MIN_AFR = 11.5;
    const WARN_MAX_AFR = 15.0;
    
    let minAFR = Infinity;
    let maxAFR = -Infinity;
    
    table.values.forEach((row, rIdx) => {
        row.forEach((value, cIdx) => {
            if (!Number.isFinite(value)) return;
            
            minAFR = Math.min(minAFR, value);
            maxAFR = Math.max(maxAFR, value);
            
            if (value < MIN_AFR || value > MAX_AFR) {
                outliers.push({
                    rpm: table.rows[rIdx],
                    map: table.columns[cIdx],
                    value
                });
            }
        });
    });
    
    if (minAFR < WARN_MIN_AFR) {
        warnings.push(`Very rich AFR detected (min: ${minAFR.toFixed(1)}). Below ${WARN_MIN_AFR} may cause fouling.`);
    }
    
    if (maxAFR > WARN_MAX_AFR) {
        warnings.push(`Very lean AFR detected (max: ${maxAFR.toFixed(1)}). Above ${WARN_MAX_AFR} may cause overheating.`);
    }
    
    if (outliers.length > 0) {
        warnings.push(`${outliers.length} AFR values outside safe range (${MIN_AFR}-${MAX_AFR})`);
    }
    
    return { isValid: warnings.length === 0, warnings, outliers };
}

/**
 * Validate bin values are in ascending order
 */
function validateBinMonotonicity(bins: number[], binType: 'RPM' | 'MAP'): BinValidation {
    const warnings: string[] = [];
    const duplicates: number[] = [];
    
    // Check ascending order
    for (let i = 0; i < bins.length - 1; i++) {
        if (bins[i] >= bins[i + 1]) {
            if (bins[i] === bins[i + 1]) {
                duplicates.push(bins[i]);
            } else {
                warnings.push(`${binType} bins not in ascending order at index ${i}: ${bins[i]} >= ${bins[i + 1]}`);
            }
        }
    }
    
    if (duplicates.length > 0) {
        warnings.push(`${binType} has ${duplicates.length} duplicate values: ${duplicates.slice(0, 5).join(', ')}${duplicates.length > 5 ? '...' : ''}`);
    }
    
    // Check for unusual gaps
    const gaps: number[] = [];
    for (let i = 0; i < bins.length - 1; i++) {
        gaps.push(bins[i + 1] - bins[i]);
    }
    const avgGap = gaps.reduce((a, b) => a + b, 0) / gaps.length;
    const largeGaps = gaps.filter(g => g > avgGap * 3);
    
    if (largeGaps.length > 0) {
        warnings.push(`${binType} has ${largeGaps.length} unusually large gaps (>3× average spacing)`);
    }
    
    return { isValid: warnings.length === 0, warnings, duplicates };
}

/**
 * Score a VE table for smart selection when multiple candidates exist
 */
function scoreVETable(table: PVVTable): VECandidate {
    const nameLower = table.name.toLowerCase();
    let score = 0;
    const reasons: string[] = [];
    
    // Prefer MAP-based (highest priority)
    const isMapBased = nameLower.includes('map') || 
                      table.columnUnits.toLowerCase().includes('kilopascal');
    const isTpsBased = nameLower.includes('tps') || table.columnUnits === '%';
    
    if (isMapBased) {
        score += 100;
        reasons.push('MAP-based (preferred)');
    } else if (isTpsBased) {
        score -= 50;
        reasons.push('TPS-based (not preferred)');
    }
    
    // Prefer larger grids (more resolution)
    const gridSize = table.rows.length * table.columns.length;
    if (gridSize > 300) {
        score += 20;
        reasons.push('High resolution grid');
    } else if (gridSize < 100) {
        score -= 10;
        reasons.push('Low resolution grid');
    }
    
    // Prefer tables with variance (actually tuned vs stock/zeros)
    const allValues = table.values.flat();
    const mean = allValues.reduce((a, b) => a + b, 0) / allValues.length;
    const variance = allValues.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / allValues.length;
    const stdDev = Math.sqrt(variance);
    
    if (stdDev > 10) {
        score += 10;
        reasons.push('Has variance (tuned)');
    } else if (stdDev < 2) {
        score -= 20;
        reasons.push('Low variance (may be stock/untuned)');
    }
    
    // Check for mostly zeros
    const zeroCount = allValues.filter(v => v === 0).length;
    const zeroPercent = (zeroCount / allValues.length) * 100;
    if (zeroPercent > 50) {
        score -= 30;
        reasons.push(`${zeroPercent.toFixed(0)}% zeros (suspicious)`);
    }
    
    return { table, score, reasons };
}

/**
 * Check data quality of a table
 */
function checkDataQuality(table: PVVTable, expectedRange: [number, number]): QualityCheck {
    const warnings: string[] = [];
    let nanCount = 0;
    let infCount = 0;
    let negCount = 0;
    let zeroCount = 0;
    let totalCells = 0;
    
    table.values.forEach(row => {
        row.forEach(value => {
            totalCells++;
            if (Number.isNaN(value)) nanCount++;
            else if (!Number.isFinite(value)) infCount++;
            else if (value < 0) negCount++;
            else if (value === 0) zeroCount++;
        });
    });
    
    const zeroPercent = (zeroCount / totalCells) * 100;
    
    if (nanCount > 0) {
        warnings.push(`Table contains ${nanCount} NaN values`);
    }
    if (infCount > 0) {
        warnings.push(`Table contains ${infCount} Infinity values`);
    }
    if (negCount > 0) {
        warnings.push(`Table contains ${negCount} negative values (unexpected for VE/AFR)`);
    }
    if (zeroPercent > 20) {
        warnings.push(`${zeroPercent.toFixed(1)}% of cells are zero (may indicate incomplete tune)`);
    }
    
    return {
        hasNaN: nanCount > 0,
        hasInfinity: infCount > 0,
        hasNegative: negCount > 0,
        zeroPercent,
        warnings
    };
}

/**
 * Compare front and rear VE tables for suspicious differences
 */
function compareFrontRearTables(front: PVVTable, rear: PVVTable): string[] {
    const warnings: string[] = [];
    
    // Check if same dimensions
    if (front.rows.length !== rear.rows.length || 
        front.columns.length !== rear.columns.length) {
        warnings.push('Front and rear VE tables have different dimensions');
        return warnings;
    }
    
    // Calculate average difference
    let sumDiff = 0;
    let maxDiff = 0;
    let cellCount = 0;
    
    front.values.forEach((row, rIdx) => {
        row.forEach((fVal, cIdx) => {
            const rVal = rear.values[rIdx]?.[cIdx];
            if (rVal !== undefined && Number.isFinite(fVal) && Number.isFinite(rVal)) {
                const diff = Math.abs(fVal - rVal);
                sumDiff += diff;
                maxDiff = Math.max(maxDiff, diff);
                cellCount++;
            }
        });
    });
    
    const avgDiff = sumDiff / cellCount;
    
    // Warn if tables are very different (may indicate wrong tables selected)
    if (avgDiff > 15) {
        warnings.push(`Front/rear VE tables differ significantly (avg: ${avgDiff.toFixed(1)}%). Verify correct tables selected.`);
    }
    
    // Warn if tables are identical (suspicious for V-twin)
    if (avgDiff < 0.5 && maxDiff < 1) {
        warnings.push('Front and rear VE tables are nearly identical (unusual for V-twin)');
    }
    
    return warnings;
}

// ============================================================================
// Main Parser
// ============================================================================

/**
 * Parse a Power Vision PVV XML file
 */
export function parsePVV(xmlContent: string): ParsedPVV {
    const result: ParsedPVV = {
        allTables: new Map(),
        parseErrors: [],
        validationWarnings: {
            grid: [],
            values: [],
            bins: [],
            quality: [],
            comparison: [],
        },
        tableScores: new Map(),
    };

    try {
        const parser = new DOMParser();
        const doc = parser.parseFromString(xmlContent, 'application/xml');

        // Check for parse errors
        const parseError = doc.querySelector('parsererror');
        if (parseError) {
            result.parseErrors.push(`XML parse error: ${parseError.textContent}`);
            return result;
        }

        // Extract source file from comment if present
        const comments = xmlContent.match(/<!--Source File Name: "([^"]+)"-->/);
        if (comments) {
            result.sourceFile = comments[1];
        }

        // Find all Item elements
        const items = doc.querySelectorAll('Item');
        
        // Candidate VE tables (may need second-pass assignment)
        const veCandidates: PVVTable[] = [];
        
        for (const item of items) {
            try {
                const table = parseTableItem(item);
                if (table) {
                    result.allTables.set(table.name, table);

                    // Engine metadata from PVV (for V3 / motor selection)
                    if (table.name === "Engine Displacement" && table.values[0]?.[0] != null) {
                        const cid = Math.round(table.values[0][0]);
                        result.engineDisplacementCid = cid;
                        result.inferredEngineFamily = PVV_ENGINE_FAMILY_MAP[cid];
                    }
                    if (table.name === "Warmup Enrichment") {
                        result.warmupEnrichment = table;
                    }
                    if (table.name === "Engine Temp Entry" && table.values[0]?.[0] != null) {
                        result.engineTempEntryF = table.values[0][0];
                    }
                    if (table.name === "Engine Temp Exit" && table.values[0]?.[0] != null) {
                        result.engineTempExitF = table.values[0][0];
                    }
                    if (table.name === "Entry Time" && table.values[0]?.[0] != null) {
                        result.entryTimeS = table.values[0][0];
                    }
                    if (table.name === "Calibration ID" && table.values[0]?.length) {
                        result.calibrationId = table.values[0]
                            .map((v) => String.fromCharCode(Math.round(v)))
                            .join("")
                            .replace(/\0/g, "");
                    }

                    // Identify key tables by name patterns
                    const nameLower = table.name.toLowerCase();
                    
                    // Front VE table - prefer MAP-based over TPS-based
                    if (nameLower.includes('ve') && nameLower.includes('front')) {
                        // Prefer MAP-based tables (check both name and column units)
                        const isMapBased = nameLower.includes('map') || 
                                          table.columnUnits.toLowerCase().includes('kilopascal');
                        const isTpsBased = nameLower.includes('tps') || 
                                          table.columnUnits === '%';
                        
                        if (isMapBased || (!isTpsBased && !result.veFront)) {
                            result.veFront = table;
                        }
                    }
                    // Rear VE table - prefer MAP-based over TPS-based
                    else if (nameLower.includes('ve') && nameLower.includes('rear')) {
                        const isMapBased = nameLower.includes('map') || 
                                          table.columnUnits.toLowerCase().includes('kilopascal');
                        const isTpsBased = nameLower.includes('tps') || 
                                          table.columnUnits === '%';
                        
                        if (isMapBased || (!isTpsBased && !result.veRear)) {
                            result.veRear = table;
                        }
                    }
                    // AFR target table
                    else if (nameLower === 'air-fuel ratio' || nameLower === 'air fuel ratio' || 
                             (nameLower.includes('afr') && nameLower.includes('target'))) {
                        result.afrTarget = table;
                    }
                    // Generic VE table (no front/rear designation) - collect as candidate
                    else if (nameLower.includes('ve') && !nameLower.includes('afr') && !nameLower.includes('error')) {
                        veCandidates.push(table);
                    }
                }
            } catch (e) {
                result.parseErrors.push(`Error parsing item: ${e}`);
            }
        }
        
        // Second pass: if we didn't find explicit front/rear VE tables,
        // use candidate VE tables (e.g. DynoAI correction output, single-table PVVs)
        if (!result.veFront && !result.veRear && veCandidates.length > 0) {
            // Use the first VE candidate for both front and rear
            // (DynoAI outputs a single combined table; real PVV files have front/rear)
            result.veFront = veCandidates[0];
            result.veRear = veCandidates.length > 1 ? veCandidates[1] : veCandidates[0];
        } else if (!result.veFront && veCandidates.length > 0) {
            result.veFront = veCandidates[0];
        } else if (!result.veRear && veCandidates.length > 0) {
            result.veRear = veCandidates[0];
        }
        
        // Validate we got MAP-based tables, not TPS-based
        if (result.veFront) {
            const frontName = result.veFront.name.toLowerCase();
            if (frontName.includes('tps')) {
                result.parseErrors.push(
                    'Warning: Using TPS-based VE table. MAP-based table not found. ' +
                    'TPS-based tables use throttle position (%) instead of MAP (kPa).'
                );
            }
            // Log what we selected for debugging
            console.log('[pvvParser] Selected VE Front table:', result.veFront.name);
            
            // Validate front VE table
            const gridVal = validateGridDimensions(result.veFront);
            result.validationWarnings.grid?.push(...gridVal.warnings);
            
            const binValRpm = validateBinMonotonicity(result.veFront.rows, 'RPM');
            const binValMap = validateBinMonotonicity(result.veFront.columns, 'MAP');
            result.validationWarnings.bins?.push(...binValRpm.warnings, ...binValMap.warnings);
            
            const valueVal = validateVEValues(result.veFront);
            result.validationWarnings.values?.push(...valueVal.warnings);
            
            const qualityVal = checkDataQuality(result.veFront, [35, 135]);
            result.validationWarnings.quality?.push(...qualityVal.warnings);
        }

        if (result.veRear) {
            const rearName = result.veRear.name.toLowerCase();
            if (rearName.includes('tps')) {
                result.parseErrors.push(
                    'Warning: Using TPS-based VE table (rear). MAP-based table not found.'
                );
            }
            console.log('[pvvParser] Selected VE Rear table:', result.veRear.name);
            
            // Validate rear VE table
            const gridVal = validateGridDimensions(result.veRear);
            result.validationWarnings.grid?.push(...gridVal.warnings);
            
            const binValRpm = validateBinMonotonicity(result.veRear.rows, 'RPM');
            const binValMap = validateBinMonotonicity(result.veRear.columns, 'MAP');
            result.validationWarnings.bins?.push(...binValRpm.warnings, ...binValMap.warnings);
            
            const valueVal = validateVEValues(result.veRear);
            result.validationWarnings.values?.push(...valueVal.warnings);
            
            const qualityVal = checkDataQuality(result.veRear, [35, 135]);
            result.validationWarnings.quality?.push(...qualityVal.warnings);
        }
        
        // Compare front and rear tables if both exist
        if (result.veFront && result.veRear) {
            const comparisonWarnings = compareFrontRearTables(result.veFront, result.veRear);
            result.validationWarnings.comparison?.push(...comparisonWarnings);
        }
        
        // Validate AFR table if present
        if (result.afrTarget) {
            const gridVal = validateGridDimensions(result.afrTarget);
            result.validationWarnings.grid?.push(...gridVal.warnings);
            
            const binValRpm = validateBinMonotonicity(result.afrTarget.rows, 'RPM');
            const binValMap = validateBinMonotonicity(result.afrTarget.columns, 'MAP');
            result.validationWarnings.bins?.push(...binValRpm.warnings, ...binValMap.warnings);
            
            const valueVal = validateAFRValues(result.afrTarget);
            result.validationWarnings.values?.push(...valueVal.warnings);
            
            const qualityVal = checkDataQuality(result.afrTarget, [11, 16]);
            result.validationWarnings.quality?.push(...qualityVal.warnings);
        }
        
        // Collect all validation warnings into parseErrors for backwards compatibility
        const allValidationWarnings = [
            ...(result.validationWarnings.grid || []),
            ...(result.validationWarnings.values || []),
            ...(result.validationWarnings.bins || []),
            ...(result.validationWarnings.quality || []),
            ...(result.validationWarnings.comparison || []),
        ];
        result.parseErrors.push(...allValidationWarnings);

    } catch (e) {
        result.parseErrors.push(`Failed to parse PVV: ${e}`);
    }

    return result;
}

export const INHG_TO_KPA = 3.38639;

export function normalizeMapColumns(
    rawColumns: number[],
    columnUnits: string,
): { columns: number[]; originalColumns: number[]; sourceUnit: 'kpa' | 'inhg' | 'unknown' } {
    const unitLower = columnUnits.toLowerCase().replace(/\s+/g, '');
    const isInhg =
        unitLower.includes('inchesofmercury') ||
        unitLower.includes('inhg') ||
        unitLower.includes('in-hg') ||
        unitLower.includes('inches_of_mercury');
    const isKpa =
        unitLower.includes('kpa') ||
        unitLower.includes('kilopascal');

    if (isInhg) {
        return {
            columns: rawColumns.map((v) => Math.round(v * INHG_TO_KPA * 10) / 10),
            originalColumns: [...rawColumns],
            sourceUnit: 'inhg',
        };
    }
    if (isKpa) {
        return { columns: [...rawColumns], originalColumns: [...rawColumns], sourceUnit: 'kpa' };
    }
    // Heuristic: if max value <= 35, likely inHg (MAP vacuum range)
    const maxVal = rawColumns.length > 0 ? Math.max(...rawColumns) : 0;
    if (maxVal > 0 && maxVal <= 35) {
        return {
            columns: rawColumns.map((v) => Math.round(v * INHG_TO_KPA * 10) / 10),
            originalColumns: [...rawColumns],
            sourceUnit: 'inhg',
        };
    }
    return { columns: [...rawColumns], originalColumns: [...rawColumns], sourceUnit: 'unknown' };
}

/**
 * Parse a single Item element into a PVVTable
 */
function parseTableItem(item: Element): PVVTable | null {
    const name = item.getAttribute('name');
    const units = item.getAttribute('units') || '';
    
    if (!name) return null;

    const columnsEl = item.querySelector('Columns');
    const rowsEl = item.querySelector('Rows');
    
    if (!columnsEl || !rowsEl) return null;

    const columnUnits = columnsEl.getAttribute('units') || '';
    const rowUnits = rowsEl.getAttribute('units') || '';

    // Parse column labels (MAP bins)
    const colEls = columnsEl.querySelectorAll('Col');
    const columns: number[] = [];
    for (const col of colEls) {
        const label = col.getAttribute('label');
        if (label) {
            columns.push(parseFloat(label));
        }
    }

    // Parse rows and cell values
    const rowEls = rowsEl.querySelectorAll('Row');
    const rows: number[] = [];
    const values: number[][] = [];

    for (const row of rowEls) {
        const label = row.getAttribute('label');
        if (label) {
            // Convert RPMx1000 to actual RPM if needed
            let rpmValue = parseFloat(label);
            if (rowUnits.toLowerCase().includes('rpmx1000') || rowUnits.toLowerCase().includes('rpm x 1000')) {
                rpmValue *= 1000;
            }
            rows.push(rpmValue);

            // Parse cell values (Power Vision may use attribute "value" or text content)
            const cellEls = row.querySelectorAll('Cell');
            const rowValues: number[] = [];
            for (const cell of cellEls) {
                const value = cell.getAttribute('value') ?? cell.textContent?.trim() ?? '';
                const num = value ? parseFloat(value) : NaN;
                rowValues.push(Number.isFinite(num) ? num : 0);
            }
            values.push(rowValues);
        }
    }

    const normalized = normalizeMapColumns(columns, columnUnits);

    const table: PVVTable = {
        name,
        units,
        columnUnits,
        rowUnits,
        columns: normalized.columns,
        rows,
        values,
        originalColumns: normalized.originalColumns,
        sourceColumnUnit: normalized.sourceUnit,
    };
    
    if (name.toLowerCase().includes('ve') && name.toLowerCase().includes('front')) {
        console.log('[pvvParser] Parsed VE Front table:', {
            name,
            rowsCount: rows.length,
            columnsCount: normalized.columns.length,
            sourceUnit: normalized.sourceUnit,
            columnsSample: normalized.columns.slice(0, 5),
            originalColumnsSample: normalized.originalColumns.slice(0, 5),
            valuesShape: `${values.length}x${values[0]?.length}`,
        });
    }
    
    return table;
}

/**
 * Convert a PVVTable to a simple 2D grid for use in the app
 * Interpolates/maps to standard bins if needed
 */
export function tableToGrid(
    table: PVVTable,
    targetRpmBins: number[],
    targetMapBins: number[]
): number[][] {
    const grid: number[][] = targetRpmBins.map(() => targetMapBins.map(() => 0));

    for (let rpmIdx = 0; rpmIdx < targetRpmBins.length; rpmIdx++) {
        for (let mapIdx = 0; mapIdx < targetMapBins.length; mapIdx++) {
            const rpm = targetRpmBins[rpmIdx];
            const map = targetMapBins[mapIdx];
            
            // Find value using bilinear interpolation
            grid[rpmIdx][mapIdx] = interpolateValue(table, rpm, map);
        }
    }

    return grid;
}

/**
 * Bilinear interpolation to get value at arbitrary RPM/MAP point
 */
function interpolateValue(table: PVVTable, rpm: number, map: number): number {
    const { rows, columns, values } = table;
    
    if (rows.length === 0 || columns.length === 0) return 0;

    // Find surrounding row indices
    let rpmLowIdx = 0;
    let rpmHighIdx = rows.length - 1;
    for (let i = 0; i < rows.length - 1; i++) {
        if (rpm >= rows[i] && rpm <= rows[i + 1]) {
            rpmLowIdx = i;
            rpmHighIdx = i + 1;
            break;
        }
    }
    if (rpm <= rows[0]) { rpmLowIdx = 0; rpmHighIdx = 0; }
    if (rpm >= rows[rows.length - 1]) { rpmLowIdx = rows.length - 1; rpmHighIdx = rows.length - 1; }

    // Find surrounding column indices
    let mapLowIdx = 0;
    let mapHighIdx = columns.length - 1;
    for (let i = 0; i < columns.length - 1; i++) {
        if (map >= columns[i] && map <= columns[i + 1]) {
            mapLowIdx = i;
            mapHighIdx = i + 1;
            break;
        }
    }
    if (map <= columns[0]) { mapLowIdx = 0; mapHighIdx = 0; }
    if (map >= columns[columns.length - 1]) { mapLowIdx = columns.length - 1; mapHighIdx = columns.length - 1; }

    // Get corner values
    const v00 = values[rpmLowIdx]?.[mapLowIdx] ?? 0;
    const v01 = values[rpmLowIdx]?.[mapHighIdx] ?? 0;
    const v10 = values[rpmHighIdx]?.[mapLowIdx] ?? 0;
    const v11 = values[rpmHighIdx]?.[mapHighIdx] ?? 0;

    // Calculate interpolation weights
    const rpmRange = rows[rpmHighIdx] - rows[rpmLowIdx];
    const mapRange = columns[mapHighIdx] - columns[mapLowIdx];
    
    const rpmWeight = rpmRange > 0 ? (rpm - rows[rpmLowIdx]) / rpmRange : 0;
    const mapWeight = mapRange > 0 ? (map - columns[mapLowIdx]) / mapRange : 0;

    // Bilinear interpolation
    const v0 = v00 + (v01 - v00) * mapWeight;
    const v1 = v10 + (v11 - v10) * mapWeight;
    return v0 + (v1 - v0) * rpmWeight;
}

/**
 * Extract AFR targets as a simple MAP -> AFR lookup
 */
export function extractAfrTargets(table: PVVTable): Record<number, number> {
    const targets: Record<number, number> = {};
    
    // Use the first row (idle RPM) or average across RPM range
    // For simplicity, use a mid-range RPM row
    const midRowIdx = Math.floor(table.rows.length / 2);
    
    for (let colIdx = 0; colIdx < table.columns.length; colIdx++) {
        const mapKpa = table.columns[colIdx];
        const afrValue = table.values[midRowIdx]?.[colIdx];
        if (afrValue !== undefined && mapKpa !== undefined) {
            targets[Math.round(mapKpa)] = afrValue;
        }
    }
    
    return targets;
}

/**
 * Get summary info about a parsed PVV
 */
export function getPVVSummary(parsed: ParsedPVV): string {
    const lines: string[] = [];

    if (parsed.sourceFile) {
        lines.push(`Source: ${parsed.sourceFile}`);
    }
    if (parsed.engineDisplacementCid != null) {
        lines.push(`Engine: ${parsed.engineDisplacementCid} CID${parsed.inferredEngineFamily ? ` (${parsed.inferredEngineFamily})` : ""}`);
    }
    if (parsed.calibrationId) {
        lines.push(`Cal ID: ${parsed.calibrationId}`);
    }

    if (parsed.veFront) {
        lines.push(`Front VE: ${parsed.veFront.rows.length} RPM × ${parsed.veFront.columns.length} MAP`);
    }
    
    if (parsed.veRear) {
        lines.push(`Rear VE: ${parsed.veRear.rows.length} RPM × ${parsed.veRear.columns.length} MAP`);
    }
    
    if (parsed.afrTarget) {
        lines.push(`AFR Targets: ${parsed.afrTarget.rows.length} RPM × ${parsed.afrTarget.columns.length} MAP`);
    }
    
    lines.push(`Total tables: ${parsed.allTables.size}`);
    
    if (parsed.parseErrors.length > 0) {
        lines.push(`Warnings: ${parsed.parseErrors.length}`);
    }
    
    return lines.join('\n');
}
