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
import { Upload, FileCheck, Settings, AlertTriangle, Check, X } from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Card, CardContent } from '../ui/card';
import { parsePVV, getPVVSummary, extractAfrTargets, type ParsedPVV, type PVVTable } from '../../utils/pvvParser';
import { listEnginePresets, getEnginePreset, type EnginePresetData } from '../../utils/enginePresets';

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
            
            if (parsed.parseErrors.length > 0 && !parsed.veFront && !parsed.afrTarget) {
                setImportError(`Parse errors: ${parsed.parseErrors.join(', ')}`);
                return;
            }

            setImportedPVV(parsed);

            // Extract and send data to parent
            const afrTargets = parsed.afrTarget 
                ? extractAfrTargets(parsed.afrTarget)
                : getEnginePreset(currentPreset)?.afrTargets ?? {};

            const result: TuneImportResult = {
                source: 'pvv',
                sourceName: parsed.sourceFile || file.name,
                veFront: parsed.veFront,
                veRear: parsed.veRear,
                afrTargets,
                rpmBins: parsed.veFront?.rows ?? getEnginePreset(currentPreset)?.rpmBins ?? [],
                mapBins: parsed.veFront?.columns ?? getEnginePreset(currentPreset)?.mapBins ?? [],
            };

            onImport(result);
        } catch (e) {
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
                        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                            <div className="flex items-start gap-2">
                                <Check className="w-4 h-4 text-green-400 mt-0.5" />
                                <div className="text-xs">
                                    <div className="text-green-400 font-medium">
                                        {importedPVV.sourceFile || 'PVV File Loaded'}
                                    </div>
                                    <div className="text-zinc-400 mt-1 whitespace-pre-line">
                                        {getPVVSummary(importedPVV)}
                                    </div>
                                </div>
                            </div>
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
