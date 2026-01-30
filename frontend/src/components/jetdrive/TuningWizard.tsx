/**
 * TuningWizard - Main auto-tune workflow orchestrator
 *
 * Provides a guided, step-by-step tuning experience with:
 * - Big button primary actions for dyno operators
 * - Progressive disclosure (details hidden until needed)
 * - Voice feedback instead of text clutter
 * - Auto-advance between steps when conditions are met
 */

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Play, Pause, ArrowRight, Download, Check, AlertCircle, RefreshCw, ChevronDown, ChevronUp, Settings, Zap } from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { cn } from '../../lib/utils';

// Types
import type { TuneImportResult } from './TuneImport';
import type { LiveVEExportData } from './LiveVETable';
import type { ApplyReport, VEBoundsPreset, CoverageReport } from '../../types/veApplyTypes';

// Core engine
import { calculateDualCylinderCoverage, getCoverageGrade, calculateApply, getApplySummary } from '../../utils/veApply';

export type WizardStep = 'setup' | 'collect' | 'analyze' | 'review' | 'apply';

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
  // External state
  isSimulatorActive: boolean;
  isCapturing: boolean;
  importedTune: TuneImportResult | null;
  liveData: LiveVEExportData | null;
  
  // Callbacks
  onStartSimulator: () => void;
  onStopSimulator: () => void;
  onStartCapture: () => void;
  onStopCapture: () => void;
  onTriggerPull: () => void;
  onAnalyze: () => Promise<void>;
  onApply: (report: ApplyReport) => void;
  onReset: () => void;
  
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
  importedTune,
  liveData,
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
  // Wizard state
  const [step, setStep] = useState<WizardStep>('setup');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [applyReport, setApplyReport] = useState<ApplyReport | null>(null);
  
  // Calculate coverage from live data
  const coverageReport = useMemo(() => {
    if (!liveData?.frontHitCounts || !liveData?.rearHitCounts) return null;
    return calculateDualCylinderCoverage(
      liveData.frontHitCounts,
      liveData.rearHitCounts,
      liveData.rpmBins,
      liveData.mapBins
    );
  }, [liveData]);
  
  // Coverage percentage for display
  const coveragePct = coverageReport?.weightedCoveragePct ?? 0;
  const totalHits = liveData?.totalHits ?? 0;
  const coverageGrade = useMemo(() => getCoverageGrade(coveragePct), [coveragePct]);
  
  // Auto-advance: Setup -> Collect
  useEffect(() => {
    if (step === 'setup' && importedTune && (isSimulatorActive || isCapturing)) {
      setStep('collect');
    }
  }, [step, importedTune, isSimulatorActive, isCapturing]);
  
  // Check if ready to proceed from Collect
  const canProceedToAnalyze = coveragePct >= COVERAGE_TARGET && totalHits >= MIN_HITS_TARGET;
  
  // Handle analyze step
  const handleAnalyze = useCallback(async () => {
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
      }
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
  
  // Get apply summary
  const applySummary = useMemo(() => {
    if (!applyReport) return null;
    return getApplySummary(applyReport);
  }, [applyReport]);
  
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
          <span className="text-4xl font-bold text-white">{coveragePct.toFixed(0)}%</span>
          <span className="text-sm text-zinc-400">Coverage</span>
          <Badge className={cn("mt-1", coverageGrade.color)}>
            {coverageGrade.grade}
          </Badge>
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
            onClick={isSimulatorActive ? onStopSimulator : onStartSimulator}
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
          <div className="space-y-4">
            {/* Primary: Trigger Pull or Analyze */}
            {canProceedToAnalyze ? (
              <Button
                onClick={handleAnalyze}
                size="lg"
                className="w-64 h-20 text-xl font-bold rounded-2xl bg-gradient-to-r from-green-600 to-green-500 hover:from-green-500 hover:to-green-400 shadow-lg shadow-green-500/25 animate-pulse"
              >
                <ArrowRight className="w-6 h-6 mr-3" />
                ANALYZE
              </Button>
            ) : (
              <Button
                onClick={onTriggerPull}
                size="lg"
                className="w-64 h-20 text-xl font-bold rounded-2xl bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-500 hover:to-red-500 shadow-lg shadow-orange-500/25"
              >
                <Zap className="w-6 h-6 mr-3" />
                RUN PULL
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
  
  // Render details (expanded view)
  const renderDetails = () => {
    if (!showDetails) return null;
    
    return (
      <div className="mt-6 p-4 bg-zinc-900/50 rounded-xl border border-zinc-800">
        {step === 'collect' && renderLiveTable?.()}
        {step === 'review' && applyReport && renderApplyPreview?.(applyReport)}
        
        {/* Coverage breakdown */}
        {step === 'collect' && coverageReport && (
          <div className="grid grid-cols-2 gap-4 mt-4">
            {coverageReport.zoneBreakdown.map(zone => (
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
        
        {/* Main content area */}
        <div className="flex flex-col items-center py-8">
          {/* Progress ring (collect step only) */}
          {step === 'collect' && renderProgressRing()}
          
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
    </Card>
  );
}

export default TuningWizard;
