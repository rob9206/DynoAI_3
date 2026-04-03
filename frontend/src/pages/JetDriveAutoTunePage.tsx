/**
 * JetDrive Command Center - Optimized Tuner Interface
 * 
 * State-aware layout that adapts to workflow:
 * - Disconnected: Prominent connect CTA
 * - Connected/Idle: Live gauges + waiting for WOT
 * - Run Detected: Capture indicator
 * - Results: VE grid + export
 * 
 * Key tuner features:
 * - Target AFR configuration
 * - Real-time AFR trace
 * - Run auto-detection
 * - One-click export
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Gauge, Play, Square, RefreshCw,
    CheckCircle2, Grid3X3,
    Download, Zap, Radio, Wifi, WifiOff,
    Activity, ChevronRight, TrendingUp,
    Wrench, Timer, Power, Settings2,
    AlertTriangle, Crosshair, Cpu, StopCircle, Mic,
    Award, Info, Flame, FileText
} from 'lucide-react';
import { toast } from '@/lib/toast';
import { cn } from '@/lib/utils';

import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Slider } from '../components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
    Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetTrigger
} from '../components/ui/sheet';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription
} from '../components/ui/dialog';
import { useJetDriveLive } from '../hooks/useJetDriveLive';
import { useYourDynoLive } from '../hooks/useYourDynoLive';
import { usePowerOpportunities } from '../hooks/usePowerOpportunities';
import { LiveVETable, LiveVEExportData } from '../components/jetdrive/LiveVETable';
import { exportToCSV, exportToJSON, exportToPVV, downloadFile } from '../utils/veExport';
import { parsePVV, extractAfrTargets } from '../utils/pvvParser';
import { TuneImport, type TuneImportResult } from '../components/jetdrive/TuneImport';
import { ApplyPreviewPanel } from '../components/jetdrive/ApplyPreviewPanel';
import { VEBoundsPreset, DualCylinderVE, DualCylinderHits, DualCylinderCorrections, ApplyReport, type CoverageReport } from '../types/veApplyTypes';
import { calculateDualCylinderCoverage } from '../utils/veApply';
import { downloadAppliedVEAllFormats } from '../utils/veExport';
import { DEFAULT_AFR_TARGETS } from '../components/jetdrive/AFRTargetTable';
import { AudioCapturePanel } from '../components/jetdrive/AudioCapturePanel';
import { RunComparisonTable } from '../components/jetdrive/RunComparisonTable';
import { RunComparisonTableEnhanced } from '../components/jetdrive/RunComparisonTableEnhanced';
import { RunComparisonChart } from '../components/jetdrive/RunComparisonChart';
import type { VEScenario } from '../components/jetdrive/VirtualECUPanel';
import { JetDriveLiveDashboard } from '../components/jetdrive/JetDriveLiveDashboard';
import { HardwareTab } from '../components/jetdrive/HardwareTab';
import { SettingsSheet } from '../components/jetdrive/SettingsSheet';
import { StageConfigPanel } from '../components/jetdrive/StageConfigPanel';
import PowerOpportunitiesPanel from '../components/PowerOpportunitiesPanel';
import { SessionReplayViewer } from '../components/session-replay';
import { useAIAssistant } from '../hooks/useAIAssistant';
import { ConfidenceBadge } from '../components/jetdrive/ConfidenceBadge';
import { TuningWizard, type WizardLiveStatus, type PullSummary } from '../components/jetdrive/TuningWizard';
import { SetupWizard } from '../components/jetdrive/SetupWizard';
import { ZoneCoverageCard } from '../components/jetdrive/ZoneCoverageCard';
import type { BikeConfig, DynoConnectionConfig } from '../types/bikeConfig';
import { SmartPromptBanner } from '../components/jetdrive/SmartPromptBanner';
import { CommandCenter } from '../components/jetdrive/CommandCenter';
import { SessionSummaryCard } from '../components/jetdrive/SessionSummaryCard';
import { useTuningWizard } from '../hooks/useTuningWizard';
import { VEHeatmap as VEGrid } from '../components/results/VEHeatmap';
import { VEHeatmapLegend } from '../components/results/VEHeatmapLegend';
import { getConfidenceReport, generateNextGenAnalysis } from '../lib/api';
import type { ConfidenceReport } from '../components/ConfidenceScoreCard';
import { ReportGenerator } from '../components/reports/ReportGenerator';
import { NextGenAnalysisPanel } from '../components/results/NextGenAnalysisPanel';
import { SimulatorLoadPanel } from '../components/jetdrive/SimulatorLoadPanel';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5001';
const API_BASE = `${API_BASE_URL}/api/jetdrive`;
const YOURDYNO_API_BASE = `${API_BASE_URL}/api/yourdyno`;

const NAV_ITEMS = [
    { label: 'Dashboard', to: '/dashboard' },
    { label: 'JetDrive', to: '/jetdrive' },
    { label: 'Results', to: '/results/last' },
    { label: 'History', to: '/history' },
];

const UnifiedTuningTab = (_props: Record<string, unknown>) => null;

export default function JetDriveAutoTunePage() {
    const location = useLocation();
    const [hardwareOpen, setHardwareOpen] = useState(false);
    const [isSimulatorActive, setIsSimulatorActive] = useState(false);
    const [isStartingSim, setIsStartingSim] = useState(false);
    const [isTriggeringPull, setIsTriggeringPull] = useState(false);
    const [simThrottle, setSimThrottle] = useState(0);
    const [activeLiveSource, setActiveLiveSource] = useState<'jetdrive' | 'yourdyno'>('jetdrive');
    const simThrottleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    
    const jetdriveLive = useJetDriveLive({
        apiUrl: API_BASE,
        autoConnect: true,
        pollInterval: 800,
        useSse: true,
        isSimulatorActive,
    });

    const yourdynoLive = useYourDynoLive({
        apiUrl: YOURDYNO_API_BASE,
        autoConnect: true,
        pollInterval: 800,
        useSse: true,
        isSimulatorActive: false,
    });

    const activeLive = activeLiveSource === 'yourdyno' ? yourdynoLive : jetdriveLive;

    const isActive = (path: string) =>
        location.pathname === path || location.pathname.startsWith(`${path}/`);

    const stopSimulator = useCallback(async (silent?: boolean) => {
        try {
            await fetch(`${API_BASE}/simulator/stop`, { method: 'POST' });
            await jetdriveLive.clearChannels();
            setIsSimulatorActive(false);
            setSimThrottle(0);
            if (!silent) {
                toast.info('Simulator stopped');
            }
        } catch (error) {
            if (!silent) {
                toast.error('Failed to stop simulator');
            }
            console.error('Simulator stop error:', error);
        }
    }, [jetdriveLive]);

    const handleToggleSimulator = async () => {
        if (activeLiveSource === 'yourdyno') {
            toast.info('Simulator is only available with JetDrive source.');
            return;
        }
        if (isSimulatorActive) {
            // Stop simulator
            await stopSimulator();
        } else {
            // Start simulator with default profile
            setIsStartingSim(true);
            try {
                const res = await fetch(`${API_BASE}/simulator/start`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        profile: 'm8_114',
                        virtual_ecu: { enabled: false },
                        auto_pull: false,
                    }),
                });

                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
                    throw new Error(errorData.error || `HTTP ${res.status}`);
                }

                const data = await res.json();
                if (data.success) {
                    setIsSimulatorActive(true);
                    toast.success(`Simulator started: ${data.profile?.name || 'M8 114'}`, {
                        description: `${data.profile?.max_hp || 114} HP @ ${data.profile?.redline_rpm || 6200} RPM`
                    });
                } else {
                    toast.error('Failed to start simulator', {
                        description: data.error || 'Unknown error'
                    });
                }
            } catch (error) {
                const errorMessage = error instanceof Error ? error.message : 'Failed to start simulator';
                toast.error('Failed to start simulator', {
                    description: errorMessage
                });
                console.error('Simulator start error:', error);
            } finally {
                setIsStartingSim(false);
            }
        }
    };

    useEffect(() => {
        if (activeLiveSource === 'yourdyno' && isSimulatorActive) {
            void stopSimulator(true);
            toast.info('Simulator controls are only available with JetDrive source.');
        }
    }, [activeLiveSource, isSimulatorActive, stopSimulator]);

    const handleThrottleChange = (value: number) => {
        // Clamp value between 0-100
        const clampedValue = Math.max(0, Math.min(100, value));
        console.log('[Throttle] Setting to:', clampedValue);
        setSimThrottle(clampedValue);
        
        // Debounce network calls while dragging
        if (simThrottleTimerRef.current) {
            clearTimeout(simThrottleTimerRef.current);
        }
        
        simThrottleTimerRef.current = setTimeout(async () => {
            simThrottleTimerRef.current = null;
            try {
                console.log('[Throttle] Sending to backend:', clampedValue);
                await fetch(`${API_BASE}/simulator/throttle`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tps: clampedValue }),
                });
            } catch (error) {
                console.error('Failed to set throttle:', error);
            }
        }, 100);
    };

    const handleTriggerPull = async () => {
        if (!isSimulatorActive) return;
        if (jetdriveLive.simState && jetdriveLive.simState !== 'idle') {
            toast.warning(`Cannot trigger pull while simulator is ${jetdriveLive.simState}`);
            return;
        }

        setIsTriggeringPull(true);
        try {
            const throttlePct = Math.round(simThrottle);
            // Ensure TPS target is set before triggering pull (some builds ignore throttle in /pull)
            await fetch(`${API_BASE}/simulator/throttle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tps: throttlePct }),
            });

            const res = await fetch(`${API_BASE}/simulator/pull`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ throttle: throttlePct, tps: throttlePct }),
            });

            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data.success) {
                toast.error(data.error || 'Cannot start pull');
                return;
            }

            // Re-assert TPS target right after pull starts to override any WOT defaults
            setTimeout(() => {
                fetch(`${API_BASE}/simulator/throttle`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tps: throttlePct }),
                }).catch(() => undefined);
            }, 80);

            window.dispatchEvent(
                new CustomEvent('dynoai:simulator-pull', {
                    detail: {
                        throttle: throttlePct,
                    },
                }),
            );
            toast.success(`Pull started at ${throttlePct}% throttle`);
        } catch (error) {
            toast.error('Failed to trigger pull');
            console.error('Trigger pull error:', error);
        } finally {
            setIsTriggeringPull(false);
        }
    };

    return (
        <div className="flex h-full flex-col">
            <header className="flex h-12 items-center justify-between border-b border-zinc-800 bg-zinc-950 px-4">
                <div className="flex items-center gap-3">
                    <div className="text-xs font-bold uppercase tracking-[0.2em] text-zinc-200">
                        THUNDERHORSE
                    </div>
                    <div className="text-xs text-zinc-500">·</div>
                    <div className="text-sm font-semibold text-zinc-100">DynoAI</div>
                </div>

                <nav className="flex items-center gap-2 text-xs">
                    {NAV_ITEMS.map((item) => (
                        <Link
                            key={item.to}
                            to={item.to}
                            className={cn(
                                'rounded-md px-3 py-2 transition-colors',
                                isActive(item.to)
                                    ? 'bg-zinc-800 text-white'
                                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900',
                            )}
                        >
                            {item.label}
                        </Link>
                    ))}
                </nav>

                <div className="flex items-center gap-4 text-xs text-zinc-300">
                    <div className="flex items-center gap-1 rounded-full border border-zinc-800 bg-zinc-900/70 p-1">
                        <Button
                            type="button"
                            variant={activeLiveSource === 'jetdrive' ? 'default' : 'ghost'}
                            size="sm"
                            className={cn(
                                'h-7 px-3 text-[11px] font-semibold',
                                activeLiveSource === 'jetdrive'
                                    ? 'bg-blue-600 text-white hover:bg-blue-500'
                                    : 'text-zinc-300 hover:text-white',
                            )}
                            onClick={() => setActiveLiveSource('jetdrive')}
                        >
                            JetDrive
                        </Button>
                        <Button
                            type="button"
                            variant={activeLiveSource === 'yourdyno' ? 'default' : 'ghost'}
                            size="sm"
                            className={cn(
                                'h-7 px-3 text-[11px] font-semibold',
                                activeLiveSource === 'yourdyno'
                                    ? 'bg-emerald-600 text-white hover:bg-emerald-500'
                                    : 'text-zinc-300 hover:text-white',
                            )}
                            onClick={() => setActiveLiveSource('yourdyno')}
                        >
                            YourDyno
                        </Button>
                    </div>
                    <div className="flex items-center gap-2">
                        <span
                            className={cn(
                                'h-2 w-2 rounded-full',
                                activeLive.isConnected ? 'bg-green-500 animate-pulse' : 'bg-zinc-600',
                            )}
                        />
                        <span>{activeLive.isConnected ? 'Connected' : 'Disconnected'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span
                            className={cn(
                                'h-2 w-2 rounded-full',
                                activeLive.isCapturing ? 'bg-red-500 animate-pulse' : 'bg-zinc-600',
                            )}
                        />
                        <span>Recording</span>
                    </div>
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className={cn(
                            'h-7 px-3 text-xs font-medium transition-colors',
                            isSimulatorActive 
                                ? 'bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 border border-yellow-500/40' 
                                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800',
                            activeLiveSource === 'yourdyno' && 'opacity-60 cursor-not-allowed',
                        )}
                        onClick={handleToggleSimulator}
                        disabled={isStartingSim || activeLiveSource === 'yourdyno'}
                    >
                        {isStartingSim ? 'Starting...' : isSimulatorActive ? 'Sim ON' : 'Sim OFF'}
                    </Button>
                    <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-zinc-400 hover:text-zinc-200"
                        onClick={() => setHardwareOpen(true)}
                    >
                        <Settings2 className="h-4 w-4" />
                    </Button>
                </div>
            </header>

            <div className="flex flex-1 flex-col min-h-0">
                {isSimulatorActive && (
                    <>
                        <div className="flex h-6 items-center justify-center bg-yellow-500/10 border-b border-yellow-500/30 text-xs font-bold uppercase tracking-widest text-yellow-400">
                            Simulator Mode
                        </div>
                        <div className="flex items-center gap-4 bg-zinc-900/50 border-b border-yellow-500/30 px-6 py-3">
                            <div className="flex items-center gap-3 text-sm text-zinc-300">
                                <span className="font-semibold">Throttle:</span>
                                <span className="font-mono text-yellow-400 font-bold min-w-[4ch] text-right">{Math.round(simThrottle)}%</span>
                            </div>
                            <div className="flex-1 max-w-md">
                                <Slider
                                    value={[Math.max(0, Math.min(100, simThrottle))]}
                                    onValueChange={(v) => handleThrottleChange(v[0] ?? 0)}
                                    min={0}
                                    max={100}
                                    step={1}
                                />
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-zinc-400">State: {jetdriveLive.simState ?? 'unknown'}</span>
                                <Button
                                    type="button"
                                    size="sm"
                                    className="h-7 bg-orange-600 hover:bg-orange-500 text-white"
                                    onClick={handleTriggerPull}
                                    disabled={isTriggeringPull || !!(jetdriveLive.simState && jetdriveLive.simState !== 'idle')}
                                >
                                    <Play className="mr-1.5 h-3.5 w-3.5" />
                                    {isTriggeringPull ? 'Starting...' : 'Trigger Pull'}
                                </Button>
                            </div>
                        </div>
                    </>
                )}
                <div className={cn('flex-1 min-h-0', isSimulatorActive && 'ring-2 ring-yellow-500/70 rounded-md m-1')}>
                    <CommandCenter
                        live={activeLive}
                        hardwareOpen={hardwareOpen}
                        onHardwareOpenChange={setHardwareOpen}
                    />
                </div>
            </div>
        </div>
    );
}

// ==================== TYPES ====================

interface RunInfo {
    run_id: string;
    timestamp: string;
    peak_hp: number;
    peak_tq: number;
    status: string;
    source?: 'simulator_pull' | 'real' | 'simulate' | 'unknown' | string;
    notes?: string;
    tags?: string[];
}

// Workflow states
type WorkflowState = 'disconnected' | 'connecting' | 'idle' | 'monitoring' | 'run_detected' | 'capturing' | 'analyzing' | 'complete';

// ==================== HELPER COMPONENTS ====================

// Needle-style gauge (half circle with tick marks)
function NeedleGauge({
    label,
    value,
    units,
    color = '#22d3ee',
    min = 0,
    max = 100,
    warning,
    critical,
    decimals = 0,
    segments = 5
}: {
    label: string;
    value: number;
    units: string;
    color?: string;
    min?: number;
    max?: number;
    warning?: number;
    critical?: number;
    decimals?: number;
    segments?: number;
}) {
    const percentage = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
    const isWarning = warning && value >= warning;
    const isCritical = critical && value >= critical;
    const displayColor = isCritical ? '#ef4444' : isWarning ? '#f59e0b' : color;

    // Needle angle: -90deg (left) to 90deg (right) for half circle
    const needleAngle = -90 + (percentage / 100) * 180;

    // Compact gauge dimensions
    const size = 120;
    const viewHeight = 75;
    const cx = size / 2;
    const cy = 50;
    const outerRadius = 40;
    const innerRadius = 34;
    const needleLength = 30;

    // Generate tick marks
    const ticks: { x1: number; y1: number; x2: number; y2: number; tickColor: string }[] = [];
    for (let i = 0; i <= segments; i++) {
        const angle = -90 + (i / segments) * 180;
        const rad = (angle * Math.PI) / 180;
        const x1 = cx + Math.cos(rad) * innerRadius;
        const y1 = cy + Math.sin(rad) * innerRadius;
        const x2 = cx + Math.cos(rad) * outerRadius;
        const y2 = cy + Math.sin(rad) * outerRadius;

        // Color segments
        const segmentWarning = warning ? ((warning - min) / (max - min)) * segments : segments;
        const segmentCritical = critical ? ((critical - min) / (max - min)) * segments : segments;
        let tickColor = '#52525b'; // zinc-600
        if (i >= segmentCritical) tickColor = '#ef4444';
        else if (i >= segmentWarning) tickColor = '#f59e0b';

        ticks.push({ x1, y1, x2, y2, tickColor });
    }

    // Arc path for the gauge background
    const arcPath = `M ${cx - outerRadius} ${cy} A ${outerRadius} ${outerRadius} 0 0 1 ${cx + outerRadius} ${cy}`;

    return (
        <div className="relative rounded-xl bg-gradient-to-br from-zinc-900/90 to-zinc-950/90 border border-zinc-800/60 p-3 overflow-hidden group hover:border-zinc-700/60 transition-all duration-300">
            {/* Label at top - horizontal with units */}
            <div className="text-[10px] uppercase tracking-[0.15em] text-zinc-500 font-medium font-mono mb-1">
                {label} {units}
            </div>

            {/* Gauge and value side by side */}
            <div className="flex items-center gap-2">
                <svg width={size} height={viewHeight} viewBox={`0 0 ${size} ${viewHeight}`} className="flex-shrink-0">
                    {/* Arc background */}
                    <path
                        d={arcPath}
                        fill="none"
                        stroke="rgba(63, 63, 70, 0.5)"
                        strokeWidth="6"
                        strokeLinecap="round"
                    />

                    {/* Colored arc based on value */}
                    <path
                        d={arcPath}
                        fill="none"
                        stroke={displayColor}
                        strokeWidth="6"
                        strokeLinecap="round"
                        strokeDasharray={`${(percentage / 100) * Math.PI * outerRadius} ${Math.PI * outerRadius}`}
                        style={{ filter: `drop-shadow(0 0 3px ${displayColor}30)` }}
                        className="transition-all duration-300"
                    />

                    {/* Tick marks */}
                    {ticks.map((tick, i) => (
                        <line
                            key={i}
                            x1={tick.x1}
                            y1={tick.y1}
                            x2={tick.x2}
                            y2={tick.y2}
                            stroke={tick.tickColor}
                            strokeWidth="2"
                            strokeLinecap="round"
                        />
                    ))}

                    {/* Needle - simple tapered line */}
                    <g style={{ transform: `rotate(${needleAngle}deg)`, transformOrigin: `${cx}px ${cy}px`, transition: 'transform 0.3s ease-out' }}>
                        <path
                            d={`M ${cx - 2} ${cy} L ${cx} ${cy - needleLength} L ${cx + 2} ${cy} Z`}
                            fill={displayColor}
                        />
                        <line
                            x1={cx}
                            y1={cy}
                            x2={cx}
                            y2={cy + 6}
                            stroke={displayColor}
                            strokeWidth="2"
                            strokeLinecap="round"
                        />
                    </g>

                    {/* Center pivot */}
                    <circle cx={cx} cy={cy} r="4" fill="#18181b" stroke="#3f3f46" strokeWidth="1.5" />
                    <circle cx={cx} cy={cy} r="1.5" fill={displayColor} />

                    {/* Min/Max below arc */}
                    <text x={cx - outerRadius + 5} y={cy + 14} fill="#52525b" fontSize="8" textAnchor="start" fontFamily="monospace">
                        {min}
                    </text>
                    <text x={cx + outerRadius - 5} y={cy + 14} fill="#52525b" fontSize="8" textAnchor="end" fontFamily="monospace">
                        {max >= 1000 ? `${(max / 1000).toFixed(0)}k` : max}
                    </text>
                </svg>

                {/* Value display - right of gauge */}
                <div className="flex-1 text-right pr-1">
                    <span
                        className="text-2xl font-bold tabular-nums font-mono"
                        style={{ color: displayColor, textShadow: `0 0 12px ${displayColor}20` }}
                    >
                        {value.toLocaleString(undefined, { maximumFractionDigits: decimals })}
                    </span>
                </div>
            </div>
        </div>
    );
}

// Compact gauge for live data
function LiveGauge({
    label,
    value,
    units,
    color = '#4ade80',
    min = 0,
    max = 100,
    warning,
    critical,
    size = 'normal',
    decimals = 1
}: {
    label: string;
    value: number;
    units: string;
    color?: string;
    min?: number;
    max?: number;
    warning?: number;
    critical?: number;
    size?: 'normal' | 'large';
    decimals?: number;
}) {
    const percentage = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
    const isWarning = warning && value >= warning;
    const isCritical = critical && value >= critical;
    const displayColor = isCritical ? '#ef4444' : isWarning ? '#f59e0b' : color;

    return (
        <div className={`relative rounded-xl bg-gradient-to-br from-zinc-900/90 to-zinc-950/90 border border-zinc-800/60 overflow-hidden group hover:border-zinc-700/60 transition-all duration-300 ${size === 'large' ? 'p-5' : 'p-3'}`}>
            {/* Subtle corner glow */}
            <div
                className="absolute -top-4 -right-4 w-12 h-12 rounded-full blur-xl opacity-10 group-hover:opacity-15 transition-opacity"
                style={{ backgroundColor: displayColor }}
            />

            {/* Progress bar background */}
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-zinc-800/50">
                <motion.div
                    className="h-full transition-all duration-300"
                    style={{
                        width: `${percentage}%`,
                        backgroundColor: displayColor,
                        boxShadow: `0 0 6px ${displayColor}30`
                    }}
                    initial={{ width: 0 }}
                    animate={{ width: `${percentage}%` }}
                />
            </div>

            <div className="text-[10px] uppercase tracking-[0.15em] text-zinc-500 mb-1.5 font-medium font-mono">
                {label}
            </div>
            <div className="flex items-baseline gap-1.5">
                <span
                    className={`font-bold tabular-nums tracking-tight ${size === 'large' ? 'text-4xl' : 'text-2xl'}`}
                    style={{ color: displayColor, textShadow: `0 0 12px ${displayColor}20` }}
                >
                    {value.toLocaleString(undefined, { maximumFractionDigits: decimals })}
                </span>
                <span className="text-xs text-zinc-500 font-mono">{units}</span>
            </div>
        </div>
    );
}

// AFR indicator with target comparison - styled to match LiveGauge
function AFRIndicator({
    value,
    target,
    showDelta = true
}: {
    value: number;
    target: number;
    showDelta?: boolean;
}) {
    const delta = value - target;
    const isLean = delta > 0.3;
    const isRich = delta < -0.3;
    const status = isLean ? 'LEAN' : isRich ? 'RICH' : 'ON TARGET';
    const statusColor = isLean ? '#ef4444' : isRich ? '#3b82f6' : '#22c55e';

    // Progress-style indicator: how far from target (centered at 50%)
    const maxDelta = 2.0; // +/- 2 AFR points = full scale
    const normalizedDelta = Math.max(-1, Math.min(1, delta / maxDelta));
    const barPosition = 50 + (normalizedDelta * 50); // 0-100, centered at 50

    return (
        <div className="relative rounded-xl bg-gradient-to-br from-zinc-900/90 to-zinc-950/90 border border-zinc-800/60 p-3 overflow-hidden group hover:border-zinc-700/60 transition-all duration-300">
            {/* Corner glow matching LiveGauge */}
            <div
                className="absolute -top-4 -right-4 w-12 h-12 rounded-full blur-xl opacity-10 group-hover:opacity-15 transition-opacity"
                style={{ backgroundColor: statusColor }}
            />

            {/* AFR deviation bar at bottom - like LiveGauge progress */}
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-zinc-800/50">
                {/* Center marker */}
                <div className="absolute left-1/2 top-0 w-px h-full bg-zinc-600" />
                {/* Deviation indicator */}
                <motion.div
                    className="absolute top-0 h-full transition-all duration-300"
                    style={{
                        left: delta >= 0 ? '50%' : `${barPosition}%`,
                        width: `${Math.abs(normalizedDelta) * 50}%`,
                        backgroundColor: statusColor,
                        boxShadow: `0 0 6px ${statusColor}30`
                    }}
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.abs(normalizedDelta) * 50}%` }}
                />
            </div>

            <div className="text-[10px] uppercase tracking-[0.15em] text-zinc-500 mb-1.5 font-medium font-mono">
                Air/Fuel Ratio
            </div>

            <div className="flex items-baseline gap-1.5">
                <span
                    className="text-2xl font-bold tabular-nums tracking-tight"
                    style={{ color: statusColor, textShadow: `0 0 12px ${statusColor}20` }}
                >
                    {value > 0 ? value.toFixed(1) : '—'}
                </span>
                <span className="text-xs text-zinc-500 font-mono">:1</span>
                {showDelta && value > 0 && (
                    <span className={`text-xs font-medium font-mono ml-1 ${isLean ? 'text-red-400' : isRich ? 'text-blue-400' : 'text-green-400'}`}>
                        {delta > 0 ? '+' : ''}{delta.toFixed(2)}
                    </span>
                )}
            </div>

            <div className="mt-1 flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-[10px] text-zinc-500 font-mono">
                    <Crosshair className="w-2.5 h-2.5 text-zinc-600" />
                    <span>Target: {target.toFixed(1)}</span>
                </div>
                <Badge
                    className="text-[8px] px-1.5 py-0 font-mono tracking-wider border h-4"
                    style={{
                        backgroundColor: `${statusColor}10`,
                        color: statusColor,
                        borderColor: `${statusColor}25`
                    }}
                >
                    {status}
                </Badge>
            </div>
        </div>
    );
}

// Workflow state indicator
function WorkflowIndicator({ state, rpmThreshold }: { state: WorkflowState; rpmThreshold: number }) {
    const states: { key: WorkflowState; label: string; icon: typeof Activity }[] = [
        { key: 'disconnected', label: 'Disconnected', icon: WifiOff },
        { key: 'idle', label: 'Connected', icon: Wifi },
        { key: 'monitoring', label: 'Monitoring', icon: Radio },
        { key: 'run_detected', label: 'Run Detected!', icon: AlertTriangle },
        { key: 'capturing', label: 'Capturing...', icon: Activity },
        { key: 'analyzing', label: 'Analyzing', icon: RefreshCw },
        { key: 'complete', label: 'Complete', icon: CheckCircle2 },
    ];

    const currentIndex = states.findIndex(s => s.key === state);
    const CurrentIcon = states[currentIndex]?.icon || Activity;

    const stateColors: Record<WorkflowState, string> = {
        disconnected: '#71717a',
        connecting: '#22d3ee',
        idle: '#22c55e',
        monitoring: '#22d3ee',
        run_detected: '#f59e0b',
        capturing: '#ef4444',
        analyzing: '#a78bfa',
        complete: '#22c55e',
    };

    return (
        <div className="flex items-center gap-3 px-4 py-2 rounded-full bg-zinc-900/70 border border-zinc-800/80 backdrop-blur-sm">
            <div
                className="relative w-8 h-8 rounded-lg flex items-center justify-center"
                style={{ backgroundColor: `${stateColors[state]}10` }}
            >
                <CurrentIcon
                    className={`w-4 h-4 ${state === 'capturing' || state === 'monitoring' ? 'animate-pulse' : ''}`}
                    style={{ color: stateColors[state] }}
                />
                {(state === 'capturing' || state === 'monitoring') && (
                    <div
                        className="absolute inset-0 rounded-lg animate-ping opacity-15"
                        style={{ backgroundColor: stateColors[state] }}
                    />
                )}
            </div>
            <div>
                <div className="text-xs font-medium font-mono uppercase tracking-wider" style={{ color: stateColors[state] }}>
                    {states[currentIndex]?.label || 'Unknown'}
                </div>
                {state === 'monitoring' && (
                    <div className="text-[10px] text-zinc-500 font-mono tracking-wide">
                        Waiting for RPM &gt; {rpmThreshold}...
                    </div>
                )}
            </div>
        </div>
    );
}

// VE Grid heatmap (compact)
interface VEGridRow { rpm: number; values: number[] }
interface VEGridSpec { map_bins: number[] }

// Standard bins matching LiveVETable (Harley M8 preset)
const STANDARD_RPM_BINS = [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500];
const STANDARD_MAP_BINS = [20, 30, 40, 50, 60, 70, 80, 90, 100, 110];

// Find nearest value from source grid
function findNearestValue(
    sourceGrid: Map<string, number>,
    sourceRpms: number[],
    sourceMaps: number[],
    targetRpm: number,
    targetMap: number
): number {
    // Find closest RPM
    let closestRpm = sourceRpms[0];
    let minRpmDiff = Math.abs(sourceRpms[0] - targetRpm);
    for (const rpm of sourceRpms) {
        const diff = Math.abs(rpm - targetRpm);
        if (diff < minRpmDiff) {
            minRpmDiff = diff;
            closestRpm = rpm;
        }
    }

    // Find closest MAP
    let closestMap = sourceMaps[0];
    let minMapDiff = Math.abs(sourceMaps[0] - targetMap);
    for (const map of sourceMaps) {
        const diff = Math.abs(map - targetMap);
        if (diff < minMapDiff) {
            minMapDiff = diff;
            closestMap = map;
        }
    }

    // Return value from closest cell, or 1.0 (no correction) if not found
    return sourceGrid.get(`${closestRpm},${closestMap}`) ?? 1.0;
}

function VEHeatmapCompact({ veGrid, grid }: { veGrid: VEGridRow[]; grid: VEGridSpec }) {
    if (veGrid.length === 0 || grid.map_bins.length === 0) return null;

    // Build source grid map for quick lookup
    const sourceGrid = new Map<string, number>();
    const sourceRpms: number[] = [];
    const sourceMaps = [...grid.map_bins];

    veGrid.forEach(row => {
        sourceRpms.push(row.rpm);
        grid.map_bins.forEach((map, idx) => {
            if (row.values[idx] !== undefined && row.values[idx] !== null) {
                sourceGrid.set(`${row.rpm},${map}`, row.values[idx]);
            }
        });
    });

    // Remove duplicates and sort
    const uniqueSourceRpms = Array.from(new Set(sourceRpms)).sort((a, b) => a - b);

    // Expand to standard bins matching LiveVETable
    const expandedData: number[][] = STANDARD_RPM_BINS.map(rpm => {
        return STANDARD_MAP_BINS.map(map => {
            // Check if exact match exists
            const exact = sourceGrid.get(`${rpm},${map}`);
            if (exact !== undefined) {
                return (exact - 1) * 100;
            }
            // Use nearest neighbor from source grid
            const nearest = findNearestValue(sourceGrid, uniqueSourceRpms, sourceMaps, rpm, map);
            return (nearest - 1) * 100;
        });
    });

    const rowLabels = STANDARD_RPM_BINS.map((r) => String(r));
    const colLabels = STANDARD_MAP_BINS.map((m) => String(m));

    return (
        <div className="space-y-2">
            <VEHeatmapLegend clampLimit={7} />
            <VEGrid
                data={expandedData}
                rowLabels={rowLabels}
                colLabels={colLabels}
                clampLimit={7}
                showClampIndicators={true}
                showValues={true}
                valueDecimals={1}
                valueLabel="Correction"
                tooltipLoadUnit="kPa"
                className="text-xs"
            />
        </div>
    );
}

// AFR Status Badge
function AFRStatusBadge({ status }: { status: string }) {
    const styles: Record<string, string> = {
        'LEAN': 'bg-red-500/20 text-red-400 border-red-500/30',
        'RICH': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        'BALANCED': 'bg-green-500/20 text-green-400 border-green-500/30',
        'OK': 'bg-green-500/20 text-green-400 border-green-500/30',
    };
    return (
        <Badge variant="outline" className={`${styles[status] || 'bg-zinc-800'} font-medium text-xs`}>
            {status}
        </Badge>
    );
}

// Simulator types
interface SimulatorProfile {
    id: string;
    name: string;
    family: string;
    displacement_ci: number;
    idle_rpm: number;
    redline_rpm: number;
    max_hp: number;
    max_tq: number;
}

interface SimulatorStatus {
    active: boolean;
    state: 'idle' | 'pull' | 'decel' | 'cooldown' | 'stopped';
    profile?: string;
    current?: {
        rpm: number;
        horsepower: number;
        torque: number;
        afr: number;
        tps?: number;
    };
}

// ==================== MAIN COMPONENT ====================

function JetDriveAutoTunePageOld() {
    // Configuration state
    const [afrTargets, setAfrTargets] = useState<Record<number, number>>(() => ({ ...DEFAULT_AFR_TARGETS }));
    const [rpmThreshold, setRpmThreshold] = useState(2000);
    const [showSettings, setShowSettings] = useState(false);
    const [activeMainTab, setActiveMainTab] = useState('tuning');
    const [isReducedMotion, setIsReducedMotion] = useState(false);
    
    // Wizard mode toggle (new simplified UI)
    const [wizardMode, setWizardMode] = useState(false);
    
    // AI Voice Assistant (re-enabled for wizard)
    const aiAssistant = useAIAssistant({ enabled: wizardMode });
    
    // VE Export modal state
    const [exportModalOpen, setExportModalOpen] = useState(false);
    const [pendingExportData, setPendingExportData] = useState<LiveVEExportData | null>(null);
    
    // Imported tune state
    const [importedTune, setImportedTune] = useState<TuneImportResult | null>(null);
    const [tuneLoadError, setTuneLoadError] = useState<string | null>(null);
    
    // Apply workflow state (Phase 3)
    const [applyPreviewOpen, setApplyPreviewOpen] = useState(false);
    const [veBoundsPreset, setVeBoundsPreset] = useState<VEBoundsPreset>('stock_harley');

    // Run state
    const [runId, setRunId] = useState(`dyno_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}_${Date.now().toString(36)}`);
    const [selectedRun, setSelectedRun] = useState<string | null>(null);
    const [selectedRunMode, setSelectedRunMode] = useState<'simulator_pull' | 'simulate' | 'csv' | null>(null); // Track which mode was used for the selected run
    const [lastPullSummary, setLastPullSummary] = useState<PullSummary | null>(null);
    const [pvvContent, setPvvContent] = useState<string>('');
    const [textExportContent, setTextExportContent] = useState<string>('');
    const [isStartingMonitor, setIsStartingMonitor] = useState(false);
    const [useEnhancedTable, setUseEnhancedTable] = useState(true); // Toggle for enhanced table
    const [comparisonMetric, setComparisonMetric] = useState<'hp' | 'tq' | 'both'>('hp');
    const [comparisonSelectedRunIds, setComparisonSelectedRunIds] = useState<string[]>([]);
    const [comparisonBaselineRunId, setComparisonBaselineRunId] = useState<string | null>(null);
    const [comparisonSource, setComparisonSource] = useState<'actual' | 'simulator' | 'real' | 'simulated' | 'all'>('actual');
    const [simThrottle, setSimThrottle] = useState<number>(0);
    const simThrottleSendRef = useRef<number | null>(null);
    const simThrottleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const [pullThrottle, setPullThrottle] = useState<number>(100); // Throttle % for triggered pulls

    // Audio capture state (real recording)
    const [audioRecording, setAudioRecording] = useState(false);
    const [audioKnockDetected, setAudioKnockDetected] = useState(false);

    // Auto-advance (wizard): collect → analyze when coverage ready
    const [autoAdvancePaused, setAutoAdvancePaused] = useState(false);
    const [autoAdvanceTimer, setAutoAdvanceTimer] = useState<ReturnType<typeof setTimeout> | null>(null);
    const [secondsRemaining, setSecondsRemaining] = useState(0);

    // Transient Fuel Analysis state
    const [transientFuelEnabled, setTransientFuelEnabled] = useState(false);

    // Virtual ECU state
    const [virtualECUEnabled, setVirtualECUEnabled] = useState(false);
    const [veScenario, setVeScenario] = useState<VEScenario>('lean');
    const [veErrorPct, setVeErrorPct] = useState(-10.0);
    const [veErrorStd, setVeErrorStd] = useState(5.0);
    
    // Auto-pull settings for simulator
    const [autoPullEnabled, setAutoPullEnabled] = useState(false);
    const [autoPullInterval, setAutoPullInterval] = useState(15); // seconds

    // Audio engine removed (AI Assistant now used for wizard mode voice)

    // Setup Wizard state (persisted to localStorage)
    const SETUP_STORAGE_KEY = 'dynoai_setup_complete';
    const [showSetupWizard, setShowSetupWizard] = useState(() => {
        try {
            const saved = localStorage.getItem(SETUP_STORAGE_KEY);
            return saved !== 'true';
        } catch {
            return true;
        }
    });
    const [bikeConfig, setBikeConfig] = useState<BikeConfig | null>(null);
    const [dynoConfig, setDynoConfig] = useState<DynoConnectionConfig | null>(null);

    // Handle setup wizard completion
    const handleSetupComplete = useCallback((setupResult: {
        dynoConfig: DynoConnectionConfig;
        bikeConfig: BikeConfig;
        tuneImport: TuneImportResult | null;
    }) => {
        console.log('[JetDriveAutoTunePage] Setup complete:', {
            hasDynoConfig: !!setupResult.dynoConfig,
            hasBikeConfig: !!setupResult.bikeConfig,
            hasTuneImport: !!setupResult.tuneImport,
        });
        setDynoConfig(setupResult.dynoConfig);
        setBikeConfig(setupResult.bikeConfig);
        if (setupResult.tuneImport) {
            console.log('[JetDriveAutoTunePage] Setting imported tune:', {
                sourceName: setupResult.tuneImport.sourceName,
                source: setupResult.tuneImport.source,
                hasVeFront: !!setupResult.tuneImport.veFront,
                hasVeRear: !!setupResult.tuneImport.veRear,
                veFrontRows: setupResult.tuneImport.veFront?.rows?.length,
                veFrontCols: setupResult.tuneImport.veFront?.columns?.length,
                veFrontSampleValues: setupResult.tuneImport.veFront?.values?.[0]?.slice(0, 3),
                rpmBins: setupResult.tuneImport.rpmBins,
                mapBins: setupResult.tuneImport.mapBins,
                afrTargetKeys: Object.keys(setupResult.tuneImport.afrTargets || {}),
            });
            setImportedTune(setupResult.tuneImport);
            if (setupResult.tuneImport.afrTargets && Object.keys(setupResult.tuneImport.afrTargets).length > 0) {
                setAfrTargets(setupResult.tuneImport.afrTargets);
            }
            toast.success(`Tune loaded: ${setupResult.tuneImport.sourceName}`);
        } else {
            console.log('[JetDriveAutoTunePage] No tune imported');
        }
        setShowSetupWizard(false);
        try {
            localStorage.setItem(SETUP_STORAGE_KEY, 'true');
        } catch {
            // Ignore storage errors
        }
        toast.success('Setup complete! Ready to tune.');
    }, []);

    // Re-run setup wizard
    const handleRerunSetup = useCallback(() => {
        setShowSetupWizard(true);
        try {
            localStorage.removeItem(SETUP_STORAGE_KEY);
        } catch {
            // Ignore storage errors
        }
    }, []);

    // Workflow state
    const [workflowState, setWorkflowState] = useState<WorkflowState>('disconnected');

    // Simulator state
    const [isSimulatorActive, setIsSimulatorActive] = useState(false);
    const [simState, setSimState] = useState<SimulatorStatus['state']>('stopped');
    const [selectedProfile, setSelectedProfile] = useState<string>('m8_114');
    const [isStartingSimulator, setIsStartingSimulator] = useState(false);
    const [activeLiveSource, setActiveLiveSource] = useState<'jetdrive' | 'yourdyno'>('jetdrive');

    // JetDrive live hook
    const jetdriveLive = useJetDriveLive({
        apiUrl: API_BASE,
        pollInterval: 100,  // 100ms (10Hz) - fast updates for live tuning
        isSimulatorActive,
    });

    // YourDyno live hook (uses compatible /hardware/* aliases on backend)
    const yourdynoLive = useYourDynoLive({
        apiUrl: YOURDYNO_API_BASE,
        pollInterval: 100,
        isSimulatorActive: false,
    });

    const liveApiBase = activeLiveSource === 'yourdyno' ? YOURDYNO_API_BASE : API_BASE;
    const activeLive = activeLiveSource === 'yourdyno' ? yourdynoLive : jetdriveLive;

    const {
        isConnected,
        isCapturing,
        providerName,
        channelCount,
        channels,
        dataSource,
        startCapture,
        stopCapture,
        clearChannels,
    } = activeLive;

    useEffect(() => {
        // Simulator transport exists only for JetDrive endpoints.
        if (activeLiveSource === 'yourdyno' && isSimulatorActive) {
            setIsSimulatorActive(false);
            setSimState('stopped');
            toast.info('Simulator controls are only available with JetDrive source.');
        }
    }, [activeLiveSource, isSimulatorActive]);

    // Explicit mode: simulator vs real vs idle (no combined booleans - prevents cross-contamination)
    const liveMode: 'simulator' | 'real' | 'idle' = isSimulatorActive ? 'simulator' : (isCapturing ? 'real' : 'idle');
    const isLive = liveMode !== 'idle';

    // Extract channel values - memoized to avoid recalculation
    const currentRpm = useMemo(() => {
        const ch = channels['Digital RPM 1'] || channels['RPM'] || channels['chan_42'];
        return ch?.value || 0;
    }, [channels]);

    // Dual-cylinder AFR extraction (LC1 = Front, LC2 = Rear)
    const currentAfrFront = useMemo(() => {
        const ch = channels['LC1 Volts Petrol AFR'] || 
                   channels['Air/Fuel Ratio 1'] || 
                   channels['AFR 1'] || 
                   channels['AFR'] || 
                   channels['chan_23'];
        return ch?.value || 0;
    }, [channels]);
    
    const currentAfrRear = useMemo(() => {
        const ch = channels['LC2 Volts Petrol AFR2'] || 
                   channels['Air/Fuel Ratio 2'] || 
                   channels['AFR 2'];
        // Fall back to front AFR if rear sensor not available
        return ch?.value || currentAfrFront;
    }, [channels, currentAfrFront]);
    
    // Legacy combined AFR (average of front and rear)
    const currentAfr = useMemo(() => {
        if (currentAfrRear !== currentAfrFront) {
            return (currentAfrFront + currentAfrRear) / 2;
        }
        return currentAfrFront;
    }, [currentAfrFront, currentAfrRear]);

    const currentForce = useMemo(() => {
        // Note: chan_39 is Atmospheric Pressure, NOT Force
        const ch =
            channels['Force Drum 1'] ||
            channels['Force'] ||
            channels['Load'];
        if (ch && typeof ch.value === 'number') return ch.value;

        // Fallback: find any channel containing "force" (handles name mismatches like
        // "Force Drum #1", "Tractive Force", etc.)
        const key = Object.keys(channels).find(k => k.toLowerCase().includes('force'));
        const fallback = key ? channels[key] : undefined;
        return fallback?.value || 0;
    }, [channels]);

    const currentMap = useMemo(() => {
        const ch = channels['MAP kPa'] || channels['MAP'] || channels['chan_102'];
        return ch?.value || 0;
    }, [channels]);

    const currentLoadPct = useMemo(() => {
        // Approximate engine load from MAP.
        // 30 kPa ~ idle/cruise vacuum baseline, 100 kPa ~ WOT (atmospheric).
        const map = Number(currentMap) || 0;
        const idleMap = 30;
        const wotMap = 100;
        const pct = ((map - idleMap) / (wotMap - idleMap)) * 100;
        return Math.max(0, Math.min(100, pct));
    }, [currentMap]);

    const currentHp = useMemo(() => {
        const ch = channels['Horsepower'] || channels['HP'] || channels['chan_101'];
        return ch?.value || 0;
    }, [channels]);

    // Get current target AFR based on MAP (finds nearest bin in table)
    const currentTargetAfr = useMemo(() => {
        const mapKeys = Object.keys(afrTargets).map(Number).sort((a, b) => a - b);
        if (mapKeys.length === 0) return 14.0;
        let closest = mapKeys[0];
        for (const key of mapKeys) {
            if (Math.abs(key - currentMap) < Math.abs(closest - currentMap)) {
                closest = key;
            }
        }
        return afrTargets[closest] ?? 14.0;
    }, [currentMap, afrTargets]);

    // Extract temperature channels
    const engineTemp = useMemo(() => {
        const ch = channels['Temperature 1'] || channels['Temp 1'] || channels['Engine Temp'];
        return ch?.value || 0;
    }, [channels]);

    const coolantTemp = useMemo(() => {
        const ch = channels['Temperature 2'] || channels['Temp 2'] || channels['Coolant Temp'];
        return ch?.value || 0;
    }, [channels]);

    const egtTemp = useMemo(() => {
        // EGT might be on Temperature 2 or a separate channel
        const ch = channels['EGT'] || channels['Exhaust Gas Temp'] || channels['Temperature 2'];
        return ch?.value || 0;
    }, [channels]);

    // Extract TPS for engine state classification
    const currentTps = useMemo(() => {
        const ch = channels['TPS'] || channels['Throttle Position'] || channels['TP'];
        return ch?.value || 0;
    }, [channels]);

    // Derive engine operating state from simState + TPS/MAP/RPM
    const engineState = useMemo((): WizardLiveStatus['engineState'] => {
        // Priority: use simState if in simulator mode
        if (isSimulatorActive) {
            if (simState === 'pull') return 'wot';
            if (simState === 'decel') return 'decel';
            if (simState === 'idle') return 'idle';
            if (simState === 'cooldown') return 'cruise';
        }

        // Otherwise classify from TPS/MAP/RPM thresholds
        const rpm = currentRpm;
        const tps = currentTps;
        const map = currentMap;

        // WOT: TPS >=85% OR MAP >=85 kPa
        if (tps >= 85 || map >= 85) return 'wot';

        // Idle: RPM <1200 AND TPS <5% AND MAP <45 kPa
        if (rpm < 1200 && tps < 5 && map < 45) return 'idle';

        // Decel: TPS <=3%, RPM >1500
        if (tps <= 3 && rpm > 1500) return 'decel';

        // Tip-in: TPS rate would require derivative; approximate with high TPS but not WOT
        if (tps > 50 && tps < 85) return 'tip_in';

        // Default: cruise
        if (rpm >= 1500) return 'cruise';

        return 'unknown';
    }, [isSimulatorActive, simState, currentRpm, currentTps, currentMap]);

    // Derive run state from workflowState and simState
    const runState = useMemo((): WizardLiveStatus['runState'] => {
        // Map workflowState to runState
        if (workflowState === 'disconnected') return 'disconnected';
        if (workflowState === 'monitoring') return 'monitoring';
        if (workflowState === 'capturing') return 'pull';
        if (workflowState === 'analyzing') return 'analyzing';
        if (workflowState === 'complete') return 'complete';

        // If simulator is active, use simState
        if (isSimulatorActive) {
            if (simState === 'pull') return 'pull';
            if (simState === 'decel' || simState === 'cooldown') return 'cooldown';
            if (simState === 'idle') return 'idle';
        }

        return 'idle';
    }, [workflowState, isSimulatorActive, simState]);

    // Legacy getter functions for backward compatibility
    const getRpmValue = useCallback(() => currentRpm, [currentRpm]);
    const getAfrValue = useCallback(() => currentAfr, [currentAfr]);
    const getForceValue = useCallback(() => currentForce, [currentForce]);
    const getMapValue = useCallback(() => currentMap, [currentMap]);
    const getHpValue = useCallback(() => currentHp, [currentHp]);

    // Fetch simulator profiles
    const { data: profilesData } = useQuery({
        queryKey: ['simulator-profiles'],
        queryFn: async () => {
            const res = await fetch(`${API_BASE}/simulator/profiles`);
            return res.json();
        },
        staleTime: Infinity, // Profiles don't change
    });

    // Poll simulator status when active
    const { data: simStatus } = useQuery({
        queryKey: ['simulator-status'],
        queryFn: async () => {
            const res = await fetch(`${API_BASE}/simulator/status`);
            return res.json() as Promise<SimulatorStatus>;
        },
        refetchInterval: isSimulatorActive ? 500 : false,
        enabled: isSimulatorActive,
    });

    // Check if simulator pull data is available
    const { data: pullDataStatus } = useQuery({
        queryKey: ['simulator-pull-data'],
        queryFn: async () => {
            const res = await fetch(`${API_BASE}/simulator/pull-data`);
            if (!res.ok) {
                return { success: false, has_data: false };
            }
            return res.json() as Promise<{ success: boolean; has_data: boolean; points?: number; peak_hp?: number; peak_tq?: number }>;
        },
        refetchInterval: isSimulatorActive ? 2000 : false,
        enabled: isSimulatorActive,
    });

    // Update sim state from status
    useEffect(() => {
        if (simStatus) {
            setSimState(simStatus.state);
            if (!simStatus.active) {
                setIsSimulatorActive(false);
            } else {
                setIsSimulatorActive(true);
            }
        }
    }, [simStatus]);

    // Keep the throttle slider roughly in sync with simulator TPS (when running)
    useEffect(() => {
        if (!simStatus?.active) return;
        const tps = simStatus.current?.tps;
        if (typeof tps === 'number' && !Number.isNaN(tps)) {
            // Avoid fighting the user's drag: only update if we're not in the middle of sending
            if (simThrottleTimerRef.current === null) {
                setSimThrottle(tps);
            }
        }
    }, [simStatus?.active, simStatus?.current?.tps]);

    // Auto-load tune from pvv_template.pvv if available
    useEffect(() => {
        const loadPvvTemplate = async () => {
            try {
                // Try to fetch the PVV template from the config folder
                const response = await fetch('/config/pvv_template.pvv');
                if (!response.ok) {
                    console.log('[TuneImport] No pvv_template.pvv found, using defaults');
                    return;
                }
                
                const content = await response.text();
                const parsed = parsePVV(content);
                
                if (parsed.parseErrors.length > 0 && !parsed.veFront && !parsed.afrTarget) {
                    console.warn('[TuneImport] Failed to parse pvv_template.pvv:', parsed.parseErrors);
                    setTuneLoadError('Failed to parse PVV template');
                    return;
                }
                
                // Extract AFR targets from the PVV
                const newAfrTargets = parsed.afrTarget 
                    ? extractAfrTargets(parsed.afrTarget)
                    : null;
                
                if (newAfrTargets && Object.keys(newAfrTargets).length > 0) {
                    setAfrTargets(newAfrTargets);
                    console.log('[TuneImport] Loaded AFR targets from pvv_template.pvv:', newAfrTargets);
                }
                
                setImportedTune({
                    source: 'pvv',
                    sourceName: parsed.sourceFile || 'pvv_template.pvv',
                    veFront: parsed.veFront,
                    veRear: parsed.veRear,
                    afrTargets: newAfrTargets ?? DEFAULT_AFR_TARGETS,
                    rpmBins: parsed.veFront?.rows ?? [],
                    mapBins: parsed.veFront?.columns ?? [],
                });
                
                console.log('[TuneImport] Auto-loaded tune from pvv_template.pvv');
            } catch (e) {
                console.log('[TuneImport] Could not auto-load pvv_template.pvv:', e);
            }
        };
        
        loadPvvTemplate();
    }, []); // Run once on mount

    // Handle tune import from TuneImport component
    const handleTuneImport = useCallback((result: TuneImportResult) => {
        setImportedTune(result);
        setTuneLoadError(null);
        
        // Update AFR targets from imported tune
        if (result.afrTargets && Object.keys(result.afrTargets).length > 0) {
            setAfrTargets(result.afrTargets);
        }
        
    }, []);

    // Handle apply corrections (Phase 3)
    const handleApplyCorrections = useCallback((report: ApplyReport) => {
        if (!pendingExportData || !importedTune) {
            toast.error('Missing data for apply');
            return;
        }
        
        // Export the applied VE tables
        const exportData = {
            sessionId: `session_${Date.now()}`,
            timestamp: new Date().toISOString(),
            enginePreset: pendingExportData.enginePreset,
            veBoundsPreset: veBoundsPreset,
            sourceFile: importedTune.sourceName,
            rpmAxis: pendingExportData.rpmBins,
            mapAxis: pendingExportData.mapBins,
            baseVE: {
                front: importedTune.veFront?.values ?? [],
                rear: importedTune.veRear?.values ?? [],
            },
            corrections: {
                front: pendingExportData.frontCorrections,
                rear: pendingExportData.rearCorrections,
            },
            hitCounts: {
                front: pendingExportData.frontHitCounts,
                rear: pendingExportData.rearHitCounts,
            },
            appliedVE: report.appliedVE,
        };
        
        // Download all formats
        downloadAppliedVEAllFormats(exportData, 'Applied_VE');
        
        toast.success(`Applied corrections to ${report.totalCells - report.skippedCells} cells`);
        setApplyPreviewOpen(false);
        
        console.log('[Apply] Corrections applied:', {
            totalCells: report.totalCells,
            skippedCells: report.skippedCells,
            clampedCells: report.clampedCells,
        });
    }, [pendingExportData, importedTune, veBoundsPreset]);

    const sendSimThrottle = useCallback(async (tps: number) => {
        try {
            await fetch(`${API_BASE}/simulator/throttle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tps }),
            });
        } catch {
            // Silent; UI will keep moving but backend may ignore if sim not running
        }
    }, []);

    const onSimThrottleChange = useCallback((next: number) => {
        setSimThrottle(next);
        simThrottleSendRef.current = next;
        // Debounce network calls while dragging
        if (simThrottleTimerRef.current) {
            clearTimeout(simThrottleTimerRef.current);
        }
        simThrottleTimerRef.current = setTimeout(() => {
            const v = simThrottleSendRef.current;
            simThrottleTimerRef.current = null;
            if (typeof v === 'number') {
                sendSimThrottle(v);
            }
        }, 80);
    }, [sendSimThrottle]);

    const handleWizardThrottleChange = useCallback((value: number) => {
        const rounded = Math.round(value);
        setPullThrottle(rounded);
        onSimThrottleChange(rounded);
    }, [onSimThrottleChange]);

    // Start simulator
    const handleStartSimulator = async () => {
        setIsStartingSimulator(true);
        try {
            const res = await fetch(`${API_BASE}/simulator/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    profile: selectedProfile,
                    virtual_ecu: virtualECUEnabled ? {
                        enabled: true,
                        scenario: veScenario,
                        ve_error_pct: veErrorPct,
                        ve_error_std: veErrorStd,
                        cylinder_balance: 'same',
                        barometric_pressure_inhg: 29.92,
                        ambient_temp_f: 75.0,
                    } : { enabled: false },
                    auto_pull: autoPullEnabled,
                    auto_pull_interval: autoPullInterval,
                }),
            });

            if (!res.ok) {
                const errorData = await res.json().catch(() => ({ error: `HTTP ${res.status}: ${res.statusText}` }));
                throw new Error(errorData.error || errorData.message || `HTTP ${res.status}: ${res.statusText}`);
            }

            const data = await res.json();
            if (data.success) {
                setIsSimulatorActive(true);
                setSimThrottle(0);
                const ecuStatus = data.virtual_ecu_enabled ? ' with Virtual ECU' : '';
                const veScenarioSuffix = virtualECUEnabled ? ` • ${veScenario} VE scenario` : '';
                toast.success(`Simulator started${ecuStatus}: ${data.profile?.name}`, {
                    description: `${data.profile?.max_hp} HP @ ${data.profile?.redline_rpm} RPM redline${veScenarioSuffix}`
                });
                // Simulator uses its own data path - do NOT start real hardware capture
            } else {
                toast.error('Failed to start simulator', {
                    description: data.error || 'Unknown error occurred'
                });
            }
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Failed to start simulator';
            toast.error('Failed to start simulator', {
                description: errorMessage
            });
            console.error('Simulator start error:', error);
        } finally {
            setIsStartingSimulator(false);
        }
    };

    // Stop simulator - clear all channel data to prevent real mode from seeing stale sim data
    const handleStopSimulator = async () => {
        try {
            await fetch(`${API_BASE}/simulator/stop`, { method: 'POST' });
            await clearChannels();
            setIsSimulatorActive(false);
            setSimState('stopped');
            toast.info('Simulator stopped');
        } catch {
            toast.error('Failed to stop simulator');
        }
    };

    // Start real hardware capture - guard against running while simulator is active
    const handleStartCapture = async () => {
        if (isSimulatorActive) {
            toast.error('Stop simulator before starting real capture');
            return;
        }
        await startCapture();
    };

    // Trigger a simulated pull
    const handleTriggerPull = async () => {
        try {
            setLastPullSummary(null);
            console.log(`[JetDrive] Triggering pull with pullThrottle=${pullThrottle}`);
            const res = await fetch(`${API_BASE}/simulator/pull`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ throttle: pullThrottle }),
            });
            const data = await res.json();
            console.log(`[JetDrive] Pull response:`, data);
            if (!data.success) {
                toast.warning(data.error || 'Cannot start pull');
            } else {
                setSimThrottle(pullThrottle);
                simThrottleSendRef.current = pullThrottle;
                console.log('[JetDrive] Calling aiAssistant.onPullStart()');
                aiAssistant.onPullStart(); // 🎤 AI: "Let's go!"
                toast.success(`Pull started at ${pullThrottle}% throttle`);
            }
        } catch {
            toast.error('Failed to trigger pull');
        }
    };

    // Sync audio engine with live RPM/MAP data for realistic engine sound - DISABLED
    // useEffect(() => {
    //     if (!audioState.isPlaying && (isCapturing || isSimulatorActive) && currentRpm > 500) {
    //         // Start audio engine when capture starts
    //         startEngine().catch(console.error);
    //     } else if (audioState.isPlaying && !isCapturing && !isSimulatorActive) {
    //         // Stop audio engine when capture stops
    //         stopEngine();
    //     }

    //     // Update RPM and load in real-time
    //     if (audioState.isPlaying) {
    //         setRpm(currentRpm);
    //         // Calculate load from MAP (0-100 kPa -> 0-1 load)
    //         const load = Math.min(1, Math.max(0, currentMap / 100));
    //         setLoad(load);
    //     }
    // }, [currentRpm, currentMap, isCapturing, isSimulatorActive, audioState.isPlaying, setRpm, setLoad, startEngine, stopEngine]);

    // Update workflow state based on connection/capture/rpm
    useEffect(() => {
        // Simulator mode takes priority
        if (isSimulatorActive) {
            // Always preserve 'complete' state after analysis - don't override it
            if (simState === 'pull') {
                setWorkflowState((prev) => prev === 'complete' ? 'complete' : 'capturing');
            } else if (simState === 'decel' || simState === 'cooldown') {
                setWorkflowState((prev) => prev === 'complete' ? 'complete' : 'analyzing');
            } else {
                setWorkflowState((prev) => prev === 'complete' ? 'complete' : 'monitoring');
            }
            return;
        }

        if (!isConnected) {
            // Preserve 'complete' state even when disconnected - analysis results should persist
            setWorkflowState((prev) => prev === 'complete' ? 'complete' : 'disconnected');
        } else if (isCapturing) {
            if (currentRpm > rpmThreshold) {
                setWorkflowState((prev) => prev === 'complete' ? 'complete' : 'capturing');
            } else {
                setWorkflowState((prev) => prev === 'complete' ? 'complete' : 'monitoring');
            }
        } else {
            setWorkflowState((prev) => prev === 'complete' ? 'complete' : 'idle');
        }
    }, [isConnected, isCapturing, currentRpm, rpmThreshold, isSimulatorActive, simState]);

    // AI Assistant triggers removed (audio/voice features disabled)

    // Status query
    const { data: statusData, refetch: refetchStatus } = useQuery({
        queryKey: ['jetdrive-status'],
        queryFn: async () => {
            const res = await fetch(`${API_BASE}/status`);
            return res.json();
        },
        refetchInterval: 10000,
    });

    const comparisonRunsList: RunInfo[] = useMemo(() => {
        const raw: RunInfo[] = statusData?.runs || [];
        if (comparisonSource === 'all') return raw;
        if (comparisonSource === 'simulated') return raw.filter(r => r.source === 'simulate');
        if (comparisonSource === 'simulator') return raw.filter(r => r.source === 'simulator_pull');
        if (comparisonSource === 'real') return raw.filter(r => r.source === 'real');
        // actual = simulator pulls + real (exclude synthetic)
        return raw.filter(r => r.source !== 'simulate');
    }, [statusData?.runs, comparisonSource]);

    // Fetch detailed data for all runs for comparison
    const { data: allRunsData } = useQuery({
        queryKey: ['jetdrive-all-runs', comparisonRunsList.map(r => r.run_id).join('|')],
        queryFn: async () => {
            if (!comparisonRunsList) return [];

            // Fetch details for up to 5 most recent runs
            const runPromises = comparisonRunsList.slice(0, 10).map(async (run: RunInfo) => {
                try {
                    const res = await fetch(`${API_BASE}/run/${run.run_id}`);
                    const data = await res.json() as { manifest?: unknown };
                    return {
                        ...run,
                        manifest: data.manifest,
                    };
                } catch {
                    return run;
                }
            });

            return Promise.all(runPromises);
        },
        enabled: comparisonRunsList.length > 0,
        staleTime: 30000, // Cache for 30 seconds
    });

    // Keep selection/baseline consistent when the filter changes
    useEffect(() => {
        const valid = new Set(comparisonRunsList.map(r => r.run_id));
        setComparisonSelectedRunIds(prev => prev.filter(id => valid.has(id)));
        setComparisonBaselineRunId(prev => (prev && valid.has(prev) ? prev : null));
    }, [comparisonRunsList]);

    // Runs (with power_curve) to drive the overlay chart
    const comparisonRunsForChart = useMemo(() => {
        if (!allRunsData || allRunsData.length === 0) return [];

        // If explicit selection exists, use it; otherwise default to the most recent 5
        const baseList = comparisonSelectedRunIds.length > 0
            ? allRunsData.filter((r) => comparisonSelectedRunIds.includes(r.run_id))
            : allRunsData.slice(0, 5);

        const baselineId = comparisonBaselineRunId ?? baseList[0]?.run_id ?? null;
        const baseline = baselineId ? allRunsData.find((r) => r.run_id === baselineId) : null;

        // Order: baseline first (if present), then remaining
        const ordered = [
            ...(baseline ? [baseline] : []),
            ...baseList.filter((r) => !baseline || r.run_id !== baseline.run_id),
        ].slice(0, 5);

        return ordered.map((r) => {
            const manifestAny = (r as unknown as { manifest?: any }).manifest;
            const curve = manifestAny?.analysis?.power_curve;
            return {
                run_id: r.run_id,
                peak_hp: r.peak_hp,
                peak_tq: r.peak_tq,
                power_curve: Array.isArray(curve) ? curve : undefined,
            };
        });
    }, [allRunsData, comparisonSelectedRunIds, comparisonBaselineRunId]);

    // Run details query
    const { data: runData } = useQuery({
        queryKey: ['jetdrive-run', selectedRun],
        queryFn: async () => {
            if (!selectedRun) return null;
            try {
                const res = await fetch(`${API_BASE}/run/${selectedRun}`);
                const data = await res.json();
                return data;
            } catch (err) {
                throw err;
            }
        },
        enabled: !!selectedRun,
    });

    // Power opportunities query
    const { data: powerOpportunities, isLoading: powerOpportunitiesLoading } = usePowerOpportunities(
        selectedRun,
        'http://127.0.0.1:5001'
    );

    // Confidence report query
    const { data: confidenceReport } = useQuery({
        queryKey: ['confidence', selectedRun],
        queryFn: async () => {
            if (!selectedRun) return null;
            try {
                const result = await getConfidenceReport(selectedRun);
                return result;
            } catch (err) {
                console.warn('Confidence report not available:', err);
                return null;
            }
        },
        enabled: !!selectedRun,
    });

    // Analyze mutation
    const analyzeMutation = useMutation({
        mutationFn: async ({ mode }: { mode: string }) => {
            // If simulator is active and has pull data, use simulator_pull mode.
            // Otherwise fall back to 'simulate' mode (synthetic data) so analysis always succeeds.
            let actualMode = mode;
            let freshPullData: any = null;
            
            if (isSimulatorActive && mode === 'simulate') {
                // CRITICAL FIX: Do a FRESH check instead of using stale pullDataStatus from React Query
                // The pullDataStatus query only polls every 2 seconds, so it can be stale when user clicks Analyze
                try {
                    console.log('[Analyze] Fetching fresh pull data status...');
                    const freshStatusRes = await fetch(`${API_BASE}/simulator/pull-data`);
                    if (freshStatusRes.ok) {
                        freshPullData = await freshStatusRes.json();
                        console.log('[Analyze] Fresh pull data status:', freshPullData);
                        
                        if (freshPullData?.has_data) {
                            actualMode = 'simulator_pull';
                            console.log(`[Analyze] ✓ Using real pull data (${freshPullData.points} points, ${freshPullData.peak_hp?.toFixed(1)} HP)`);
                        } else {
                            console.warn('[Analyze] ⚠ No pull data available - falling back to simulate mode');
                            actualMode = 'simulate';
                        }
                    } else {
                        console.warn('[Analyze] Could not fetch pull data status, falling back to simulate');
                        actualMode = 'simulate';
                    }
                } catch (err) {
                    console.error('[Analyze] Error checking pull data status:', err);
                    console.warn('[Analyze] Falling back to simulate mode due to error');
                    actualMode = 'simulate';
                }
            }

            console.log('[Analyze] Mode:', mode, '→ Actual mode:', actualMode, '| Simulator active:', isSimulatorActive);
            console.log('[Analyze] Stale pullDataStatus (for comparison):', pullDataStatus);

            const res = await fetch(`${API_BASE}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    run_id: runId,
                    mode: actualMode,
                    afr_targets: afrTargets,
                }),
            });

            if (!res.ok) {
                const errorData = await res.json().catch(() => {
                    return { error: 'Analysis request failed' };
                });
                console.error('[Analyze] Request failed:', res.status, errorData);
                throw new Error(errorData.error || `Analysis failed with status ${res.status}`);
            }

            const result = await res.json();
            console.log('[Analyze] Success:', result);
            return result;
        },
        onSuccess: (data) => {
            if (data.success) {
                // Safely access analysis data with null checks
                const peakHp = data.analysis?.peak_hp ?? 0;
                const peakHpRpm = data.analysis?.peak_hp_rpm ?? 0;
                const actualModeUsed = data.mode || 'unknown';
                const modeUsed = (actualModeUsed === 'simulator_pull') ? 'simulator pull data' : 'simulated data';

                toast.success('Analysis complete!', {
                    description: `${peakHp.toFixed(1)} HP @ ${peakHpRpm} RPM (from ${modeUsed})`
                });
                setSelectedRun(data.run_id);
                setSelectedRunMode(actualModeUsed as 'simulator_pull' | 'simulate' | 'csv'); // Store the actual mode used
                setWorkflowState('complete');
                void refetchStatus();
                // Generate new run ID for next run
                setRunId(`dyno_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}_${Date.now().toString(36)}`);

                if (wizardMode) {
                    void (async () => {
                        try {
                            const nextGen = await generateNextGenAnalysis(data.run_id, { includeFull: true });
                            const nextStep = nextGen.payload?.next_tests?.steps?.[0];
                            const nextAction = nextStep
                                ? `${nextStep.name}: ${nextStep.goal}`
                                : 'Run another pull to build coverage';
                            const coveragePct = coverageComputed?.weightedCoveragePct ?? 0;
                            const pullNumber = (statusData?.runs_count ?? 0) + 1;

                            setLastPullSummary({
                                peakHp: data.analysis?.peak_hp ?? 0,
                                peakTq: data.analysis?.peak_tq ?? 0,
                                peakRpm: data.analysis?.peak_hp_rpm ?? 0,
                                afrAvg: data.analysis?.avg_afr ?? 0,
                                nextAction,
                                coverageGain: coveragePct,
                                pullNumber,
                            });
                        } catch {
                            setLastPullSummary({
                                peakHp: data.analysis?.peak_hp ?? 0,
                                peakTq: data.analysis?.peak_tq ?? 0,
                                peakRpm: data.analysis?.peak_hp_rpm ?? 0,
                                afrAvg: data.analysis?.avg_afr ?? 0,
                                nextAction: 'Run another pull to build coverage',
                            });
                        }
                    })();
                }
            } else {
                toast.error('Analysis failed', { description: data.error });
            }
        },
        onError: (error: Error) => {
            toast.error('Analysis failed', { description: error.message });
        },
    });

    // Coverage from live export data (wizard auto-advance)
    const coverageComputed = useMemo((): CoverageReport | null => {
        if (!pendingExportData?.frontHitCounts || !pendingExportData?.rearHitCounts) return null;
        return calculateDualCylinderCoverage(
            pendingExportData.frontHitCounts,
            pendingExportData.rearHitCounts,
            pendingExportData.rpmBins,
            pendingExportData.mapBins
        );
    }, [pendingExportData]);

    const canProceedToAnalyze = useMemo(() => {
        if (!coverageComputed) return false;
        const totalHits = pendingExportData?.totalHits ?? 0;
        return coverageComputed.weightedCoveragePct >= 60 && totalHits >= 500;
    }, [coverageComputed, pendingExportData?.totalHits]);

    const handleAnalyze = useCallback(async () => {
        aiAssistant.onStepChange?.('analyze');
        await analyzeMutation.mutateAsync({ mode: 'simulate' });
    }, [aiAssistant, analyzeMutation]);

    // Track previous simState to detect pull end
    const prevSimStateRef = useRef<string>('stopped');
    const eventDispatchedRef = useRef<boolean>(false);
    useEffect(() => {
        // Use jetdriveLive.simState if available (more reliable), otherwise fall back to local simState
        const currentState = jetdriveLive.simState || simState;
        
        // Detect pull end: transitioning from 'pull' to 'decel' or 'cooldown'
        const wasPulling = prevSimStateRef.current === 'pull';
        const isNowDecelOrCooldown = currentState === 'decel' || currentState === 'cooldown';
        
        if (wasPulling && isNowDecelOrCooldown && !eventDispatchedRef.current) {
            // Pull just ended, announce with peak HP
            aiAssistant.onPullEnd(currentHp);

            // Dispatch event for AI Coach to update after pull completes
            console.log('[AI Coach] Pull completed, dispatching update event');
            window.dispatchEvent(
                new CustomEvent('dynoai:simulator-pull-complete', {
                    detail: {
                        peakHp: currentHp,
                        state: currentState,
                    },
                }),
            );
            eventDispatchedRef.current = true;

            if (wizardMode && !canProceedToAnalyze && !analyzeMutation.isPending) {
                void handleAnalyze();
            }
        }
        
        // Reset event dispatch flag when back to idle
        if (currentState === 'idle' || currentState === 'stopped') {
            eventDispatchedRef.current = false;
        }
        
        prevSimStateRef.current = currentState;
    }, [aiAssistant, analyzeMutation.isPending, canProceedToAnalyze, currentHp, handleAnalyze, simState, jetdriveLive.simState, wizardMode]);

    // Start hardware monitor
    const handleStartMonitor = async () => {
        setIsStartingMonitor(true);
        setWorkflowState('connecting');
        try {
            const res = await fetch(`${API_BASE}/hardware/monitor/start`, { method: 'POST' });
            if (!res.ok) throw new Error('Failed to start monitor');
            toast.success('Hardware monitor started');
        } catch {
            toast.error('Failed to start monitor');
            setWorkflowState('disconnected');
        } finally {
            setIsStartingMonitor(false);
        }
    };

    // Auto-advance effect: Collect → Analyze when coverage ready
    useEffect(() => {
        if (wizardMode && canProceedToAnalyze && !autoAdvancePaused && !autoAdvanceTimer) {
            setSecondsRemaining(2);
            const timer = setTimeout(() => {
                handleAnalyze();
                toast.success('Auto-advancing to analysis...');
                aiAssistant.onCoverageReady?.();
            }, 2000);
            
            setAutoAdvanceTimer(timer);
            
            // Countdown timer
            let seconds = 2;
            const countdown = setInterval(() => {
                seconds -= 1;
                setSecondsRemaining(seconds);
                if (seconds <= 0) {
                    clearInterval(countdown);
                    setAutoAdvanceTimer(null);
                    setSecondsRemaining(0);
                }
            }, 1000);

            return () => {
                clearTimeout(timer);
                clearInterval(countdown);
                setAutoAdvanceTimer(null);
                setSecondsRemaining(0);
            };
        }
    }, [wizardMode, canProceedToAnalyze, autoAdvancePaused, autoAdvanceTimer, handleAnalyze]);

    // Cleanup auto-advance timer on dismount or mode change
    useEffect(() => {
        return () => {
            if (autoAdvanceTimer) {
                clearTimeout(autoAdvanceTimer);
                setAutoAdvanceTimer(null);
                setSecondsRemaining(0);
            }
        };
    }, [autoAdvanceTimer]);

    // Cancel auto-advance on user interaction
    const handleCancelAutoAdvance = () => {
        if (autoAdvanceTimer) {
            clearTimeout(autoAdvanceTimer);
            setAutoAdvanceTimer(null);
            setAutoAdvancePaused(true);
            setSecondsRemaining(0);
            toast.info('Auto-advance canceled');
            // Re-enable auto-advance after 30 seconds
            setTimeout(() => {
                setAutoAdvancePaused(false);
            }, 30000);
        }
    };

    // Download PVV
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

// Enhanced Smart Prompt Banner Component
function SmartPromptBanner({ 
    step, 
    coverageReport, 
    canProceedToAnalyze, 
    onActionClick, 
    onCancelAdvance,
    secondsRemaining 
}: {
    step: 'setup' | 'collect' | 'analyze' | 'review' | 'apply';
    coverageReport: CoverageReport | null;
    canProceedToAnalyze: boolean;
    onActionClick: (action: string) => void;
    onCancelAdvance?: () => void;
    secondsRemaining?: number;
}) {
    const aiAssistant = useAIAssistant();
    
    const getPrompt = () => {
        switch (step) {
            case 'setup':
                return {
                    title: "Ready to Start!",
                    message: "Import a tune file or use simulator to begin data collection."
                };
            case 'collect':
                if (canProceedToAnalyze) {
                    return {
                        title: "Coverage Target Reached!",
                        message: "60% weighted coverage achieved. Ready to analyze."
                    };
                } else if (coverageReport) {
                    return {
                        title: `Coverage: ${Math.round(coverageReport.weightedCoveragePct)}%`,
                        message: `Weighted coverage: ${Math.round(coverageReport.weightedCoveragePct)}%. Aim for 60% with at least 500 hits.`
                    };
                } else {
                    return {
                        title: "Start Collecting Data",
                        message: "Run some pulls to build your VE correction table."
                    };
                }
            case 'analyze':
                return {
                    title: "Analyzing Data...",
                    message: "Processing your VE corrections and generating recommendations."
                };
            case 'review':
                return {
                    title: "Review Your Corrections",
                    message: "Check the applied changes and coverage before proceeding."
                };
            case 'apply':
                return {
                    title: "Ready to Apply!",
                    message: "Your corrections are ready. Download the tuned file."
                };
            default:
                return { title: "Status Unknown", message: "" };
        }
    };

    const { title, message } = getPrompt();
    const coveragePercentage = coverageReport?.weightedCoveragePct ?? 0;

    return (
        <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="p-4 bg-zinc-900/50 border border-zinc-800 rounded-xl"
            role="status"
            aria-live="polite"
        >
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                        <Zap className="w-4 h-4 text-cyan-400" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-white">{title}</h3>
                        <p className="text-xs text-zinc-400">{message}</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {step === 'collect' && coverageReport && (
                        <div className="text-right">
                            <Badge 
                                variant="outline" 
                                className={canProceedToAnalyze ? 'border-green-500/30 text-green-400' : 'border-cyan-500/30 text-cyan-400'}
                            >
                                {Math.round(coveragePercentage)}%
                            </Badge>
                            {canProceedToAnalyze && secondsRemaining !== undefined && secondsRemaining > 0 && (
                                <div className="text-xs text-green-400 mt-1">
                                    Auto-advancing in {secondsRemaining}s
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
            
            {canProceedToAnalyze && secondsRemaining !== undefined && secondsRemaining > 0 && onCancelAdvance && (
                <div className="flex items-center gap-2 mt-3 pl-11">
                    <Badge variant="outline" className="border-green-500/30 text-green-400 text-xs">
                        Ready for analysis
                    </Badge>
                    <Button 
                        size="sm" 
                        variant="ghost" 
                        onClick={onCancelAdvance}
                        className="text-xs text-zinc-400 hover:text-zinc-300"
                        aria-label="Cancel auto-advance"
                    >
                        Cancel
                    </Button>
                </div>
            )}
        </motion.div>
    );
}


    const runs: RunInfo[] = statusData?.runs || [];
    const analysis = runData?.manifest?.analysis;
    const grid = runData?.manifest?.grid;
    const veGrid = runData?.ve_grid || [];

    return (
        <div className={cn(
            'min-h-screen bg-gradient-to-b from-zinc-950 via-zinc-900/95 to-zinc-950 relative',
            isSimulatorActive && 'ring-4 ring-orange-500/70 ring-inset'
        )}>
            {/* SIMULATOR MODE banner - only when simulator is active */}
            {isSimulatorActive && (
                <div className="sticky top-0 z-50 bg-orange-500/90 text-black font-bold text-center py-2 text-sm tracking-wider">
                    SIMULATOR MODE — Data is synthetic, not from real hardware
                </div>
            )}
            {/* Setup Wizard Modal */}
            <AnimatePresence>
                {showSetupWizard && (
                    <SetupWizard
                        onComplete={handleSetupComplete}
                        onDismiss={() => setShowSetupWizard(false)}
                        apiUrl={API_BASE}
                        isModal={true}
                    />
                )}
            </AnimatePresence>

            {/* Subtle grid pattern */}
            <div className="absolute inset-0 bg-[linear-gradient(to_right,transparent_49.5%,rgba(34,211,238,0.015)_49.5%,rgba(34,211,238,0.015)_50.5%,transparent_50.5%)] bg-[length:60px_60px] pointer-events-none" />
            <div className="absolute inset-0 bg-[linear-gradient(to_bottom,transparent_49.5%,rgba(34,211,238,0.015)_49.5%,rgba(34,211,238,0.015)_50.5%,transparent_50.5%)] bg-[length:60px_60px] pointer-events-none" />

            <div className="relative max-w-[1600px] mx-auto p-4 space-y-4">

                {/* Header Row */}
                <div className="flex items-center justify-between pb-4 border-b border-cyan-500/10">
                    <div className="flex items-center gap-4">
                        <div className="relative">
                            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-cyan-500/10 to-cyan-600/5 border border-cyan-500/20 flex items-center justify-center">
                                <Gauge className="w-5 h-5 text-cyan-400" />
                            </div>
                            <div className="absolute inset-0 w-11 h-11 rounded-xl bg-cyan-400/10 blur-lg -z-10" />
                        </div>
                        <div>
                            <h1 className="text-xl font-bold text-white tracking-tight font-mono uppercase">JetDrive Command Center</h1>
                            <p className="text-[10px] text-zinc-500 font-mono uppercase tracking-[0.2em] mt-0.5">Connect • Capture • Analyze • Tune</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <WorkflowIndicator state={workflowState} rpmThreshold={rpmThreshold} />
                        
                        {/* Tune Import - Compact */}
                        <div data-testid="tune-import">
                            <TuneImport 
                                onImport={handleTuneImport}
                                currentPreset="harley_m8"
                                compact={true}
                            />
                        </div>

                        {/* Quick Decel Pop Fix Sheet */}
                        <Sheet>
                            <SheetTrigger asChild>
                                <Button
                                    variant="outline"
                                    className="relative border-orange-500/30 bg-orange-500/10 hover:bg-orange-500/20 hover:border-orange-500/50 text-orange-300 gap-2"
                                >
                                    <Flame className="w-4 h-4" />
                                    <span className="hidden sm:inline">Decel Fix</span>
                                </Button>
                            </SheetTrigger>
                            <SheetContent side="right" className="w-[380px] sm:w-[420px] overflow-y-auto">
                                <SheetHeader className="mb-4">
                                    <SheetTitle className="flex items-center gap-2">
                                        <Flame className="w-5 h-5 text-orange-400" />
                                        Decel Pop Fix
                                    </SheetTitle>
                                    <SheetDescription>
                                        Eliminate exhaust popping with proven enrichment patterns
                                    </SheetDescription>
                                </SheetHeader>
                                <StageConfigPanel
                                    afrTargets={afrTargets}
                                    onAfrTargetsChange={setAfrTargets}
                                    runId={runId}
                                    compact={true}
                                />
                            </SheetContent>
                        </Sheet>

                        {/* Audio Capture Sheet - Prominent Button */}
                        <Sheet>
                            <SheetTrigger asChild>
                                <Button
                                    variant="outline"
                                    className="relative border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 hover:border-cyan-500/50 text-cyan-300 gap-2"
                                >
                                    <Mic className="w-4 h-4" />
                                    <span className="hidden sm:inline">Audio</span>
                                    {/* Pulse indicator when recording or knock detected */}
                                    {(audioRecording || audioKnockDetected) && (
                                        <span className="absolute -top-1 -right-1 flex h-3 w-3">
                                            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${audioKnockDetected ? 'bg-orange-400' : 'bg-red-400'} opacity-75`}></span>
                                            <span className={`relative inline-flex rounded-full h-3 w-3 ${audioKnockDetected ? 'bg-orange-500' : 'bg-red-500'}`}></span>
                                        </span>
                                    )}
                                </Button>
                            </SheetTrigger>
                            <SheetContent side="right" className="w-[420px] sm:w-[480px] overflow-y-auto">
                                <SheetHeader className="mb-4">
                                    <SheetTitle>Audio Capture</SheetTitle>
                                    <SheetDescription>
                                        Record engine audio and detect knock during dyno pulls
                                    </SheetDescription>
                                </SheetHeader>
                                <AudioCapturePanel
                                    isDynoCapturing={isLive}
                                    currentRpm={currentRpm}
                                    rpmThreshold={rpmThreshold}
                                    onRecordingStart={() => {
                                        setAudioRecording(true);
                                    }}
                                    onRecordingStop={() => {
                                        setAudioRecording(false);
                                    }}
                                    onKnockDetected={() => {
                                        setAudioKnockDetected(true);
                                        aiAssistant.onKnockDetected(); // 🎤 AI: "Knock detected!"
                                        setTimeout(() => setAudioKnockDetected(false), 3000);
                                    }}
                                />
                            </SheetContent>
                        </Sheet>

                        {/* Re-run Setup Button */}
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleRerunSetup}
                            className="text-zinc-400 hover:text-white gap-1.5"
                            title="Re-run setup wizard"
                        >
                            <Wrench className="w-4 h-4" />
                            <span className="hidden lg:inline text-xs">Setup</span>
                        </Button>

                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setShowSettings(true)}
                            className={showSettings ? 'bg-zinc-800' : ''}
                        >
                            <Settings2 className="w-4 h-4" />
                        </Button>
                    </div>
                </div>

                {/* Settings Sheet */}
                <SettingsSheet
                    open={showSettings}
                    onOpenChange={setShowSettings}
                    afrTargets={afrTargets}
                    onAfrTargetsChange={setAfrTargets}
                    rpmThreshold={rpmThreshold}
                    onRpmThresholdChange={setRpmThreshold}
                    runId={runId}
                    onRunIdChange={setRunId}
                    currentMap={currentMap}
                    currentRpm={currentRpm}
                    transientFuelEnabled={transientFuelEnabled}
                    onTransientFuelEnabledChange={setTransientFuelEnabled}
                    selectedRun={selectedRun}
                    isCapturing={isLive}
                    currentTps={channels['TPS']?.value || channels['Throttle Position']?.value || 0}
                    currentTargetAfr={currentTargetAfr}
                    virtualECUEnabled={virtualECUEnabled}
                    onVirtualECUEnabledChange={setVirtualECUEnabled}
                    veScenario={veScenario}
                    onVeScenarioChange={setVeScenario}
                    veErrorPct={veErrorPct}
                    onVeErrorPctChange={setVeErrorPct}
                    veErrorStd={veErrorStd}
                    onVeErrorStdChange={setVeErrorStd}
                    autoPullEnabled={autoPullEnabled}
                    onAutoPullEnabledChange={setAutoPullEnabled}
                    autoPullInterval={autoPullInterval}
                    onAutoPullIntervalChange={setAutoPullInterval}
                    isSimulatorActive={isSimulatorActive}
                    selectedProfile={selectedProfile}
                />

                {/* Main Tabs */}
                <Tabs value={activeMainTab} onValueChange={setActiveMainTab} className="w-full">
                    <div className="mb-3 flex items-center gap-2">
                        <span className="text-xs text-zinc-400">Live source:</span>
                        <Button
                            size="sm"
                            variant={activeLiveSource === 'jetdrive' ? 'default' : 'outline'}
                            onClick={() => setActiveLiveSource('jetdrive')}
                            className="h-7"
                        >
                            JetDrive
                        </Button>
                        <Button
                            size="sm"
                            variant={activeLiveSource === 'yourdyno' ? 'default' : 'outline'}
                            onClick={() => setActiveLiveSource('yourdyno')}
                            className="h-7"
                            disabled={isSimulatorActive}
                        >
                            YourDyno
                        </Button>
                        <Badge variant="outline" className="ml-1 text-[10px] uppercase tracking-wide">
                            {activeLiveSource}
                        </Badge>
                    </div>
                    <TabsList className="grid w-full grid-cols-3 max-w-2xl">
                        <TabsTrigger value="hardware" className="flex items-center gap-2">
                            <Radio className="h-4 w-4" />
                            Hardware
                        </TabsTrigger>
                        <TabsTrigger value="live" className="flex items-center gap-2">
                            <Activity className="h-4 w-4" />
                            Live
                        </TabsTrigger>
                        <TabsTrigger value="tuning" className="flex items-center gap-2">
                            <Zap className="h-4 w-4" />
                            Tuning
                        </TabsTrigger>
                    </TabsList>

                    {/* Hardware Tab */}
                    <TabsContent value="hardware" className="mt-6">
                        <HardwareTab apiUrl={liveApiBase} />
                    </TabsContent>

                    {/* Live Dashboard Tab */}
                    <TabsContent value="live" className="mt-6">
                        <JetDriveLiveDashboard apiUrl={liveApiBase} />
                    </TabsContent>

                    {/* Unified Tuning Tab: Wizard | Manual | Accelerated */}
                    <TabsContent value="tuning" className="mt-6">
                        <UnifiedTuningTab
                            importedTune={importedTune}
                            onTuningModeChange={(mode) => setWizardMode(mode === 'wizard')}
                            renderWizardContent={() => (
                                <div className="space-y-4">
                                    <SmartPromptBanner
                                        step={isLive ? 'collect' : 'setup'}
                                        coverageReport={coverageComputed}
                                        canProceedToAnalyze={canProceedToAnalyze}
                                        onActionClick={(action) => {
                                            if (action === 'wot') aiAssistant.onWotSuggestion();
                                            if (action === 'cruise') aiAssistant.onCruiseSuggestion();
                                        }}
                                        onCancelAdvance={handleCancelAutoAdvance}
                                        secondsRemaining={secondsRemaining}
                                    />
                                    <TuningWizard
                                    isSimulatorActive={isSimulatorActive}
                                    isCapturing={isCapturing}
                                    isLive={isLive}
                                    importedTune={importedTune}
                                    liveData={pendingExportData}
                                    liveStatus={{
                                        engineState,
                                        runState,
                                        afrValue: currentAfr,
                                        afrTarget: currentTargetAfr,
                                        rpm: currentRpm,
                                        engineTemp,
                                        coolantTemp,
                                        egtTemp,
                                        tps: currentTps,
                                        loadPct: currentLoadPct,
                                    }}
                                    pullThrottle={pullThrottle}
                                    onThrottleChange={handleWizardThrottleChange}
                                    lastPullSummary={lastPullSummary}
                                    onDismissPullSummary={() => setLastPullSummary(null)}
                                    onStartSimulator={handleStartSimulator}
                                    onStopSimulator={handleStopSimulator}
                                    onStartCapture={handleStartCapture}
                                    onStopCapture={stopCapture}
                                    onTriggerPull={handleTriggerPull}
                                    onAnalyze={async () => {
                                        aiAssistant.onStepChange('analyze');
                                        await analyzeMutation.mutateAsync({ mode: 'simulate' });
                                    }}
                                    onShowTuneImport={() => {
                                        // Scroll to tune import section
                                        document.querySelector('[data-testid="tune-import"]')?.scrollIntoView({ behavior: 'smooth' });
                                    }}
                                    onApply={(report) => {
                                        aiAssistant.onStepChange('complete');
                                        // Handle apply - download all formats
                                        if (pendingExportData && importedTune) {
                                            downloadAppliedVEAllFormats({
                                                sessionId: `session_${Date.now()}`,
                                                timestamp: new Date().toISOString(),
                                                enginePreset: pendingExportData.enginePreset,
                                                veBoundsPreset,
                                                sourceFile: importedTune.sourceName,
                                                rpmAxis: pendingExportData.rpmBins,
                                                mapAxis: pendingExportData.mapBins,
                                                baseVE: {
                                                    front: importedTune.veFront?.values ?? [],
                                                    rear: importedTune.veRear?.values ?? [],
                                                },
                                                corrections: {
                                                    front: pendingExportData.frontCorrections,
                                                    rear: pendingExportData.rearCorrections,
                                                },
                                                hitCounts: {
                                                    front: pendingExportData.frontHitCounts,
                                                    rear: pendingExportData.rearHitCounts,
                                                },
                                                appliedVE: report.appliedVE,
                                            });
                                        }
                                    }}
                                    onReset={() => {
                                        handleStopSimulator();
                                        setPendingExportData(null);
                                    }}
                                    veBoundsPreset={veBoundsPreset}
                                    onVeBoundsPresetChange={setVeBoundsPreset}
                                    renderLiveTable={() => (
                                        <LiveVETable
                                            currentRpm={currentRpm}
                                            currentMap={currentMap}
                                            currentAfrFront={currentAfrFront}
                                            currentAfrRear={currentAfrRear}
                                            afrTargets={afrTargets}
                                            isLive={isLive}
                                            customRpmBins={importedTune?.rpmBins}
                                            customMapBins={importedTune?.mapBins}
                                            onExport={(data) => {
                                                setPendingExportData(data);
                                            }}
                                            onLiveDataUpdate={(data) => {
                                                setPendingExportData(data);
                                            }}
                                        />
                                    )}
                                    renderApplyPreview={(report) => (
                                        <ApplyPreviewPanel
                                            baseVE={{
                                                front: importedTune?.veFront?.values ?? [],
                                                rear: importedTune?.veRear?.values ?? [],
                                            }}
                                            corrections={{
                                                front: pendingExportData?.frontCorrections ?? [],
                                                rear: pendingExportData?.rearCorrections ?? [],
                                            }}
                                            hitCounts={{
                                                front: pendingExportData?.frontHitCounts ?? [],
                                                rear: pendingExportData?.rearHitCounts ?? [],
                                            }}
                                            rpmAxis={pendingExportData?.rpmBins ?? []}
                                            mapAxis={pendingExportData?.mapBins ?? []}
                                            boundsPreset={veBoundsPreset}
                                            onBoundsPresetChange={setVeBoundsPreset}
                                        />
                                    )}
                                    />
                                </div>
                            )}
                            renderManualContent={() => (
                                workflowState === 'disconnected' ? (
                            /* DISCONNECTED STATE */
                            <div className="space-y-6">
                                {/* Primary: Hardware Connection */}
                                <Card className="bg-gradient-to-br from-zinc-900/80 to-zinc-950/80 border-cyan-500/15 relative overflow-hidden">
                                    {/* Subtle decorative glow */}
                                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-20 bg-cyan-500/5 blur-2xl pointer-events-none" />

                                    <CardContent className="py-14 text-center relative">
                                        <div className="relative w-20 h-20 mx-auto mb-6">
                                            <div className="absolute inset-0 rounded-2xl bg-cyan-400/10 blur-lg" />
                                            <div className="relative w-20 h-20 rounded-2xl bg-gradient-to-br from-cyan-500/15 to-cyan-600/5 border border-cyan-500/20 flex items-center justify-center">
                                                <Wifi className="w-10 h-10 text-cyan-400" />
                                            </div>
                                        </div>
                                        <h2 className="text-2xl font-bold text-white mb-3 font-mono uppercase tracking-wide">Connect to Your Dyno</h2>
                                        <p className="text-sm text-zinc-400 mb-8 max-w-md mx-auto leading-relaxed">
                                            Connect to your Dynojet dyno via JetDrive protocol for real-time data capture,
                                            VE table generation, and Power Vision export.
                                        </p>
                                        <Button
                                            onClick={handleStartMonitor}
                                            disabled={isStartingMonitor}
                                            size="lg"
                                            className="bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 px-10 py-6 text-lg font-mono uppercase tracking-wider shadow-md shadow-cyan-500/15 hover:shadow-lg hover:shadow-cyan-500/20 transition-all duration-300"
                                        >
                                            {isStartingMonitor ? (
                                                <RefreshCw className="w-5 h-5 mr-2 animate-spin" />
                                            ) : (
                                                <Power className="w-5 h-5 mr-2" />
                                            )}
                                            Connect to Dyno
                                        </Button>
                                        <p className="text-[10px] text-zinc-600 mt-5 font-mono uppercase tracking-wider">
                                            Requires JetDrive-compatible Dynojet dynamometer
                                        </p>
                                    </CardContent>
                                </Card>

                                {/* Secondary: Testing & Development Section */}
                                <div className="border-t border-zinc-800 pt-6">
                                    <div className="flex items-center gap-2 mb-4">
                                        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-800/50 border border-zinc-700">
                                            <Wrench className="w-3 h-3 text-zinc-500" />
                                            <span className="text-xs text-zinc-500 font-medium">Testing & Development</span>
                                        </div>
                                        <div className="flex-1 h-px bg-zinc-800" />
                                    </div>

                                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                        {/* Simulator Subsection */}
                                        <Card className="bg-zinc-900/50 border-zinc-800/50 hover:border-zinc-700/50 transition-colors">
                                            <CardContent className="py-6">
                                                <div className="flex items-start gap-4">
                                                    <div className="w-12 h-12 rounded-xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center flex-shrink-0">
                                                        <Cpu className="w-6 h-6 text-orange-400" />
                                                    </div>
                                                    <div className="flex-1">
                                                        <h3 className="text-sm font-semibold text-zinc-200 mb-1">Live Simulator</h3>
                                                        <p className="text-xs text-zinc-500 mb-3">
                                                            Test the tuning workflow with synthetic dyno data
                                                        </p>

                                                        {/* Compact Profile Selector */}
                                                        <div className="flex flex-wrap gap-1.5 mb-3">
                                                            {(profilesData?.profiles || [
                                                                { id: 'm8_114', name: 'M8-114', max_hp: 110, family: 'M8' },
                                                                { id: 'm8_131', name: 'M8-131', max_hp: 145, family: 'M8' },
                                                                { id: 'twin_cam_103', name: 'TC 103', max_hp: 85, family: 'TwinCam' },
                                                                { id: 'sportbike_600', name: 'CBR600', max_hp: 118, family: 'Sportbike' },
                                                            ] as SimulatorProfile[]).map((profile: SimulatorProfile) => (
                                                                <button
                                                                    key={profile.id}
                                                                    onClick={() => setSelectedProfile(profile.id)}
                                                                    className={`
                                                                px-2 py-1 rounded text-[10px] font-medium transition-all
                                                                ${selectedProfile === profile.id
                                                                            ? 'bg-orange-500/20 text-orange-400 border border-orange-500/40'
                                                                            : 'bg-zinc-800 text-zinc-400 border border-zinc-700 hover:border-zinc-600'
                                                                        }
                                                            `}
                                                                >
                                                                    {profile.name}
                                                                </button>
                                                            ))}
                                                        </div>

                                                        <Button
                                                            onClick={handleStartSimulator}
                                                            disabled={isStartingSimulator}
                                                            size="sm"
                                                            variant="outline"
                                                            className="border-orange-500/30 text-orange-400 hover:bg-orange-500/10"
                                                        >
                                                            {isStartingSimulator ? (
                                                                <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                                                            ) : (
                                                                <Play className="w-3.5 h-3.5 mr-1.5" />
                                                            )}
                                                            Start Simulator
                                                        </Button>

                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>

                                        {/* Quick Analysis Subsection */}
                                        <Card className="bg-zinc-900/50 border-zinc-800/50 hover:border-zinc-700/50 transition-colors">
                                            <CardContent className="py-6">
                                                <div className="flex items-start gap-4">
                                                    <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center flex-shrink-0">
                                                        <Zap className="w-6 h-6 text-purple-400" />
                                                    </div>
                                                    <div className="flex-1">
                                                        <h3 className="text-sm font-semibold text-zinc-200 mb-1">Quick Analysis</h3>
                                                        <p className="text-xs text-zinc-500 mb-3">
                                                            Run instant VE analysis with pre-generated sample data
                                                        </p>
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            onClick={() => analyzeMutation.mutate({ mode: 'simulate' })}
                                                            disabled={analyzeMutation.isPending}
                                                            className="border-purple-500/30 text-purple-400 hover:bg-purple-500/10"
                                                        >
                                                            {analyzeMutation.isPending ? (
                                                                <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                                                            ) : (
                                                                <Zap className="w-3.5 h-3.5 mr-1.5" />
                                                            )}
                                                            Quick Simulate
                                                        </Button>
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>

                                        {/* AutoTune Demo Subsection */}
                                        <Card className="bg-zinc-900/50 border-zinc-800/50 hover:border-cyan-700/50 transition-colors">
                                            <CardContent className="py-6">
                                                <div className="flex items-start gap-4">
                                                    <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center flex-shrink-0">
                                                        <Crosshair className="w-6 h-6 text-cyan-400" />
                                                    </div>
                                                    <div className="flex-1">
                                                        <h3 className="text-sm font-semibold text-zinc-200 mb-1">AutoTune Demo</h3>
                                                        <p className="text-xs text-zinc-500 mb-3">
                                                            Interactive VE auto-correction with live visualization
                                                        </p>
                                                        <Link to="/autotune-demo">
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                className="border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10"
                                                            >
                                                                <Crosshair className="w-3.5 h-3.5 mr-1.5" />
                                                                Launch Demo
                                                            </Button>
                                                        </Link>
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            /* CONNECTED STATES */
                            <div className="grid grid-cols-12 gap-4">

                                {/* Left Column - Live Data */}
                                <div className="col-span-12 lg:col-span-8 space-y-4">

                                    {/* Live Gauges Row */}
                                    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
                                        <NeedleGauge
                                            label="Engine"
                                            value={currentRpm}
                                            units="RPM"
                                            color="#22d3ee"
                                            min={0}
                                            max={8000}
                                            decimals={0}
                                            warning={6000}
                                            critical={7000}
                                            segments={8}
                                        />
                                        <AFRIndicator
                                            value={currentAfr}
                                            target={currentTargetAfr}
                                        />
                                        <LiveGauge
                                            label="Drum Force"
                                            value={currentForce}
                                            units="lbs"
                                            color="#f97316"
                                            min={0}
                                            max={500}
                                            decimals={0}
                                        />
                                        <LiveGauge
                                            label="Load"
                                            value={currentLoadPct}
                                            units="%"
                                            color="#06b6d4"
                                            min={0}
                                            max={100}
                                            decimals={0}
                                        />
                                        <NeedleGauge
                                            label={analysis ? "Peak" : "Live"}
                                            value={isLive ? currentHp : (analysis?.peak_hp || 0)}
                                            units="HP"
                                            color="#a78bfa"
                                            min={0}
                                            max={300}
                                            decimals={0}
                                            segments={6}
                                        />
                                    </div>

                                    {/* Audio engine removed */}

                                    {/* Capture Controls */}
                                    <div className="flex items-center gap-3">
                                        {isSimulatorActive ? (
                                            /* Simulator Controls */
                                            <>
                                                <div className="flex flex-col gap-2">
                                                    <div className="flex items-center gap-3">
                                                        <Button
                                                            onClick={handleTriggerPull}
                                                            disabled={simState !== 'idle'}
                                                            uiSound="pull"
                                                            className="bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-500 hover:to-red-500"
                                                        >
                                                            <Play className="w-4 h-4 mr-2" />
                                                            {simState === 'idle' ? `Trigger Pull (${pullThrottle}%)` :
                                                                simState === 'pull' ? 'Pulling...' :
                                                                    simState === 'decel' ? 'Decelerating' : 'Cooling Down'}
                                                        </Button>

                                                        <Button
                                                            onClick={handleStopSimulator}
                                                            variant="outline"
                                                            className="border-red-500/30 text-red-400 hover:bg-red-500/10"
                                                        >
                                                            <StopCircle className="w-4 h-4 mr-2" />
                                                            Stop Simulator
                                                        </Button>

                                                        <Button
                                                            onClick={() => analyzeMutation.mutate({ mode: 'simulate' })}
                                                            disabled={analyzeMutation.isPending || (isSimulatorActive && !pullDataStatus?.has_data)}
                                                            variant="outline"
                                                            className="border-zinc-700"
                                                            title={
                                                                isSimulatorActive && !pullDataStatus?.has_data
                                                                    ? "No pull data available. Run a pull first."
                                                                    : isSimulatorActive && pullDataStatus?.has_data
                                                                        ? `Analyze simulator pull data (${pullDataStatus.points} points, ${pullDataStatus.peak_hp?.toFixed(1)} HP)`
                                                                        : "Analyze with simulated data"
                                                            }
                                                        >
                                                            {analyzeMutation.isPending ? (
                                                                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                                                            ) : (
                                                                <Zap className="w-4 h-4 mr-2" />
                                                            )}
                                                            {isSimulatorActive && pullDataStatus?.has_data
                                                                ? `Analyze Pull (${pullDataStatus.points} pts)`
                                                                : "Analyze"}
                                                        </Button>

                                                        <div className="ml-auto flex items-center gap-2 text-xs">
                                                            <Badge variant="outline" className="border-orange-500/30 bg-orange-500/10 text-orange-400">
                                                                <Cpu className="w-3 h-3 mr-1" />
                                                                Simulator
                                                            </Badge>
                                                            <span className="text-zinc-500">
                                                                {simState === 'pull' && '🔥 WOT Pull'}
                                                                {simState === 'idle' && '⏳ Waiting...'}
                                                                {simState === 'decel' && '📉 Decel'}
                                                                {simState === 'cooldown' && '❄️ Cooldown'}
                                                            </span>
                                                        </div>
                                                    </div>

                                                    {/* Pull Throttle Setting */}
                                                    <div className="flex items-center gap-3 px-3 py-2 rounded-md bg-zinc-950/40 border border-zinc-800">
                                                        <Label className="text-xs text-zinc-400 font-medium whitespace-nowrap">
                                                            Pull Throttle:
                                                        </Label>
                                                        <Slider
                                                            value={[pullThrottle]}
                                                            onValueChange={(v) => {
                                                                const newVal = v?.[0] ?? 100;
                                                                console.log(`[JetDrive] Pull Throttle changed to ${newVal}%`);
                                                                setPullThrottle(newVal);
                                                            }}
                                                            min={0}
                                                            max={100}
                                                            step={5}
                                                            className="flex-1"
                                                        />
                                                        <span className="text-xs font-mono text-zinc-200 tabular-nums w-12 text-right">
                                                            {pullThrottle}%
                                                        </span>
                                                        <span className="text-[10px] text-zinc-500">
                                                            {pullThrottle === 100 ? 'WOT' : pullThrottle >= 75 ? 'High' : pullThrottle >= 50 ? 'Mid' : pullThrottle >= 25 ? 'Low' : 'Idle'}
                                                        </span>
                                                    </div>
                                                </div>
                                            </>
                                        ) : (
                                            /* Hardware Controls */
                                            <>
                                                <Button
                                                    onClick={isCapturing ? stopCapture : handleStartCapture}
                                                    variant={isCapturing ? "destructive" : "default"}
                                                    className={!isCapturing ? "bg-green-600 hover:bg-green-500" : ""}
                                                >
                                                    {isCapturing ? (
                                                        <>
                                                            <Square className="w-4 h-4 mr-2" />
                                                            Stop Capture
                                                        </>
                                                    ) : (
                                                        <>
                                                            <Radio className="w-4 h-4 mr-2" />
                                                            Start Capture
                                                        </>
                                                    )}
                                                </Button>

                                                <Button
                                                    onClick={() => analyzeMutation.mutate({ mode: 'simulate' })}
                                                    disabled={analyzeMutation.isPending}
                                                    variant="outline"
                                                    className="border-orange-500/30 text-orange-400 hover:bg-orange-500/10"
                                                >
                                                    {analyzeMutation.isPending ? (
                                                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                                                    ) : (
                                                        <Zap className="w-4 h-4 mr-2" />
                                                    )}
                                                    Simulate Run
                                                </Button>

                                                {analyzeMutation.isPending && (
                                                    <div className="flex-1 flex items-center gap-3">
                                                        <Progress value={66} className="h-2 flex-1 max-w-xs" />
                                                        <span className="text-xs text-zinc-500">Analyzing...</span>
                                                    </div>
                                                )}

                                                <div className="ml-auto flex items-center gap-2 text-xs text-zinc-500">
                                                    <Wifi className="w-3 h-3 text-green-500" />
                                                    <span>{providerName || 'JetDrive'}</span>
                                                    <span className="text-zinc-600">•</span>
                                                    <span>{channelCount} ch</span>
                                                </div>
                                            </>
                                        )}
                                    </div>

                                    {/* Manual throttle control (visible in CONNECTED view while simulator is running) */}
                                    {isSimulatorActive && (
                                        <div className="mt-3 p-3 rounded-md bg-zinc-950/40 border border-zinc-800">
                                            <div className="flex items-center justify-between mb-2">
                                                <div className="text-xs text-zinc-400 font-medium">Throttle (TPS)</div>
                                                <div className="text-xs font-mono text-zinc-200 tabular-nums">
                                                    {simState === 'pull' && typeof simStatus?.current?.tps === 'number'
                                                        ? `${Math.round(simStatus.current.tps)}%`
                                                        : `${Math.round(simThrottle)}%`}
                                                </div>
                                            </div>
                                            <Slider
                                                value={[simThrottle]}
                                                onValueChange={(v) => onSimThrottleChange(v?.[0] ?? 0)}
                                                min={0}
                                                max={100}
                                                step={1}
                                                disabled={simState === 'pull'}
                                            />
                                            <div className="mt-2 text-[10px] text-zinc-500">
                                                Drag to set throttle; you can still use <span className="font-mono">Trigger Pull</span> for a sweep.
                                            </div>
                                        </div>
                                    )}

                                    {/* Simulator load control (eddy brake / road load) */}
                                    {isSimulatorActive && (
                                        <SimulatorLoadPanel apiUrl={API_BASE} />
                                    )}

                                    {/* Live VE Table with Cell Tracing */}
                                    {(isConnected || isSimulatorActive) && (
                                        <Card className="bg-zinc-900/50 border-zinc-800">
                                            <CardContent className="pt-4">
                                                <LiveVETable
                                                    currentRpm={currentRpm}
                                                    currentMap={currentMap}
                                                    currentAfrFront={currentAfrFront}
                                                    currentAfrRear={currentAfrRear}
                                                    afrTargets={afrTargets}
                                                    isLive={isLive}
                                                    customRpmBins={importedTune?.rpmBins}
                                                    customMapBins={importedTune?.mapBins}
                                                    onExport={(data) => {
                                                        setPendingExportData(data);
                                                        setExportModalOpen(true);
                                                    }}
                                                />
                                            </CardContent>
                                        </Card>
                                    )}

                                    {/* Results Section */}
                                    {selectedRun && runData && (
                                        <Card className="bg-zinc-900/50 border-zinc-800">
                                            <CardHeader className="pb-3">
                                                <div className="flex items-center justify-between">
                                                    <div>
                                                        <CardTitle className="text-base flex items-center gap-2">
                                                            <CheckCircle2 className="w-4 h-4 text-green-500" />
                                                            {selectedRun}
                                                        </CardTitle>
                                                        <CardDescription className="text-xs">
                                                            {analysis?.total_samples} samples • {(analysis?.duration_ms / 1000)?.toFixed(1)}s
                                                        </CardDescription>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        {confidenceReport && (
                                                            <ConfidenceBadge confidence={confidenceReport} compact />
                                                        )}
                                                        {selectedRunMode && (
                                                            <Badge 
                                                                variant="outline" 
                                                                className={cn(
                                                                    "text-xs",
                                                                    selectedRunMode === 'simulator_pull' 
                                                                        ? "bg-blue-500/10 text-blue-400 border-blue-500/30" 
                                                                        : "bg-purple-500/10 text-purple-400 border-purple-500/30"
                                                                )}
                                                            >
                                                                {selectedRunMode === 'simulator_pull' ? '📊 Real Pull Data' : '🔮 Synthetic Data'}
                                                            </Badge>
                                                        )}
                                                        <AFRStatusBadge status={analysis?.overall_status || 'Unknown'} />
                                                        <Button
                                                            onClick={downloadPvv}
                                                            size="sm"
                                                            className="bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-500 hover:to-red-500"
                                                        >
                                                            <Download className="w-3 h-3 mr-1" />
                                                            .PVV
                                                        </Button>
                                                        {selectedRun && (
                                                            <ReportGenerator 
                                                                runId={selectedRun}
                                                                trigger={
                                                                    <Button
                                                                        size="sm"
                                                                        variant="outline"
                                                                        className="border-amber-600 text-amber-400 hover:bg-amber-600/20"
                                                                    >
                                                                        <FileText className="w-3 h-3 mr-1" />
                                                                        PDF Report
                                                                    </Button>
                                                                }
                                                            />
                                                        )}
                                                    </div>
                                                </div>
                                            </CardHeader>
                                            <CardContent className="space-y-4">
                                                {/* Quick Stats */}
                                                <div className="grid grid-cols-5 gap-3">
                                                    <div className="p-3 rounded-md bg-orange-500/10 border border-orange-500/20 text-center">
                                                        <div className="text-2xl font-bold text-orange-400">{analysis?.peak_hp?.toFixed(1)}</div>
                                                        <div className="text-[10px] text-zinc-500">HP @ {analysis?.peak_hp_rpm}</div>
                                                    </div>
                                                    <div className="p-3 rounded-md bg-blue-500/10 border border-blue-500/20 text-center">
                                                        <div className="text-2xl font-bold text-blue-400">{analysis?.peak_tq?.toFixed(1)}</div>
                                                        <div className="text-[10px] text-zinc-500">TQ @ {analysis?.peak_tq_rpm}</div>
                                                    </div>
                                                    <div className="p-3 rounded-md bg-green-500/10 border border-green-500/20 text-center">
                                                        <div className="text-2xl font-bold text-green-400">{analysis?.ok_cells}</div>
                                                        <div className="text-[10px] text-zinc-500">OK Cells</div>
                                                    </div>
                                                    <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-center">
                                                        <div className="text-2xl font-bold text-red-400">
                                                            {(analysis?.lean_cells || 0) + (analysis?.rich_cells || 0)}
                                                        </div>
                                                        <div className="text-[10px] text-zinc-500">Needs Fix</div>
                                                    </div>
                                                    {confidenceReport && (
                                                        <div className={`p-3 rounded-md border text-center ${confidenceReport.letter_grade === 'A' ? 'bg-green-500/10 border-green-500/20' :
                                                            confidenceReport.letter_grade === 'B' ? 'bg-blue-500/10 border-blue-500/20' :
                                                                confidenceReport.letter_grade === 'C' ? 'bg-yellow-500/10 border-yellow-500/20' :
                                                                    'bg-red-500/10 border-red-500/20'
                                                            }`}>
                                                            <div className={`text-2xl font-bold ${confidenceReport.letter_grade === 'A' ? 'text-green-400' :
                                                                confidenceReport.letter_grade === 'B' ? 'text-blue-400' :
                                                                    confidenceReport.letter_grade === 'C' ? 'text-yellow-400' :
                                                                        'text-red-400'
                                                                }`}>
                                                                {confidenceReport.letter_grade}
                                                            </div>
                                                            <div className="text-[10px] text-zinc-500">Confidence</div>
                                                        </div>
                                                    )}
                                                </div>

                                                {/* VE Heatmap */}
                                                <div>
                                                    <div className="flex items-center justify-between mb-2">
                                                        <h4 className="text-xs font-medium text-zinc-400 flex items-center gap-1">
                                                            <Grid3X3 className="w-3 h-3" />
                                                            VE Correction Grid
                                                        </h4>
                                                        <div className="flex items-center gap-3 text-[10px] text-zinc-400">
                                                            <span className="flex items-center gap-1.5">
                                                                <div className="w-3 h-3 bg-red-500/60 rounded border border-red-500/80" />
                                                                <span className="font-medium">Lean</span>
                                                            </span>
                                                            <span className="flex items-center gap-1.5">
                                                                <div className="w-3 h-3 bg-green-500/40 rounded border border-green-500/60" />
                                                                <span className="font-medium">OK</span>
                                                            </span>
                                                            <span className="flex items-center gap-1.5">
                                                                <div className="w-3 h-3 bg-blue-500/60 rounded border border-blue-500/80" />
                                                                <span className="font-medium">Rich</span>
                                                            </span>
                                                        </div>
                                                    </div>
                                                    <div className="rounded-lg border border-zinc-800 overflow-hidden">
                                                        <VEHeatmapCompact veGrid={veGrid} grid={grid} />
                                                    </div>
                                                </div>

                                                {/* Confidence Score Details */}
                                                {confidenceReport && (
                                                    <div className="pt-4 border-t border-zinc-800">
                                                        <h4 className="text-xs font-medium text-zinc-400 mb-3 flex items-center gap-1">
                                                            <Award className="w-3 h-3" />
                                                            Tune Quality Assessment
                                                        </h4>
                                                        <div className="grid grid-cols-3 gap-3">
                                                            {/* Regions */}
                                                            {confidenceReport.region_breakdown && Object.entries(confidenceReport.region_breakdown).map(([region, data]) => {
                                                                const regionData = data as ConfidenceReport['region_breakdown'][string];
                                                                return (
                                                                    <div key={region} className="p-2 rounded-lg bg-zinc-800/50 border border-zinc-700/50">
                                                                        <div className="text-[10px] text-zinc-500 uppercase font-medium mb-1">
                                                                            {region}
                                                                        </div>
                                                                        <div className="text-xs text-zinc-300">
                                                                            <span className="font-mono">{regionData.coverage_percentage.toFixed(0)}%</span>
                                                                            <span className="text-zinc-600 mx-1">•</span>
                                                                            <span className="text-zinc-500">MAD {regionData.average_mad.toFixed(2)}</span>
                                                                        </div>
                                                                    </div>
                                                                );
                                                            })}
                                                        </div>

                                                        {/* Recommendations */}
                                                        {confidenceReport.recommendations && Array.isArray(confidenceReport.recommendations) && confidenceReport.recommendations.length > 0 && (
                                                            <div className="mt-3 space-y-1.5">
                                                                {confidenceReport.recommendations.slice(0, 2).map((rec, idx) => (
                                                                    <div key={idx} className="text-[11px] text-zinc-400 flex items-start gap-2 p-2 rounded bg-zinc-800/30">
                                                                        <Info className="w-3 h-3 text-cyan-500 mt-0.5 flex-shrink-0" />
                                                                        <span className="leading-relaxed">{rec}</span>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </CardContent>
                                        </Card>
                                    )}

                                    {/* NextGen Analysis - Physics-informed ECU reasoning */}
                                    {selectedRun && (
                                        <NextGenAnalysisPanel runId={selectedRun} />
                                    )}

                                    {/* Power Opportunities Panel */}
                                    {selectedRun && (powerOpportunities || powerOpportunitiesLoading) && (
                                        <PowerOpportunitiesPanel
                                            data={powerOpportunities || null}
                                            loading={powerOpportunitiesLoading}
                                            onDownload={() => {
                                                if (selectedRun) {
                                                    window.open(`${API_BASE}/download/${selectedRun}/PowerOpportunities.json`, '_blank');
                                                }
                                            }}
                                        />
                                    )}

                                    {/* Session Replay */}
                                    {selectedRun && (
                                        <Card className="bg-zinc-900/50 border-zinc-800">
                                            <CardHeader className="pb-3">
                                                <CardTitle className="text-base flex items-center gap-2">
                                                    <Activity className="w-4 h-4 text-cyan-500" />
                                                    Session Replay
                                                </CardTitle>
                                                <CardDescription className="text-xs">
                                                    Timeline of all decisions made during tuning
                                                </CardDescription>
                                            </CardHeader>
                                            <CardContent>
                                                <SessionReplayViewer runId={selectedRun} />
                                            </CardContent>
                                        </Card>
                                    )}

                                    {/* Run Comparison Table - Show when we have multiple runs */}
                                    {runs.length > 1 && allRunsData && allRunsData.length > 1 && (
                                        <>
                                            {/* Chart + View Toggles */}
                                            <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-zinc-500">Curve:</span>
                                                    <Button
                                                        variant={comparisonMetric === 'hp' ? 'outline' : 'ghost'}
                                                        size="sm"
                                                        onClick={() => setComparisonMetric('hp')}
                                                        className="h-7 text-xs"
                                                    >
                                                        HP
                                                    </Button>
                                                    <Button
                                                        variant={comparisonMetric === 'tq' ? 'outline' : 'ghost'}
                                                        size="sm"
                                                        onClick={() => setComparisonMetric('tq')}
                                                        className="h-7 text-xs"
                                                    >
                                                        TQ
                                                    </Button>
                                                    <Button
                                                        variant={comparisonMetric === 'both' ? 'outline' : 'ghost'}
                                                        size="sm"
                                                        onClick={() => setComparisonMetric('both')}
                                                        className="h-7 text-xs border-cyan-500/30 text-cyan-400"
                                                    >
                                                        Both
                                                    </Button>
                                                </div>

                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-zinc-500">Comparison View:</span>
                                                    <Button
                                                        variant={useEnhancedTable ? "ghost" : "outline"}
                                                        size="sm"
                                                        onClick={() => setUseEnhancedTable(false)}
                                                        className="h-7 text-xs"
                                                    >
                                                        Standard
                                                    </Button>
                                                    <Button
                                                        variant={useEnhancedTable ? "outline" : "ghost"}
                                                        size="sm"
                                                        onClick={() => setUseEnhancedTable(true)}
                                                        className="h-7 text-xs border-cyan-500/30 text-cyan-400"
                                                    >
                                                        Enhanced
                                                    </Button>
                                                </div>

                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-zinc-500">Data:</span>
                                                    <Button
                                                        variant={comparisonSource === 'actual' ? 'outline' : 'ghost'}
                                                        size="sm"
                                                        onClick={() => setComparisonSource('actual')}
                                                        className="h-7 text-xs"
                                                    >
                                                        Actual
                                                    </Button>
                                                    <Button
                                                        variant={comparisonSource === 'simulator' ? 'outline' : 'ghost'}
                                                        size="sm"
                                                        onClick={() => setComparisonSource('simulator')}
                                                        className="h-7 text-xs"
                                                    >
                                                        Simulator
                                                    </Button>
                                                    <Button
                                                        variant={comparisonSource === 'real' ? 'outline' : 'ghost'}
                                                        size="sm"
                                                        onClick={() => setComparisonSource('real')}
                                                        className="h-7 text-xs"
                                                    >
                                                        Real
                                                    </Button>
                                                    <Button
                                                        variant={comparisonSource === 'simulated' ? 'outline' : 'ghost'}
                                                        size="sm"
                                                        onClick={() => setComparisonSource('simulated')}
                                                        className="h-7 text-xs"
                                                    >
                                                        Synthetic
                                                    </Button>
                                                </div>
                                            </div>

                                            <RunComparisonChart
                                                runs={comparisonRunsForChart}
                                                metric={comparisonMetric}
                                                height={280}
                                            />

                                            {useEnhancedTable ? (
                                                <RunComparisonTableEnhanced
                                                    runs={allRunsData}
                                                    onRunClick={setSelectedRun}
                                                    maxRuns={10}
                                                    selectedRunIds={comparisonSelectedRunIds}
                                                    onSelectedRunIdsChange={setComparisonSelectedRunIds}
                                                    baselineRunId={comparisonBaselineRunId}
                                                    onBaselineRunIdChange={setComparisonBaselineRunId}
                                                />
                                            ) : (
                                                <RunComparisonTable
                                                    runs={allRunsData}
                                                    selectedRuns={selectedRun ? [selectedRun] : []}
                                                    onRunClick={setSelectedRun}
                                                    maxRuns={5}
                                                />
                                            )}
                                        </>
                                    )}
                                </div>

                                {/* Right Column - Runs & Tips */}
                                <div className="col-span-12 lg:col-span-4 space-y-4">

                                    {/* Recent Runs */}
                                    <Card className="bg-zinc-900/50 border-zinc-800">
                                        <CardHeader className="py-3">
                                            <CardTitle className="text-sm flex items-center gap-2">
                                                <Timer className="w-4 h-4" />
                                                Recent Runs
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="pt-0">
                                            {runs.length === 0 ? (
                                                <div className="text-center py-6 text-zinc-500">
                                                    <Gauge className="w-8 h-8 mx-auto mb-2 opacity-30" />
                                                    <p className="text-xs">No runs yet</p>
                                                </div>
                                            ) : (
                                                <div className="space-y-1.5 max-h-[300px] overflow-y-auto pr-1">
                                                    {runs.slice(0, 10).map((run) => (
                                                        <button
                                                            key={run.run_id}
                                                            onClick={() => setSelectedRun(run.run_id)}
                                                            className={`
                                                        w-full text-left p-2.5 rounded-lg border transition-all text-xs
                                                        ${selectedRun === run.run_id
                                                                    ? 'border-orange-500 bg-orange-500/10'
                                                                    : 'border-zinc-800 hover:border-zinc-700 hover:bg-zinc-800/50'
                                                                }
                                                    `}
                                                        >
                                                            <div className="flex items-center justify-between mb-0.5">
                                                                <span className="font-medium text-zinc-200 truncate max-w-[120px]">
                                                                    {run.run_id}
                                                                </span>
                                                                {(['BALANCED', 'OK'].includes(run.status)) ? (
                                                                    <span
                                                                        className="inline-flex items-center"
                                                                        aria-label={`AFR status ${run.status}`}
                                                                        title={run.status}
                                                                    >
                                                                        <span className="w-2 h-2 rounded-full bg-green-500/60 border border-green-500/30" />
                                                                    </span>
                                                                ) : (
                                                                    <AFRStatusBadge status={run.status} />
                                                                )}
                                                            </div>
                                                            <div className="flex items-center gap-2 text-zinc-500">
                                                                <TrendingUp className="w-3 h-3" />
                                                                <span>{run.peak_hp.toFixed(0)} HP</span>
                                                                <span className="text-zinc-600">•</span>
                                                                <span>{run.peak_tq.toFixed(0)} ft-lb</span>
                                                            </div>
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>

                                    {/* Tuner Tips */}
                                    <Card className="bg-zinc-900/30 border-zinc-800/50">
                                        <CardHeader className="py-3">
                                            <CardTitle className="text-xs flex items-center gap-2 text-zinc-400">
                                                <Wrench className="w-3 h-3" />
                                                Quick Reference
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="pt-0">
                                            <ul className="space-y-2 text-[11px] text-zinc-500">
                                                <li className="flex items-start gap-2">
                                                    <ChevronRight className="w-3 h-3 mt-0.5 text-orange-500 flex-shrink-0" />
                                                    <span><strong className="text-zinc-400">NA engines:</strong> 12.5-13.0 AFR for peak power</span>
                                                </li>
                                                <li className="flex items-start gap-2">
                                                    <ChevronRight className="w-3 h-3 mt-0.5 text-orange-500 flex-shrink-0" />
                                                    <span><strong className="text-zinc-400">Turbo:</strong> 11.5-12.0 AFR with proper fuel</span>
                                                </li>
                                                <li className="flex items-start gap-2">
                                                    <ChevronRight className="w-3 h-3 mt-0.5 text-orange-500 flex-shrink-0" />
                                                    <span><strong className="text-zinc-400">VE formula:</strong> 7% correction per AFR point</span>
                                                </li>
                                                <li className="flex items-start gap-2">
                                                    <ChevronRight className="w-3 h-3 mt-0.5 text-orange-500 flex-shrink-0" />
                                                    <span><strong className="text-zinc-400">Export:</strong> .PVV → Power Vision → Flash</span>
                                                </li>
                                            </ul>
                                        </CardContent>
                                    </Card>
                                </div>
                            </div>
                            )
                            )}
                        />
                    </TabsContent>
                </Tabs>
            </div>
            
            {/* VE Export Modal */}
            <Dialog open={exportModalOpen} onOpenChange={setExportModalOpen}>
                <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
                    <DialogHeader>
                        <DialogTitle className="text-white">Export VE Corrections</DialogTitle>
                        <DialogDescription className="text-zinc-400">
                            Choose export format. Dual-cylinder corrections (Front/Rear) will be included.
                        </DialogDescription>
                    </DialogHeader>
                    
                    {pendingExportData && (
                        <div className="space-y-4">
                            {/* Summary */}
                            <div className="bg-zinc-800/50 rounded-lg p-3 text-xs">
                                <div className="grid grid-cols-2 gap-2 text-zinc-400">
                                    <div>Engine: <span className="text-white">{pendingExportData.enginePreset}</span></div>
                                    <div>Total Hits: <span className="text-green-400">{pendingExportData.totalHits}</span></div>
                                    <div>Grid: <span className="text-white">{pendingExportData.rpmBins.length}x{pendingExportData.mapBins.length}</span></div>
                                    <div>Cylinders: <span className="text-orange-400">Front + Rear</span></div>
                                </div>
                            </div>
                            
                            {/* Export Buttons */}
                            <div className="grid grid-cols-1 gap-2">
                                <Button
                                    onClick={() => {
                                        const csv = exportToCSV(pendingExportData, 'front');
                                        downloadFile(csv, `VE_Corrections_Front_${new Date().toISOString().slice(0,10)}.csv`, 'text/csv');
                                        toast.success('Front cylinder CSV exported');
                                    }}
                                    variant="outline"
                                    className="justify-start border-zinc-700 hover:bg-zinc-800"
                                >
                                    <Download className="w-4 h-4 mr-2" />
                                    CSV (Front Cylinder)
                                </Button>
                                
                                <Button
                                    onClick={() => {
                                        const csv = exportToCSV(pendingExportData, 'rear');
                                        downloadFile(csv, `VE_Corrections_Rear_${new Date().toISOString().slice(0,10)}.csv`, 'text/csv');
                                        toast.success('Rear cylinder CSV exported');
                                    }}
                                    variant="outline"
                                    className="justify-start border-zinc-700 hover:bg-zinc-800"
                                >
                                    <Download className="w-4 h-4 mr-2" />
                                    CSV (Rear Cylinder)
                                </Button>
                                
                                <Button
                                    onClick={() => {
                                        const pvv = exportToPVV(pendingExportData);
                                        downloadFile(pvv, `VE_Corrections_${new Date().toISOString().slice(0,10)}.pvv`, 'application/xml');
                                        toast.success('Power Vision PVV exported');
                                    }}
                                    className="justify-start bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-500 hover:to-red-500"
                                >
                                    <Download className="w-4 h-4 mr-2" />
                                    Power Vision (.pvv) - Both Cylinders
                                </Button>
                                
                                <Button
                                    onClick={() => {
                                        const json = exportToJSON(pendingExportData);
                                        downloadFile(json, `VE_Corrections_${new Date().toISOString().slice(0,10)}.json`, 'application/json');
                                        toast.success('JSON exported');
                                    }}
                                    variant="outline"
                                    className="justify-start border-zinc-700 hover:bg-zinc-800"
                                >
                                    <Download className="w-4 h-4 mr-2" />
                                    JSON (Full Data)
                                </Button>
                            </div>
                            
                            <p className="text-xs text-zinc-500 text-center">
                                PVV export uses partial bin matching for safety
                            </p>
                            
                            {/* Apply Button - Opens ApplyPreviewPanel */}
                            {importedTune && (
                                <div className="pt-3 border-t border-zinc-800 mt-3">
                                    <Button
                                        onClick={() => {
                                            setExportModalOpen(false);
                                            setApplyPreviewOpen(true);
                                        }}
                                        className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500"
                                    >
                                        <Zap className="w-4 h-4 mr-2" />
                                        Apply to Base Tune
                                    </Button>
                                    <p className="text-xs text-zinc-500 text-center mt-2">
                                        Preview and apply corrections to your imported tune
                                    </p>
                                </div>
                            )}
                        </div>
                    )}
                </DialogContent>
            </Dialog>
            
            {/* Apply Preview Dialog (Phase 3) */}
            <Dialog open={applyPreviewOpen} onOpenChange={setApplyPreviewOpen}>
                <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle className="text-white">Apply VE Corrections</DialogTitle>
                        <DialogDescription className="text-zinc-400">
                            Review corrections before applying to your base tune.
                        </DialogDescription>
                    </DialogHeader>
                    
                    {pendingExportData && importedTune && (
                        <ApplyPreviewPanel
                            baseVE={{
                                front: importedTune.veFront?.values ?? [],
                                rear: importedTune.veRear?.values ?? [],
                            }}
                            corrections={{
                                front: pendingExportData.frontCorrections,
                                rear: pendingExportData.rearCorrections,
                            }}
                            hitCounts={{
                                front: pendingExportData.frontHitCounts,
                                rear: pendingExportData.rearHitCounts,
                            }}
                            rpmAxis={pendingExportData.rpmBins}
                            mapAxis={pendingExportData.mapBins}
                            boundsPreset={veBoundsPreset}
                            onBoundsPresetChange={setVeBoundsPreset}
                            onApply={handleApplyCorrections}
                            onCancel={() => setApplyPreviewOpen(false)}
                        />
                    )}
                    
                    {(!pendingExportData || !importedTune) && (
                        <div className="text-center py-8 text-zinc-500">
                            <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-yellow-500" />
                            <p>Missing data for apply preview.</p>
                            <p className="text-xs mt-1">
                                {!importedTune && 'Import a base tune first. '}
                                {!pendingExportData && 'Collect some VE data first.'}
                            </p>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    );
}
