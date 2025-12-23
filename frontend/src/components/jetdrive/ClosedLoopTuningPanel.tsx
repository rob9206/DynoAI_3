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
import { Play, Square, RefreshCw, CheckCircle2, AlertTriangle, TrendingDown, Zap, ChevronDown, Activity } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Progress } from '../ui/progress';
import { Badge } from '../ui/badge';
import { Alert, AlertDescription } from '../ui/alert';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';

const API_BASE = 'http://127.0.0.1:5001/api/virtual-tune';

// Session recovery constants
const HOUR_IN_MS = 60 * 60 * 1000;
const SESSION_STORAGE_KEY = 'dynoai_active_tuning_session';

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
    progress_pct: number;
    progress_message: string;
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
    const [showErrorDetails, setShowErrorDetails] = useState(false);
    const [lastConfig, setLastConfig] = useState<any>(null);
    const [isResumed, setIsResumed] = useState(false);

    // Session recovery from localStorage
    useEffect(() => {
        const savedSession = localStorage.getItem(SESSION_STORAGE_KEY);
        if (savedSession) {
            try {
                const { sessionId: savedId, startTime } = JSON.parse(savedSession);
                // Only resume if session was started less than 1 hour ago
                const hourAgo = Date.now() - HOUR_IN_MS;
                if (startTime > hourAgo) {
                    setSessionId(savedId);
                    setIsResumed(true);
                    toast.info('Resumed monitoring session', {
                        description: `Session from ${new Date(startTime).toLocaleTimeString()}`,
                    });
                } else {
                    localStorage.removeItem(SESSION_STORAGE_KEY);
                }
            } catch (e) {
                localStorage.removeItem(SESSION_STORAGE_KEY);
            }
        }
    }, []);

    // Save active session to localStorage
    useEffect(() => {
        if (sessionId && status?.status === 'running') {
            localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({
                sessionId,
                startTime: Date.now()
            }));
        } else if (sessionId && (status?.status === 'converged' || status?.status === 'failed' || status?.status === 'stopped' || status?.status === 'max_iterations')) {
            // Clear localStorage when session completes
            localStorage.removeItem(SESSION_STORAGE_KEY);
        }
    }, [sessionId, status?.status]);

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
            const config = {
                engine_profile: engineProfile,
                base_ve_scenario: baseScenario,
                max_iterations: maxIterations,
                convergence_threshold_afr: convergenceThreshold,
            };
            setLastConfig(config);  // Save config for retry
            
            const res = await fetch(`${API_BASE}/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
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

    // Health check mutation
    const healthCheck = useMutation({
        mutationFn: async () => {
            const res = await fetch(`${API_BASE}/health`);
            if (!res.ok) throw new Error(await res.text());
            return res.json();
        },
        onSuccess: (data) => {
            if (data.healthy) {
                toast.success('All systems operational', {
                    description: 'Virtual tuning system is healthy',
                });
            } else {
                const failedComponents = Object.entries(data.components)
                    .filter(([_, status]) => status !== 'ok')
                    .map(([name, _]) => name)
                    .join(', ');
                toast.warning('Some components have issues', {
                    description: `Failed: ${failedComponents}`,
                });
            }
        },
        onError: (error) => {
            toast.error('Health check failed', {
                description: error instanceof Error ? error.message : String(error),
            });
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
        setShowErrorDetails(false);
    };

    const handleRetry = () => {
        // Reset and start a new session with the same config
        setSessionId(null);
        setIsStarting(true);
        setShowErrorDetails(false);
        startTuning.mutate();
    };

    const isRunning = status?.status === 'running';
    const isComplete = status?.status === 'converged' || status?.status === 'max_iterations';
    const isFailed = status?.status === 'failed';

    // Helper function to calculate overall progress percentage
    const calculateProgressPercentage = (status: SessionStatus | null | undefined): number => {
        if (!status) return 0;
        
        // First iteration: use sub-iteration progress
        if (status.current_iteration === 0 && status.status === 'running') {
            return status.progress_pct || 5;  // Show 5% minimum to indicate activity
        }
        
        // Subsequent iterations: combine iteration count with sub-progress
        const completedProgress = status.current_iteration / status.max_iterations;
        const currentProgress = (status.progress_pct || 0) / 100 / status.max_iterations;
        return (completedProgress + currentProgress) * 100;
    };

    const progressPct = calculateProgressPercentage(status);
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

                        <div className="flex gap-2">
                            <Button onClick={handleStart} disabled={isStarting} className="flex-1 bg-cyan-600 hover:bg-cyan-700">
                                <Play className="h-4 w-4 mr-2" />
                                Start Closed-Loop Tuning
                            </Button>
                            <Button 
                                onClick={() => healthCheck.mutate()} 
                                variant="outline" 
                                size="default"
                                disabled={healthCheck.isPending}
                            >
                                <Activity className="h-4 w-4 mr-2" />
                                Test Health
                            </Button>
                        </div>
                    </>
                )}

                {sessionId && status && (
                    <>
                        {/* Resumed Session Banner */}
                        {isResumed && (
                            <Alert className="bg-blue-500/10 border-blue-500/30">
                                <AlertDescription className="flex items-center justify-between">
                                    <span>
                                        <strong>Session Resumed</strong>
                                        <br />
                                        Monitoring session from previous page visit
                                    </span>
                                    <Button 
                                        variant="ghost" 
                                        size="sm" 
                                        onClick={() => {
                                            setIsResumed(false);
                                            localStorage.removeItem(SESSION_STORAGE_KEY);
                                        }}
                                    >
                                        Dismiss
                                    </Button>
                                </AlertDescription>
                            </Alert>
                        )}
                        
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
                        {isRunning && (
                            <Alert className="bg-cyan-500/10 border-cyan-500/30">
                                <RefreshCw className="h-4 w-4 text-cyan-500 animate-spin" />
                                <AlertDescription>
                                    <strong>{status.progress_message || `Running iteration ${status.current_iteration || 1}...`}</strong>
                                    <br />
                                    {status.current_iteration === 0 ? (
                                        <>This takes 10-15 seconds (running full dyno pull + analysis).</>
                                    ) : (
                                        <>Processing iteration {status.current_iteration} of {status.max_iterations}</>
                                    )}
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
                            <div className="space-y-2">
                                <Alert variant="destructive">
                                    <AlertTriangle className="h-4 w-4" />
                                    <AlertDescription>
                                        <strong>Tuning Failed</strong>
                                        <br />
                                        {status.error_message || 'Unknown error occurred'}
                                    </AlertDescription>
                                </Alert>
                                
                                <Collapsible open={showErrorDetails} onOpenChange={setShowErrorDetails}>
                                    <CollapsibleTrigger asChild>
                                        <Button variant="ghost" size="sm" className="w-full justify-between">
                                            <span>Error Details</span>
                                            <ChevronDown className={`h-4 w-4 transition-transform ${showErrorDetails ? 'rotate-180' : ''}`} />
                                        </Button>
                                    </CollapsibleTrigger>
                                    <CollapsibleContent className="mt-2">
                                        <div className="p-3 rounded-lg bg-muted/50 space-y-2 text-sm">
                                            <div>
                                                <span className="text-muted-foreground">Session ID:</span>
                                                <div className="font-mono text-xs break-all">{status.session_id}</div>
                                            </div>
                                            <div>
                                                <span className="text-muted-foreground">Failed at:</span>
                                                <div>Iteration {status.current_iteration}/{status.max_iterations}</div>
                                            </div>
                                            <div>
                                                <span className="text-muted-foreground">Error Message:</span>
                                                <div className="text-red-500 font-medium">{status.error_message || 'No details available'}</div>
                                            </div>
                                            {status.start_time && (
                                                <div>
                                                    <span className="text-muted-foreground">Duration before failure:</span>
                                                    <div>{status.duration_sec.toFixed(1)}s</div>
                                                </div>
                                            )}
                                        </div>
                                    </CollapsibleContent>
                                </Collapsible>
                            </div>
                        )}

                        {/* Controls */}
                        <div className="flex gap-2">
                            {isRunning && (
                                <Button onClick={handleStop} variant="destructive" size="sm" className="flex-1">
                                    <Square className="h-4 w-4 mr-2" />
                                    Stop
                                </Button>
                            )}
                            {isFailed && (
                                <>
                                    <Button onClick={handleRetry} variant="outline" size="sm" className="flex-1">
                                        <RefreshCw className="h-4 w-4 mr-2" />
                                        Retry Tuning
                                    </Button>
                                    <Button onClick={handleReset} variant="outline" size="sm" className="flex-1">
                                        New Session
                                    </Button>
                                </>
                            )}
                            {isComplete && (
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

