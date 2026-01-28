/**
 * LiveAnalysisOverlay - Real-time analysis feedback during JetDrive capture
 * 
 * Displays:
 * - Coverage percentage and active cell
 * - VE delta (AFR error) summary
 * - Quality score
 * - Active alerts
 * 
 * Polls backend at 1Hz to avoid impacting 20Hz UI updates.
 */

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
    Activity, AlertTriangle, CheckCircle, XCircle, RefreshCw,
    Target, Gauge, Thermometer, BarChart3, Power
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { cn } from '../../lib/utils';

// =============================================================================
// Types
// =============================================================================

interface CoverageCell {
    rpm_min: number;
    rpm_max: number;
    map_min: number;
    map_max: number;
    hit_count: number;
    afr_error_mean?: number | null;
}

interface CoverageStats {
    cells: CoverageCell[];
    total_hits: number;
    cells_hit: number;
    total_cells: number;
    coverage_pct: number;
    active_cell: CoverageCell | null;
}

interface VEDeltaStats {
    cells: Array<{
        rpm_min: number;
        rpm_max: number;
        map_min: number;
        map_max: number;
        afr_error_mean: number;
        sample_count: number;
    }>;
    mean_error: number;
    sample_count: number;
    target_afr: number;
}

interface QualityMetrics {
    score: number;
    channel_freshness: Record<string, number>;
    channel_variance: Record<string, number | null>;
    missing_channels: string[];
}

interface Alert {
    type: string;
    severity: 'info' | 'warning' | 'critical';
    channel: string;
    message: string;
    timestamp: number;
    value?: number | null;
}

interface RealtimeAnalysisState {
    success: boolean;
    enabled: boolean;
    coverage?: CoverageStats;
    ve_delta?: VEDeltaStats;
    quality?: QualityMetrics;
    alerts?: Alert[];
    uptime_sec?: number;
    message?: string;
}

// =============================================================================
// Props
// =============================================================================

interface LiveAnalysisOverlayProps {
    apiUrl?: string;
    enabled?: boolean;
    refreshInterval?: number;
    onEnableChange?: (enabled: boolean) => void;
}

// =============================================================================
// Helper Components
// =============================================================================

function AlertBadge({ severity }: { severity: Alert['severity'] }) {
    const variants: Record<Alert['severity'], { className: string; icon: typeof AlertTriangle }> = {
        info: { className: 'bg-blue-500/20 text-blue-400 border-blue-500/30', icon: Activity },
        warning: { className: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30', icon: AlertTriangle },
        critical: { className: 'bg-red-500/20 text-red-400 border-red-500/30', icon: XCircle },
    };
    
    const { className, icon: Icon } = variants[severity];
    
    return (
        <Badge variant="outline" className={className}>
            <Icon className="w-3 h-3 mr-1" />
            {severity.toUpperCase()}
        </Badge>
    );
}

function QualityBadge({ score }: { score: number }) {
    let variant: 'default' | 'secondary' | 'destructive' = 'default';
    let className = '';
    
    if (score >= 80) {
        className = 'bg-green-500/20 text-green-400 border-green-500/30';
    } else if (score >= 50) {
        className = 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    } else {
        className = 'bg-red-500/20 text-red-400 border-red-500/30';
    }
    
    return (
        <Badge variant="outline" className={className}>
            {score.toFixed(0)}/100
        </Badge>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export function LiveAnalysisOverlay({
    apiUrl = 'http://127.0.0.1:5001/api/jetdrive',
    enabled = true,
    refreshInterval = 1000,
    onEnableChange,
}: LiveAnalysisOverlayProps) {
    const queryClient = useQueryClient();
    const [isAnalysisEnabled, setIsAnalysisEnabled] = useState(false);

    // Fetch analysis state
    const { data: analysis, isLoading, error, refetch } = useQuery<RealtimeAnalysisState>({
        queryKey: ['jetdrive-realtime-analysis', apiUrl],
        queryFn: async () => {
            const res = await fetch(`${apiUrl}/realtime/analysis`);
            if (!res.ok) throw new Error('Failed to fetch analysis');
            return res.json();
        },
        refetchInterval: enabled ? refreshInterval : false,
        enabled,
    });

    // Enable analysis mutation
    const enableMutation = useMutation({
        mutationFn: async (targetAfr: number = 14.7) => {
            const res = await fetch(`${apiUrl}/realtime/enable?target_afr=${targetAfr}`, {
                method: 'POST',
            });
            if (!res.ok) throw new Error('Failed to enable analysis');
            return res.json();
        },
        onSuccess: () => {
            setIsAnalysisEnabled(true);
            queryClient.invalidateQueries({ queryKey: ['jetdrive-realtime-analysis'] });
        },
    });

    // Disable analysis mutation
    const disableMutation = useMutation({
        mutationFn: async () => {
            const res = await fetch(`${apiUrl}/realtime/disable`, { method: 'POST' });
            if (!res.ok) throw new Error('Failed to disable analysis');
            return res.json();
        },
        onSuccess: () => {
            setIsAnalysisEnabled(false);
            queryClient.invalidateQueries({ queryKey: ['jetdrive-realtime-analysis'] });
        },
    });

    // Reset analysis mutation
    const resetMutation = useMutation({
        mutationFn: async () => {
            const res = await fetch(`${apiUrl}/realtime/reset`, { method: 'POST' });
            if (!res.ok) throw new Error('Failed to reset analysis');
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['jetdrive-realtime-analysis'] });
        },
    });

    // Update local state when analysis state changes
    useEffect(() => {
        if (analysis?.enabled !== undefined) {
            setIsAnalysisEnabled(analysis.enabled);
        }
    }, [analysis?.enabled]);

    // Handle toggle
    const handleToggle = () => {
        if (isAnalysisEnabled) {
            disableMutation.mutate();
        } else {
            enableMutation.mutate(14.7);
        }
        onEnableChange?.(!isAnalysisEnabled);
    };

    // Not enabled state
    if (!analysis?.enabled) {
        return (
            <Card className="bg-gray-900/80 backdrop-blur border-gray-700">
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-lg flex items-center gap-2">
                            <BarChart3 className="h-5 w-5 text-blue-500" />
                            Live Analysis
                        </CardTitle>
                        <Badge variant="outline" className="text-gray-400">
                            Disabled
                        </Badge>
                    </div>
                </CardHeader>
                <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                        Enable real-time analysis to see coverage, VE delta, and quality metrics during capture.
                    </p>
                    <Button 
                        onClick={() => enableMutation.mutate(14.7)}
                        disabled={enableMutation.isPending}
                        className="w-full"
                    >
                        <Power className="h-4 w-4 mr-2" />
                        {enableMutation.isPending ? 'Enabling...' : 'Enable Analysis'}
                    </Button>
                </CardContent>
            </Card>
        );
    }

    const { coverage, ve_delta, quality, alerts } = analysis;

    return (
        <Card className="bg-gray-900/80 backdrop-blur border-gray-700">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <BarChart3 className="h-5 w-5 text-blue-500" />
                        Live Analysis
                    </CardTitle>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => resetMutation.mutate()}
                            disabled={resetMutation.isPending}
                            title="Reset analysis"
                        >
                            <RefreshCw className={cn("h-4 w-4", resetMutation.isPending && "animate-spin")} />
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleToggle}
                            disabled={disableMutation.isPending}
                        >
                            {disableMutation.isPending ? 'Disabling...' : 'Disable'}
                        </Button>
                    </div>
                </div>
                {analysis.uptime_sec !== undefined && (
                    <CardDescription>
                        Running for {analysis.uptime_sec.toFixed(0)}s
                    </CardDescription>
                )}
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Coverage Section */}
                {coverage && (
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-medium flex items-center gap-2">
                                <Target className="h-4 w-4 text-green-500" />
                                Coverage
                            </span>
                            <Badge variant="secondary">
                                {coverage.coverage_pct.toFixed(1)}%
                            </Badge>
                        </div>
                        <Progress value={coverage.coverage_pct} className="h-2" />
                        <div className="text-xs text-muted-foreground">
                            {coverage.total_hits.toLocaleString()} samples across {coverage.cells_hit} / {coverage.total_cells} cells
                        </div>
                    </div>
                )}

                {/* Active Cell */}
                {coverage?.active_cell && (
                    <div className="p-3 rounded-lg bg-gray-800/50 border border-gray-700">
                        <div className="text-xs text-muted-foreground mb-1">Active Cell</div>
                        <div className="font-mono text-sm">
                            RPM: {coverage.active_cell.rpm_min}-{coverage.active_cell.rpm_max} | 
                            MAP: {coverage.active_cell.map_min}-{coverage.active_cell.map_max} kPa
                        </div>
                        <div className="text-xs mt-1 flex gap-4">
                            <span>Hits: {coverage.active_cell.hit_count}</span>
                            {coverage.active_cell.afr_error_mean !== null && coverage.active_cell.afr_error_mean !== undefined && (
                                <span className={cn(
                                    coverage.active_cell.afr_error_mean > 0.5 ? 'text-yellow-400' :
                                    coverage.active_cell.afr_error_mean < -0.5 ? 'text-blue-400' :
                                    'text-green-400'
                                )}>
                                    AFR Error: {coverage.active_cell.afr_error_mean > 0 ? '+' : ''}{coverage.active_cell.afr_error_mean.toFixed(2)}
                                </span>
                            )}
                        </div>
                    </div>
                )}

                {/* VE Delta Summary */}
                {ve_delta && ve_delta.sample_count > 0 && (
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-medium flex items-center gap-2">
                                <Gauge className="h-4 w-4 text-orange-500" />
                                VE Delta (AFR Error)
                            </span>
                            <Badge 
                                variant="outline"
                                className={cn(
                                    Math.abs(ve_delta.mean_error) < 0.3 ? 'text-green-400 border-green-500/30' :
                                    Math.abs(ve_delta.mean_error) < 0.7 ? 'text-yellow-400 border-yellow-500/30' :
                                    'text-red-400 border-red-500/30'
                                )}
                            >
                                {ve_delta.mean_error > 0 ? '+' : ''}{ve_delta.mean_error.toFixed(2)} AFR
                            </Badge>
                        </div>
                        <div className="text-xs text-muted-foreground">
                            Target: {ve_delta.target_afr} AFR | {ve_delta.sample_count.toLocaleString()} samples
                        </div>
                    </div>
                )}

                {/* Quality Score */}
                {quality && (
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-medium flex items-center gap-2">
                                <CheckCircle className="h-4 w-4 text-blue-500" />
                                Quality
                            </span>
                            <QualityBadge score={quality.score} />
                        </div>
                        <Progress 
                            value={quality.score} 
                            className={cn(
                                "h-2",
                                quality.score >= 80 ? '[&>div]:bg-green-500' :
                                quality.score >= 50 ? '[&>div]:bg-yellow-500' :
                                '[&>div]:bg-red-500'
                            )}
                        />
                        {quality.missing_channels.length > 0 && (
                            <div className="text-xs text-yellow-400">
                                Missing: {quality.missing_channels.join(', ')}
                            </div>
                        )}
                    </div>
                )}

                {/* Alerts */}
                {alerts && alerts.length > 0 && (
                    <div className="space-y-2">
                        <div className="text-sm font-medium flex items-center gap-2">
                            <AlertTriangle className="h-4 w-4 text-yellow-500" />
                            Alerts ({alerts.length})
                        </div>
                        <div className="space-y-2 max-h-40 overflow-y-auto">
                            {alerts.slice(0, 5).map((alert, i) => (
                                <div 
                                    key={i} 
                                    className={cn(
                                        "p-2 rounded text-xs border",
                                        alert.severity === 'critical' ? 'bg-red-500/10 border-red-500/30' :
                                        alert.severity === 'warning' ? 'bg-yellow-500/10 border-yellow-500/30' :
                                        'bg-blue-500/10 border-blue-500/30'
                                    )}
                                >
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="font-medium">{alert.type.replace(/_/g, ' ')}</span>
                                        <AlertBadge severity={alert.severity} />
                                    </div>
                                    <div className="text-muted-foreground">{alert.message}</div>
                                </div>
                            ))}
                            {alerts.length > 5 && (
                                <div className="text-xs text-muted-foreground text-center">
                                    +{alerts.length - 5} more alerts
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* No alerts state */}
                {(!alerts || alerts.length === 0) && coverage && coverage.total_hits > 0 && (
                    <div className="flex items-center gap-2 text-xs text-green-400">
                        <CheckCircle className="h-4 w-4" />
                        No active alerts
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

export default LiveAnalysisOverlay;
