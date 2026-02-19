/**
 * SetupWizard - Main setup wizard orchestrator for Command Center
 * 
 * Three-step guided setup:
 * 1. Dyno Connection - Configure and test dyno network settings
 * 2. Bike Configuration - Enter vehicle details and engine parameters
 * 3. Tune Import - Import PVV file or use engine presets
 * 
 * Persists configuration to localStorage for session continuity.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Wifi, Bike, Upload, Check, ArrowRight, ArrowLeft, X, RotateCcw,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Progress } from '../ui/progress';
import { cn } from '../../lib/utils';

import { DynoConnectionSetup } from './DynoConnectionSetup';
import { BikeConfigForm } from './BikeConfigForm';
import { TuneImport, type TuneImportResult } from './TuneImport';
import {
  BikeConfig,
  DynoConnectionConfig,
  SetupWizardState,
  DEFAULT_BIKE_CONFIG,
  DEFAULT_DYNO_CONFIG,
  DEFAULT_SETUP_STATE,
} from '../../types/bikeConfig';
import { bikeConfigFromPreset } from '../../utils/enginePresets';

// Storage key for persisting setup state
const STORAGE_KEY = 'dynoai_setup_state';

type WizardStep = 'dyno' | 'bike' | 'tune' | 'complete';

interface StepConfig {
  id: WizardStep;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

const STEPS: StepConfig[] = [
  { id: 'dyno', title: 'Connect Dyno', description: 'Network settings', icon: Wifi },
  { id: 'bike', title: 'Configure Bike', description: 'Vehicle details', icon: Bike },
  { id: 'tune', title: 'Import Tune', description: 'VE tables & AFR', icon: Upload },
];

interface SetupWizardProps {
  /** Called when setup is complete with all configuration */
  onComplete: (state: {
    dynoConfig: DynoConnectionConfig;
    bikeConfig: BikeConfig;
    tuneImport: TuneImportResult | null;
  }) => void;
  /** Called when user dismisses the wizard */
  onDismiss?: () => void;
  /** API base URL for dyno connection */
  apiUrl?: string;
  /** Whether to show as modal overlay */
  isModal?: boolean;
  /** Initial state (for re-running setup) */
  initialState?: Partial<SetupWizardState>;
}

export function SetupWizard({
  onComplete,
  onDismiss,
  apiUrl = 'http://127.0.0.1:5001/api/jetdrive',
  isModal = true,
  initialState,
}: SetupWizardProps) {
  // Load saved state or use defaults
  const [state, setState] = useState<SetupWizardState>(() => {
    if (initialState) {
      return { ...DEFAULT_SETUP_STATE, ...initialState };
    }
    
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        return { ...DEFAULT_SETUP_STATE, ...parsed, currentStep: 'dyno' };
      }
    } catch {
      // Ignore parse errors
    }
    return DEFAULT_SETUP_STATE;
  });

  const [tuneImport, setTuneImport] = useState<TuneImportResult | null>(null);
  const [dynoConnected, setDynoConnected] = useState(false);
  
  // Use ref to always have latest tuneImport value in callbacks
  const tuneImportRef = useRef<TuneImportResult | null>(null);
  useEffect(() => {
    tuneImportRef.current = tuneImport;
  }, [tuneImport]);

  // Save state to localStorage on changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // Ignore storage errors
    }
  }, [state]);

  const currentStepIndex = STEPS.findIndex(s => s.id === state.currentStep);
  const progress = ((currentStepIndex + 1) / STEPS.length) * 100;

  const handleDynoConfigChange = useCallback((config: DynoConnectionConfig) => {
    setState(prev => ({ ...prev, dynoConfig: config }));
  }, []);

  const handleDynoConnectionSuccess = useCallback(() => {
    setDynoConnected(true);
    setState(prev => ({ ...prev, dynoConnected: true }));
  }, []);

  const handleBikeConfigChange = useCallback((config: BikeConfig) => {
    setState(prev => ({ ...prev, bikeConfig: config }));
  }, []);

  const handlePresetSelect = useCallback((presetKey: string) => {
    const bikeConfig = bikeConfigFromPreset(presetKey);
    if (bikeConfig) {
      setState(prev => ({ ...prev, bikeConfig }));
    }
  }, []);

  const handleTuneImport = useCallback((result: TuneImportResult) => {
    console.log('[SetupWizard] Tune imported:', {
      sourceName: result.sourceName,
      source: result.source,
      hasVeFront: !!result.veFront,
      hasVeRear: !!result.veRear,
      veFrontRows: result.veFront?.rows?.length,
      veFrontCols: result.veFront?.columns?.length,
      rpmBins: result.rpmBins,
      mapBins: result.mapBins,
    });
    setTuneImport(result);
    tuneImportRef.current = result; // Update ref immediately
  }, []);

  const goToStep = useCallback((step: WizardStep) => {
    setState(prev => ({ ...prev, currentStep: step }));
  }, []);

  const goNext = useCallback(() => {
    const nextIndex = currentStepIndex + 1;
    if (nextIndex < STEPS.length) {
      goToStep(STEPS[nextIndex].id);
    } else {
      // Complete - use ref to get latest tuneImport value
      const currentTuneImport = tuneImportRef.current;
      console.log('[SetupWizard] Completing setup with tuneImport:', {
        hasTuneImport: !!currentTuneImport,
        tuneImportFromRef: !!tuneImportRef.current,
        tuneImportFromState: !!tuneImport,
        sourceName: currentTuneImport?.sourceName,
        hasVeFront: !!currentTuneImport?.veFront,
        hasVeRear: !!currentTuneImport?.veRear,
        veFrontRows: currentTuneImport?.veFront?.rows?.length,
        veFrontValues: currentTuneImport?.veFront?.values?.length,
      });
      setState(prev => ({ ...prev, currentStep: 'complete', setupComplete: true }));
      onComplete({
        dynoConfig: state.dynoConfig,
        bikeConfig: state.bikeConfig,
        tuneImport: currentTuneImport,
      });
    }
  }, [currentStepIndex, goToStep, onComplete, state.dynoConfig, state.bikeConfig, tuneImport]);

  const goBack = useCallback(() => {
    const prevIndex = currentStepIndex - 1;
    if (prevIndex >= 0) {
      goToStep(STEPS[prevIndex].id);
    }
  }, [currentStepIndex, goToStep]);

  const handleSkipTune = useCallback(() => {
    setState(prev => ({ ...prev, currentStep: 'complete', setupComplete: true }));
    onComplete({
      dynoConfig: state.dynoConfig,
      bikeConfig: state.bikeConfig,
      tuneImport: null,
    });
  }, [onComplete, state.dynoConfig, state.bikeConfig]);

  const handleReset = useCallback(() => {
    setState(DEFAULT_SETUP_STATE);
    setTuneImport(null);
    setDynoConnected(false);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  const canProceed = useCallback(() => {
    switch (state.currentStep) {
      case 'dyno':
        return dynoConnected || state.dynoConnected;
      case 'bike':
        return state.bikeConfig.make && state.bikeConfig.displacement > 0;
      case 'tune':
        return true; // Can always proceed (skip or import)
      default:
        return false;
    }
  }, [state.currentStep, state.dynoConnected, state.bikeConfig, dynoConnected]);

  // Render step indicator
  const renderStepIndicator = () => (
    <div className="flex items-center justify-center gap-2 mb-8">
      {STEPS.map((step, idx) => {
        const isCurrent = state.currentStep === step.id;
        const isPast = currentStepIndex > idx;
        const Icon = step.icon;

        return (
          <div key={step.id} className="flex items-center">
            {idx > 0 && (
              <div
                className={cn(
                  'w-12 h-0.5 mx-2 transition-colors',
                  isPast ? 'bg-green-500' : 'bg-zinc-700'
                )}
              />
            )}
            <button
              onClick={() => isPast && goToStep(step.id)}
              disabled={!isPast}
              className={cn(
                'flex flex-col items-center gap-1 transition-all',
                isPast && 'cursor-pointer'
              )}
            >
              <div
                className={cn(
                  'w-12 h-12 rounded-full flex items-center justify-center transition-all',
                  isCurrent && 'bg-cyan-500 text-white ring-4 ring-cyan-500/20',
                  isPast && 'bg-green-500 text-white',
                  !isCurrent && !isPast && 'bg-zinc-800 text-zinc-500'
                )}
              >
                {isPast ? <Check className="w-5 h-5" /> : <Icon className="w-5 h-5" />}
              </div>
              <span
                className={cn(
                  'text-xs font-medium',
                  isCurrent && 'text-cyan-400',
                  isPast && 'text-green-400',
                  !isCurrent && !isPast && 'text-zinc-500'
                )}
              >
                {step.title}
              </span>
            </button>
          </div>
        );
      })}
    </div>
  );

  // Render current step content
  const renderStepContent = () => {
    switch (state.currentStep) {
      case 'dyno':
        return (
          <DynoConnectionSetup
            config={state.dynoConfig}
            onChange={handleDynoConfigChange}
            onConnectionSuccess={handleDynoConnectionSuccess}
            apiUrl={apiUrl}
          />
        );
      case 'bike':
        return (
          <BikeConfigForm
            config={state.bikeConfig}
            onChange={handleBikeConfigChange}
            onPresetSelect={handlePresetSelect}
          />
        );
      case 'tune':
        return (
          <div className="space-y-6">
            {/* Header */}
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center">
                <Upload className="w-8 h-8 text-purple-400" />
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">Import Your Tune</h2>
              <p className="text-zinc-400 text-sm max-w-md mx-auto">
                Import a PVV file from Power Vision to use your existing VE tables and AFR targets
              </p>
            </div>

            {/* Tune Import Component */}
            <TuneImport
              onImport={handleTuneImport}
              currentPreset="harley_m8"
            />

            {/* Import Status */}
            {tuneImport && (
              <Card className="bg-gradient-to-br from-green-500/10 to-emerald-500/10 border-green-500/30">
                <CardContent className="pt-4">
                  <div className="flex items-center gap-3">
                    <Check className="w-5 h-5 text-green-400" />
                    <div>
                      <p className="text-sm font-medium text-green-400">
                        {tuneImport.source === 'pvv'
                          ? 'PVV File Imported'
                          : tuneImport.source === 'yourdyno'
                            ? 'YourDyno Run Loaded'
                            : 'Preset Selected'}
                      </p>
                      <p className="text-xs text-zinc-400">{tuneImport.sourceName}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Skip Option */}
            <div className="text-center">
              <Button
                variant="ghost"
                onClick={handleSkipTune}
                className="text-zinc-400 hover:text-white"
              >
                Skip and use defaults
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  const content = (
    <div className="w-full max-w-2xl mx-auto">
      {/* Header with close button */}
      {isModal && (
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-white">Setup Wizard</h1>
            <p className="text-sm text-zinc-400">Configure your tuning session</p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReset}
              className="text-zinc-400 hover:text-white"
            >
              <RotateCcw className="w-4 h-4 mr-1" />
              Reset
            </Button>
            {onDismiss && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onDismiss}
                className="text-zinc-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Progress bar */}
      <Progress value={progress} className="h-1 mb-6" />

      {/* Step indicator */}
      {renderStepIndicator()}

      {/* Step content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={state.currentStep}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2 }}
        >
          {renderStepContent()}
        </motion.div>
      </AnimatePresence>

      {/* Navigation buttons */}
      <div className="flex items-center justify-between mt-8 pt-6 border-t border-zinc-800">
        <Button
          variant="outline"
          onClick={goBack}
          disabled={currentStepIndex === 0}
          className="border-zinc-700"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>

        <Button
          onClick={goNext}
          disabled={!canProceed()}
          className={cn(
            'min-w-[140px]',
            canProceed()
              ? 'bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500'
              : 'bg-zinc-700 cursor-not-allowed'
          )}
        >
          {state.currentStep === 'tune' ? (
            <>
              Complete Setup
              <Check className="w-4 h-4 ml-2" />
            </>
          ) : (
            <>
              Continue
              <ArrowRight className="w-4 h-4 ml-2" />
            </>
          )}
        </Button>
      </div>
    </div>
  );

  if (isModal) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        {/* Backdrop */}
        <div
          className="absolute inset-0 bg-black/80 backdrop-blur-sm"
          onClick={onDismiss}
        />
        
        {/* Modal content */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="relative z-10 w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-zinc-950 border border-zinc-800 rounded-2xl p-6 m-4 shadow-2xl"
        >
          {content}
        </motion.div>
      </div>
    );
  }

  return content;
}

export default SetupWizard;
