/**
 * TransientFuelPanel - Transient Fuel Compensation Analysis
 * 
 * Analyzes acceleration/deceleration events in dyno data and generates
 * fuel compensation tables for Power Vision tuning.
 * 
 * Features:
 * - Real-time transient event detection
 * - MAP and TPS rate-based enrichment calculation
 * - Wall-wetting compensation factors
 * - Power Vision export
 */

import { useState, useEffect, useMemo } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Activity, Zap, Download, AlertTriangle, CheckCircle2,
    TrendingUp, TrendingDown, Gauge, Settings2, Info,
    ChevronRight, Loader2, BarChart3, Flame
} from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Badge } from '../ui/badge';
import { Slider } from '../ui/slider';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import { Progress } from '../ui/progress';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '../ui/tooltip';
import {
    getTransientConfig,
    analyzeTransientsFromRun,
    getTransientExportUrl,
    type TransientAnalysisResult,
    type TransientEvent,
    type TransientConfig,
} from '../../api/transient';

interface TransientFuelPanelProps {
    /** Whether transient analysis is enabled */
    enabled: boolean;
    /** Callback when enabled state changes */
    onEnabledChange: (enabled: boolean) => void;
    /** Current run ID to analyze */
    runId?: string;
    /** Whether a dyno run is currently active */
    isCapturing?: boolean;
    /** Current RPM for live detection */
    currentRpm?: number;
    /** Current MAP for live detection */
    currentMap?: number;
    /** Current TPS for live detection */
    currentTps?: number;
    /** Target AFR from settings */
    targetAfr?: number;
    /** Compact mode for settings panel */
    compact?: boolean;
}

// Severity color mapping
const severityColors: Record<string, { bg: string; text: string; border: string }> = {
    mild: { bg: 'bg-green-500/10', text: 'text-green-400', border: 'border-green-500/30' },
    moderate: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/30' },
    aggressive: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30' },
};

// Event type icons
const eventIcons = {
    accel: TrendingUp,
    decel: TrendingDown,
};

export function TransientFuelPanel({
    enabled,
    onEnabledChange,
    runId,
    isCapturing = false,
    currentRpm = 0,
    currentMap = 0,
    currentTps = 0,
    targetAfr = 13.0,
    compact = false,
}: TransientFuelPanelProps) {
    // Configuration state
    const [mapRateThreshold, setMapRateThreshold] = useState(50);
    const [tpsRateThreshold, setTpsRateThreshold] = useState(20);
    const [analysisResult, setAnalysisResult] = useState<TransientAnalysisResult | null>(null);

    // Live detection state (computed from rate of change)
    const [prevMap, setPrevMap] = useState(currentMap);
    const [prevTps, setPrevTps] = useState(currentTps);
    const [mapRate, setMapRate] = useState(0);
    const [tpsRate, setTpsRate] = useState(0);
    const [isTransient, setIsTransient] = useState(false);

    // Fetch configuration
    const { data: config } = useQuery<TransientConfig>({
        queryKey: ['transient-config'],
        queryFn: getTransientConfig,
        staleTime: Infinity,
    });

    // Analysis mutation
    const analyzeMutation = useMutation({
        mutationFn: (params: { runId: string; targetAfr: number; mapRateThreshold: number; tpsRateThreshold: number }) =>
            analyzeTransientsFromRun(params.runId, {
                target_afr: params.targetAfr,
                map_rate_threshold: params.mapRateThreshold,
                tps_rate_threshold: params.tpsRateThreshold,
            }),
        onSuccess: (data) => {
            setAnalysisResult(data);
            toast.success('Transient analysis complete!', {
                description: `Detected ${data.events_detected} transient events`
            });
        },
        onError: (error: Error) => {
            toast.error('Analysis failed', { description: error.message });
        },
    });

    // Calculate live rates
    useEffect(() => {
        if (!enabled || !isCapturing) return;

        // Calculate rates (assuming ~100ms poll interval = 10 samples/sec)
        const dt = 0.1; // seconds
        const newMapRate = (currentMap - prevMap) / dt;
        const newTpsRate = (currentTps - prevTps) / dt;

        setMapRate(newMapRate);
        setTpsRate(newTpsRate);
        setPrevMap(currentMap);
        setPrevTps(currentTps);

        // Check if in transient condition
        const isCurrentlyTransient =
            Math.abs(newMapRate) > mapRateThreshold ||
            Math.abs(newTpsRate) > tpsRateThreshold;
        setIsTransient(isCurrentlyTransient);
    }, [enabled, isCapturing, currentMap, currentTps, prevMap, prevTps, mapRateThreshold, tpsRateThreshold]);

    // Auto-analyze when run completes
    useEffect(() => {
        if (enabled && runId && !isCapturing && !analysisResult) {
            // Small delay to ensure data is saved
            const timer = setTimeout(() => {
                analyzeMutation.mutate({
                    runId,
                    targetAfr,
                    mapRateThreshold,
                    tpsRateThreshold,
                });
            }, 1000);
            return () => clearTimeout(timer);
        }
    }, [enabled, runId, isCapturing]);

    // Handle manual analysis
    const handleAnalyze = () => {
        if (!runId) {
            toast.error('No run selected');
            return;
        }
        analyzeMutation.mutate({
            runId,
            targetAfr,
            mapRateThreshold,
            tpsRateThreshold,
        });
    };

    // Handle download
    const handleDownload = () => {
        if (analysisResult?.run_id) {
            window.open(getTransientExportUrl(analysisResult.run_id), '_blank');
        }
    };

    // Compact mode - just the toggle and status
    if (compact) {
        return (
            <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${enabled ? 'bg-orange-500/20' : 'bg-zinc-800'}`}>
                        <Flame className={`w-4 h-4 ${enabled ? 'text-orange-400' : 'text-zinc-500'}`} />
                    </div>
                    <div>
                        <Label className="text-sm font-medium">Transient Fuel Analysis</Label>
                        <p className="text-xs text-zinc-500">
                            {enabled ? 'Analyzing acceleration/deceleration events' : 'Enable to analyze transients'}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    {enabled && isTransient && (
                        <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30 animate-pulse">
                            <Activity className="w-3 h-3 mr-1" />
                            TRANSIENT
                        </Badge>
                    )}
                    <Switch
                        checked={enabled}
                        onCheckedChange={onEnabledChange}
                    />
                </div>
            </div>
        );
    }

    // Full panel
    return (
        <Card className={`border-orange-500/20 ${enabled ? 'bg-gradient-to-br from-orange-950/20 to-background' : 'bg-zinc-900/50'}`}>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className={`p-2.5 rounded-xl ${enabled ? 'bg-orange-500/20' : 'bg-zinc-800'}`}>
                            <Flame className={`w-5 h-5 ${enabled ? 'text-orange-400' : 'text-zinc-500'}`} />
                        </div>
                        <div>
                            <CardTitle className="text-base">Transient Fuel Compensation</CardTitle>
                            <CardDescription className="text-xs">
                                Analyze throttle response and generate enrichment tables
                            </CardDescription>
                        </div>
                    </div>
                    <Switch
                        checked={enabled}
                        onCheckedChange={onEnabledChange}
                    />
                </div>
            </CardHeader>

            <AnimatePresence>
                {enabled && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                    >
                        <CardContent className="space-y-4 pt-0">
                            {/* Live Status Indicator */}
                            {isCapturing && (
                                <div className={`p-3 rounded-lg border ${isTransient
                                    ? 'border-orange-500/40 bg-orange-500/10'
                                    : 'border-zinc-800 bg-zinc-900/50'
                                    }`}>
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <Activity className={`w-4 h-4 ${isTransient ? 'text-orange-400 animate-pulse' : 'text-zinc-500'}`} />
                                            <span className="text-sm font-medium">
                                                {isTransient ? 'Transient Detected!' : 'Monitoring...'}
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-4 text-xs font-mono">
                                            <span className={mapRate > mapRateThreshold ? 'text-orange-400' : 'text-zinc-500'}>
                                                MAP: {mapRate > 0 ? '+' : ''}{mapRate.toFixed(0)} kPa/s
                                            </span>
                                            <span className={tpsRate > tpsRateThreshold ? 'text-orange-400' : 'text-zinc-500'}>
                                                TPS: {tpsRate > 0 ? '+' : ''}{tpsRate.toFixed(0)} %/s
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Configuration */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-xs text-zinc-400">MAP Rate Threshold</Label>
                                        <span className="text-sm font-mono text-orange-400">{mapRateThreshold} kPa/s</span>
                                    </div>
                                    <Slider
                                        value={[mapRateThreshold]}
                                        onValueChange={([v]) => setMapRateThreshold(v)}
                                        min={config?.ranges.map_rate_threshold.min ?? 20}
                                        max={config?.ranges.map_rate_threshold.max ?? 150}
                                        step={config?.ranges.map_rate_threshold.step ?? 5}
                                        className="w-full"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-xs text-zinc-400">TPS Rate Threshold</Label>
                                        <span className="text-sm font-mono text-orange-400">{tpsRateThreshold} %/s</span>
                                    </div>
                                    <Slider
                                        value={[tpsRateThreshold]}
                                        onValueChange={([v]) => setTpsRateThreshold(v)}
                                        min={config?.ranges.tps_rate_threshold.min ?? 10}
                                        max={config?.ranges.tps_rate_threshold.max ?? 80}
                                        step={config?.ranges.tps_rate_threshold.step ?? 5}
                                        className="w-full"
                                    />
                                </div>
                            </div>

                            {/* Analysis Results */}
                            {analysisResult && (
                                <div className="space-y-3">
                                    {/* Summary Stats */}
                                    <div className="grid grid-cols-4 gap-2">
                                        <div className="p-2 rounded-lg bg-orange-500/10 border border-orange-500/20 text-center">
                                            <div className="text-lg font-bold text-orange-400">
                                                {analysisResult.events_detected}
                                            </div>
                                            <div className="text-[10px] text-zinc-500">Events</div>
                                        </div>
                                        <div className="p-2 rounded-lg bg-green-500/10 border border-green-500/20 text-center">
                                            <div className="text-lg font-bold text-green-400">
                                                {analysisResult.analysis.accel_events}
                                            </div>
                                            <div className="text-[10px] text-zinc-500">Accel</div>
                                        </div>
                                        <div className="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-center">
                                            <div className="text-lg font-bold text-blue-400">
                                                {analysisResult.analysis.decel_events}
                                            </div>
                                            <div className="text-[10px] text-zinc-500">Decel</div>
                                        </div>
                                        <div className="p-2 rounded-lg bg-purple-500/10 border border-purple-500/20 text-center">
                                            <div className="text-lg font-bold text-purple-400">
                                                {analysisResult.analysis.recommendations.length}
                                            </div>
                                            <div className="text-[10px] text-zinc-500">Tips</div>
                                        </div>
                                    </div>

                                    {/* Events List */}
                                    {analysisResult.analysis.events.length > 0 && (
                                        <div className="space-y-1.5 max-h-[150px] overflow-y-auto">
                                            {analysisResult.analysis.events.slice(0, 5).map((event, i) => {
                                                const Icon = eventIcons[event.type];
                                                const colors = severityColors[event.severity];
                                                return (
                                                    <div
                                                        key={i}
                                                        className={`p-2 rounded-lg border ${colors.border} ${colors.bg}`}
                                                    >
                                                        <div className="flex items-center justify-between">
                                                            <div className="flex items-center gap-2">
                                                                <Icon className={`w-3.5 h-3.5 ${colors.text}`} />
                                                                <span className={`text-xs font-medium ${colors.text}`}>
                                                                    {event.type === 'accel' ? 'Acceleration' : 'Deceleration'}
                                                                </span>
                                                                <Badge variant="outline" className={`text-[9px] ${colors.text} ${colors.border}`}>
                                                                    {event.severity}
                                                                </Badge>
                                                            </div>
                                                            <span className="text-[10px] text-zinc-500 font-mono">
                                                                t={event.start_time.toFixed(1)}s
                                                            </span>
                                                        </div>
                                                        <div className="flex items-center gap-3 mt-1 text-[10px] text-zinc-400">
                                                            <span>MAP: {event.peak_map_rate.toFixed(0)} kPa/s</span>
                                                            <span>TPS: {event.peak_tps_rate.toFixed(0)} %/s</span>
                                                            <span>AFR err: {event.afr_error_avg > 0 ? '+' : ''}{event.afr_error_avg.toFixed(2)}</span>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}

                                    {/* Recommendations */}
                                    {analysisResult.analysis.recommendations.length > 0 && (
                                        <div className="space-y-1">
                                            {analysisResult.analysis.recommendations.slice(0, 3).map((rec, i) => (
                                                <div key={i} className="flex items-start gap-2 text-xs text-zinc-400">
                                                    <ChevronRight className="w-3 h-3 mt-0.5 text-orange-400 flex-shrink-0" />
                                                    <span>{rec}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Actions */}
                            <div className="flex items-center justify-between pt-2 border-t border-zinc-800">
                                <TooltipProvider>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <div className="flex items-center gap-1 text-xs text-zinc-500">
                                                <Info className="w-3 h-3" />
                                                <span>Generates enrichment tables for Power Vision</span>
                                            </div>
                                        </TooltipTrigger>
                                        <TooltipContent>
                                            <p>Analyzes MAP and TPS rate of change during</p>
                                            <p>acceleration to calculate fuel compensation</p>
                                        </TooltipContent>
                                    </Tooltip>
                                </TooltipProvider>

                                <div className="flex items-center gap-2">
                                    {analysisResult && (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={handleDownload}
                                            className="border-orange-500/30 text-orange-400 hover:bg-orange-500/10"
                                        >
                                            <Download className="w-3 h-3 mr-1" />
                                            Export
                                        </Button>
                                    )}
                                    <Button
                                        size="sm"
                                        onClick={handleAnalyze}
                                        disabled={!runId || analyzeMutation.isPending}
                                        className="bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-500 hover:to-red-500"
                                    >
                                        {analyzeMutation.isPending ? (
                                            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                        ) : (
                                            <Zap className="w-3 h-3 mr-1" />
                                        )}
                                        Analyze
                                    </Button>
                                </div>
                            </div>
                        </CardContent>
                    </motion.div>
                )}
            </AnimatePresence>
        </Card>
    );
}

export default TransientFuelPanel;

