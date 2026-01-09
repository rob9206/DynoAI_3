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
import { Link } from 'react-router-dom';
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
import { useJetDriveLive } from '../hooks/useJetDriveLive';
import { usePowerOpportunities } from '../hooks/usePowerOpportunities';
import { LiveVETable } from '../components/jetdrive/LiveVETable';
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
// import { useAIAssistant } from '../hooks/useAIAssistant';
import { ConfidenceBadge } from '../components/jetdrive/ConfidenceBadge';
import { VEHeatmap as VEGrid } from '../components/results/VEHeatmap';
import { VEHeatmapLegend } from '../components/results/VEHeatmapLegend';
import { getConfidenceReport } from '../lib/api';
import type { ConfidenceReport } from '../components/ConfidenceScoreCard';
import { ReportGenerator } from '../components/reports/ReportGenerator';

const API_BASE = 'http://127.0.0.1:5001/api/jetdrive';

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

export default function JetDriveAutoTunePage() {
    // Configuration state
    const [afrTargets, setAfrTargets] = useState<Record<number, number>>(() => ({ ...DEFAULT_AFR_TARGETS }));
    const [rpmThreshold, setRpmThreshold] = useState(2000);
    const [showSettings, setShowSettings] = useState(false);
    const [activeMainTab, setActiveMainTab] = useState('autotune');

    // Run state
    const [runId, setRunId] = useState(`dyno_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}_${Date.now().toString(36)}`);
    const [selectedRun, setSelectedRun] = useState<string | null>(null);
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

    // Audio capture state (real recording)
    const [audioRecording, setAudioRecording] = useState(false);
    const [audioKnockDetected, setAudioKnockDetected] = useState(false);

    // Transient Fuel Analysis state
    const [transientFuelEnabled, setTransientFuelEnabled] = useState(false);

    // Virtual ECU state
    const [virtualECUEnabled, setVirtualECUEnabled] = useState(false);
    const [veScenario, setVeScenario] = useState<VEScenario>('lean');
    const [veErrorPct, setVeErrorPct] = useState(-10.0);
    const [veErrorStd, setVeErrorStd] = useState(5.0);

    // AI Assistant - DISABLED (kept as stub to prevent errors)
    const aiAssistant = {
        state: { voiceName: null },
        onPullStart: () => { },
        onPullEnd: () => { },
        onHighRpm: () => { },
        onGoodPull: () => { },
        onAfrLean: () => { },
        onAfrRich: () => { },
        onKnockDetected: () => { },
        testVoice: () => { },
    };

    // Audio engine removed

    // Workflow state
    const [workflowState, setWorkflowState] = useState<WorkflowState>('disconnected');

    // Simulator state
    const [isSimulatorActive, setIsSimulatorActive] = useState(false);
    const [simState, setSimState] = useState<SimulatorStatus['state']>('stopped');
    const [selectedProfile, setSelectedProfile] = useState<string>('m8_114');
    const [isStartingSimulator, setIsStartingSimulator] = useState(false);

    // JetDrive live hook
    const {
        isConnected,
        isCapturing,
        providerName,
        channelCount,
        channels,
        startCapture,
        stopCapture,
    } = useJetDriveLive({
        apiUrl: API_BASE,
        pollInterval: 250,  // 250ms (4Hz) - responsive and rate-limit friendly
    });

    // Extract channel values - memoized to avoid recalculation
    const currentRpm = useMemo(() => {
        const ch = channels['Digital RPM 1'] || channels['RPM'] || channels['chan_42'];
        return ch?.value || 0;
    }, [channels]);

    const currentAfr = useMemo(() => {
        const ch = channels['Air/Fuel Ratio 1'] || channels['AFR 1'] || channels['AFR'] || channels['chan_23'];
        return ch?.value || 0;
    }, [channels]);

    const currentForce = useMemo(() => {
        const ch =
            channels['Force Drum 1'] ||
            channels['Force'] ||
            channels['Load'] ||
            channels['chan_39'];
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
        // Debug: Log available channels and HP value
        if (Object.keys(channels).length > 0) {
            console.log('[HP Debug] Available channels:', Object.keys(channels));
            console.log('[HP Debug] HP channel:', ch);
            console.log('[HP Debug] HP value:', ch?.value);
        }
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
                // Also start live capture
                await startCapture();
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

    // Stop simulator
    const handleStopSimulator = async () => {
        try {
            await fetch(`${API_BASE}/simulator/stop`, { method: 'POST' });
            await stopCapture();
            setIsSimulatorActive(false);
            setSimState('stopped');
            toast.info('Simulator stopped');
        } catch {
            toast.error('Failed to stop simulator');
        }
    };

    // Trigger a simulated pull
    const handleTriggerPull = async () => {
        try {
            // Ensure WOT for pulls unless user intentionally holds lower TPS
            // (Operator can always drag the slider back down mid-pull.)
            await sendSimThrottle(Math.max(0, Math.min(100, simThrottle)));
            const res = await fetch(`${API_BASE}/simulator/pull`, { method: 'POST' });
            const data = await res.json();
            if (!data.success) {
                toast.warning(data.error || 'Cannot start pull');
            } else {
                console.log('[JetDrive] Calling aiAssistant.onPullStart()');
                aiAssistant.onPullStart(); // 🎤 AI: "Let's go!"
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

    // Track previous simState to detect pull end
    const prevSimStateRef = useRef<string>('stopped');
    useEffect(() => {
        // Detect pull end: transitioning from 'pull' to 'decel' or 'cooldown'
        if (prevSimStateRef.current === 'pull' && (simState === 'decel' || simState === 'cooldown')) {
            // Pull just ended, announce with peak HP
            aiAssistant.onPullEnd(currentHp);
        }
        prevSimStateRef.current = simState;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [simState, currentHp]);

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
            // If simulator is active and mode is 'simulate', use simulator_pull instead
            const actualMode = (isSimulatorActive && mode === 'simulate') ? 'simulator_pull' : mode;

            console.log('[Analyze] Mode:', mode, 'Actual mode:', actualMode, 'Simulator active:', isSimulatorActive);
            console.log('[Analyze] Pull data status:', pullDataStatus);

            // If using simulator_pull mode, check if pull data is available
            // Note: We allow the backend to validate as well, since the frontend check might be stale
            if (actualMode === 'simulator_pull' && pullDataStatus && !pullDataStatus.has_data) {
                console.warn('[Analyze] No pull data detected in frontend, but allowing backend to validate');
                // Don't throw here - let backend handle validation for more accurate error messages
            }

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
                const modeUsed = (isSimulatorActive && data.mode === 'simulator_pull') ? 'simulator pull data' : 'simulated data';

                toast.success('Analysis complete!', {
                    description: `${peakHp.toFixed(1)} HP @ ${peakHpRpm} RPM (from ${modeUsed})`
                });
                setSelectedRun(data.run_id);
                setWorkflowState('complete');
                void refetchStatus();
                // Generate new run ID for next run
                setRunId(`dyno_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}_${Date.now().toString(36)}`);
            } else {
                toast.error('Analysis failed', { description: data.error });
            }
        },
        onError: (error: Error) => {
            toast.error('Analysis failed', { description: error.message });
        },
    });

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

    // Fetch PVV
    useEffect(() => {
        if (selectedRun) {
            fetch(`${API_BASE}/run/${selectedRun}/pvv`)
                .then(r => r.json())
                .then(d => setPvvContent(d.content))
                .catch(() => { });
        }
    }, [selectedRun]);

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

    const runs: RunInfo[] = statusData?.runs || [];
    const analysis = runData?.manifest?.analysis;
    const grid = runData?.manifest?.grid;
    const veGrid = runData?.ve_grid || [];

    return (
        <div className="min-h-screen bg-gradient-to-b from-zinc-950 via-zinc-900/95 to-zinc-950 relative">
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
                                    isDynoCapturing={isCapturing || isSimulatorActive}
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
                    isCapturing={isCapturing || isSimulatorActive}
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
                    selectedProfile={selectedProfile}
                />

                {/* Main Tabs */}
                <Tabs value={activeMainTab} onValueChange={setActiveMainTab} className="w-full">
                    <TabsList className="grid w-full grid-cols-3 max-w-lg">
                        <TabsTrigger value="hardware" className="flex items-center gap-2">
                            <Radio className="h-4 w-4" />
                            Hardware
                        </TabsTrigger>
                        <TabsTrigger value="live" className="flex items-center gap-2">
                            <Activity className="h-4 w-4" />
                            Live
                        </TabsTrigger>
                        <TabsTrigger value="autotune" className="flex items-center gap-2">
                            <Zap className="h-4 w-4" />
                            Auto-Tune
                        </TabsTrigger>
                    </TabsList>

                    {/* Hardware Tab */}
                    <TabsContent value="hardware" className="mt-6">
                        <HardwareTab apiUrl={API_BASE} />
                    </TabsContent>

                    {/* Live Dashboard Tab */}
                    <TabsContent value="live" className="mt-6">
                        <JetDriveLiveDashboard apiUrl={API_BASE} />
                    </TabsContent>

                    {/* Auto-Tune Tab */}
                    <TabsContent value="autotune" className="mt-6">
                        {/* Main Content - State Aware */}
                        {workflowState === 'disconnected' ? (
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
                                            value={isSimulatorActive || isCapturing ? currentHp : (analysis?.peak_hp || 0)}
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
                                                <Button
                                                    onClick={handleTriggerPull}
                                                    disabled={simState !== 'idle'}
                                                    uiSound="pull"
                                                    className="bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-500 hover:to-red-500"
                                                >
                                                    <Play className="w-4 h-4 mr-2" />
                                                    {simState === 'idle' ? 'Trigger Pull' :
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
                                            </>
                                        ) : (
                                            /* Hardware Controls */
                                            <>
                                                <Button
                                                    onClick={isCapturing ? stopCapture : startCapture}
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
                                                    {Math.round(simThrottle)}%
                                                </div>
                                            </div>
                                            <Slider
                                                value={[simThrottle]}
                                                onValueChange={(v) => onSimThrottleChange(v?.[0] ?? 0)}
                                                min={0}
                                                max={100}
                                                step={1}
                                            />
                                            <div className="mt-2 text-[10px] text-zinc-500">
                                                Drag to set throttle; you can still use <span className="font-mono">Trigger Pull</span> for a sweep.
                                            </div>
                                        </div>
                                    )}

                                    {/* Live VE Table with Cell Tracing */}
                                    {(isConnected || isSimulatorActive) && (
                                        <Card className="bg-zinc-900/50 border-zinc-800">
                                            <CardContent className="pt-4">
                                                <LiveVETable
                                                    currentRpm={currentRpm}
                                                    currentMap={currentMap}
                                                    currentAfr={currentAfr}
                                                    afrTargets={afrTargets}
                                                    isLive={isCapturing || isSimulatorActive}
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
                        )}
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    );
}
