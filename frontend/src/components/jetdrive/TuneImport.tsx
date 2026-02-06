/**
 * TuneImport - Import tune data from PVV files or engine presets
 * 
 * Provides:
 * - PVV file upload (drag-drop or file picker)
 * - Auto-parse VE tables and AFR targets
 * - Engine preset fallback
 * - Summary of imported data
 */

import { useState, useCallback, useRef } from 'react';
import { Upload, FileCheck, Settings, AlertTriangle, Check, X, ChevronDown, ChevronUp, Table } from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Card, CardContent } from '../ui/card';
import { parsePVV, getPVVSummary, extractAfrTargets, type ParsedPVV, type PVVTable } from '../../utils/pvvParser';
import { listEnginePresets, getEnginePreset } from '../../utils/enginePresets';

// ==================== VE Preview Table Component ====================

interface VEPreviewTableProps {
    table: PVVTable;
    title: string;
    maxRows?: number;
    maxCols?: number;
}

/**
 * Compact preview table for VE data with color-coded cells
 */
function VEPreviewTable({ table, title, maxRows = 8, maxCols = 8 }: VEPreviewTableProps) {
    const { rows, columns, values } = table;
    
    // Sample rows and columns for preview
    const displayRows = rows.slice(0, maxRows);
    const displayCols = columns.slice(0, maxCols);
    const hasMoreRows = rows.length > maxRows;
    const hasMoreCols = columns.length > maxCols;
    
    // Get color for VE value (green = high efficiency, yellow = mid, red = low)
    const getVEColor = (value: number): string => {
        if (value >= 100) return 'bg-green-500/30 text-green-300';
        if (value >= 90) return 'bg-emerald-500/20 text-emerald-300';
        if (value >= 80) return 'bg-yellow-500/20 text-yellow-300';
        if (value >= 70) return 'bg-orange-500/20 text-orange-300';
        return 'bg-red-500/20 text-red-300';
    };
    
    return (
        <div className="space-y-2">
            <div className="text-xs font-medium text-zinc-300">{title}</div>
            <div className="overflow-x-auto">
                <table className="text-[10px] border-collapse">
                    <thead>
                        <tr>
                            <th className="px-1.5 py-1 text-zinc-500 font-normal text-left border-b border-zinc-700">
                                RPM↓ / MAP→
                            </th>
                            {displayCols.map((col, i) => (
                                <th key={i} className="px-1.5 py-1 text-zinc-400 font-medium text-center border-b border-zinc-700 min-w-[36px]">
                                    {Math.round(col)}
                                </th>
                            ))}
                            {hasMoreCols && (
                                <th className="px-1.5 py-1 text-zinc-500 text-center border-b border-zinc-700">...</th>
                            )}
                        </tr>
                    </thead>
                    <tbody>
                        {displayRows.map((rpm, rowIdx) => (
                            <tr key={rowIdx}>
                                <td className="px-1.5 py-0.5 text-zinc-400 font-medium border-r border-zinc-700">
                                    {Math.round(rpm)}
                                </td>
                                {displayCols.map((_, colIdx) => {
                                    const value = values[rowIdx]?.[colIdx] ?? 0;
                                    return (
                                        <td 
                                            key={colIdx} 
                                            className={`px-1.5 py-0.5 text-center font-mono ${getVEColor(value)}`}
                                        >
                                            {value.toFixed(1)}
                                        </td>
                                    );
                                })}
                                {hasMoreCols && (
                                    <td className="px-1.5 py-0.5 text-zinc-500 text-center">...</td>
                                )}
                            </tr>
                        ))}
                        {hasMoreRows && (
                            <tr>
                                <td className="px-1.5 py-0.5 text-zinc-500 border-r border-zinc-700">...</td>
                                {displayCols.map((_, i) => (
                                    <td key={i} className="px-1.5 py-0.5 text-zinc-500 text-center">...</td>
                                ))}
                                {hasMoreCols && <td className="px-1.5 py-0.5 text-zinc-500 text-center">...</td>}
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
            <div className="text-[10px] text-zinc-500">
                Showing {displayRows.length} of {rows.length} RPM bins × {displayCols.length} of {columns.length} MAP bins
            </div>
        </div>
    );
}

/**
 * AFR targets preview as a simple row
 */
function AFRPreviewTable({ table }: { table: PVVTable }) {
    const { columns, values } = table;
    
    // Use middle row for AFR targets (typical operating RPM)
    const midRowIdx = Math.floor(values.length / 2);
    const afrRow = values[midRowIdx] || values[0] || [];
    
    // Show first 8 MAP bins
    const displayCols = columns.slice(0, 8);
    const displayValues = afrRow.slice(0, 8);
    
    const getAFRColor = (value: number): string => {
        if (value >= 14.5) return 'text-blue-300'; // Lean
        if (value >= 13.5) return 'text-green-300'; // Stoich/slightly rich
        if (value >= 12.5) return 'text-yellow-300'; // Rich
        return 'text-orange-300'; // Very rich
    };
    
    return (
        <div className="space-y-2">
            <div className="text-xs font-medium text-zinc-300">AFR Targets (at {Math.round(table.rows[midRowIdx] || 0)} RPM)</div>
            <div className="flex flex-wrap gap-2">
                {displayCols.map((map, i) => (
                    <div key={i} className="text-center">
                        <div className="text-[10px] text-zinc-500">{Math.round(map)} kPa</div>
                        <div className={`text-xs font-mono font-medium ${getAFRColor(displayValues[i] || 0)}`}>
                            {(displayValues[i] || 0).toFixed(2)}
                        </div>
                    </div>
                ))}
                {columns.length > 8 && (
                    <div className="text-center">
                        <div className="text-[10px] text-zinc-500">...</div>
                        <div className="text-xs text-zinc-500">+{columns.length - 8}</div>
                    </div>
                )}
            </div>
        </div>
    );
}

export interface TuneImportResult {
    source: 'pvv' | 'preset';
    sourceName: string;
    veFront?: PVVTable;
    veRear?: PVVTable;
    afrTargets: Record<number, number>;
    rpmBins: number[];
    mapBins: number[];
}

interface TuneImportProps {
    onImport: (result: TuneImportResult) => void;
    currentPreset?: string;
    compact?: boolean;
}

export function TuneImport({ onImport, currentPreset = 'harley_m8', compact = false }: TuneImportProps) {
    const [isDragging, setIsDragging] = useState(false);
    const [importedPVV, setImportedPVV] = useState<ParsedPVV | null>(null);
    const [importError, setImportError] = useState<string | null>(null);
    const [showPresets, setShowPresets] = useState(false);
    const [showPreview, setShowPreview] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFile = useCallback(async (file: File) => {
        setImportError(null);
        
        if (!file.name.toLowerCase().endsWith('.pvv')) {
            setImportError('Please select a .pvv file from Power Vision');
            return;
        }

        try {
            const content = await file.text();
            const parsed = parsePVV(content);
            
            console.log('[TuneImport] Parsed PVV file:', {
                sourceFile: parsed.sourceFile,
                veFront: parsed.veFront ? {
                    name: parsed.veFront.name,
                    rows: parsed.veFront.rows.length,
                    columns: parsed.veFront.columns.length,
                    sampleValues: parsed.veFront.values[0]?.slice(0, 3),
                } : null,
                veRear: parsed.veRear ? {
                    name: parsed.veRear.name,
                    rows: parsed.veRear.rows.length,
                    columns: parsed.veRear.columns.length,
                } : null,
                afrTarget: parsed.afrTarget ? {
                    name: parsed.afrTarget.name,
                    rows: parsed.afrTarget.rows.length,
                    columns: parsed.afrTarget.columns.length,
                } : null,
                allTables: Array.from(parsed.allTables.keys()),
                parseErrors: parsed.parseErrors,
            });
            
            if (parsed.parseErrors.length > 0 && !parsed.veFront && !parsed.afrTarget) {
                setImportError(`Parse errors: ${parsed.parseErrors.join(', ')}`);
                return;
            }

            // Warn if this looks like a DynoAI correction file, not a base tune
            if (parsed.veFront) {
                const tableName = parsed.veFront.name.toLowerCase();
                const values = parsed.veFront.values;
                const isCorrection = tableName.includes('correction') || tableName.includes('dynoai');
                // Correction files have small values (percentage changes near 0)
                // Base tune files have larger VE values (typically 50-120)
                const sampleValues = values.flat().filter(v => Number.isFinite(v));
                const avgAbsValue = sampleValues.length > 0 
                    ? sampleValues.reduce((sum, v) => sum + Math.abs(v), 0) / sampleValues.length 
                    : 0;
                
                if (isCorrection || avgAbsValue < 30) {
                    console.warn('[TuneImport] This appears to be a correction file, not a base tune.',
                        { tableName: parsed.veFront.name, avgAbsValue: avgAbsValue.toFixed(1) });
                    setImportError(
                        'This appears to be a VE correction file, not a base tune. ' +
                        'Please import your original Power Vision tune file (.pvv) with base VE tables, ' +
                        'or use a preset instead.'
                    );
                    return;
                }
            }

            setImportedPVV(parsed);

            // Extract and send data to parent
            const afrTargets = parsed.afrTarget 
                ? extractAfrTargets(parsed.afrTarget)
                : getEnginePreset(currentPreset)?.afrTargets ?? {};

            // Deduplicate bins - PVV files can have near-duplicate values that
            // round to the same integer, causing duplicate rows/columns in the grid
            const deduplicateBins = (bins: number[]): number[] => {
                const rounded = bins.map(b => Math.round(b));
                return [...new Set(rounded)].sort((a, b) => a - b);
            };

            const rawRpmBins = parsed.veFront?.rows ?? getEnginePreset(currentPreset)?.rpmBins ?? [];
            const rawMapBins = parsed.veFront?.columns ?? getEnginePreset(currentPreset)?.mapBins ?? [];

            const result: TuneImportResult = {
                source: 'pvv',
                sourceName: parsed.sourceFile || file.name,
                veFront: parsed.veFront,
                veRear: parsed.veRear,
                afrTargets,
                rpmBins: deduplicateBins(rawRpmBins),
                mapBins: deduplicateBins(rawMapBins),
            };

            console.log('[TuneImport] Sending result to parent:', {
                source: result.source,
                sourceName: result.sourceName,
                hasVeFront: !!result.veFront,
                hasVeRear: !!result.veRear,
                rpmBins: result.rpmBins,
                mapBins: result.mapBins,
                afrTargetKeys: Object.keys(result.afrTargets),
            });

            onImport(result);
        } catch (e) {
            console.error('[TuneImport] Error parsing file:', e);
            setImportError(`Failed to read file: ${e}`);
        }
    }, [currentPreset, onImport]);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        
        const file = e.dataTransfer.files[0];
        if (file) {
            handleFile(file);
        }
    }, [handleFile]);

    const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            handleFile(file);
        }
    }, [handleFile]);

    const handlePresetSelect = useCallback((presetKey: string) => {
        const preset = getEnginePreset(presetKey);
        if (!preset) return;

        setImportedPVV(null);
        setShowPresets(false);

        const result: TuneImportResult = {
            source: 'preset',
            sourceName: preset.name,
            afrTargets: preset.afrTargets,
            rpmBins: preset.rpmBins,
            mapBins: preset.mapBins,
        };

        onImport(result);
    }, [onImport]);

    const clearImport = useCallback(() => {
        setImportedPVV(null);
        setImportError(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    }, []);

    const presets = listEnginePresets();

    if (compact) {
        return (
            <div className="flex items-center gap-2">
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pvv"
                    onChange={handleFileSelect}
                    className="hidden"
                />
                
                {importedPVV ? (
                    <Badge variant="outline" className="text-green-400 border-green-500/30 bg-green-500/10">
                        <FileCheck className="w-3 h-3 mr-1" />
                        {importedPVV.sourceFile || 'PVV Loaded'}
                    </Badge>
                ) : (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => fileInputRef.current?.click()}
                        className="text-xs"
                    >
                        <Upload className="w-3 h-3 mr-1" />
                        Import PVV
                    </Button>
                )}
                
                <div className="relative">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowPresets(!showPresets)}
                        className="text-xs"
                    >
                        <Settings className="w-3 h-3 mr-1" />
                        Preset
                    </Button>
                    
                    {showPresets && (
                        <div className="absolute right-0 top-full mt-1 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl py-1 min-w-[180px] z-50">
                            {presets.map(p => (
                                <button
                                    key={p.key}
                                    onClick={() => handlePresetSelect(p.key)}
                                    className="w-full text-left px-3 py-1.5 hover:bg-zinc-700 text-xs text-zinc-300"
                                >
                                    {p.name}
                                    <span className="text-zinc-500 ml-1 text-[10px]">{p.description}</span>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        );
    }

    return (
        <Card className="bg-zinc-900/50 border-zinc-800">
            <CardContent className="pt-4">
                <div className="space-y-4">
                    {/* Header */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center">
                                <Upload className="w-4 h-4 text-blue-400" />
                            </div>
                            <div>
                                <h3 className="text-sm font-semibold text-white">Import Tune</h3>
                                <p className="text-[10px] text-zinc-500">Load VE tables from Power Vision</p>
                            </div>
                        </div>
                        
                        {importedPVV && (
                            <Button variant="ghost" size="sm" onClick={clearImport}>
                                <X className="w-3 h-3" />
                            </Button>
                        )}
                    </div>

                    {/* Import Status */}
                    {importedPVV ? (
                        <div className="space-y-3">
                            <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                                <div className="flex items-start gap-2">
                                    <Check className="w-4 h-4 text-green-400 mt-0.5" />
                                    <div className="text-xs flex-1">
                                        <div className="text-green-400 font-medium">
                                            {importedPVV.sourceFile || 'PVV File Loaded'}
                                        </div>
                                        <div className="text-zinc-400 mt-1 whitespace-pre-line">
                                            {getPVVSummary(importedPVV)}
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            {/* Preview Data Toggle */}
                            {(importedPVV.veFront || importedPVV.veRear || importedPVV.afrTarget) && (
                                <div className="border border-zinc-700 rounded-lg overflow-hidden">
                                    <button
                                        onClick={() => setShowPreview(!showPreview)}
                                        className="w-full flex items-center justify-between px-3 py-2 bg-zinc-800/50 hover:bg-zinc-800 transition-colors"
                                    >
                                        <span className="flex items-center gap-2 text-xs text-zinc-300">
                                            <Table className="w-3.5 h-3.5" />
                                            Preview Data
                                        </span>
                                        {showPreview ? (
                                            <ChevronUp className="w-4 h-4 text-zinc-400" />
                                        ) : (
                                            <ChevronDown className="w-4 h-4 text-zinc-400" />
                                        )}
                                    </button>
                                    
                                    {showPreview && (
                                        <div className="p-3 space-y-4 bg-zinc-900/50">
                                            {importedPVV.veFront && (
                                                <VEPreviewTable 
                                                    table={importedPVV.veFront} 
                                                    title="Front Cylinder VE (%)"
                                                />
                                            )}
                                            {importedPVV.veRear && (
                                                <VEPreviewTable 
                                                    table={importedPVV.veRear} 
                                                    title="Rear Cylinder VE (%)"
                                                />
                                            )}
                                            {importedPVV.afrTarget && (
                                                <AFRPreviewTable table={importedPVV.afrTarget} />
                                            )}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ) : importError ? (
                        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                            <div className="flex items-start gap-2">
                                <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5" />
                                <div className="text-xs text-red-400">
                                    {importError}
                                </div>
                            </div>
                        </div>
                    ) : (
                        /* Drop Zone */
                        <div
                            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                            onDragLeave={() => setIsDragging(false)}
                            onDrop={handleDrop}
                            onClick={() => fileInputRef.current?.click()}
                            className={`
                                border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-all
                                ${isDragging 
                                    ? 'border-blue-500 bg-blue-500/10' 
                                    : 'border-zinc-700 hover:border-zinc-600 hover:bg-zinc-800/50'
                                }
                            `}
                        >
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".pvv"
                                onChange={handleFileSelect}
                                className="hidden"
                            />
                            <Upload className={`w-8 h-8 mx-auto mb-2 ${isDragging ? 'text-blue-400' : 'text-zinc-500'}`} />
                            <div className="text-sm text-zinc-400">
                                Drop .pvv file here or click to browse
                            </div>
                            <div className="text-xs text-zinc-600 mt-1">
                                Exports from Power Vision will auto-populate VE and AFR tables
                            </div>
                        </div>
                    )}

                    {/* Engine Presets */}
                    <div className="border-t border-zinc-800 pt-4">
                        <div className="text-xs text-zinc-500 mb-2">Or use an engine preset:</div>
                        <div className="grid grid-cols-2 gap-2">
                            {presets.map(p => (
                                <Button
                                    key={p.key}
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handlePresetSelect(p.key)}
                                    className={`justify-start text-xs ${
                                        currentPreset === p.key 
                                            ? 'border-orange-500/50 text-orange-400' 
                                            : 'border-zinc-700'
                                    }`}
                                >
                                    {p.name}
                                </Button>
                            ))}
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

export default TuneImport;
