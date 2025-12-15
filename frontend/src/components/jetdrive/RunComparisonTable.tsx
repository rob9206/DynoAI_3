/**
 * Run Comparison Table Component
 * 
 * Displays multiple dyno runs side-by-side for easy comparison of:
 * - Peak HP/Torque
 * - AFR status
 * - VE corrections
 * - Run metadata
 */

import { useMemo } from 'react';
import { TrendingUp, TrendingDown, Minus, CheckCircle2, AlertTriangle } from 'lucide-react';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '../ui/table';
import { Badge } from '../ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';

interface RunData {
    run_id: string;
    timestamp: string;
    peak_hp: number;
    peak_tq: number;
    status: string;
    manifest?: {
        analysis?: {
            peak_hp_rpm?: number;
            peak_tq_rpm?: number;
            ok_cells?: number;
            lean_cells?: number;
            rich_cells?: number;
            overall_status?: string;
            duration_ms?: number;
        };
    };
}

interface RunComparisonTableProps {
    runs: RunData[];
    selectedRuns?: string[];
    onRunClick?: (runId: string) => void;
    maxRuns?: number;
}

export function RunComparisonTable({
    runs,
    selectedRuns = [],
    onRunClick,
    maxRuns = 5
}: RunComparisonTableProps) {
    // Filter to selected runs or take most recent
    const compareRuns = useMemo(() => {
        if (selectedRuns.length > 0) {
            return runs.filter(r => selectedRuns.includes(r.run_id)).slice(0, maxRuns);
        }
        return runs.slice(0, maxRuns);
    }, [runs, selectedRuns, maxRuns]);

    if (compareRuns.length === 0) {
        return null;
    }

    // Calculate deltas from baseline (first run)
    const baseline = compareRuns[0];

    // Find best run (highest HP)
    const bestRun = useMemo(() => {
        return compareRuns.reduce((best, run) => 
            run.peak_hp > best.peak_hp ? run : best
        , compareRuns[0]);
    }, [compareRuns]);

    const getHpDelta = (run: RunData) => {
        if (run === baseline) return null;
        return run.peak_hp - baseline.peak_hp;
    };

    const getTqDelta = (run: RunData) => {
        if (run === baseline) return null;
        return run.peak_tq - baseline.peak_tq;
    };

    const DeltaBadge = ({ value, baselineValue }: { value: number | null; baselineValue: number }) => {
        if (value === null) {
            return <Badge variant="outline" className="bg-zinc-800/50 text-zinc-400 border-zinc-700 text-xs">BASELINE</Badge>;
        }

        const isPositive = value > 0;
        const isNeutral = Math.abs(value) < 0.5;
        const percentChange = baselineValue > 0 ? (value / baselineValue) * 100 : 0;

        if (isNeutral) {
            return (
                <div className="flex flex-col items-center gap-0.5">
                    <div className="flex items-center gap-1 text-zinc-500 text-xs">
                        <Minus className="w-3 h-3" />
                        <span>{value.toFixed(1)}</span>
                    </div>
                    <span className="text-[10px] text-zinc-600">
                        ({percentChange > 0 ? '+' : ''}{percentChange.toFixed(1)}%)
                    </span>
                </div>
            );
        }

        return (
            <div className="flex flex-col items-center gap-0.5">
                <div className={`flex items-center gap-1 text-xs ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                    {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    <span>{isPositive ? '+' : ''}{value.toFixed(1)}</span>
                </div>
                <span className={`text-[10px] ${isPositive ? 'text-green-500' : 'text-red-500'}`}>
                    ({percentChange > 0 ? '+' : ''}{percentChange.toFixed(1)}%)
                </span>
            </div>
        );
    };

    const StatusBadge = ({ status }: { status: string }) => {
        const statusStyles: Record<string, string> = {
            'LEAN': 'bg-red-500/20 text-red-400 border-red-500/30',
            'RICH': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
            'BALANCED': 'bg-green-500/20 text-green-400 border-green-500/30',
            'OK': 'bg-green-500/20 text-green-400 border-green-500/30',
        };

        return (
            <Badge variant="outline" className={`${statusStyles[status] || 'bg-zinc-800 text-zinc-400'} text-xs`}>
                {status}
            </Badge>
        );
    };

    return (
        <Card className="bg-zinc-900/50 border-zinc-800">
            <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                    Run Comparison
                </CardTitle>
                <CardDescription className="text-xs">
                    Comparing {compareRuns.length} run{compareRuns.length !== 1 ? 's' : ''} • Baseline: {baseline.run_id}
                </CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
                <div className="overflow-x-auto">
                    <Table>
                        <TableHeader>
                            <TableRow className="border-zinc-800 hover:bg-transparent">
                                <TableHead className="text-zinc-400 font-medium text-xs sticky left-0 bg-zinc-900/95 z-10">
                                    Metric
                                </TableHead>
                                {compareRuns.map((run) => {
                                    const isBest = run === bestRun;
                                    return (
                                        <TableHead
                                            key={run.run_id}
                                            className={`text-zinc-300 font-medium text-xs text-center min-w-[140px] ${
                                                onRunClick ? 'cursor-pointer hover:text-cyan-400 transition-colors' : ''
                                            } ${isBest ? 'bg-green-500/10' : ''}`}
                                            onClick={() => onRunClick?.(run.run_id)}
                                        >
                                            <div className="flex items-center justify-center gap-1">
                                                <div className="truncate" title={run.run_id}>
                                                    {run.run_id}
                                                </div>
                                                {isBest && (
                                                    <span className="text-green-400" title="Best HP">⭐</span>
                                                )}
                                            </div>
                                            <div className="text-[10px] text-zinc-500 font-normal mt-0.5">
                                                {new Date(run.timestamp).toLocaleTimeString()}
                                            </div>
                                        </TableHead>
                                    );
                                })}
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {/* Peak HP */}
                            <TableRow className="border-zinc-800 hover:bg-zinc-800/30">
                                <TableCell className="font-medium text-xs text-zinc-400 sticky left-0 bg-zinc-900/95 z-10">
                                    Peak HP
                                </TableCell>
                                {compareRuns.map((run) => (
                                    <TableCell key={run.run_id} className="text-center">
                                        <div className="flex flex-col items-center gap-1">
                                            <span className="text-lg font-bold text-orange-400 tabular-nums">
                                                {run.peak_hp.toFixed(1)}
                                            </span>
                                            <DeltaBadge value={getHpDelta(run)} baselineValue={baseline.peak_hp} />
                                            {run.manifest?.analysis?.peak_hp_rpm && (
                                                <span className="text-[10px] text-zinc-500">
                                                    @ {run.manifest.analysis.peak_hp_rpm} RPM
                                                </span>
                                            )}
                                        </div>
                                    </TableCell>
                                ))}
                            </TableRow>

                            {/* Peak Torque */}
                            <TableRow className="border-zinc-800 hover:bg-zinc-800/30">
                                <TableCell className="font-medium text-xs text-zinc-400 sticky left-0 bg-zinc-900/95 z-10">
                                    Peak Torque
                                </TableCell>
                                {compareRuns.map((run) => (
                                    <TableCell key={run.run_id} className="text-center">
                                        <div className="flex flex-col items-center gap-1">
                                            <span className="text-lg font-bold text-blue-400 tabular-nums">
                                                {run.peak_tq.toFixed(1)}
                                            </span>
                                            <DeltaBadge value={getTqDelta(run)} baselineValue={baseline.peak_tq} />
                                            {run.manifest?.analysis?.peak_tq_rpm && (
                                                <span className="text-[10px] text-zinc-500">
                                                    @ {run.manifest.analysis.peak_tq_rpm} RPM
                                                </span>
                                            )}
                                        </div>
                                    </TableCell>
                                ))}
                            </TableRow>

                            {/* AFR Status */}
                            <TableRow className="border-zinc-800 hover:bg-zinc-800/30">
                                <TableCell className="font-medium text-xs text-zinc-400 sticky left-0 bg-zinc-900/95 z-10">
                                    AFR Status
                                </TableCell>
                                {compareRuns.map((run) => (
                                    <TableCell key={run.run_id} className="text-center">
                                        <StatusBadge status={run.manifest?.analysis?.overall_status || run.status} />
                                    </TableCell>
                                ))}
                            </TableRow>

                            {/* VE Corrections */}
                            <TableRow className="border-zinc-800 hover:bg-zinc-800/30">
                                <TableCell className="font-medium text-xs text-zinc-400 sticky left-0 bg-zinc-900/95 z-10">
                                    VE Cells
                                </TableCell>
                                {compareRuns.map((run) => {
                                    const analysis = run.manifest?.analysis;
                                    const okCells = analysis?.ok_cells || 0;
                                    const needsFixCells = (analysis?.lean_cells || 0) + (analysis?.rich_cells || 0);
                                    const totalCells = okCells + needsFixCells;
                                    const okPercent = totalCells > 0 ? (okCells / totalCells) * 100 : 0;

                                    return (
                                        <TableCell key={run.run_id} className="text-center">
                                            <div className="flex flex-col items-center gap-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm font-medium text-green-400 tabular-nums">
                                                        {okCells}
                                                    </span>
                                                    <span className="text-zinc-600">/</span>
                                                    <span className="text-sm font-medium text-zinc-400 tabular-nums">
                                                        {totalCells}
                                                    </span>
                                                </div>
                                                {totalCells > 0 && (
                                                    <div className="flex items-center gap-1">
                                                        <div className="w-16 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                                                            <div
                                                                className="h-full bg-green-500 transition-all"
                                                                style={{ width: `${okPercent}%` }}
                                                            />
                                                        </div>
                                                        <span className="text-[10px] text-zinc-500 tabular-nums">
                                                            {okPercent.toFixed(0)}%
                                                        </span>
                                                    </div>
                                                )}
                                            </div>
                                        </TableCell>
                                    );
                                })}
                            </TableRow>

                            {/* Duration */}
                            <TableRow className="border-zinc-800 hover:bg-zinc-800/30">
                                <TableCell className="font-medium text-xs text-zinc-400 sticky left-0 bg-zinc-900/95 z-10">
                                    Duration
                                </TableCell>
                                {compareRuns.map((run) => {
                                    const durationSec = run.manifest?.analysis?.duration_ms
                                        ? (run.manifest.analysis.duration_ms / 1000).toFixed(1)
                                        : '—';

                                    return (
                                        <TableCell key={run.run_id} className="text-center">
                                            <span className="text-sm text-zinc-300 tabular-nums">
                                                {durationSec}s
                                            </span>
                                        </TableCell>
                                    );
                                })}
                            </TableRow>

                            {/* Issues */}
                            <TableRow className="border-zinc-800 hover:bg-zinc-800/30">
                                <TableCell className="font-medium text-xs text-zinc-400 sticky left-0 bg-zinc-900/95 z-10">
                                    Issues
                                </TableCell>
                                {compareRuns.map((run) => {
                                    const analysis = run.manifest?.analysis;
                                    const leanCells = analysis?.lean_cells || 0;
                                    const richCells = analysis?.rich_cells || 0;
                                    const hasIssues = leanCells > 0 || richCells > 0;

                                    return (
                                        <TableCell key={run.run_id} className="text-center">
                                            {hasIssues ? (
                                                <div className="flex flex-col items-center gap-1">
                                                    {leanCells > 0 && (
                                                        <div className="flex items-center gap-1 text-xs text-red-400">
                                                            <AlertTriangle className="w-3 h-3" />
                                                            <span>{leanCells} lean</span>
                                                        </div>
                                                    )}
                                                    {richCells > 0 && (
                                                        <div className="flex items-center gap-1 text-xs text-blue-400">
                                                            <AlertTriangle className="w-3 h-3" />
                                                            <span>{richCells} rich</span>
                                                        </div>
                                                    )}
                                                </div>
                                            ) : (
                                                <div className="flex items-center justify-center gap-1 text-xs text-green-400">
                                                    <CheckCircle2 className="w-3 h-3" />
                                                    <span>None</span>
                                                </div>
                                            )}
                                        </TableCell>
                                    );
                                })}
                            </TableRow>
                        </TableBody>
                    </Table>
                </div>

                {/* Legend */}
                <div className="mt-4 pt-3 border-t border-zinc-800 flex items-center justify-center gap-6 text-xs text-zinc-400">
                    <div className="flex items-center gap-2">
                        <TrendingUp className="w-4 h-4 text-green-400" />
                        <span className="font-medium">Improvement</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <TrendingDown className="w-4 h-4 text-red-400" />
                        <span className="font-medium">Decrease</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Minus className="w-4 h-4 text-zinc-500" />
                        <span className="font-medium">Minimal change</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-green-400 text-lg">⭐</span>
                        <span className="font-medium">Best HP</span>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

