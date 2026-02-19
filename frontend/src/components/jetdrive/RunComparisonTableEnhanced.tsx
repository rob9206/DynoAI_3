/**
 * Enhanced Run Comparison Table Component
 * 
 * Advanced features:
 * - Run selection with checkboxes
 * - Custom baseline selection
 * - Sortable columns
 * - Export to CSV
 * - Expandable rows with detailed metrics
 * - Notes/tags per run
 */

import { useState, useMemo } from 'react';
import { 
    TrendingUp, TrendingDown, Minus, CheckCircle2, AlertTriangle,
    Download, ChevronDown, ChevronRight, Star, StarOff
} from 'lucide-react';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '../ui/table';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
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
            avg_afr?: number;
            max_rpm?: number;
        };
    };
}

interface RunComparisonTableEnhancedProps {
    runs: RunData[];
    onRunClick?: (runId: string) => void;
    maxRuns?: number;
    selectedRunIds?: string[];
    onSelectedRunIdsChange?: (ids: string[]) => void;
    baselineRunId?: string | null;
    onBaselineRunIdChange?: (runId: string | null) => void;
}

type SortKey = 'timestamp' | 'peak_hp' | 'peak_tq' | 'status';
type SortDirection = 'asc' | 'desc';

export function RunComparisonTableEnhanced({
    runs,
    onRunClick,
    maxRuns = 10,
    selectedRunIds: selectedRunIdsProp,
    onSelectedRunIdsChange,
    baselineRunId: baselineRunIdProp,
    onBaselineRunIdChange,
}: RunComparisonTableEnhancedProps) {
    const [selectedRunIdsUncontrolled, setSelectedRunIdsUncontrolled] = useState<string[]>([]);
    const [baselineRunIdUncontrolled, setBaselineRunIdUncontrolled] = useState<string | null>(null);

    const selectedRunIds = selectedRunIdsProp ?? selectedRunIdsUncontrolled;
    const setSelectedRunIds = onSelectedRunIdsChange ?? setSelectedRunIdsUncontrolled;

    const baselineRunId = baselineRunIdProp ?? baselineRunIdUncontrolled;
    const setBaselineRunId = onBaselineRunIdChange ?? setBaselineRunIdUncontrolled;
    const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
    const [sortKey, setSortKey] = useState<SortKey>('timestamp');
    const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

    // Sort and filter runs
    const sortedRuns = useMemo(() => {
        let filtered = [...runs];
        
        // Sort
        filtered.sort((a, b) => {
            let aVal: number | string = 0;
            let bVal: number | string = 0;

            switch (sortKey) {
                case 'timestamp':
                    aVal = new Date(a.timestamp).getTime();
                    bVal = new Date(b.timestamp).getTime();
                    break;
                case 'peak_hp':
                    aVal = a.peak_hp;
                    bVal = b.peak_hp;
                    break;
                case 'peak_tq':
                    aVal = a.peak_tq;
                    bVal = b.peak_tq;
                    break;
                case 'status':
                    aVal = a.manifest?.analysis?.overall_status || a.status;
                    bVal = b.manifest?.analysis?.overall_status || b.status;
                    break;
            }

            if (sortDirection === 'asc') {
                return aVal > bVal ? 1 : -1;
            } else {
                return aVal < bVal ? 1 : -1;
            }
        });

        return filtered.slice(0, maxRuns);
    }, [runs, sortKey, sortDirection, maxRuns]);

    // Get selected or all runs for comparison
    const compareRuns = useMemo(() => {
        if (selectedRunIds.length > 0) {
            const selected = sortedRuns.filter(r => selectedRunIds.includes(r.run_id));
            // Always include baseline if set, even if not checked
            if (baselineRunId && !selected.some(r => r.run_id === baselineRunId)) {
                const baseline = sortedRuns.find(r => r.run_id === baselineRunId);
                if (baseline) return [baseline, ...selected];
            }
            return selected;
        }
        return sortedRuns.slice(0, 5);
    }, [sortedRuns, selectedRunIds, baselineRunId]);

    // Determine baseline
    const baseline = useMemo(() => {
        if (baselineRunId) {
            return compareRuns.find(r => r.run_id === baselineRunId) || compareRuns[0];
        }
        return compareRuns[0];
    }, [compareRuns, baselineRunId]);

    // Toggle run selection
    const toggleRunSelection = (runId: string) => {
        setSelectedRunIds(prev => {
            if (prev.includes(runId)) {
                return prev.filter(id => id !== runId);
            } else {
                return [...prev, runId];
            }
        });
    };

    // Toggle row expansion
    const toggleRowExpansion = (runId: string) => {
        setExpandedRows(prev => {
            const newSet = new Set(prev);
            if (newSet.has(runId)) {
                newSet.delete(runId);
            } else {
                newSet.add(runId);
            }
            return newSet;
        });
    };

    // Export to CSV
    const exportToCSV = () => {
        const headers = ['Run ID', 'Timestamp', 'Peak HP', 'HP Delta', 'Peak TQ', 'TQ Delta', 'AFR Status', 'VE Cells OK', 'Duration (s)'];
        const rows = compareRuns.map(run => {
            const hpDelta = run === baseline ? 0 : run.peak_hp - baseline.peak_hp;
            const tqDelta = run === baseline ? 0 : run.peak_tq - baseline.peak_tq;
            const okCells = run.manifest?.analysis?.ok_cells || 0;
            const duration = run.manifest?.analysis?.duration_ms ? (run.manifest.analysis.duration_ms / 1000).toFixed(1) : 'N/A';
            
            return [
                run.run_id,
                new Date(run.timestamp).toLocaleString(),
                run.peak_hp.toFixed(1),
                hpDelta.toFixed(1),
                run.peak_tq.toFixed(1),
                tqDelta.toFixed(1),
                run.manifest?.analysis?.overall_status || run.status,
                okCells.toString(),
                duration
            ];
        });

        const csv = [headers, ...rows].map(row => row.join(',')).join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `run_comparison_${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    // Handle column sort
    const handleSort = (key: SortKey) => {
        if (sortKey === key) {
            setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
        } else {
            setSortKey(key);
            setSortDirection('desc');
        }
    };

    const getHpDelta = (run: RunData) => {
        if (run === baseline) return null;
        return run.peak_hp - baseline.peak_hp;
    };

    const getTqDelta = (run: RunData) => {
        if (run === baseline) return null;
        return run.peak_tq - baseline.peak_tq;
    };

    const DeltaBadge = ({ value }: { value: number | null }) => {
        if (value === null) {
            return <Badge variant="outline" className="bg-zinc-800/50 text-zinc-400 border-zinc-700 text-xs">BASELINE</Badge>;
        }

        const isPositive = value > 0;
        const isNeutral = Math.abs(value) < 0.5;

        if (isNeutral) {
            return (
                <div className="flex items-center gap-1 text-zinc-500 text-xs">
                    <Minus className="w-3 h-3" />
                    <span>{value.toFixed(1)}</span>
                </div>
            );
        }

        return (
            <div className={`flex items-center gap-1 text-xs ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                <span>{isPositive ? '+' : ''}{value.toFixed(1)}</span>
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

    if (compareRuns.length === 0) {
        return null;
    }

    return (
        <Card className="bg-zinc-900/50 border-zinc-800">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="text-base flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                            Run Comparison
                            {selectedRunIds.length > 0 && (
                                <Badge variant="outline" className="ml-2 text-xs">
                                    {selectedRunIds.length} selected
                                </Badge>
                            )}
                        </CardTitle>
                        <CardDescription className="text-xs">
                            Comparing {compareRuns.length} run{compareRuns.length !== 1 ? 's' : ''} • Baseline: {baseline.run_id}
                        </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={exportToCSV}
                            className="text-xs h-8"
                        >
                            <Download className="w-3 h-3 mr-1" />
                            Export CSV
                        </Button>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="pt-0">
                <div className="overflow-x-auto">
                    <Table>
                        <TableHeader>
                            <TableRow className="border-zinc-800 hover:bg-transparent">
                                <TableHead className="w-10"></TableHead>
                                <TableHead className="w-10"></TableHead>
                                <TableHead 
                                    className="text-zinc-400 font-medium text-xs cursor-pointer hover:text-zinc-300"
                                    onClick={() => handleSort('timestamp')}
                                >
                                    Run ID
                                </TableHead>
                                <TableHead 
                                    className="text-zinc-400 font-medium text-xs text-center cursor-pointer hover:text-zinc-300"
                                    onClick={() => handleSort('peak_hp')}
                                >
                                    Peak HP
                                </TableHead>
                                <TableHead 
                                    className="text-zinc-400 font-medium text-xs text-center cursor-pointer hover:text-zinc-300"
                                    onClick={() => handleSort('peak_tq')}
                                >
                                    Peak TQ
                                </TableHead>
                                <TableHead 
                                    className="text-zinc-400 font-medium text-xs text-center cursor-pointer hover:text-zinc-300"
                                    onClick={() => handleSort('status')}
                                >
                                    Status
                                </TableHead>
                                <TableHead className="text-zinc-400 font-medium text-xs text-center">
                                    VE Progress
                                </TableHead>
                                <TableHead className="text-zinc-400 font-medium text-xs text-center">
                                    Duration
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {compareRuns.map((run) => {
                                const isExpanded = expandedRows.has(run.run_id);
                                const isBaseline = run === baseline;
                                const analysis = run.manifest?.analysis;
                                const okCells = analysis?.ok_cells || 0;
                                const needsFixCells = (analysis?.lean_cells || 0) + (analysis?.rich_cells || 0);
                                const totalCells = okCells + needsFixCells;
                                const okPercent = totalCells > 0 ? (okCells / totalCells) * 100 : 0;

                                return (
                                    <>
                                        <TableRow 
                                            key={run.run_id} 
                                            className={`border-zinc-800 hover:bg-zinc-800/30 ${isBaseline ? 'bg-cyan-500/5' : ''}`}
                                        >
                                            <TableCell>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-6 w-6 p-0"
                                                    onClick={() => toggleRowExpansion(run.run_id)}
                                                >
                                                    {isExpanded ? (
                                                        <ChevronDown className="w-3 h-3" />
                                                    ) : (
                                                        <ChevronRight className="w-3 h-3" />
                                                    )}
                                                </Button>
                                            </TableCell>
                                            <TableCell>
                                                <div className="flex items-center gap-2">
                                                    <Checkbox
                                                        checked={selectedRunIds.includes(run.run_id)}
                                                        onCheckedChange={() => toggleRunSelection(run.run_id)}
                                                    />
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        className="h-6 w-6 p-0"
                                                        onClick={() => setBaselineRunId(run.run_id)}
                                                    >
                                                        {isBaseline ? (
                                                            <Star className="w-3 h-3 fill-cyan-400 text-cyan-400" />
                                                        ) : (
                                                            <StarOff className="w-3 h-3 text-zinc-600" />
                                                        )}
                                                    </Button>
                                                </div>
                                            </TableCell>
                                            <TableCell 
                                                className="font-medium text-xs cursor-pointer hover:text-cyan-400"
                                                onClick={() => onRunClick?.(run.run_id)}
                                            >
                                                <div>
                                                    <div className="truncate max-w-[200px]" title={run.run_id}>
                                                        {run.run_id}
                                                    </div>
                                                    <div className="text-[10px] text-zinc-500">
                                                        {new Date(run.timestamp).toLocaleString()}
                                                    </div>
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-center">
                                                <div className="flex flex-col items-center gap-1">
                                                    <span className="text-sm font-bold text-orange-400 tabular-nums">
                                                        {run.peak_hp.toFixed(1)}
                                                    </span>
                                                    <DeltaBadge value={getHpDelta(run)} />
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-center">
                                                <div className="flex flex-col items-center gap-1">
                                                    <span className="text-sm font-bold text-blue-400 tabular-nums">
                                                        {run.peak_tq.toFixed(1)}
                                                    </span>
                                                    <DeltaBadge value={getTqDelta(run)} />
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-center">
                                                <StatusBadge status={analysis?.overall_status || run.status} />
                                            </TableCell>
                                            <TableCell className="text-center">
                                                <div className="flex flex-col items-center gap-1">
                                                    <div className="w-20 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                                                        <div
                                                            className="h-full bg-green-500 transition-all"
                                                            style={{ width: `${okPercent}%` }}
                                                        />
                                                    </div>
                                                    <span className="text-[10px] text-zinc-500 tabular-nums">
                                                        {okCells}/{totalCells} ({okPercent.toFixed(0)}%)
                                                    </span>
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-center">
                                                <span className="text-xs text-zinc-300 tabular-nums">
                                                    {analysis?.duration_ms ? (analysis.duration_ms / 1000).toFixed(1) : '—'}s
                                                </span>
                                            </TableCell>
                                        </TableRow>

                                        {/* Expanded row with additional details */}
                                        {isExpanded && (
                                            <TableRow className="border-zinc-800 bg-zinc-900/50">
                                                <TableCell colSpan={8} className="py-3">
                                                    <div className="grid grid-cols-4 gap-4 text-xs">
                                                        <div>
                                                            <div className="text-zinc-500 mb-1">Peak HP RPM</div>
                                                            <div className="text-zinc-200 font-medium">
                                                                {analysis?.peak_hp_rpm || 'N/A'}
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <div className="text-zinc-500 mb-1">Peak TQ RPM</div>
                                                            <div className="text-zinc-200 font-medium">
                                                                {analysis?.peak_tq_rpm || 'N/A'}
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <div className="text-zinc-500 mb-1">Avg AFR</div>
                                                            <div className="text-zinc-200 font-medium">
                                                                {analysis?.avg_afr?.toFixed(2) || 'N/A'}
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <div className="text-zinc-500 mb-1">Max RPM</div>
                                                            <div className="text-zinc-200 font-medium">
                                                                {analysis?.max_rpm || 'N/A'}
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div className="mt-3 flex items-center gap-4 text-xs">
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-zinc-500">Lean Cells:</span>
                                                            <span className="text-red-400 font-medium">
                                                                {analysis?.lean_cells || 0}
                                                            </span>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-zinc-500">Rich Cells:</span>
                                                            <span className="text-blue-400 font-medium">
                                                                {analysis?.rich_cells || 0}
                                                            </span>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-zinc-500">OK Cells:</span>
                                                            <span className="text-green-400 font-medium">
                                                                {okCells}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </TableCell>
                                            </TableRow>
                                        )}
                                    </>
                                );
                            })}
                        </TableBody>
                    </Table>
                </div>

                {/* Legend */}
                <div className="mt-4 pt-3 border-t border-zinc-800 flex items-center justify-between text-xs text-zinc-400">
                    <div className="flex items-center gap-6">
                        <div className="flex items-center gap-2">
                            <Star className="w-4 h-4 fill-cyan-400 text-cyan-400" />
                            <span className="font-medium">Baseline</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <TrendingUp className="w-4 h-4 text-green-400" />
                            <span className="font-medium">Improvement</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <TrendingDown className="w-4 h-4 text-red-400" />
                            <span className="font-medium">Decrease</span>
                        </div>
                    </div>
                    <div className="text-zinc-500 text-[11px]">
                        Click ⭐ to set baseline • Click ▶ to expand details
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

