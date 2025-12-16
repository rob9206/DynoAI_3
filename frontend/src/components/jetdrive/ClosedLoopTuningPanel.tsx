/**
 * Closed-Loop Tuning Panel - Real-time multi-iteration tuning progress
 * 
 * Shows:
 * - Current iteration progress
 * - AFR error convergence
 * - VE corrections applied
 * - Convergence status
 * - Iteration history
 */

import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Play, Square, RefreshCw, CheckCircle2, AlertTriangle, TrendingDown, Zap } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Progress } from '../ui/progress';
import { Badge } from '../ui/badge';
import { Alert, AlertDescription } from '../ui/alert';

const API_BASE = 'http://127.0.0.1:5001/api/virtual-tune';

interface IterationData {
    iteration: number;
    max_afr_error: number;
    mean_afr_error: number;
    max_ve_correction_pct: number;
    converged: boolean;
    peak_hp: number;
    peak_tq: number;
}

interface SessionStatus {
    session_id: string;
    status: 'initializing' | 'running' | 'converged' | 'failed' | 'stopped' | 'max_iterations';
    current_iteration: number;
    max_iterations: number;
    converged: boolean;
    iterations: IterationData[];
    duration_sec: number;
    error_message?: string;
}

interface ClosedLoopTuningPanelProps {
    engineProfile?: string;
    baseScenario?: 'perfect' | 'lean' | 'rich' | 'custom';
    maxIterations?: number;
    convergenceThreshold?: number;
}

export function ClosedLoopTuningPanel({
    engineProfile = 'm8_114',
    baseScenario = 'lean',
    maxIterations = 10,
    convergenceThreshold = 0.3,
}: ClosedLoopTuningPanelProps) {
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [isStarting, setIsStarting] = useState(false);

    // Poll session status
    const { data: status, refetch } = useQuery<SessionStatus>({
        queryKey: ['closed-loop-status', sessionId],
        queryFn: async () => {
            if (!sessionId) return null;
            const res = await fetch(`${API_BASE}/status/${sessionId}`);
            if (!res.ok) throw new Error('Failed to get status');
            return res.json();
        },
        enabled: !!sessionId,
        refetchInterval: (data) => {
            // Poll every 3 seconds while running (iterations take ~4s each)
            if (data?.status === 'running' || data?.status === 'initializing') return 3000;
            return false; // Stop polling when complete
        },
    });

    // Start tuning mutation
    const startTuning = useMutation({
        mutationFn: async () => {
            const res = await fetch(`${API_BASE}/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    engine_profile: engineProfile,
                    base_ve_scenario: baseScenario,
                    max_iterations: maxIterations,
                    convergence_threshold_afr: convergenceThreshold,
                }),
            });
            if (!res.ok) throw new Error(await res.text());
            return res.json();
        },
        onSuccess: (data) => {
            setSessionId(data.session_id);
            toast.success('Closed-loop tuning started', {
                description: `Session: ${data.session_id}`,
            });
        },
        onError: (error) => {
            toast.error('Failed to start tuning', {
                description: error instanceof Error ? error.message : String(error),
            });
        },
    });

    // Stop tuning mutation
    const stopTuning = useMutation({
        mutationFn: async () => {
            if (!sessionId) return;
            const res = await fetch(`${API_BASE}/stop/${sessionId}`, {
                method: 'POST',
            });
            if (!res.ok) throw new Error(await res.text());
            return res.json();
        },
        onSuccess: () => {
            toast.info('Tuning session stopped');
            refetch();
        },
    });

    const handleStart = () => {
        setIsStarting(true);
        startTuning.mutate();
    };

    const handleStop = () => {
        stopTuning.mutate();
    };

    const handleReset = () => {
        setSessionId(null);
        setIsStarting(false);
    };

    const isRunning = status?.status === 'running';
    const isComplete = status?.status === 'converged' || status?.status === 'max_iterations';
    const isFailed = status?.status === 'failed';

    // Calculate progress - show partial progress during first iteration
    const progressPct = status
        ? status.current_iteration === 0 && status.status === 'running'
            ? 5  // Show 5% to indicate activity
            : (status.current_iteration / status.max_iterations) * 100
        : 0;

    // Get latest iteration data
    const latestIteration = status?.iterations?.[status.iterations.length - 1];

    return (
        <Card className="border-cyan-500/30 bg-gradient-to-br from-cyan-500/5 to-transparent">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <RefreshCw className={`h-5 w-5 text-cyan-500 ${isRunning ? 'animate-spin' : ''}`} />
                        <CardTitle>Closed-Loop Auto-Tune</CardTitle>
                        {status && (
                            <Badge
                                variant="outline"
                                className={
                                    isComplete
                                        ? 'bg-green-500/10 text-green-500 border-green-500/30'
                                        : isRunning
                                            ? 'bg-cyan-500/10 text-cyan-500 border-cyan-500/30'
                                            : isFailed
                                                ? 'bg-red-500/10 text-red-500 border-red-500/30'
                                                : 'bg-zinc-500/10 text-zinc-500 border-zinc-500/30'
                                }
                            >
                                {status.status.toUpperCase()}
                            </Badge>
                        )}
                    </div>
                </div>
                <CardDescription>
                    Fully automated multi-iteration tuning until convergence
                </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
                {!sessionId && (
                    <>
                        <Alert>
                            <Zap className="h-4 w-4" />
                            <AlertDescription>
                                Start a closed-loop tuning session to automatically iterate until AFR is on target.
                                The system will run multiple pulls, analyze errors, and apply corrections automatically.
                            </AlertDescription>
                        </Alert>

                        <div className="grid grid-cols-2 gap-3 text-sm">
                            <div className="p-3 rounded-lg bg-muted/50">
                                <div className="text-muted-foreground">Starting Scenario</div>
                                <div className="font-semibold">{baseScenario.toUpperCase()}</div>
                            </div>
                            <div className="p-3 rounded-lg bg-muted/50">
                                <div className="text-muted-foreground">Max Iterations</div>
                                <div className="font-semibold">{maxIterations}</div>
                            </div>
                            <div className="p-3 rounded-lg bg-muted/50">
                                <div className="text-muted-foreground">Convergence</div>
                                <div className="font-semibold">&lt; {convergenceThreshold} AFR</div>
                            </div>
                            <div className="p-3 rounded-lg bg-muted/50">
                                <div className="text-muted-foreground">Engine</div>
                                <div className="font-semibold">{engineProfile.toUpperCase()}</div>
                            </div>
                        </div>

                        <Button onClick={handleStart} disabled={isStarting} className="w-full bg-cyan-600 hover:bg-cyan-700">
                            <Play className="h-4 w-4 mr-2" />
                            Start Closed-Loop Tuning
                        </Button>
                    </>
                )}

                {sessionId && status && (
                    <>
                        {/* Progress Bar */}
                        <div className="space-y-2">
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-muted-foreground flex items-center gap-2">
                                    {isRunning && status.current_iteration === 0 && (
                                        <RefreshCw className="h-3 w-3 animate-spin text-cyan-500" />
                                    )}
                                    Iteration {status.current_iteration} / {status.max_iterations}
                                    {isRunning && status.current_iteration === 0 && (
                                        <span className="text-xs text-cyan-500">(Running...)</span>
                                    )}
                                </span>
                                <span className="font-mono">{progressPct.toFixed(0)}%</span>
                            </div>
                            <Progress value={progressPct} className={`h-2 ${isRunning && status.current_iteration === 0 ? 'animate-pulse' : ''}`} />
                        </div>

                        {/* Current Status */}
                        {isRunning && status.current_iteration === 0 && (
                            <Alert className="bg-cyan-500/10 border-cyan-500/30">
                                <RefreshCw className="h-4 w-4 text-cyan-500 animate-spin" />
                                <AlertDescription>
                                    <strong>Running first iteration...</strong>
                                    <br />
                                    This takes 10-15 seconds (running full dyno pull + analysis).
                                    <br />
                                    Progress will update when iteration 1 completes.
                                </AlertDescription>
                            </Alert>
                        )}

                        {latestIteration && (
                            <div className="grid grid-cols-2 gap-3">
                                <div className="p-3 rounded-lg bg-muted/30">
                                    <div className="text-xs text-muted-foreground">Max AFR Error</div>
                                    <div className="text-lg font-mono font-semibold">
                                        {latestIteration.max_afr_error.toFixed(3)}
                                    </div>
                                    <div className="text-xs text-muted-foreground">
                                        Target: &lt; {convergenceThreshold}
                                    </div>
                                </div>
                                <div className="p-3 rounded-lg bg-muted/30">
                                    <div className="text-xs text-muted-foreground">VE Correction</div>
                                    <div className="text-lg font-mono font-semibold">
                                        {latestIteration.max_ve_correction_pct > 0 ? '+' : ''}
                                        {latestIteration.max_ve_correction_pct.toFixed(2)}%
                                    </div>
                                    <div className="text-xs text-muted-foreground">Applied</div>
                                </div>
                            </div>
                        )}

                        {/* Iteration History */}
                        {status.iterations.length > 0 && (
                            <div className="space-y-2">
                                <div className="text-sm font-semibold">Iteration History</div>
                                <div className="space-y-1 max-h-48 overflow-y-auto">
                                    {status.iterations.map((it) => (
                                        <div
                                            key={it.iteration}
                                            className="flex items-center justify-between p-2 rounded bg-muted/20 text-sm"
                                        >
                                            <div className="flex items-center gap-2">
                                                <span className="font-mono text-xs text-muted-foreground w-6">#{it.iteration}</span>
                                                {it.converged ? (
                                                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                                                ) : (
                                                    <TrendingDown className="h-4 w-4 text-cyan-500" />
                                                )}
                                            </div>
                                            <div className="flex items-center gap-4 font-mono text-xs">
                                                <span className={it.max_afr_error < convergenceThreshold ? 'text-green-500' : 'text-orange-500'}>
                                                    {it.max_afr_error.toFixed(3)} AFR
                                                </span>
                                                <span className="text-muted-foreground">
                                                    {it.max_ve_correction_pct > 0 ? '+' : ''}
                                                    {it.max_ve_correction_pct.toFixed(1)}% VE
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Status Messages */}
                        {isComplete && (
                            <Alert className="bg-green-500/10 border-green-500/30">
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                                <AlertDescription>
                                    <strong>Converged in {status.current_iteration} iterations!</strong>
                                    <br />
                                    Final AFR error: {latestIteration?.max_afr_error.toFixed(3)} points
                                    <br />
                                    Duration: {status.duration_sec.toFixed(1)}s
                                </AlertDescription>
                            </Alert>
                        )}

                        {isFailed && (
                            <Alert className="bg-red-500/10 border-red-500/30">
                                <AlertTriangle className="h-4 w-4 text-red-500" />
                                <AlertDescription>
                                    <strong>Tuning failed</strong>
                                    <br />
                                    {status.error_message || 'Unknown error'}
                                </AlertDescription>
                            </Alert>
                        )}

                        {/* Controls */}
                        <div className="flex gap-2">
                            {isRunning && (
                                <Button onClick={handleStop} variant="destructive" size="sm" className="flex-1">
                                    <Square className="h-4 w-4 mr-2" />
                                    Stop
                                </Button>
                            )}
                            {(isComplete || isFailed) && (
                                <Button onClick={handleReset} variant="outline" size="sm" className="flex-1">
                                    <RefreshCw className="h-4 w-4 mr-2" />
                                    New Session
                                </Button>
                            )}
                        </div>
                    </>
                )}
            </CardContent>
        </Card>
    );
}

