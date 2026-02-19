/**
 * TuningWizard - Main auto-tune workflow orchestrator
 *
 * Provides a guided, step-by-step tuning experience with:
 * - Big button primary actions for dyno operators
 * - Progressive disclosure (details hidden until needed)
 * - Voice feedback instead of text clutter
 * - Auto-advance between steps when conditions are met
 */

import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { Play, Pause, ArrowRight, Download, Check, AlertCircle, RefreshCw, ChevronDown, ChevronUp, Settings, Zap, Upload, FileText, Flame, Thermometer, Activity, Gauge, Crosshair } from 'lucide-react';
import { toast } from '@/lib/toast';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { cn } from '../../lib/utils';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';

// Types
import type { TuneImportResult } from './TuneImport';
import type { LiveVEExportData } from './LiveVETable';
import type { ApplyReport, VEBoundsPreset, CoverageReport } from '../../types/veApplyTypes';

// Core engine
import { calculateDualCylinderCoverage, getCoverageGrade, calculateApply, getApplySummary } from '../../utils/veApply';

export type WizardStep = 'setup' | 'collect' | 'analyze' | 'review' | 'apply';

export interface WizardLiveStatus {
  // Engine operating state
  engineState: 'idle' | 'cruise' | 'wot' | 'decel' | 'tip_in' | 'unknown';
  // Run/workflow state  
  runState: 'disconnected' | 'monitoring' | 'pull' | 'cooldown' | 'analyzing' | 'complete' | 'idle';
  // AFR
  afrValue: number;       // current AFR reading
  afrTarget: number;      // current target
  rpm: number;            // engine rpm
  // Temperatures
  engineTemp: number;     // Temperature 1 (F)
  coolantTemp: number;    // Temperature 2 (F)
  egtTemp: number;        // EGT if available (F)
  // Throttle/Load
  tps: number;            // Throttle position 0-100
  loadPct: number;        // Engine load 0-100
}

export interface PullSummary {
  peakHp: number;
  peakTq: number;
  peakRpm: number;
  afrAvg: number;
  nextAction?: string;
  coverageGain?: number;
  pullNumber?: number;
}

export interface WizardState {
  step: WizardStep;
  isSimulatorActive: boolean;
  isCapturing: boolean;
  importedTune: TuneImportResult | null;
  liveData: LiveVEExportData | null;
  applyReport: ApplyReport | null;
  coverageReport: CoverageReport | null;
}

interface TuningWizardProps {
  // External state (use isLive for mode-agnostic "has live data"; keep booleans for button logic)
  isSimulatorActive: boolean;
  isCapturing: boolean;
  /** True when simulator or real capture is active - use this to avoid combined boolean logic */
  isLive?: boolean;
  importedTune: TuneImportResult | null;
  liveData: LiveVEExportData | null;
  
  // Live status data
  liveStatus?: WizardLiveStatus;

  // Throttle control
  onThrottleChange?: (throttlePct: number) => void;
  pullThrottle?: number;

  // Post-pull summary
  lastPullSummary?: PullSummary | null;
  onDismissPullSummary?: () => void;
  
  // Callbacks
  onStartSimulator: () => void;
  onStopSimulator: () => void;
  onStartCapture: () => void;
  onStopCapture: () => void;
  onTriggerPull: () => void;
  onAnalyze: () => Promise<void>;
  onApply: (report: ApplyReport) => void;
  onReset: () => void;
  onShowTuneImport?: () => void; // NEW: Callback to show tune import dialog
  
  // Settings
  veBoundsPreset?: VEBoundsPreset;
  onVeBoundsPresetChange?: (preset: VEBoundsPreset) => void;
  
  // Optional: render custom content in expanded areas
  renderLiveTable?: () => React.ReactNode;
  renderApplyPreview?: (report: ApplyReport) => React.ReactNode;
}

// Step configuration
const STEP_CONFIG: Record<WizardStep, {
  number: number;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
}> = {
  setup: { number: 1, title: 'Setup', icon: Settings },
  collect: { number: 2, title: 'Collect', icon: Zap },
  analyze: { number: 3, title: 'Analyze', icon: RefreshCw },
  review: { number: 4, title: 'Review', icon: AlertCircle },
  apply: { number: 5, title: 'Apply', icon: Download },
};

// Coverage thresholds for auto-advance
const COVERAGE_TARGET = 60; // weightedCoveragePct
const MIN_HITS_TARGET = 500;

export function TuningWizard({
  isSimulatorActive,
  isCapturing,
  isLive: isLiveProp,
  importedTune,
  liveData,
  liveStatus,
  onThrottleChange,
  pullThrottle,
  lastPullSummary,
  onDismissPullSummary,
  onStartSimulator,
  onStopSimulator,
  onStartCapture,
  onStopCapture,
  onTriggerPull,
  onAnalyze,
  onApply,
  onReset,
  veBoundsPreset = 'na_harley',
  onVeBoundsPresetChange,
  renderLiveTable,
  renderApplyPreview,
}: TuningWizardProps) {
  const isLive = isLiveProp ?? (isSimulatorActive || isCapturing);
  // Wizard state
  const [step, setStep] = useState<WizardStep>('setup');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [applyReport, setApplyReport] = useState<ApplyReport | null>(null);
  const [showPvvAlert, setShowPvvAlert] = useState(false);
  
  // Throttled coverage state to prevent flashing
  const [throttledCoverageReport, setThrottledCoverageReport] = useState<CoverageReport | null>(null);
  const [throttledCoveragePct, setThrottledCoveragePct] = useState(0);
  const [throttledTotalHits, setThrottledTotalHits] = useState(0);
  const lastCoverageUpdateRef = useRef<number>(0);
  
  // Calculate coverage from live data (immediate calculation)
  const coverageReport = useMemo(() => {
    if (!liveData?.frontHitCounts || !liveData?.rearHitCounts) return null;
    return calculateDualCylinderCoverage(
      liveData.frontHitCounts,
      liveData.rearHitCounts,
      liveData.rpmBins,
      liveData.mapBins
    );
  }, [liveData]);
  
  // Throttle coverage updates to prevent flashing (update max every 1 second)
  useEffect(() => {
    if (!coverageReport) {
      setThrottledCoverageReport(null);
      setThrottledCoveragePct(0);
      setThrottledTotalHits(0);
      return;
    }
    
    const now = Date.now();
    const timeSinceLastUpdate = now - lastCoverageUpdateRef.current;
    
    // Only update if enough time has passed (1000ms) or if it's a significant change (>2%)
    const newCoveragePct = coverageReport.weightedCoveragePct;
    const newTotalHits = liveData?.totalHits ?? 0;
    const significantChange = Math.abs(newCoveragePct - throttledCoveragePct) > 2;
    const shouldUpdate = timeSinceLastUpdate > 1000 || significantChange || throttledCoverageReport === null;
    
    if (shouldUpdate) {
      setThrottledCoverageReport(coverageReport);
      setThrottledCoveragePct(newCoveragePct);
      setThrottledTotalHits(newTotalHits);
      lastCoverageUpdateRef.current = now;
    }
  }, [coverageReport, liveData?.totalHits, throttledCoveragePct, throttledCoverageReport]);
  
  // Use throttled values for display to prevent flashing
  const coveragePct = throttledCoveragePct;
  const totalHits = throttledTotalHits;
  const coverageGrade = useMemo(() => getCoverageGrade(coveragePct), [coveragePct]);
  
  // Auto-advance: Setup -> Collect (use isLive so mode is explicit)
  useEffect(() => {
    if (step === 'setup' && importedTune && isLive) {
      setStep('collect');
    }
  }, [step, importedTune, isLive]);
  
  // Check if ready to proceed from Collect
  const canProceedToAnalyze = coveragePct >= COVERAGE_TARGET && totalHits >= MIN_HITS_TARGET;
  
  // Handle analyze step with PVV validation
  const handleAnalyze = useCallback(async () => {
    // Check if PVV/tune is imported
    if (!importedTune) {
      setShowPvvAlert(true);
      return;
    }
    
    setIsAnalyzing(true);
    setStep('analyze');
    
    try {
      await onAnalyze();
      
      // Calculate apply report
      if (importedTune && liveData) {
        const report = calculateApply(
          { front: importedTune.veFront?.values ?? [], rear: importedTune.veRear?.values ?? [] },
          { front: liveData.frontCorrections, rear: liveData.rearCorrections },
          { front: liveData.frontHitCounts, rear: liveData.rearHitCounts },
          liveData.rpmBins,
          liveData.mapBins,
          veBoundsPreset
        );
        setApplyReport(report);
        setStep('review');
      } else {
        // Analysis succeeded but no live data to calculate corrections
        // Go back to collect step so user can run more pulls
        console.warn('[TuningWizard] Analysis succeeded but missing liveData - returning to collect');
        setStep('collect');
      }
    } catch (error) {
      // Analysis failed - go back to collect step instead of getting stuck
      console.error('[TuningWizard] Analysis failed:', error);
      toast.error('Analysis failed. Please try again.');
      setStep('collect');
    } finally {
      setIsAnalyzing(false);
    }
  }, [onAnalyze, importedTune, liveData, veBoundsPreset]);
  
  // Handle apply
  const handleApply = useCallback(() => {
    if (applyReport && applyReport.blockReasons.length === 0) {
      onApply(applyReport);
      setStep('apply');
    }
  }, [applyReport, onApply]);

  // Handle trigger pull with PVV validation
  const handleTriggerPull = useCallback(() => {
    // Check if PVV/tune is imported
    if (!importedTune) {
      setShowPvvAlert(true);
      return;
    }
    
    onTriggerPull();
  }, [importedTune, onTriggerPull]);

  // Handle start simulator with PVV validation
  const handleStartSimulator = useCallback(() => {
    // Check if PVV/tune is imported
    if (!importedTune) {
      setShowPvvAlert(true);
      return;
    }
    
    onStartSimulator();
  }, [importedTune, onStartSimulator]);
  
  // Get apply summary
  const applySummary = useMemo(() => {
    if (!applyReport) return null;
    return getApplySummary(applyReport);
  }, [applyReport]);

  const throttleTrackRef = useRef<HTMLDivElement | null>(null);
  const [isDraggingThrottle, setIsDraggingThrottle] = useState(false);
  const throttleValueRef = useRef(0);
  const liveRpmRef = useRef(0);
  const lastTargetForPullRef = useRef(0);

  const currentRunState = liveStatus?.runState;
  const isPulling = currentRunState === 'pull';
  const minPullRpm = 1500;

  useEffect(() => {
    liveRpmRef.current = liveStatus?.rpm ?? 0;
  }, [liveStatus?.rpm]);

  // Trigger pull on roll-on to WOT (target crosses ≥98%), no hold delay
  const updateThrottleFromClientY = useCallback((clientY: number) => {
    if (!throttleTrackRef.current || !isSimulatorActive) return;
    const rect = throttleTrackRef.current.getBoundingClientRect();
    const rawPct = ((rect.bottom - clientY) / rect.height) * 100;
    const clamped = Math.max(0, Math.min(100, rawPct));
    throttleValueRef.current = clamped;
    onThrottleChange?.(clamped);

    const rpmOk = liveRpmRef.current >= minPullRpm;
    const crossedWot = clamped >= 98 && lastTargetForPullRef.current < 98;
    if (crossedWot && !isPulling && rpmOk) {
      handleTriggerPull();
    }
    lastTargetForPullRef.current = clamped;
  }, [minPullRpm, handleTriggerPull, isPulling, isSimulatorActive, onThrottleChange]);

  useEffect(() => {
    if (!isDraggingThrottle) return;
    const onMove = (event: PointerEvent) => {
      updateThrottleFromClientY(event.clientY);
    };
    const onUp = () => {
      setIsDraggingThrottle(false);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, [isDraggingThrottle, updateThrottleFromClientY]);
  
  // Render live status strip (3-column layout: bars | pills | temps)
  const renderLiveStatusStrip = () => {
    if (!liveStatus || (step !== 'collect' && step !== 'analyze')) return null;
    
    // Color mappings
    const engineStateColors: Record<string, string> = {
      idle: '#a1a1aa',      // zinc-400
      cruise: '#22d3ee',    // cyan-400
      wot: '#f97316',       // orange-500
      decel: '#3b82f6',     // blue-400
      tip_in: '#f59e0b',    // amber-400
      unknown: '#71717a',   // zinc-500
    };
    
    const runStateColors: Record<string, string> = {
      disconnected: '#71717a',  // zinc-500
      monitoring: '#22d3ee',    // cyan-400
      pull: '#ef4444',          // red-500 (pulsing)
      cooldown: '#f59e0b',      // amber-500
      analyzing: '#a78bfa',     // violet-400
      complete: '#22c55e',      // green-500
      idle: '#22c55e',          // green-500
    };
    
    const { engineState, runState, afrValue, afrTarget, engineTemp, coolantTemp, egtTemp, tps, loadPct } = liveStatus;
    
    // AFR status
    const afrDelta = afrValue - afrTarget;
    const isLean = afrDelta > 0.3;
    const isRich = afrDelta < -0.3;
    const afrStatus = isLean ? 'LEAN' : isRich ? 'RICH' : 'ON TARGET';
    const afrColor = isLean ? '#ef4444' : isRich ? '#3b82f6' : '#22c55e';
    
    // TPS/Load bar colors
    const getBarColor = (value: number) => {
      if (value >= 85) return '#f97316'; // orange-500 (WOT)
      if (value >= 50) return '#f59e0b'; // amber-500
      return '#4ade80'; // green-400
    };
    
    // Temperature thresholds
    const getTempColor = (temp: number, isEGT: boolean = false) => {
      if (isEGT) {
        if (temp >= 1600) return '#ef4444'; // red-500 critical
        if (temp >= 1400) return '#f59e0b'; // amber-500 warning
        return '#4ade80'; // green-400 normal
      } else {
        if (temp >= 240) return '#ef4444'; // red-500 critical
        if (temp >= 220) return '#f59e0b'; // amber-500 warning
        return '#4ade80'; // green-400 normal
      }
    };
    
    const tpsColor = getBarColor(tps);
    const loadColor = getBarColor(loadPct);
    const engineTempColor = getTempColor(engineTemp);
    const coolantTempColor = getTempColor(coolantTemp);
    const egtTempColor = getTempColor(egtTemp, true);
    
    // Vertical fill bar component - LARGER
    const VerticalBar = ({ label, value, color }: { label: string; value: number; color: string }) => (
      <div className="flex flex-col items-center gap-1.5">
        <div className="text-[11px] uppercase tracking-wider text-zinc-400 font-mono font-semibold">{label}</div>
        <div className="relative w-6 h-24 bg-zinc-800 rounded-lg overflow-hidden border border-zinc-700/50">
          <div
            className="absolute bottom-0 left-0 right-0 rounded-b-md transition-all duration-300"
            style={{
              height: `${Math.min(100, Math.max(0, value))}%`,
              backgroundColor: color,
              boxShadow: `0 0 12px ${color}50`
            }}
          />
        </div>
        <div className="text-sm font-bold tabular-nums font-mono" style={{ color }}>
          {value.toFixed(0)}%
        </div>
      </div>
    );
    
    return (
      <div className="flex items-center justify-between gap-6 mb-6 px-2">
        {/* Left: Vertical bars for TPS and Load */}
        <div className="flex gap-4 p-3 rounded-xl bg-zinc-900/70 border border-zinc-800/50">
          <VerticalBar label="TPS" value={tps} color={tpsColor} />
          <VerticalBar label="LOAD" value={loadPct} color={loadColor} />
        </div>
        
        {/* Center: Status pills - LARGER */}
        <div className="flex flex-wrap items-center justify-center gap-3">
          {/* Engine State Pill */}
          <div
            className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-bold uppercase tracking-wide"
            style={{
              backgroundColor: `${engineStateColors[engineState]}20`,
              color: engineStateColors[engineState],
              border: `1px solid ${engineStateColors[engineState]}40`
            }}
          >
            <Activity className="w-4 h-4" />
            {engineState}
          </div>
          
          {/* Run State Pill */}
          <div
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-full text-sm font-bold uppercase tracking-wide",
              runState === 'pull' && "animate-pulse"
            )}
            style={{
              backgroundColor: `${runStateColors[runState]}20`,
              color: runStateColors[runState],
              border: `1px solid ${runStateColors[runState]}40`
            }}
          >
            <Gauge className="w-4 h-4" />
            {runState}
          </div>
          
          {/* AFR Pill */}
          <div
            className="flex items-center gap-2 px-4 py-2 rounded-full"
            style={{
              backgroundColor: `${afrColor}20`,
              border: `1px solid ${afrColor}40`
            }}
          >
            <Crosshair className="w-4 h-4" style={{ color: afrColor }} />
            <span className="text-lg font-bold tabular-nums" style={{ color: afrColor }}>
              {afrValue > 0 ? afrValue.toFixed(1) : '—'}
            </span>
            <Badge
              className="text-[10px] px-1.5 py-0.5 font-mono tracking-wider border h-5"
              style={{
                backgroundColor: `${afrColor}25`,
                color: afrColor,
                borderColor: `${afrColor}50`
              }}
            >
              {afrStatus}
            </Badge>
          </div>
        </div>
        
        {/* Right: Stacked temps - LARGER */}
        <div className="flex flex-col gap-2 p-3 rounded-xl bg-zinc-900/70 border border-zinc-800/50 min-w-[110px]">
          {/* Engine Temp */}
          <div className="flex items-center justify-between gap-3">
            <Thermometer className="w-4 h-4 text-zinc-400" />
            <span className="text-xs text-zinc-400 font-mono font-semibold">ENG</span>
            <span className="text-base font-bold tabular-nums font-mono" style={{ color: engineTempColor }}>
              {engineTemp > 0 ? `${engineTemp.toFixed(0)}°` : '—'}
            </span>
          </div>
          {/* Coolant Temp */}
          <div className="flex items-center justify-between gap-3">
            <Thermometer className="w-4 h-4 text-zinc-400" />
            <span className="text-xs text-zinc-400 font-mono font-semibold">CLT</span>
            <span className="text-base font-bold tabular-nums font-mono" style={{ color: coolantTempColor }}>
              {coolantTemp > 0 ? `${coolantTemp.toFixed(0)}°` : '—'}
            </span>
          </div>
          {/* EGT */}
          <div className="flex items-center justify-between gap-3">
            <Flame className="w-4 h-4 text-zinc-400" />
            <span className="text-xs text-zinc-400 font-mono font-semibold">EGT</span>
            <span className="text-base font-bold tabular-nums font-mono" style={{ color: egtTempColor }}>
              {egtTemp > 0 ? `${egtTemp.toFixed(0)}°` : '—'}
            </span>
          </div>
        </div>
      </div>
    );
  };
  
  // Render step indicator
  const renderStepIndicator = () => (
    <div className="flex items-center justify-center gap-2 mb-6">
      {(['setup', 'collect', 'analyze', 'review', 'apply'] as WizardStep[]).map((s, idx) => {
        const config = STEP_CONFIG[s];
        const isCurrent = step === s;
        const isPast = STEP_CONFIG[step].number > config.number;
        const Icon = config.icon;
        
        return (
          <React.Fragment key={s}>
            {idx > 0 && (
              <div className={cn(
                "w-8 h-0.5 transition-colors",
                isPast ? "bg-green-500" : "bg-zinc-700"
              )} />
            )}
            <button
              onClick={() => isPast && setStep(s)}
              disabled={!isPast}
              className={cn(
                "w-10 h-10 rounded-full flex items-center justify-center transition-all",
                isCurrent && "bg-cyan-500 text-white ring-4 ring-cyan-500/20",
                isPast && "bg-green-500 text-white cursor-pointer hover:bg-green-400",
                !isCurrent && !isPast && "bg-zinc-800 text-zinc-500"
              )}
            >
              {isPast ? <Check className="w-5 h-5" /> : <Icon className="w-5 h-5" />}
            </button>
          </React.Fragment>
        );
      })}
    </div>
  );
  
  // Render progress ring (big visual)
  const renderProgressRing = () => {
    const radius = 80;
    const circumference = 2 * Math.PI * radius;
    const progress = (coveragePct / 100) * circumference;
    
    return (
      <div className="relative w-48 h-48 mx-auto mb-6">
        {/* Background ring */}
        <svg className="w-48 h-48 transform -rotate-90">
          <circle
            cx="96"
            cy="96"
            r={radius}
            stroke="currentColor"
            strokeWidth="12"
            fill="transparent"
            className="text-zinc-800"
          />
          <circle
            cx="96"
            cy="96"
            r={radius}
            stroke="currentColor"
            strokeWidth="12"
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={circumference - progress}
            strokeLinecap="round"
            className={cn(
              "transition-all duration-500",
              coveragePct >= 75 ? "text-green-500" :
              coveragePct >= 50 ? "text-yellow-500" :
              coveragePct >= 25 ? "text-orange-500" : "text-red-500"
            )}
          />
        </svg>
        
        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-bold text-white transition-all duration-500">{coveragePct.toFixed(0)}%</span>
          <span className="text-sm text-zinc-400">Coverage</span>
          <Badge className={cn("mt-1 transition-all duration-500", coverageGrade.color)}>
            {coverageGrade.grade}
          </Badge>
        </div>
      </div>
    );
  };

  const renderThrottleControl = () => {
    if (!isSimulatorActive || !onThrottleChange || !liveStatus || step !== 'collect') return null;
    const liveTps = liveStatus.tps ?? 0;
    const targetTps = pullThrottle ?? 0;
    const rpm = liveStatus.rpm ?? 0;
    const rpmTooLow = rpm < minPullRpm;
    const throttleColor = liveTps >= 85 ? '#f97316' : liveTps >= 50 ? '#f59e0b' : '#4ade80';
    const targetTop = 100 - Math.min(100, Math.max(0, targetTps));

    return (
      <div className="flex flex-col items-center gap-3">
        <div className="text-xs uppercase tracking-wider text-zinc-400 font-mono">
          Roll on to WOT to start pull
        </div>
        <div
          ref={throttleTrackRef}
          onPointerDown={(event) => {
            setIsDraggingThrottle(true);
            updateThrottleFromClientY(event.clientY);
          }}
          className="relative w-16 h-48 rounded-2xl bg-zinc-900/80 border border-zinc-800/60 overflow-hidden cursor-pointer"
        >
          {/* WOT marker */}
          <div className="absolute left-0 right-0 top-2 h-px bg-zinc-700/80" />
          <div
            className="absolute bottom-0 left-0 right-0 transition-all duration-300"
            style={{
              height: `${Math.min(100, Math.max(0, liveTps))}%`,
              backgroundColor: throttleColor,
              boxShadow: `0 0 16px ${throttleColor}60`,
            }}
          />
          {/* Target marker */}
          <div
            className="absolute left-0 right-0 h-px bg-cyan-500/70"
            style={{ top: `${targetTop}%` }}
          />
          <div className="absolute top-2 left-1/2 -translate-x-1/2 text-[10px] text-zinc-500 font-mono">
            WOT
          </div>
        </div>
        <div className="text-3xl font-bold font-mono tabular-nums" style={{ color: throttleColor }}>
          {Math.round(liveTps)}%
        </div>
        <div className="text-[11px] text-zinc-500 font-mono">
          Target {Math.round(targetTps)}%
        </div>
        <div className={cn("text-[11px] font-mono", rpmTooLow ? "text-red-400" : "text-emerald-400")}>
          RPM {Math.round(rpm)} {rpmTooLow ? `(min ${minPullRpm})` : 'ready'}
        </div>
        <div className="text-xs text-zinc-500 font-mono">
          {isPulling ? 'PULLING...' : rpmTooLow ? 'RPM TOO LOW' : 'READY'}
        </div>
      </div>
    );
  };
  
  // Render big action button based on current step
  const renderActionButton = () => {
    switch (step) {
      case 'setup':
        return (
          <Button
            onClick={isSimulatorActive ? onStopSimulator : handleStartSimulator}
            size="lg"
            className={cn(
              "w-64 h-20 text-xl font-bold rounded-2xl transition-all",
              isSimulatorActive
                ? "bg-red-600 hover:bg-red-500"
                : "bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 shadow-lg shadow-cyan-500/25"
            )}
          >
            {isSimulatorActive ? (
              <>
                <Pause className="w-6 h-6 mr-3" />
                STOP
              </>
            ) : (
              <>
                <Play className="w-6 h-6 mr-3" />
                START
              </>
            )}
          </Button>
        );
        
      case 'collect':
        return (
          <div className="space-y-5">
            {/* Primary: Trigger Pull or Analyze */}
            {canProceedToAnalyze && (
              <Button
                onClick={handleAnalyze}
                size="lg"
                className="w-64 h-20 text-xl font-bold rounded-2xl bg-gradient-to-r from-green-600 to-green-500 hover:from-green-500 hover:to-green-400 shadow-lg shadow-green-500/25 animate-pulse"
              >
                <ArrowRight className="w-6 h-6 mr-3" />
                ANALYZE
              </Button>
            )}
            
            {/* Secondary: Manual analyze */}
            {!canProceedToAnalyze && totalHits > 50 && (
              <Button
                onClick={handleAnalyze}
                variant="outline"
                className="w-64 border-zinc-700 text-zinc-400"
              >
                <ArrowRight className="w-4 h-4 mr-2" />
                Analyze Anyway
              </Button>
            )}
          </div>
        );
        
      case 'analyze':
        return (
          <div className="flex flex-col items-center gap-4">
            <RefreshCw className="w-16 h-16 text-cyan-400 animate-spin" />
            <span className="text-xl text-zinc-300">Analyzing...</span>
          </div>
        );
        
      case 'review':
        return (
          <Button
            onClick={handleApply}
            disabled={!applySummary?.canApply}
            size="lg"
            className={cn(
              "w-64 h-20 text-xl font-bold rounded-2xl transition-all",
              applySummary?.canApply
                ? "bg-gradient-to-r from-green-600 to-green-500 hover:from-green-500 hover:to-green-400 shadow-lg shadow-green-500/25"
                : "bg-zinc-700 cursor-not-allowed opacity-50"
            )}
          >
            {applySummary?.canApply ? (
              <>
                <Check className="w-6 h-6 mr-3" />
                APPLY
              </>
            ) : (
              <>
                <AlertCircle className="w-6 h-6 mr-3" />
                BLOCKED
              </>
            )}
          </Button>
        );
        
      case 'apply':
        return (
          <div className="space-y-4">
            <Button
              onClick={() => {
                if (applyReport) {
                  onApply(applyReport);
                }
              }}
              size="lg"
              className="w-64 h-20 text-xl font-bold rounded-2xl bg-gradient-to-r from-green-600 to-green-500 hover:from-green-500 hover:to-green-400 shadow-lg shadow-green-500/25"
            >
              <Download className="w-6 h-6 mr-3" />
              DOWNLOAD
            </Button>
            
            <Button
              onClick={() => {
                onReset();
                setStep('setup');
                setApplyReport(null);
              }}
              variant="outline"
              className="w-64 border-zinc-700"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              New Session
            </Button>
          </div>
        );
    }
  };
  
  // Render status badge
  const renderStatusBadge = () => {
    if (step === 'collect') {
      return (
        <div className="flex items-center justify-center gap-4 mb-4">
          <Badge variant="outline" className="text-cyan-400 border-cyan-400/30">
            {totalHits.toLocaleString()} hits
          </Badge>
          {isSimulatorActive && (
            <Badge variant="outline" className="text-orange-400 border-orange-400/30 animate-pulse">
              LIVE
            </Badge>
          )}
        </div>
      );
    }
    
    if (step === 'review' && applySummary) {
      return (
        <Badge
          className={cn(
            "mb-4",
            applySummary.status === 'blocked' && "bg-red-500/20 text-red-400",
            applySummary.status === 'warnings' && "bg-yellow-500/20 text-yellow-400",
            applySummary.status === 'ready' && "bg-green-500/20 text-green-400"
          )}
        >
          {applySummary.headline}
        </Badge>
      );
    }
    
    return null;
  };

  const renderPullSummary = () => {
    if (!lastPullSummary) return null;
    const afrTargetValue = liveStatus?.afrTarget ?? 14.7;
    const afrDelta = lastPullSummary.afrAvg - afrTargetValue;
    const isLean = afrDelta > 0.3;
    const isRich = afrDelta < -0.3;
    const afrStatus = isLean ? 'LEAN' : isRich ? 'RICH' : 'ON TARGET';
    const afrColor = isLean ? '#ef4444' : isRich ? '#3b82f6' : '#22c55e';

    return (
      <div className="mt-6 w-full max-w-2xl rounded-2xl bg-zinc-900/80 border border-zinc-800/60 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-sm uppercase tracking-wider text-zinc-400 font-mono">
              Last Pull Summary
            </div>
            <div className="mt-2 grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold text-cyan-400">{lastPullSummary.peakHp.toFixed(1)}</div>
                <div className="text-xs text-zinc-500">Peak HP</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-cyan-400">{lastPullSummary.peakTq.toFixed(1)}</div>
                <div className="text-xs text-zinc-500">Peak TQ</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-cyan-400">{lastPullSummary.peakRpm.toFixed(0)}</div>
                <div className="text-xs text-zinc-500">Peak RPM</div>
              </div>
            </div>
          </div>
          {onDismissPullSummary && (
            <Button
              variant="outline"
              size="sm"
              className="border-zinc-700 text-zinc-400"
              onClick={onDismissPullSummary}
            >
              Dismiss
            </Button>
          )}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full border" style={{ borderColor: `${afrColor}40`, backgroundColor: `${afrColor}15` }}>
            <span className="text-sm font-bold tabular-nums" style={{ color: afrColor }}>
              AFR {lastPullSummary.afrAvg.toFixed(1)}
            </span>
            <Badge
              className="text-[10px] px-1.5 py-0.5 font-mono tracking-wider border h-5"
              style={{ backgroundColor: `${afrColor}25`, color: afrColor, borderColor: `${afrColor}50` }}
            >
              {afrStatus}
            </Badge>
          </div>
          {typeof lastPullSummary.coverageGain === 'number' && (
            <div className="text-sm text-zinc-400">
              Coverage: <span className="text-emerald-400 font-semibold">+{lastPullSummary.coverageGain.toFixed(1)}%</span>
            </div>
          )}
          {typeof lastPullSummary.pullNumber === 'number' && (
            <div className="text-sm text-zinc-500">
              Pull {lastPullSummary.pullNumber}
            </div>
          )}
        </div>

        {lastPullSummary.nextAction && (
          <div className="mt-4 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800 text-sm text-zinc-200">
            <span className="text-zinc-400 font-mono text-xs uppercase tracking-wider">NextGen</span>
            <div className="mt-1">{lastPullSummary.nextAction}</div>
          </div>
        )}
      </div>
    );
  };
  
  // Render details (expanded view)
  const renderDetails = () => {
    if (!showDetails) return null;
    
    return (
      <div className="mt-6 p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
        {step === 'collect' && renderLiveTable?.()}
        {step === 'review' && applyReport && renderApplyPreview?.(applyReport)}
        
        {/* Coverage breakdown */}
        {step === 'collect' && throttledCoverageReport && (
          <div className="grid grid-cols-2 gap-4 mt-4">
            {throttledCoverageReport.zoneBreakdown.map(zone => (
              <div key={zone.zone} className="flex items-center gap-2">
                <div className="w-24 text-xs text-zinc-400 capitalize">{zone.zone}</div>
                <Progress value={zone.coveragePct} className="flex-1 h-2" />
                <div className="w-12 text-xs text-right text-zinc-500">{zone.coveragePct.toFixed(0)}%</div>
              </div>
            ))}
          </div>
        )}
        
        {/* Apply summary */}
        {step === 'review' && applyReport && (
          <div className="grid grid-cols-4 gap-4 mt-4 text-center">
            <div>
              <div className="text-2xl font-bold text-green-400">{applyReport.totalCells - applyReport.skippedCells}</div>
              <div className="text-xs text-zinc-500">Updated</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-zinc-400">{applyReport.skippedCells}</div>
              <div className="text-xs text-zinc-500">Skipped</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-yellow-400">{applyReport.clampedCells}</div>
              <div className="text-xs text-zinc-500">Clamped</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-orange-400">{applyReport.boundedCells}</div>
              <div className="text-xs text-zinc-500">Bounded</div>
            </div>
          </div>
        )}
      </div>
    );
  };
  
  return (
    <Card className="bg-zinc-950/80 border-zinc-800">
      <CardContent className="pt-6">
        {/* Step indicator */}
        {renderStepIndicator()}
        
        {/* Live status strip */}
        {renderLiveStatusStrip()}
        
        {/* Main content area */}
        <div className="flex flex-col items-center py-8">
          {/* Progress ring + throttle (collect step only) */}
          {step === 'collect' && (
            <div className="flex items-center justify-center gap-10">
              {renderProgressRing()}
              {renderThrottleControl()}
            </div>
          )}
          
          {/* Success animation (apply step) */}
          {step === 'apply' && (
            <div className="w-32 h-32 rounded-full bg-green-500/20 flex items-center justify-center mb-6 animate-bounce">
              <Check className="w-16 h-16 text-green-400" />
            </div>
          )}
          
          {/* Status badge */}
          {renderStatusBadge()}
          
          {/* Big action button */}
          {renderActionButton()}

        {/* Post-pull summary */}
        {renderPullSummary()}
        </div>
        
        {/* Details toggle */}
        {(step === 'collect' || step === 'review') && (
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="w-full flex items-center justify-center gap-2 py-3 text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            {showDetails ? (
              <>
                <ChevronUp className="w-4 h-4" />
                Hide Details
              </>
            ) : (
              <>
                <ChevronDown className="w-4 h-4" />
                Show Details
              </>
            )}
          </button>
        )}
        
        {/* Expandable details */}
        {renderDetails()}
      </CardContent>

      {/* PVV import required alert */}
      <AlertDialog open={showPvvAlert} onOpenChange={setShowPvvAlert}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Import a tune first</AlertDialogTitle>
            <AlertDialogDescription>
              Import a base tune (PVV or preset) before analyzing or triggering pulls so corrections can be applied correctly.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => setShowPvvAlert(false)}>OK</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}

export default TuningWizard;
