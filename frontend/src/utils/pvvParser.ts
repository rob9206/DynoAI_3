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
    columns: number[];      // MAP bins
    rows: number[];         // RPM bins (in actual RPM, not x1000)
    values: number[][];     // [rowIdx][colIdx]
}

export interface ParsedPVV {
    sourceFile?: string;
    veFront?: PVVTable;
    veRear?: PVVTable;
    afrTarget?: PVVTable;
    allTables: Map<string, PVVTable>;
    parseErrors: string[];
}

/**
 * Parse a Power Vision PVV XML file
 */
export function parsePVV(xmlContent: string): ParsedPVV {
    const result: ParsedPVV = {
        allTables: new Map(),
        parseErrors: [],
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
        
        for (const item of items) {
            try {
                const table = parseTableItem(item);
                if (table) {
                    result.allTables.set(table.name, table);
                    
                    // Identify key tables
                    const nameLower = table.name.toLowerCase();
                    if (nameLower.includes('ve') && nameLower.includes('map') && nameLower.includes('front')) {
                        result.veFront = table;
                    } else if (nameLower.includes('ve') && nameLower.includes('map') && nameLower.includes('rear')) {
                        result.veRear = table;
                    } else if (nameLower === 'air-fuel ratio' || nameLower === 'air fuel ratio') {
                        result.afrTarget = table;
                    }
                }
            } catch (e) {
                result.parseErrors.push(`Error parsing item: ${e}`);
            }
        }

    } catch (e) {
        result.parseErrors.push(`Failed to parse PVV: ${e}`);
    }

    return result;
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

            // Parse cell values
            const cellEls = row.querySelectorAll('Cell');
            const rowValues: number[] = [];
            for (const cell of cellEls) {
                const value = cell.getAttribute('value');
                rowValues.push(value ? parseFloat(value) : 0);
            }
            values.push(rowValues);
        }
    }

    return {
        name,
        units,
        columnUnits,
        rowUnits,
        columns,
        rows,
        values,
    };
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
