/**
 * Stage Configuration Panel - Integrated into Command Center
 * 
 * Combines Stage Presets, Cam Family Presets, and Decel Pop Fix
 * from the Tuning Wizards page into a unified panel.
 */

import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { toast } from '@/lib/toast';
import {
    Flame,
    Gauge,
    Settings2,
    Download,
    AlertTriangle,
    ChevronRight,
    ChevronDown,
    Info,
    Loader2,
    Sparkles,
    Wrench,
    Zap,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';
import {
    getWizardConfig,
    previewDecelFix,
    applyDecelFix,
    type StagePreset,
    type CamPreset,
    type DecelPreviewResult,
    type WizardConfig,
} from '../../api/wizards';

interface StageConfigPanelProps {
    /** Current AFR targets (MAP -> AFR) */
    afrTargets: Record<number, number>;
    /** Callback when AFR targets should be updated */
    onAfrTargetsChange: (targets: Record<number, number>) => void;
    /** Current run ID for decel fix association */
    runId?: string;
    /** Whether panel is in compact mode */
    compact?: boolean;
}

// Helper to convert stage preset AFR targets to our MAP-based format
function stageToAfrTargets(stage: StagePreset): Record<number, number> {
    // Create a graduated AFR curve based on stage targets
    const { cruise, wot, idle } = stage.afr_targets;
    
    // MAP bins: 20 (idle) -> 100 (WOT)
    return {
        20: idle,
        30: (idle + cruise) / 2,
        40: cruise,
        50: cruise,
        60: (cruise + wot) / 2,
        70: (cruise + wot) / 2,
        80: wot,
        90: wot,
        100: wot,
    };
}

// Helper to convert cam preset AFR targets to our MAP-based format  
function camToAfrTargets(cam: CamPreset): Record<number, number> {
    const { idle, cruise, wot } = cam.afr_targets;
    
    return {
        20: idle,
        30: (idle + cruise) / 2,
        40: cruise,
        50: cruise,
        60: (cruise + wot) / 2,
        70: (cruise + wot) / 2,
        80: wot,
        90: wot,
        100: wot,
    };
}

export function StageConfigPanel({
    afrTargets,
    onAfrTargetsChange,
    runId,
    compact = false,
}: StageConfigPanelProps) {
    // Selected presets
    const [selectedStage, setSelectedStage] = useState<string>('stock');
    const [selectedCam, setSelectedCam] = useState<string>('stock');
    
    // Decel wizard state
    const [decelSeverity, setDecelSeverity] = useState<'low' | 'medium' | 'high'>('medium');
    const [decelRpmMin, setDecelRpmMin] = useState(1750);
    const [decelRpmMax, setDecelRpmMax] = useState(5500);
    const [decelPreview, setDecelPreview] = useState<DecelPreviewResult | null>(null);
    
    // Collapsible states
    const [stageOpen, setStageOpen] = useState(true);
    const [camOpen, setCamOpen] = useState(false);
    const [decelOpen, setDecelOpen] = useState(false);

    // Fetch wizard config
    const { data: config, isLoading: configLoading } = useQuery({
        queryKey: ['wizardConfig'],
        queryFn: getWizardConfig,
        staleTime: Infinity, // Config doesn't change
    });

    // Decel preview mutation
    const previewMutation = useMutation({
        mutationFn: previewDecelFix,
        onSuccess: (data) => {
            setDecelPreview(data);
        },
        onError: (error: Error) => {
            toast.error(error.message ?? 'Failed to preview decel fix');
        },
    });

    // Decel apply mutation
    const applyMutation = useMutation({
        mutationFn: applyDecelFix,
        onSuccess: (data) => {
            toast.success('Decel Pop Fix applied!', {
                description: `${data.cells_modified} cells modified`
            });
            window.open(data.download_url, '_blank');
        },
        onError: (error: Error) => {
            toast.error(error.message ?? 'Failed to apply decel fix');
        },
    });

    // Preview decel when params change
    useEffect(() => {
        if (config && decelOpen) {
            previewMutation.mutate({
                severity: decelSeverity,
                rpm_min: decelRpmMin,
                rpm_max: decelRpmMax,
                cam_family: selectedCam,
            });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [decelSeverity, decelRpmMin, decelRpmMax, selectedCam, config, decelOpen]);

    // Handle stage selection
    const handleStageChange = (stageLevel: string) => {
        setSelectedStage(stageLevel);
        const stagePreset = config?.stages.find(s => s.level === stageLevel);
        if (stagePreset) {
            const newTargets = stageToAfrTargets(stagePreset);
            onAfrTargetsChange(newTargets);
            toast.success(`Applied ${stagePreset.display_name} AFR targets`, {
                description: `Cruise: ${stagePreset.afr_targets.cruise} • WOT: ${stagePreset.afr_targets.wot}`
            });
        }
    };

    // Handle cam selection
    const handleCamChange = (camFamily: string) => {
        setSelectedCam(camFamily);
        const camPreset = config?.cams.find(c => c.family === camFamily);
        if (camPreset) {
            const newTargets = camToAfrTargets(camPreset);
            onAfrTargetsChange(newTargets);
            toast.success(`Applied ${camPreset.display_name} AFR targets`, {
                description: `Idle: ${camPreset.afr_targets.idle} • VE offset: +${camPreset.idle_characteristics.ve_offset_pct}%`
            });
        }
    };

    // Handle decel apply
    const handleApplyDecelFix = () => {
        applyMutation.mutate({
            severity: decelSeverity,
            rpm_min: decelRpmMin,
            rpm_max: decelRpmMax,
            cam_family: selectedCam,
            run_id: runId,
        });
    };

    const selectedStagePreset = config?.stages.find(s => s.level === selectedStage);
    const selectedCamPreset = config?.cams.find(c => c.family === selectedCam);

    if (configLoading) {
        return (
            <div className="flex items-center gap-2 py-4 text-zinc-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-xs">Loading presets...</span>
            </div>
        );
    }

    return (
        <div className={`space-y-3 ${compact ? '' : 'pt-4 border-t border-zinc-800'}`}>
            {/* Section Header */}
            {!compact && (
                <div className="flex items-center gap-2 mb-3">
                    <div className="p-1.5 bg-blue-500/10 rounded-lg">
                        <Sparkles className="h-4 w-4 text-blue-400" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-zinc-200">Build Configuration</h3>
                        <p className="text-[10px] text-zinc-500">Auto-configure AFR targets by stage & cam</p>
                    </div>
                </div>
            )}

            {/* Stage Configuration */}
            <Collapsible open={stageOpen} onOpenChange={setStageOpen}>
                <CollapsibleTrigger className="w-full flex items-center justify-between p-2.5 rounded-lg bg-blue-500/5 border border-blue-500/20 hover:bg-blue-500/10 transition-colors">
                    <div className="flex items-center gap-2">
                        <Gauge className="h-4 w-4 text-blue-400" />
                        <span className="text-xs font-medium text-blue-300">Stage Configuration</span>
                        {selectedStagePreset && (
                            <Badge variant="outline" className="text-[10px] border-blue-500/30 text-blue-400 py-0">
                                {selectedStagePreset.display_name}
                            </Badge>
                        )}
                    </div>
                    {stageOpen ? (
                        <ChevronDown className="h-4 w-4 text-blue-400" />
                    ) : (
                        <ChevronRight className="h-4 w-4 text-blue-400" />
                    )}
                </CollapsibleTrigger>
                <CollapsibleContent className="pt-3 space-y-3">
                    <Select value={selectedStage} onValueChange={handleStageChange}>
                        <SelectTrigger className="h-9 bg-zinc-800/50 border-zinc-700">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {config?.stages.map((stage) => (
                                <SelectItem key={stage.level} value={stage.level}>
                                    <div className="flex items-center gap-2">
                                        <span className="font-medium">{stage.display_name}</span>
                                        <span className="text-[10px] text-zinc-500">
                                            {stage.ve_scaling.percentage_range}
                                        </span>
                                    </div>
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    {selectedStagePreset && (
                        <div className="p-3 bg-zinc-900/50 rounded-lg border border-zinc-800/50 space-y-2">
                            <p className="text-[11px] text-zinc-400 leading-relaxed">
                                {selectedStagePreset.description}
                            </p>
                            
                            <div className="grid grid-cols-3 gap-2">
                                <div className="text-center p-2 bg-blue-500/10 rounded border border-blue-500/20">
                                    <div className="text-sm font-bold text-blue-300">
                                        {selectedStagePreset.afr_targets.cruise}
                                    </div>
                                    <div className="text-[9px] text-zinc-500">Cruise AFR</div>
                                </div>
                                <div className="text-center p-2 bg-blue-500/10 rounded border border-blue-500/20">
                                    <div className="text-sm font-bold text-blue-300">
                                        {selectedStagePreset.afr_targets.wot}
                                    </div>
                                    <div className="text-[9px] text-zinc-500">WOT AFR</div>
                                </div>
                                <div className="text-center p-2 bg-blue-500/10 rounded border border-blue-500/20">
                                    <div className="text-sm font-bold text-blue-300">
                                        ±{selectedStagePreset.tuning_params.suggested_clamp}%
                                    </div>
                                    <div className="text-[9px] text-zinc-500">Clamp</div>
                                </div>
                            </div>

                            {selectedStagePreset.notes.length > 0 && (
                                <div className="pt-2 border-t border-zinc-800/50 space-y-1">
                                    {selectedStagePreset.notes.slice(0, 2).map((note, i) => (
                                        <div key={i} className="flex items-start gap-1.5 text-[10px] text-zinc-500">
                                            <ChevronRight className="h-3 w-3 text-blue-400 mt-0.5 flex-shrink-0" />
                                            <span>{note}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </CollapsibleContent>
            </Collapsible>

            {/* Cam Family Presets */}
            <Collapsible open={camOpen} onOpenChange={setCamOpen}>
                <CollapsibleTrigger className="w-full flex items-center justify-between p-2.5 rounded-lg bg-purple-500/5 border border-purple-500/20 hover:bg-purple-500/10 transition-colors">
                    <div className="flex items-center gap-2">
                        <Settings2 className="h-4 w-4 text-purple-400" />
                        <span className="text-xs font-medium text-purple-300">Cam Family</span>
                        {selectedCamPreset && (
                            <Badge variant="outline" className="text-[10px] border-purple-500/30 text-purple-400 py-0">
                                {selectedCamPreset.display_name}
                            </Badge>
                        )}
                    </div>
                    {camOpen ? (
                        <ChevronDown className="h-4 w-4 text-purple-400" />
                    ) : (
                        <ChevronRight className="h-4 w-4 text-purple-400" />
                    )}
                </CollapsibleTrigger>
                <CollapsibleContent className="pt-3 space-y-3">
                    <Select value={selectedCam} onValueChange={handleCamChange}>
                        <SelectTrigger className="h-9 bg-zinc-800/50 border-zinc-700">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {config?.cams.map((cam) => (
                                <SelectItem key={cam.family} value={cam.family}>
                                    <div className="flex items-center gap-2">
                                        <span className="font-medium">{cam.display_name}</span>
                                        <span className="text-[10px] text-zinc-500">
                                            {cam.lift_range}
                                        </span>
                                    </div>
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    {selectedCamPreset && (
                        <div className="p-3 bg-zinc-900/50 rounded-lg border border-zinc-800/50 space-y-2">
                            <p className="text-[11px] text-zinc-400 leading-relaxed">
                                {selectedCamPreset.description}
                            </p>
                            
                            <div className="grid grid-cols-4 gap-2">
                                <div className="text-center p-2 bg-purple-500/10 rounded border border-purple-500/20">
                                    <div className="text-sm font-bold text-purple-300">
                                        +{selectedCamPreset.idle_characteristics.ve_offset_pct}%
                                    </div>
                                    <div className="text-[9px] text-zinc-500">VE Offset</div>
                                </div>
                                <div className="text-center p-2 bg-purple-500/10 rounded border border-purple-500/20">
                                    <div className="text-sm font-bold text-purple-300">
                                        {selectedCamPreset.idle_characteristics.rpm_target}
                                    </div>
                                    <div className="text-[9px] text-zinc-500">Target RPM</div>
                                </div>
                                <div className="text-center p-2 bg-purple-500/10 rounded border border-purple-500/20">
                                    <div className="text-sm font-bold text-purple-300">
                                        {selectedCamPreset.idle_characteristics.vacuum_expected_hg}"
                                    </div>
                                    <div className="text-[9px] text-zinc-500">Vacuum</div>
                                </div>
                                <div className="text-center p-2 bg-purple-500/10 rounded border border-purple-500/20">
                                    <div className="text-sm font-bold text-purple-300">
                                        {selectedCamPreset.afr_targets.idle}
                                    </div>
                                    <div className="text-[9px] text-zinc-500">Idle AFR</div>
                                </div>
                            </div>

                            {selectedCamPreset.notes.length > 0 && (
                                <div className="pt-2 border-t border-zinc-800/50 space-y-1">
                                    {selectedCamPreset.notes.slice(0, 2).map((note, i) => (
                                        <div key={i} className="flex items-start gap-1.5 text-[10px] text-zinc-500">
                                            <ChevronRight className="h-3 w-3 text-purple-400 mt-0.5 flex-shrink-0" />
                                            <span>{note}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </CollapsibleContent>
            </Collapsible>

            {/* Decel Pop Wizard */}
            <Collapsible open={decelOpen} onOpenChange={setDecelOpen}>
                <CollapsibleTrigger className="w-full flex items-center justify-between p-2.5 rounded-lg bg-orange-500/5 border border-orange-500/20 hover:bg-orange-500/10 transition-colors">
                    <div className="flex items-center gap-2">
                        <Flame className="h-4 w-4 text-orange-400" />
                        <span className="text-xs font-medium text-orange-300">Decel Pop Fix</span>
                        <Badge variant="outline" className="text-[10px] border-orange-500/30 text-orange-400 py-0 bg-orange-500/10">
                            ⚡ Quick Fix
                        </Badge>
                    </div>
                    {decelOpen ? (
                        <ChevronDown className="h-4 w-4 text-orange-400" />
                    ) : (
                        <ChevronRight className="h-4 w-4 text-orange-400" />
                    )}
                </CollapsibleTrigger>
                <CollapsibleContent className="pt-3 space-y-3">
                    <div className="p-2.5 bg-orange-500/5 rounded-lg border border-orange-500/20">
                        <div className="flex items-start gap-2">
                            <Info className="h-3.5 w-3.5 text-orange-400 mt-0.5 flex-shrink-0" />
                            <p className="text-[10px] text-orange-200/70 leading-relaxed">
                                Every Harley with aftermarket exhaust has decel pop. This wizard applies proven 
                                enrichment patterns that eliminate it.
                            </p>
                        </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                        <div className="space-y-1.5">
                            <Label className="text-[10px] text-zinc-400">Severity</Label>
                            <Select value={decelSeverity} onValueChange={(v) => setDecelSeverity(v as 'low' | 'medium' | 'high')}>
                                <SelectTrigger className="h-8 text-xs bg-zinc-800/50 border-zinc-700">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {config?.decel_severities.map((opt) => (
                                        <SelectItem key={opt.value} value={opt.value}>
                                            <span className="text-xs">{opt.label}</span>
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-1.5">
                            <Label className="text-[10px] text-zinc-400">Min RPM</Label>
                            <Input
                                type="number"
                                value={decelRpmMin}
                                onChange={(e) => setDecelRpmMin(parseInt(e.target.value) || 1750)}
                                min={1000}
                                max={4000}
                                className="h-8 text-xs bg-zinc-800/50 border-zinc-700"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <Label className="text-[10px] text-zinc-400">Max RPM</Label>
                            <Input
                                type="number"
                                value={decelRpmMax}
                                onChange={(e) => setDecelRpmMax(parseInt(e.target.value) || 5500)}
                                min={3000}
                                max={7000}
                                className="h-8 text-xs bg-zinc-800/50 border-zinc-700"
                            />
                        </div>
                    </div>

                    {/* Preview Results */}
                    {decelPreview && (
                        <div className="p-3 bg-zinc-900/50 rounded-lg border border-zinc-800/50 space-y-2">
                            <div className="flex items-center justify-between">
                                <span className="text-[10px] text-zinc-400 font-medium">Preview</span>
                                <Badge variant="outline" className="text-[10px] text-green-400 border-green-500/40 py-0">
                                    {decelPreview.cells_modified} cells
                                </Badge>
                            </div>

                            <div className="grid grid-cols-3 gap-2">
                                <div className="text-center p-1.5 bg-orange-500/10 rounded">
                                    <div className="text-sm font-bold text-orange-300">
                                        +{decelPreview.enrichment_preview.avg_enrichment}%
                                    </div>
                                    <div className="text-[8px] text-zinc-500">Avg</div>
                                </div>
                                <div className="text-center p-1.5 bg-orange-500/10 rounded">
                                    <div className="text-sm font-bold text-orange-300">
                                        +{decelPreview.enrichment_preview.max_enrichment}%
                                    </div>
                                    <div className="text-[8px] text-zinc-500">Max</div>
                                </div>
                                <div className="text-center p-1.5 bg-orange-500/10 rounded">
                                    <div className="text-sm font-bold text-orange-300">
                                        {decelPreview.rpm_range[0]}-{decelPreview.rpm_range[1]}
                                    </div>
                                    <div className="text-[8px] text-zinc-500">RPM</div>
                                </div>
                            </div>

                            {decelPreview.warnings.length > 0 && (
                                <div className="space-y-1">
                                    {decelPreview.warnings.map((warning, i) => (
                                        <div key={i} className="flex items-center gap-1.5 text-[10px] text-yellow-400">
                                            <AlertTriangle className="h-3 w-3" />
                                            {warning}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    <Button
                        onClick={handleApplyDecelFix}
                        disabled={applyMutation.isPending}
                        className="w-full bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-medium text-xs h-9 shadow-lg shadow-orange-500/20"
                    >
                        {applyMutation.isPending ? (
                            <>
                                <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                                Generating...
                            </>
                        ) : (
                            <>
                                <Download className="mr-2 h-3.5 w-3.5" />
                                Fix Decel Pop & Download
                            </>
                        )}
                    </Button>
                </CollapsibleContent>
            </Collapsible>
        </div>
    );
}

export default StageConfigPanel;

