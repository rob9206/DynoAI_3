/**
 * VE Export Utilities
 * 
 * Provides export functions for VE correction data in multiple formats:
 * - CSV: Simple spreadsheet format
 * - JSON: Full structured data
 * - PVV: Power Vision XML format (for direct import into Power Vision)
 * 
 * Supports dual-cylinder exports (Front/Rear) for V-twin engines.
 */

import { LiveVEExportData } from '../components/jetdrive/LiveVETable';

// ECU bin definitions from Power Vision (from config/pvv_template.pvv)
// These are the actual bins used by Harley-Davidson ECUs
export const ECU_MAP_BINS = [
    10.3, 15.1, 19.9, 25.1, 29.9, 35.1, 39.9, 45, 50.2, 55,
    60.1, 64.9, 70.1, 74.9, 84.9, 94.8, 104.4
];

export const ECU_RPM_BINS = [
    0.75, 1, 1.125, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 2.75,
    3, 3.25, 3.5, 3.75, 4, 4.25, 4.5, 4.75, 5, 5.25, 5.5, 5.75, 6, 6.25, 6.5
];

/**
 * Find the closest ECU bin for a DynoAI bin value
 * Returns the ECU bin index or -1 if no close match (within tolerance)
 */
function findClosestEcuBin(value: number, ecuBins: number[], tolerance: number = 2): number {
    let closestIdx = -1;
    let closestDist = Infinity;
    
    for (let i = 0; i < ecuBins.length; i++) {
        const dist = Math.abs(ecuBins[i] - value);
        if (dist < closestDist && dist <= tolerance) {
            closestDist = dist;
            closestIdx = i;
        }
    }
    
    return closestIdx;
}

/**
 * Map DynoAI bins to ECU bins
 * Returns array of [dynoaiIdx, ecuIdx] pairs for matching bins
 */
export function mapBinsToEcu(
    dynoaiBins: number[],
    ecuBins: number[],
    tolerance: number = 2
): Map<number, number> {
    const mapping = new Map<number, number>();
    
    for (let i = 0; i < dynoaiBins.length; i++) {
        const ecuIdx = findClosestEcuBin(dynoaiBins[i], ecuBins, tolerance);
        if (ecuIdx >= 0) {
            mapping.set(i, ecuIdx);
        }
    }
    
    return mapping;
}

/**
 * Export VE corrections to CSV format
 * Creates a grid with RPM columns and MAP rows
 */
export function exportToCSV(data: LiveVEExportData, cylinder: 'front' | 'rear' | 'combined' = 'combined'): string {
    const corrections = cylinder === 'front' 
        ? data.frontCorrections 
        : cylinder === 'rear' 
            ? data.rearCorrections 
            : data.frontCorrections.map((row, i) => 
                row.map((v, j) => (v + data.rearCorrections[i][j]) / 2)
            );
    
    const lines: string[] = [];
    
    // Header with metadata
    lines.push(`# DynoAI VE Corrections Export`);
    lines.push(`# Cylinder: ${cylinder}`);
    lines.push(`# Engine: ${data.enginePreset}`);
    lines.push(`# Total Hits: ${data.totalHits}`);
    lines.push(`# Exported: ${data.exportedAt}`);
    lines.push('');
    
    // Column headers (RPM bins)
    lines.push(`MAP_kPa,${data.rpmBins.join(',')}`);
    
    // Data rows (MAP bins with corrections as percentage deltas)
    for (let mapIdx = 0; mapIdx < data.mapBins.length; mapIdx++) {
        const mapKpa = data.mapBins[mapIdx];
        const rowValues = data.rpmBins.map((_, rpmIdx) => {
            const mult = corrections[rpmIdx]?.[mapIdx] ?? 1.0;
            const pctDelta = ((mult - 1) * 100).toFixed(2);
            return pctDelta;
        });
        lines.push(`${mapKpa},${rowValues.join(',')}`);
    }
    
    return lines.join('\n');
}

/**
 * Export VE corrections to JSON format
 * Includes full structured data with metadata
 */
export function exportToJSON(data: LiveVEExportData): string {
    return JSON.stringify({
        version: '1.0',
        type: 'dynoai_ve_corrections',
        metadata: {
            enginePreset: data.enginePreset,
            totalHits: data.totalHits,
            exportedAt: data.exportedAt,
        },
        bins: {
            rpm: data.rpmBins,
            map: data.mapBins,
        },
        afrTargets: data.afrTargets,
        corrections: {
            front: data.frontCorrections.map((row, i) => 
                row.map((v, j) => ({
                    rpmIdx: i,
                    mapIdx: j,
                    rpm: data.rpmBins[i],
                    map: data.mapBins[j],
                    multiplier: v,
                    pctDelta: ((v - 1) * 100).toFixed(2),
                    hits: data.hitCounts[i]?.[j] ?? 0,
                }))
            ).flat().filter(c => c.hits > 0),
            rear: data.rearCorrections.map((row, i) => 
                row.map((v, j) => ({
                    rpmIdx: i,
                    mapIdx: j,
                    rpm: data.rpmBins[i],
                    map: data.mapBins[j],
                    multiplier: v,
                    pctDelta: ((v - 1) * 100).toFixed(2),
                    hits: data.hitCounts[i]?.[j] ?? 0,
                }))
            ).flat().filter(c => c.hits > 0),
        },
        hitCounts: data.hitCounts,
    }, null, 2);
}

/**
 * Export VE corrections to Power Vision PVV XML format
 * 
 * Uses PARTIAL bin matching - only exports cells where DynoAI bins
 * approximately match ECU bins. This is safer than interpolation.
 * 
 * Exports separate tables for Front and Rear cylinders.
 */
export function exportToPVV(data: LiveVEExportData): string {
    // Map DynoAI bins to ECU bins (partial matching)
    const rpmMapping = mapBinsToEcu(
        data.rpmBins.map(r => r / 1000), // Convert to RPMx1000 format
        ECU_RPM_BINS,
        0.3 // Tolerance of 0.3 (300 RPM)
    );
    
    const mapMapping = mapBinsToEcu(
        data.mapBins,
        ECU_MAP_BINS,
        3 // Tolerance of 3 kPa
    );
    
    // Build XML
    const lines: string[] = [];
    lines.push('<?xml version="1.0" encoding="utf-8"?>');
    lines.push('<PVV>');
    lines.push('  <!-- DynoAI VE Corrections Export -->');
    lines.push(`  <!-- Engine: ${data.enginePreset} -->`);
    lines.push(`  <!-- Total Hits: ${data.totalHits} -->`);
    lines.push(`  <!-- Exported: ${data.exportedAt} -->`);
    lines.push('  <!-- Note: Only cells with matching ECU bins are included -->');
    lines.push('');
    
    // Helper to generate a VE table for one cylinder
    const generateVETable = (name: string, corrections: number[][]) => {
        lines.push(`  <Item name="${name}" units="%">`);
        
        // Columns (MAP bins that we have data for)
        lines.push('    <Columns units="Kilopascals">');
        for (const [dynoIdx, ecuIdx] of mapMapping.entries()) {
            lines.push(`      <Col label="${ECU_MAP_BINS[ecuIdx]}" />`);
        }
        lines.push('    </Columns>');
        
        // Rows (RPM bins that we have data for)
        lines.push('    <Rows units="RPMx1000">');
        for (const [dynoRpmIdx, ecuRpmIdx] of rpmMapping.entries()) {
            const rpmLabel = ECU_RPM_BINS[ecuRpmIdx];
            lines.push(`      <Row label="${rpmLabel}">`);
            
            for (const [dynoMapIdx] of mapMapping.entries()) {
                const mult = corrections[dynoRpmIdx]?.[dynoMapIdx] ?? 1.0;
                const hits = data.hitCounts[dynoRpmIdx]?.[dynoMapIdx] ?? 0;
                
                // Convert multiplier to percentage delta
                // Only include if we have data (hits > 0)
                if (hits > 0) {
                    const pctDelta = ((mult - 1) * 100).toFixed(2);
                    lines.push(`        <Cell value="${pctDelta}" />`);
                } else {
                    lines.push(`        <Cell value="0" />`);
                }
            }
            
            lines.push('      </Row>');
        }
        lines.push('    </Rows>');
        lines.push('  </Item>');
    };
    
    // Generate Front Cylinder VE table
    generateVETable('VE Correction (DynoAI/Front Cyl)', data.frontCorrections);
    lines.push('');
    
    // Generate Rear Cylinder VE table
    generateVETable('VE Correction (DynoAI/Rear Cyl)', data.rearCorrections);
    lines.push('');
    
    // Add hit count reference table
    lines.push('  <Item name="Sample Count (DynoAI)" units="count">');
    lines.push('    <Columns units="Kilopascals">');
    for (const [, ecuIdx] of mapMapping.entries()) {
        lines.push(`      <Col label="${ECU_MAP_BINS[ecuIdx]}" />`);
    }
    lines.push('    </Columns>');
    lines.push('    <Rows units="RPMx1000">');
    for (const [dynoRpmIdx, ecuRpmIdx] of rpmMapping.entries()) {
        const rpmLabel = ECU_RPM_BINS[ecuRpmIdx];
        lines.push(`      <Row label="${rpmLabel}">`);
        for (const [dynoMapIdx] of mapMapping.entries()) {
            const hits = data.hitCounts[dynoRpmIdx]?.[dynoMapIdx] ?? 0;
            lines.push(`        <Cell value="${hits}" />`);
        }
        lines.push('      </Row>');
    }
    lines.push('    </Rows>');
    lines.push('  </Item>');
    
    lines.push('</PVV>');
    
    return lines.join('\n');
}

/**
 * Trigger a file download in the browser
 */
export function downloadFile(content: string, filename: string, mimeType: string): void {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/**
 * Export and download in all formats as a zip
 */
export function downloadAllFormats(data: LiveVEExportData, baseName: string = 'VE_Corrections'): void {
    const timestamp = new Date().toISOString().slice(0, 10);
    
    // Download each format
    downloadFile(exportToCSV(data, 'front'), `${baseName}_Front_${timestamp}.csv`, 'text/csv');
    downloadFile(exportToCSV(data, 'rear'), `${baseName}_Rear_${timestamp}.csv`, 'text/csv');
    downloadFile(exportToJSON(data), `${baseName}_${timestamp}.json`, 'application/json');
    downloadFile(exportToPVV(data), `${baseName}_${timestamp}.pvv`, 'application/xml');
}

// =============================================================================
// ABSOLUTE VE EXPORT (Phase 3 - Applied VE Tables)
// =============================================================================

import type { ApplyExportData, DualCylinderVE } from '../types/veApplyTypes';

/**
 * Export applied VE tables (absolute values, not deltas) to CSV
 */
export function exportAppliedVEToCSV(
    appliedVE: DualCylinderVE,
    rpmAxis: number[],
    mapAxis: number[],
    cylinder: 'front' | 'rear',
    metadata?: {
        sessionId?: string;
        sourceFile?: string;
        boundsPreset?: string;
        timestamp?: string;
    }
): string {
    const lines: string[] = [];
    
    // Header with metadata
    lines.push(`# DynoAI Applied VE Table Export`);
    lines.push(`# Cylinder: ${cylinder}`);
    if (metadata?.sessionId) lines.push(`# Session: ${metadata.sessionId}`);
    if (metadata?.sourceFile) lines.push(`# Source: ${metadata.sourceFile}`);
    if (metadata?.boundsPreset) lines.push(`# Bounds: ${metadata.boundsPreset}`);
    lines.push(`# Exported: ${metadata?.timestamp ?? new Date().toISOString()}`);
    lines.push('');
    
    // Column headers (RPM bins)
    lines.push(`MAP_kPa,${rpmAxis.join(',')}`);
    
    // Data rows (MAP bins with VE percentages)
    const veTable = appliedVE[cylinder];
    for (let mapIdx = 0; mapIdx < mapAxis.length; mapIdx++) {
        const mapKpa = mapAxis[mapIdx];
        const rowValues = rpmAxis.map((_, rpmIdx) => {
            const ve = veTable[rpmIdx]?.[mapIdx] ?? 0;
            return ve.toFixed(1);
        });
        lines.push(`${mapKpa},${rowValues.join(',')}`);
    }
    
    return lines.join('\n');
}

/**
 * Export applied VE to JSON (full session bundle)
 */
export function exportAppliedVEToJSON(data: ApplyExportData): string {
    return JSON.stringify({
        version: '2.0',
        type: 'dynoai_applied_ve',
        sessionId: data.sessionId,
        timestamp: data.timestamp,
        enginePreset: data.enginePreset,
        veBoundsPreset: data.veBoundsPreset,
        sourceFile: data.sourceFile,
        axes: {
            rpm: data.rpmAxis,
            map: data.mapAxis,
        },
        baseVE: data.baseVE,
        corrections: data.corrections,
        hitCounts: data.hitCounts,
        appliedVE: data.appliedVE,
        hashes: data.hashes,
    }, null, 2);
}

/**
 * Export applied VE to Power Vision PVV XML format (ABSOLUTE values)
 * 
 * This differs from exportToPVV in that it exports the final VE values,
 * not the correction deltas. This is what you'd import into Power Vision
 * to replace the existing VE tables.
 */
export function exportAppliedVEToPVV(
    appliedVE: DualCylinderVE,
    rpmAxis: number[],
    mapAxis: number[],
    metadata?: {
        sessionId?: string;
        sourceFile?: string;
        boundsPreset?: string;
        timestamp?: string;
    }
): string {
    // Map DynoAI bins to ECU bins (partial matching)
    const rpmMapping = mapBinsToEcu(
        rpmAxis.map(r => r / 1000), // Convert to RPMx1000 format
        ECU_RPM_BINS,
        0.3 // Tolerance of 0.3 (300 RPM)
    );
    
    const mapMapping = mapBinsToEcu(
        mapAxis,
        ECU_MAP_BINS,
        3 // Tolerance of 3 kPa
    );
    
    // Build XML
    const lines: string[] = [];
    lines.push('<?xml version="1.0" encoding="utf-8"?>');
    lines.push('<PVV>');
    lines.push('  <!-- DynoAI Applied VE Table Export (Absolute Values) -->');
    if (metadata?.sessionId) lines.push(`  <!-- Session: ${metadata.sessionId} -->`);
    if (metadata?.sourceFile) lines.push(`  <!-- Source: ${metadata.sourceFile} -->`);
    if (metadata?.boundsPreset) lines.push(`  <!-- Bounds: ${metadata.boundsPreset} -->`);
    lines.push(`  <!-- Exported: ${metadata?.timestamp ?? new Date().toISOString()} -->`);
    lines.push('  <!-- Note: These are ABSOLUTE VE values, not deltas -->');
    lines.push('');
    
    // Helper to generate a VE table for one cylinder
    const generateVETable = (name: string, veTable: number[][]) => {
        lines.push(`  <Item name="${name}" units="%">`);
        
        // Columns (MAP bins that we have data for)
        lines.push('    <Columns units="Kilopascals">');
        for (const [, ecuIdx] of mapMapping.entries()) {
            lines.push(`      <Col label="${ECU_MAP_BINS[ecuIdx]}" />`);
        }
        lines.push('    </Columns>');
        
        // Rows (RPM bins that we have data for)
        lines.push('    <Rows units="RPMx1000">');
        for (const [dynoRpmIdx, ecuRpmIdx] of rpmMapping.entries()) {
            const rpmLabel = ECU_RPM_BINS[ecuRpmIdx];
            lines.push(`      <Row label="${rpmLabel}">`);
            
            for (const [dynoMapIdx] of mapMapping.entries()) {
                const ve = veTable[dynoRpmIdx]?.[dynoMapIdx] ?? 0;
                // Export absolute VE value (not delta)
                lines.push(`        <Cell value="${ve.toFixed(1)}" />`);
            }
            
            lines.push('      </Row>');
        }
        lines.push('    </Rows>');
        lines.push('  </Item>');
    };
    
    // Generate Front Cylinder VE table (absolute)
    generateVETable('VE (MAP based/Front Cyl)', appliedVE.front);
    lines.push('');
    
    // Generate Rear Cylinder VE table (absolute)
    generateVETable('VE (MAP based/Rear Cyl)', appliedVE.rear);
    
    lines.push('</PVV>');
    
    return lines.join('\n');
}

/**
 * Download applied VE in all formats
 */
export function downloadAppliedVEAllFormats(
    data: ApplyExportData,
    baseName: string = 'Applied_VE'
): void {
    const timestamp = new Date().toISOString().slice(0, 10);
    const metadata = {
        sessionId: data.sessionId,
        sourceFile: data.sourceFile,
        boundsPreset: data.veBoundsPreset,
        timestamp: data.timestamp,
    };
    
    // Download CSV for each cylinder
    downloadFile(
        exportAppliedVEToCSV(data.appliedVE, data.rpmAxis, data.mapAxis, 'front', metadata),
        `${baseName}_Front_${timestamp}.csv`,
        'text/csv'
    );
    downloadFile(
        exportAppliedVEToCSV(data.appliedVE, data.rpmAxis, data.mapAxis, 'rear', metadata),
        `${baseName}_Rear_${timestamp}.csv`,
        'text/csv'
    );
    
    // Download full JSON bundle
    downloadFile(
        exportAppliedVEToJSON(data),
        `${baseName}_${timestamp}.json`,
        'application/json'
    );
    
    // Download PVV (absolute values)
    downloadFile(
        exportAppliedVEToPVV(data.appliedVE, data.rpmAxis, data.mapAxis, metadata),
        `${baseName}_${timestamp}.pvv`,
        'application/xml'
    );
}
