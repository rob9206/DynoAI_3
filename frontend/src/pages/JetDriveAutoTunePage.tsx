/**
 * JetDriveAutoTunePage - JetDrive Auto-Tune Analysis
 * 
 * Provides a complete interface for:
 * - Running simulated or real JetDrive dyno captures
 * - 2D RPM × MAP grid AFR analysis
 * - VE correction calculation and export
 * - Power Vision PVV XML generation
 */

import { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
    Gauge, Play, FileDown, Upload, RefreshCw,
    CheckCircle2, XCircle, AlertCircle, Grid3X3,
    FileText, Download, Zap
} from 'lucide-react';
import { toast } from 'sonner';

import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';

// API base URL
const API_BASE = 'http://127.0.0.1:5000/api/jetdrive';

interface AnalysisResult {
    success: boolean;
    run_id: string;
    output_dir: string;
    analysis: {
        total_samples: number;
        duration_ms: number;
        peak_hp: number;
        peak_hp_rpm: number;
        peak_tq: number;
        peak_tq_rpm: number;
        overall_status: string;
        lean_cells: number;
        rich_cells: number;
        ok_cells: number;
        no_data_cells: number;
    };
    grid: {
        rpm_bins: number[];
        map_bins: number[];
    };
    ve_grid: { rpm: number; values: number[] }[];
}

interface RunInfo {
    run_id: string;
    timestamp: string;
    peak_hp: number;
    peak_tq: number;
    status: string;
}

// VE Heatmap cell color based on correction value
function getCellColor(value: number): string {
    const delta = (value - 1) * 100;
    if (Math.abs(delta) < 0.5) return 'bg-green-500/20 text-green-400';
    if (delta > 5) return 'bg-red-500/40 text-red-300';
    if (delta > 2) return 'bg-orange-500/30 text-orange-300';
    if (delta < -5) return 'bg-blue-500/40 text-blue-300';
    if (delta < -2) return 'bg-cyan-500/30 text-cyan-300';
    return 'bg-yellow-500/20 text-yellow-300';
}

// Status badge
function StatusBadge({ status }: { status: string }) {
    const colors: Record<string, string> = {
        'LEAN': 'bg-red-500/20 text-red-400 border-red-500/30',
        'RICH': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        'BALANCED': 'bg-green-500/20 text-green-400 border-green-500/30',
        'OK': 'bg-green-500/20 text-green-400 border-green-500/30',
    };
    return (
        <Badge variant="outline" className={colors[status] || 'bg-muted'}>
            {status}
        </Badge>
    );
}

export default function JetDriveAutoTunePage() {
    const [runId, setRunId] = useState(`run_${Date.now()}`);
    const [selectedRun, setSelectedRun] = useState<string | null>(null);
    const [pvvContent, setPvvContent] = useState<string>('');

    // Fetch available runs
    const { data: statusData, refetch: refetchStatus } = useQuery({
        queryKey: ['jetdrive-status'],
        queryFn: async () => {
            const res = await fetch(`${API_BASE}/status`);
            return res.json();
        },
        refetchInterval: 10000,
    });

    // Fetch selected run details
    const { data: runData, isLoading: runLoading } = useQuery({
        queryKey: ['jetdrive-run', selectedRun],
        queryFn: async () => {
            if (!selectedRun) return null;
            const res = await fetch(`${API_BASE}/run/${selectedRun}`);
            return res.json();
        },
        enabled: !!selectedRun,
    });

    // Run analysis mutation
    const analyzeMutation = useMutation({
        mutationFn: async ({ mode, csvPath }: { mode: string; csvPath?: string }) => {
            const res = await fetch(`${API_BASE}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    run_id: runId,
                    mode,
                    csv_path: csvPath,
                }),
            });
            return res.json();
        },
        onSuccess: (data) => {
            if (data.success) {
                toast.success(`Analysis complete: ${data.run_id}`, {
                    description: `Peak HP: ${data.analysis.peak_hp.toFixed(1)} @ ${data.analysis.peak_hp_rpm} RPM`
                });
                setSelectedRun(data.run_id);
                refetchStatus();
            } else {
                toast.error('Analysis failed', { description: data.error });
            }
        },
        onError: (err) => {
            toast.error('Analysis error', { description: String(err) });
        },
    });

    // Fetch PVV content
    const fetchPvv = async (rid: string) => {
        const res = await fetch(`${API_BASE}/run/${rid}/pvv`);
        const data = await res.json();
        setPvvContent(data.content);
    };

    // Download PVV file
    const downloadPvv = () => {
        if (!pvvContent || !selectedRun) return;
        const blob = new Blob([pvvContent], { type: 'application/xml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `VE_Correction_${selectedRun}.pvv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    useEffect(() => {
        if (selectedRun) {
            fetchPvv(selectedRun);
        }
    }, [selectedRun]);

    const runs: RunInfo[] = statusData?.runs || [];
    const analysis = runData?.manifest?.analysis;
    const grid = runData?.manifest?.grid;
    const veGrid = runData?.ve_grid || [];

    return (
        <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 p-4 md:p-6">
            {/* Page Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
                        <Gauge className="h-8 w-8 text-orange-500" />
                        JetDrive Auto-Tune
                    </h1>
                    <p className="text-muted-foreground">
                        2D RPM × MAP grid analysis with Power Vision PVV export
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => refetchStatus()}
                    >
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Refresh
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Column - Controls */}
                <div className="space-y-4">
                    {/* New Analysis Card */}
                    <Card className="border-orange-500/30 bg-gradient-to-br from-orange-500/5 to-transparent">
                        <CardHeader>
                            <CardTitle className="text-lg flex items-center gap-2">
                                <Play className="h-5 w-5 text-orange-500" />
                                New Analysis
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="run-id">Run ID</Label>
                                <Input
                                    id="run-id"
                                    value={runId}
                                    onChange={(e) => setRunId(e.target.value)}
                                    placeholder="my_dyno_run"
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-2">
                                <Button
                                    onClick={() => analyzeMutation.mutate({ mode: 'simulate' })}
                                    disabled={analyzeMutation.isPending}
                                    className="bg-orange-600 hover:bg-orange-700"
                                >
                                    {analyzeMutation.isPending ? (
                                        <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                                    ) : (
                                        <Zap className="h-4 w-4 mr-2" />
                                    )}
                                    Simulate
                                </Button>
                                <Button
                                    variant="outline"
                                    disabled={true}
                                    title="Upload CSV first"
                                >
                                    <Upload className="h-4 w-4 mr-2" />
                                    CSV
                                </Button>
                            </div>

                            {analyzeMutation.isPending && (
                                <div className="space-y-2">
                                    <Progress value={66} className="h-2" />
                                    <p className="text-xs text-muted-foreground text-center">
                                        Running analysis...
                                    </p>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Recent Runs */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg flex items-center gap-2">
                                <Grid3X3 className="h-5 w-5" />
                                Recent Runs
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {runs.length === 0 ? (
                                <p className="text-sm text-muted-foreground">No runs yet</p>
                            ) : (
                                <div className="space-y-2 max-h-64 overflow-y-auto">
                                    {runs.map((run) => (
                                        <button
                                            key={run.run_id}
                                            onClick={() => setSelectedRun(run.run_id)}
                                            className={`w-full text-left p-3 rounded-lg border transition-all ${selectedRun === run.run_id
                                                    ? 'border-orange-500 bg-orange-500/10'
                                                    : 'border-border hover:border-orange-500/50 hover:bg-muted/50'
                                                }`}
                                        >
                                            <div className="flex items-center justify-between">
                                                <span className="font-medium text-sm">{run.run_id}</span>
                                                <StatusBadge status={run.status} />
                                            </div>
                                            <div className="text-xs text-muted-foreground mt-1">
                                                {run.peak_hp > 0 && `${run.peak_hp.toFixed(0)} HP`}
                                                {run.peak_tq > 0 && ` / ${run.peak_tq.toFixed(0)} ft-lb`}
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Right Column - Results */}
                <div className="lg:col-span-2 space-y-4">
                    {selectedRun && runData ? (
                        <>
                            {/* Analysis Summary */}
                            <Card>
                                <CardHeader>
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="flex items-center gap-2">
                                            <CheckCircle2 className="h-5 w-5 text-green-500" />
                                            {selectedRun}
                                        </CardTitle>
                                        <StatusBadge status={analysis?.overall_status || 'Unknown'} />
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                        <div className="text-center p-3 bg-muted/30 rounded-lg">
                                            <div className="text-2xl font-bold text-orange-500">
                                                {analysis?.peak_hp?.toFixed(1)}
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                Peak HP @ {analysis?.peak_hp_rpm} RPM
                                            </div>
                                        </div>
                                        <div className="text-center p-3 bg-muted/30 rounded-lg">
                                            <div className="text-2xl font-bold text-blue-500">
                                                {analysis?.peak_tq?.toFixed(1)}
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                Peak TQ @ {analysis?.peak_tq_rpm} RPM
                                            </div>
                                        </div>
                                        <div className="text-center p-3 bg-muted/30 rounded-lg">
                                            <div className="text-2xl font-bold">
                                                {analysis?.total_samples}
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                Samples
                                            </div>
                                        </div>
                                        <div className="text-center p-3 bg-muted/30 rounded-lg">
                                            <div className="flex justify-center gap-1">
                                                <span className="text-green-500">{analysis?.ok_cells}</span>
                                                <span className="text-muted-foreground">/</span>
                                                <span className="text-red-500">{analysis?.lean_cells}</span>
                                                <span className="text-muted-foreground">/</span>
                                                <span className="text-blue-500">{analysis?.rich_cells}</span>
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                OK / Lean / Rich
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Tabs for Grid and Export */}
                            <Tabs defaultValue="grid" className="w-full">
                                <TabsList className="grid w-full grid-cols-3">
                                    <TabsTrigger value="grid">
                                        <Grid3X3 className="h-4 w-4 mr-2" />
                                        VE Grid
                                    </TabsTrigger>
                                    <TabsTrigger value="pvv">
                                        <FileDown className="h-4 w-4 mr-2" />
                                        PVV Export
                                    </TabsTrigger>
                                    <TabsTrigger value="report">
                                        <FileText className="h-4 w-4 mr-2" />
                                        Report
                                    </TabsTrigger>
                                </TabsList>

                                {/* VE Correction Grid */}
                                <TabsContent value="grid">
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="text-sm">
                                                VE Correction Grid (% change)
                                            </CardTitle>
                                            <CardDescription>
                                                {grid?.rpm_bins?.length} RPM × {grid?.map_bins?.length} MAP bins
                                            </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="overflow-x-auto">
                                                <table className="w-full text-xs">
                                                    <thead>
                                                        <tr>
                                                            <th className="p-2 text-left bg-muted/50">RPM \ MAP</th>
                                                            {grid?.map_bins?.map((m: number) => (
                                                                <th key={m} className="p-2 text-center bg-muted/50 min-w-[60px]">
                                                                    {m} kPa
                                                                </th>
                                                            ))}
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {veGrid.map((row, i) => (
                                                            <tr key={row.rpm}>
                                                                <td className="p-2 font-medium bg-muted/30">
                                                                    {row.rpm}
                                                                </td>
                                                                {row.values.map((val, j) => {
                                                                    const delta = ((val - 1) * 100);
                                                                    return (
                                                                        <td
                                                                            key={j}
                                                                            className={`p-2 text-center font-mono ${getCellColor(val)}`}
                                                                        >
                                                                            {delta === 0 ? '—' : `${delta > 0 ? '+' : ''}${delta.toFixed(1)}%`}
                                                                        </td>
                                                                    );
                                                                })}
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>

                                            <div className="mt-4 flex items-center justify-center gap-4 text-xs">
                                                <div className="flex items-center gap-1">
                                                    <div className="w-4 h-4 bg-red-500/40 rounded" />
                                                    <span>Lean (+)</span>
                                                </div>
                                                <div className="flex items-center gap-1">
                                                    <div className="w-4 h-4 bg-green-500/20 rounded" />
                                                    <span>OK</span>
                                                </div>
                                                <div className="flex items-center gap-1">
                                                    <div className="w-4 h-4 bg-blue-500/40 rounded" />
                                                    <span>Rich (−)</span>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </TabsContent>

                                {/* PVV Export */}
                                <TabsContent value="pvv">
                                    <Card>
                                        <CardHeader>
                                            <div className="flex items-center justify-between">
                                                <div>
                                                    <CardTitle className="text-sm">Power Vision PVV Export</CardTitle>
                                                    <CardDescription>
                                                        Import directly into Power Core
                                                    </CardDescription>
                                                </div>
                                                <Button onClick={downloadPvv} size="sm">
                                                    <Download className="h-4 w-4 mr-2" />
                                                    Download .pvv
                                                </Button>
                                            </div>
                                        </CardHeader>
                                        <CardContent>
                                            <pre className="bg-muted/50 p-4 rounded-lg text-xs overflow-x-auto max-h-96">
                                                {pvvContent || 'Loading...'}
                                            </pre>
                                        </CardContent>
                                    </Card>
                                </TabsContent>

                                {/* Report */}
                                <TabsContent value="report">
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="text-sm">Diagnostics Report</CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="bg-muted/50 p-4 rounded-lg text-xs font-mono whitespace-pre-wrap max-h-96 overflow-y-auto">
                                                {runData?.manifest ? (
                                                    JSON.stringify(runData.manifest, null, 2)
                                                ) : (
                                                    'Loading...'
                                                )}
                                            </div>
                                        </CardContent>
                                    </Card>
                                </TabsContent>
                            </Tabs>
                        </>
                    ) : (
                        <Card className="h-full flex items-center justify-center min-h-[400px]">
                            <CardContent className="text-center">
                                <Gauge className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                                <h3 className="text-lg font-medium mb-2">No Run Selected</h3>
                                <p className="text-sm text-muted-foreground mb-4">
                                    Run a simulation or select a previous run to view results
                                </p>
                                <Button
                                    onClick={() => analyzeMutation.mutate({ mode: 'simulate' })}
                                    className="bg-orange-600 hover:bg-orange-700"
                                >
                                    <Zap className="h-4 w-4 mr-2" />
                                    Run Simulation
                                </Button>
                            </CardContent>
                        </Card>
                    )}
                </div>
            </div>

            {/* Info Alert */}
            <Alert className="bg-orange-500/10 border-orange-500/30">
                <AlertCircle className="h-4 w-4 text-orange-500" />
                <AlertTitle>JetDrive Auto-Tune</AlertTitle>
                <AlertDescription>
                    This tool analyzes dyno captures using a 2D RPM × MAP grid and calculates
                    VE corrections using DynoAI's "7% per AFR point" formula. Export corrections
                    directly to Power Vision PVV format for immediate application.
                </AlertDescription>
            </Alert>
        </div>
    );
}

