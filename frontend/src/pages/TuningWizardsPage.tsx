import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { toast } from '@/lib/toast';
import {
    Flame,
    Gauge,
    Thermometer,
    Settings2,
    Download,
    AlertTriangle,
    CheckCircle2,
    ChevronRight,
    Info,
    Loader2,
    Sparkles,
    BarChart3,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';
import {
    getWizardConfig,
    previewDecelFix,
    applyDecelFix,
    quickHeatCheck,
    DecelPreviewResult,
    QuickHeatCheckResult,
} from '../api/wizards';

export default function TuningWizardsPage() {
    const [selectedStage, setSelectedStage] = useState<string>('stock');
    const [selectedCam, setSelectedCam] = useState<string>('stock');
    const [decelSeverity, setDecelSeverity] = useState<'low' | 'medium' | 'high'>('medium');
    const [decelRpmMin, setDecelRpmMin] = useState(1750);
    const [decelRpmMax, setDecelRpmMax] = useState(5500);
    const [decelPreview, setDecelPreview] = useState<DecelPreviewResult | null>(null);

    // Heat soak quick check
    const [hpValues, setHpValues] = useState<string>('');
    const [heatCheckResult, setHeatCheckResult] = useState<QuickHeatCheckResult | null>(null);

    // Fetch wizard config
    const { data: config, isLoading: configLoading } = useQuery({
        queryKey: ['wizardConfig'],
        queryFn: getWizardConfig,
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
            toast.success('Decel Pop Fix applied successfully!');
            // Trigger download
            window.open(data.download_url, '_blank');
        },
        onError: (error: Error) => {
            toast.error(error.message ?? 'Failed to apply decel fix');
        },
    });

    // Heat check mutation
    const heatCheckMutation = useMutation({
        mutationFn: (values: number[]) => quickHeatCheck(values),
        onSuccess: (data) => {
            setHeatCheckResult(data);
        },
        onError: (error: Error) => {
            toast.error(error.message ?? 'Failed to analyze heat soak');
        },
    });

    // Auto-preview when decel params change
    useEffect(() => {
        if (config) {
            previewMutation.mutate({
                severity: decelSeverity,
                rpm_min: decelRpmMin,
                rpm_max: decelRpmMax,
                cam_family: selectedCam,
            });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [decelSeverity, decelRpmMin, decelRpmMax, selectedCam, config]);

    const handleApplyDecelFix = () => {
        applyMutation.mutate({
            severity: decelSeverity,
            rpm_min: decelRpmMin,
            rpm_max: decelRpmMax,
            cam_family: selectedCam,
        });
    };

    const handleHeatCheck = () => {
        const values = hpValues
            .split(',')
            .map((v) => parseFloat(v.trim()))
            .filter((v) => !isNaN(v));

        if (values.length < 2) {
            toast.error('Enter at least 2 HP values separated by commas');
            return;
        }

        heatCheckMutation.mutate(values);
    };

    const selectedStagePreset = config?.stages.find((s) => s.level === selectedStage);
    const selectedCamPreset = config?.cams.find((c) => c.family === selectedCam);

    if (configLoading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="text-center space-y-4">
                    <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto" />
                    <p className="text-muted-foreground">Loading Tuning Wizards...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Hero Header */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-orange-500/20 via-amber-500/10 to-red-500/20 border border-orange-500/20 p-8">
                <div className="absolute inset-0 bg-grid-white/5 [mask-image:radial-gradient(ellipse_at_center,transparent_20%,black)]" />
                <div className="relative">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="p-3 bg-orange-500/20 rounded-xl">
                            <Sparkles className="h-8 w-8 text-orange-400" />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold tracking-tight">Tuning Wizards</h1>
                            <p className="text-muted-foreground">One-click solutions for common V-twin tuning problems</p>
                        </div>
                    </div>
                    <div className="flex flex-wrap gap-2 mt-4">
                        <Badge variant="outline" className="bg-orange-500/10 text-orange-300 border-orange-500/30">
                            <Flame className="h-3 w-3 mr-1" /> Decel Pop Fix
                        </Badge>
                        <Badge variant="outline" className="bg-blue-500/10 text-blue-300 border-blue-500/30">
                            <Gauge className="h-3 w-3 mr-1" /> Stage Config
                        </Badge>
                        <Badge variant="outline" className="bg-purple-500/10 text-purple-300 border-purple-500/30">
                            <Settings2 className="h-3 w-3 mr-1" /> Cam Presets
                        </Badge>
                        <Badge variant="outline" className="bg-red-500/10 text-red-300 border-red-500/30">
                            <Thermometer className="h-3 w-3 mr-1" /> Heat Soak
                        </Badge>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* ================================================================ */}
                {/* DECEL POP WIZARD - THE HERO FEATURE */}
                {/* ================================================================ */}
                <Card className="lg:col-span-2 border-orange-500/30 bg-gradient-to-br from-orange-950/30 to-background">
                    <CardHeader className="pb-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="p-2.5 bg-orange-500/20 rounded-lg">
                                    <Flame className="h-6 w-6 text-orange-400" />
                                </div>
                                <div>
                                    <CardTitle className="text-xl">Decel Pop Wizard</CardTitle>
                                    <CardDescription>Eliminate exhaust popping with one click</CardDescription>
                                </div>
                            </div>
                            <Badge className="bg-orange-500/20 text-orange-300 border-orange-500/40">
                                #1 Requested Feature
                            </Badge>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <Alert className="bg-orange-500/5 border-orange-500/20">
                            <Info className="h-4 w-4 text-orange-400" />
                            <AlertTitle className="text-orange-300">Universal Problem, Zero Automation</AlertTitle>
                            <AlertDescription className="text-orange-200/70">
                                Every Harley with aftermarket exhaust has decel pop. Power Vision can't autotune this.
                                This wizard applies proven enrichment patterns that work.
                            </AlertDescription>
                        </Alert>

                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                            <div className="space-y-2">
                                <Label className="text-sm font-medium">Severity</Label>
                                <Select value={decelSeverity} onValueChange={(v) => setDecelSeverity(v as 'low' | 'medium' | 'high')}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {config?.decel_severities.map((opt) => (
                                            <SelectItem key={opt.value} value={opt.value}>
                                                <div className="flex flex-col">
                                                    <span className="font-medium">{opt.label}</span>
                                                    <span className="text-xs text-muted-foreground">{opt.fuel_economy_impact}</span>
                                                </div>
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="space-y-2">
                                <Label className="text-sm font-medium">Cam Profile</Label>
                                <Select value={selectedCam} onValueChange={setSelectedCam}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {config?.cams.map((cam) => (
                                            <SelectItem key={cam.family} value={cam.family}>
                                                {cam.display_name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="space-y-2">
                                <Label className="text-sm font-medium">Min RPM</Label>
                                <Input
                                    type="number"
                                    value={decelRpmMin}
                                    onChange={(e) => setDecelRpmMin(parseInt(e.target.value) || 1750)}
                                    min={1000}
                                    max={4000}
                                />
                            </div>

                            <div className="space-y-2">
                                <Label className="text-sm font-medium">Max RPM</Label>
                                <Input
                                    type="number"
                                    value={decelRpmMax}
                                    onChange={(e) => setDecelRpmMax(parseInt(e.target.value) || 5500)}
                                    min={3000}
                                    max={7000}
                                />
                            </div>
                        </div>

                        {/* Preview Results */}
                        {decelPreview && (
                            <div className="space-y-4 p-4 bg-black/20 rounded-lg border border-orange-500/10">
                                <div className="flex items-center justify-between">
                                    <h4 className="font-semibold text-orange-300">Preview</h4>
                                    <Badge variant="outline" className="text-green-400 border-green-500/40">
                                        {decelPreview.cells_modified} cells to modify
                                    </Badge>
                                </div>

                                <div className="grid grid-cols-3 gap-4">
                                    <div className="text-center p-3 bg-orange-500/10 rounded-lg">
                                        <div className="text-2xl font-bold text-orange-300">
                                            +{decelPreview.enrichment_preview.avg_enrichment}%
                                        </div>
                                        <div className="text-xs text-muted-foreground">Avg Enrichment</div>
                                    </div>
                                    <div className="text-center p-3 bg-orange-500/10 rounded-lg">
                                        <div className="text-2xl font-bold text-orange-300">
                                            +{decelPreview.enrichment_preview.max_enrichment}%
                                        </div>
                                        <div className="text-xs text-muted-foreground">Max Enrichment</div>
                                    </div>
                                    <div className="text-center p-3 bg-orange-500/10 rounded-lg">
                                        <div className="text-2xl font-bold text-orange-300">
                                            {decelPreview.rpm_range[0]}-{decelPreview.rpm_range[1]}
                                        </div>
                                        <div className="text-xs text-muted-foreground">RPM Range</div>
                                    </div>
                                </div>

                                {/* RPM Zone Breakdown */}
                                <div className="space-y-2">
                                    <h5 className="text-sm font-medium text-muted-foreground">Enrichment by RPM Zone</h5>
                                    <div className="grid grid-cols-4 gap-2">
                                        {Object.entries(decelPreview.enrichment_preview.by_rpm_zone || {}).map(([zone, pct]) => (
                                            <div key={zone} className="text-center p-2 bg-black/30 rounded">
                                                <div className="text-sm font-mono text-orange-300">+{pct}%</div>
                                                <div className="text-xs text-muted-foreground">{zone} RPM</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Warnings */}
                                {decelPreview.warnings.length > 0 && (
                                    <div className="space-y-1">
                                        {decelPreview.warnings.map((warning, i) => (
                                            <div key={i} className="flex items-center gap-2 text-sm text-yellow-400">
                                                <AlertTriangle className="h-3 w-3" />
                                                {warning}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </CardContent>
                    <CardFooter className="flex justify-between items-center border-t border-orange-500/10 pt-6">
                        <div className="text-sm text-muted-foreground">
                            Generates CSV overlay for VE table
                        </div>
                        <Button
                            size="lg"
                            onClick={handleApplyDecelFix}
                            disabled={applyMutation.isPending}
                            className="bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-semibold shadow-lg shadow-orange-500/25 transition-all hover:shadow-orange-500/40"
                        >
                            {applyMutation.isPending ? (
                                <>
                                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                                    Generating...
                                </>
                            ) : (
                                <>
                                    <Download className="mr-2 h-5 w-5" />
                                    Fix Decel Pop &amp; Download
                                </>
                            )}
                        </Button>
                    </CardFooter>
                </Card>

                {/* ================================================================ */}
                {/* STAGE CONFIGURATION */}
                {/* ================================================================ */}
                <Card className="border-blue-500/30 bg-gradient-to-br from-blue-950/30 to-background">
                    <CardHeader>
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-blue-500/20 rounded-lg">
                                <Gauge className="h-5 w-5 text-blue-400" />
                            </div>
                            <div>
                                <CardTitle className="text-lg">Stage Configuration</CardTitle>
                                <CardDescription>Set VE expectations by build level</CardDescription>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Select value={selectedStage} onValueChange={setSelectedStage}>
                            <SelectTrigger className="h-12">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {config?.stages.map((stage) => (
                                    <SelectItem key={stage.level} value={stage.level}>
                                        <div className="flex items-center gap-2">
                                            <span className="font-medium">{stage.display_name}</span>
                                            <Badge variant="secondary" className="text-xs">
                                                {stage.ve_scaling.percentage_range}
                                            </Badge>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>

                        {selectedStagePreset && (
                            <div className="space-y-4 p-4 bg-black/20 rounded-lg">
                                <p className="text-sm text-muted-foreground">{selectedStagePreset.description}</p>

                                <div className="grid grid-cols-3 gap-3">
                                    <div className="text-center p-2 bg-blue-500/10 rounded">
                                        <div className="text-lg font-bold text-blue-300">
                                            {selectedStagePreset.afr_targets.cruise}
                                        </div>
                                        <div className="text-xs text-muted-foreground">Cruise AFR</div>
                                    </div>
                                    <div className="text-center p-2 bg-blue-500/10 rounded">
                                        <div className="text-lg font-bold text-blue-300">
                                            {selectedStagePreset.afr_targets.wot}
                                        </div>
                                        <div className="text-xs text-muted-foreground">WOT AFR</div>
                                    </div>
                                    <div className="text-center p-2 bg-blue-500/10 rounded">
                                        <div className="text-lg font-bold text-blue-300">
                                            ±{selectedStagePreset.tuning_params.suggested_clamp}%
                                        </div>
                                        <div className="text-xs text-muted-foreground">Clamp</div>
                                    </div>
                                </div>

                                <Separator className="bg-blue-500/20" />

                                <div className="space-y-1">
                                    {selectedStagePreset.notes.slice(0, 3).map((note, i) => (
                                        <div key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                                            <ChevronRight className="h-3 w-3 mt-0.5 text-blue-400" />
                                            {note}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* ================================================================ */}
                {/* CAM FAMILY PRESETS */}
                {/* ================================================================ */}
                <Card className="border-purple-500/30 bg-gradient-to-br from-purple-950/30 to-background">
                    <CardHeader>
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-purple-500/20 rounded-lg">
                                <Settings2 className="h-5 w-5 text-purple-400" />
                            </div>
                            <div>
                                <CardTitle className="text-lg">Cam Family Presets</CardTitle>
                                <CardDescription>Idle VE and AFR by cam profile</CardDescription>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Select value={selectedCam} onValueChange={setSelectedCam}>
                            <SelectTrigger className="h-12">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {config?.cams.map((cam) => (
                                    <SelectItem key={cam.family} value={cam.family}>
                                        <div className="flex items-center gap-2">
                                            <span className="font-medium">{cam.display_name}</span>
                                            <Badge variant="secondary" className="text-xs">
                                                {cam.lift_range} lift
                                            </Badge>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>

                        {selectedCamPreset && (
                            <div className="space-y-4 p-4 bg-black/20 rounded-lg">
                                <p className="text-sm text-muted-foreground">{selectedCamPreset.description}</p>

                                <div className="grid grid-cols-2 gap-3">
                                    <div className="text-center p-2 bg-purple-500/10 rounded">
                                        <div className="text-lg font-bold text-purple-300">
                                            +{selectedCamPreset.idle_characteristics.ve_offset_pct}%
                                        </div>
                                        <div className="text-xs text-muted-foreground">Idle VE Offset</div>
                                    </div>
                                    <div className="text-center p-2 bg-purple-500/10 rounded">
                                        <div className="text-lg font-bold text-purple-300">
                                            {selectedCamPreset.idle_characteristics.rpm_target}
                                        </div>
                                        <div className="text-xs text-muted-foreground">Target Idle RPM</div>
                                    </div>
                                    <div className="text-center p-2 bg-purple-500/10 rounded">
                                        <div className="text-lg font-bold text-purple-300">
                                            {selectedCamPreset.idle_characteristics.vacuum_expected_hg}"
                                        </div>
                                        <div className="text-xs text-muted-foreground">Expected Vacuum</div>
                                    </div>
                                    <div className="text-center p-2 bg-purple-500/10 rounded">
                                        <div className="text-lg font-bold text-purple-300">
                                            {selectedCamPreset.afr_targets.idle}
                                        </div>
                                        <div className="text-xs text-muted-foreground">Idle AFR</div>
                                    </div>
                                </div>

                                <Separator className="bg-purple-500/20" />

                                <div className="space-y-1">
                                    {selectedCamPreset.notes.slice(0, 3).map((note, i) => (
                                        <div key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                                            <ChevronRight className="h-3 w-3 mt-0.5 text-purple-400" />
                                            {note}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* ================================================================ */}
                {/* HEAT SOAK WARNING */}
                {/* ================================================================ */}
                <Card className="lg:col-span-2 border-red-500/30 bg-gradient-to-br from-red-950/30 to-background">
                    <CardHeader>
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-red-500/20 rounded-lg">
                                <Thermometer className="h-5 w-5 text-red-400" />
                            </div>
                            <div>
                                <CardTitle className="text-lg">Heat Soak Warning System</CardTitle>
                                <CardDescription>Track HP degradation across sequential pulls</CardDescription>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <Alert className="bg-red-500/5 border-red-500/20">
                            <Thermometer className="h-4 w-4 text-red-400" />
                            <AlertTitle className="text-red-300">2-8 HP Variation is Normal</AlertTitle>
                            <AlertDescription className="text-red-200/70">
                                Air-cooled V-twins lose power as IAT rises. This tool detects when data becomes
                                unreliable due to heat soak so you can cool down before tuning.
                            </AlertDescription>
                        </Alert>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <Label className="text-sm font-medium">Enter HP values from sequential pulls</Label>
                                    <Input
                                        placeholder="e.g., 95.2, 94.1, 92.8, 91.5"
                                        value={hpValues}
                                        onChange={(e) => setHpValues(e.target.value)}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Comma-separated HP values in order of pulls
                                    </p>
                                </div>
                                <Button
                                    onClick={handleHeatCheck}
                                    disabled={heatCheckMutation.isPending || !hpValues.trim()}
                                    className="w-full"
                                    variant="outline"
                                >
                                    {heatCheckMutation.isPending ? (
                                        <>
                                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                            Analyzing...
                                        </>
                                    ) : (
                                        <>
                                            <BarChart3 className="mr-2 h-4 w-4" />
                                            Check Heat Soak
                                        </>
                                    )}
                                </Button>
                            </div>

                            {/* Results */}
                            <div className="p-4 bg-black/20 rounded-lg border border-red-500/10 min-h-[200px]">
                                {!heatCheckResult ? (
                                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                                        <Thermometer className="h-8 w-8 mb-2 opacity-50" />
                                        <p className="text-sm">Enter HP values to analyze</p>
                                    </div>
                                ) : heatCheckResult.status === 'insufficient_data' ? (
                                    <div className="flex flex-col items-center justify-center h-full text-yellow-400">
                                        <AlertTriangle className="h-8 w-8 mb-2" />
                                        <p className="text-sm">{heatCheckResult.recommendation}</p>
                                    </div>
                                ) : (
                                    <div className="space-y-4">
                                        <div className="flex items-center gap-3">
                                            {heatCheckResult.status === 'heat_soaked' ? (
                                                <>
                                                    <div className="p-2 bg-red-500/20 rounded-full">
                                                        <AlertTriangle className="h-6 w-6 text-red-400" />
                                                    </div>
                                                    <div>
                                                        <div className="font-semibold text-red-400">Heat Soak Detected</div>
                                                        <div className="text-sm text-muted-foreground">
                                                            {heatCheckResult.hp_degradation_pct?.toFixed(1)}% HP degradation
                                                        </div>
                                                    </div>
                                                </>
                                            ) : (
                                                <>
                                                    <div className="p-2 bg-green-500/20 rounded-full">
                                                        <CheckCircle2 className="h-6 w-6 text-green-400" />
                                                    </div>
                                                    <div>
                                                        <div className="font-semibold text-green-400">Data is Reliable</div>
                                                        <div className="text-sm text-muted-foreground">
                                                            {heatCheckResult.hp_degradation_pct?.toFixed(1)}% variation (acceptable)
                                                        </div>
                                                    </div>
                                                </>
                                            )}
                                        </div>

                                        <Separator className="bg-red-500/20" />

                                        <p className="text-sm">{heatCheckResult.recommendation}</p>

                                        {heatCheckResult.warnings?.length > 0 && (
                                            <div className="space-y-1">
                                                {heatCheckResult.warnings.map((warning: string, i: number) => (
                                                    <div key={i} className="flex items-center gap-2 text-xs text-yellow-400">
                                                        <AlertTriangle className="h-3 w-3" />
                                                        {warning}
                                                    </div>
                                                ))}
                                            </div>
                                        )}

                                        {heatCheckResult.use_baseline_pull && (
                                            <Badge variant="outline" className="text-green-400 border-green-500/40">
                                                Use Pull #{heatCheckResult.use_baseline_pull} as baseline
                                            </Badge>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

