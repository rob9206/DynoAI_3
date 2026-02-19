/**
 * useTuningWizard - State management hook for the auto-tune wizard
 *
 * Manages:
 * - Wizard step progression
 * - Coverage tracking and auto-advance conditions
 * - Apply report generation
 * - Session timing
 */

import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import type { TuneImportResult } from '../components/jetdrive/TuneImport';
import type { LiveVEExportData } from '../components/jetdrive/LiveVETable';
import type {
  ApplyReport,
  CoverageReport,
  VEBoundsPreset,
} from '../types/veApplyTypes';
import {
  calculateDualCylinderCoverage,
  calculateApply,
  getApplySummary,
} from '../utils/veApply';

export type WizardStep = 'setup' | 'collect' | 'analyze' | 'review' | 'apply';

export interface WizardConfig {
  targetCoverage: number;
  targetHits: number;
  autoAdvance: boolean;
}

const DEFAULT_CONFIG: WizardConfig = {
  targetCoverage: 60,
  targetHits: 500,
  autoAdvance: true,
};

export interface UseTuningWizardOptions {
  importedTune: TuneImportResult | null;
  liveData: LiveVEExportData | null;
  isSimulatorActive: boolean;
  isCapturing: boolean;
  veBoundsPreset?: VEBoundsPreset;
  config?: Partial<WizardConfig>;
}

export interface UseTuningWizardReturn {
  // Current state
  step: WizardStep;
  coverageReport: CoverageReport | null;
  applyReport: ApplyReport | null;
  applySummary: ReturnType<typeof getApplySummary> | null;

  // Computed values
  isReady: boolean;
  canAdvance: boolean;
  canApply: boolean;

  // Session tracking
  sessionStartTime: number | null;
  sessionDuration: number;
  pullCount: number;

  // Actions
  setStep: (step: WizardStep) => void;
  advanceStep: () => void;
  goBack: () => void;
  reset: () => void;
  recordPull: () => void;

  // Analysis
  runAnalysis: () => Promise<ApplyReport | null>;
}

export function useTuningWizard({
  importedTune,
  liveData,
  isSimulatorActive,
  isCapturing,
  veBoundsPreset = 'na_harley',
  config: userConfig,
}: UseTuningWizardOptions): UseTuningWizardReturn {
  const config = { ...DEFAULT_CONFIG, ...userConfig };

  // Core state
  const [step, setStep] = useState<WizardStep>('setup');
  const [applyReport, setApplyReport] = useState<ApplyReport | null>(null);

  // Session tracking
  const [sessionStartTime, setSessionStartTime] = useState<number | null>(null);
  const [pullCount, setPullCount] = useState(0);
  const prevCoverageRef = useRef<number>(0);

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

  const totalHits = liveData?.totalHits ?? 0;
  const weightedCoverage = coverageReport?.weightedCoveragePct ?? 0;

  // Computed values
  const isReady = weightedCoverage >= config.targetCoverage && totalHits >= config.targetHits;

  const canAdvance = useMemo(() => {
    switch (step) {
      case 'setup':
        return !!importedTune && (isSimulatorActive || isCapturing);
      case 'collect':
        return isReady || totalHits > 50; // Allow manual advance with some data
      case 'analyze':
        return !!applyReport;
      case 'review':
        return applyReport?.blockReasons.length === 0;
      case 'apply':
        return true;
      default:
        return false;
    }
  }, [step, importedTune, isSimulatorActive, isCapturing, isReady, totalHits, applyReport]);

  const canApply = applyReport?.blockReasons.length === 0;

  const applySummary = useMemo(() => {
    if (!applyReport) return null;
    return getApplySummary(applyReport);
  }, [applyReport]);

  // Session duration
  const sessionDuration = useMemo(() => {
    if (!sessionStartTime) return 0;
    return Math.floor((Date.now() - sessionStartTime) / 1000);
  }, [sessionStartTime]);

  // Auto-start session timer when entering collect step
  useEffect(() => {
    if (step === 'collect' && !sessionStartTime) {
      setSessionStartTime(Date.now());
    }
  }, [step, sessionStartTime]);

  // Auto-advance from setup to collect
  useEffect(() => {
    if (
      config.autoAdvance &&
      step === 'setup' &&
      importedTune &&
      (isSimulatorActive || isCapturing)
    ) {
      setStep('collect');
    }
  }, [config.autoAdvance, step, importedTune, isSimulatorActive, isCapturing]);

  // Track coverage milestones (for voice feedback)
  useEffect(() => {
    const prev = prevCoverageRef.current;
    const curr = weightedCoverage;

    if (prev < 50 && curr >= 50) {
      // 50% milestone
      console.log('[Wizard] Coverage milestone: 50%');
    } else if (prev < 75 && curr >= 75) {
      // 75% milestone
      console.log('[Wizard] Coverage milestone: 75%');
    } else if (prev < config.targetCoverage && curr >= config.targetCoverage) {
      // Ready milestone
      console.log('[Wizard] Coverage target reached:', curr);
    }

    prevCoverageRef.current = curr;
  }, [weightedCoverage, config.targetCoverage]);

  // Actions
  const advanceStep = useCallback(() => {
    const order: WizardStep[] = ['setup', 'collect', 'analyze', 'review', 'apply'];
    const currentIdx = order.indexOf(step);
    if (currentIdx < order.length - 1 && canAdvance) {
      setStep(order[currentIdx + 1]);
    }
  }, [step, canAdvance]);

  const goBack = useCallback(() => {
    const order: WizardStep[] = ['setup', 'collect', 'analyze', 'review', 'apply'];
    const currentIdx = order.indexOf(step);
    if (currentIdx > 0) {
      setStep(order[currentIdx - 1]);
    }
  }, [step]);

  const reset = useCallback(() => {
    setStep('setup');
    setApplyReport(null);
    setSessionStartTime(null);
    setPullCount(0);
    prevCoverageRef.current = 0;
  }, []);

  const recordPull = useCallback(() => {
    setPullCount((prev) => prev + 1);
  }, []);

  const runAnalysis = useCallback(async (): Promise<ApplyReport | null> => {
    if (!importedTune || !liveData) {
      console.warn('[Wizard] Cannot analyze: missing tune or live data');
      return null;
    }

    const baseVE = {
      front: importedTune.veFront?.values ?? [],
      rear: importedTune.veRear?.values ?? [],
    };

    const corrections = {
      front: liveData.frontCorrections,
      rear: liveData.rearCorrections,
    };

    const hitCounts = {
      front: liveData.frontHitCounts,
      rear: liveData.rearHitCounts,
    };

    const report = calculateApply(
      baseVE,
      corrections,
      hitCounts,
      liveData.rpmBins,
      liveData.mapBins,
      veBoundsPreset
    );

    setApplyReport(report);
    return report;
  }, [importedTune, liveData, veBoundsPreset]);

  return {
    // State
    step,
    coverageReport,
    applyReport,
    applySummary,

    // Computed
    isReady,
    canAdvance,
    canApply: canApply ?? false,

    // Session
    sessionStartTime,
    sessionDuration,
    pullCount,

    // Actions
    setStep,
    advanceStep,
    goBack,
    reset,
    recordPull,
    runAnalysis,
  };
}

export default useTuningWizard;
